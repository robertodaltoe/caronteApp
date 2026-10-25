"""
Invio email con la Gmail API (solo scope gmail.send), senza dipendenze
esterne: usa solo la libreria standard.

File (cartella data/, esclusa da git):
  data/gmail_client.json  credenziali "App desktop" scaricate da Google Cloud
  data/gmail_token.json   token di refresh, creato da autorizza_gmail.py

L'intestazione From non viene impostata: Gmail usa l'account autorizzato.
L'account autorizzato viene verificato in autorizza_gmail.py (deve essere
MITTENTE_ATTESO), per non spedire da una casella sbagliata.
"""
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, 'data')
FILE_CLIENT = os.path.join(DATA, 'gmail_client.json')
FILE_TOKEN = os.path.join(DATA, 'gmail_token.json')
SCOPE = 'https://www.googleapis.com/auth/gmail.send'
MITTENTE_ATTESO = 'roberto.daltoe@davincichiavenna.edu.it'
URL_TOKEN = 'https://oauth2.googleapis.com/token'
URL_SEND = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send'


class GmailNonConfigurato(Exception):
    pass


def _leggi(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise GmailNonConfigurato(f'manca {os.path.basename(path)} (vedi guida_passo_passo)')


def _credenziali_client():
    c = _leggi(FILE_CLIENT)
    c = c.get('installed') or c.get('web') or c
    return c['client_id'], c['client_secret']


def _post(url, dati, intestazioni=None, json_body=False):
    corpo = json.dumps(dati).encode() if json_body else urllib.parse.urlencode(dati).encode()
    h = {'Content-Type': 'application/json' if json_body else 'application/x-www-form-urlencoded'}
    h.update(intestazioni or {})
    req = urllib.request.Request(url, data=corpo, headers=h, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode() or '{}')
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'Google ha risposto {e.code}: {e.read().decode()[:200]}')


def access_token():
    cid, secret = _credenziali_client()
    rt = _leggi(FILE_TOKEN).get('refresh_token')
    if not rt:
        raise GmailNonConfigurato('token senza refresh_token: rilancia autorizza_gmail.py')
    r = _post(URL_TOKEN, dict(client_id=cid, client_secret=secret,
                              refresh_token=rt, grant_type='refresh_token'))
    return r['access_token']


def costruisci(destinatario, oggetto, corpo, allegati=()):
    m = EmailMessage()
    m['To'] = destinatario
    m['Subject'] = oggetto
    m.set_content(corpo)
    for nome, dati in allegati:
        m.add_attachment(dati, maintype='application', subtype='pdf', filename=nome)
    return m


def invia(destinatario, oggetto, corpo, allegati=()):
    token = access_token()
    m = costruisci(destinatario, oggetto, corpo, allegati)
    raw = base64.urlsafe_b64encode(m.as_bytes()).decode()
    return _post(URL_SEND, {'raw': raw}, {'Authorization': f'Bearer {token}'}, json_body=True)
