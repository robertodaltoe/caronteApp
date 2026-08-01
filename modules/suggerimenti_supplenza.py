"""
modules/suggerimenti_supplenza.py — logica di business per il calcolo
dei docenti suggeriti come sostituti (usata da
routes/supplenze.py::api_suggerimenti()).

Estratto da una singola funzione-route di ~400 righe (route Flask +
query DB + regole di business tutte insieme) in funzioni più piccole,
con un nome e una responsabilità precisi, testabili passando dati già
letti dal DB invece di dover simulare un'intera richiesta HTTP.

Non tutta la logica è "pura" in senso stretto — buona parte dipende
comunque da query al DB (chi è assente, chi ha compresenza attiva) — ma
isolarla in funzioni dedicate rende leggibile QUALE regola si sta
applicando in ogni punto, invece di dover leggere 400 righe di seguito
per capirlo. Le funzioni davvero pure (niente DB, solo calcolo su dati
già in memoria) sono segnalate nel docstring di ciascuna.
"""
from datetime import date as _date
from models import db
from models.assenza import Assenza
from models.indisponibilita import Indisponibilita
from models.supplenza import Supplenza
from models.movimento_banca_ore import MovimentoBancaOre
from sqlalchemy import func


def formatta_saldo_label(minuti):
    """PURA — nessuna query. Converte un numero di minuti (segno incluso)
    in una stringa leggibile tipo '+3h' o '-1h30'."""
    ore  = abs(minuti) // 60
    mins = abs(minuti) % 60
    segno = '+' if minuti >= 0 else '-'
    if mins:
        return f"{segno}{ore}h{mins:02d}"
    return f"{segno}{ore}h"


def formatta_saldo_label_proiettato(saldo_eff, saldo_prev):
    """PURA — nessuna query. Etichetta saldo effettivo, con eventuale
    proiezione (' → +Xh') se ci sono movimenti futuri già programmati.
    Usata sia nei gruppi principali sia nel gruppo 'fuori aula' — prima
    era duplicata identica in due punti della funzione originale."""
    label = formatta_saldo_label(saldo_eff)
    if saldo_prev != 0:
        label += f' → {formatta_saldo_label(saldo_eff + saldo_prev)}'
    return label


def calcola_saldi_docenti(anno_scol, oggi=None):
    """
    Calcola il saldo banca ore di tutti i docenti per l'anno scolastico
    indicato, diviso in effettivo (movimenti fino a oggi) e previsto
    (movimenti futuri già programmati). Stessa convenzione usata in
    routes/report.py.

    Ritorna (saldi_eff, saldi_prev, saldi_totale) — tre dict
    {id_docente: minuti}.
    """
    oggi = oggi or _date.today()

    saldi_eff_raw = db.session.query(
        MovimentoBancaOre.id_docente,
        func.sum(MovimentoBancaOre.minuti).label('totale')
    ).filter(MovimentoBancaOre.anno_scol == anno_scol,
             MovimentoBancaOre.data <= oggi
    ).group_by(MovimentoBancaOre.id_docente).all()
    saldi_eff = {r.id_docente: r.totale or 0 for r in saldi_eff_raw}

    saldi_prev_raw = db.session.query(
        MovimentoBancaOre.id_docente,
        func.sum(MovimentoBancaOre.minuti).label('totale')
    ).filter(MovimentoBancaOre.anno_scol == anno_scol,
             MovimentoBancaOre.data > oggi
    ).group_by(MovimentoBancaOre.id_docente).all()
    saldi_prev = {r.id_docente: r.totale or 0 for r in saldi_prev_raw}

    saldi_totale = {doc_id: saldi_eff.get(doc_id, 0) for doc_id in
                    set(list(saldi_eff.keys()) + list(saldi_prev.keys()))}
    for doc_id in saldi_prev:
        saldi_totale.setdefault(doc_id, 0)

    return saldi_eff, saldi_prev, saldi_totale


def docenti_esclusi(data_sel, ora, giorno):
    """
    Determina quali docenti NON sono candidabili come sostituti in una
    data/ora/giorno-settimana specifici, per motivi diversi da "occupato
    su un'altra supplenza": assenza (tutto il giorno o solo quell'ora)
    e indisponibilità puntuale.

    Ritorna (assenti_tutto_giorno_ids, assenti_ora_ids, indisp_ids).
    Le indisponibilità ricorrenti e i colloqui fissi restano nella route
    (dipendono anche da eccezioni per-docente più complesse da isolare
    senza rischiare regressioni).
    """
    assenze_giorno = Assenza.query.filter_by(data=data_sel).all()

    assenti_tutto_giorno_ids = set()
    assenti_ora_ids = set()
    for a in assenze_giorno:
        if a.ora_inizio is None or a.ora_fine is None:
            assenti_tutto_giorno_ids.add(a.id_docente)
        elif a.ora_inizio <= 1 and a.ora_fine >= 8:
            assenti_tutto_giorno_ids.add(a.id_docente)
        elif a.ora_inizio <= ora <= a.ora_fine:
            assenti_ora_ids.add(a.id_docente)

    indisp_ids = {
        i.id_docente for i in
        Indisponibilita.query.filter_by(data=data_sel)
        .filter(db.or_(Indisponibilita.ora.is_(None), Indisponibilita.ora == ora))
        .all()
    }

    return assenti_tutto_giorno_ids, assenti_ora_ids, indisp_ids


def docenti_occupati_stessa_ora(data_sel, ora):
    """
    Docenti già assegnati come sostituto in un'altra supplenza nella
    stessa data/ora. Chi copre potenziamento resta comunque visibile nel
    gruppo potenziamento (non è "impegnato su una classe vera").

    Ritorna (occupati_ids, occupati_potenziamento_ids).
    """
    sups_stessa_ora = (Supplenza.query
        .filter_by(data=data_sel, ora=ora)
        .filter(Supplenza.stato.in_(['assegnata', 'scoperta']))
        .filter(Supplenza.id_sostituto.isnot(None))
        .all())
    occupati_ids = {s.id_sostituto for s in sups_stessa_ora if s.tipo != 'potenziamento'}
    occupati_pot_ids = {s.id_sostituto for s in sups_stessa_ora if s.tipo == 'potenziamento'}
    return occupati_ids, occupati_pot_ids


def ha_ora_adiacente(ore_occupate, ora):
    """PURA — nessuna query. Dato l'insieme di ore in cui il docente ha
    già un impegno nel giorno, dice se l'ora immediatamente prima o dopo
    'ora' è tra queste (utile per proporre chi ha già un buco vicino,
    invece di far venire a scuola qualcuno solo per quell'ora)."""
    return (ora - 1) in ore_occupate or (ora + 1) in ore_occupate
