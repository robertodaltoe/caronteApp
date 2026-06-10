from functools import wraps
from flask import session, redirect, url_for, request

# PIN di default — cambiabile dalla pagina impostazioni
DEFAULT_PIN = "1234"

def login_required(f):
    """Decorator che protegge le route della dashboard."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('autenticato'):
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated
