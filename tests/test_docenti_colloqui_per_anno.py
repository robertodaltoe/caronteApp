"""
Roberto: i giorni di colloqui fissi (e le relative eccezioni) erano
campi unici sul Docente, non potevano differire tra un anno scolastico
e l'altro — stesso problema già risolto per ore_max_anno/tipo_contratto/
Materie insegnate. Aggiunta DocenteColloquiAnno (una riga per docente
per anno) con fallback all'ultimo anno con un override esplicito, e un
selettore anno nella scheda docente (stesso pattern di "Materie
insegnate") per editare l'uno o l'altro senza sovrascriverli a vicenda.
"""
from datetime import date
from models import db
from models.colloqui_eccezione import ColloquiEccezione
from tests.conftest import crea_docente


def _cattura(monkeypatch, modulo):
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(modulo, 'render_template', _finto_render)
    return catturato


def _post_modifica(client, d, anno_colloqui, colloqui_giorno, colloqui_ora_inizio='',
                    colloqui_ora_fine='', extra=None):
    from concorrenza import versione_str
    data = {
        'cognome': d.cognome, 'nome': d.nome,
        'ore_contratto': str(d.ore_contratto or 18),
        'tipo_contratto': d.tipo_contratto or 'TI',
        'ruolo': d.ruolo or 'titolare',
        'tipo_servizio': 'full',
        'anno_colloqui': anno_colloqui,
        'colloqui_giorno': str(colloqui_giorno) if colloqui_giorno is not None else '',
        'colloqui_ora_inizio': str(colloqui_ora_inizio),
        'colloqui_ora_fine': str(colloqui_ora_fine),
        'versione': versione_str(d.modificato_il),
    }
    if extra:
        data.update(extra)
    return client.post(f'/docenti/{d.id}/modifica', data=data)


def test_colloqui_di_due_anni_non_si_sovrascrivono_a_vicenda(app, db_session):
    import routes.docenti as mod
    if 'docenti' not in app.blueprints:
        app.register_blueprint(mod.docenti_bp)

    d = crea_docente('Colloqui1')
    db.session.commit()

    with app.test_client() as c:
        r = _post_modifica(c, d, '2025-2026', colloqui_giorno=1,
                            colloqui_ora_inizio=2, colloqui_ora_fine=3)
        assert r.status_code == 302
        db.session.refresh(d)
        r = _post_modifica(c, d, '2026-2027', colloqui_giorno=4,
                            colloqui_ora_inizio=5, colloqui_ora_fine=6)
        assert r.status_code == 302

    eff_2526 = d.colloqui_effettivi_per_anno('2025-2026')
    eff_2627 = d.colloqui_effettivi_per_anno('2026-2027')
    assert eff_2526 == {'giorno': 1, 'ora_inizio': 2, 'ora_fine': 3, 'esplicito': True}
    assert eff_2627 == {'giorno': 4, 'ora_inizio': 5, 'ora_fine': 6, 'esplicito': True}


def test_anno_senza_override_eredita_lultimo_esplicito_precedente(app, db_session):
    """"Ultimo noto" (confermato da Roberto): un anno senza override
    esplicito prende l'ultimo valore impostato apposta, non il campo
    base originario — così una modifica fatta per il 2025-2026 si
    riflette anche sul 2026-2027 finché non lo si imposta a sua volta
    esplicitamente."""
    import routes.docenti as mod
    if 'docenti' not in app.blueprints:
        app.register_blueprint(mod.docenti_bp)

    d = crea_docente('Colloqui2')
    d.colloqui_giorno = 0  # valore-seme pre-esistente, non deve vincere sul più recente
    db.session.commit()

    with app.test_client() as c:
        r = _post_modifica(c, d, '2025-2026', colloqui_giorno=2,
                            colloqui_ora_inizio=1, colloqui_ora_fine=2)
        assert r.status_code == 302

    eff_2627 = d.colloqui_effettivi_per_anno('2026-2027')
    assert eff_2627 == {'giorno': 2, 'ora_inizio': 1, 'ora_fine': 2, 'esplicito': False}


def test_anno_senza_nessun_override_ricade_sul_campo_base(app, db_session):
    d = crea_docente('Colloqui3')
    d.colloqui_giorno = 3
    d.colloqui_ora_inizio = 1
    d.colloqui_ora_fine = 1
    db.session.commit()

    eff = d.colloqui_effettivi_per_anno('2030-2031')
    assert eff == {'giorno': 3, 'ora_inizio': 1, 'ora_fine': 1, 'esplicito': False}


def test_scheda_docente_mostra_colloqui_dellanno_selezionato(app, db_session, monkeypatch):
    import routes.docenti as mod
    if 'docenti' not in app.blueprints:
        app.register_blueprint(mod.docenti_bp)
    catturato = _cattura(monkeypatch, mod)

    d = crea_docente('Colloqui4')
    db.session.commit()

    with app.test_client() as c:
        _post_modifica(c, d, '2025-2026', colloqui_giorno=1, colloqui_ora_inizio=1, colloqui_ora_fine=2)
        db.session.refresh(d)
        r = c.get(f'/docenti/{d.id}/modifica?anno_colloqui=2025-2026')
        assert r.status_code == 200
    assert catturato['kwargs']['colloqui_eff'] == {'giorno': 1, 'ora_inizio': 1, 'ora_fine': 2, 'esplicito': True}
    assert catturato['kwargs']['anno_sel_colloqui'] == '2025-2026'
    assert '2025-2026' in catturato['kwargs']['anni_colloqui']


def test_salvataggio_colloqui_non_cancella_eccezioni_di_un_altro_anno(app, db_session):
    """Roberto: le eccezioni mostrate/modificabili in scheda sono solo
    quelle dell'anno selezionato — il salvataggio NON deve però
    cancellare quelle di anni diversi non presenti in quel momento nel
    form (bug potenziale di data-loss individuato durante
    l'implementazione, non segnalato da Roberto ma corretto qui)."""
    import routes.docenti as mod
    if 'docenti' not in app.blueprints:
        app.register_blueprint(mod.docenti_bp)

    d = crea_docente('Colloqui5')
    db.session.commit()
    ecc_2526 = ColloquiEccezione(id_docente=d.id, data=date(2025, 10, 1), note='2025-2026')
    ecc_2627 = ColloquiEccezione(id_docente=d.id, data=date(2026, 10, 1), note='2026-2027 vecchia')
    db.session.add_all([ecc_2526, ecc_2627])
    db.session.commit()

    with app.test_client() as c:
        # Salva la scheda per il 2026-2027 SENZA riproporre l'eccezione
        # di quell'anno (form vuoto per quel campo) — deve sparire solo
        # quella, non quella del 2025-2026.
        r = _post_modifica(c, d, '2026-2027', colloqui_giorno=1,
                            colloqui_ora_inizio=1, colloqui_ora_fine=1)
        assert r.status_code == 302

    rimaste = ColloquiEccezione.query.filter_by(id_docente=d.id).all()
    assert len(rimaste) == 1
    assert rimaste[0].note == '2025-2026'


def _ids_nei_gruppi(resp):
    gruppi = resp.get_json()['gruppi']
    return {doc['id'] for g in gruppi for doc in g['docenti']}


def test_suggerimento_supplenza_usa_colloqui_dellanno_della_data(app, db_session):
    """routes/supplenze.py (API /api/suggerimenti) leggeva sempre
    Docente.colloqui_giorno "così com'è", ignorando che potesse
    riferirsi a un anno diverso da quello della data del suggerimento."""
    import routes.supplenze as mod
    if 'supplenze' not in app.blueprints:
        app.register_blueprint(mod.supplenze_bp)

    d = crea_docente('Colloqui6')
    db.session.commit()
    from models.docente import DocenteColloquiAnno
    from models.orario_docente import OrarioDocente
    # Una lezione qualunque nel primo pomeriggio, sia lunedì che martedì,
    # solo per renderlo un candidato valido quel giorno (altrimenti
    # "nessuna ora nel giorno" lo esclude a prescindere dai colloqui).
    db.session.add(OrarioDocente(id_docente=d.id, giorno=0, ora=6, classe='1A LSC'))
    db.session.add(OrarioDocente(id_docente=d.id, giorno=1, ora=6, classe='1A LSC'))
    # Lunedì 1ª-2ª ora nel 2025-2026; nel 2026-2027 i colloqui sono
    # martedì ma alla 4ª-5ª ora (giorno E ora diversi), cosi' la 1ª ora
    # del martedì resta libera SOLO se la route usa davvero la
    # configurazione del 2026-2027 e non quella (sbagliata) del
    # 2025-2026.
    db.session.add(DocenteColloquiAnno(id_docente=d.id, anno_scol='2025-2026',
                                        giorno=0, ora_inizio=1, ora_fine=2))
    db.session.add(DocenteColloquiAnno(id_docente=d.id, anno_scol='2026-2027',
                                        giorno=1, ora_inizio=4, ora_fine=5))
    db.session.commit()

    # 6/10/2025 è un lunedì (2025-2026): il colloquio del 2025-2026
    # copre la 1ª ora, quindi il docente deve risultare indisponibile
    # (assente da tutti i gruppi di candidati).
    with app.test_client() as c:
        r = c.get('/api/suggerimenti?data=2025-10-06&ora=1')
        assert r.status_code == 200
    assert d.id not in _ids_nei_gruppi(r)

    # 6/10/2026 è un martedì (2026-2027): il colloquio di quell'anno è
    # alla 4ª-5ª ora, non alla 1ª — se la route avesse ancora usato la
    # configurazione del 2025-2026 (lunedì 1ª-2ª, campo base "congelato")
    # lo avrebbe segnato indisponibile per errore anche qui.
    with app.test_client() as c:
        r = c.get('/api/suggerimenti?data=2026-10-06&ora=1')
        assert r.status_code == 200
    assert d.id in _ids_nei_gruppi(r)


def test_eccezione_con_periodo_copre_tutti_i_giorni_non_solo_il_primo(app, db_session):
    """Bug trovato durante l'implementazione (non segnalato da Roberto):
    il filtro delle eccezioni in routes/supplenze.py confrontava solo
    ColloquiEccezione.data == data_sel, ignorando data_fine — un
    periodo di più giorni valeva di fatto solo per il primo."""
    import routes.supplenze as mod
    if 'supplenze' not in app.blueprints:
        app.register_blueprint(mod.supplenze_bp)

    d = crea_docente('Colloqui7')
    db.session.commit()
    from models.docente import DocenteColloquiAnno
    from models.orario_docente import OrarioDocente
    db.session.add(OrarioDocente(id_docente=d.id, giorno=0, ora=6, classe='1A LSC'))
    db.session.add(DocenteColloquiAnno(id_docente=d.id, anno_scol='2025-2026',
                                        giorno=0, ora_inizio=1, ora_fine=2))
    db.session.add(ColloquiEccezione(id_docente=d.id, data=date(2025, 10, 6),
                                      data_fine=date(2025, 10, 13)))  # copre due lunedì
    db.session.commit()

    # 13/10/2025 è il SECONDO giorno del periodo (non il primo): prima
    # del fix, non veniva riconosciuto come coperto dall'eccezione e il
    # docente sarebbe risultato indisponibile per errore.
    with app.test_client() as c:
        r = c.get('/api/suggerimenti?data=2025-10-13&ora=1')
        assert r.status_code == 200
    assert d.id in _ids_nei_gruppi(r)
