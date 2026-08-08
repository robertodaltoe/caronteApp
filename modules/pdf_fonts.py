"""
Font incorporati (base64) per i template PDF generati con WeasyPrint.

WeasyPrint qui viene chiamato come HTML(string=...) senza base_url (vedi
routes/report.py, routes/docenti.py, routes/mail_bozze.py): un font
referenziato da file statico o da Google Fonts non si risolverebbe in modo
affidabile. La soluzione più semplice è incorporarlo come data URI
direttamente nel CSS del template.

Caricati una sola volta per processo (i file non cambiano a runtime).
"""
import base64
import os

_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'fonts')

_CACHE = {}


def _carica_b64(nome_file):
    if nome_file not in _CACHE:
        percorso = os.path.join(_BASE_DIR, nome_file)
        with open(percorso, 'rb') as f:
            _CACHE[nome_file] = base64.b64encode(f.read()).decode('ascii')
    return _CACHE[nome_file]


def contesto_open_sans():
    """Dict da passare a render_template() per i template PDF che usano
    Open Sans incorporato (pesi 400/600/700/800 — niente 'light', poco
    leggibile in stampa)."""
    return {
        'FONT_OS_400': _carica_b64('opensans-400.woff2'),
        'FONT_OS_600': _carica_b64('opensans-600.woff2'),
        'FONT_OS_700': _carica_b64('opensans-700.woff2'),
        'FONT_OS_800': _carica_b64('opensans-800.woff2'),
    }
