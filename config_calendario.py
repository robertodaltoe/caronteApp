"""
Parametri di calendario scolastico configurabili, usati da
routes/report.py::pianifica_permessi() per calcolare le date future
disponibili per proporre permessi orari.

Prima erano hardcoded nel codice (data(2026, 6, 6) come ultimo giorno di
lezione, 1-2 giugno 2026 come festivi, riduzione a 3 ore il 6 giugno):
funzionavano solo per l'anno scolastico 2025-2026 e, se non aggiornate a
mano ogni anno, avrebbero silenziosamente prodotto un calcolo sbagliato
(nessun errore, nessun avviso — solo un risultato non corretto).

Ora questi valori sono in `config_app` (stessa tabella chiave/valore usata
da config_anno.py per l'anno scolastico corrente) e, se non ancora
impostati per l'anno in corso, la funzione che li usa mostra un avviso
esplicito invece di usare in silenzio una data sbagliata.

I giorni di sospensione/ponte (prima un elenco separato qui,
"giorni_festivi_extra") sono stati unificati con Impostazioni >
Sospensioni didattiche (models.sospensione.SospensioneDidattica): un solo
elenco condiviso invece di doverlo mantenere allineato in due posti.
pianifica_permessi() ora legge le sospensioni direttamente da lì.

USO:
    from config_calendario import get_data_fine_lezioni, set_data_fine_lezioni
    from config_calendario import get_ore_ultimo_giorno, set_ore_ultimo_giorno
"""
from datetime import date


def _chiave_fine_lezioni(anno_scol):
    return f'data_fine_lezioni_{anno_scol}'


def _chiave_ore_ultimo_giorno(anno_scol):
    return f'ore_ultimo_giorno_{anno_scol}'


def get_data_fine_lezioni(anno_scol):
    """
    Ultimo giorno di lezione dell'anno scolastico indicato, se configurato.
    Ritorna None se non ancora impostato (il chiamante deve gestire questo
    caso mostrando un avviso, non usare una data indovinata).
    """
    from models.config_app import ConfigApp
    riga = ConfigApp.query.filter_by(chiave=_chiave_fine_lezioni(anno_scol)).first()
    if riga and riga.valore:
        try:
            return date.fromisoformat(riga.valore)
        except ValueError:
            return None
    return None


def set_data_fine_lezioni(anno_scol, data_fine):
    from models.config_app import ConfigApp
    from models import db
    chiave = _chiave_fine_lezioni(anno_scol)
    riga = ConfigApp.query.filter_by(chiave=chiave).first()
    valore = data_fine.isoformat()
    if riga:
        riga.valore = valore
    else:
        db.session.add(ConfigApp(chiave=chiave, valore=valore))
    db.session.commit()


def get_ore_ultimo_giorno(anno_scol):
    """
    Numero massimo di ore di lezione nell'ultimo giorno (se quel giorno ha
    un orario ridotto). Ritorna None se non configurato (nessuna
    riduzione applicata di default — più sicuro di indovinare un valore).
    """
    from models.config_app import ConfigApp
    riga = ConfigApp.query.filter_by(chiave=_chiave_ore_ultimo_giorno(anno_scol)).first()
    if riga and riga.valore:
        try:
            return int(riga.valore)
        except ValueError:
            return None
    return None


def set_ore_ultimo_giorno(anno_scol, ore):
    from models.config_app import ConfigApp
    from models import db
    chiave = _chiave_ore_ultimo_giorno(anno_scol)
    riga = ConfigApp.query.filter_by(chiave=chiave).first()
    valore = str(ore) if ore else None
    if riga:
        riga.valore = valore
    else:
        db.session.add(ConfigApp(chiave=chiave, valore=valore))
    db.session.commit()
