"""
Dati anagrafici dell'istituto e parametri economici/contrattuali
configurabili, salvati in `config_app` (stessa tabella chiave/valore
usata da config_anno.py e config_calendario.py).

Prima di questo modulo, alcuni di questi valori erano scritti a mano nel
codice, in più punti e in modo incoerente:
- il costo orario supplenza era 29.08€ in due file diversi (routes/report.py,
  routes/banca_ore.py) ma ~30€ ("MAD") in un terzo (templates/report/dirigente.html)
  — due report diversi stimavano lo stesso costo con due numeri diversi.
- il nome/indirizzo dell'istituto era ripetuto identico in oltre 10 punti
  (login, display pubblico, export Excel, privacy, ecc.).
- le soglie ore istituzionali CCNL art.44 (40h limite, 32h attenzione) e
  la scadenza dei 3 mesi per il saldo banca ore (accordo sindacale) erano
  hardcoded nel codice.

Ora tutti questi valori hanno un'unica fonte, modificabile in qualsiasi
momento dalla pagina Impostazioni → Dati istituto, senza dover toccare
il codice.

USO:
    from config_istituto import get_dati_istituto, set_dati_istituto
    dati = get_dati_istituto()
    dati['costo_ora_supplenza']  # es. 29.08
"""

DEFAULTS = {
    'nome_istituto':          'IIS "Leonardo da Vinci" — Chiavenna',
    'indirizzo_istituto':     'Via Garibaldi, Chiavenna (SO)',
    'costo_ora_supplenza':    29.08,
    'ore_ist_limite':         40,     # limite CCNL art.44 (bucket A/B)
    'ore_ist_soglia_alert':   32,     # soglia di attenzione (cruscotto)
    'scadenza_saldo_mesi':    3,      # accordo sindacale: mesi per saldare
}

_CHIAVE_PREFIX = 'istituto_'


def get_dati_istituto():
    """
    Restituisce un dict con tutti i parametri configurabili, usando i
    valori salvati in config_app se presenti, altrimenti il default.
    Non richiede che siano già stati salvati — funziona anche al primo
    avvio, prima che nessuno abbia mai aperto la pagina di configurazione.
    """
    from models.config_app import ConfigApp
    risultato = dict(DEFAULTS)
    righe = ConfigApp.query.filter(
        ConfigApp.chiave.like(f'{_CHIAVE_PREFIX}%')).all()
    per_chiave = {r.chiave[len(_CHIAVE_PREFIX):]: r.valore for r in righe}
    for chiave, default in DEFAULTS.items():
        if chiave in per_chiave and per_chiave[chiave] not in (None, ''):
            valore_grezzo = per_chiave[chiave]
            if isinstance(default, float):
                try:
                    risultato[chiave] = float(valore_grezzo)
                except ValueError:
                    pass
            elif isinstance(default, int):
                try:
                    risultato[chiave] = int(valore_grezzo)
                except ValueError:
                    pass
            else:
                risultato[chiave] = valore_grezzo
    return risultato


def set_dati_istituto(nuovi_valori):
    """
    Salva i parametri passati (dict, anche parziale) in config_app.
    Solo le chiavi note in DEFAULTS vengono accettate.
    """
    from models.config_app import ConfigApp
    from models import db
    for chiave, valore in nuovi_valori.items():
        if chiave not in DEFAULTS:
            continue
        chiave_db = f'{_CHIAVE_PREFIX}{chiave}'
        riga = ConfigApp.query.filter_by(chiave=chiave_db).first()
        valore_str = str(valore)
        if riga:
            riga.valore = valore_str
        else:
            db.session.add(ConfigApp(chiave=chiave_db, valore=valore_str))
    db.session.commit()


def get_costo_ora():
    """Scorciatoia: solo il costo orario supplenza (il valore più usato)."""
    return get_dati_istituto()['costo_ora_supplenza']
