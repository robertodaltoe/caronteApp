"""
Utility per la gestione delle compresenze.
Una compresenza è quando due docenti hanno lezione nella stessa classe,
stesso giorno, stessa ora.
"""
from models import db
from models.orario_docente import OrarioDocente
from collections import defaultdict

_cache = {}

def get_compresenze(giorno, ora, classe):
    """
    Restituisce la lista di id_docente per (giorno, ora, classe).
    Include titolari (lezione), ITP (compresenza) e docenti di sostegno
    (models.orario_sostegno.OrarioSostegno, tabella separata) — tutti e
    tre possono tenere la classe da soli se gli altri sono assenti.
    """
    key = (giorno, ora, classe)
    if key not in _cache:
        slots = OrarioDocente.query.filter_by(
            giorno=giorno, ora=ora, classe=classe
        ).filter(
            OrarioDocente.tipo_ora.in_(['lezione', 'compresenza'])
        ).all()
        from models.orario_sostegno import OrarioSostegno
        slots_sostegno = OrarioSostegno.query.filter_by(
            giorno=giorno, ora=ora, classe=classe
        ).all()
        # Deduplica per id_docente
        seen = set()
        ids = []
        for s in list(slots) + list(slots_sostegno):
            if s.id_docente not in seen:
                seen.add(s.id_docente)
                ids.append(s.id_docente)
        _cache[key] = ids
    return _cache[key]

def ha_compresenza(giorno, ora, classe):
    """True se c'è più di un docente in quell'ora/classe."""
    return len(get_compresenze(giorno, ora, classe)) > 1

def compagno_compresenza(id_docente, giorno, ora, classe):
    """Ritorna gli altri docenti in compresenza (lista di id)."""
    tutti = get_compresenze(giorno, ora, classe)
    return [d for d in tutti if d != id_docente]

def invalida_cache():
    """Da chiamare quando l'orario cambia."""
    global _cache
    _cache = {}


def compagni_presenti(id_docente, giorno, ora, classe, data):
    """
    Restituisce i compagni di compresenza che sono EFFETTIVAMENTE presenti
    (non assenti e non indisponibili) in quella data/ora/classe.
    """
    from models.assenza import Assenza
    from models.indisponibilita import Indisponibilita

    compagni = [c for c in get_compresenze(giorno, ora, classe)
                if c != id_docente]
    presenti = []
    for cid in compagni:
        # Assente?
        assente = Assenza.query.filter_by(id_docente=cid, data=data).filter(
            Assenza.ora_inizio <= ora,
            Assenza.ora_fine   >= ora
        ).first()
        if assente:
            continue
        # Indisponibile (BIM, simulazione, ecc.)?
        indisp = Indisponibilita.query.filter_by(
            id_docente=cid, data=data, ora=ora
        ).first()
        if indisp:
            continue
        presenti.append(cid)
    return presenti


def ha_compagno_presente(id_docente, giorno, ora, classe, data):
    """True se c'è almeno un compagno presente in quella compresenza."""
    return len(compagni_presenti(id_docente, giorno, ora, classe, data)) > 0
