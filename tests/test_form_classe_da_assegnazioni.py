"""
Roberto: "quando modifico una voce con il tasto modifica che era stata
creata in automatico mi scompare il badge della classe".

Causa in routes/attivita_ist.py::form(): la tendina "Classe" del form
(classi_db) veniva popolata solo da OrarioDocente.query.all() — che dalla
Sessione 66 addendum 107/108 resta vuoto per settimane a inizio anno
scolastico. Aprendo il form di un Consiglio di classe/GLO già creato per
una classe non (ancora) in orario, la tendina non aveva quella classe tra
le opzioni: il <select> mostrava "— nessuna —", e salvando il form la
classe veniva sovrascritta a None — un evento con classe già impostata
la perdeva silenziosamente al primo salvataggio.

Fix: classi_db unisce anche le classi da Assegnazioni
(AssegnazioneClasse.label_classe), disponibili molto prima dell'orario.
"""
from datetime import date, timedelta
from models import db
from models.attivita_ist import AttivitaIst
from models.classe_concorso import ClasseConcorso
from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse
from tests.conftest import crea_docente

FUTURO = date.today() + timedelta(days=30)
ANNO = f'{FUTURO.year}-{FUTURO.year+1}' if FUTURO.month >= 9 else f'{FUTURO.year-1}-{FUTURO.year}'


def _registra_blueprint(app):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)


def test_classe_solo_in_assegnazioni_resta_nella_tendina_e_non_si_perde_al_salvataggio(app, db_session, monkeypatch):
    _registra_blueprint(app)

    docente = crea_docente('Rossi')
    cc = ClasseConcorso(codice='A012', nome='A012')
    db.session.add(cc)
    db.session.commit()
    asgn = AssegnazioneDocente(anno_scol=ANNO, id_classe_concorso=cc.id,
                                id_docente=docente.id, tipo='titolare')
    db.session.add(asgn)
    db.session.flush()
    db.session.add(AssegnazioneClasse(id_assegnazione=asgn.id, indirizzo='LSC',
                                       anno_corso=1, sezione='A', ore=9))
    db.session.commit()

    from models.orario_docente import OrarioDocente
    assert OrarioDocente.query.count() == 0  # condizione reale che ha fatto scoprire il bug

    ev = AttivitaIst(tipo='consiglio_classe', titolo='CdC 1A LSC', classe='1A LSC',
                      data=FUTURO, origine='manuale')
    db.session.add(ev)
    db.session.commit()

    import routes.attivita_ist as mod
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r_get = c.get(f'/attivita-ist/{ev.id}/modifica')
        assert r_get.status_code == 200
        assert '1A LSC' in catturato['kwargs']['classi']

    monkeypatch.undo()  # ripristina render_template reale per il POST (nessuna template renderizzata su redirect)
    with app.test_client() as c:
        r_post = c.post(f'/attivita-ist/{ev.id}/modifica', data={
            'tipo': 'consiglio_classe', 'titolo': 'CdC 1A LSC',
            'data': FUTURO.isoformat(), 'classe': '1A LSC',
            'partecipanti_form_presente': '1',
        })
        assert r_post.status_code == 302

    db.session.refresh(ev)
    assert ev.classe == '1A LSC'
