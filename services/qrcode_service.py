from pathlib import Path
import qrcode
from qrcode.constants import ERROR_CORRECT_Q

from config import Config


def build_animal_public_url(qr_code_token: str, base_url: str) -> str:
    """
    Monta a URL pública de identificação do animal na plataforma Animora.
    O QR Code contém exclusivamente a URL de identificação segura.
    """
    clean_base = (Config.APP_BASE_URL or base_url or "http://localhost:5000").rstrip("/")
    return f"{clean_base}/animal/{qr_code_token}"


def get_qrcode_file_path(qr_code_token: str) -> Path:
    """Retorna o caminho absoluto do arquivo PNG do QR Code."""
    Config.QRCODES_DIR.mkdir(parents=True, exist_ok=True)
    return Config.QRCODES_DIR / f"{qr_code_token}.png"


def generate_animal_qrcode(qr_code_token: str, base_url: str) -> tuple[Path, str]:
    """
    Gera o arquivo PNG do QR Code exclusivo do animal em alto contraste (Pitch Black sobre branco).
    Retorna uma tupla (caminho_arquivo_png, url_codificada).
    """
    target_url = build_animal_public_url(qr_code_token, base_url)
    file_path = get_qrcode_file_path(qr_code_token)

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_Q,
        box_size=10,
        border=4,
    )
    qr.add_data(target_url)
    qr.make(fit=True)

    image = qr.make_image(fill_color="#070600", back_color="#FFFFFF")
    image.save(file_path, format="PNG")

    return file_path, target_url


def ensure_qrcode_exists(qr_code_token: str, base_url: str) -> tuple[Path, str]:
    """
    Garante que a imagem PNG do QR Code exista em disco (regerando-a se necessário).
    """
    target_url = build_animal_public_url(qr_code_token, base_url)
    file_path = get_qrcode_file_path(qr_code_token)

    if not file_path.exists():
        return generate_animal_qrcode(qr_code_token, base_url)

    return file_path, target_url
