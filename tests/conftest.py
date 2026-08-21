"""
Fixture condivise per i test. Crea un'app Flask minima con database
SQLite in-memory (mai il database.db reale), cosi' i test sono
completamente isolati e ripetibili senza rischio per i dati di produzione.
"""
import sys
import os
import pytest
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask
from models import db


@pytest.fixture
def app():
    """App Flask di test con DB SQLite in-memory."""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-key'
    app.config['TESTING'] = True

    db.init_app(app)

    with app.app_context():
        # Import di tutti i modelli necessari ai test, cosi' create_all()
        # crea le tabelle corrispondenti nel DB in-memory.
        from models.classe_concorso import ClasseConcorso, CattedraOrganico  # noqa
        from models.docente import Docente, CoppiaDocenteItp  # noqa
        from models.assenza import Assenza  # noqa
        from models.orario_docente import OrarioDocente  # noqa
        from models.supplenza import Supplenza  # noqa
        from models.movimento_banca_ore import MovimentoBancaOre  # noqa
        from models.indisponibilita import Indisponibilita  # noqa
        from models.materia import Dipartimento, Materia, DocenteMateria  # noqa
        from models.recupero import (RecuperoDocente, RecuperoGruppo,  # noqa
                                      RecuperoLezione, RecuperoAlunno,
                                      RecuperoVincolo, RecuperoImport,
                                      RecuperoPeriodo)
        from models.rientro import (RientroMateriaClasse, RientroCandidato,  # noqa
                                     RientroColloquio, RuoloIstituzionale)
        from models.aula import Aula  # noqa
        from models.utente import Utente  # noqa
        from models.log_accesso import LogAccesso  # noqa
        from models.attivita_ist import (AttivitaIst, AttivitaIstPartecipante,  # noqa
                                          AttivitaIstPresenza)
        from models.formazione import CorsoFormazione  # noqa
        from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse  # noqa
        from models.piano_studi import PianoStudi  # noqa
        from models.config_app import ConfigApp  # noqa
        from models.piano_attivita_personale import (PianoAttivitaPersonale,  # noqa
                                                       PianoAttivitaPersonaleVoce)
        from models.generatore_cdc import VincoloOrarioClasse, VincoloGeneratoreCdc  # noqa
        from models.sospensione import SospensioneDidattica  # noqa
        from models.incarico import CategoriaIncarico, TipoIncarico, IncaricaDocente  # noqa
        from models.sostituzione_scrutinio import SostituzioneScrutinio  # noqa
        db.create_all()
        yield app
        db.session.remove()


@pytest.fixture
def db_session(app):
    """Sessione DB pulita, usata dai test per leggere/scrivere dati di fixture."""
    with app.app_context():
        yield db.session


def crea_docente(cognome, nome='Mario', tipo_contratto='TI', attivo=True,
                  materia=None, ruolo='titolare'):
    """Helper: crea e salva un Docente minimo per i test."""
    from models.docente import Docente
    d = Docente(cognome=cognome, nome=nome, tipo_contratto=tipo_contratto,
                attivo=attivo, materia=materia, ruolo=ruolo)
    db.session.add(d)
    db.session.commit()
    return d


def crea_periodo(codice, anno_scol='2025-2026', data_inizio=date(2026, 8, 24),
                  data_fine=date(2026, 8, 28), ora_inizio='08:00', ora_fine='16:00'):
    """Helper: crea e salva un RecuperoPeriodo (condiviso tra moduli)."""
    from models.recupero import RecuperoPeriodo
    p = RecuperoPeriodo(anno_scol=anno_scol, codice=codice,
                         label=codice, data_inizio=data_inizio, data_fine=data_fine,
                         ora_inizio=ora_inizio, ora_fine=ora_fine)
    db.session.add(p)
    db.session.commit()
    return p



@pytest.fixture
def app_con_blueprint(app):
    """
    Come 'app', ma con recupero_bp registrato — serve per testare route
    Flask vere e proprie (es. genera_bozza) che usano request.form,
    flash, redirect/url_for verso altri endpoint dello stesso blueprint.
    """
    from routes.recupero import recupero_bp
    if 'recupero' not in app.blueprints:
        app.register_blueprint(recupero_bp)
    return app
