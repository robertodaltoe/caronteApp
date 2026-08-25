"""
Sync automatico "additivo" in background.

Mentre l'app è aperta e funzionante, ogni INTERVALLO_SECONDI (30s di
default) un thread in background:

1. scarica (senza toccare il lock manuale di sync_db.py) il database
   pubblicato su Google Drive dall'altra postazione;
2. confronta, tabella per tabella (vedi TABELLE più sotto — 'assenze',
   'supplenze', 'indisponibilita': sono i dati che segreteria e chi
   gestisce le supplenze aggiornano in parallelo — vedi DEVLOG Task
   46 — più 'sostituzioni_scrutinio', aggiunta su richiesta esplicita
   di Roberto per verificare i conflitti tra postazioni anche sulle
   nomine dei sostituti agli scrutini), le righe locali e quelle remote
   usando una chiave logica stabile (es. docente+data+fascia oraria),
   non l'id autoincrementale, che può coincidere per righe diverse su
   database indipendenti;
3. importa in locale, in automatico, SOLO le righe che sul locale non
   esistono ancora (nessuna riga esistente viene mai modificata da
   questo meccanismo);
4. se la STESSA riga logica esiste su entrambe le macchine ma con un
   contenuto diverso (vero conflitto — es. la supplenza è stata
   assegnata in modo diverso sulle due postazioni), NON sceglie da
   sola: registra il conflitto in SyncConflitto e lo lascia in
   sospeso per la revisione umana in /sync/conflitti;
5. se ha aggiunto almeno una riga (o una lapide, vedi sotto), ripubblica
   su Drive il database locale aggiornato (così l'altra macchina, al
   giro successivo, riceve anche ciò che questa ha appena prodotto).

Le eliminazioni si propagano con un meccanismo di "lapidi" (tombstone,
vedi models/sync_tombstone.py): senza, una riga eliminata su una
postazione ricomparirebbe al giro successivo perché l'altra macchina la
ha ancora e verrebbe vista come "nuova". Quando una route elimina una
riga di 'assenze'/'supplenze' registra prima la sua chiave in
SyncTombstone (vedi registra_eliminazione più sotto); il merge unisce
le lapidi tra le macchine, non reintroduce mai una riga la cui chiave
ha una lapide, ed elimina anche in locale una riga la cui chiave
risulta lapidata dall'altra macchina.

Le cattedre annuali (assegnazioni_docenti/assegnazioni_classi) restano
FUORI da questo meccanismo: la struttura padre-figlio e i conflitti su
ore/classi richiedono lo stesso tipo di revisione manuale fatta per il
merge macmini→macbookpro del 5/8/2026 (vedi DEVLOG Task 45) — troppo
delicato per un merge automatico anche solo parziale.
"""
import json
import os
import platform
import sqlite3
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

def _parse_dt(v):
    """Converte in datetime un valore letto da SQLite grezzo (stringa
    ISO, possibile spazio invece di 'T') o già un datetime — None se
    mancante o non interpretabile. Usato per confrontare l'orario di
    una lapide con quello dell'ultima modifica di una riga (vedi sotto,
    'colonna_timestamp')."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v).replace(' ', 'T', 1))
    except ValueError:
        return None


INTERVALLO_SECONDI = 30
AUTOSYNC_LOCK_NAME = 'caronte_autosync.lock'
AUTOSYNC_LOCK_MAX_ETA_SEC = 180  # oltre questa età il lock si considera abbandonato (crash) e si ignora

_LOCK = threading.Lock()   # evita due giri sovrapposti sulla stessa macchina


def _chiave_assenza(r):
    # NOTA: 'motivo' non fa parte della chiave di identità — se lo stesso
    # docente ha un'assenza nella stessa fascia oraria dello stesso giorno
    # ma con un motivo diverso su due postazioni (es. "lutto" su una,
    # "malattia" sull'altra), è la STESSA riga logica modificata in modo
    # diverso: va segnalata come conflitto (motivo è in 'campi_confronto'
    # qui sotto), non trattata come due assenze distinte da sommare.
    return {
        'id_docente': r['id_docente'], 'data': r['data'],
        'ora_inizio': r['ora_inizio'], 'ora_fine': r['ora_fine'],
    }


def _chiave_supplenza(r):
    return {
        'data': r['data'], 'ora': r['ora'], 'classe': r['classe'],
        'id_assente': r['id_assente'],
    }


def _chiave_indisponibilita(r):
    return {
        'id_docente': r['id_docente'], 'data': r['data'], 'ora': r['ora'],
    }


def _chiave_sostituzione_scrutinio(r):
    # Stessa coppia dell'UniqueConstraint del modello (id_attivita,
    # id_assente): un solo sostituto nominato per assente per riunione.
    return {'id_attivita': r['id_attivita'], 'id_assente': r['id_assente']}


TABELLE = {
    'assenze': {
        'chiave': _chiave_assenza,
        'campi_confronto': ['motivo', 'classe_libera', 'note_interne',
                             'ora_ist_inizio', 'ora_ist_fine'],
        'colonne_insert': ['id_docente', 'data', 'ora_inizio', 'ora_fine',
                            'motivo', 'classe_libera', 'note_interne',
                            'creato_il', 'ora_ist_inizio', 'ora_ist_fine',
                            'creato_da'],
        'fk': [('id_docente', 'docenti')],
        'colonna_timestamp': 'creato_il',
        'label': lambda r: f"Assenza — docente #{r['id_docente']} il {r['data']} "
                            f"(ore {r['ora_inizio']}-{r['ora_fine']}, {r['motivo']})",
    },
    'supplenze': {
        'chiave': _chiave_supplenza,
        'campi_confronto': ['id_sostituto', 'tipo', 'stato', 'origine',
                             'note_display', 'note'],
        'colonne_insert': ['data', 'ora', 'classe', 'id_assente', 'id_sostituto',
                            'tipo', 'stato', 'origine', 'note_display', 'note',
                            'creato_il', 'modificato_il', 'creato_da'],
        'fk': [('id_assente', 'docenti'), ('id_sostituto', 'docenti')],
        'colonna_timestamp': 'modificato_il',
        'label': lambda r: f"Supplenza — {r['data']} ora {r['ora']} classe {r['classe']}",
    },
    'indisponibilita': {
        'chiave': _chiave_indisponibilita,
        'campi_confronto': ['motivo', 'note'],
        'colonne_insert': ['id_docente', 'data', 'ora', 'motivo', 'note',
                            'creato_il', 'creato_da'],
        'fk': [('id_docente', 'docenti')],
        'colonna_timestamp': 'creato_il',
        'label': lambda r: f"Indisponibilità — docente #{r['id_docente']} il {r['data']} "
                            f"(ora {r['ora'] if r['ora'] is not None else 'tutta la giornata'})",
    },
    'sostituzioni_scrutinio': {
        'chiave': _chiave_sostituzione_scrutinio,
        # id_attivita non è nei campi di confronto: è parte della chiave
        # logica stessa (identifica la riunione), non un valore che possa
        # "differire" tra le due macchine per la stessa riga.
        'campi_confronto': ['id_sostituto', 'n_protocollo', 'data_nomina', 'note'],
        'colonne_insert': ['id_attivita', 'id_assente', 'id_sostituto',
                            'n_protocollo', 'data_nomina', 'note',
                            'creato_il', 'modificato_il'],
        'colonna_timestamp': 'modificato_il',
        # id_attivita punta a AttivitaIst, che non è (ancora) in questo
        # meccanismo di sync — stessa assunzione già in uso per id_docente
        # verso 'docenti': se l'id non esiste in locale (evento creato
        # indipendentemente sulle due macchine, con id diversi) la riga
        # viene semplicemente saltata per questo giro, non forzata — non
        # una FK rotta, solo un sync rimandato finché l'evento non è
        # anche lui allineato (es. da un checkout/checkin manuale).
        'fk': [('id_assente', 'docenti'), ('id_sostituto', 'docenti'),
               ('id_attivita', 'attivita_ist')],
        'label': lambda r: f"Sostituzione scrutinio — evento #{r['id_attivita']}, "
                            f"assente #{r['id_assente']}",
    },
}


def registra_eliminazione(tabella, riga_dict, utente=None):
    """Da chiamare PRIMA di eliminare fisicamente una riga di 'assenze' o
    'supplenze' (db.session.delete/DELETE), passando la riga come dict
    con almeno i campi usati dalla sua chiave logica (vedi TABELLE).
    Registra una "lapide" così il sync automatico non la resuscita
    quando la trova ancora sull'altra macchina, e la elimina anche là.
    Idempotente — se esiste già una lapide per questa chiave non fa
    nulla. Non fa il commit: lo fa la route chiamante insieme
    all'eliminazione vera e propria, nella stessa transazione."""
    from models.sync_tombstone import SyncTombstone
    from models import db as _db

    if tabella not in TABELLE:
        return
    chiave_json = json.dumps(TABELLE[tabella]['chiave'](riga_dict), sort_keys=True)
    esiste = SyncTombstone.query.filter_by(
        tabella=tabella, chiave_logica=chiave_json).first()
    if not esiste:
        _db.session.add(SyncTombstone(
            tabella=tabella, chiave_logica=chiave_json, eliminato_da=utente))


def _prova_lock_autosync(cartella):
    """Lock leggero SU DRIVE, separato dal lock manuale di sync_db.py:
    evita che due macchine facciano il merge additivo nello stesso
    istante. Se il lock esiste già ma è più vecchio di
    AUTOSYNC_LOCK_MAX_ETA_SEC lo consideriamo abbandonato (es. l'altra
    macchina si è spenta a metà) e lo ignoriamo."""
    lock_path = Path(cartella) / AUTOSYNC_LOCK_NAME
    if lock_path.exists():
        eta = time.time() - lock_path.stat().st_mtime
        if eta < AUTOSYNC_LOCK_MAX_ETA_SEC:
            return None
    try:
        with open(lock_path, 'w', encoding='utf-8') as f:
            f.write(f"{platform.node()} — {datetime.now().isoformat()}")
    except OSError:
        return None
    return lock_path


def _rilascia_lock_autosync(lock_path):
    try:
        lock_path.unlink()
    except OSError:
        # Alcuni mount di rete non permettono l'unlink: svuotarlo e
        # lasciarlo con mtime corrente è comunque sufficiente a farlo
        # sembrare "appena rilasciato" — verrà ignorato al prossimo giro
        # non appena passano AUTOSYNC_LOCK_MAX_ETA_SEC secondi.
        pass


def _righe(conn, tabella):
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(f"SELECT * FROM {tabella}")]
    except sqlite3.OperationalError as e:
        if 'no such table' in str(e):
            # Il DB scaricato da Drive è stato pubblicato da una macchina
            # con codice più vecchio, che non ha ancora questa tabella
            # (es. le lapidi, introdotte dopo). Non è un errore: vuol
            # dire semplicemente "nessuna riga da lì", finché anche
            # l'altra macchina non aggiorna.
            return []
        raise


def _merge_additivo(db, tmp_remoto_path):
    """Confronta 'assenze'/'supplenze' tra il DB locale (via la sessione
    SQLAlchemy già connessa, viva, dell'app) e il DB remoto scaricato da
    Drive. Inserisce solo le righe nuove, segnala i conflitti reali,
    applica le eliminazioni tramite le lapidi (vedi modulo)."""
    from models.sync_conflitto import SyncConflitto
    from models.sync_tombstone import SyncTombstone

    conn_remoto = sqlite3.connect(tmp_remoto_path)
    conn_remoto.row_factory = sqlite3.Row

    inserite, conflitti_nuovi, conflitti_aggiornati, eliminate = 0, 0, 0, 0
    solo_locali = 0   # righe (o lapidi) che esistono qui ma non (ancora) su
                       # Drive: segnala che tocca ripubblicare, altrimenti
                       # l'altra postazione non le vedrebbe mai finché non
                       # chiudiamo l'app (l'unico altro momento in cui si
                       # pubblica).
    dettagli = []

    try:
        # --- 0) Lapidi: si uniscono per prime, sono "solo aggiunta" — non
        # può mai esserci un conflitto su un'eliminazione (o è lapidata o
        # non lo è). Il set risultante serve sia a NON reintrodurre righe
        # eliminate altrove, sia a eliminare qui righe la cui lapide è
        # appena arrivata dall'altra macchina. ---
        tomb_remote = _righe(conn_remoto, 'sync_tombstones')
        tomb_locali_rows = SyncTombstone.query.all()
        tomb_locali = {(t.tabella, t.chiave_logica) for t in tomb_locali_rows}
        tomb_remote_set = {(t['tabella'], t['chiave_logica']) for t in tomb_remote}
        # Orario della lapide per ogni chiave, usato sotto per non
        # ricancellare una riga più recente della lapide stessa (vedi
        # 'colonna_timestamp'). Preservare l'eliminato_il ORIGINALE del
        # remoto quando si importa una lapide non vista prima è
        # essenziale: prima veniva ri-timbrata "adesso" al momento
        # dell'importazione, rendendo impossibile qualunque confronto
        # sensato con l'orario di modifica di una riga (bug trovato
        # insieme a quello sotto, Sessione 66 addendum 54).
        tomb_ts = {(t.tabella, t.chiave_logica): t.eliminato_il for t in tomb_locali_rows}

        for t in tomb_remote:
            chiave_t = (t['tabella'], t['chiave_logica'])
            ts_remoto = _parse_dt(t.get('eliminato_il'))
            if chiave_t not in tomb_locali:
                db.session.add(SyncTombstone(
                    tabella=t['tabella'], chiave_logica=t['chiave_logica'],
                    eliminato_il=ts_remoto or datetime.utcnow(),
                    eliminato_da=t.get('eliminato_da')))
                tomb_locali.add(chiave_t)
                tomb_ts[chiave_t] = ts_remoto
            elif ts_remoto and (tomb_ts.get(chiave_t) is None or ts_remoto > tomb_ts[chiave_t]):
                tomb_ts[chiave_t] = ts_remoto

        solo_locali += sum(1 for k in tomb_locali if k not in tomb_remote_set)

        for tabella, cfg in TABELLE.items():
            tomb_per_tabella = {chiave for (tab, chiave) in tomb_locali if tab == tabella}
            colonna_ts = cfg.get('colonna_timestamp')

            righe_remote = _righe(conn_remoto, tabella)
            righe_locali = [dict(r._mapping) for r in
                             db.session.execute(text(f"SELECT * FROM {tabella}"))]
            mappa_locale = {json.dumps(cfg['chiave'](r), sort_keys=True): r
                             for r in righe_locali}

            # Righe presenti in locale la cui chiave è lapidata (da questa
            # macchina o dall'altra): vanno eliminate anche qui, non solo
            # ignorate — altrimenti resterebbero visibili in locale mentre
            # sull'altra macchina non ci sono più.
            for chiave_json, riga_locale in list(mappa_locale.items()):
                if chiave_json in tomb_per_tabella:
                    # Una riga più recente della lapide stessa non va
                    # cancellata: significa che qualcuno ha inserito
                    # apposta dati nuovi per questa chiave DOPO che era
                    # stata cancellata altrove — la lapide è superata
                    # (bug reale: una nomina appena salvata su una
                    # postazione spariva di nuovo perché una lapide
                    # "vecchia" della stessa chiave era ancora presente
                    # su Drive, vedi DEVLOG Sessione 66 addendum 54).
                    ts_lapide = tomb_ts.get((tabella, chiave_json))
                    ts_riga = _parse_dt(riga_locale.get(colonna_ts)) if colonna_ts else None
                    if ts_riga and ts_lapide and ts_riga > ts_lapide:
                        continue
                    db.session.execute(
                        text(f"DELETE FROM {tabella} WHERE id=:id"),
                        {'id': riga_locale['id']})
                    del mappa_locale[chiave_json]
                    eliminate += 1
                    dettagli.append(f"- {cfg['label'](riga_locale)}")

            chiavi_remote = {json.dumps(cfg['chiave'](r), sort_keys=True)
                              for r in righe_remote}
            solo_locali += sum(1 for k in mappa_locale if k not in chiavi_remote)

            for r_remota in righe_remote:
                chiave = cfg['chiave'](r_remota)
                chiave_json = json.dumps(chiave, sort_keys=True)
                if chiave_json in tomb_per_tabella:
                    ts_lapide = tomb_ts.get((tabella, chiave_json))
                    ts_remota = _parse_dt(r_remota.get(colonna_ts)) if colonna_ts else None
                    if not (ts_remota and ts_lapide and ts_remota > ts_lapide):
                        continue  # eliminata (qui o là), non superata da dati più recenti: non reintrodurla
                locale = mappa_locale.get(chiave_json)

                if locale is None:
                    fk_ok = True
                    for campo, tabella_fk in cfg['fk']:
                        val = r_remota.get(campo)
                        if val is not None:
                            trovato = db.session.execute(
                                text(f"SELECT 1 FROM {tabella_fk} WHERE id=:id"),
                                {'id': val}).first()
                            if not trovato:
                                fk_ok = False
                                break
                    if not fk_ok:
                        continue  # riga collegata non presente in locale: non rischiare una FK rotta

                    colonne = cfg['colonne_insert']
                    valori = {c: r_remota.get(c) for c in colonne}
                    placeholders = ', '.join(f':{c}' for c in colonne)
                    db.session.execute(
                        text(f"INSERT INTO {tabella} ({', '.join(colonne)}) "
                             f"VALUES ({placeholders})"),
                        valori)
                    inserite += 1
                    dettagli.append(f"+ {cfg['label'](r_remota)}")
                else:
                    diversi = [c for c in cfg['campi_confronto']
                               if r_remota.get(c) != locale.get(c)]
                    if not diversi:
                        continue
                    esistente = SyncConflitto.query.filter_by(
                        tabella=tabella, chiave_logica=chiave_json,
                        risolto=False).first()
                    if esistente:
                        esistente.campi_diversi = json.dumps(diversi)
                        esistente.dati_locali = json.dumps(locale, default=str)
                        esistente.dati_remoti = json.dumps(r_remota, default=str)
                        esistente.aggiornato_il = datetime.utcnow()
                        conflitti_aggiornati += 1
                        continue

                    # Scegliendo "tieni versione locale" il contenuto non
                    # cambia: resta diverso da quello remoto anche dopo la
                    # risoluzione. Senza questo controllo, il giro
                    # successivo lo vedrebbe di nuovo diverso e ne
                    # creerebbe uno NUOVO (nessun conflitto "non risolto"
                    # con questa chiave) — un ciclo infinito. Se la stessa
                    # identica proposta remota era già stata rifiutata in
                    # passato, non richiederla di nuovo; se invece il
                    # valore remoto è cambiato da allora, è un conflitto
                    # genuinamente nuovo e va segnalato.
                    gia_deciso = (SyncConflitto.query
                                  .filter_by(tabella=tabella, chiave_logica=chiave_json,
                                             risolto=True, scelta='locale')
                                  .order_by(SyncConflitto.risolto_il.desc())
                                  .first())
                    if gia_deciso:
                        remoto_deciso = json.loads(gia_deciso.dati_remoti or '{}')
                        campi_decisi = set(json.loads(gia_deciso.campi_diversi or '[]'))
                        if (campi_decisi == set(diversi) and
                                all(remoto_deciso.get(c) == r_remota.get(c) for c in diversi)):
                            continue  # stessa proposta già rifiutata: non richiedere di nuovo

                    db.session.add(SyncConflitto(
                        tabella=tabella,
                        chiave_logica=chiave_json,
                        descrizione=cfg['label'](r_remota),
                        campi_diversi=json.dumps(diversi),
                        dati_locali=json.dumps(locale, default=str),
                        dati_remoti=json.dumps(r_remota, default=str),
                    ))
                    conflitti_nuovi += 1

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    finally:
        conn_remoto.close()

    return {
        'inserite': inserite,
        'eliminate': eliminate,
        'conflitti_nuovi': conflitti_nuovi,
        'conflitti_aggiornati': conflitti_aggiornati,
        'solo_locali': solo_locali,
        'dettagli': dettagli,
    }


def esegui_sync_automatico(app):
    """Un giro di sync additivo. Va richiamata dentro un app_context
    Flask attivo. Ritorna un dict di riepilogo (usato solo per il log)."""
    if not _LOCK.acquire(blocking=False):
        return {'saltato': 'giro precedente ancora in corso su questa macchina'}

    lock_drive = None
    try:
        from sync_db import cartella_drive, DRIVE_DB_NAME, carica
        from modules.backup_cifrato import decifra_file
        from models import db

        cartella = cartella_drive()
        if not cartella:
            return {'saltato': 'Google Drive non trovato'}

        db_drive = Path(cartella) / DRIVE_DB_NAME
        if not db_drive.exists():
            return {'saltato': 'nessun database pubblicato su Drive'}

        lock_drive = _prova_lock_autosync(cartella)
        if lock_drive is None:
            return {'saltato': 'sync occupato da un altro giro/un\'altra postazione'}

        tmp_dir = Path(app.root_path) / 'data' / 'tmp_autosync'
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_remoto = tmp_dir / 'remoto.db'
        try:
            decifra_file(str(db_drive), str(tmp_remoto))
        except Exception as e:
            return {'errore': f'impossibile decifrare il DB da Drive: {e}'}

        db_locale = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')

        risultato = _merge_additivo(db, str(tmp_remoto))

        try:
            tmp_remoto.unlink()
        except OSError:
            pass

        # Ripubblica su Drive se: abbiamo importato qualcosa dall'altra
        # postazione, OPPURE abbiamo noi righe locali (es. un'assenza
        # appena inserita qui) che su Drive non ci sono ancora — altrimenti
        # l'altra macchina non le vedrebbe mai finché qualcuno non chiude
        # l'app (unico altro momento in cui si pubblica).
        if risultato['inserite'] > 0 or risultato['solo_locali'] > 0:
            carica(db_locale)

        return risultato
    except Exception as e:
        return {'errore': str(e), 'trace': traceback.format_exc()}
    finally:
        if lock_drive is not None:
            _rilascia_lock_autosync(lock_drive)
        _LOCK.release()


def avvia_thread_autosync(app):
    """Avvia il ciclo in un thread daemon separato. Va chiamata una sola
    volta all'avvio dell'app (vedi app.py — con guardia contro il doppio
    avvio dovuto al reloader di Flask in debug)."""

    def _loop():
        # Piccola attesa iniziale: lascia che l'app finisca di avviarsi
        # (migrazioni, seed) prima del primo giro.
        time.sleep(10)
        while True:
            try:
                with app.app_context():
                    risultato = esegui_sync_automatico(app)
                # Una riga ad OGNI giro (non solo quando succede qualcosa):
                # serve a vedere da terminale che il thread è davvero
                # attivo, non solo quando c'è qualcosa da segnalare.
                # print() invece di app.logger perché il livello di log di
                # Flask di default filtra via gli INFO anche in debug.
                print(f"[auto_sync] {datetime.now().strftime('%H:%M:%S')} — {risultato}",
                      flush=True)
            except Exception:
                print("[auto_sync] errore nel giro periodico:\n"
                      + traceback.format_exc(), flush=True)
            time.sleep(INTERVALLO_SECONDI)

    t = threading.Thread(target=_loop, name='auto_sync', daemon=True)
    t.start()
    return t
