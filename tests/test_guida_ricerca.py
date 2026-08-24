"""
Roberto: nella pagina Guida vuole un campo di ricerca per parole
chiave che restituisca i risultati più coerenti, non solo un elenco
statico di sezioni. modules/guida_content.py::cerca() cerca su tutti i
campi di ogni sezione (titolo, riassunto, passi, FAQ, attenzione) con
un punteggio pesato per campo, così un match nel titolo o in una
domanda FAQ conta più di uno perso nel corpo di un passo.
"""
from modules.guida_content import cerca, SEZIONI


def test_query_vuota_non_restituisce_risultati():
    assert cerca('') == []
    assert cerca('   ') == []


def test_trova_sezione_per_parola_nel_titolo():
    risultati = cerca('docenti')
    slugs = [r['sezione']['slug'] for r in risultati]
    assert 'docenti' in slugs


def test_match_nel_titolo_pesa_piu_di_un_match_nel_corpo():
    """'docenti' compare nel TITOLO della sezione 'docenti' e solo nel
    corpo di molte altre sezioni (che parlano anche loro di docenti) —
    deve comunque risultare la più rilevante."""
    risultati = cerca('docenti')
    assert risultati[0]['sezione']['slug'] == 'docenti'


def test_risultati_ordinati_per_punteggio_decrescente():
    risultati = cerca('anno scolastico')
    punteggi = [r['punteggio'] for r in risultati]
    assert punteggi == sorted(punteggi, reverse=True)


def test_parola_inesistente_non_trova_nulla():
    assert cerca('xyzqwertynonesiste123') == []


def test_snippet_presente_e_centrato_sulla_parola_cercata():
    risultati = cerca('protocollo')
    assert risultati
    assert any('protocollo' in (r['snippet'] or '').lower() for r in risultati)


def test_route_guida_cerca_restituisce_risultati_ordinati(app, monkeypatch):
    import routes.guida as mod
    if 'guida' not in app.blueprints:
        app.register_blueprint(mod.guida_bp)
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r = c.get('/guida/cerca?q=docenti')
        assert r.status_code == 200
    assert catturato['kwargs']['query'] == 'docenti'
    assert catturato['kwargs']['risultati'][0]['sezione']['slug'] == 'docenti'


def test_route_guida_cerca_senza_query_non_mostra_risultati(app, monkeypatch):
    import routes.guida as mod
    if 'guida' not in app.blueprints:
        app.register_blueprint(mod.guida_bp)
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r = c.get('/guida/cerca')
        assert r.status_code == 200
    assert catturato['kwargs']['risultati'] is None
