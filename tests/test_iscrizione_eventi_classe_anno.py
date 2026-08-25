"""
Roberto: in Assegnazioni ha assegnato un docente a una classe per il
2026-2027 (anno in preparazione) e quel docente è comparso come
partecipante previsto nello scrutinio del 31/08/2026 — che appartiene
ancora al 2025-2026. Causa: iscrivi_docente_a_eventi_classe()
(routes/attivita_ist.py, chiamata da routes/assegnazioni.py quando si
assegna una classe) cercava eventi futuri (data >= oggi) con
l'etichetta classe corrispondente, senza controllare che l'evento
appartenesse allo STESSO anno scolastico dell'assegnazione — l'
etichetta (es. "3A LLI") è identica sia per la classe uscente sia per
quella entrante, e uno scrutinio di fine agosto è "futuro" rispetto a
una sessione di lavoro di metà mese pur appartenendo all'anno vecchio.
"""
from datetime import date
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
from tests.conftest import crea_docente


def test_non_iscrive_a_evento_di_un_altro_anno_scolastico(app, db_session):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)

    d = crea_docente('Pedeferri')
    db.session.commit()

    # Scrutinio del 31/08/2026 -> anno scolastico 2025-2026.
    ev_vecchio_anno = AttivitaIst(tipo='scrutinio', titolo='Scrutinio', classe='1A CAT',
                                   data=date(2026, 8, 31), origine='manuale')
    db.session.add(ev_vecchio_anno)
    db.session.commit()

    # L'assegnazione è per il 2026-2027 (in preparazione): l'evento del
    # 31/08/2026 appartiene ancora al 2025-2026, non deve iscriverlo.
    n = mod.iscrivi_docente_a_eventi_classe(d.id, ['1A CAT'], anno_scol='2026-2027')

    assert n == 0
    assert AttivitaIstPartecipante.query.filter_by(
        id_attivita=ev_vecchio_anno.id, id_docente=d.id).first() is None


def test_iscrive_a_evento_dello_stesso_anno_scolastico(app, db_session):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)

    d = crea_docente('Zampetti')
    db.session.commit()

    # Consiglio di classe di ottobre 2026 -> anno scolastico 2026-2027.
    ev_stesso_anno = AttivitaIst(tipo='consiglio_classe', titolo='CdC', classe='4A RIM',
                                  data=date(2026, 10, 15), origine='manuale')
    db.session.add(ev_stesso_anno)
    db.session.commit()

    n = mod.iscrivi_docente_a_eventi_classe(d.id, ['4A RIM'], anno_scol='2026-2027')

    assert n == 1
    assert AttivitaIstPartecipante.query.filter_by(
        id_attivita=ev_stesso_anno.id, id_docente=d.id).first() is not None


def test_senza_anno_scol_si_comporta_come_prima_nessun_filtro(app, db_session):
    """Compatibilità: se il chiamante non passa anno_scol, il
    comportamento resta quello di sempre (nessun filtro per anno) —
    nessuna chiamata esistente nel codice lo fa più senza passarlo, ma
    la funzione non deve rompersi se qualcuno la richiama così."""
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)

    d = crea_docente('SenzaFiltro')
    db.session.commit()

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio', classe='2A AFM',
                      data=date(2026, 8, 31), origine='manuale')
    db.session.add(ev)
    db.session.commit()

    n = mod.iscrivi_docente_a_eventi_classe(d.id, ['2A AFM'])

    assert n == 1
