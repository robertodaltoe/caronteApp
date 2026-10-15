"""
Regressione: i pulsanti Prec./Succ. nella scheda docente scorrevano anche
i docenti non più in servizio (anno_scol_uscita passato, attivo=True) che
l'elenco /docenti nasconde. La navigazione ora usa lo stesso elenco.
"""
from tests.test_docente_nuovo_render import app_reale  # noqa: F401


def test_prev_next_saltano_docenti_usciti(app_reale):  # noqa: F811
    from config_anno import get_anno_corrente
    from models import db
    from models.docente import Docente

    anno = get_anno_corrente()
    anno_passato = f"{int(anno[:4]) - 1}-{int(anno[:4])}"
    with app_reale.app_context():
        ids = {}
        for cogn, uscita in [('Aaa', None), ('Bbb', anno_passato), ('Ccc', None)]:
            d = Docente(cognome='ZZ' + cogn, nome='T', ore_contratto=18,
                        attivo=True, anno_scol_uscita=uscita)
            db.session.add(d)
            db.session.flush()
            ids[cogn] = d.id
        db.session.commit()

    with app_reale.test_client() as c:
        corpo = c.get(f"/docenti/{ids['Aaa']}/modifica").get_data(as_text=True)
        assert f"/docenti/{ids['Ccc']}/modifica" in corpo
        assert f"/docenti/{ids['Bbb']}/modifica" not in corpo


def test_disattivazione_usciti_e_storico(app_reale):  # noqa: F811
    from app import _migra_disattiva_docenti_usciti
    from config_anno import get_anno_corrente
    from models import db
    from models.docente import Docente
    from routes.impostazione_anno import _docenti_per_anno
    import tempfile

    anno = get_anno_corrente()
    prec = f"{int(anno[:4]) - 1}-{int(anno[:4])}"
    with app_reale.app_context():
        u = Docente(cognome='ZZUscito', nome='T', ore_contratto=18,
                    attivo=True, anno_scol_uscita=anno)
        r = Docente(cognome='ZZResta', nome='T', ore_contratto=18, attivo=True)
        e = Docente(cognome='ZZElim', nome='T', ore_contratto=18, attivo=False)
        db.session.add_all([u, r, e])
        db.session.commit()
        uid, rid, eid = u.id, r.id, e.id

        # base_dir vuoto: nessun database.db => nessun backup, solo la modifica
        _migra_disattiva_docenti_usciti(tempfile.mkdtemp())
        _migra_disattiva_docenti_usciti(tempfile.mkdtemp())  # idempotente

        assert db.session.get(Docente, uid).attivo is False
        assert db.session.get(Docente, rid).attivo is True
        corrente = {d.id for d in _docenti_per_anno(anno)}
        passato = {d.id for d in _docenti_per_anno(prec)}
        assert uid not in corrente and rid in corrente
        assert uid in passato and eid not in passato and eid not in corrente
