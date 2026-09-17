"""
Roberto: nel form di registrazione assenza, cambiando la data
dell'assenza il riquadro "Attività istituzionali in programma questo
giorno" non si aggiornava — restava sempre quello della data con cui
il form si era aperto.

Causa: contesto_form_assenza() interrogava un SOLO giorno
(eventi_ist_giorno) e il template lo renderizzava una volta sola lato
server; il campo data del form invece si può cambiare senza ricaricare
la pagina. Fix: una mappa data->eventi per l'intero anno scolastico
(eventi_ist_per_data, stesso raggio di inizio_as/fine_as già usato per
gli utilizzi CCNL), passata come JSON al template e riletta lato
client ad ogni cambio data (stesso meccanismo già in uso per
DATE_SOSPESE/verificaSospensione in templates/assenza_form.html).

Questi test coprono solo la parte Python (la mappa costruita da
contesto_form_assenza); il comportamento lato JS non è testabile da
qui, verificato invece a mano in browser.
"""
from datetime import date

from models import db
from models.attivita_ist import AttivitaIst
from modules.assenze_registrazione import contesto_form_assenza


def _crea_tabelle(app):
    with app.app_context():
        from models.attivita_ist import AttivitaIstPartecipante, AttivitaIstPresenza  # noqa
        from models.scambio_orario import ScambioOrario, ScambioSlot  # noqa
        db.create_all()


def _anno_scol_corrente_oggi():
    oggi = date.today()
    return oggi.year if oggi.month >= 9 else oggi.year - 1


def test_eventi_ist_per_data_raggruppa_per_giorno(app, db_session):
    """La mappa deve contenere una voce per ciascuna data con eventi,
    con la lista degli eventi di quel giorno -- è la stessa cosa che
    prima si otteneva rifacendo la query per un giorno alla volta."""
    _crea_tabelle(app)
    anno = _anno_scol_corrente_oggi()
    giorno1 = date(anno, 11, 10)
    giorno2 = date(anno, 11, 12)
    db.session.add(AttivitaIst(tipo='collegio', titolo='Collegio docenti', data=giorno1,
                               ora_inizio='16:30', ora_fine='18:30'))
    db.session.add(AttivitaIst(tipo='consiglio_classe', titolo='CdC 3A LSC', data=giorno1,
                               ora_inizio='14:00', ora_fine='15:00', classe='3A LSC'))
    db.session.add(AttivitaIst(tipo='dipartimento', titolo='Dipartimento lettere', data=giorno2))
    db.session.commit()

    ctx = contesto_form_assenza(giorno1.isoformat())
    mappa = ctx['eventi_ist_per_data']

    assert len(mappa[giorno1.isoformat()]) == 2
    assert len(mappa[giorno2.isoformat()]) == 1
    titoli_giorno1 = {ev['titolo'] for ev in mappa[giorno1.isoformat()]}
    assert titoli_giorno1 == {'Collegio docenti', 'CdC 3A LSC'}


def test_eventi_ist_per_data_include_campi_usati_dal_template(app, db_session):
    """Il template legge tipo_emoji/tipo_label/titolo/ora_inizio/
    ora_fine/classe -- verifica che la mappa li porti tutti, non solo
    l'id o l'oggetto SQLAlchemy (che non sarebbe serializzabile in
    JSON per il passaggio al client)."""
    _crea_tabelle(app)
    anno = _anno_scol_corrente_oggi()
    giorno = date(anno, 11, 10)
    ev = AttivitaIst(tipo='consiglio_classe', titolo='CdC 3A LSC', data=giorno,
                      ora_inizio='14:00', ora_fine='15:00', classe='3A LSC')
    db.session.add(ev)
    db.session.commit()

    ctx = contesto_form_assenza(giorno.isoformat())
    voce = ctx['eventi_ist_per_data'][giorno.isoformat()][0]

    assert voce['titolo'] == 'CdC 3A LSC'
    assert voce['ora_inizio'] == '14:00'
    assert voce['ora_fine'] == '15:00'
    assert voce['classe'] == '3A LSC'
    assert voce['tipo_label'] == ev.tipo_label
    assert voce['tipo_emoji'] == ev.tipo_emoji


def test_eventi_ist_per_data_non_include_eventi_fuori_anno_scolastico(app, db_session):
    """La mappa è limitata all'anno scolastico corrente (stesso raggio
    già usato per gli utilizzi CCNL) -- un evento di due anni fa non
    deve gonfiare inutilmente il JSON passato al client."""
    _crea_tabelle(app)
    anno = _anno_scol_corrente_oggi()
    vecchio = date(anno - 2, 11, 10)
    db.session.add(AttivitaIst(tipo='altro', titolo='Evento vecchio', data=vecchio))
    db.session.commit()

    ctx = contesto_form_assenza(date(anno, 9, 15).isoformat())

    assert vecchio.isoformat() not in ctx['eventi_ist_per_data']


def test_eventi_ist_giorno_retrocompatibile_con_la_mappa(app, db_session):
    """eventi_ist_giorno (usato altrove/in passato per il solo giorno
    di apertura del form) deve restare coerente con la nuova mappa per
    quella stessa data, non un dato calcolato in modo indipendente che
    potrebbe disallinearsi."""
    _crea_tabelle(app)
    anno = _anno_scol_corrente_oggi()
    giorno = date(anno, 11, 10)
    db.session.add(AttivitaIst(tipo='altro', titolo='Riunione', data=giorno))
    db.session.commit()

    ctx = contesto_form_assenza(giorno.isoformat())

    assert ctx['eventi_ist_giorno'] == ctx['eventi_ist_per_data'][giorno.isoformat()]


def test_eventi_ist_giorno_vuoto_per_data_senza_eventi(app, db_session):
    _crea_tabelle(app)
    anno = _anno_scol_corrente_oggi()
    ctx = contesto_form_assenza(date(anno, 10, 1).isoformat())
    assert ctx['eventi_ist_giorno'] == []
    assert date(anno, 10, 1).isoformat() not in ctx['eventi_ist_per_data']
