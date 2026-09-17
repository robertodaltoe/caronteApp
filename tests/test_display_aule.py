"""
Roberto: nel display non compaiono le aule in cui il docente sostituto
si deve recare.

Causa reale: routes/display.py::display() cercava l'aula con un lookup
esatto `aule_map.get(s.classe)`, ma `Aula.classe` è sempre salvata con
lo spazio ("1A CAT") mentre `Supplenza.classe` (copiata dall'orario
importato) è spesso salvata SENZA lo spazio ("1ACAT") — stesso
disallineamento già trovato e risolto in modules/prospetto_supplenze.py
(vedi _norm_compatto lì). Il lookup falliva in silenzio: nessun errore,
solo l'aula che non compariva.

In più aule_map non filtrava per anno scolastico (`Aula.query.all()`
prendeva righe di qualunque anno), diversamente da come routes/aule.py
fa sempre `.filter_by(anno_scol=...)`.

Copre:
1. _norm_classe() — normalizzazione (spazi via, maiuscolo).
2. display(): l'aula compare anche quando Supplenza.classe è in
   formato compatto e Aula.classe ha lo spazio.
3. display(): funziona anche nel caso "già allineato" (nessuna
   regressione per le classi che già coincidevano).
4. display(): un'aula di un anno scolastico diverso non viene usata.
"""
import os
from datetime import date

from models import db
from models.aula import Aula
from models.supplenza import Supplenza
from routes.display import _norm_classe
from tests.conftest import crea_docente

LUNEDI = date(2026, 9, 21)


def _crea_tabelle(app):
    with app.app_context():
        from models.aula import Aula  # noqa
        from models.aula_override import AulaOverride  # noqa
        from models.migrazione_slot import MigrazioneSlot  # noqa
        from models.attivita_fuori_aula import AttivitaFuoriAula, AttivitaClasse  # noqa
        db.create_all()


def _registra_blueprint(app):
    from routes.display import display_bp
    if 'display' not in app.blueprints:
        app.register_blueprint(display_bp)
    # La fixture 'app' e' un Flask() nudo senza template_folder verso
    # la vera cartella templates/ del progetto -- serve puntarcelo
    # esplicitamente per poter renderizzare display.html nel test.
    app.template_folder = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'templates'))


# ── _norm_classe() ─────────────────────────────────────────────────

def test_norm_classe_toglie_spazi_e_maiuscolizza():
    assert _norm_classe('1A CAT') == '1ACAT'
    assert _norm_classe('1acat') == '1ACAT'
    assert _norm_classe('1ACAT') == '1ACAT'
    assert _norm_classe('  3A   LSU ') == '3ALSU'


# ── display(): match compatto ───────────────────────────────────────

def test_display_mostra_aula_anche_con_classe_compatta(app, db_session):
    _crea_tabelle(app)
    _registra_blueprint(app)
    assente = crea_docente('Rossi')
    sostituto = crea_docente('Verdi')

    db.session.add(Aula(anno_scol='2026-2027', classe='1A CAT', aula='12', sede='Sede Centrale - Piano Terra'))
    db.session.add(Supplenza(data=LUNEDI, ora=3, classe='1ACAT',  # compatto, come lo salva l'import orario
                              id_assente=assente.id, id_sostituto=sostituto.id,
                              tipo='recupero', stato='assegnata'))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/display?data={LUNEDI.isoformat()}')
        assert r.status_code == 200
        html = r.get_data(as_text=True)

    assert 'Aula 12' in html
    assert 'Sede Centrale' in html


def test_display_mostra_aula_quando_gia_allineata(app, db_session):
    """Nessuna regressione per le classi già salvate con lo spazio."""
    _crea_tabelle(app)
    _registra_blueprint(app)
    assente = crea_docente('Rossi')
    sostituto = crea_docente('Verdi')

    db.session.add(Aula(anno_scol='2026-2027', classe='3A LSU', aula='7', sede='Sede Staccata'))
    db.session.add(Supplenza(data=LUNEDI, ora=2, classe='3A LSU',
                              id_assente=assente.id, id_sostituto=sostituto.id,
                              tipo='recupero', stato='assegnata'))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/display?data={LUNEDI.isoformat()}')
        html = r.get_data(as_text=True)

    assert 'Aula 7' in html


def test_display_ignora_aula_di_un_altro_anno_scolastico(app, db_session):
    _crea_tabelle(app)
    _registra_blueprint(app)
    assente = crea_docente('Rossi')
    sostituto = crea_docente('Verdi')

    # Solo un'aula per un anno DIVERSO da quello corrente (2026-2027,
    # calcolato dal calendario per l'oggi reale di questa sessione).
    db.session.add(Aula(anno_scol='2025-2026', classe='1ACAT', aula='99', sede='Sede Staccata'))
    db.session.add(Supplenza(data=LUNEDI, ora=3, classe='1ACAT',
                              id_assente=assente.id, id_sostituto=sostituto.id,
                              tipo='recupero', stato='assegnata'))
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/display?data={LUNEDI.isoformat()}')
        html = r.get_data(as_text=True)

    assert 'Aula 99' not in html
