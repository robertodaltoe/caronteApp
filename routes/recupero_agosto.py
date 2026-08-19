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

# Re-export per compatibilità: la funzione vive ora in
# modules/recupero_agosto_calendario.py (spostata per consolidare la
# business logic fuori dalla route, era una funzione di 295 righe usata
# solo qui), ma i test esistenti la importano da questo modulo.
from modules.recupero_agosto_calendario import genera_bozza_agosto as _genera_bozza_agosto


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

    # Vedi routes/recupero_costanti.py::docenti_idonei_periodo() — prima
    # mancava il filtro sull'anno di servizio, comparivano anche docenti
    # non ancora in servizio o con contratto scaduto (Sessione 62).
    from routes.recupero_costanti import docenti_idonei_periodo
    docenti_validi = docenti_idonei_periodo(ANNO_AGO)

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
    # e in servizio nell'anno delle prove — vedi routes/recupero_costanti.py
    # ::docenti_idonei_periodo() (Sessione 62: creava una riga anche per
    # chi non è ancora in servizio o ha contratto scaduto).
    from routes.recupero_costanti import docenti_idonei_periodo
    docenti_idonei = docenti_idonei_periodo(ANNO_AGO)

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
    from modules.recupero_agosto_calendario import (
        azione_aggiungi, azione_modifica, azione_elimina,
        azione_elimina_giorno, azione_elimina_tutto,
        azione_genera_bozza, azione_completa_bozza,
        costruisci_dati_agosto,
    )

    if request.method == 'POST':
        azione = request.form.get('azione')
        handlers = {
            'aggiungi':        lambda: azione_aggiungi(request.form),
            'modifica':        lambda: azione_modifica(request.form),
            'elimina':         lambda: azione_elimina(request.form),
            'elimina_giorno':  lambda: azione_elimina_giorno(request.form),
            'elimina_tutto':   lambda: azione_elimina_tutto(),
            'genera_bozza':    lambda: azione_genera_bozza(request.form),
            'completa_bozza':  lambda: azione_completa_bozza(),
        }
        handler = handlers.get(azione)
        if handler:
            risultato = handler()
            if risultato['msg']:
                flash(risultato['msg'], risultato['cat'])
        return redirect(url_for('recupero.agosto_calendario'))

    # Tutto il calcolo (date disponibili, conflitti, docenti validi) è in
    # modules/recupero_agosto_calendario.py: la route si limita a
    # chiamarlo e a passare il risultato al template.
    dati = costruisci_dati_agosto()
    return render_template('recupero/agosto_calendario.html', **dati)



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
