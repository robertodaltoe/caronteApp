from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from models.docente import Docente
from models.supplenza import Supplenza
from models.assenza import Assenza
from models.movimento_banca_ore import MovimentoBancaOre
from models.indisponibilita import Indisponibilita
from models.indisponibilita_ricorrente import IndisponibilitaRicorrente
from models.orario_docente import OrarioDocente
from models.variazione_orario import VariazioneOrario
from models.scambio_ore import ScambioOre
from models.sync_orario import AliasDocente, LogImportazione
from models.attivita_fuori_aula import AttivitaFuoriAula, AttivitaClasse
from models.migrazione_slot import MigrazioneSlot
from models.scambio_orario import ScambioOrario, ScambioSlot
