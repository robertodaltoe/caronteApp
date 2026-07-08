"""
Fonte unica di verità per l'anno scolastico corrente in CaronteApp.

L'anno scolastico corrente è memorizzato nella tabella `config_app`
(chiave 'anno_scol_corrente'). Se non trovato, viene calcolato dal
calendario (settembre = inizio nuovo anno).

USO:
    from config_anno import get_anno_corrente, set_anno_corrente

    anno = get_anno_corrente()          # es. '2025-2026'
    set_anno_corrente('2026-2027')      # cambio anno
"""
from datetime import date


def _calcola_da_calendario():
    """Calcola l'anno scolastico corrente dal calendario."""
    oggi = date.today()
    if oggi.month >= 9:
        return f'{oggi.year}-{oggi.year + 1}'
    return f'{oggi.year - 1}-{oggi.year}'


def get_anno_corrente(app=None):
    """
    Restituisce l'anno scolastico corrente.
    Legge dal database (tabella config_app); se non presente usa il calendario.
    Può essere chiamato sia dentro che fuori il contesto Flask.
    """
    try:
        from models.config_app import ConfigApp
        val = ConfigApp.query.filter_by(chiave='anno_scol_corrente').first()
        if val and val.valore:
            return val.valore
    except Exception:
        pass
    return _calcola_da_calendario()


def set_anno_corrente(nuovo_anno):
    """
    Imposta l'anno scolastico corrente nel database.
    Deve essere chiamato dentro un contesto Flask attivo.
    """
    from models.config_app import ConfigApp
    from models import db
    riga = ConfigApp.query.filter_by(chiave='anno_scol_corrente').first()
    if riga:
        riga.valore = nuovo_anno
    else:
        db.session.add(ConfigApp(chiave='anno_scol_corrente', valore=nuovo_anno))
    db.session.commit()
