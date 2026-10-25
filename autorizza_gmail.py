"""
Autorizzazione una tantum dell'invio email (da lanciare sul PC server).

Prerequisito: data/gmail_client.json (credenziali "App desktop").
Si apre il browser: accedi con roberto.daltoe@davincichiavenna.edu.it e
concedi il permesso di invio (piu' la lettura del solo indirizzo email, per
controllare che sia l'account giusto). Il token viene salvato in
data/gmail_token.json. Per revocare: myaccount.google.com -> Sicurezza.

Uso:  python autorizza_gmail.py
"""
import base64
import hashlib
import json
import os
import secrets
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from modules import gmail_invio as g


def main():
    cid, secret = g._credenziali_client()
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    stato = secrets.token_urlsafe(16)
    risultato = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get('state', [''])[0] == stato and 'code' in q:
                risultato['code'] = q['code'][0]
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write('Autorizzazione ricevuta: puoi chiudere questa pagina.'.encode())

        def log_message(self, *a):
            pass

    srv = HTTPServer(('127.0.0.1', 0), H)
    redirect = f'http://127.0.0.1:{srv.server_port}'
    url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(dict(
        client_id=cid, redirect_uri=redirect, response_type='code', scope=g.SCOPE + ' openid email',
        access_type='offline', prompt='consent', state=stato,
        code_challenge=challenge, code_challenge_method='S256',
        login_hint=g.MITTENTE_ATTESO))
    print('Apro il browser. Se non si apre, copia questo indirizzo:\n', url)
    webbrowser.open(url)
    t = threading.Thread(target=srv.handle_request)
    t.start()
    t.join(timeout=300)
    if 'code' not in risultato:
        raise SystemExit('Nessuna autorizzazione ricevuta.')
    tok = g._post(g.URL_TOKEN, dict(
        client_id=cid, client_secret=secret, code=risultato['code'],
        code_verifier=verifier, redirect_uri=redirect, grant_type='authorization_code'))
    if 'refresh_token' not in tok:
        raise SystemExit('Google non ha restituito il refresh_token: riprova.')
    # l'account si legge dall'id_token (scope 'email'): il profilo Gmail non
    # e' leggibile con il solo permesso di invio
    account = None
    if tok.get('id_token'):
        pl = tok['id_token'].split('.')[1]
        account = json.loads(base64.urlsafe_b64decode(pl + '=' * (-len(pl) % 4))).get('email', '').lower()
    if account != g.MITTENTE_ATTESO:
        raise SystemExit(f'Account autorizzato ({account or "sconosciuto"}) diverso da {g.MITTENTE_ATTESO}: '
                         f'nulla e\' stato salvato.')
    os.makedirs(g.DATA, exist_ok=True)
    with open(g.FILE_TOKEN, 'w', encoding='utf-8') as f:
        json.dump({'refresh_token': tok['refresh_token']}, f)
    try:
        os.chmod(g.FILE_TOKEN, 0o600)
    except OSError:
        pass
    print('Fatto: token salvato in', g.FILE_TOKEN)


if __name__ == '__main__':
    main()
