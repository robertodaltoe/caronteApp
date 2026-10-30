"""
Invio automatico delle notifiche supplenze (spento di default).

Un thread in background controlla ogni 30 s se e' ora di inviare: con
l'invio automatico attivo, all'orario impostato (default 15:30) manda le
notifiche per il prossimo giorno di lezione, esattamente come il
pulsante manuale della pagina «Notifiche supplenze»: stesse regole
(modalita' spento/simulato/reale, lista «Solo a», anti-duplicato,
indirizzi non validi saltati). Un solo invio al giorno; se qualche
messaggio va in errore si riprova ogni 10 minuti, al massimo 3 volte.
Attivazione e orario si cambiano dalla pagina, nella tabella config_app.
"""
import threading
import time
import traceback
from datetime import date, datetime, timedelta

CHIAVE_ATTIVO = 'auto_supplenze_attivo'
CHIAVE_ORA = 'auto_supplenze_ora'
CHIAVE_FATTO = 'auto_supplenze_fatto'          # giorno (ISO) dell'ultimo invio concluso
CHIAVE_TENTATIVI = 'auto_supplenze_tentativi'  # "ISO-giorno:n"
CHIAVE_RIPROVA = 'auto_supplenze_riprova'      # ISO datetime del prossimo tentativo
CHIAVE_ESITO = 'auto_supplenze_esito'
ORA_DEFAULT = '15:30'
MAX_TENTATIVI = 3
PAUSA_RIPROVA = timedelta(minutes=10)
INTERVALLO_SECONDI = 30


def _get(chiave):
    from models.config_app import ConfigApp
    r = ConfigApp.query.filter_by(chiave=chiave).first()
    return r.valore if r else None


def _set(chiave, valore):
    from models import db
    from models.config_app import ConfigApp
    r = ConfigApp.query.filter_by(chiave=chiave).first()
    if r is None:
        db.session.add(ConfigApp(chiave=chiave, valore=valore))
    else:
        r.valore = valore


def ora_valida(testo):
    try:
        h, m = (testo or '').strip().split(':')
        return 0 <= int(h) <= 23 and 0 <= int(m) <= 59 and len(m) == 2
    except ValueError:
        return False


def impostazioni():
    ora = (_get(CHIAVE_ORA) or ORA_DEFAULT).strip()
    return {'attivo': _get(CHIAVE_ATTIVO) == '1',
            'ora': ora if ora_valida(ora) else ORA_DEFAULT,
            'esito': _get(CHIAVE_ESITO)}


def imposta(attivo, ora):
    """Salva attivazione e orario (l'orario non valido viene ignorato)."""
    from models import db
    _set(CHIAVE_ATTIVO, '1' if attivo else '0')
    ora = (ora or '').strip()
    if ora_valida(ora):
        h, m = ora.split(':')
        _set(CHIAVE_ORA, f'{int(h):02d}:{m}')
    db.session.commit()


def esegui(adesso=None):
    """Un giro di controllo. Ritorna una frase sull'esito, o None se non c'era niente da fare."""
    from models import db
    from modules import notifiche_email as ne
    adesso = adesso or datetime.now()
    imp = impostazioni()
    oggi = adesso.date()
    if not imp['attivo'] or oggi.weekday() == 6:     # niente invii di domenica
        return None
    h, m = imp['ora'].split(':')
    if adesso.time() < adesso.time().replace(hour=int(h), minute=int(m), second=0, microsecond=0):
        return None
    if _get(CHIAVE_FATTO) == oggi.isoformat():
        return None
    riprova = _get(CHIAVE_RIPROVA)
    if riprova and datetime.fromisoformat(riprova) > adesso:
        return None
    if ne.modalita() == 'off':
        return None                                   # invio spento: si riprova al giro dopo

    giorno = ne.giorno_default(oggi)
    ids = [p['docente'].id for p in ne.proposte_supplenze(giorno)
           if p['variante'] != 'gia_inviata' and not p['blocco']]
    risultati = ne.invia_supplenze(giorno, ids) if ids else []
    conteggio = {}
    for _, stato, _ in risultati:
        conteggio[stato] = conteggio.get(stato, 0) + 1
    errori = conteggio.get('errore', 0)

    prefisso, n = (_get(CHIAVE_TENTATIVI) or ':0').rsplit(':', 1)
    tentativi = (int(n) if prefisso == oggi.isoformat() else 0) + 1
    _set(CHIAVE_TENTATIVI, f'{oggi.isoformat()}:{tentativi}')
    if errori and tentativi < MAX_TENTATIVI:
        _set(CHIAVE_RIPROVA, (adesso + PAUSA_RIPROVA).isoformat(timespec='seconds'))
        seguito = f'{errori} errori, riprovo tra 10 minuti'
    else:
        _set(CHIAVE_FATTO, oggi.isoformat())
        _set(CHIAVE_RIPROVA, '')
        seguito = f'{errori} errori' if errori else 'concluso'
    parti = ', '.join(f'{v} {k}' for k, v in sorted(conteggio.items())) or 'nessuna notifica da inviare'
    frase = (f'{adesso.strftime("%d/%m %H:%M")} — supplenze di {giorno.strftime("%d/%m")}: '
             f'{parti} ({seguito})')
    _set(CHIAVE_ESITO, frase)
    db.session.commit()
    try:
        from routes.auth import log as auth_log
        auth_log('invio_automatico_supplenze', frase)
    except Exception:
        pass
    return frase


def avvia_thread(app):
    """Thread daemon: va chiamato una sola volta all'avvio (vedi app.py)."""
    def _loop():
        time.sleep(20)
        while True:
            try:
                with app.app_context():
                    frase = esegui()
                if frase:
                    print(f'[invio_automatico] {frase}', flush=True)
            except Exception:
                print('[invio_automatico] errore:\n' + traceback.format_exc(), flush=True)
                try:
                    from models import db
                    db.session.rollback()
                except Exception:
                    pass
            time.sleep(INTERVALLO_SECONDI)

    t = threading.Thread(target=_loop, name='invio_automatico', daemon=True)
    t.start()
    return t
