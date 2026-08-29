"""Envio de e-mails transacionais.

Sem MAIL_SERVER configurado (ambiente local, ou antes de contratar um
provedor de e-mail), as mensagens só são registradas no log — o formulário
público continua funcionando normalmente. Configure MAIL_* no .env quando
tiver um provedor (Gmail com senha de app, Resend, SendGrid etc.).
"""

from flask import current_app, render_template
from flask_mail import Message

from extensions import mail


def send_diagnostic_confirmation(client):
    if not current_app.config.get("MAIL_SERVER"):
        current_app.logger.info(
            "[e-mail simulado] Confirmação de diagnóstico para %s "
            "(configure MAIL_SERVER no .env para enviar de verdade)",
            client.email,
        )
        return False

    try:
        msg = Message(
            subject="Recebemos seu diagnóstico ✔",
            recipients=[client.email],
            body=render_template("email/diagnostic_confirmation.txt", client=client),
        )
        mail.send(msg)
        return True
    except Exception:
        current_app.logger.exception("Falha ao enviar e-mail de confirmação para %s", client.email)
        return False


def send_ebook_email(client, ebook):
    if not current_app.config.get("MAIL_SERVER"):
        current_app.logger.info(
            "[e-mail simulado] Envio do ebook '%s' para %s "
            "(configure MAIL_SERVER no .env para enviar de verdade)",
            ebook.title,
            client.email,
        )
        return False

    try:
        msg = Message(
            subject=f"Seu ebook \"{ebook.title}\" chegou 📘",
            recipients=[client.email],
            body=render_template("email/ebook_delivery.txt", client=client, ebook=ebook),
        )
        mail.send(msg)
        return True
    except Exception:
        current_app.logger.exception("Falha ao enviar e-mail do ebook para %s", client.email)
        return False
