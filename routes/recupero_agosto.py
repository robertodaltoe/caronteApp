"""
Route specifiche delle prove di recupero di agosto: gestione gruppi
prova (somministratore+assistente), generazione calendario con
controllo conflitti e limite di parallelismo, verifica docenti
disponibili, coppie titolare/ITP.

Registrate sullo stesso blueprint recupero_bp importato da
routes.recupero — questo file importa SOLO da recupero_costanti
(foglia), mai da routes.recupero stesso, per evitare un ciclo (lo
stesso schema già usato per recupero_export.py).
"""
from flask import render_template, request, redirect, url_for, flash
from models import db
from models.recupero import RecuperoDocente, RecuperoGruppo, RecuperoLezione, RecuperoAlunno
from models.docente import Docente
from datetime import date, timedelta
from routes.recupero_costanti import (
    ANNO_AGO, PERIODO_AGO, CONTRATTI_OK, TIPO_PROVA_LABEL,
    _FAMIGLIE_MATERIE, _materia_canonica, _norm_materia,
    _split_cognome_nome, _parse_tipo_prova,
)

from routes.recupero import recupero_bp


@recupero_bp.route('/recupero/agosto')
def agosto_index():
    from models.recupero import RecuperoPeriodo
    periodo = RecuperoPeriodo.query.filter_by(
        anno_scol=ANNO_AGO, codice=PERIODO_AGO).first()

    gruppi = (RecuperoGruppo.query
              .join(RecuperoDocente)
              .filter(RecuperoDocente.anno_scol == ANNO_AGO,
                      RecuperoGruppo.periodo_codice == PERIODO_AGO)
              .order_by(RecuperoGruppo.materia)
              .all())

    tot_alunni  = sum(len(g.alunni) for g in gruppi)
    tot_lezioni = sum(len(g.lezioni) for g in gruppi)

    return render_template('recupero/agosto_index.html',
        periodo=periodo, gruppi=gruppi,
        tot_alunni=tot_alunni, tot_lezioni=tot_lezioni,
        anno=ANNO_AGO)


@recupero_bp.route('/recupero/agosto/docenti-disponibili')
def agosto_docenti_disponibili():
    """
    Verifica disponibilità docenti per le prove di agosto.
    A differenza di giugno, la disponibilità NON dipende da un'iscrizione
    manuale (RecuperoDocente) ma da:
      1. Tipo di contratto idoneo (TI, TD_annuale — CONTRATTI_OK)
      2. Assenza di assenze registrate manualmente nel periodo prove agosto
    """
    from models.recupero import RecuperoPeriodo
    from models.assenza import Assenza
    from datetime import timedelta

    periodo = RecuperoPeriodo.query.filter_by(
        anno_scol=ANNO_AGO, codice=PERIODO_AGO).first()

    date_periodo = []
    if periodo:
        cur = periodo.data_inizio
        while cur <= periodo.data_fine:
            if cur.weekday() < 5:  # solo giorni feriali lun-ven
                date_periodo.append(cur)
            cur += timedelta(days=1)

    docenti_validi = Docente.query.filter(
        Docente.attivo == True,
        Docente.tipo_contratto.in_(CONTRATTI_OK)
    ).order_by(Docente.cognome).all()

    righe = []
    for d in docenti_validi:
        assenze_periodo = []
        if date_periodo:
            assenze_periodo = Assenza.query.filter(
                Assenza.id_docente == d.id,
                Assenza.data >= date_periodo[0],
                Assenza.data <= date_periodo[-1],
            ).order_by(Assenza.data).all()

        giorni_assente = {a.data for a in assenze_periodo}
        giorni_liberi = [dt for dt in date_periodo if dt not in giorni_assente]

        righe.append({
            'docente': d,
            'contratto': d.tipo_contratto,
            'assenze': assenze_periodo,
            'n_giorni_assente': len(giorni_assente),
            'n_giorni_liberi': len(giorni_liberi),
            'n_giorni_totali': len(date_periodo),
            'completamente_libero': len(giorni_assente) == 0,
            'completamente_assente': len(date_periodo) > 0 and len(giorni_liberi) == 0,
        })

    n_completamente_liberi = sum(1 for r in righe if r['completamente_libero'])
    n_con_assenze = sum(1 for r in righe if r['n_giorni_assente'] > 0)
    n_non_disponibili = sum(1 for r in righe if r['completamente_assente'])

    return render_template('recupero/agosto_docenti_disponibili.html',
        periodo=periodo,
        date_periodo=date_periodo,
        righe=righe,
        contratti_ok=CONTRATTI_OK,
        n_totale=len(righe),
        n_completamente_liberi=n_completamente_liberi,
        n_con_assenze=n_con_assenze,
        n_non_disponibili=n_non_disponibili,
        anno=ANNO_AGO)


@recupero_bp.route('/recupero/agosto/gruppi', methods=['GET', 'POST'])
def agosto_gruppi():
    """
    Creazione manuale gruppi prove agosto (modello identico a /recupero/gruppi
    di giugno). Per ogni docente titolare si selezionano le classi (tra quelle
    con alunni in debito nella sua materia di titolarita') con pillole
    cliccabili, accorpando piu' classi nello stesso gruppo. Il sorvegliante
    si scegli liberamente tra tutti i docenti disponibili per contratto,
    con indicazione delle classi in cui insegna (informativo, non vincolante).
    """
    from collections import defaultdict
    from models.recupero import RecuperoImport

    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione in ('aggiungi', 'crea_da_proposta'):
            id_recdoc      = int(request.form['id_rec_docente'])
            materia        = request.form.get('materia', '').strip()
            cognome_doc    = request.form.get('cognome_doc', '').strip()
            tipo_prova     = request.form.get('tipo_prova', 'scritto')
            durata_ore     = float(request.form.get('durata_ore', 2.0) or 2.0)
            id_sorv        = request.form.get('id_sorvegliante') or None
            classi_list    = request.form.getlist('classi_cb')
            classi         = ','.join(cl.strip() for cl in classi_list if cl.strip())

            if not classi:
                flash('Seleziona almeno una classe.', 'warning')
                return redirect(url_for('recupero.agosto_gruppi'))

            g = RecuperoGruppo(
                id_rec_docente=id_recdoc, materia=materia,
                classi=classi, periodo_codice=PERIODO_AGO,
                tipo_prova=tipo_prova, durata_ore=durata_ore,
                max_ore=durata_ore, max_ore_giorno=durata_ore,
                id_sorvegliante=int(id_sorv) if id_sorv else None,
            )
            db.session.add(g)
            db.session.flush()

            # Collega gli alunni delle classi selezionate, in quella materia
            # (per assegnante, usando famiglie sinonimi per materia)
            mat_can = _materia_canonica(materia)
            classi_up = {cl.strip().upper() for cl in classi_list}
            imports = RecuperoImport.query.filter_by(anno_scol=ANNO_AGO).all()
            for imp in imports:
                if imp.classe.upper() not in classi_up: continue
                if _materia_canonica(imp.materia_norm or '') != mat_can: continue
                exists = RecuperoAlunno.query.filter_by(
                    id_gruppo=g.id, cognome=imp.cognome,
                    nome=imp.nome, classe=imp.classe).first()
                if not exists:
                    db.session.add(RecuperoAlunno(
                        id_gruppo=g.id, classe=imp.classe,
                        cognome=imp.cognome, nome=imp.nome,
                        codice_fisc=imp.codice_fisc, email=imp.email,
                    ))
            db.session.commit()
            flash(f'Gruppo creato: {materia} ({classi}).', 'success')

        elif azione == 'modifica':
            gid = int(request.form['id'])
            g   = RecuperoGruppo.query.get_or_404(gid)
            g.tipo_prova = request.form.get('tipo_prova', g.tipo_prova)
            g.durata_ore = float(request.form.get('durata_ore', g.durata_ore) or g.durata_ore)
            g.max_ore    = g.durata_ore
            id_sorv = request.form.get('id_sorvegliante')
            if id_sorv is not None:
                g.id_sorvegliante = int(id_sorv) if id_sorv else None
            classi_cb = request.form.getlist('classi_cb')
            if classi_cb:
                nuove_classi = ','.join(cl.strip() for cl in classi_cb if cl.strip())
                vecchie_classi_up = {cl.strip().upper() for cl in g.classi.split(',')}
                nuove_classi_up = {cl.strip().upper() for cl in classi_cb}
                g.classi = nuove_classi
                # Rimuovi alunni delle classi tolte dal gruppo
                classi_rimosse = vecchie_classi_up - nuove_classi_up
                if classi_rimosse:
                    for al in list(g.alunni):
                        if al.classe.upper() in classi_rimosse:
                            db.session.delete(al)
                # Aggiungi alunni delle classi nuove
                classi_aggiunte = nuove_classi_up - vecchie_classi_up
                if classi_aggiunte:
                    mat_can = _materia_canonica(g.materia)
                    imports = RecuperoImport.query.filter_by(anno_scol=ANNO_AGO).all()
                    for imp in imports:
                        if imp.classe.upper() not in classi_aggiunte: continue
                        if _materia_canonica(imp.materia_norm or '') != mat_can: continue
                        exists = RecuperoAlunno.query.filter_by(
                            id_gruppo=g.id, cognome=imp.cognome,
                            nome=imp.nome, classe=imp.classe).first()
                        if not exists:
                            db.session.add(RecuperoAlunno(
                                id_gruppo=g.id, classe=imp.classe,
                                cognome=imp.cognome, nome=imp.nome,
                                codice_fisc=imp.codice_fisc, email=imp.email,
                            ))
            db.session.commit()
            flash('Gruppo aggiornato.', 'success')

        elif azione == 'elimina':
            gid = int(request.form['id'])
            g   = RecuperoGruppo.query.get_or_404(gid)
            RecuperoLezione.query.filter_by(id_gruppo=gid).delete()
            RecuperoAlunno.query.filter_by(id_gruppo=gid).delete()
            db.session.delete(g)
            db.session.commit()
            flash('Gruppo eliminato.', 'warning')

        return redirect(url_for('recupero.agosto_gruppi'))

    # ── GET ────────────────────────────────────────────────────────
    imports = RecuperoImport.query.filter_by(anno_scol=ANNO_AGO).all()

    # Garantisce un RecuperoDocente per ogni docente idoneo per contratto
    docenti_idonei = Docente.query.filter(
        Docente.attivo == True,
        Docente.tipo_contratto.in_(CONTRATTI_OK)
    ).order_by(Docente.cognome).all()

    rd_esistenti = {
        rd.id_docente: rd for rd in
        RecuperoDocente.query.filter_by(anno_scol=ANNO_AGO).all()
    }
    for d in docenti_idonei:
        if d.id not in rd_esistenti:
            nuovo_rd = RecuperoDocente(id_docente=d.id, anno_scol=ANNO_AGO)
            db.session.add(nuovo_rd)
            rd_esistenti[d.id] = nuovo_rd
    db.session.commit()

    # Esclude chi è assente per TUTTO il periodo prove (stessa logica di
    # agosto_docenti_disponibili): chi ha solo alcune assenze resta
    # selezionabile, ma chi non è mai libero non deve comparire affatto.
    from models.recupero import RecuperoPeriodo
    from models.assenza import Assenza
    from datetime import timedelta as _timedelta

    periodo_disp = RecuperoPeriodo.query.filter_by(
        anno_scol=ANNO_AGO, codice=PERIODO_AGO).first()
    date_periodo_disp = []
    if periodo_disp:
        cur = periodo_disp.data_inizio
        while cur <= periodo_disp.data_fine:
            if cur.weekday() < 5:
                date_periodo_disp.append(cur)
            cur += _timedelta(days=1)

    id_completamente_assenti = set()
    if date_periodo_disp:
        for rd in rd_esistenti.values():
            assenze_doc = Assenza.query.filter(
                Assenza.id_docente == rd.docente.id,
                Assenza.data >= date_periodo_disp[0],
                Assenza.data <= date_periodo_disp[-1],
            ).all()
            giorni_assente = {a.data for a in assenze_doc}
            if giorni_assente and all(d in giorni_assente for d in date_periodo_disp):
                id_completamente_assenti.add(rd.docente.id)

    disponibili = sorted(
        (rd for rd in rd_esistenti.values() if rd.docente.id not in id_completamente_assenti),
        key=lambda rd: rd.docente.cognome
    )

    # Conteggio sorveglianze e titolarità già assegnate per agosto, per
    # favorire una distribuzione equa tra i docenti disponibili.
    gruppi_per_conteggio = (RecuperoGruppo.query
                            .join(RecuperoDocente)
                            .filter(RecuperoDocente.anno_scol == ANNO_AGO,
                                    RecuperoGruppo.periodo_codice == PERIODO_AGO)
                            .all())
    n_impegni_docente = defaultdict(int)
    for g in gruppi_per_conteggio:
        if g.id_sorvegliante:
            n_impegni_docente[g.id_sorvegliante] += 1
        if g.docente_rec and g.docente_rec.docente:
            n_impegni_docente[g.docente_rec.docente.id] += 1

    def trova_disponibile(cognome_doc, nome_ini=''):
        cogn = cognome_doc.upper()
        ini  = nome_ini.upper()
        if ini:
            for rd in disponibili:
                if rd.docente.cognome.upper() == cogn and (rd.docente.nome or '').strip().upper()[:1] == ini:
                    return rd
        trovati = [rd for rd in disponibili if rd.docente.cognome.upper() == cogn]
        if len(trovati) == 1:
            return trovati[0]
        return None

    def trova_disponibile_per_id_docente(id_docente, lista_disponibili):
        """Trova il RecuperoDocente a partire dall'id reale del docente (Docente.id)."""
        for rd in lista_disponibili:
            if rd.docente.id == id_docente:
                return rd
        return None

    # Per ogni docente assegnante (titolare potenziale), elenco delle materie,
    # classi e ALUNNI con debito in quella materia
    per_doc_materia = defaultdict(lambda: {'classi': set(), 'materia_raw': '', 'alunni': []})
    for imp in imports:
        key = (imp.cognome_docente, imp.nome_ini_docente, _materia_canonica(imp.materia_norm or ''))
        per_doc_materia[key]['classi'].add(imp.classe)
        per_doc_materia[key]['materia_raw'] = imp.materia_norm or imp.materia_raw
        per_doc_materia[key]['alunni'].append(imp)

    # Gruppi gia' creati per agosto (per materia+docente, per individuare
    # le classi gia' coperte ed evitare di riproporle come libere)
    gruppi_esistenti = (RecuperoGruppo.query
                        .join(RecuperoDocente)
                        .filter(RecuperoDocente.anno_scol == ANNO_AGO,
                                RecuperoGruppo.periodo_codice == PERIODO_AGO)
                        .all())

    # Copertura PER SOLA MATERIA — una classe coperta da un gruppo qualsiasi
    # (indipendentemente da chi ne è il titolare) non deve più comparire
    # come "libera" in nessuna proposta di quella materia.
    classi_coperte_solo_materia = defaultdict(set)  # materia_can -> classi già in un gruppo
    for g in gruppi_esistenti:
        classi_coperte_solo_materia[_materia_canonica(g.materia)] |= \
            {cl.strip().upper() for cl in g.classi.split(',')}

    proposte_list = []
    for (cogn_doc, ini_doc, mat_can), dati in sorted(per_doc_materia.items()):
        rd_sug = trova_disponibile(cogn_doc, ini_doc)
        classi_tutte = sorted(dati['classi'])
        classi_gia_coperte = classi_coperte_solo_materia.get(mat_can, set())
        classi_libere = [cl for cl in classi_tutte if cl.upper() not in classi_gia_coperte]

        n_alunni_totale = len(dati['alunni'])
        n_alunni_libere = sum(1 for a in dati['alunni'] if a.classe.upper() not in classi_gia_coperte)

        proposte_list.append({
            'materia':        mat_can,
            'materia_raw':    dati['materia_raw'],
            'cognome_doc':    cogn_doc,
            'nome_ini_doc':   ini_doc,
            'rd_suggerito':   rd_sug,
            'classi_tutte':   classi_tutte,
            'classi_libere':  classi_libere,
            'n_classi_coperte': len(classi_gia_coperte),
            'n_alunni_totale':  n_alunni_totale,
            'n_alunni_libere':  n_alunni_libere,
        })

    # Classi disponibili PER MATERIA, indipendentemente da chi e' l'assegnante
    # del debito — usata sia per il gruppo libero (opzione B) sia per
    # ricalcolare le classi disponibili quando si modifica un gruppo
    # esistente il cui titolare non coincide con l'assegnante originale.
    classi_per_materia_tutte = defaultdict(set)
    for imp in imports:
        classi_per_materia_tutte[_materia_canonica(imp.materia_norm or '')].add(imp.classe)

    # Elenco materie (per il select del gruppo libero): solo quelle con
    # almeno una classe ancora libera (non già completamente coperta da
    # un gruppo, qualsiasi titolare).
    materie_disponibili = sorted(
        mat for mat, classi in classi_per_materia_tutte.items()
        if (classi - {c.upper() for c in classi_coperte_solo_materia.get(mat, set())})
    )

    # Mappa ITP -> titolare abbinato, letta dal dato strutturale sul
    # docente (Docente.id_titolare_riferimento, impostato in /docenti
    # insieme al resto della cattedra) — più la vecchia tabella
    # CoppiaDocenteItp per compatibilità con abbinamenti inseriti prima
    # che il campo fosse disponibile sull'anagrafica. I debiti assegnati
    # dall'ITP confluiscono nel conteggio del titolare: es. Informatica:
    # Landi (titolare) + Luzzi (ITP) -> sommati sotto Landi.
    from models.docente import CoppiaDocenteItp
    itp_to_titolare = {
        d.id: d.id_titolare_riferimento
        for d in Docente.query.filter(
            Docente.ruolo == 'itp',
            Docente.id_titolare_riferimento.isnot(None)).all()
    }
    coppie_attive = CoppiaDocenteItp.query.filter_by(attiva=True).all()
    for c_ in coppie_attive:
        itp_to_titolare.setdefault(c_.id_itp, c_.id_titolare)

    # Identifica il docente reale (per cognome+iniziale) su TUTTI i docenti,
    # non solo i disponibili — serve per riconoscere l'ITP anche quando non
    # ha contratto idoneo (es. TD_GS in scadenza), cosa che capita spesso
    # per gli ITP. Solo dopo aver dedotto il titolare abbinato si applica
    # il filtro di disponibilità per contratto.
    def trova_docente_per_cognome(cognome_doc, nome_ini=''):
        cogn = cognome_doc.upper()
        ini  = nome_ini.upper()
        candidati = Docente.query.filter(Docente.cognome.ilike(cogn)).all()
        if ini:
            for d in candidati:
                if (d.nome or '').strip().upper()[:1] == ini:
                    return d
        return candidati[0] if len(candidati) == 1 else None

    # Per ogni materia: elenco docenti (titolari) che hanno assegnato debiti
    # in quella materia, sommando anche i debiti del loro ITP abbinato.
    # Ordinati per numero di alunni decrescente. Usato nel select "Docente
    # titolare" del gruppo libero, filtrato via JS in base alla materia scelta.
    accumulo = defaultdict(lambda: {'alunni': [], 'rd': None})  # (mat_can, id_docente_titolare) -> dati
    for (cogn_doc, ini_doc, mat_can), dati in per_doc_materia.items():
        doc_reale = trova_docente_per_cognome(cogn_doc, ini_doc)

        # Se questo docente è l'ITP di un titolare con coppia attiva, i suoi
        # alunni confluiscono sotto il titolare — anche se l'ITP stesso non
        # è più disponibile per contratto (es. TD_GS scaduto): i suoi debiti
        # contano comunque per il titolare.
        id_titolare_abbinato = itp_to_titolare.get(doc_reale.id) if doc_reale else None
        if id_titolare_abbinato:
            rd_titolare = trova_disponibile_per_id_docente(id_titolare_abbinato, disponibili)
            if rd_titolare:
                key = (mat_can, rd_titolare.id)
                accumulo[key]['rd'] = rd_titolare
                accumulo[key]['alunni'].extend(dati['alunni'])
            continue  # l'ITP non genera mai una riga propria, anche se il
                       # titolare abbinato non risultasse disponibile

        rd_sug = trova_disponibile(cogn_doc, ini_doc)
        if not rd_sug:
            continue  # docente non tra i disponibili per contratto: non proponibile

        key = (mat_can, rd_sug.id)
        accumulo[key]['rd'] = rd_sug
        accumulo[key]['alunni'].extend(dati['alunni'])

    docenti_per_materia = defaultdict(list)
    for (mat_can, id_rec_docente), dati in accumulo.items():
        rd = dati['rd']
        n_classi = len({a.classe for a in dati['alunni']})
        docenti_per_materia[mat_can].append({
            'id_rec_docente': rd.id,
            'label': f"{rd.docente.cognome} {(rd.docente.nome or '')[:1]}.",
            'n_alunni': len(dati['alunni']),
            'n_classi': n_classi,
            'con_debito': True,
        })

    # Aggiunge anche i docenti DISPONIBILI (contratto ok, non assenti) che
    # insegnano la materia secondo l'orario reale (OrarioDocente), ma a cui
    # nello staging non risulta nessun debito assegnato — es. un docente
    # abilitato sia su Matematica sia su Fisica i cui alunni quest'anno
    # non hanno avuto insufficienze in una delle due. Senza questa aggiunta
    # tali docenti non comparirebbero mai nel select del titolare, pur
    # essendo perfettamente idonei a tenere la prova.
    from models.orario_docente import OrarioDocente as _OrarioDocenteEarly

    id_gia_presenti_per_materia = {
        mat_can: {d['id_rec_docente'] for d in lista}
        for mat_can, lista in docenti_per_materia.items()
    }
    materie_con_proposte = set(docenti_per_materia.keys()) | set(materie_disponibili)
    rd_per_id_docente = {rd.docente.id: rd for rd in disponibili}
    for o in _OrarioDocenteEarly.query.filter(
            _OrarioDocenteEarly.id_docente.in_(rd_per_id_docente.keys())).all():
        if not o.materia:
            continue
        mat_can = _materia_canonica(o.materia)
        if mat_can not in materie_con_proposte:
            continue  # materia senza nessun debito/proposta: non interessa qui
        rd = rd_per_id_docente.get(o.id_docente)
        if not rd:
            continue
        gia_presenti = id_gia_presenti_per_materia.setdefault(mat_can, set())
        if rd.id in gia_presenti:
            continue  # già proposto come "con debito": non duplicare
        gia_presenti.add(rd.id)
        docenti_per_materia[mat_can].append({
            'id_rec_docente': rd.id,
            'label': f"{rd.docente.cognome} {(rd.docente.nome or '')[:1]}.",
            'n_alunni': 0,
            'n_classi': 0,
            'con_debito': False,
        })

    for mat_can in docenti_per_materia:
        # Con debito prima (più alunni prima), poi i disponibili senza
        # debito in ordine alfabetico — cosi' chi ha già un'insufficienza
        # da coprire resta in cima, ma chi e' idoneo per materia/classe di
        # concorso compare comunque, subito sotto.
        docenti_per_materia[mat_can].sort(
            key=lambda d: (not d['con_debito'], -d['n_alunni'], d['label']))
    docenti_per_materia_json = dict(docenti_per_materia)

    # Gruppi esistenti: classi disponibili per la materia di quel gruppo,
    # cosi' anche un gruppo creato con titolare "esterno" (opzione B) puo'
    # essere ampliato con qualsiasi classe di quella materia.
    classi_per_gruppo = {}
    for g in gruppi_esistenti:
        mat_can = _materia_canonica(g.materia)
        tutte = classi_per_materia_tutte.get(mat_can, set())
        classi_proprie = {cl.strip().upper() for cl in g.classi.split(',')}
        classi_per_gruppo[g.id] = sorted(tutte | classi_proprie) if tutte else g.classi.split(',')

    # Classi in cui insegna ciascun docente disponibile (per l'etichetta sorvegliante)
    from models.orario_docente import OrarioDocente
    classi_per_docente = defaultdict(set)
    for o in OrarioDocente.query.filter(
            OrarioDocente.id_docente.in_([rd.docente.id for rd in disponibili])).all():
        if o.classe:
            classi_per_docente[o.id_docente].add(o.classe)

    # Converte i set in liste ordinate per la serializzazione JSON nel template
    # (riusa classi_coperte_solo_materia, calcolata sopra: copertura per sola
    # materia, qualsiasi titolare — stessa logica usata per le Proposte)
    classi_per_materia_tutte_json = {k: sorted(v) for k, v in classi_per_materia_tutte.items()}
    classi_coperte_per_materia_json = {k: sorted(v) for k, v in classi_coperte_solo_materia.items()}

    n_impegni_docente_json = dict(n_impegni_docente)

    return render_template('recupero/agosto_gruppi.html',
        proposte=proposte_list,
        gruppi=gruppi_esistenti,
        disponibili=disponibili,
        classi_per_gruppo=classi_per_gruppo,
        classi_per_docente=classi_per_docente,
        materie_disponibili=materie_disponibili,
        classi_per_materia_tutte=classi_per_materia_tutte_json,
        classi_coperte_per_materia=classi_coperte_per_materia_json,
        docenti_per_materia=docenti_per_materia_json,
        n_impegni_docente=n_impegni_docente_json,
        TIPO_PROVA_LABEL=TIPO_PROVA_LABEL,
        anno=ANNO_AGO)


@recupero_bp.route('/recupero/agosto/calendario', methods=['GET', 'POST'])
def agosto_calendario():
    from models.recupero import RecuperoPeriodo
    from datetime import timedelta
    from collections import defaultdict

    periodo = RecuperoPeriodo.query.filter_by(
        anno_scol=ANNO_AGO, codice=PERIODO_AGO).first()

    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione == 'aggiungi':
            id_gruppo  = int(request.form['id_gruppo'])
            data_str   = request.form.get('data', '')
            ora_inizio = request.form.get('ora_inizio', '08:00')
            ora_fine   = request.form.get('ora_fine', '10:00')
            aula       = request.form.get('aula', '').strip() or None

            g = RecuperoGruppo.query.get_or_404(id_gruppo)
            data_d = date.fromisoformat(data_str)

            def _t(s):
                try: h,m = map(int,s.split(':')); return h*60+m
                except: return 0

            ini_m, fin_m = _t(ora_inizio), _t(ora_fine)

            # Controllo conflitti alunni e docenti
            tutti_ag = RecuperoGruppo.query.join(RecuperoDocente).filter(
                RecuperoDocente.anno_scol==ANNO_AGO,
                RecuperoGruppo.periodo_codice==PERIODO_AGO).all()

            errori = []
            for ag in tutti_ag:
                if ag.id == id_gruppo: continue
                ll_ag = RecuperoLezione.query.filter_by(id_gruppo=ag.id, data=data_d).all()
                for ll in ll_ag:
                    sovrappone = _t(ll.ora_inizio) < fin_m and _t(ll.ora_fine) > ini_m
                    if not sovrappone: continue
                    # Conflitto alunni
                    al1={(a.cognome,a.nome,a.classe) for a in g.alunni}
                    al2={(a.cognome,a.nome,a.classe) for a in ag.alunni}
                    comuni=al1&al2
                    if comuni:
                        nomi=', '.join(f'{a[0]}' for a in list(comuni)[:3])
                        errori.append(f'👨‍🎓 Alunni in conflitto con {ag.materia[:15]}: {nomi}')
                    # Conflitto docenti: somministratore (titolare) e assistente (sorvegliante).
                    # Usa l'id reale del Docente (g.docente.id), non id_rec_docente
                    # (che è l'id di RecuperoDocente — spazio di id diverso).
                    doc_ids_g  = set(filter(None, [
                        g.docente.id if g.docente else None, g.id_sorvegliante]))
                    doc_ids_ag = set(filter(None, [
                        ag.docente.id if ag.docente else None, ag.id_sorvegliante]))
                    comuni_doc = doc_ids_g & doc_ids_ag
                    for did in comuni_doc:
                        from models import Docente as _D
                        d = _D.query.get(did)
                        errori.append(f'👨‍🏫 {d.cognome if d else "?"} già impegnato in {ag.materia[:15]}')

            if errori:
                flash('⚠ NON salvato — ' + ' | '.join(errori[:3]), 'danger')
                return redirect(url_for('recupero.agosto_calendario'))

            db.session.add(RecuperoLezione(
                id_gruppo=id_gruppo, data=data_d,
                ora_inizio=ora_inizio, ora_fine=ora_fine, aula=aula,
            ))
            db.session.commit()
            flash('Prova aggiunta.', 'success')

        elif azione == 'modifica':
            lid = int(request.form['id'])
            l   = RecuperoLezione.query.get_or_404(lid)
            nuova_data = date.fromisoformat(request.form['data'])
            nuova_ini  = request.form.get('ora_inizio', l.ora_inizio)
            nuova_fin  = request.form.get('ora_fine',   l.ora_fine)
            l.data       = nuova_data
            l.ora_inizio = nuova_ini
            l.ora_fine   = nuova_fin
            l.aula       = request.form.get('aula','').strip() or None
            db.session.commit()
            flash('Prova aggiornata.', 'success')

        elif azione == 'elimina':
            lid = int(request.form['id'])
            l = RecuperoLezione.query.get_or_404(lid)
            db.session.delete(l)
            db.session.commit()

        elif azione == 'elimina_giorno':
            from datetime import date as _date
            data_str = request.form.get('data','')
            if data_str:
                data_d = _date.fromisoformat(data_str)
                ids_g = [g.id for g in RecuperoGruppo.query.join(RecuperoDocente)
                    .filter(RecuperoDocente.anno_scol==ANNO_AGO,
                            RecuperoGruppo.periodo_codice==PERIODO_AGO).all()]
                n = RecuperoLezione.query.filter(
                    RecuperoLezione.id_gruppo.in_(ids_g),
                    RecuperoLezione.data==data_d
                ).delete(synchronize_session=False)
                db.session.commit()
                flash(f'Eliminate {n} prove del {data_d.strftime("%d/%m/%Y")}.', 'warning')

        elif azione == 'elimina_tutto':
            ids_g = [g.id for g in RecuperoGruppo.query.join(RecuperoDocente)
                .filter(RecuperoDocente.anno_scol==ANNO_AGO,
                        RecuperoGruppo.periodo_codice==PERIODO_AGO).all()]
            n = RecuperoLezione.query.filter(
                RecuperoLezione.id_gruppo.in_(ids_g)
            ).delete(synchronize_session=False)
            db.session.commit()
            flash(f'Calendario azzerato: {n} prove eliminate.', 'warning')

        elif azione == 'genera_bozza':
            if request.form.get('conferma_elimina') != '1':
                flash('Seleziona la casella di conferma.', 'warning')
                return redirect(url_for('recupero.agosto_calendario'))
            _genera_bozza_agosto()
            flash('Bozza prove agosto generata.', 'success')

        elif azione == 'completa_bozza':
            n_prima = RecuperoLezione.query.join(RecuperoGruppo).join(RecuperoDocente).filter(
                RecuperoDocente.anno_scol == ANNO_AGO,
                RecuperoGruppo.periodo_codice == PERIODO_AGO).count()
            _genera_bozza_agosto(solo_incompleti=True)
            n_dopo = RecuperoLezione.query.join(RecuperoGruppo).join(RecuperoDocente).filter(
                RecuperoDocente.anno_scol == ANNO_AGO,
                RecuperoGruppo.periodo_codice == PERIODO_AGO).count()
            if n_dopo > n_prima:
                flash(f'Bozza completata: aggiunte {n_dopo - n_prima} prove ai gruppi che ne erano privi. '
                      'Le prove già pianificate non sono state toccate.', 'success')
            else:
                flash('Tutti i gruppi hanno già almeno una prova pianificata.', 'info')

        return redirect(url_for('recupero.agosto_calendario'))

    # Date disponibili
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

    # Calcolo conflitti agosto (docente + alunni)
    def _t_ago(s):
        try: h,m = map(int,s.split(':')); return h*60+m
        except: return 0

    conflitti_ago = []
    for data, coppie in lezioni_per_data.items():
        # Conflitto docente: somministratore (titolare) e assistente
        # (sorvegliante). Usa l'id reale del Docente (g.docente.id), non
        # id_rec_docente (id di RecuperoDocente — spazio di id diverso).
        doc_ll = {}
        for l,g in coppie:
            id_titolare_reale = g.docente.id if g.docente else None
            for doc_id in filter(None, [id_titolare_reale, g.id_sorvegliante]):
                doc_ll.setdefault(doc_id, []).append((l,g))
        for doc_id, ll in doc_ll.items():
            for i in range(len(ll)):
                for j in range(i+1, len(ll)):
                    l1,g1=ll[i]; l2,g2=ll[j]
                    if g1.id==g2.id: continue
                    if _t_ago(l1.ora_inizio)<_t_ago(l2.ora_fine) and _t_ago(l2.ora_inizio)<_t_ago(l1.ora_fine):
                        from models import Docente as _D
                        doc = _D.query.get(doc_id)
                        conflitti_ago.append({
                            'tipo':'docente','data':data,
                            'msg':f'{doc.cognome if doc else "?"} impegnato in due prove: '
                                  f'{g1.materia[:15]} {l1.ora_inizio}-{l1.ora_fine} / '
                                  f'{g2.materia[:15]} {l2.ora_inizio}-{l2.ora_fine}',
                            'ids':[l1.id,l2.id]})
        # Conflitto alunni
        for i in range(len(coppie)):
            for j in range(i+1, len(coppie)):
                l1,g1=coppie[i]; l2,g2=coppie[j]
                if g1.id==g2.id: continue
                if not (_t_ago(l1.ora_inizio)<_t_ago(l2.ora_fine) and _t_ago(l2.ora_inizio)<_t_ago(l1.ora_fine)): continue
                al1={(a.cognome,a.nome,a.classe) for a in g1.alunni}
                al2={(a.cognome,a.nome,a.classe) for a in g2.alunni}
                comuni=al1&al2
                if comuni:
                    nomi=', '.join(f'{a[0]} {a[1]}' for a in list(comuni)[:2])
                    conflitti_ago.append({
                        'tipo':'alunno','data':data,
                        'msg':f'{nomi}: {g1.materia[:12]} {l1.ora_inizio}-{l1.ora_fine} / {g2.materia[:12]} {l2.ora_inizio}-{l2.ora_fine}',
                        'ids':[l1.id,l2.id]})

    conflitti_ids_ago = {lid for cf in conflitti_ago for lid in cf['ids']}

    # Docenti validi come assistente (sorvegliante): contratto idoneo
    docenti_validi = Docente.query.filter(
        Docente.attivo == True,
        Docente.tipo_contratto.in_(CONTRATTI_OK)
    ).order_by(Docente.cognome).all()

    # Conteggio impegni (somministratore + assistente) per favorire una
    # distribuzione equa quando si assegna l'assistente manualmente.
    n_impegni_doc = defaultdict(int)
    for g in gruppi:
        if g.id_sorvegliante:
            n_impegni_doc[g.id_sorvegliante] += 1
        if g.docente:
            n_impegni_doc[g.docente.id] += 1

    return render_template('recupero/agosto_calendario.html',
        periodo=periodo, gruppi=gruppi,
        date_disponibili=date_disp,
        lezioni_per_data=lezioni_per_data,
        docenti_validi=docenti_validi,
        n_impegni_docente=dict(n_impegni_doc),
        TIPO_PROVA_LABEL=TIPO_PROVA_LABEL,
        conflitti=conflitti_ago,
        conflitti_ids=conflitti_ids_ago)


def _genera_bozza_agosto(solo_incompleti=False):
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
    from datetime import timedelta
    from collections import defaultdict
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

    def _t(s):
        try: h, m = map(int, s.split(':')); return h * 60 + m
        except Exception: return 0

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


@recupero_bp.route('/recupero/agosto/assistente', methods=['POST'])
def agosto_set_assistente():
    """Aggiorna il docente assistente (sorvegliante) di un gruppo agosto."""
    id_gruppo = int(request.form['id_gruppo'])
    g = RecuperoGruppo.query.get_or_404(id_gruppo)
    if 'id_sorvegliante' in request.form:
        id_sorv = request.form.get('id_sorvegliante') or None
        g.id_sorvegliante = int(id_sorv) if id_sorv else None
    db.session.commit()
    return redirect(url_for('recupero.agosto_calendario'))


# ── COPERTURA AGOSTO ──────────────────────────────────────────────────
@recupero_bp.route('/recupero/agosto/copertura')
def agosto_copertura():
    """
    Reindirizza alla vista unificata: /recupero/copertura mostra già sia
    lo stato giugno sia lo stato agosto per ogni alunno+materia, con la
    logica corretta (ad agosto la prova e' sempre rilevante, anche per
    chi non ha aderito al corso o ha scelto studio individuale).
    """
    return redirect(url_for('recupero.copertura'))
