"""
Roberto: "in registra assenza, nel menu a tendina di selezione docenti,
mi compaiono ancora i docenti non più attivi (in teoria) cioè quelli
che hanno il contratto scaduto".

Causa in modules/assenze_registrazione.py::contesto_form_assenza(): la
tendina si popolava con Docente.query.filter_by(attivo=True) — il flag
`attivo` non si azzera mai da solo quando arriva anno_scol_uscita o
scade un contratto a termine (si aggiorna solo a mano, vedi CLAUDE.md),
quindi continuava a includere chi era ormai fuori servizio.

Fix: applicato lo stesso controllo puntuale sulla data già usato per i
partecipanti agli eventi istituzionali (_non_in_servizio_per_data).
Anche routes/assenze.py::modifica() calcolava una SECONDA lista docenti
separata (stessa query naive), che sovrascriveva quella già corretta
restituita da contesto_form_assenza() — corretto anche quello, riusando
ctx['docenti'].
"""
from datetime import date
from models import db
from models.assenza import Assenza
from tests.conftest import crea_docente


def _anno_scolastico(d):
    return f'{d.year}-{d.year+1}' if d.month >= 9 else f'{d.year-1}-{d.year}'


def test_docente_con_anno_uscita_gia_passato_non_compare_nel_form_nuova_assenza(app, db_session):
    oggi = date.today()
    anno_corrente = _anno_scolastico(oggi)

    attivo = crea_docente('Rossi')
    uscito = crea_docente('Bianchi')
    uscito.anno_scol_uscita = anno_corrente
    uscito.motivo_uscita = 'pensionamento'
    db.session.commit()

    from modules.assenze_registrazione import contesto_form_assenza
    ctx = contesto_form_assenza(oggi.isoformat())

    ids = {d.id for d in ctx['docenti']}
    assert attivo.id in ids
    assert uscito.id not in ids


def test_contratto_scaduto_ad_agosto_non_compare_nel_form(app, db_session):
    anno_corrente = '2025-2026'
    supplente_breve = crea_docente('Verdi', tipo_contratto='supplente_breve')

    from modules.assenze_registrazione import contesto_form_assenza
    ctx = contesto_form_assenza(date(2026, 8, 20).isoformat())

    assert supplente_breve.id not in {d.id for d in ctx['docenti']}


def test_modifica_assenza_non_perde_dalla_tendina_il_docente_ormai_uscito(app, db_session):
    """Modificare un'assenza storica di un docente uscito nel frattempo
    non deve rompersi: il suo nome deve restare selezionabile (era già
    nella tendina prima di questo fix, non deve sparire ora)."""
    oggi = date.today()
    anno_corrente = _anno_scolastico(oggi)

    uscito = crea_docente('Neri')
    a = Assenza(id_docente=uscito.id, data=oggi, motivo='malattia')
    db.session.add(a)
    db.session.commit()

    # Uscito DOPO aver registrato l'assenza — scenario reale: si modifica
    # un'assenza storica di qualcuno che nel frattempo ha lasciato la scuola.
    uscito.anno_scol_uscita = anno_corrente
    uscito.motivo_uscita = 'trasferimento'
    db.session.commit()

    from modules.assenze_registrazione import contesto_form_assenza
    ctx = contesto_form_assenza(oggi.isoformat(), escludi_assenza_id=a.id)

    assert uscito.id in {d.id for d in ctx['docenti']}
