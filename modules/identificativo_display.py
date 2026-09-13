"""
Identificativo "sicuro" di un docente da mostrare sul monitor pubblico
(routes/display.py) — Sessione 69 addendum 6, richiesto dal DS dopo la
comunicazione del DPO sul Provvedimento Garante n. 112/2026: niente
cognomi/nomi interi sullo schermo condiviso in sala docenti/segreteria,
anche a login ormai richiesto (vedi app.py::ROUTE_PUBBLICHE).

Due livelli, scelti per docente:
1. Docente.codice_display valorizzato -> usato cosi' com'e' (pensato
   per un futuro codice alfanumerico "noto solo al docente", es. un
   badge — non ancora attivato: nessun docente ce l'ha finche' il DS
   non decide di introdurlo, dalla scheda anagrafica).
2. Altrimenti (il caso di oggi): iniziali calcolate al volo — prima
   lettera del cognome + iniziale del nome (es. "S.M."); se due o piu'
   docenti attivi condividono la stessa sigla, si allunga la parte di
   cognome di quei soli docenti di una lettera alla volta finche' non
   sono di nuovo distinguibili tra loro (es. "SA.M." vs "SA.G.") —
   esattamente la regola indicata dal DS. Ricalcolate ad ogni richiesta
   sull'insieme dei docenti attivi: nessuna cache da invalidare quando
   cambia l'anagrafica, il costo (poche decine di docenti) è
   trascurabile.

Attenzione: anche le iniziali restano dato personale a tutti gli
effetti (in una scuola piccola, sigla + classe + materia identificano
la persona con la stessa facilita' del nome per iscritto) — questo
modulo riduce la leggibilita' immediata sullo schermo condiviso, non
sostituisce il controllo d'accesso (login) richiesto su /display.
"""


def _sigla_base(docente, lunghezza_cognome):
    cognome = (docente.cognome or '').strip().upper()
    nome = (docente.nome or '').strip().upper()
    base = cognome[:lunghezza_cognome] or '?'
    return f"{base}.{nome[0]}." if nome else f"{base}."


def calcola_iniziali_uniche(docenti):
    """{id_docente: sigla} per l'elenco di docenti passato, uniche tra
    loro (non rispetto a docenti fuori da questo elenco)."""
    lunghezza = {d.id: 1 for d in docenti}
    mappa = {}

    max_lunghezza = max((len(d.cognome or '') for d in docenti), default=1) or 1

    while True:
        sigle = {}
        for d in docenti:
            sigle.setdefault(_sigla_base(d, lunghezza[d.id]), []).append(d.id)

        ancora_ambigue = False
        for sigla, ids in sigle.items():
            if len(ids) == 1:
                mappa[ids[0]] = sigla
                continue
            for id_doc in ids:
                if lunghezza[id_doc] < max_lunghezza:
                    lunghezza[id_doc] += 1
                    ancora_ambigue = True
                else:
                    # Cognome identico esaurito (omonimia vera): restano
                    # indistinguibili solo dalle iniziali, si accetta la
                    # sigla uguale piuttosto che bloccarsi in un ciclo
                    # infinito — caso raro, segnalabile solo assegnando
                    # un codice alfanumerico manuale (codice_display).
                    mappa[id_doc] = sigla
        if not ancora_ambigue:
            break

    return mappa


def identificativi_display(docenti):
    """{id_docente: stringa da mostrare} per l'elenco di docenti dato —
    usa codice_display quando presente, altrimenti le iniziali uniche
    calcolate SOLO tra i docenti senza un codice_display proprio."""
    con_codice = {d.id: d.codice_display for d in docenti if d.codice_display}
    senza_codice = [d for d in docenti if not d.codice_display]
    iniziali = calcola_iniziali_uniche(senza_codice) if senza_codice else {}
    return {**iniziali, **con_codice}
