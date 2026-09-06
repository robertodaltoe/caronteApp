"""
Roberto: "dobbiamo sistemare risincronizza partecipanti. non c'è un
tasto di selezione rapida (tutti - nessuno), non è ammissibile che se
io tolgo tutti o seleziono i partecipanti dall'evento il sistema mi
chieda di inserire nuovamente tutti."

Due fix distinti:

1. UI: aggiunti pulsanti "Tutti"/"Nessuno" per ciascun gruppo (da
   aggiungere / da rimuovere) in templates/attivita_ist/risincronizza.html
   — verificato qui solo a livello di sorgente del template (nessun
   render Jinja completo disponibile nei fixture di test).

2. Logica: nuovo campo AttivitaIst.partecipanti_manuali — impostato in
   form() quando la checklist partecipanti viene inviata esplicitamente
   con una selezione diversa da quella che _preset_partecipanti()
   calcolerebbe in quel momento (l'utente ha deliberatamente scelto un
   elenco diverso, es. "Nessuno" poi una selezione ridotta a mano).
   Una volta True, _diff_risincronizzazione() non propone più "da
   aggiungere" per quell'evento — altrimenti la risincronizzazione
   proponeva sempre di ripristinare l'elenco automatico completo,
   vanificando la scelta manuale appena fatta. "da rimuovibili" resta
   invece invariato: è un controllo di sicurezza (chi non è più in
   servizio), non un'opinione sul numero di partecipanti.
"""
import re
from datetime import date, timedelta
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
from tests.conftest import crea_docente

FUTURO = date.today() + timedelta(days=30)


def _registra_blueprint(app):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)


def test_template_ha_i_pulsanti_tutti_nessuno_per_ciascun_gruppo():
    with open('templates/attivita_ist/risincronizza.html', encoding='utf-8') as f:
        html = f.read()

    assert re.search(r"selezionaGruppo\('agg',\s*true\)", html)
    assert re.search(r"selezionaGruppo\('agg',\s*false\)", html)
    assert re.search(r"selezionaGruppo\('rim',\s*true\)", html)
    assert re.search(r"selezionaGruppo\('rim',\s*false\)", html)


def test_form_marca_partecipanti_manuali_se_selezione_diversa_dal_preset(app, db_session):
    """Tipo 'riunione_extra': preset sempre vuoto (solo manuale) — quindi
    QUALUNQUE selezione non vuota differisce dal preset."""
    _registra_blueprint(app)
    d1 = crea_docente('Rossi')
    ev = AttivitaIst(tipo='riunione_extra', titolo='Riunione referenti', data=FUTURO, origine='manuale')
    db.session.add(ev)
    db.session.commit()

    with app.test_client() as c:
        c.post(f'/attivita-ist/{ev.id}/modifica', data={
            'tipo': 'riunione_extra', 'titolo': 'Riunione referenti', 'data': FUTURO.isoformat(),
            'partecipanti_form_presente': '1',
            'docenti_ids': [str(d1.id)],
        })

    db.session.refresh(ev)
    assert ev.partecipanti_manuali is True


def test_form_non_marca_manuali_se_selezione_coincide_col_preset(app, db_session):
    """Tipo 'collegio': preset è sempre 'tutti i docenti attivi' — se
    l'utente seleziona esattamente tutti, non ha cambiato nulla."""
    _registra_blueprint(app)
    d1 = crea_docente('Rossi')
    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=FUTURO, origine='manuale')
    db.session.add(ev)
    db.session.commit()

    with app.test_client() as c:
        c.post(f'/attivita-ist/{ev.id}/modifica', data={
            'tipo': 'collegio', 'titolo': 'Collegio', 'data': FUTURO.isoformat(),
            'partecipanti_form_presente': '1',
            'docenti_ids': [str(d1.id)],
        })

    db.session.refresh(ev)
    assert ev.partecipanti_manuali is False


def test_diff_non_propone_aggiunte_se_partecipanti_manuali(app, db_session):
    _registra_blueprint(app)
    d1 = crea_docente('Rossi')
    d2 = crea_docente('Bianchi')
    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=FUTURO, origine='manuale',
                      partecipanti_manuali=True)
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d1.id, preset=True))
    db.session.commit()

    from routes.attivita_ist import _diff_risincronizzazione
    da_aggiungere, da_rimuovibili, non_rimovibili = _diff_risincronizzazione(ev)

    # d2 (attivo, tipo 'collegio' => nel preset) NON viene proposto,
    # nonostante manchi dall'elenco: l'evento è gestito a mano.
    assert da_aggiungere == []


def test_diff_continua_a_proporre_rimozioni_anche_se_partecipanti_manuali(app, db_session):
    _registra_blueprint(app)
    uscito = crea_docente('Verdi', attivo=False)
    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=FUTURO, origine='manuale',
                      partecipanti_manuali=True)
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=uscito.id, preset=True))
    db.session.commit()

    from routes.attivita_ist import _diff_risincronizzazione
    da_aggiungere, da_rimuovibili, non_rimovibili = _diff_risincronizzazione(ev)

    assert da_aggiungere == []
    assert [d.id for d in da_rimuovibili] == [uscito.id]
