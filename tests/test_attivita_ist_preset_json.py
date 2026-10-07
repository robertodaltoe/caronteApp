"""
Roberto: creando un CdC straordinario scegliendo solo la classe si
aspettava tutti i docenti della classe come partecipanti (con segnalati
gli assenti/indisponibili/già impegnati). Prima la checklist di un
evento nuovo partiva vuota e il form inviava sempre la sentinella
"partecipanti_form_presente": risultato, zero partecipanti.

Il form ora chiede il preset a /attivita-ist/preset-partecipanti a ogni
cambio di tipo/classe/data; qui si verifica quell'endpoint.
"""
from datetime import date, timedelta
from models import db
from models.assenza import Assenza
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
from models.classe_concorso import ClasseConcorso
from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse
from models.indisponibilita import Indisponibilita
from tests.conftest import crea_docente

FUTURO = date.today() + timedelta(days=30)
ANNO = f'{FUTURO.year}-{FUTURO.year+1}' if FUTURO.month >= 9 else f'{FUTURO.year-1}-{FUTURO.year}'


def _setup(app):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    cc = ClasseConcorso(codice='A012', nome='A012')
    db.session.add(cc)
    db.session.commit()
    docenti = [crea_docente(n) for n in ('Rossi', 'Bianchi', 'Verdi', 'Neri')]
    for d in docenti[:3]:  # Neri non insegna nella classe
        a = AssegnazioneDocente(anno_scol=ANNO, id_classe_concorso=cc.id,
                                 id_docente=d.id, tipo='titolare')
        db.session.add(a)
        db.session.flush()
        db.session.add(AssegnazioneClasse(id_assegnazione=a.id, indirizzo='LSC',
                                           anno_corso=3, sezione='A', ore=3))
    db.session.commit()
    return docenti


def test_preset_cdc_docenti_della_classe_con_segnalazioni(app, db_session):
    rossi, bianchi, verdi, neri = _setup(app)
    db.session.add(Assenza(id_docente=bianchi.id, data=FUTURO))
    db.session.add(Indisponibilita(id_docente=verdi.id, data=FUTURO, ora=None))
    altro = AttivitaIst(tipo='collegio', titolo='Collegio', data=FUTURO,
                         ora_inizio='14:30', ora_fine='16:30', origine='manuale')
    db.session.add(altro)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=altro.id, id_docente=rossi.id))
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/attivita-ist/preset-partecipanti', query_string={
            'tipo': 'consiglio_classe', 'classe': '3A LSC',
            'data': FUTURO.isoformat(), 'ora_inizio': '15:00', 'ora_fine': '16:00'})
    j = r.get_json()
    assert set(j['ids']) == {rossi.id, bianchi.id, verdi.id}
    seg = j['segnalazioni']
    assert 'assente' in seg[str(bianchi.id)][0]
    assert 'indisponibile' in seg[str(verdi.id)][0]
    assert 'Collegio' in seg[str(rossi.id)][0]
    assert str(neri.id) not in seg


def test_preset_non_segnala_riunione_non_sovrapposta(app, db_session):
    rossi, *_ = _setup(app)
    altro = AttivitaIst(tipo='collegio', titolo='Collegio', data=FUTURO,
                         ora_inizio='08:00', ora_fine='09:00', origine='manuale')
    db.session.add(altro)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=altro.id, id_docente=rossi.id))
    db.session.commit()
    with app.test_client() as c:
        j = c.get('/attivita-ist/preset-partecipanti', query_string={
            'tipo': 'consiglio_classe', 'classe': '3A LSC',
            'data': FUTURO.isoformat(), 'ora_inizio': '15:00', 'ora_fine': '16:00'}).get_json()
    assert str(rossi.id) not in j['segnalazioni']


def test_preset_data_non_valida_risposta_vuota(app, db_session):
    _setup(app)
    with app.test_client() as c:
        j = c.get('/attivita-ist/preset-partecipanti',
                  query_string={'tipo': 'consiglio_classe', 'data': ''}).get_json()
    assert j == {'ids': [], 'segnalazioni': {}}
