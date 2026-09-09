"""
modules/dati_istituto.py — Dati anagrafici dell'Istituto usati nei
documenti amministrativi generati (avvisi, decreti, incarichi...).

CaronteApp gestisce un solo istituto (IIS "Leonardo da Vinci",
Chiavenna): questi dati cambiano raramente (es. solo quando cambia il
Dirigente Scolastico) e vanno aggiornati qui a mano, una sola volta,
invece di essere ripetuti in ogni progetto FSE/FESR.
"""

DENOMINAZIONE = 'I.I.S. Leonardo da Vinci'
COMUNE = 'Chiavenna'
PROVINCIA = 'Sondrio'
INDIRIZZO = 'Via Bottonera, 21'
CODICE_FISCALE = '81004790143'
CODICE_UNIVOCO_FATTURAZIONE = 'UF3ETE'
PEO = 'sois00600d@istruzione.it'
SITO_WEB = 'https://www.davincichiavenna.edu.it/'
FORO_COMPETENTE = 'Sondrio'

DS_TITOLO = 'Dott.'
DS_NOME_COGNOME = "Ottavio D'Addea"

REGOLAMENTO_INCARICHI_INDIVIDUALI = 'delibera n. 70 del 30.04.2019'


# ── Intestazione istituzionale (logo MIM + logo Istituto, banner PN
# "Scuola e competenze"/UE) — presa dai modelli reali del DS, incorporata
# come base64 perché i template PDF generati con WeasyPrint sono
# chiamati con HTML(string=...) senza base_url (stesso motivo/pattern di
# modules/pdf_fonts.py: un file statico referenziato da URL relativo non
# si risolverebbe in modo affidabile).
import base64
import os

_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'img', 'istituto')
_CACHE = {}


def _carica_immagine_b64(nome_file):
    if nome_file not in _CACHE:
        percorso = os.path.join(_BASE_DIR, nome_file)
        with open(percorso, 'rb') as f:
            _CACHE[nome_file] = base64.b64encode(f.read()).decode('ascii')
    return _CACHE[nome_file]


def intestazione_data_uri():
    """Logo MIM + logo Istituto con dati di contatto — da mettere in
    testa a ogni documento amministrativo generato."""
    return 'data:image/jpeg;base64,' + _carica_immagine_b64('intestazione.jpg')


def footer_ue_data_uri():
    """Banner PN 'Scuola e competenze'/cofinanziamento UE — da mettere a
    fondo pagina nei documenti dei progetti finanziati da fondi
    strutturali europei."""
    return 'data:image/jpeg;base64,' + _carica_immagine_b64('footer_ue.jpg')
