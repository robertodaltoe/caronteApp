"""
Business logic per la pianificazione dei permessi/ferie, estratta da
routes/report.py::pianifica_permessi() (era arrivata a ~190 righe che
mescolavano calcolo e presentazione).

Per ogni docente con saldo banca ore positivo, calcola le date future in
cui potrebbe chiedere un permesso orario, sfruttando le ore libere da
assenze/indisponibilità già note, con particolare attenzione a liberare
l'inizio o la fine della giornata (sequenze consecutive).
"""
from collections import defaultdict
from datetime import date, timedelta

from models import db
from models.docente import Docente
from models.orario_docente import OrarioDocente
from models.assenza import Assenza
from models.indisponibilita import Indisponibilita
from models.supplenza import Supplenza
from models.movimento_banca_ore import MovimentoBancaOre

GIORNI_NOMI = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato']


def calcola_pianificazione(anno_corrente):
    """
    Ritorna un dict con tutti i dati necessari alla pagina
    'Pianifica permessi': oggi, fine_anno (None se il calendario per
    l'anno scolastico non è ancora configurato), ore_ultimo_giorno,
    n_festivi_extra, risultati (lista per docente, ordinata per saldo
    finale decrescente, solo chi ha saldo positivo e almeno un'opzione
    disponibile).
    """
    from config_calendario import get_data_fine_lezioni, get_ore_ultimo_giorno
    from models.sospensione import SospensioneDidattica

    oggi = date.today()
    fine_anno = get_data_fine_lezioni(anno_corrente)

    if fine_anno is None:
        return {
            'oggi': oggi,
            'fine_anno': None,
            'ore_ultimo_giorno': None,
            'n_festivi_extra': 0,
            'risultati': None,
        }

    ore_ultimo_giorno = get_ore_ultimo_giorno(anno_corrente)

    # Giorni non didattici (ponti/sospensioni) presi da Sospensioni
    # didattiche (Impostazioni), non da un elenco separato nel codice.
    festivi_extra = set()
    for s in SospensioneDidattica.query.filter(
            SospensioneDidattica.data_fine >= oggi,
            SospensioneDidattica.data_inizio <= fine_anno).all():
        cur_f = max(s.data_inizio, oggi)
        fine_f = min(s.data_fine, fine_anno)
        while cur_f <= fine_f:
            festivi_extra.add(cur_f)
            cur_f += timedelta(days=1)

    # Saldi proiettati (solo anno scolastico corrente)
    saldi_eff_raw = db.session.query(
        MovimentoBancaOre.id_docente,
        db.func.sum(MovimentoBancaOre.minuti)
    ).filter(MovimentoBancaOre.anno_scol == anno_corrente,
             MovimentoBancaOre.data <= oggi).group_by(MovimentoBancaOre.id_docente).all()
    saldi_prev_raw = db.session.query(
        MovimentoBancaOre.id_docente,
        db.func.sum(MovimentoBancaOre.minuti)
    ).filter(MovimentoBancaOre.anno_scol == anno_corrente,
             MovimentoBancaOre.data > oggi).group_by(MovimentoBancaOre.id_docente).all()

    saldi_eff  = {r[0]: (r[1] or 0)//60 for r in saldi_eff_raw}
    saldi_prev = {r[0]: (r[1] or 0)//60 for r in saldi_prev_raw}

    # Date future lavorative (esclusi i giorni festivi configurati per
    # l'anno scolastico corrente)
    date_future = []
    cur = oggi + timedelta(days=1)
    while cur <= fine_anno:
        if cur.weekday() < 6 and cur not in festivi_extra:
            date_future.append(cur)
        cur += timedelta(days=1)

    # Assenze e indisponibilità future per docente+data (cache)
    ass_future = defaultdict(set)   # doc_id -> set di date con assenza
    for a in Assenza.query.filter(Assenza.data > oggi).all():
        ass_future[a.id_docente].add(a.data)
    indisp_future = defaultdict(lambda: defaultdict(set))  # doc_id -> data -> set ore
    for i in Indisponibilita.query.filter(Indisponibilita.data > oggi).all():
        indisp_future[i.id_docente][i.data].add(i.ora)
    # Supplenze già assegnate come sostituto — bloccano l'ora
    for s in Supplenza.query.filter(
        Supplenza.data > oggi,
        Supplenza.stato == 'assegnata',
        Supplenza.id_sostituto != None
    ).all():
        indisp_future[s.id_sostituto][s.data].add(s.ora)

    risultati = []
    for doc in Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all():
        sal_eff  = saldi_eff.get(doc.id, 0)
        sal_prev = saldi_prev.get(doc.id, 0)
        sal_fin  = sal_eff + sal_prev
        if sal_fin < 1:
            continue

        # Orario per giorno — tutte le ore di servizio (lezione + potenziamento)
        orario = defaultdict(list)
        for s in OrarioDocente.query.filter_by(id_docente=doc.id).all():
            if (s.tipo_ora in ('lezione', 'potenziamento')
                    and s.classe not in ('---', '-x-', '', None)):
                orario[s.giorno].append(s.ora)

        opzioni = _opzioni_docente(doc, date_future, orario, ass_future,
                                    indisp_future, ore_ultimo_giorno, fine_anno)

        if opzioni:
            risultati.append({
                'doc':      doc,
                'sal_fin':  sal_fin,
                'sal_eff':  sal_eff,
                'sal_prev': sal_prev,
                'opzioni':  opzioni,
            })

    risultati.sort(key=lambda x: -x['sal_fin'])

    return {
        'oggi': oggi,
        'fine_anno': fine_anno,
        'ore_ultimo_giorno': ore_ultimo_giorno,
        'n_festivi_extra': len(festivi_extra),
        'risultati': risultati,
    }


def _opzioni_docente(doc, date_future, orario, ass_future, indisp_future,
                      ore_ultimo_giorno, fine_anno):
    """Calcola le opzioni di permesso disponibili per un singolo docente."""
    opzioni = []
    for data in date_future:
        giorno = data.weekday()
        ore_base = sorted(set(orario.get(giorno, [])))
        if not ore_base:
            continue
        # Già totalmente assente quel giorno (assenza manuale)?
        if data in ass_future[doc.id]:
            continue
        # Ore bloccate = indisponibilità (simulazioni, BIM, ecc.)
        # In quelle ore NON può chiedere permesso
        ore_bloccate = indisp_future[doc.id].get(data, set())
        # Nell'ultimo giorno di lezione l'orario può essere ridotto
        # (configurabile per anno scolastico)
        if ore_ultimo_giorno is not None and data == fine_anno:
            ora_max_giorno = ore_ultimo_giorno
        else:
            ora_max_giorno = 9
        # Ore richiedibili = ore di servizio NON bloccate e nei limiti della giornata
        ore_permesso = [o for o in ore_base
                        if o not in ore_bloccate and o <= ora_max_giorno]
        if not ore_permesso:
            continue

        # Sequenza finale consecutiva (per liberare fine giornata)
        seq_fine = [ore_permesso[-1]]
        for i in range(len(ore_permesso)-2, -1, -1):
            if ore_permesso[i] == ore_permesso[i+1] - 1:
                seq_fine.insert(0, ore_permesso[i])
            else:
                break

        # Sequenza iniziale consecutiva
        seq_inizio = [ore_permesso[0]]
        for i in range(1, len(ore_permesso)):
            if ore_permesso[i] == ore_permesso[i-1] + 1:
                seq_inizio.append(ore_permesso[i])
            else:
                break

        opzioni.append({
            'data':          data,
            'giorno_nome':   GIORNI_NOMI[giorno],
            'ore_totali':    [o for o in ore_base if o <= ora_max_giorno],
            'ore_permesso':  ore_permesso,
            'ore_bloccate':  [o for o in ore_bloccate if o <= ora_max_giorno],
            'fine': {
                'da': seq_fine[0], 'a': seq_fine[-1], 'n': len(seq_fine),
                'label': f'{seq_fine[0]}ª–{seq_fine[-1]}ª' if len(seq_fine) > 1 else f'{seq_fine[0]}ª'
            },
            'inizio': {
                'da': seq_inizio[0], 'a': seq_inizio[-1], 'n': len(seq_inizio),
                'label': f'{seq_inizio[0]}ª–{seq_inizio[-1]}ª' if len(seq_inizio) > 1 else f'{seq_inizio[0]}ª'
            },
        })
    return opzioni
