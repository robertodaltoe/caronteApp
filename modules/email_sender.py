"""
modules/email_sender.py
Gestione invio email via Gmail SMTP con App Password.
"""
import smtplib
import io
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import date


SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

CORPO_EMAIL = """\
Buongiorno,

trasmetto in allegato il prospetto personale aggiornato relativo alle ore svolte o da recuperare ad oggi. Si prega di verificare la correttezza dei dati.

Cordiali saluti

Mail generata automaticamente
"""


def invia_report_docente(docente, xlsx_bytes, config):
    """
    Invia il report XLSX a un singolo docente.

    config = {
        'smtp_user':     'roberto.daltoe@davincichiavenna.edu.it',
        'smtp_password': 'xxxx xxxx xxxx xxxx',   # App Password
        'smtp_from':     'Roberto Dal Toe <roberto.daltoe@davincichiavenna.edu.it>',
    }

    Ritorna (True, None) oppure (False, messaggio_errore)
    """
    if not docente.email:
        return False, f"Email mancante per {docente.cognome}"

    try:
        msg = MIMEMultipart()
        msg['From']    = config['smtp_from']
        msg['To']      = docente.email
        msg['Subject'] = (f"Report banca ore — {docente.cognome}"
                          f" — aggiornamento {date.today().strftime('%d/%m/%Y')}")

        msg.attach(MIMEText(CORPO_EMAIL, 'plain', 'utf-8'))

        # Allegato XLSX
        part = MIMEBase('application',
                        'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        part.set_payload(xlsx_bytes)
        encoders.encode_base64(part)
        nome_file = (f"BancaOre_{docente.cognome.replace(' ', '_')}"
                     f"_{date.today().isoformat()}.xlsx")
        part.add_header('Content-Disposition', 'attachment',
                        filename=nome_file)
        msg.attach(part)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(config['smtp_user'], config['smtp_password'])
            server.send_message(msg)

        return True, None

    except smtplib.SMTPAuthenticationError:
        return False, "Autenticazione fallita — controlla App Password"
    except smtplib.SMTPException as e:
        return False, f"Errore SMTP: {e}"
    except Exception as e:
        return False, f"Errore generico: {e}"


def test_connessione(config):
    """Verifica che le credenziali SMTP funzionino."""
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(config['smtp_user'], config['smtp_password'])
        return True, None
    except smtplib.SMTPAuthenticationError:
        return False, "Autenticazione fallita — controlla App Password"
    except Exception as e:
        return False, str(e)
