"""
Roberto, prima di eseguire il cambio anno reale: "ho un dubbio; ho
delle indisponibilità che scavalcano l'anno scolastico [...] quelli
li perderò?" — verificato nel codice: routes/cambio_anno.py::attiva()
cancellava TUTTE le righe di Indisponibilita senza alcun filtro per
data (Indisponibilita.query.delete() sull'intera tabella), non solo
quelle dell'anno che si chiude — un'indisponibilità già inserita per
il nuovo anno sarebbe sparita insieme alle vecchie.

Fix: elimina solo le righe datate entro la fine dell'anno precedente
(31/08), lasciando intatte quelle già inserite per il nuovo anno.

Poi, alla domanda "Backup cifrato prima di 'Attiva' questo è
predisposto?": non lo era — l'unico backup esistente è quello
giornaliero legato all'avvio del server (app.py::_backup_automatico),
non garantito recente se il server è acceso da giorni. Aggiunto un
backup cifrato dedicato dentro attiva() stessa, prima di ogni
scrittura, con annullamento dell'intera operazione se il backup fallisce.

I test qui sotto NON devono mai toccare il vero database.db/la vera
cartella data/backup del progetto — crea_backup_cifrato è quindi
sempre monkeypatchata con un finto che si limita a registrare la
chiamata, invece di cifrare/scrivere file reali.
"""
from datetime import date
from models import db
from models.indisponibilita import Indisponibilita
from models.config_app import ConfigApp
from models.piano_studi import ClasseSezione


def _imposta_anno_corrente(anno):
    db.session.add(ConfigApp(chiave='anno_scol_corrente', valore=anno))
    db.session.commit()


def _registra_blueprint(app):
    import routes.cambio_anno as mod
    if 'cambio_anno' not in app.blueprints:
        app.register_blueprint(mod.cambio_anno_bp)
    return mod


def _finto_backup(chiamate, path_ritorno='/finto/backup.db.enc'):
    def _fake(db_path, backup_dir, suffisso=''):
        chiamate.append({'db_path': db_path, 'backup_dir': backup_dir, 'suffisso': suffisso})
        return path_ritorno
    return _fake


def test_attiva_crea_il_backup_prima_di_scrivere(app, db_session, monkeypatch):
    mod = _registra_blueprint(app)
    chiamate = []
    monkeypatch.setattr(mod, 'crea_backup_cifrato', _finto_backup(chiamate))
    _imposta_anno_corrente('2025-2026')
    db.session.add(ClasseSezione(anno_scol='2026-2027', indirizzo='AFM',
                                  anno_corso=1, sezione='A', attiva=False))
    db.session.commit()

    with app.test_client() as c:
        r = c.post('/cambio-anno/attiva', data={
            'anno_nuovo': '2026-2027', 'conferma': 'CONFERMO',
        })
        assert r.status_code == 302

    assert len(chiamate) == 1
    assert '2025-2026' in chiamate[0]['suffisso']
    assert '2026-2027' in chiamate[0]['suffisso']
    from config_anno import get_anno_corrente
    assert get_anno_corrente() == '2026-2027'  # l'operazione è comunque proseguita


def test_attiva_annulla_tutto_se_il_backup_fallisce(app, db_session, monkeypatch):
    """Se il backup non riesce, l'operazione si ferma subito: niente
    anno cambiato, niente indisponibilità cancellate."""
    mod = _registra_blueprint(app)

    def _fake_fallisce(db_path, backup_dir, suffisso=''):
        raise OSError('disco pieno (simulato)')
    monkeypatch.setattr(mod, 'crea_backup_cifrato', _fake_fallisce)

    _imposta_anno_corrente('2025-2026')
    db.session.add(ClasseSezione(anno_scol='2026-2027', indirizzo='AFM',
                                  anno_corso=1, sezione='A', attiva=False))
    db.session.add(Indisponibilita(id_docente=1, data=date(2026, 6, 4), motivo='altro'))
    db.session.commit()

    with app.test_client() as c:
        r = c.post('/cambio-anno/attiva', data={
            'anno_nuovo': '2026-2027', 'conferma': 'CONFERMO',
        })
        assert r.status_code == 302

    from config_anno import get_anno_corrente
    assert get_anno_corrente() == '2025-2026'  # invariato
    assert Indisponibilita.query.count() == 1  # nulla cancellato


def test_attiva_elimina_solo_indisponibilita_anno_precedente(app, db_session, monkeypatch):
    mod = _registra_blueprint(app)
    monkeypatch.setattr(mod, 'crea_backup_cifrato', _finto_backup([]))
    _imposta_anno_corrente('2025-2026')

    # L'anno nuovo deve risultare "preparato" (almeno una ClasseSezione)
    db.session.add(ClasseSezione(anno_scol='2026-2027', indirizzo='AFM',
                                  anno_corso=1, sezione='A', attiva=False))
    db.session.commit()

    # Indisponibilità dell'anno che si chiude (deve sparire)
    db.session.add(Indisponibilita(id_docente=1, data=date(2026, 6, 4), motivo='altro'))
    db.session.add(Indisponibilita(id_docente=1, data=date(2026, 8, 31), motivo='altro'))
    # Indisponibilità già inserita per il nuovo anno (deve restare)
    db.session.add(Indisponibilita(id_docente=1, data=date(2026, 10, 15), motivo='altro'))
    db.session.commit()

    with app.test_client() as c:
        r = c.post('/cambio-anno/attiva', data={
            'anno_nuovo': '2026-2027', 'conferma': 'CONFERMO',
        })
        assert r.status_code == 302

    rimaste = Indisponibilita.query.all()
    assert len(rimaste) == 1
    assert rimaste[0].data == date(2026, 10, 15)


def test_attiva_registra_le_lapidi_per_le_indisponibilita_eliminate(app, db_session, monkeypatch):
    """Prova reale (prima esecuzione di attiva() sul DB reale): le righe
    eliminate senza lapide sono state resuscitate dal thread di sync
    automatico in background alla prima occasione utile — 'indisponibilita'
    è una delle tabelle sincronizzate additivamente (modules/auto_sync.py).
    Senza una lapide per ciascuna, il prossimo giro di sync le rivede
    come "nuove dall'altra macchina" e le reinserisce."""
    from models.sync_tombstone import SyncTombstone
    mod = _registra_blueprint(app)
    monkeypatch.setattr(mod, 'crea_backup_cifrato', _finto_backup([]))
    _imposta_anno_corrente('2025-2026')
    db.session.add(ClasseSezione(anno_scol='2026-2027', indirizzo='AFM',
                                  anno_corso=1, sezione='A', attiva=False))
    db.session.add(Indisponibilita(id_docente=7, data=date(2026, 6, 4), ora=None, motivo='altro'))
    db.session.commit()

    with app.test_client() as c:
        c.post('/cambio-anno/attiva', data={
            'anno_nuovo': '2026-2027', 'conferma': 'CONFERMO',
        })

    lapidi = SyncTombstone.query.filter_by(tabella='indisponibilita').all()
    assert len(lapidi) == 1
    import json
    chiave = json.loads(lapidi[0].chiave_logica)
    assert chiave == {'id_docente': 7, 'data': '2026-06-04', 'ora': None}


def test_attiva_senza_indisponibilita_future_le_elimina_tutte(app, db_session, monkeypatch):
    """Caso comune (nessuna indisponibilità ancora inserita per il nuovo
    anno): il comportamento resta lo stesso di prima, tutto svuotato."""
    mod = _registra_blueprint(app)
    monkeypatch.setattr(mod, 'crea_backup_cifrato', _finto_backup([]))
    _imposta_anno_corrente('2025-2026')
    db.session.add(ClasseSezione(anno_scol='2026-2027', indirizzo='AFM',
                                  anno_corso=1, sezione='A', attiva=False))
    db.session.add(Indisponibilita(id_docente=1, data=date(2026, 5, 1), motivo='altro'))
    db.session.add(Indisponibilita(id_docente=2, data=date(2026, 8, 31), motivo='altro'))
    db.session.commit()

    with app.test_client() as c:
        c.post('/cambio-anno/attiva', data={
            'anno_nuovo': '2026-2027', 'conferma': 'CONFERMO',
        })

    assert Indisponibilita.query.count() == 0
