"""
Roberto: la pagina Sostituzioni di uno scrutinio mostrava un solo
segnale per candidato (quasi sempre "③ riunione lo stesso giorno"),
anche quando il candidato aveva ANCHE altri segnali applicabili (es.
stessa materia dell'assente) — voleva vederli tutti, non solo quello
che decideva l'ordinamento.

Causa: routes/attivita_ist.py::_score_candidato (ora
_segnali_candidato) usciva con un return non appena trovava il primo
segnale (materia > dipartimento > riunione > generico), quindi un
candidato con materia E riunione risultava etichettato solo "① mat.",
uno con solo riunione "③ riunione" — mai la combinazione. Corretto
calcolando tutti i segnali applicabili insieme, mantenendo lo stesso
punteggio di ordinamento di prima (il segnale migliore decide sempre
la posizione in lista, invariato).
"""
from datetime import date
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPresenza
from models.materia import Dipartimento, Materia, DocenteMateria
from tests.conftest import crea_docente


def _cattura(monkeypatch, modulo):
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(modulo, 'render_template', _finto_render)
    return catturato


def _materia(nome, sigla, dip):
    m = Materia(nome=nome, sigla=sigla, id_dipartimento=dip.id)
    db.session.add(m)
    db.session.flush()
    return m


def test_candidato_con_piu_segnali_li_mostra_tutti(app, db_session, monkeypatch):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    dip = Dipartimento(nome='Umanistico', sigla='UMA')
    db.session.add(dip)
    db.session.flush()
    mat = _materia('Storia', 'STO', dip)

    assente = crea_docente('Assente')
    # Candidato con DUE segnali insieme: stessa materia dell'assente E
    # un'altra riunione lo stesso giorno, PRIMA dello scrutinio.
    cand_doppio = crea_docente('DoppioSegnale')
    # Candidato con un solo segnale: solo la riunione (nessuna materia
    # in comune con l'assente).
    cand_solo_riunione = crea_docente('SoloRiunione')
    db.session.commit()

    anno = mod._anno_scolastico(date(2026, 8, 31))
    db.session.add(DocenteMateria(id_docente=assente.id, id_materia=mat.id, anno_scol=anno))
    db.session.add(DocenteMateria(id_docente=cand_doppio.id, id_materia=mat.id, anno_scol=anno))
    db.session.commit()

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio finale', classe='3A LSC',
                      data=date(2026, 8, 31), ora_inizio='10:00', ora_fine='11:00',
                      origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=assente.id, stato='assente'))
    db.session.commit()

    # Riunione precedente lo stesso giorno, per ENTRAMBI i candidati.
    riun = AttivitaIst(tipo='collegio', titolo='Collegio', data=date(2026, 8, 31),
                        ora_inizio='08:30', ora_fine='09:30', origine='manuale')
    db.session.add(riun)
    db.session.flush()
    from models.attivita_ist import AttivitaIstPartecipante
    db.session.add(AttivitaIstPartecipante(id_attivita=riun.id, id_docente=cand_doppio.id, preset=True))
    db.session.add(AttivitaIstPartecipante(id_attivita=riun.id, id_docente=cand_solo_riunione.id, preset=True))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev.id}/sostituzioni')
        assert r.status_code == 200

    candidati = catturato['kwargs']['righe'][0]['candidati']
    segnali_per_id = {d.id: segnali for d, score, segnali, riun_prec, riun_succ in candidati}

    # Stessa materia implica anche stesso dipartimento: tutti e tre i
    # segnali applicabili (1, 2, 3) sono visibili insieme, non solo il
    # migliore che decide l'ordinamento.
    assert segnali_per_id[cand_doppio.id] == {1, 2, 3}
    assert segnali_per_id[cand_solo_riunione.id] == {3}  # solo riunione

    # A parità di comodità oraria (entrambi hanno la stessa riunione
    # prima dello scrutinio), chi condivide anche la materia va prima
    # (bonus a parità di fascia oraria — vedi addendum 41).
    ids_ordinati = [d.id for d, *_ in candidati]
    assert ids_ordinati.index(cand_doppio.id) < ids_ordinati.index(cand_solo_riunione.id)


def test_candidato_senza_segnali_mostra_solo_generico(app, db_session, monkeypatch):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    assente = crea_docente('Assente2')
    cand = crea_docente('Generico')
    db.session.commit()

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio finale', classe='4A LSC',
                      data=date(2026, 8, 31), ora_inizio='10:00', ora_fine='11:00',
                      origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=assente.id, stato='assente'))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev.id}/sostituzioni')
        assert r.status_code == 200

    candidati = catturato['kwargs']['righe'][0]['candidati']
    segnali_per_id = {d.id: segnali for d, score, segnali, riun_prec, riun_succ in candidati}
    assert segnali_per_id[cand.id] == {4}


def test_segnale_materia_usa_il_campo_libero_se_manca_docentemateria(app, db_session, monkeypatch):
    """Caso reale segnalato da Roberto: la maggior parte dei docenti (in
    particolare ITP/TD_GS) non ha righe strutturate in DocenteMateria
    (popolate solo da Assegnazioni o dal box "Materie insegnate"), ma HA
    il campo libero Docente.materia compilato in anagrafica. Prima del
    fix, questi docenti non ottenevano mai il segnale ① o ② anche quando
    insegnavano davvero la stessa materia dell'assente, perché
    _segnali_candidato guardava solo DocenteMateria."""
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    dip = Dipartimento(nome='Lingue', sigla='LIN')
    db.session.add(dip)
    db.session.flush()
    _materia('Spagnolo', 'SPA', dip)  # esiste in anagrafica materie, ma nessuna DocenteMateria la collega

    # Nessuno dei due ha righe DocenteMateria/DocenteClasseConcorso —
    # solo il campo libero "materia" in anagrafica, come i docenti ITP/
    # TD_GS reali che hanno innescato la segnalazione.
    assente = crea_docente('OrdinanaTortosa', materia='Spagnolo')
    cand_stessa_materia = crea_docente('DeGennaro', materia='Spagnolo')
    cand_altra_materia = crea_docente('Fontana', materia='Inglese')
    db.session.commit()

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio finale', classe='5A LSC',
                      data=date(2026, 8, 31), ora_inizio='10:00', ora_fine='11:00',
                      origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=assente.id, stato='assente'))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev.id}/sostituzioni')
        assert r.status_code == 200

    candidati = catturato['kwargs']['righe'][0]['candidati']
    segnali_per_id = {d.id: segnali for d, score, segnali, riun_prec, riun_succ in candidati}
    assert 1 in segnali_per_id[cand_stessa_materia.id]  # stessa materia via campo libero
    assert 1 not in segnali_per_id[cand_altra_materia.id]


def test_vicinanza_oraria_batte_la_materia_in_comune(app, db_session, monkeypatch):
    """Roberto, dopo il fix precedente: la vicinanza oraria deve restare
    il criterio DOMINANTE — un candidato con un impegno subito prima
    dello scrutinio (comodissimo, già a scuola) deve venire prima di uno
    che condivide la materia con l'assente ma non ha nessun altro
    impegno quel giorno (va richiamato apposta). Materia/dipartimento
    restano un bonus fine solo a parità di fascia oraria, non un
    criterio che scavalca l'orario."""
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    dip = Dipartimento(nome='Scientifico', sigla='SCI')
    db.session.add(dip)
    db.session.flush()
    mat = _materia('Fisica', 'FIS', dip)

    assente = crea_docente('Assente3')
    # Stessa materia dell'assente, ma nessun altro impegno quel giorno —
    # va richiamato apposta.
    cand_solo_materia = crea_docente('SoloMateria')
    # Nessuna materia in comune, ma ha una riunione appena prima dello
    # scrutinio — è già a scuola, il più comodo da chiamare.
    cand_solo_orario = crea_docente('SoloOrario')
    db.session.commit()

    anno = mod._anno_scolastico(date(2026, 8, 31))
    db.session.add(DocenteMateria(id_docente=assente.id, id_materia=mat.id, anno_scol=anno))
    db.session.add(DocenteMateria(id_docente=cand_solo_materia.id, id_materia=mat.id, anno_scol=anno))
    db.session.commit()

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio finale', classe='2B LSC',
                      data=date(2026, 8, 31), ora_inizio='10:00', ora_fine='11:00',
                      origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=assente.id, stato='assente'))
    db.session.commit()

    riun = AttivitaIst(tipo='collegio', titolo='Collegio', data=date(2026, 8, 31),
                        ora_inizio='09:30', ora_fine='09:55', origine='manuale')
    db.session.add(riun)
    db.session.flush()
    from models.attivita_ist import AttivitaIstPartecipante
    db.session.add(AttivitaIstPartecipante(id_attivita=riun.id, id_docente=cand_solo_orario.id, preset=True))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev.id}/sostituzioni')
        assert r.status_code == 200

    candidati = catturato['kwargs']['righe'][0]['candidati']
    segnali_per_id = {d.id: segnali for d, score, segnali, riun_prec, riun_succ in candidati}
    assert segnali_per_id[cand_solo_materia.id] == {1, 2}  # stessa materia implica stesso dip.
    assert segnali_per_id[cand_solo_orario.id] == {3}

    ids_ordinati = [d.id for d, *_ in candidati]
    assert ids_ordinati.index(cand_solo_orario.id) < ids_ordinati.index(cand_solo_materia.id)


def test_segnale_materia_usa_anche_la_classe_di_concorso(app, db_session, monkeypatch):
    """Caso reale segnalato da Roberto (2B LSC, assente Del Curto):
    Boffi non risultava "① stessa materia" nonostante stessa classe di
    concorso e stessa materia insegnata, solo perché il campo libero
    "materia" era scritto in modo diverso ("Scienze motorie" contro
    "Discipline sportive") — il fallback sul testo libero da solo non
    bastava. La classe di concorso, quando coincide, è un segnale più
    affidabile del testo libero."""
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    from models.classe_concorso import ClasseConcorso
    cc = ClasseConcorso(codice='AS48', nome='Scienze motorie')
    db.session.add(cc)
    db.session.flush()

    assente = crea_docente('DelCurto', materia='SCIENZE MOTORIE')
    cand_stessa_cc = crea_docente('Boffi', materia='Discipline sportive')
    cand_altra_cc = crea_docente('Landi', materia='Diritto')
    assente.id_classe_concorso = cc.id
    cand_stessa_cc.id_classe_concorso = cc.id
    db.session.commit()

    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio finale', classe='2B LSC',
                      data=date(2026, 8, 31), ora_inizio='10:00', ora_fine='11:00',
                      origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=assente.id, stato='assente'))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev.id}/sostituzioni')
        assert r.status_code == 200

    candidati = catturato['kwargs']['righe'][0]['candidati']
    segnali_per_id = {d.id: segnali for d, score, segnali, riun_prec, riun_succ in candidati}
    assert 1 in segnali_per_id[cand_stessa_cc.id]
    assert 1 not in segnali_per_id[cand_altra_cc.id]
