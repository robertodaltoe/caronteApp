"""
Formato delle etichette di classe.

Nel progetto convivono due scritture della stessa classe: "4A LSU"
(AssegnazioneClasse.label_classe, Aule, generatore CdC — la forma
ufficiale, con spazio) e "4ALSU" (OrarioDocente/Supplenza.classe, copiate
dall'orario importato, spesso senza spazio). Un confronto o un parsing
che assume una sola delle due fallisce in silenzio: nessun errore, il
dato semplicemente non compare (display aule, prospetto supplenze,
alternativa IRC e, per i CdC, preset partecipanti e iscrizione dei
docenti agli eventi).

etichetta_classe() porta qualunque forma a quella ufficiale;
stessa_classe() confronta due etichette indipendentemente dalla forma.
"""
import re

# Indirizzi noti (stesso elenco di modules/generatore_cdc.py::_IND_SEQUENCE
# più SOS): servono a trovare il confine sezione/indirizzo senza
# indovinare ("1AFM" potrebbe essere "1A FM" o "1 AFM").
_INDIRIZZI = ('AFM', 'RIM', 'CAT', 'LLI', 'LSC', 'LSP', 'LSU', 'SOS')

_RE_SPAZIATA = re.compile(r'^(\d+)\s*([AB]?)\s+(.+)$', re.I)
_RE_PREFISSO = re.compile(r'^(\d+)([AB]?)$')


def etichetta_classe(c):
    """'4ALSU' / '4a lsu' / '4A  LSU' -> '4A LSU'. Valori non
    riconoscibili (potenziamento, '---', vuoti) tornano invariati."""
    if not c:
        return c
    t = str(c).strip().upper()
    m = _RE_SPAZIATA.match(t)
    if m:
        return f'{m.group(1)}{m.group(2)} {m.group(3).strip()}'
    compatto = re.sub(r'\s+', '', t)
    for ind in _INDIRIZZI:
        if compatto.endswith(ind):
            m = _RE_PREFISSO.match(compatto[:-len(ind)])
            if m:
                return f'{m.group(1)}{m.group(2)} {ind}'
    return str(c).strip()


def stessa_classe(a, b):
    return bool(a) and bool(b) and \
        re.sub(r'\s+', '', str(a)).upper() == re.sub(r'\s+', '', str(b)).upper()


def scomponi_classe(c):
    """'4ALSU' -> ('4A', 'LSU'); (None, None) se non riconosciuta."""
    m = re.match(r'^(\d+[AB]?) (.+)$', etichetta_classe(c) or '')
    return (m.group(1), m.group(2)) if m else (None, None)
