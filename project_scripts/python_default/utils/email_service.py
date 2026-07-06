import os
import smtplib
import sys
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from settings import LOGGER, SETTINGS

MAX_EMAIL_RETRIES = 3
EMAIL_RETRY_DELAY_SECONDS = 2


def send_email(
    email_to: str,
    subject: str,
    template_name: str,
    environment: dict[str, Any],
) -> None:
    if not SETTINGS.SMTP_HOST:
        LOGGER.warning(
            "Configurações de SMTP (Host) não encontradas. Email não enviado."
        )
        return

    msg = MIMEMultipart()
    msg["From"] = f"{SETTINGS.EMAILS_FROM_NAME} <{SETTINGS.EMAILS_FROM_EMAIL}>"
    msg["To"] = email_to
    msg["Subject"] = subject

    # Aqui poderíamos usar um sistema de templates mais robusto (Jinja2),
    # mas por hora vamos fazer simples strings formatadas
    body = render_template(template_name, environment)
    msg.attach(MIMEText(body, "html"))
    text = msg.as_string()

    last_error: Exception | None = None
    for attempt in range(1, MAX_EMAIL_RETRIES + 1):
        try:
            LOGGER.info(
                f"Conectando ao servidor SMTP: {SETTINGS.SMTP_HOST}:{SETTINGS.SMTP_PORT or 587} (tentativa {attempt}/{MAX_EMAIL_RETRIES})"
            )
            server = smtplib.SMTP(
                str(SETTINGS.SMTP_HOST), int(SETTINGS.SMTP_PORT or 587)
            )

            # Tenta STARTTLS, mas não falha se não suportado
            # try:
            #     server.starttls()
            #     LOGGER.info("STARTTLS ativado com sucesso.")
            # except Exception as e:
            #     LOGGER.warning(
            #         f"Não foi possível ativar STARTTLS (pode ser normal para relays internos): {e}"
            #     )

            server.sendmail(str(SETTINGS.EMAILS_FROM_EMAIL), email_to, text)
            server.quit()
            LOGGER.info(f"Email enviado com sucesso para {email_to}")
            return
        except (ConnectionRefusedError, OSError, smtplib.SMTPException) as e:
            last_error = e
            if attempt < MAX_EMAIL_RETRIES:
                LOGGER.warning(
                    f"Falha ao enviar email (tentativa {attempt}/{MAX_EMAIL_RETRIES}): {e}. "
                    f"Reagendando em {EMAIL_RETRY_DELAY_SECONDS}s..."
                )
                time.sleep(EMAIL_RETRY_DELAY_SECONDS)
            else:
                LOGGER.error(
                    f"Erro ao enviar email após {MAX_EMAIL_RETRIES} tentativas: {e}"
                )
                import traceback

                print(traceback.format_exc())
        except Exception as e:
            last_error = e
            LOGGER.error(f"Erro ao enviar email: {e}")
            return

    if last_error:
        import traceback

        LOGGER.debug(traceback.format_exc())


def render_template(template_name: str, environment: dict[str, Any]) -> str:
    """
    Renderiza um template de email simples com estilos inline (shadcn/ui Neutral).
    """
    # Cores e Estilos Base
    style_body_bg = "#f4f4f5"
    style_card_bg = "#ffffff"
    style_text_primary = "#09090b"
    style_text_muted = "#71717a"
    style_button_bg = "#18181b"
    style_button_text = "#ffffff"
    style_border = "#e4e4e7"

    font_family = (
        "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    )

    # Template Base - Estrutura de tabela para compatibilidade
    base_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: {style_body_bg}; font-family: {font_family}; -webkit-font-smoothing: antialiased;">
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: {style_body_bg};">
            <tr>
                <td align="center" style="padding: 40px 20px;">
                    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 600px; background-color: {style_card_bg}; border-radius: 8px; border: 1px solid {style_border}; overflow: hidden;">
                        <tr>
                            <td style="padding: 32px;">
                                {{content}}
                            </td>
                        </tr>
                    </table>
                    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 600px;">
                        <tr>
                            <td align="center" style="padding-top: 32px;">
                                <p style="margin: 0; font-size: 12px; color: {style_text_muted}; text-align: center;">
                                    {{footer_text}}
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    if template_name == "invite_user":
        content = f"""
            <h2 style="margin: 0 0 24px; font-size: 24px; font-weight: 600; color: {style_text_primary};">Convite para Organização</h2>
            <p style="margin: 0 0 16px; font-size: 16px; line-height: 24px; color: {style_text_primary};">
                Olá!
                <br><br>
                Você foi convidado para participar da organização <strong>{environment.get("org_name")}</strong> como <strong>{environment.get("role")}</strong>.
            </p>
            <div style="margin: 32px 0;">
                <a href="{environment.get("link")}" style="display: inline-block; background-color: {style_button_bg}; color: {style_button_text}; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 500; font-size: 14px;">
                    Aceitar Convite
                </a>
            </div>
            <p style="margin: 0 0 16px; font-size: 16px; line-height: 24px; color: {style_text_primary};">
                Clique no botão acima para criar sua conta ou entrar.
            </p>
        """
        footer = "Se você não esperava este convite, pode ignorar este email."
        return base_template.format(content=content, footer_text=footer)

    if template_name == "reset_password":
        content = f"""
            <h2 style="margin: 0 0 24px; font-size: 24px; font-weight: 600; color: {style_text_primary};">Recuperação de Senha</h2>
            <p style="margin: 0 0 16px; font-size: 16px; line-height: 24px; color: {style_text_primary};">
                Olá!
                <br><br>
                Recebemos uma solicitação para redefinir sua senha associada a este endereço de email.
            </p>
            <div style="margin: 32px 0;">
                <a href="{environment.get("link")}" style="display: inline-block; background-color: {style_button_bg}; color: {style_button_text}; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 500; font-size: 14px;">
                    Redefinir Senha
                </a>
            </div>
            <p style="margin: 0; font-size: 16px; line-height: 24px; color: {style_text_primary};">
                Se você não solicitou a redefinição de senha, ignore este email. Sua senha permanecerá a mesma.
            </p>
        """
        footer = "Gestão de Agentes • Recuperação de Conta"
        return base_template.format(content=content, footer_text=footer)

    return ""


def send_invite_email(email: str, org_name: str, role: str, link: str) -> None:
    subject = f"Convite para participar da {org_name}"
    send_email(
        email,
        subject,
        "invite_user",
        {"org_name": org_name, "role": role, "link": link},
    )


def send_password_reset_email(email: str, link: str) -> None:
    subject = "Recuperação de Senha - Gestão de Agentes"
    send_email(email, subject, "reset_password", {"link": link})


if __name__ == "__main__":
    send_invite_email("giovanni.morassi@exata.it", "exata", "membro", "teste")
