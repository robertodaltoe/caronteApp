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
