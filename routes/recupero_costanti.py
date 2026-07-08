"""
Costanti e funzioni helper condivise tra tutti i sotto-moduli del
modulo recupero (giugno, agosto, export). Questo file non importa NULLA
da routes/recupero.py né dagli altri sotto-moduli — è una "foglia"
dell'albero di import, per evitare ogni rischio di import circolare
quando recupero.py importa le route definite altrove.
"""
from datetime import date
from models.docente import Docente

from config_anno import get_anno_corrente as _get_anno
ANNO = _get_anno()
DATA_INIZIO = date(2026, 6, 15)
DATA_FINE   = date(2026, 7, 4)

ANNO_AGO     = _get_anno()
PERIODO_AGO  = 'prove_agosto'
CONTRATTI_OK = ('TI', 'TD_annuale')  # solo tempo indeterminato + tempo determinato annuale

TIPO_PROVA_LABEL = {
    'scritto':       '✏️ Scritto',
    'orale':         '🗣 Orale',
    'pratico':       '🔧 Pratico',
    'scritto_orale': '✏️🗣 Scritto + Orale',
}


_FAMIGLIE_MATERIE = [
    {'LATINO', 'LINGUA LATINA', 'LINGUA E CULTURA LATINA'},
    {'ITALIANO', 'LINGUA E LETTERATURA ITALIANA', 'LINGUA E CULTURA ITALIANA'},
    {'MATEMATICA', 'MATEMATICA CON INFORMATICA', 'MATEMATICA E COMPLEMENTI DI MATEMATICA'},
    {'INFORMATICA', 'TECNOLOGIE INFORMATICHE'},
    {'STORIA', 'STORIA E GEOGRAFIA'},
    {'FISICA', 'SCIENZE INTEGRATE (FISICA)'},
    {'INGLESE', 'LINGUA INGLESE', 'LINGUA E CULTURA STRANIERA (INGLESE)'},
    {'TEDESCO', 'LINGUA TEDESCA', 'LINGUA E CULTURA STRANIERA TEDESCO'},
]

def _materia_canonica(materia):
    """
    Restituisce un'etichetta canonica per la materia, usando la prima voce
    della famiglia di sinonimi se esiste, altrimenti la materia stessa.
    Usata come chiave di raggruppamento per evitare di separare ad es.
    'FISICA' da 'SCIENZE INTEGRATE (FISICA)'.
    """
    mu = materia.strip().upper()
    for famiglia in _FAMIGLIE_MATERIE:
        if mu in famiglia:
            return sorted(famiglia)[0]
    return mu


def _norm_materia(s):
    """Normalizza il testo grezzo della materia (maiuscolo, troncato a 100 char)."""
    return str(s).strip().upper()[:100]


def _split_cognome_nome(s):
    """
    "DEL PAPA MARCO" -> ('DEL PAPA', 'M')
    "VALENA SARA"    -> ('VALENA', 'S')
    Cerca tra i cognomi noti del DB la corrispondenza più lunga all'inizio
    della stringa (gestisce correttamente i cognomi composti, es. "DEL
    PAPA"); se non trova nulla, usa la prima parola come fallback.
    """
    cognomi_noti = sorted(
        {d.cognome.strip().upper() for d in Docente.query.all() if d.cognome},
        key=lambda c: -len(c.split())
    )
    s = str(s).strip().upper()
    s = s.split(',')[0].strip()
    parts = s.split()
    if not parts:
        return '', ''
    for cognome_noto in cognomi_noti:
        n_parole = len(cognome_noto.split())
        if n_parole >= len(parts):
            continue
        if ' '.join(parts[:n_parole]) == cognome_noto:
            resto = parts[n_parole:]
            ini = resto[0][0] if resto else ''
            return cognome_noto, ini
    return parts[0], (parts[1][0] if len(parts) > 1 else '')


def _parse_tipo_prova(s):
    """Normalizza il tipo prova dal file registro."""
    s = str(s).strip().lower()
    if 'orale' in s and 'scritt' in s:
        return 'scritto_orale'
    if 'orale' in s:
        return 'orale'
    if 'pratico' in s or 'pratica' in s:
        return 'pratico'
    return 'scritto'
