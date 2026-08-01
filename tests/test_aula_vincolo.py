"""
Test di regressione: la stessa classe deve poter avere aule diverse in
anni scolastici diversi (vincolo UNIQUE su anno_scol+classe, non su
classe da sola). Vedi DEVLOG Sessione 4 e app.py::_migra_vincolo_aule
per la storia di questo bug.
"""
import pytest
from sqlalchemy.exc import IntegrityError
from models import db
from models.aula import Aula


def test_stessa_classe_anni_diversi_e_permessa(app):
    """Il vincolo UNIQUE è su (anno_scol, classe): stessa classe, anni
    diversi, deve essere permesso senza IntegrityError."""
    with app.app_context():
        db.session.add(Aula(anno_scol='2025-2026', classe='1A AFM',
                             aula='10', sede='Sede Centrale - Piano Terra'))
        db.session.add(Aula(anno_scol='2026-2027', classe='1A AFM',
                             aula='11', sede='Sede Centrale - Piano Terra'))
        db.session.commit()

        righe = Aula.query.filter_by(classe='1A AFM').order_by(Aula.anno_scol).all()
        assert len(righe) == 2
        assert righe[0].anno_scol == '2025-2026' and righe[0].aula == '10'
        assert righe[1].anno_scol == '2026-2027' and righe[1].aula == '11'


def test_stessa_classe_stesso_anno_e_vietata(app):
    """Stessa classe, stesso anno: deve violare il vincolo UNIQUE."""
    with app.app_context():
        db.session.add(Aula(anno_scol='2025-2026', classe='1A AFM',
                             aula='10', sede='Sede Centrale - Piano Terra'))
        db.session.commit()

        db.session.add(Aula(anno_scol='2025-2026', classe='1A AFM',
                             aula='99', sede='Sede Staccata'))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_stesso_anno_classi_diverse_e_permesso(app):
    """Stesso anno, classi diverse: sempre stato permesso, verifica che
    il nuovo vincolo non lo rompa."""
    with app.app_context():
        db.session.add(Aula(anno_scol='2025-2026', classe='1A AFM',
                             aula='10', sede='Sede Centrale - Piano Terra'))
        db.session.add(Aula(anno_scol='2025-2026', classe='1B AFM',
                             aula='11', sede='Sede Centrale - Piano Terra'))
        db.session.commit()
        assert Aula.query.filter_by(anno_scol='2025-2026').count() == 2
