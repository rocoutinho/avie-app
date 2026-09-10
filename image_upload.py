"""Upload de imagem via Cloudinary — perfil, looks, closet.

Sem CLOUDINARY_URL configurado (ambiente local sem conta Cloudinary, ou
antes de contratar), `upload_image` não faz nada e devolve None — os
formulários caem de volta pro campo de link externo manual, mesmo padrão
MAIL_SERVER-gated no-op usado em emails.py. Configure CLOUDINARY_URL no
.env (formato "cloudinary://<api_key>:<api_secret>@<cloud_name>", copiado
direto do dashboard Cloudinary) quando tiver uma conta.
"""

import cloudinary
import cloudinary.uploader
from flask import current_app


def upload_image(file_storage):
    """Recebe um FileStorage (campo de upload do formulário) e devolve a
    URL segura da imagem no Cloudinary, ou None se não configurado ou se o
    upload falhar — nunca levanta exceção pro chamador (mesmo espírito dos
    envios de e-mail: um provedor externo fora do ar não pode quebrar o
    cadastro do cliente)."""
    if not file_storage or not file_storage.filename:
        return None

    cloudinary_url = current_app.config.get("CLOUDINARY_URL")
    if not cloudinary_url:
        current_app.logger.info(
            "[upload simulado] Imagem '%s' não enviada — configure CLOUDINARY_URL "
            "no .env para enviar de verdade.",
            file_storage.filename,
        )
        return None

    try:
        cloudinary.config(cloudinary_url=cloudinary_url)
        result = cloudinary.uploader.upload(file_storage, folder="avie")
        return result.get("secure_url")
    except Exception:
        current_app.logger.exception("Falha ao enviar imagem '%s' pro Cloudinary", file_storage.filename)
        return None
