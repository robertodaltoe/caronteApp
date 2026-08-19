"""
Business logic della pagina calendario delle prove di recupero di agosto,
estratta da routes/recupero_agosto.py (route agosto_calendario(), 229
righe, e la funzione di generazione automatica _genera_bozza_agosto(),
295 righe — la seconda funzione più lunga del progetto).

Stesso schema già usato per modules/recupero_giugno_calendario.py: ogni
azione_* ritorna {'msg':..., 'cat':...} e fa il proprio commit; la route
si limita a un dispatch table + flash + redirect. costruisci_dati_agosto()
prepara tutti i dati per la vista GET (conflitti, docenti validi come
assistente, conteggio impegni).
"""
from datetime import date, timedelta
from collections import defaultdict

from models import db
from models.recupero import RecuperoDocente, RecuperoGruppo, RecuperoLezione
from models.docente import Docente
from routes.recupero_costanti import ANNO_AGO, PERIODO_AGO, CONTRATTI_OK, TIPO_PROVA_LABEL


def _t(s):
    try:
        h, m = map(int, s.split(':'))
        return h * 60 + m
    except Exception:
        return 0


def azione_aggiungi(form):
    id_gruppo  = int(form['id_gruppo'])
    data_str   = form.get('data', '')
    ora_inizio = form.get('ora_inizio', '08:00')
    ora_fine   = form.get('ora_fine', '10:00')
    aula       = form.get('aula', '').strip() or None

    g = RecuperoGruppo.query.get_or_404(id_gruppo)
    data_d = date.fromisoformat(data_str)

    ini_m, fin_m = _t(ora_inizio), _t(ora_fine)

    # Controllo conflitti alunni e docenti
    tutti_ag = RecuperoGruppo.query.join(RecuperoDocente).filter(
        RecuperoDocente.anno_scol == ANNO_AGO,
        RecuperoGruppo.periodo_codice == PERIODO_AGO).all()

    errori = []
    for ag in tutti_ag:
        if ag.id == id_gruppo:
            continue
        ll_ag = RecuperoLezione.query.filter_by(id_gruppo=ag.id, data=data_d).all()
        for ll in ll_ag:
            sovrappone = _t(ll.ora_inizio) < fin_m and _t(ll.ora_fine) > ini_m
            if not sovrappone:
                continue
            # Conflitto alunni
            al1 = {(a.cognome, a.nome, a.classe) for a in g.alunni}
            al2 = {(a.cognome, a.nome, a.classe) for a in ag.alunni}
            comuni = al1 & al2
            if comuni:
                nomi = ', '.join(f'{a[0]}' for a in list(comuni)[:3])
                errori.append(f'◍︎△︎ Alunni in conflitto con {ag.materia[:15]}: {nomi}')
            # Conflitto docenti: somministratore (titolare) e assistente (sorvegliante).
            # Usa l'id reale del Docente (g.docente.id), non id_rec_docente
            # (che è l'id di RecuperoDocente — spazio di id diverso).
            doc_ids_g  = set(filter(None, [
                g.docente.id if g.docente else None, g.id_sorvegliante]))
            doc_ids_ag = set(filter(None, [
                ag.docente.id if ag.docente else None, ag.id_sorvegliante]))
            comuni_doc = doc_ids_g & doc_ids_ag
            for did in comuni_doc:
                d = Docente.query.get(did)
                errori.append(f'◍︎▨︎ {d.cognome if d else "?"} già impegnato in {ag.materia[:15]}')

    if errori:
        return {'msg': '⚠︎ NON salvato — ' + ' | '.join(errori[:3]), 'cat': 'danger'}

    db.session.add(RecuperoLezione(
        id_gruppo=id_gruppo, data=data_d,
        ora_inizio=ora_inizio, ora_fine=ora_fine, aula=aula,
    ))
    db.session.commit()
    return {'msg': 'Prova aggiunta.', 'cat': 'success'}


def azione_modifica(form):
    lid = int(form['id'])
    l   = RecuperoLezione.query.get_or_404(lid)
    nuova_data = date.fromisoformat(form['data'])
    nuova_ini  = form.get('ora_inizio', l.ora_inizio)
    nuova_fin  = form.get('ora_fine', l.ora_fine)
    l.data       = nuova_data
    l.ora_inizio = nuova_ini
    l.ora_fine   = nuova_fin
    l.aula       = form.get('aula', '').strip() or None
    db.session.commit()
    return {'msg': 'Prova aggiornata.', 'cat': 'success'}


def azione_elimina(form):
    lid = int(form['id'])
    l = RecuperoLezione.query.get_or_404(lid)
    db.session.delete(l)
    db.session.commit()
    return {'msg': None, 'cat': None}


def azione_elimina_giorno(form):
    data_str = form.get('data', '')
    if not data_str:
        return {'msg': None, 'cat': None}
    data_d = date.fromisoformat(data_str)
    ids_g = [g.id for g in RecuperoGruppo.query.join(RecuperoDocente)
        .filter(RecuperoDocente.anno_scol == ANNO_AGO,
                RecuperoGruppo.periodo_codice == PERIODO_AGO).all()]
    n = RecuperoLezione.query.filter(
        RecuperoLezione.id_gruppo.in_(ids_g),
        RecuperoLezione.data == data_d
    ).delete(synchronize_session=False)
    db.session.commit()
    return {'msg': f'Eliminate {n} prove del {data_d.strftime("%d/%m/%Y")}.', 'cat': 'warning'}


def azione_elimina_tutto():
    ids_g = [g.id for g in RecuperoGruppo.query.join(RecuperoDocente)
        .filter(RecuperoDocente.anno_scol == ANNO_AGO,
                RecuperoGruppo.periodo_codice == PERIODO_AGO).all()]
    n = RecuperoLezione.query.filter(
        RecuperoLezione.id_gruppo.in_(ids_g)
    ).delete(synchronize_session=False)
    db.session.commit()
    return {'msg': f'Calendario azzerato: {n} prove eliminate.', 'cat': 'warning'}


def azione_genera_bozza(form):
    if form.get('conferma_elimina') != '1':
        return {'msg': 'Seleziona la casella di conferma.', 'cat': 'warning'}
    genera_bozza_agosto()
    return {'msg': 'Bozza prove agosto generata.', 'cat': 'success'}


def azione_completa_bozza():
    n_prima = RecuperoLezione.query.join(RecuperoGruppo).join(RecuperoDocente).filter(
        RecuperoDocente.anno_scol == ANNO_AGO,
        RecuperoGruppo.periodo_codice == PERIODO_AGO).count()
    genera_bozza_agosto(solo_incompleti=True)
    n_dopo = RecuperoLezione.query.join(RecuperoGruppo).join(RecuperoDocente).filter(
        RecuperoDocente.anno_scol == ANNO_AGO,
        RecuperoGruppo.periodo_codice == PERIODO_AGO).count()
    if n_dopo > n_prima:
        return {'msg': f'Bozza completata: aggiunte {n_dopo - n_prima} prove ai gruppi che ne erano privi. '
                        'Le prove già pianificate non sono state toccate.', 'cat': 'success'}
    return {'msg': 'Tutti i gruppi hanno già almeno una prova pianificata.', 'cat': 'info'}


def costruisci_dati_agosto():
    """
    Prepara tutti i dati per la pagina GET del calendario agosto: periodo,
    gruppi, lezioni per data, conflitti (docente/alunni), docenti validi
    come assistente e conteggio impegni.
    """
    from models.recupero import RecuperoPeriodo

    periodo = RecuperoPeriodo.query.filter_by(
        anno_scol=ANNO_AGO, codice=PERIODO_AGO).first()

    date_disp = []
    if periodo:
        cur = periodo.data_inizio
        while cur <= periodo.data_fine:
            if cur.weekday() < 5:
                date_disp.append(cur)
            cur += timedelta(days=1)

    gruppi = (RecuperoGruppo.query
              .join(RecuperoDocente)
              .filter(RecuperoDocente.anno_scol == ANNO_AGO,
                      RecuperoGruppo.periodo_codice == PERIODO_AGO)
              .order_by(RecuperoGruppo.materia).all())

    lezioni_per_data = {}
    for g in gruppi:
        for l in g.lezioni:
            lezioni_per_data.setdefault(l.data, []).append((l, g))

    conflitti_ago = []
    for data, coppie in lezioni_per_data.items():
        # Conflitto docente: somministratore (titolare) e assistente
        # (sorvegliante). Usa l'id reale del Docente (g.docente.id), non
        # id_rec_docente (id di RecuperoDocente — spazio di id diverso).
        doc_ll = {}
        for l, g in coppie:
            id_titolare_reale = g.docente.id if g.docente else None
            for doc_id in filter(None, [id_titolare_reale, g.id_sorvegliante]):
                doc_ll.setdefault(doc_id, []).append((l, g))
        for doc_id, ll in doc_ll.items():
            for i in range(len(ll)):
                for j in range(i + 1, len(ll)):
                    l1, g1 = ll[i]
                    l2, g2 = ll[j]
                    if g1.id == g2.id:
                        continue
                    if _t(l1.ora_inizio) < _t(l2.ora_fine) and _t(l2.ora_inizio) < _t(l1.ora_fine):
                        doc = Docente.query.get(doc_id)
                        conflitti_ago.append({
                            'tipo': 'docente', 'data': data,
                            'msg': f'{doc.cognome if doc else "?"} impegnato in due prove: '
                                   f'{g1.materia[:15]} {l1.ora_inizio}-{l1.ora_fine} / '
                                   f'{g2.materia[:15]} {l2.ora_inizio}-{l2.ora_fine}',
                            'ids': [l1.id, l2.id]})
        # Conflitto alunni
        for i in range(len(coppie)):
            for j in range(i + 1, len(coppie)):
                l1, g1 = coppie[i]
                l2, g2 = coppie[j]
                if g1.id == g2.id:
                    continue
                if not (_t(l1.ora_inizio) < _t(l2.ora_fine) and _t(l2.ora_inizio) < _t(l1.ora_fine)):
                    continue
                al1 = {(a.cognome, a.nome, a.classe) for a in g1.alunni}
                al2 = {(a.cognome, a.nome, a.classe) for a in g2.alunni}
                comuni = al1 & al2
                if comuni:
                    nomi = ', '.join(f'{a[0]} {a[1]}' for a in list(comuni)[:2])
                    conflitti_ago.append({
                        'tipo': 'alunno', 'data': data,
                        'msg': f'{nomi}: {g1.materia[:12]} {l1.ora_inizio}-{l1.ora_fine} / {g2.materia[:12]} {l2.ora_inizio}-{l2.ora_fine}',
                        'ids': [l1.id, l2.id]})

    # Conflitto assenza: un docente assegnato (titolare o sorvegliante) su
    # una prova ha un'assenza registrata quel giorno — segnalato solo a
    # livello di data (non incrocia le ore): le ore di RecuperoLezione sono
    # orari assoluti HH:MM mentre quelle di Assenza sono numeri di ora
    # scolastica (1-9), rappresentazioni diverse che non si confrontano
    # direttamente senza la tabella di conversione oraria — un'assenza
    # quel giorno è comunque un segnale da controllare a mano, anche solo
    # a livello di data. Roberto ha segnalato un caso concreto (Santagata)
    # senza alcun riscontro perché prima questo controllo non esisteva.
    from models.assenza import Assenza
    date_coinvolte = list(lezioni_per_data.keys())
    if date_coinvolte:
        assenze_periodo = Assenza.query.filter(Assenza.data.in_(date_coinvolte)).all()
        assenti_per_data = defaultdict(set)
        for a in assenze_periodo:
            assenti_per_data[a.data].add(a.id_docente)
        for data, coppie in lezioni_per_data.items():
            assenti_oggi = assenti_per_data.get(data)
            if not assenti_oggi:
                continue
            segnalati = set()
            for l, g in coppie:
                id_titolare_reale = g.docente.id if g.docente else None
                for doc_id in filter(None, [id_titolare_reale, g.id_sorvegliante]):
                    if doc_id in assenti_oggi and (doc_id, l.id) not in segnalati:
                        segnalati.add((doc_id, l.id))
                        doc = Docente.query.get(doc_id)
                        ruolo = 'somministratore' if doc_id == id_titolare_reale else 'assistente'
                        conflitti_ago.append({
                            'tipo': 'assenza', 'data': data,
                            'msg': f'{doc.cognome if doc else "?"} ({ruolo}) risulta assente questo giorno — '
                                   f'{g.materia[:15]} {l.ora_inizio}-{l.ora_fine}',
                            'ids': [l.id]})

    conflitti_ids_ago = {lid for cf in conflitti_ago for lid in cf['ids']}

    # Docenti validi come assistente (sorvegliante): contratto idoneo e
    # in servizio nell'anno scolastico delle prove — stesso filtro
    # anno_scol_inizio/anno_scol_uscita usato da _docenti_per_anno() in
    # routes/impostazione_anno.py (replicato qui, non importato, per non
    # introdurre una dipendenza da un modulo route dentro modules/).
    # Prima mancava del tutto: comparivano sia docenti non ancora in
    # servizio (arrivano dal 1° settembre, dopo le prove) sia docenti con
    # contratto già scaduto (segnalato da Roberto).
    from sqlalchemy import or_
    docenti_validi = Docente.query.filter(
        Docente.attivo == True,
        Docente.tipo_contratto.in_(CONTRATTI_OK),
        or_(Docente.anno_scol_inizio == None, Docente.anno_scol_inizio <= ANNO_AGO),
        or_(Docente.anno_scol_uscita == None, Docente.anno_scol_uscita > ANNO_AGO),
    ).order_by(Docente.cognome).all()

    # Conteggio impegni (somministratore + assistente) per favorire una
    # distribuzione equa quando si assegna l'assistente manualmente.
    n_impegni_doc = defaultdict(int)
    for g in gruppi:
        if g.id_sorvegliante:
            n_impegni_doc[g.id_sorvegliante] += 1
        if g.docente:
            n_impegni_doc[g.docente.id] += 1

    return {
        'periodo': periodo,
        'gruppi': gruppi,
        'date_disponibili': date_disp,
        'lezioni_per_data': lezioni_per_data,
        'docenti_validi': docenti_validi,
        'n_impegni_docente': dict(n_impegni_doc),
        'TIPO_PROVA_LABEL': TIPO_PROVA_LABEL,
        'conflitti': conflitti_ago,
        'conflitti_ids': conflitti_ids_ago,
    }


def genera_bozza_agosto(solo_incompleti=False):
    """
    Genera bozza calendario prove agosto.

    Criteri di priorità (in ordine):
    1. Mattino prima del pomeriggio. Scritto+orale necessita di due sessioni
       (mattina e pomeriggio, entro le 15:00) — vengono prenotati entrambi
       gli slot per quel gruppo nello stesso giorno.
    2. Ordine materie nei giorni della settimana: Matematica e Italiano
       all'inizio (lun-mar, hanno bisogno di più tempo per la correzione),
       poi Fisica e lingue (mer-gio), Storia per ultima (ven).
    3. Due gruppi possono stare nello STESSO slot se non condividono né
       titolare, né sorvegliante, né alunni — la concorrenza è permessa
       e ricercata attivamente, non solo "non impedita".
    4. Titolare e sorvegliante già impostati su un gruppo (in
       /recupero/agosto/gruppi) non vengono mai toccati. Se il sorvegliante
       manca, viene proposto il docente disponibile con meno impegni totali
       (per distribuire equamente il carico), libero in quello slot.

    Se solo_incompleti=True (modalità "completa bozza"): non elimina nulla,
    piazza lezioni solo per i gruppi che non ne hanno ancora nessuna —
    le prove già pianificate (automaticamente o a mano) restano intatte
    e vengono comunque considerate nel calcolo dei conflitti.
    """
    from models.recupero import RecuperoPeriodo

    periodo = RecuperoPeriodo.query.filter_by(
        anno_scol=ANNO_AGO, codice=PERIODO_AGO).first()
    if not periodo:
        return

    tutti_i_gruppi = (RecuperoGruppo.query
              .join(RecuperoDocente)
              .filter(RecuperoDocente.anno_scol == ANNO_AGO,
                      RecuperoGruppo.periodo_codice == PERIODO_AGO).all())

    if solo_incompleti:
        # Non tocca nulla: i gruppi già pianificati restano com'erano.
        gruppi_gia_pianificati = [g for g in tutti_i_gruppi if len(g.lezioni) > 0]
        gruppi = [g for g in tutti_i_gruppi if len(g.lezioni) == 0]
        if not gruppi:
            return
    else:
        # Elimina lezioni esistenti (si riparte da zero ad ogni generazione)
        for g in tutti_i_gruppi:
            RecuperoLezione.query.filter_by(id_gruppo=g.id).delete()
        db.session.commit()
        gruppi_gia_pianificati = []
        gruppi = tutti_i_gruppi

    def _fmt(m):
        return f'{m//60:02d}:{m%60:02d}'

    ORA_INI_GIORNO = _t(periodo.ora_inizio)          # es. 08:00
    ORA_FINE_GIORNO = _t(periodo.ora_fine)            # es. 16:00
    LIMITE_POMERIGGIO = _t('15:00')                   # scritto+orale: 2a sessione entro le 15
    INIZIO_POMERIGGIO = _t('13:00')

    # Giorni feriali del periodo, in ordine
    giorni = []
    cur = periodo.data_inizio
    while cur <= periodo.data_fine:
        if cur.weekday() < 5:
            giorni.append(cur)
        cur += timedelta(days=1)
    if not giorni:
        return

    # Priorità materia -> indice giorno preferito (0 = primo giorno disponibile)
    # Matematica/Italiano: giorno 0-1 — Fisica/lingue: giorno 1-3 — Storia: ultimo
    def _priorita_materia(materia):
        m = (materia or '').upper()
        if 'MATEMATICA' in m or 'ITALIANO' in m or 'LETTERATURA ITALIANA' in m:
            return 0
        if 'STORIA' in m:
            return 3
        if 'FISICA' in m or 'INGLESE' in m or 'LINGUA' in m or 'TEDESC' in m or 'FRANCESE' in m or 'SPAGNOL' in m:
            return 1
        return 2

    # Ordina i gruppi: prima per priorità materia, poi per chi ha meno
    # disponibilità (durata maggiore = più vincolante da piazzare), poi
    # scritto_orale prima (ha bisogno di due sessioni, va piazzato con più
    # margine), poi per numero di alunni decrescente.
    def _peso_gruppo(g):
        tipo_peso = 0 if (g.tipo_prova == 'scritto_orale') else 1
        return (_priorita_materia(g.materia), tipo_peso, -(g.durata_ore or 2.0), -len(g.alunni))

    gruppi_ordinati = sorted(gruppi, key=_peso_gruppo)

    # Stato occupazione: per ogni giorno, lista di (ini_m, fin_m, set_docenti, set_alunni)
    occupazione = {d: [] for d in giorni}

    # Massimo prove in contemporanea (vincolo rigido) — l'ideale sarebbe
    # restare su 2-3, ma si arriva a 4 se serve per piazzare tutto nel periodo.
    MAX_PROVE_PARALLELE = 4

    def _n_sovrapposte(giorno, ini_m, fin_m):
        return sum(1 for oi, of, _, _ in occupazione[giorno] if oi < fin_m and of > ini_m)

    def _slot_libero(giorno, ini_m, fin_m, docenti_gruppo, alunni_gruppo):
        n_sovrapposte = 0
        for oi, of, docs, als in occupazione[giorno]:
            if oi < fin_m and of > ini_m:
                if docenti_gruppo & docs:
                    return False
                if alunni_gruppo & als:
                    return False
                n_sovrapposte += 1
        if n_sovrapposte >= MAX_PROVE_PARALLELE:
            return False
        return True

    def _docenti_gruppo(g):
        # Somministratore (titolare) + assistente (sorvegliante) — i due
        # unici ruoli reali per le prove di agosto.
        return set(filter(None, [
            g.docente_rec.docente.id if g.docente_rec and g.docente_rec.docente else None,
            g.id_sorvegliante,
        ]))

    def _alunni_gruppo(g):
        return {(a.cognome, a.nome, a.classe) for a in g.alunni}

    # Modalità "completa bozza": registra subito l'occupazione delle prove
    # già pianificate (a mano o da una generazione precedente), così i nuovi
    # piazzamenti evitano conflitti con quanto già esiste senza toccarlo.
    if solo_incompleti:
        for g_fatto in gruppi_gia_pianificati:
            docs_g = _docenti_gruppo(g_fatto)
            als_g = _alunni_gruppo(g_fatto)
            for l in g_fatto.lezioni:
                if l.data in occupazione:
                    occupazione[l.data].append(
                        (_t(l.ora_inizio), _t(l.ora_fine), docs_g, als_g))

    # Conteggio impegni per docente (somministratore + assistente), per
    # proporre l'assistente mancante con il carico più basso.
    n_impegni = defaultdict(int)
    for g in tutti_i_gruppi:
        if g.id_sorvegliante:
            n_impegni[g.id_sorvegliante] += 1
        if g.docente_rec and g.docente_rec.docente:
            n_impegni[g.docente_rec.docente.id] += 1

    docenti_idonei_ord = Docente.query.filter(
        Docente.attivo == True,
        Docente.tipo_contratto.in_(CONTRATTI_OK)
    ).all()

    # Assenze registrate nel periodo, per escludere chi non è davvero
    # disponibile in quel giorno specifico (non solo per tutto il periodo).
    from models.assenza import Assenza
    assenze_per_doc_giorno = defaultdict(set)  # id_docente -> set di date assente
    if giorni:
        assenze_periodo = Assenza.query.filter(
            Assenza.data >= giorni[0], Assenza.data <= giorni[-1]).all()
        for a in assenze_periodo:
            assenze_per_doc_giorno[a.id_docente].add(a.data)

    def _trova_sorvegliante_libero(giorno, ini_m, fin_m, escludi_ids):
        candidati = [d for d in docenti_idonei_ord
                     if d.id not in escludi_ids
                     and giorno not in assenze_per_doc_giorno.get(d.id, set())]
        candidati.sort(key=lambda d: n_impegni.get(d.id, 0))
        for d in candidati:
            occupato = False
            for oi, of, docs, als in occupazione[giorno]:
                if oi < fin_m and of > ini_m and d.id in docs:
                    occupato = True
                    break
            if not occupato:
                return d
        return None

    def _registra_slot(giorno, ini_m, fin_m, g, docenti_extra=None):
        docs = _docenti_gruppo(g)
        if docenti_extra:
            docs |= docenti_extra
        als = _alunni_gruppo(g)
        occupazione[giorno].append((ini_m, fin_m, docs, als))

    def _crea_lezione(g, giorno, ini_m, fin_m):
        db.session.add(RecuperoLezione(
            id_gruppo=g.id, data=giorno,
            ora_inizio=_fmt(ini_m), ora_fine=_fmt(fin_m),
        ))

    def _assegna_sorvegliante_se_manca(g, giorno, ini_m, fin_m):
        if g.id_sorvegliante:
            return  # già fissato in /recupero/agosto/gruppi: non si tocca
        escludi = _docenti_gruppo(g)
        sorv = _trova_sorvegliante_libero(giorno, ini_m, fin_m, escludi)
        if sorv:
            g.id_sorvegliante = sorv.id
            n_impegni[sorv.id] = n_impegni.get(sorv.id, 0) + 1
            return sorv.id
        return None

    def _piazza_in_giorno_preferito(g, durata_m, giorno_pref_idx, scegli_pomeriggio=False):
        """Cerca uno slot libero a partire dal giorno preferito, scorrendo
        i giorni successivi se necessario. PRIVILEGIA gli orari di inizio
        già usati da altri gruppi compatibili in quel giorno — così le prove
        si affiancano in parallelo invece di accodarsi sempre in sequenza —
        e solo come fallback apre un nuovo slot scandendo a passi di 15 min.
        Se scegli_pomeriggio, cerca nella fascia 13:00-15:00, altrimenti
        nella fascia mattutina."""
        docenti_g = _docenti_gruppo(g)
        alunni_g = _alunni_gruppo(g)

        ordine_giorni = giorni[giorno_pref_idx:] + giorni[:giorno_pref_idx]
        for giorno in ordine_giorni:
            if scegli_pomeriggio:
                base_m, limite_m = INIZIO_POMERIGGIO, LIMITE_POMERIGGIO
            else:
                base_m, limite_m = ORA_INI_GIORNO, ORA_FINE_GIORNO

            # 1. Prova ad affiancarsi a slot già aperti in questo giorno
            #    (stesso orario di inizio di un gruppo già piazzato).
            #    Ordina per affollamento CRESCENTE: preferisce gli slot con
            #    meno prove già presenti, per restare vicino all'ideale di
            #    2-3 contemporanee prima di arrivare al massimo di 4.
            inizi_unici = {oi for oi, of, _, _ in occupazione[giorno]
                          if base_m <= oi and oi + durata_m <= limite_m}
            inizi_esistenti = sorted(inizi_unici,
                key=lambda oi: _n_sovrapposte(giorno, oi, oi + durata_m))
            for ini_m in inizi_esistenti:
                fin_m = ini_m + durata_m
                if _slot_libero(giorno, ini_m, fin_m, docenti_g, alunni_g):
                    return giorno, ini_m, fin_m

            # 2. Fallback: apre un nuovo slot, scandendo dall'inizio fascia.
            ini_m = base_m
            while ini_m + durata_m <= limite_m:
                fin_m = ini_m + durata_m
                if _slot_libero(giorno, ini_m, fin_m, docenti_g, alunni_g):
                    return giorno, ini_m, fin_m
                ini_m += 15
        return None, None, None

    for g in gruppi_ordinati:
        tipo = g.tipo_prova or 'scritto'
        durata_m = int((g.durata_ore or 2.0) * 60)
        giorno_pref_idx = min(_priorita_materia(g.materia), len(giorni) - 1)

        if tipo == 'scritto_orale':
            # Due sessioni: una al mattino, una al pomeriggio (entro le 15),
            # preferibilmente lo stesso giorno.
            giorno1, ini1, fin1 = _piazza_in_giorno_preferito(
                g, durata_m, giorno_pref_idx, scegli_pomeriggio=False)
            if giorno1 is None:
                continue  # nessuno slot mattutino disponibile in tutto il periodo
            _crea_lezione(g, giorno1, ini1, fin1)
            _registra_slot(giorno1, ini1, fin1, g)
            sorv_id = _assegna_sorvegliante_se_manca(g, giorno1, ini1, fin1)

            # Seconda sessione: stesso giorno se possibile, pomeriggio
            docenti_g = _docenti_gruppo(g)
            alunni_g = _alunni_gruppo(g)
            ini2 = INIZIO_POMERIGGIO
            trovato2 = False
            while ini2 + durata_m <= LIMITE_POMERIGGIO:
                fin2 = ini2 + durata_m
                if _slot_libero(giorno1, ini2, fin2, docenti_g, alunni_g):
                    _crea_lezione(g, giorno1, ini2, fin2)
                    _registra_slot(giorno1, ini2, fin2, g)
                    trovato2 = True
                    break
                ini2 += 15
            if not trovato2:
                # Stesso giorno pieno: prova nei giorni successivi
                g2, i2, f2 = _piazza_in_giorno_preferito(
                    g, durata_m, giorno_pref_idx, scegli_pomeriggio=True)
                if g2 is not None:
                    _crea_lezione(g, g2, i2, f2)
                    _registra_slot(g2, i2, f2, g)
        else:
            giorno, ini_m, fin_m = _piazza_in_giorno_preferito(
                g, durata_m, giorno_pref_idx, scegli_pomeriggio=False)
            if giorno is None:
                # Nessuno slot mattutino: prova anche il pomeriggio (entro le 15)
                giorno, ini_m, fin_m = _piazza_in_giorno_preferito(
                    g, durata_m, giorno_pref_idx, scegli_pomeriggio=True)
            if giorno is None:
                continue  # non è stato possibile piazzare il gruppo
            _crea_lezione(g, giorno, ini_m, fin_m)
            _registra_slot(giorno, ini_m, fin_m, g)
            _assegna_sorvegliante_se_manca(g, giorno, ini_m, fin_m)

    db.session.commit()
