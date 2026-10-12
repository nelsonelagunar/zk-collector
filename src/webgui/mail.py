"""
Mail Module - Envío de emails para recuperación de contraseña
Soporta SMTP con TLS/SSL
"""

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)


class MailError(Exception):
    """Excepción para errores de envío de email"""
    pass


class Mailer:
    """
    Cliente SMTP para envío de emails
    - Soporta TLS (STARTTLS) y SSL
    - Timeout configurable
    """

    def __init__(self, host: str, port: int, username: str,
                 password: str, from_email: str,
                 use_tls: bool = True, use_ssl: bool = False,
                 timeout: int = 30):
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password
        self.from_email = from_email
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.timeout = timeout

    @classmethod
    def from_config(cls, config: dict) -> Optional['Mailer']:
        """
        Construir Mailer desde configuración de system_config (dict)

        Returns None si SMTP no está configurado
        """
        if not config.get('smtp_host'):
            return None
        if config.get('smtp_configured', 'false') != 'true':
            return None

        return cls(
            host=config['smtp_host'],
            port=config.get('smtp_port', '587'),
            username=config.get('smtp_username', ''),
            password=config.get('smtp_password', ''),
            from_email=config.get('smtp_from_email') or config.get('smtp_username', ''),
            use_tls=config.get('smtp_use_tls', 'true') == 'true',
            use_ssl=int(config.get('smtp_port', '587')) == 465,
        )

    def send(self, to_email: str, subject: str, body: str, html_body: Optional[str] = None):
        """Enviar email (texto plano + HTML opcional)"""
        msg = MIMEMultipart('alternative')
        msg['From'] = self.from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        if html_body:
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        try:
            if self.use_ssl:
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=context)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
                if self.use_tls:
                    server.starttls(context=ssl.create_default_context())

            with server:
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.sendmail(self.from_email, [to_email], msg.as_string())

            logger.info(f"Email enviado a {to_email} ({subject})")
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"Autenticación SMTP fallida: {e}")
            raise MailError(f"SMTP auth failed: {e}") from e
        except (smtplib.SMTPException, OSError) as e:
            logger.error(f"Error enviando email: {e}")
            raise MailError(f"SMTP send failed: {e}") from e

    def send_password_reset(self, to_email: str, username: str, reset_url: str, expiry_minutes: int):
        """Enviar email de reset de contraseña"""
        subject = "Attendance Collector - Recuperación de contraseña"
        body = (
            f"Hola {username},\n\n"
            f"Recibimos una solicitud para restablecer tu contraseña.\n\n"
            f"Visita el siguiente enlace para elegir una nueva contraseña (vence en {expiry_minutes} minutos):\n"
            f"{reset_url}\n\n"
            f"Si no solicitaste este cambio, ignora este email y tu contraseña permanecerá sin cambios.\n\n"
            f"-- Attendance Collector"
        )
        html_body = f"""
        <html>
        <body style="font-family: sans-serif; color: #1f2937;">
            <h2>Recuperación de contraseña</h2>
            <p>Hola <strong>{username}</strong>,</p>
            <p>Recibimos una solicitud para restablecer tu contraseña.</p>
            <p>
                <a href="{reset_url}"
                   style="background-color: #2563eb; color: #ffffff; padding: 10px 20px;
                          text-decoration: none; border-radius: 6px; display: inline-block;">
                    Restablecer contraseña
                </a>
            </p>
            <p style="color: #6b7280; font-size: 0.875rem;">
                Este enlace vence en {expiry_minutes} minutos. Si no solicitaste este cambio,
                ignora este email y tu contraseña permanecerá sin cambios.
            </p>
        </body>
        </html>
        """
        self.send(to_email, subject, body, html_body)