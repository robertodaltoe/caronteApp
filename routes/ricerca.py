"""
Ricerca globale cross-sezione: una singola casella di ricerca (in nav,
sempre visibile) che cerca in parallelo tra Docenti, Supplenze, Assenze,
Movimenti banca ore e Sospensioni didattiche, invece di dover sapere in
quale sezione dell'app si trova un dato.

Ricerca semplice per sottostringa (case-insensitive, LIKE %q%), niente
full-text/indicizzazione: il volume di dati della scuola è piccolo
abbastanza da non giustificare l'infrastruttura in più.
"""
from flask import Blueprint, render_template, request
from sqlalchemy import or_

from routes.auth import login_required
from models.docente import Docente
from models.supplenza import Supplenza
from models.assenza import Assenza, MOTIVI_RISERVATI, RUOLI_MOTIVO_SPECIFICO
from models.movimento_banca_ore import MovimentoBancaOre
from models.sospensione import SospensioneDidattica

ricerca_bp = Blueprint('ricerca', __name__)

LIMITE_RISULTATI = 25


@ricerca_bp.route('/ricerca')
@login_required()
def index():
    from flask import session
    ruolo = session.get('ruolo')
    q = (request.args.get('q') or '').strip()
    risultati = {
        'docenti': [], 'supplenze': [], 'assenze': [],
        'movimenti': [], 'sospensioni': [],
    }
    n_totale = 0

    if len(q) >= 2:
        like = f'%{q}%'

        risultati['docenti'] = Docente.query.filter(or_(
            Docente.cognome.ilike(like),
            Docente.nome.ilike(like),
            Docente.nome_display.ilike(like),
            Docente.materia.ilike(like),
            Docente.email.ilike(like),
            Docente.note.ilike(like),
        )).order_by(Docente.cognome).limit(LIMITE_RISULTATI).all()

        risultati['supplenze'] = Supplenza.query.join(
            Docente, Supplenza.id_assente == Docente.id, isouter=True
        ).filter(or_(
            Supplenza.classe.ilike(like),
            Supplenza.note_display.ilike(like),
            Supplenza.note.ilike(like),
            Docente.cognome.ilike(like),
            Docente.nome.ilike(like),
        )).order_by(Supplenza.data.desc()).limit(LIMITE_RISULTATI).all()

        # Chi non ha titolo a vedere il motivo specifico (vedi
        # models/assenza.py::RUOLI_MOTIVO_SPECIFICO) non deve poterlo
        # nemmeno usare come chiave di ricerca: digitare "lutto" e
        # trovare un risultato rivelerebbe comunque il motivo riservato,
        # anche se poi l'etichetta mostrata resta mascherata.
        filtri_assenze = [Assenza.note_interne.ilike(like),
                          Docente.cognome.ilike(like), Docente.nome.ilike(like)]
        if ruolo in RUOLI_MOTIVO_SPECIFICO:
            filtri_assenze.append(Assenza.motivo.ilike(like))
        risultati['assenze'] = Assenza.query.join(Docente).filter(
            or_(*filtri_assenze)
        ).order_by(Assenza.data.desc()).limit(LIMITE_RISULTATI).all()

        risultati['movimenti'] = MovimentoBancaOre.query.join(Docente).filter(or_(
            MovimentoBancaOre.descrizione.ilike(like),
            Docente.cognome.ilike(like),
            Docente.nome.ilike(like),
        )).order_by(MovimentoBancaOre.data.desc()).limit(LIMITE_RISULTATI).all()

        risultati['sospensioni'] = SospensioneDidattica.query.filter(
            SospensioneDidattica.descrizione.ilike(like)
        ).order_by(SospensioneDidattica.data_inizio.desc()).limit(LIMITE_RISULTATI).all()

        n_totale = sum(len(v) for v in risultati.values())

    return render_template('ricerca/risultati.html',
        q=q, risultati=risultati, n_totale=n_totale)
