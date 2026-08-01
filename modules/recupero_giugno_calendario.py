"""
Business logic della pagina calendario dei corsi di recupero di giugno,
estratta da routes/recupero_giugno.py::calendario() (era arrivata a 465
righe, la funzione più lunga del progetto): gestione delle azioni POST
(aggiungi/modifica/elimina lezione, azzeramento calendario, completamento
automatico bozza) e costruzione dei dati per la pagina GET (sincronizzazione
alunni aderenti da staging, calcolo conflitti docente/alunni).

Ogni funzione azione_* ritorna un dict {'msg': ..., 'cat': ...} (categoria
per flash Flask) e si occupa del proprio commit; la route si limita a
chiamarla e a fare flash+redirect — nessuna logica di business resta lì.
"""
from datetime import date, timedelta
from models import db
from models.recupero import (RecuperoDocente, RecuperoGruppo, RecuperoLezione,
                              RecuperoAlunno, RecuperoImport)
from routes.recupero_costanti import ANNO, DATA_INIZIO, DATA_FINE


def _t(s):
    """Converte 'HH:MM' in minuti dall'inizio giornata (0 se non valido)."""
    try:
        h, m = map(int, s.split(':'))
        return h * 60 + m
    except Exception:
        return 0


def controlla_conflitti(id_gruppo, data_d, ora_inizio, ora_fine, escludi_lid=None):
    """Restituisce lista di messaggi di conflitto (vuota = nessun conflitto)."""
    ini_m = _t(ora_inizio)
    fin_m = _t(ora_fine)
    g = RecuperoGruppo.query.get(id_gruppo)
    if not g:
        return []
    errori = []

    tutti_gruppi = (RecuperoGruppo.query
        .join(RecuperoDocente)
        .filter(RecuperoDocente.anno_scol == ANNO,
                RecuperoGruppo.periodo_codice == 'corsi_giugno')
        .all())

    for ag in tutti_gruppi:
        lezioni_ag = [l for l in RecuperoLezione.query.filter_by(
            id_gruppo=ag.id, data=data_d).all()
            if l.id != escludi_lid]

        for ll in lezioni_ag:
            sovrappone = _t(ll.ora_inizio) < fin_m and _t(ll.ora_fine) > ini_m
            if not sovrappone:
                continue

            # Conflitto docente: stesso id_rec_docente
            if ag.id != id_gruppo and ag.id_rec_docente == g.id_rec_docente:
                doc = g.docente
                errori.append(
                    f'◍︎▨︎ Docente {doc.cognome if doc else "?"} già impegnato '
                    f'{ll.ora_inizio}–{ll.ora_fine} ({ag.materia[:20]})')

            # Conflitto alunni: solo su chi ha effettivamente aderito a entrambi
            if ag.id != id_gruppo:
                alunni_g  = {(a.cognome, a.nome, a.classe) for a in g.alunni}
                alunni_ag = {(a.cognome, a.nome, a.classe) for a in ag.alunni}
                comuni = alunni_g & alunni_ag
                if comuni:
                    nomi = ', '.join(f'{a[0]} {a[1]}' for a in list(comuni)[:3])
                    errori.append(
                        f'◍︎△︎ {len(comuni)} alunni in conflitto con {ag.materia[:20]} '
                        f'{ll.ora_inizio}–{ll.ora_fine}: {nomi}'
                        + ('...' if len(comuni) > 3 else ''))
    return errori


def azione_aggiungi(form):
    id_gruppo  = int(form['id_gruppo'])
    data_str   = form.get('data', '')
    ora_inizio = form.get('ora_inizio', '')
    ora_fine   = form.get('ora_fine', '')
    aula       = form.get('aula', '').strip() or None
    note       = form.get('note', '').strip() or None

    g = RecuperoGruppo.query.get_or_404(id_gruppo)

    # Verifica limite ore per gruppo (configurabile)
    max_ore = g.max_ore or 10
    if g.ore_pianificate >= max_ore:
        return {'msg': f'Gruppo {g.materia} ha già raggiunto le {max_ore} ore massime.',
                'cat': 'warning'}

    # Verifica max 2h in un giorno per questo gruppo
    lezioni_giorno = [l for l in g.lezioni
                      if l.data == date.fromisoformat(data_str)]
    ore_giorno = sum(l.durata_ore for l in lezioni_giorno)
    try:
        h1, m1 = map(int, ora_inizio.split(':'))
        h2, m2 = map(int, ora_fine.split(':'))
        durata = (h2 * 60 + m2 - h1 * 60 - m1) / 60
    except Exception:
        durata = 0

    max_ore_giorno = g.max_ore_giorno or 2
    if ore_giorno + durata > max_ore_giorno:
        return {'msg': f'Massimo {max_ore_giorno} ore al giorno per gruppo.', 'cat': 'warning'}

    data_d = date.fromisoformat(data_str)
    errori = controlla_conflitti(id_gruppo, data_d, ora_inizio, ora_fine)
    if errori:
        return {'msg': '⚠︎ Lezione NON salvata — ' + ' | '.join(errori[:3]), 'cat': 'danger'}

    db.session.add(RecuperoLezione(
        id_gruppo=id_gruppo,
        data=data_d,
        ora_inizio=ora_inizio,
        ora_fine=ora_fine,
        aula=aula,
        note=note,
    ))
    db.session.commit()
    return {'msg': 'Lezione aggiunta.', 'cat': 'success'}


def azione_modifica(form):
    lid        = int(form['id'])
    l          = RecuperoLezione.query.get_or_404(lid)
    nuova_data = date.fromisoformat(form['data'])
    nuova_ini  = form.get('ora_inizio', l.ora_inizio)
    nuova_fin  = form.get('ora_fine', l.ora_fine)

    errori = controlla_conflitti(l.id_gruppo, nuova_data, nuova_ini, nuova_fin,
                                  escludi_lid=lid)
    if errori:
        return {'msg': '⚠︎ Modifica NON salvata — ' + ' | '.join(errori[:3]), 'cat': 'danger'}

    l.data       = nuova_data
    l.ora_inizio = nuova_ini
    l.ora_fine   = nuova_fin
    l.aula       = form.get('aula', '').strip() or None
    l.note       = form.get('note', '').strip() or None
    db.session.commit()
    return {'msg': 'Lezione aggiornata.', 'cat': 'success'}


def azione_elimina(form):
    lid = int(form['id'])
    l = RecuperoLezione.query.get_or_404(lid)
    db.session.delete(l)
    db.session.commit()
    return {'msg': 'Lezione eliminata.', 'cat': 'warning'}


def azione_elimina_giorno(form):
    data_str = form.get('data', '')
    if not data_str:
        return {'msg': 'Data mancante.', 'cat': 'warning'}
    data_d = date.fromisoformat(data_str)
    gruppi_ids = [g.id for g in RecuperoGruppo.query
        .join(RecuperoDocente)
        .filter(RecuperoDocente.anno_scol == ANNO,
                RecuperoGruppo.periodo_codice == 'corsi_giugno').all()]
    n = RecuperoLezione.query.filter(
        RecuperoLezione.id_gruppo.in_(gruppi_ids),
        RecuperoLezione.data == data_d
    ).delete(synchronize_session=False)
    db.session.commit()
    return {'msg': f'Eliminate {n} lezioni del {data_d.strftime("%d/%m/%Y")}.', 'cat': 'warning'}


def azione_elimina_tutto():
    # Solo i gruppi dei corsi di giugno: non toccare le prove di agosto
    gruppi_ids = [g.id for g in RecuperoGruppo.query
        .join(RecuperoDocente)
        .filter(RecuperoDocente.anno_scol == ANNO,
                RecuperoGruppo.periodo_codice == 'corsi_giugno').all()]
    n = RecuperoLezione.query.filter(
        RecuperoLezione.id_gruppo.in_(gruppi_ids)
    ).delete(synchronize_session=False)
    db.session.commit()
    return {'msg': f'Calendario azzerato: {n} lezioni eliminate.', 'cat': 'warning'}


def azione_completa_bozza():
    """Genera lezioni solo per i gruppi (di giugno) che non ne hanno ancora."""
    gruppi_incompleti = [g for g in (RecuperoGruppo.query
        .join(RecuperoDocente)
        .filter(RecuperoDocente.anno_scol == ANNO,
                RecuperoGruppo.periodo_codice == 'corsi_giugno')
        .all()) if len(g.lezioni) == 0]

    if not gruppi_incompleti:
        return {'msg': 'Tutti i gruppi hanno già lezioni pianificate.', 'cat': 'info'}

    date_disp = []
    cur = DATA_INIZIO
    while cur <= DATA_FINE:
        if cur.weekday() < 5:
            date_disp.append(cur)
        cur += timedelta(days=1)

    def _sovrappone(d, ini, fin, occupied):
        ini_m, fin_m = _t(ini), _t(fin)
        for od, oi, of in occupied:
            if od == d and oi < fin_m and of > ini_m:
                return True
        return False

    # Carica slot già occupati da alunni E docenti (solo gruppi di giugno)
    slot_alunni   = {}
    slot_docente2 = {}
    for g in RecuperoGruppo.query.join(RecuperoDocente).filter(
            RecuperoDocente.anno_scol == ANNO,
            RecuperoGruppo.periodo_codice == 'corsi_giugno').all():
        for l in g.lezioni:
            for al in g.alunni:
                key = (al.cognome, al.nome, al.classe)
                slot_alunni.setdefault(key, set()).add(
                    (l.data, _t(l.ora_inizio), _t(l.ora_fine)))
            # Traccia fine ultima lezione del docente
            doc_id = g.id_rec_docente
            fine = _t(l.ora_fine)
            prev = slot_docente2.get(doc_id, {}).get(l.data, 0)
            slot_docente2.setdefault(doc_id, {})[l.data] = max(prev, fine)

    def _priorita_c(g):
        vincoli = g.docente_rec.vincoli if g.docente_rec else []
        ore_disp = 0.0
        for data in date_disp:
            wd = data.weekday()
            for v in vincoli:
                if v.data_inizio and data < v.data_inizio:
                    continue
                if v.data_fine and data > v.data_fine:
                    continue
                if v.giorno is not None and v.giorno != wd:
                    continue
                try:
                    h1, m1 = map(int, v.ora_inizio.split(':'))
                    h2, m2 = map(int, v.ora_fine.split(':'))
                    ore_disp += (h2 * 60 + m2 - h1 * 60 - m1) / 60
                except Exception:
                    pass
        if not vincoli:
            ore_disp = 999
        return (1.0 / (ore_disp + 1)) * 3 + (len(g.alunni) / 50.0) * 2 + (len(vincoli) / 20.0)

    gruppi_incompleti = sorted(gruppi_incompleti, key=_priorita_c, reverse=True)

    inserite = 0
    saltati  = []
    for g in gruppi_incompleti:
        vincoli_doc = g.docente_rec.vincoli
        ha_vincoli  = bool(vincoli_doc)

        def _slot_per_data_c(data):
            wd = data.weekday()
            if not ha_vincoli:
                return [('08:00', '13:00')]
            classi_g = {x.strip().upper() for x in g.classi.split(',')}
            slots = []
            for v in vincoli_doc:
                if v.data_inizio and data < v.data_inizio:
                    continue
                if v.data_fine and data > v.data_fine:
                    continue
                if v.giorno is not None and v.giorno != wd:
                    continue
                if v.classi_vincolo:
                    cv = {x.strip().upper() for x in v.classi_vincolo.split(',')}
                    if not classi_g.intersection(cv):
                        continue
                slots.append((v.ora_inizio, v.ora_fine))
            return slots or []

        max_ore_tot  = g.max_ore or 10
        max_ore_g    = g.max_ore_giorno or 2
        ore_pian     = 0
        ore_per_data = {}
        alunni_g     = g.alunni

        for data in date_disp:
            if ore_pian >= max_ore_tot:
                break
            ore_ok = _slot_per_data_c(data)
            if not ore_ok:
                continue
            ore_oggi = ore_per_data.get(data, 0)
            if ore_oggi >= max_ore_g:
                continue

            for fascia_ini, fascia_fin in ore_ok:
                durata_h = min(
                    (_t(fascia_fin) - _t(fascia_ini)) / 60,
                    max_ore_g - ore_oggi,
                    max_ore_tot - ore_pian, 2)
                if durata_h <= 0:
                    continue
                fin_m = _t(fascia_ini) + int(durata_h * 60)
                ini_s = fascia_ini
                fin_s = f'{fin_m//60:02d}:{fin_m%60:02d}'

                # Ora inizio: dopo l'ultima lezione del docente
                doc_id2 = g.id_rec_docente
                fine_doc2 = slot_docente2.get(doc_id2, {}).get(data, _t(fascia_ini))
                ini_m2 = fine_doc2 + 30 if fine_doc2 > _t(fascia_ini) else _t(fascia_ini)
                fin_max2 = _t(fascia_fin)
                dur_m2 = int(durata_h * 60)
                if ini_m2 + dur_m2 > fin_max2:
                    continue
                ini_s = f'{ini_m2 // 60:02d}:{ini_m2 % 60:02d}'
                fin_s = f'{(ini_m2 + dur_m2) // 60:02d}:{(ini_m2 + dur_m2) % 60:02d}'

                conflitto = any(
                    _sovrappone(data, ini_s, fin_s,
                                slot_alunni.get((al.cognome, al.nome, al.classe), set()))
                    for al in alunni_g)
                if conflitto:
                    continue

                db.session.add(RecuperoLezione(
                    id_gruppo=g.id, data=data,
                    ora_inizio=ini_s, ora_fine=fin_s))
                ore_pian += durata_h
                ore_per_data[data] = ore_per_data.get(data, 0) + durata_h
                inserite += 1
                for al in alunni_g:
                    key = (al.cognome, al.nome, al.classe)
                    slot_alunni.setdefault(key, set()).add(
                        (data, ini_m2, ini_m2 + dur_m2))
                slot_docente2.setdefault(doc_id2, {})[data] = ini_m2 + dur_m2
                break

        if ore_pian == 0:
            saltati.append(g)

    db.session.commit()
    msg = f'Completamento: {inserite} lezioni aggiunte per {len(gruppi_incompleti)-len(saltati)} gruppi.'
    if saltati:
        msg += f' ⚠︎ {len(saltati)} gruppi ancora senza slot: ' + \
               ', '.join(g.materia[:15] for g in saltati)
    return {'msg': msg, 'cat': 'success' if not saltati else 'warning'}


_FAMIGLIE_SYNC = [
    {'LATINO', 'LINGUA LATINA', 'LINGUA E CULTURA LATINA'},
    {'ITALIANO', 'LINGUA E LETTERATURA ITALIANA', 'LINGUA E CULTURA ITALIANA'},
    {'MATEMATICA', 'MATEMATICA CON INFORMATICA', 'MATEMATICA E COMPLEMENTI DI MATEMATICA'},
    {'INFORMATICA', 'TECNOLOGIE INFORMATICHE'},
    {'STORIA', 'STORIA E GEOGRAFIA'},
    {'FISICA', 'SCIENZE INTEGRATE (FISICA)'},
    {'INGLESE', 'LINGUA INGLESE', 'LINGUA E CULTURA STRANIERA (INGLESE)'},
    {'TEDESCO', 'LINGUA TEDESCA', 'LINGUA E CULTURA STRANIERA TEDESCO'},
]


def _match_sync(m1, m2):
    m1u, m2u = m1.strip().upper(), m2.strip().upper()
    if m1u == m2u:
        return True
    for f in _FAMIGLIE_SYNC:
        fs = {x.upper() for x in f}
        if m1u in fs and m2u in fs:
            return True
    return False


def _sync_alunni_da_staging(gruppi_list):
    """
    Sincronizza gli alunni aderenti nello staging import con i gruppi
    (aggiunge i nuovi aderenti, rimuove chi ha cambiato stato). Fa commit.
    """
    imports_all = RecuperoImport.query.filter_by(anno_scol=ANNO).all()

    # Indice staging: (cognome, nome, classe, materia_norm) →︎ stato_adesione
    staging_idx = {}
    for imp in imports_all:
        for f in _FAMIGLIE_SYNC:
            fs = {x.upper() for x in f}
            if imp.materia_norm and imp.materia_norm.upper() in fs:
                for variante in fs:
                    staging_idx[(imp.cognome, imp.nome, imp.classe.upper(), variante)] = imp.stato_adesione
                break
        staging_idx[(imp.cognome, imp.nome, imp.classe.upper(), (imp.materia_norm or '').upper())] = imp.stato_adesione

    for g in gruppi_list:
        classi_g = {cl.strip().upper() for cl in g.classi.split(',')}

        # 1. Aggiungi nuovi aderenti
        for imp in imports_all:
            if imp.classe.upper() not in classi_g:
                continue
            if not _match_sync(g.materia, imp.materia_norm or ''):
                continue
            if imp.stato_adesione not in ('aderisce', 'sconosciuto'):
                continue
            exists = RecuperoAlunno.query.filter_by(
                id_gruppo=g.id, cognome=imp.cognome,
                nome=imp.nome, classe=imp.classe).first()
            if not exists:
                db.session.add(RecuperoAlunno(
                    id_gruppo=g.id, classe=imp.classe,
                    cognome=imp.cognome, nome=imp.nome,
                    codice_fisc=imp.codice_fisc, email=imp.email))

        # 2. Rimuovi chi ha cambiato stato a non_aderisce o studio_ind
        for al in list(g.alunni):
            mat_up = g.materia.upper()
            stato = staging_idx.get((al.cognome, al.nome, al.classe.upper(), mat_up))
            if stato is None:
                for f in _FAMIGLIE_SYNC:
                    fs = {x.upper() for x in f}
                    if mat_up in fs:
                        for variante in fs:
                            stato = staging_idx.get((al.cognome, al.nome, al.classe.upper(), variante))
                            if stato:
                                break
                        break
            if stato in ('non_aderisce', 'studio_ind'):
                db.session.delete(al)

    db.session.commit()


def _calcola_conflitti(lezioni_per_data):
    """Ritorna (conflitti, conflitti_ids) per la vista calendario."""
    conflitti = []

    for data, coppie in lezioni_per_data.items():
        # Conflitto docente: stesso docente in fasce sovrapposte
        doc_lezioni = {}
        for l, g in coppie:
            doc_id = g.id_rec_docente
            doc_lezioni.setdefault(doc_id, []).append((l, g))
        for doc_id, ll in doc_lezioni.items():
            for i in range(len(ll)):
                for j in range(i + 1, len(ll)):
                    l1, g1 = ll[i]
                    l2, g2 = ll[j]
                    if _t(l1.ora_inizio) < _t(l2.ora_fine) and _t(l2.ora_inizio) < _t(l1.ora_fine):
                        doc = g1.docente
                        conflitti.append({
                            'tipo': 'docente',
                            'data': data,
                            'msg': f'{doc.cognome if doc else "?"} ha due lezioni sovrapposte: '
                                   f'{g1.materia[:20]} {l1.ora_inizio}-{l1.ora_fine} / '
                                   f'{g2.materia[:20]} {l2.ora_inizio}-{l2.ora_fine}',
                            'ids': [l1.id, l2.id],
                        })

        # Conflitto alunni: controlla sia alunni espliciti che classi in comune
        for i in range(len(coppie)):
            for j in range(i + 1, len(coppie)):
                l1, g1 = coppie[i]
                l2, g2 = coppie[j]
                if g1.id == g2.id:
                    continue
                sovrappone = _t(l1.ora_inizio) < _t(l2.ora_fine) and _t(l2.ora_inizio) < _t(l1.ora_fine)
                if not sovrappone:
                    continue

                al1 = {(a.cognome, a.nome, a.classe) for a in g1.alunni}
                al2 = {(a.cognome, a.nome, a.classe) for a in g2.alunni}
                comuni = al1 & al2
                if comuni:
                    nomi = ', '.join(f'{a[0]} {a[1]}' for a in list(comuni)[:2])
                    conflitti.append({
                        'tipo': 'alunno',
                        'data': data,
                        'msg': f'{nomi} in due lezioni: {g1.materia[:15]} {l1.ora_inizio}-{l1.ora_fine} / {g2.materia[:15]} {l2.ora_inizio}-{l2.ora_fine}',
                        'ids': [l1.id, l2.id],
                    })

    conflitti_ids = set()
    for cf in conflitti:
        for lid in cf['ids']:
            conflitti_ids.add(lid)

    return conflitti, conflitti_ids


def costruisci_dati_calendario():
    """
    Prepara tutti i dati per la pagina GET del calendario: date lavorative
    disponibili, elenco gruppi (con sync alunni da staging), lezioni
    raggruppate per data, conflitti calcolati.
    """
    date_disponibili = []
    cur = DATA_INIZIO
    while cur <= DATA_FINE:
        if cur.weekday() < 5:  # lun-ven
            date_disponibili.append(cur)
        cur += timedelta(days=1)

    gruppi_list = (RecuperoGruppo.query
                   .join(RecuperoDocente)
                   .filter(RecuperoDocente.anno_scol == ANNO,
                           RecuperoGruppo.periodo_codice == 'corsi_giugno')
                   .order_by(RecuperoGruppo.materia)
                   .all())

    _sync_alunni_da_staging(gruppi_list)

    lezioni_per_data = {}
    for g in gruppi_list:
        for l in g.lezioni:
            lezioni_per_data.setdefault(l.data, []).append((l, g))

    conflitti, conflitti_ids = _calcola_conflitti(lezioni_per_data)

    return {
        'gruppi': gruppi_list,
        'date_disponibili': date_disponibili,
        'lezioni_per_data': lezioni_per_data,
        'conflitti': conflitti,
        'conflitti_ids': conflitti_ids,
    }
