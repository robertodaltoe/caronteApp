"""
Roberto: nella scheda docente, il box "Materie insegnate" mostrava solo
l'anno corrente (get_anno_corrente()) senza modo di risalire a quelle
degli anni passati/futuri assegnate da Assegnazioni. Aggiunto un
selettore anno accanto al box (querystring ?anno_materie=...), che
filtra mat_assegnate per quell'anno invece che sempre per l'anno
corrente.
"""
from models import db
from models.materia import Dipartimento, Materia, DocenteMateria
from tests.conftest import crea_docente


def test_scheda_docente_mostra_materie_dellanno_selezionato(app, db_session, monkeypatch):
    import routes.docenti as mod
    if 'docenti' not in app.blueprints:
        app.register_blueprint(mod.docenti_bp)

    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    dip = Dipartimento(nome='Meccanica', sigla='MEC', ordine=1)
    db.session.add(dip)
    db.session.flush()
    mat = Materia(nome='Meccanica', sigla='MEC', id_dipartimento=dip.id)
    db.session.add(mat)
    db.session.flush()

    d = crea_docente('Palermo')
    db.session.add(DocenteMateria(id_docente=d.id, id_materia=mat.id, anno_scol='2026-2027'))
    db.session.commit()

    with app.test_client() as c:
        # Anno corrente (2025-2026, calcolato da get_anno_corrente()): la
        # materia assegnata per il 2026-2027 non deve comparire.
        r = c.get(f'/docenti/{d.id}/modifica')
        assert r.status_code == 200
    assert mat.id not in catturato['kwargs']['mat_assegnate']
    assert catturato['kwargs']['anno_sel_materie'] == catturato['kwargs']['anno_corrente_materie']

    with app.test_client() as c:
        r = c.get(f'/docenti/{d.id}/modifica?anno_materie=2026-2027')
        assert r.status_code == 200
    assert mat.id in catturato['kwargs']['mat_assegnate']
    assert catturato['kwargs']['anno_sel_materie'] == '2026-2027'
    assert '2026-2027' in catturato['kwargs']['anni_materie']
