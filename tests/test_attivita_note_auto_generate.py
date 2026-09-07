"""
Audit usabilità (Sessione 66): le note auto-generate per le assenze
legate ad attività fuori aula mostravano due difetti visibili ogni
giorno agli utenti:
1. parola duplicata, es. "📝 Simulazione Simulazione colloquio orale"
   (l'etichetta breve tipo_label e la descrizione, che inizia con la
   stessa parola, venivano concatenate senza controllo);
2. sintassi grezza di una lista Python esposta all'utente, es.
   "classe ['5A LSP']" invece di "classe 5A LSP" (routes/attivita.py,
   f-string con attivita.classi_list interpolato direttamente).

_tipo_e_descrizione() risolve il primo; il secondo è risolto con
', '.join(attivita.classi_list) al posto dell'interpolazione diretta.
"""
from datetime import date
from models import db
from models.attivita_fuori_aula import AttivitaFuoriAula, AttivitaClasse
from routes.attivita import _tipo_e_descrizione


def _crea_tabelle(app):
    with app.app_context():
        db.create_all()


def _attivita(tipo='simulazione', descrizione=''):
    return AttivitaFuoriAula(tipo=tipo, descrizione=descrizione,
                              data_inizio=date(2026, 5, 4), data_fine=date(2026, 5, 4))


def test_descrizione_che_inizia_come_letichetta_non_si_ripete(app, db_session):
    att = _attivita('simulazione', 'Simulazione colloquio orale')
    assert _tipo_e_descrizione(att) == 'Simulazione colloquio orale'


def test_descrizione_diversa_dalletichetta_viene_concatenata(app, db_session):
    att = _attivita('progetto', 'ERASMUS')
    assert _tipo_e_descrizione(att) == '📐 Progetto ERASMUS'


def test_descrizione_vuota_usa_solo_letichetta(app, db_session):
    att = _attivita('gita', '')
    assert _tipo_e_descrizione(att) == '✈ Gita'


def test_classi_list_non_espone_sintassi_python_nella_nota(app, db_session):
    """La formattazione delle classi nella nota deve unire i nomi con
    virgola, mai mostrare la lista Python grezza (['5A LSP'])."""
    _crea_tabelle(app)
    att = _attivita('progetto', 'Uscita didattica')
    db.session.add(att)
    db.session.flush()
    db.session.add(AttivitaClasse(id_attivita=att.id, classe='5A LSP'))
    db.session.commit()

    classi_join = ', '.join(att.classi_list) or '—'
    nota = f'Auto — {_tipo_e_descrizione(att)} [{att.id}] (classe {classi_join} fuori aula)'

    assert nota == f'Auto — 📐 Progetto Uscita didattica [{att.id}] (classe 5A LSP fuori aula)'
    assert '[' not in nota.split(f'[{att.id}]')[1]  # nessuna lista Python dopo l'id
