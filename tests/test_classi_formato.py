"""Etichette di classe: "4ALSU" (orario) e "4A LSU" (Assegnazioni) sono
la stessa classe — vedi modules/classi.py."""
from datetime import date, timedelta
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
from models.classe_concorso import ClasseConcorso
from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse
from modules.classi import etichetta_classe, stessa_classe, scomponi_classe
from tests.conftest import crea_docente

FUTURO = date.today() + timedelta(days=30)
ANNO = f'{FUTURO.year}-{FUTURO.year+1}' if FUTURO.month >= 9 else f'{FUTURO.year-1}-{FUTURO.year}'


def test_etichetta_classe_forme_equivalenti():
    for forma in ('4ALSU', '4A LSU', '4a lsu', ' 4A  LSU ', '4A\tLSU'):
        assert etichetta_classe(forma) == '4A LSU'
    assert etichetta_classe('1BAFM') == '1B AFM'
    assert etichetta_classe('POTENZIAMENTO') == 'POTENZIAMENTO'
    assert etichetta_classe(None) is None
    assert etichetta_classe('') == ''


def test_etichetta_classe_afm_senza_sezione_non_ambigua():
    # "1AFM": l'indirizzo noto AFM vince, resta "1 AFM" (nessuna sezione)
    assert etichetta_classe('1AFM') == '1 AFM'
    assert etichetta_classe('1AAFM') == '1A AFM'


def test_stessa_classe_e_scomponi():
    assert stessa_classe('4ALSU', '4A LSU')
    assert not stessa_classe('4ALSU', '4B LSU')
    assert not stessa_classe(None, '4A LSU')
    assert scomponi_classe('4ALSU') == ('4A', 'LSU')
    assert scomponi_classe('POTENZIAMENTO') == (None, None)


def test_iscrizione_docente_a_evento_con_classe_senza_spazio(app, db_session):
    from routes.attivita_ist import iscrivi_docente_a_eventi_classe
    d = crea_docente('Rossi')
    ev = AttivitaIst(tipo='consiglio_classe', titolo='CdC', classe='4ALSU',
                      data=FUTURO, origine='manuale')
    db.session.add(ev)
    db.session.commit()
    assert iscrivi_docente_a_eventi_classe(d.id, ['4A LSU'], anno_scol=ANNO) == 1
    assert AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id, id_docente=d.id).count() == 1


def test_form_evento_salva_classe_in_forma_canonica(app, db_session):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    with app.test_client() as c:
        r = c.post('/attivita-ist/nuova', data={
            'tipo': 'consiglio_classe', 'titolo': 'CdC', 'data': FUTURO.isoformat(),
            'classe': '4ALSU', 'partecipanti_form_presente': '1'})
        assert r.status_code == 302
    assert AttivitaIst.query.one().classe == '4A LSU'
