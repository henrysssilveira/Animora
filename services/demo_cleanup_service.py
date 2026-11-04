from pathlib import Path
from typing import Any

import click

from config import Config
from services.supabase_service import (
    MigrationRequiredError,
    SupabaseServiceError,
    TagMigrationRequiredError,
    get_supabase_client,
    translate_supabase_error,
)

# UUIDs fixos definidos em database/seeds/002_demo_data.sql
DEMO_ANIMAL_IDS: tuple[str, ...] = (
    "88888888-8888-4888-8888-000000000001",
    "88888888-8888-4888-8888-000000000002",
    "88888888-8888-4888-8888-000000000003",
    "88888888-8888-4888-8888-000000000004",
    "88888888-8888-4888-8888-000000000005",
)

DEMO_QR_TOKENS: tuple[str, ...] = (
    "99999999-9999-4999-8999-000000000001",
    "99999999-9999-4999-8999-000000000002",
    "99999999-9999-4999-8999-000000000003",
    "99999999-9999-4999-8999-000000000004",
    "99999999-9999-4999-8999-000000000005",
)

DEMO_VACCINE_IDS: tuple[str, ...] = (
    "55555555-5555-4555-8555-000000000001",
    "55555555-5555-4555-8555-000000000002",
    "55555555-5555-4555-8555-000000000003",
)

DEMO_PROTOCOL_IDS: tuple[str, ...] = (
    "66666666-6666-4666-8666-000000000001",
    "66666666-6666-4666-8666-000000000002",
)

DEMO_RULE_IDS: tuple[str, ...] = (
    "77777777-7777-4777-8777-000000000001",
    "77777777-7777-4777-8777-000000000002",
    "77777777-7777-4777-8777-000000000003",
    "77777777-7777-4777-8777-000000000004",
)

DEMO_CAMPAIGN_IDS: tuple[str, ...] = (
    "aaaaaaaa-aaaa-4aaa-8aaa-000000000001",
)

DEMO_SCHEDULE_IDS: tuple[str, ...] = (
    "bbbbbbbb-bbbb-4bbb-8bbb-000000000001",
    "bbbbbbbb-bbbb-4bbb-8bbb-000000000002",
    "bbbbbbbb-bbbb-4bbb-8bbb-000000000003",
    "bbbbbbbb-bbbb-4bbb-8bbb-000000000004",
    "bbbbbbbb-bbbb-4bbb-8bbb-000000000005",
    "bbbbbbbb-bbbb-4bbb-8bbb-000000000006",
    "bbbbbbbb-bbbb-4bbb-8bbb-000000000007",
    "bbbbbbbb-bbbb-4bbb-8bbb-000000000008",
)

DEMO_VACCINATION_RECORD_IDS: tuple[str, ...] = (
    "cccccccc-cccc-4ccc-8ccc-000000000001",
    "cccccccc-cccc-4ccc-8ccc-000000000002",
    "cccccccc-cccc-4ccc-8ccc-000000000003",
)

DEMO_HEALTH_RECORD_IDS: tuple[str, ...] = (
    "dddddddd-dddd-4ddd-8ddd-000000000001",
    "dddddddd-dddd-4ddd-8ddd-000000000002",
)

DEMO_LOT_IDS: tuple[str, ...] = (
    "44444444-4444-4444-8444-000000000001",
    "44444444-4444-4444-8444-000000000002",
    "44444444-4444-4444-8444-000000000003",
    "44444444-4444-4444-8444-000000000004",
)

# Propriedade adicional inserida exclusivamente pelo seed 002 (Fazenda Sede 2222...2222 é mantida)
DEMO_EXTRA_PROPERTY_ID: str = "22222222-2222-4222-8222-222222222223"


def _unique_ids(*iterables: list[str] | set[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for group in iterables:
        for item in group:
            if item and item not in seen:
                seen.add(item)
                ordered.append(item)
    return ordered


def _select_ids_in(client, table: str, column: str, values: list[str] | tuple[str, ...]) -> list[str]:
    if not values:
        return []
    rows = client.table(table).select("id").in_(column, list(values)).execute().data or []
    return [r["id"] for r in rows if r.get("id")]


def _delete_by_ids(client, table: str, ids: list[str]) -> int:
    if not ids:
        return 0
    total = 0
    chunk_size = 100
    for idx in range(0, len(ids), chunk_size):
        batch = ids[idx : idx + chunk_size]
        res = client.table(table).delete().in_("id", batch).execute()
        total += len(res.data or batch)
    return total


def _find_demo_qrcode_files(extra_tokens: list[str]) -> list[Path]:
    qrcodes_dir = Config.QRCODES_DIR
    if not qrcodes_dir.exists():
        return []

    candidate_tokens = _unique_ids(DEMO_QR_TOKENS, extra_tokens)
    existing_files: list[Path] = []
    for token in candidate_tokens:
        png_path = qrcodes_dir / f"{token}.png"
        if png_path.is_file():
            existing_files.append(png_path)
    return existing_files


def inspect_demo_data() -> dict[str, Any]:
    """
    Mapeia todos os registros demonstrativos presentes no Supabase e arquivos QR locais,
    verificando vínculos reais antes de marcar lotes ou a propriedade extra para exclusão.
    """
    client = get_supabase_client()
    plan: dict[str, Any] = {
        "sanitary_ready": True,
        "tags_ready": True,
        "animals": [],
        "qr_files": [],
        "vaccines": [],
        "protocols": [],
        "protocol_rules": [],
        "animal_protocols": [],
        "campaigns": [],
        "schedules": [],
        "vaccination_records": [],
        "health_records": [],
        "tag_units_to_release": [],
        "lots_to_delete": [],
        "lots_preserved": [],
        "delete_extra_property": False,
        "extra_property_preserved": False,
    }

    try:
        animals_by_id = (
            client.table("animals")
            .select("id, ear_tag, qr_code_token")
            .in_("id", list(DEMO_ANIMAL_IDS))
            .execute()
            .data
            or []
        )
        animals_by_tag = (
            client.table("animals")
            .select("id, ear_tag, qr_code_token")
            .like("ear_tag", "DEMO-%")
            .execute()
            .data
            or []
        )
    except Exception as exc:
        raise translate_supabase_error(exc) from exc

    demo_animals_map = {row["id"]: row for row in (*animals_by_id, *animals_by_tag) if row.get("id")}
    demo_animal_ids = list(demo_animals_map.keys())
    demo_tokens = [
        str(row["qr_code_token"])
        for row in demo_animals_map.values()
        if row.get("qr_code_token")
    ]

    plan["animals"] = demo_animal_ids
    plan["qr_files"] = _find_demo_qrcode_files(demo_tokens)

    # Inspeção das tabelas do Módulo Sanitário (caso migration 001 esteja aplicada)
    try:
        vac_by_id = _select_ids_in(client, "vaccines", "id", DEMO_VACCINE_IDS)
        vac_by_name = [
            r["id"]
            for r in (
                client.table("vaccines")
                .select("id")
                .ilike("commercial_name", "%[DEMO]%")
                .execute()
                .data
                or []
            )
            if r.get("id")
        ]
        demo_vaccine_ids = _unique_ids(vac_by_id, vac_by_name)
        plan["vaccines"] = demo_vaccine_ids

        proto_by_id = _select_ids_in(client, "sanitary_protocols", "id", DEMO_PROTOCOL_IDS)
        proto_by_name = [
            r["id"]
            for r in (
                client.table("sanitary_protocols")
                .select("id")
                .ilike("name", "%[DEMO]%")
                .execute()
                .data
                or []
            )
            if r.get("id")
        ]
        demo_protocol_ids = _unique_ids(proto_by_id, proto_by_name)
        plan["protocols"] = demo_protocol_ids

        demo_rule_ids = _unique_ids(
            _select_ids_in(client, "sanitary_protocol_rules", "id", DEMO_RULE_IDS),
            _select_ids_in(client, "sanitary_protocol_rules", "protocol_id", demo_protocol_ids),
            _select_ids_in(client, "sanitary_protocol_rules", "vaccine_id", demo_vaccine_ids),
        )
        plan["protocol_rules"] = demo_rule_ids

        camp_by_name = [
            r["id"]
            for r in (
                client.table("vaccination_campaigns")
                .select("id")
                .ilike("name", "%[DEMO]%")
                .execute()
                .data
                or []
            )
            if r.get("id")
        ]
        demo_campaign_ids = _unique_ids(
            _select_ids_in(client, "vaccination_campaigns", "id", DEMO_CAMPAIGN_IDS),
            camp_by_name,
            _select_ids_in(client, "vaccination_campaigns", "vaccine_id", demo_vaccine_ids),
        )
        plan["campaigns"] = demo_campaign_ids

        plan["animal_protocols"] = _unique_ids(
            _select_ids_in(client, "animal_protocols", "animal_id", demo_animal_ids),
            _select_ids_in(client, "animal_protocols", "protocol_id", demo_protocol_ids),
        )

        plan["schedules"] = _unique_ids(
            _select_ids_in(client, "vaccination_schedules", "id", DEMO_SCHEDULE_IDS),
            _select_ids_in(client, "vaccination_schedules", "animal_id", demo_animal_ids),
            _select_ids_in(client, "vaccination_schedules", "campaign_id", demo_campaign_ids),
            _select_ids_in(client, "vaccination_schedules", "protocol_id", demo_protocol_ids),
            _select_ids_in(client, "vaccination_schedules", "protocol_rule_id", demo_rule_ids),
            _select_ids_in(client, "vaccination_schedules", "vaccine_id", demo_vaccine_ids),
        )

        plan["vaccination_records"] = _unique_ids(
            _select_ids_in(client, "vaccination_records", "id", DEMO_VACCINATION_RECORD_IDS),
            _select_ids_in(client, "vaccination_records", "animal_id", demo_animal_ids),
            _select_ids_in(client, "vaccination_records", "vaccine_id", demo_vaccine_ids),
            _select_ids_in(client, "vaccination_records", "campaign_id", demo_campaign_ids),
        )

        plan["health_records"] = _unique_ids(
            _select_ids_in(client, "health_records", "id", DEMO_HEALTH_RECORD_IDS),
            _select_ids_in(client, "health_records", "animal_id", demo_animal_ids),
        )

        # Lotes demo: só remove aqueles sem vínculo com animais/campanhas reais
        existing_demo_lots = (
            client.table("lots")
            .select("id, name")
            .in_("id", list(DEMO_LOT_IDS))
            .execute()
            .data
            or []
        )
        demo_animal_set = set(demo_animal_ids)
        demo_campaign_set = set(demo_campaign_ids)

        for lot in existing_demo_lots:
            lot_id = lot["id"]
            lot_animals = (
                client.table("animals").select("id").eq("lot_id", lot_id).execute().data or []
            )
            lot_campaigns = (
                client.table("vaccination_campaigns")
                .select("id")
                .eq("lot_id", lot_id)
                .execute()
                .data
                or []
            )
            has_real_animals = any(a["id"] not in demo_animal_set for a in lot_animals)
            has_real_campaigns = any(c["id"] not in demo_campaign_set for c in lot_campaigns)
            if has_real_animals or has_real_campaigns:
                plan["lots_preserved"].append(lot)
            else:
                plan["lots_to_delete"].append(lot_id)

        # Propriedade extra do seed 002 ("Estância Santa Clara")
        prop_rows = (
            client.table("properties")
            .select("id, name")
            .eq("id", DEMO_EXTRA_PROPERTY_ID)
            .execute()
            .data
            or []
        )
        if prop_rows:
            deleting_sets: dict[str, set[str]] = {
                "animals": demo_animal_set,
                "lots": set(plan["lots_to_delete"]),
                "sanitary_protocols": set(demo_protocol_ids),
                "animal_protocols": set(plan["animal_protocols"]),
                "vaccination_campaigns": demo_campaign_set,
                "vaccination_schedules": set(plan["schedules"]),
                "vaccination_records": set(plan["vaccination_records"]),
                "health_records": set(plan["health_records"]),
                "organization_members": set(),
            }
            in_use = False
            for tbl, excluded_ids in deleting_sets.items():
                refs = (
                    client.table(tbl)
                    .select("id")
                    .eq("property_id", DEMO_EXTRA_PROPERTY_ID)
                    .execute()
                    .data
                    or []
                )
                if any(r["id"] not in excluded_ids for r in refs):
                    in_use = True
                    break

            if not in_use:
                try:
                    batch_refs = (
                        client.table("tag_batches")
                        .select("id")
                        .eq("property_id", DEMO_EXTRA_PROPERTY_ID)
                        .limit(1)
                        .execute()
                        .data
                        or []
                    )
                    if batch_refs:
                        in_use = True
                except Exception as tag_exc:
                    translated = translate_supabase_error(tag_exc)
                    if not isinstance(translated, TagMigrationRequiredError):
                        raise translated from tag_exc

            if in_use:
                plan["extra_property_preserved"] = True
            else:
                plan["delete_extra_property"] = True

    except Exception as exc:
        err = translate_supabase_error(exc)
        if isinstance(err, MigrationRequiredError) and not isinstance(err, TagMigrationRequiredError):
            plan["sanitary_ready"] = False
        else:
            raise err from exc

    # Inspeção de etiquetas vinculadas a animais demo (caso migration 003 esteja aplicada)
    if demo_animal_ids:
        try:
            plan["tag_units_to_release"] = _select_ids_in(
                client, "tag_units", "animal_id", demo_animal_ids
            )
        except Exception as exc:
            err = translate_supabase_error(exc)
            if isinstance(err, TagMigrationRequiredError):
                plan["tags_ready"] = False
            else:
                raise err from exc

    return plan


def has_pending_demo_items(plan: dict[str, Any], include_qrcodes: bool = True) -> bool:
    keys = (
        "health_records",
        "vaccination_records",
        "schedules",
        "campaigns",
        "animal_protocols",
        "protocol_rules",
        "protocols",
        "vaccines",
        "tag_units_to_release",
        "animals",
        "lots_to_delete",
    )
    if any(bool(plan.get(k)) for k in keys) or bool(plan.get("delete_extra_property")):
        return True
    if include_qrcodes and bool(plan.get("qr_files")):
        return True
    return False


def execute_demo_cleanup(
    plan: dict[str, Any] | None = None,
    remove_qrcodes: bool = True,
) -> dict[str, Any]:
    """
    Executa a remoção dos dados demonstrativos respeitando rigorosamente as restrições
    ON DELETE RESTRICT do PostgreSQL e preservando quaisquer dados reais existentes.
    """
    active_plan = plan or inspect_demo_data()
    client = get_supabase_client()
    counts: dict[str, int] = {
        "health_records": 0,
        "vaccination_records": 0,
        "schedules": 0,
        "campaigns": 0,
        "animal_protocols": 0,
        "protocol_rules": 0,
        "protocols": 0,
        "vaccines": 0,
        "tag_units_released": 0,
        "animals": 0,
        "lots": 0,
        "properties": 0,
        "qr_files": 0,
    }

    try:
        if active_plan.get("sanitary_ready"):
            counts["health_records"] = _delete_by_ids(
                client, "health_records", active_plan["health_records"]
            )
            counts["vaccination_records"] = _delete_by_ids(
                client, "vaccination_records", active_plan["vaccination_records"]
            )
            counts["schedules"] = _delete_by_ids(
                client, "vaccination_schedules", active_plan["schedules"]
            )
            counts["campaigns"] = _delete_by_ids(
                client, "vaccination_campaigns", active_plan["campaigns"]
            )
            counts["animal_protocols"] = _delete_by_ids(
                client, "animal_protocols", active_plan["animal_protocols"]
            )
            counts["protocol_rules"] = _delete_by_ids(
                client, "sanitary_protocol_rules", active_plan["protocol_rules"]
            )
            counts["protocols"] = _delete_by_ids(
                client, "sanitary_protocols", active_plan["protocols"]
            )
            counts["vaccines"] = _delete_by_ids(
                client, "vaccines", active_plan["vaccines"]
            )

        if active_plan.get("tags_ready") and active_plan.get("tag_units_to_release"):
            res = (
                client.table("tag_units")
                .update(
                    {
                        "animal_id": None,
                        "status": "available",
                        "assigned_at": None,
                        "activated_at": None,
                    }
                )
                .in_("id", active_plan["tag_units_to_release"])
                .execute()
            )
            counts["tag_units_released"] = len(
                res.data or active_plan["tag_units_to_release"]
            )

        counts["animals"] = _delete_by_ids(client, "animals", active_plan["animals"])

        if active_plan.get("sanitary_ready"):
            # Revalida ausência de vínculos reais antes de apagar cada lote demo
            safe_lots: list[str] = []
            for lot_id in active_plan["lots_to_delete"]:
                rem_animals = (
                    client.table("animals")
                    .select("id")
                    .eq("lot_id", lot_id)
                    .limit(1)
                    .execute()
                    .data
                )
                rem_campaigns = (
                    client.table("vaccination_campaigns")
                    .select("id")
                    .eq("lot_id", lot_id)
                    .limit(1)
                    .execute()
                    .data
                )
                if not rem_animals and not rem_campaigns:
                    safe_lots.append(lot_id)
            counts["lots"] = _delete_by_ids(client, "lots", safe_lots)

            if active_plan.get("delete_extra_property"):
                counts["properties"] = _delete_by_ids(
                    client, "properties", [DEMO_EXTRA_PROPERTY_ID]
                )
    except Exception as exc:
        raise translate_supabase_error(exc) from exc

    if remove_qrcodes:
        for png_path in active_plan.get("qr_files", []):
            try:
                if Path(png_path).exists():
                    Path(png_path).unlink()
                    counts["qr_files"] += 1
            except OSError:
                pass

    return {
        "counts": counts,
        "lots_preserved": active_plan.get("lots_preserved", []),
        "extra_property_preserved": active_plan.get("extra_property_preserved", False),
    }


def run_clean_demo_cli(dry_run: bool = False, yes: bool = False, keep_qrcodes: bool = False) -> None:
    """Interface de linha de comando compartilhada entre `flask clean-demo` e execução direta."""
    click.secho("\n[BoviTrack] Inspecionando dados demonstrativos (Seed 002)...", fg="cyan", bold=True)

    try:
        plan = inspect_demo_data()
    except SupabaseServiceError as exc:
        raise click.ClickException(str(exc)) from exc

    include_qrcodes = not keep_qrcodes
    if not has_pending_demo_items(plan, include_qrcodes=include_qrcodes):
        click.secho("Nenhum dado demonstrativo pendente foi encontrado. Seu banco já está limpo!", fg="green")
        return

    summary_rows = [
        ("Ocorrências clínicas (health_records)", len(plan["health_records"])),
        ("Aplicações vacinais (vaccination_records)", len(plan["vaccination_records"])),
        ("Agendamentos sanitários (vaccination_schedules)", len(plan["schedules"])),
        ("Campanhas [DEMO] (vaccination_campaigns)", len(plan["campaigns"])),
        ("Vínculos animal x protocolo (animal_protocols)", len(plan["animal_protocols"])),
        ("Regras de protocolo [DEMO] (sanitary_protocol_rules)", len(plan["protocol_rules"])),
        ("Protocolos [DEMO] (sanitary_protocols)", len(plan["protocols"])),
        ("Vacinas fictícias [DEMO] (vaccines)", len(plan["vaccines"])),
        ("Etiquetas a liberar (tag_units)", len(plan["tag_units_to_release"])),
        ("Animais DEMO-* (animals)", len(plan["animals"])),
        ("Lotes demo sem uso real (lots)", len(plan["lots_to_delete"])),
        ("Propriedade 'Estância Santa Clara' (properties)", 1 if plan["delete_extra_property"] else 0),
    ]
    if include_qrcodes:
        summary_rows.append(("Arquivos PNG de QR Code demo (static/qrcodes)", len(plan["qr_files"])))

    click.echo("\nItens identificados para limpeza:")
    for label, qty in summary_rows:
        if qty > 0:
            click.echo(f"  - {label}: {click.style(str(qty), fg='yellow', bold=True)}")

    if plan["lots_preserved"]:
        preserved_names = ", ".join(l.get("name", l["id"]) for l in plan["lots_preserved"])
        click.secho(
            f"\nNota: Lote(s) preservado(s) por possuírem vínculos reais: {preserved_names}",
            fg="blue",
        )
    if plan["extra_property_preserved"]:
        click.secho(
            "Nota: 'Estância Santa Clara' será preservada pois possui registros reais vinculados.",
            fg="blue",
        )

    click.echo("  * 'Fazenda Sede BoviTrack' e todos os seus animais/registros reais serão mantidos.")

    if dry_run:
        click.secho("\n[Modo --dry-run] Nenhuma alteração foi realizada no banco ou nos arquivos.", fg="cyan")
        return

    if not yes:
        click.echo("")
        if not click.confirm("Deseja confirmar a remoção definitiva desses dados demonstrativos?", default=False):
            click.secho("Operação cancelada.", fg="yellow")
            return

    try:
        result = execute_demo_cleanup(plan=plan, remove_qrcodes=include_qrcodes)
    except SupabaseServiceError as exc:
        raise click.ClickException(str(exc)) from exc

    counts = result["counts"]
    total_db_changes = sum(v for k, v in counts.items() if k != "qr_files")
    click.secho(
        f"\nLimpeza concluída com sucesso! ({total_db_changes} registro(s) demo processados no Supabase"
        + (f", {counts['qr_files']} QR Code(s) PNG removidos" if include_qrcodes else "")
        + ").",
        fg="green",
        bold=True,
    )


@click.command("clean-demo")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Apenas lista o que seria removido, sem alterar o banco de dados.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Executa a limpeza sem solicitar confirmação interativa.",
)
@click.option(
    "--keep-qrcodes",
    is_flag=True,
    help="Mantém os arquivos PNG dos QR Codes demo em static/qrcodes.",
)
def clean_demo_command(dry_run: bool, yes: bool, keep_qrcodes: bool) -> None:
    """Remove os dados demonstrativos (Seed 002 / [DEMO]) preservando cadastros reais."""
    run_clean_demo_cli(dry_run=dry_run, yes=yes, keep_qrcodes=keep_qrcodes)


if __name__ == "__main__":
    clean_demo_command()
