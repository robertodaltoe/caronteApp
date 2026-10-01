"""
Nuovo tipo di contratto 'suppl_breve' — "Contratto Suppl. Breve"
(richiesto da Roberto): supplente temporaneo che sostituisce un docente
assente (es. malattia) per un breve periodo (1, 2 o 3 mesi).

Deve comparire ovunque si sceglie il tipo di contratto: anagrafica
docente, Docenti anno (aggiunta docente e contratto per anno), e come
ogni contratto a termine non va considerato in servizio a luglio/agosto.

I test di rendering usano l'app reale su una copia isolata del database
(fixture app_reale di test_docente_nuovo_render.py), mai database.db.
"""
from datetime import date

from tests.conftest import crea_docente
from tests.test_docente_nuovo_render import app_reale  # noqa: F401 (fixture)


def test_etichette_suppl_breve():
    from models.docente import TIPO_CONTRATTO_LABELS, TIPO_CONTRATTO_LABELS_BREVI
    assert TIPO_CONTRATTO_LABELS['suppl_breve'] == 'Contratto Suppl. Breve'
    assert 'suppl_breve' in TIPO_CONTRATTO_LABELS_BREVI
    # I valori esistenti restano invariati.
    assert TIPO_CONTRATTO_LABELS['supplente'] == 'TD fino a GS'
    assert TIPO_CONTRATTO_LABELS['TD_GS'] == 'TD 30 giugno'


def test_label_su_docente(app, db_session):
    d = crea_docente('Breve', tipo_contratto='suppl_breve')
    assert d.tipo_contratto_label == 'Contratto Suppl. Breve'


def test_suppl_breve_non_in_servizio_ad_agosto(app, db_session):
    from routes.attivita_ist import _non_in_servizio_per_data
    d = crea_docente('Breve', tipo_contratto='suppl_breve')
    oggi = date.today()
    anno = oggi.year if oggi.month >= 9 else oggi.year - 1
    assert d.id in _non_in_servizio_per_data(date(anno + 1, 8, 20))
    assert d.id not in _non_in_servizio_per_data(date(anno + 1, 3, 10))


def test_anagrafica_mostra_opzione(app_reale):  # noqa: F811
    with app_reale.test_client() as c:
        r = c.get('/docenti/nuovo')
        assert r.status_code == 200
        assert 'value="suppl_breve"' in r.get_data(as_text=True)


def test_docenti_anno_aggiunge_suppl_breve(app_reale):  # noqa: F811
    from models.docente import Docente
    app_reale.config['WTF_CSRF_ENABLED'] = False
    with app_reale.test_client() as c:
        r = c.get('/impostazione-anno/docenti-anno')
        assert r.status_code == 200
        corpo = r.get_data(as_text=True)
        assert '<option value="suppl_breve">Contratto Suppl. Breve</option>' in corpo

        r = c.post('/impostazione-anno/docenti-anno',
                   data={'azione': 'aggiungi_docente', 'cognome': 'Breve',
                         'nome': 'Prova', 'tipo_contratto': 'suppl_breve',
                         'ruolo': 'titolare'})
        assert r.status_code in (200, 302)

    with app_reale.app_context():
        d = Docente.query.filter_by(cognome='BREVE').one()
        assert d.tipo_contratto == 'suppl_breve'
        assert d.tipo_contratto_label == 'Contratto Suppl. Breve'
