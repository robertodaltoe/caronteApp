"""
Test di regressione per la Sessione 54: un collaboratore del DS non deve
poter conoscere il motivo specifico di un'assenza (malattia, lutto,
permesso personale...) — solo se l'ora è recuperabile (permesso_orario)
o no ('non_recuperabile', motivo riservato a DS/DSGA/segreteria).

Copre tre livelli di difesa, tutti verificati qui:
1. l'etichetta mostrata (cat_label_visibile / label_motivo_assenza globale)
2. cosa il form propone in scrittura (contesto_form_assenza: tipi_visivi,
   utilizzi_ccnl)
3. la validazione server-side (registra_assenze_form/modifica_assenza),
   che non si fida del solo form — un ruolo senza titolo non può
   registrare né "scoprire" un motivo specifico nemmeno forzando il POST.
"""
from datetime import date
from flask import g

from models import db
from models.assenza import (
    Assenza, cat_label_visibile, motivo_visibile,
    MOTIVI_RISERVATI, RUOLI_MOTIVO_SPECIFICO, LABEL_INTERNE,
)
from modules.assenze_registrazione import (
    contesto_form_assenza, registra_assenze_form, modifica_assenza,
)
from tests.conftest import crea_docente


def _crea_tabelle_estese(app):
    with app.app_context():
        from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante, AttivitaIstPresenza  # noqa
        from models.scambio_orario import ScambioOrario, ScambioSlot  # noqa
        db.create_all()


# ── 1. Etichetta mostrata ───────────────────────────────────────────

def test_ruolo_non_autorizzato_vede_solo_etichetta_generica():
    for motivo in ('malattia', 'lutto', 'permesso_personale', 'matrimonio',
                    'permesso_sindacale', 'non_recuperabile'):
        assert cat_label_visibile(motivo, 'collaboratore') == LABEL_INTERNE['non_recuperabile']
        assert cat_label_visibile(motivo, None) == LABEL_INTERNE['non_recuperabile']


def test_ruoli_autorizzati_vedono_lo_specifico():
    for ruolo in ('ds', 'dsga', 'segreteria'):
        assert cat_label_visibile('lutto', ruolo) == LABEL_INTERNE['lutto']
        assert cat_label_visibile('malattia', ruolo) == LABEL_INTERNE['malattia']


def test_motivi_non_sensibili_visibili_a_tutti():
    for ruolo in (None, 'collaboratore', 'ds', 'segreteria'):
        assert cat_label_visibile('ferie', ruolo) == LABEL_INTERNE['ferie']
        assert cat_label_visibile('permesso_orario', ruolo) == LABEL_INTERNE['permesso_orario']


def test_motivo_visibile_maschera_il_codice_non_solo_etichetta():
    """Il valore da scrivere nell'HTML (campo nascosto del form) deve
    diventare 'non_recuperabile', non solo l'etichetta — altrimenti il
    valore reale resterebbe leggibile nel sorgente della pagina."""
    assert motivo_visibile('lutto', 'collaboratore') == 'non_recuperabile'
    assert motivo_visibile('lutto', 'ds') == 'lutto'
    assert motivo_visibile('ferie', 'collaboratore') == 'ferie'


# ── 2. Cosa propone il form in scrittura ────────────────────────────

def test_form_non_offre_motivi_specifici_a_ruolo_non_autorizzato(app, db_session):
    with app.app_context():
        ctx = contesto_form_assenza(date.today().isoformat(), ruolo='collaboratore')
    codici = {t[0] for t in ctx['tipi_visivi']}
    assert codici.isdisjoint(MOTIVI_RISERVATI - {'non_recuperabile'})
    assert 'non_recuperabile' in codici
    assert 'permesso_orario' in codici  # non sensibile, resta visibile


def test_form_offre_motivi_specifici_a_ruolo_autorizzato(app, db_session):
    with app.app_context():
        ctx = contesto_form_assenza(date.today().isoformat(), ruolo='ds')
    codici = {t[0] for t in ctx['tipi_visivi']}
    assert 'lutto' in codici
    assert 'malattia' in codici
    assert 'non_recuperabile' not in codici  # non gli serve: sceglie subito lo specifico


def test_form_senza_ruolo_esplicito_resta_prudente(app, db_session):
    """ruolo non passato (None): trattato come NON autorizzato, mai il
    contrario — un punto di chiamata che dimentica di passare il ruolo
    non deve poter esporre lo specifico per omissione."""
    with app.app_context():
        ctx = contesto_form_assenza(date.today().isoformat())
    codici = {t[0] for t in ctx['tipi_visivi']}
    assert 'lutto' not in codici
    assert 'non_recuperabile' in codici


def test_utilizzi_ccnl_non_espone_contatori_riservati_a_chi_non_ha_titolo(app, db_session):
    _crea_tabelle_estese(app)
    with app.app_context():
        d = crea_docente('Verdi')
        db.session.add(Assenza(id_docente=d.id, data=date(2025, 10, 10),
                                ora_inizio=1, ora_fine=2, motivo='lutto'))
        db.session.commit()

        ctx_collab = contesto_form_assenza(date.today().isoformat(), ruolo='collaboratore')
        assert not any(k.split('_')[1:2] == ['lutto'] for k in ctx_collab['utilizzi_ccnl'])
        assert all('lutto' not in k for k in ctx_collab['utilizzi_ccnl'])

        ctx_ds = contesto_form_assenza(date.today().isoformat(), ruolo='ds')
        assert any('lutto' in k for k in ctx_ds['utilizzi_ccnl'])


# ── 3. Validazione server-side (difesa in profondità) ───────────────

class _UtenteFinto:
    def __init__(self, ruolo, username='test'):
        self.ruolo = ruolo
        self.username = username


def _form(**over):
    base = {
        'id_docente': None, 'data': date.today().isoformat(),
        'ora_inizio': '3', 'ora_fine': '4', 'motivo': 'lutto',
        'note': '',
    }
    base.update(over)
    class F(dict):
        def getlist(self, k):
            v = self.get(k)
            return v if isinstance(v, list) else ([v] if v else [])
    return F(base)


def test_collaboratore_non_puo_registrare_motivo_specifico_forzando_il_post(app, db_session):
    _crea_tabelle_estese(app)
    with app.app_context():
        d = crea_docente('Neri')
        with app.test_request_context():
            g.utente = _UtenteFinto('collaboratore')
            registra_assenze_form(_form(id_docente=d.id, motivo='lutto'))
        creata = Assenza.query.filter_by(id_docente=d.id).first()
        assert creata.motivo == 'non_recuperabile'


def test_ds_puo_registrare_motivo_specifico(app, db_session):
    _crea_tabelle_estese(app)
    with app.app_context():
        d = crea_docente('Bruni')
        with app.test_request_context():
            g.utente = _UtenteFinto('ds')
            registra_assenze_form(_form(id_docente=d.id, motivo='lutto'))
        creata = Assenza.query.filter_by(id_docente=d.id).first()
        assert creata.motivo == 'lutto'


def test_collaboratore_non_puo_declassare_assenza_gia_classificata(app, db_session):
    """Il DS ha già riclassificato un'assenza come 'lutto'; il
    collaboratore la riapre solo per cambiare orario/note — non deve
    poterne cancellare la classificazione, nemmeno inviando il valore
    mascherato 'non_recuperabile' che il suo form gli mostra."""
    _crea_tabelle_estese(app)
    with app.app_context():
        d = crea_docente('Ferri')
        a = Assenza(id_docente=d.id, data=date(2025, 10, 10),
                    ora_inizio=1, ora_fine=2, motivo='lutto')
        db.session.add(a)
        db.session.commit()
        aid = a.id

        with app.test_request_context():
            g.utente = _UtenteFinto('collaboratore')
            a_ref = db.session.get(Assenza, aid)
            modifica_assenza(a_ref, _form(id_docente=d.id, data='2025-10-10',
                                           motivo='non_recuperabile'))
        db.session.refresh(a_ref)
        assert a_ref.motivo == 'lutto'


def test_ds_puo_riclassificare_unassenza_generica(app, db_session):
    _crea_tabelle_estese(app)
    with app.app_context():
        d = crea_docente('Gialli')
        a = Assenza(id_docente=d.id, data=date(2025, 10, 10),
                    ora_inizio=1, ora_fine=2, motivo='non_recuperabile')
        db.session.add(a)
        db.session.commit()
        aid = a.id

        with app.test_request_context():
            g.utente = _UtenteFinto('ds')
            a_ref = db.session.get(Assenza, aid)
            modifica_assenza(a_ref, _form(id_docente=d.id, data='2025-10-10',
                                           motivo='lutto'))
        db.session.refresh(a_ref)
        assert a_ref.motivo == 'lutto'
