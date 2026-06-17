from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from models import db
from models.recupero import RecuperoDocente, RecuperoGruppo, RecuperoLezione, RecuperoAlunno, RecuperoVincolo
from models.docente import Docente
from models.materia import Materia, DocenteMateria
from datetime import date, timedelta

recupero_bp = Blueprint('recupero', __name__)

ANNO = '2025-2026'
DATA_INIZIO = date(2026, 6, 15)
DATA_FINE   = date(2026, 7, 4)


# ── INDICE ────────────────────────────────────────────────────────────
@recupero_bp.route('/recupero')
def index():
    docenti_disp = (RecuperoDocente.query
                    .filter_by(anno_scol=ANNO)
                    .join(Docente)
                    .order_by(Docente.cognome)
                    .all())
    gruppi = (RecuperoGruppo.query
              .join(RecuperoDocente)
              .filter(RecuperoDocente.anno_scol == ANNO)
              .order_by(RecuperoGruppo.materia)
              .all())
    # Statistiche
    tot_ore = sum(g.ore_pianificate for g in gruppi)
    tot_alunni = sum(g.n_alunni or 0 for g in gruppi)

    return render_template('recupero/index.html',
        docenti_disp=docenti_disp,
        gruppi=gruppi,
        tot_ore=tot_ore,
        tot_alunni=tot_alunni,
        anno=ANNO,
    )


# ── DOCENTI DISPONIBILI ───────────────────────────────────────────────
@recupero_bp.route('/recupero/docenti', methods=['GET', 'POST'])
def docenti():
    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione == 'aggiungi':
            id_doc = int(request.form['id_docente'])
            note   = request.form.get('note', '').strip() or None
            exists = RecuperoDocente.query.filter_by(
                id_docente=id_doc, anno_scol=ANNO).first()
            materie_extra = request.form.get('materie_extra','').strip() or None
            if not exists:
                db.session.add(RecuperoDocente(
                    id_docente=id_doc, anno_scol=ANNO, note=note,
                    materie_extra=materie_extra))
                db.session.commit()
                d = Docente.query.get(id_doc)
                flash(f'{d.cognome} aggiunto ai disponibili.', 'success')
            else:
                flash('Docente già presente.', 'warning')

        elif azione == 'modifica_docente':
            rid = int(request.form['id'])
            rd  = RecuperoDocente.query.get_or_404(rid)
            rd.note          = request.form.get('note','').strip() or None
            rd.materie_extra = request.form.get('materie_extra','').strip() or None
            db.session.commit()
            flash('Aggiornato.', 'success')

        elif azione == 'rimuovi':
            rid = int(request.form['id'])
            rd  = RecuperoDocente.query.get_or_404(rid)
            db.session.delete(rd)
            db.session.commit()
            flash('Docente rimosso.', 'warning')

        return redirect(url_for('recupero.docenti'))

    disponibili = (RecuperoDocente.query.filter_by(anno_scol=ANNO)
                   .join(Docente).order_by(Docente.cognome).all())
    disp_ids = {rd.id_docente for rd in disponibili}
    tutti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    non_ancora = [d for d in tutti if d.id not in disp_ids]

    return render_template('recupero/docenti.html',
        disponibili=disponibili,
        non_ancora=non_ancora,
        anno=ANNO,
    )


# ── GRUPPI ────────────────────────────────────────────────────────────
@recupero_bp.route('/recupero/gruppi', methods=['GET', 'POST'])
def gruppi():
    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione == 'aggiungi':
            id_recdoc      = int(request.form['id_rec_docente'])
            materia        = request.form.get('materia', '').strip()
            note           = request.form.get('note', '').strip() or None
            max_ore        = int(request.form.get('max_ore', '10') or 10)
            max_ore_giorno = int(request.form.get('max_ore_giorno', '2') or 2)
            # Classi da checkbox o testo libero
            classi_list = request.form.getlist('classi_cb')
            classi = ','.join(cl.strip() for cl in classi_list if cl.strip()) if classi_list else request.form.get('classi','').strip()
            db.session.add(RecuperoGruppo(
                id_rec_docente=id_recdoc, materia=materia,
                classi=classi, max_ore=max_ore,
                max_ore_giorno=max_ore_giorno, note=note,
            ))
            db.session.commit()
            flash('Gruppo aggiunto.', 'success')

        elif azione == 'modifica':
            gid = int(request.form['id'])
            g   = RecuperoGruppo.query.get_or_404(gid)
            g.materia        = request.form.get('materia','').strip() or g.materia
            g.id_rec_docente = int(request.form['id_rec_docente'])
            g.max_ore        = int(request.form.get('max_ore', g.max_ore or 10) or 10)
            g.max_ore_giorno = int(request.form.get('max_ore_giorno', g.max_ore_giorno or 2) or 2)
            g.note           = request.form.get('note','').strip() or None
            # Classi: da checkbox (classi_cb) o testo libero (classi)
            classi_cb = request.form.getlist('classi_cb')
            if classi_cb:
                # Checkbox presenti: usa quelli (anche se la lista è vuota = nessuna classe)
                g.classi = ','.join(cl.strip() for cl in classi_cb if cl.strip())
            else:
                # Fallback testo libero
                classi_txt = request.form.get('classi','').strip()
                if classi_txt:
                    g.classi = classi_txt
                # Se entrambi vuoti: mantieni le classi esistenti
            db.session.commit()
            flash('Gruppo aggiornato.', 'success')

        elif azione == 'elimina':
            gid = int(request.form['id'])
            g   = RecuperoGruppo.query.get_or_404(gid)
            db.session.delete(g)
            db.session.commit()
            flash('Gruppo eliminato.', 'warning')

        elif azione == 'crea_da_proposta':
            from models.recupero import RecuperoImport
            materia     = request.form.get('materia','').strip()
            cognome_doc = request.form.get('cognome_doc','').strip()
            classi_list = request.form.getlist('classi_cb')
            classi      = ','.join(classi_list) if classi_list else request.form.get('classi','').strip()
            id_recdoc   = int(request.form['id_rec_docente'])
            max_ore     = int(request.form.get('max_ore', 10) or 10)
            max_ore_g   = int(request.form.get('max_ore_giorno', 2) or 2)
            g = RecuperoGruppo(
                id_rec_docente=id_recdoc, materia=materia,
                classi=classi, max_ore=max_ore, max_ore_giorno=max_ore_g,
            )
            db.session.add(g); db.session.flush()
            # Collega alunni dal staging
            imports = RecuperoImport.query.filter_by(
                anno_scol=ANNO, materia_norm=materia,
                cognome_docente=cognome_doc).all()
            for imp in imports:
                if imp.classe.upper() in [cl.strip().upper() for cl in classi_list]:
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

        return redirect(url_for('recupero.gruppi'))

    # GET ─────────────────────────────────────────────────────────────
    from models.recupero import RecuperoImport
    from collections import defaultdict

    disponibili = (RecuperoDocente.query.filter_by(anno_scol=ANNO)
                   .join(Docente).order_by(Docente.cognome).all())
    gruppi_list = (RecuperoGruppo.query
                   .join(RecuperoDocente)
                   .join(Docente, Docente.id == RecuperoDocente.id_docente)
                   .filter(RecuperoDocente.anno_scol == ANNO,
                           RecuperoGruppo.periodo_codice == 'corsi_giugno')
                   .order_by(RecuperoGruppo.materia)
                   .all())

    # Famiglie di sinonimi — solo quelli confermati, nessuna inferenza per somiglianza
    # Ogni famiglia è un insieme: se due materie appartengono alla stessa famiglia, matchano.
    _FAMIGLIE = [
        # Latino
        {'LATINO', 'LINGUA LATINA', 'LINGUA E CULTURA LATINA'},
        # Italiano
        {'ITALIANO', 'LINGUA E LETTERATURA ITALIANA', 'LINGUA E CULTURA ITALIANA'},
        # Matematica
        {'MATEMATICA', 'MATEMATICA CON INFORMATICA', 'MATEMATICA E COMPLEMENTI DI MATEMATICA'},
        # Storia
        {'STORIA', 'STORIA E GEOGRAFIA'},
        # Fisica
        {'FISICA', 'SCIENZE INTEGRATE (FISICA)'},
        # Inglese
        {'INGLESE', 'LINGUA INGLESE', 'LINGUA E CULTURA STRANIERA (INGLESE)'},
        # Tedesco (solo esatta, nessun alias noto)
        {'TEDESCO', 'LINGUA TEDESCA', 'LINGUA E CULTURA STRANIERA TEDESCO'},
        # Le altre materie (topografia, filosofia, economia, scienze naturali, informatica, ecc.)
        # NON hanno alias — vengono confrontate solo per corrispondenza esatta o sottostringa.
    ]

    def _match_sinonimi(m1, m2):
        m1u = m1.strip().upper()
        m2u = m2.strip().upper()
        if m1u == m2u:
            return True
        # Match solo se ENTRAMBE le materie sono membri esatti della stessa famiglia
        # Nessuna inferenza per sottostringa — evita MATEMATICA vs INFORMATICA
        for famiglia in _FAMIGLIE:
            f = {x.upper() for x in famiglia}
            if m1u in f and m2u in f:
                return True
        return False

    # Proposte dai dati importati
    imports = RecuperoImport.query.filter_by(anno_scol=ANNO).all()
    per_proposta = defaultdict(lambda: {'classi':set(),'alunni':[],'docente_raw':'',
                                        'cognome_doc':'','n_non_risposto':0,'n_non_aderisce':0})
    for imp in imports:
        key = (imp.materia_norm, imp.cognome_docente)
        per_proposta[key]['classi'].add(imp.classe)
        per_proposta[key]['alunni'].append(imp)
        per_proposta[key]['docente_raw'] = imp.docente_raw
        per_proposta[key]['cognome_doc'] = imp.cognome_docente
        if imp.stato_adesione == 'non_risposto': per_proposta[key]['n_non_risposto'] += 1
        elif imp.stato_adesione == 'non_aderisce': per_proposta[key]['n_non_aderisce'] += 1

    def trova_rd(cognome_doc, nome_ini=''):
        cogn = cognome_doc.upper()
        ini  = nome_ini.upper()
        if ini:
            for rd in disponibili:
                rc = rd.docente.cognome.upper()
                rn_ini = (rd.docente.nome or '').strip().upper()[:1]
                if rc == cogn and rn_ini == ini:
                    return rd
        trovati = [rd for rd in disponibili if rd.docente.cognome.upper() == cogn]
        if len(trovati) == 1: return trovati[0]
        for rd in disponibili:
            if rd.docente.cognome.upper() in cogn or cogn in rd.docente.cognome.upper():
                return rd
        return None

    # Mappa (materia_upper, cognome_upper) → lista gruppi creati
    gruppi_per_proposta = {}
    for g in gruppi_list:
        cogn_g = (g.docente_rec.docente.cognome.upper()
                  if g.docente_rec and g.docente_rec.docente else '')
        key = (g.materia.upper(), cogn_g)
        gruppi_per_proposta.setdefault(key, []).append(g)

    proposte = []
    for (materia, cogn_doc), dati in sorted(per_proposta.items()):
        ini_doc = dati['alunni'][0].nome_ini_docente if dati['alunni'] else ''
        rd = trova_rd(cogn_doc, ini_doc)
        classi_ord = sorted(dati['classi'])
        n_ader = len([a for a in dati['alunni']
                      if a.stato_adesione in ('aderisce','sconosciuto')])
        # Per ogni classe della proposta, trova il gruppo che la copre (se esiste)
        mat_up = materia.upper()

        def _gruppi_per_materia(mat):
            result = []
            for g in gruppi_list:
                if _match_sinonimi(mat, g.materia) and g not in result:
                    result.append(g)
            return result

        gruppi_materia = _gruppi_per_materia(mat_up)

        # copertura_classi: {classe: gruppo_che_la_copre | None}
        # Una classe è coperta solo se:
        # 1. Esiste un gruppo con quella materia+classe, E
        # 2. Il docente del gruppo coincide con il docente assegnante (stesso cognome)
        #    OPPURE tutti gli alunni aderenti di quella classe sono già nel gruppo
        copertura_classi = {}
        for cls in classi_ord:
            cls_up = cls.upper()
            copertura_classi[cls] = None
            for g in gruppi_materia:
                classi_g = {cl.strip().upper() for cl in g.classi.split(',')}
                if cls_up not in classi_g:
                    continue
                # Verifica che il docente del gruppo corrisponda all'assegnante
                # oppure che gli alunni aderenti di questa classe siano già coperti
                doc_g = g.docente.cognome.upper() if g.docente else ''
                alunni_cls = [a for a in dati['alunni']
                              if a.classe.upper() == cls_up
                              and a.stato_adesione in ('aderisce','sconosciuto')]
                alunni_nel_gruppo = {(a.cognome, a.nome, a.classe) for a in g.alunni}
                alunni_aderenti_cls = {(a.cognome, a.nome, a.classe) for a in alunni_cls}
                # Coperto se: stesso cognome assegnante O tutti gli alunni già nel gruppo
                stesso_doc = cogn_doc.upper() == doc_g or cogn_doc.upper() in doc_g
                tutti_coperti = bool(alunni_aderenti_cls) and alunni_aderenti_cls.issubset(alunni_nel_gruppo)
                if stesso_doc or tutti_coperti:
                    copertura_classi[cls] = g
                    break

        gruppi_creati = list({g for g in copertura_classi.values() if g})
        classi_libere = [cls for cls, g in copertura_classi.items() if g is None]
        if n_ader > 0 or gruppi_creati:
            proposte.append({
                'materia': materia, 'cognome_doc': cogn_doc,
                'docente_raw': dati['docente_raw'],
                'classi': classi_ord,
                'n_alunni': n_ader, 'n_tot': len(dati['alunni']),
                'n_non_risposto': dati['n_non_risposto'],
                'n_non_aderisce': dati['n_non_aderisce'],
                'rd': rd,
                'gruppi_creati': gruppi_creati,
                'copertura_classi': copertura_classi,  # {cls: gruppo|None}
                'classi_libere': classi_libere,         # classi senza gruppo
            })

    # Classi disponibili per selettore manuale
    all_classi = sorted({imp.classe for imp in imports if imp.classe})
    materie_imp = sorted({imp.materia_norm for imp in imports if imp.materia_norm})

    # Classi per gruppo: quelle della materia del gruppo
    def _classi_per_materia(materia):
        mat = materia.strip().upper()
        classi = set()
        for i in imports:
            if i.classe and i.materia_norm and _match_sinonimi(mat, i.materia_norm):
                classi.add(i.classe)
        return sorted(classi) if classi else all_classi

    classi_per_gruppo = {g.id: _classi_per_materia(g.materia) for g in gruppi_list}

    # Conteggio aderenti per gruppo: conta gli import che matchano materia+classe del gruppo
    def _conta_aderenti(g):
        classi_g = {cl.strip().upper() for cl in g.classi.split(',')}
        tot = ader = 0
        for imp in imports:
            if imp.classe.upper() not in classi_g: continue
            if not _match_sinonimi(g.materia, imp.materia_norm or ''): continue
            tot += 1
            if imp.stato_adesione == 'aderisce':
                ader += 1
        return tot, ader

    aderenti_per_gruppo = {g.id: _conta_aderenti(g) for g in gruppi_list}

    tot_alunni_gruppi = sum(v[0] for v in aderenti_per_gruppo.values())
    tot_aderenti_gruppi = sum(v[1] for v in aderenti_per_gruppo.values())

    return render_template('recupero/gruppi.html',
        disponibili=disponibili, gruppi=gruppi_list,
        proposte=proposte, all_classi=all_classi,
        materie_imp=materie_imp,
        classi_per_gruppo=classi_per_gruppo,
        aderenti_per_gruppo=aderenti_per_gruppo,
        tot_alunni_gruppi=tot_alunni_gruppi,
        tot_aderenti_gruppi=tot_aderenti_gruppi,
    )


# ── CALENDARIO ────────────────────────────────────────────────────────
@recupero_bp.route('/recupero/calendario', methods=['GET', 'POST'])
def calendario():
    from datetime import timedelta
    if request.method == 'POST':
        azione = request.form.get('azione')

        def _t(s):
            try: h,m = map(int,s.split(':')); return h*60+m
            except: return 0

        def _controlla_conflitti(id_gruppo, data_d, ora_inizio, ora_fine, escludi_lid=None):
            """Restituisce lista di messaggi di conflitto (vuota = nessun conflitto)."""
            ini_m = _t(ora_inizio)
            fin_m = _t(ora_fine)
            g     = RecuperoGruppo.query.get(id_gruppo)
            if not g: return []
            errori = []

            tutti_gruppi = (RecuperoGruppo.query
                .join(RecuperoDocente)
                .filter(RecuperoDocente.anno_scol == ANNO)
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
                            f'👨‍🏫 Docente {doc.cognome if doc else "?"} già impegnato '
                            f'{ll.ora_inizio}–{ll.ora_fine} ({ag.materia[:20]})')

                    # Conflitto alunni: solo su chi ha effettivamente aderito a entrambi
                    if ag.id != id_gruppo:
                        alunni_g  = {(a.cognome,a.nome,a.classe) for a in g.alunni}
                        alunni_ag = {(a.cognome,a.nome,a.classe) for a in ag.alunni}
                        comuni = alunni_g & alunni_ag
                        if comuni:
                            nomi = ', '.join(f'{a[0]} {a[1]}' for a in list(comuni)[:3])
                            errori.append(
                                f'👨‍🎓 {len(comuni)} alunni in conflitto con {ag.materia[:20]} '
                                f'{ll.ora_inizio}–{ll.ora_fine}: {nomi}'
                                + ('...' if len(comuni)>3 else ''))
            return errori

        if azione == 'aggiungi':
            id_gruppo  = int(request.form['id_gruppo'])
            data_str   = request.form.get('data', '')
            ora_inizio = request.form.get('ora_inizio', '')
            ora_fine   = request.form.get('ora_fine', '')
            aula       = request.form.get('aula', '').strip() or None
            note       = request.form.get('note', '').strip() or None

            g = RecuperoGruppo.query.get_or_404(id_gruppo)

            # Verifica limite ore per gruppo (configurabile)
            max_ore = g.max_ore or 10
            if g.ore_pianificate >= max_ore:
                flash(f'Gruppo {g.materia} ha già raggiunto le {max_ore} ore massime.', 'warning')
                return redirect(url_for('recupero.calendario'))

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
                flash(f'Massimo {max_ore_giorno} ore al giorno per gruppo.', 'warning')
                return redirect(url_for('recupero.calendario'))

            data_d  = date.fromisoformat(data_str)
            errori  = _controlla_conflitti(id_gruppo, data_d, ora_inizio, ora_fine)
            if errori:
                flash('⚠ Lezione NON salvata — ' + ' | '.join(errori[:3]), 'danger')
                return redirect(url_for('recupero.calendario'))

            db.session.add(RecuperoLezione(
                id_gruppo=id_gruppo,
                data=data_d,
                ora_inizio=ora_inizio,
                ora_fine=ora_fine,
                aula=aula,
                note=note,
            ))
            db.session.commit()
            flash('Lezione aggiunta.', 'success')

        elif azione == 'modifica':
            lid          = int(request.form['id'])
            l            = RecuperoLezione.query.get_or_404(lid)
            nuova_data   = date.fromisoformat(request.form['data'])
            nuova_ini    = request.form.get('ora_inizio', l.ora_inizio)
            nuova_fin    = request.form.get('ora_fine',   l.ora_fine)
            # Controlla conflitti escludendo la lezione stessa
            errori = _controlla_conflitti(l.id_gruppo, nuova_data, nuova_ini, nuova_fin,
                                          escludi_lid=lid)
            if errori:
                flash('⚠ Modifica NON salvata — ' + ' | '.join(errori[:3]), 'danger')
                return redirect(url_for('recupero.calendario'))
            l.data       = nuova_data
            l.ora_inizio = nuova_ini
            l.ora_fine   = nuova_fin
            l.aula       = request.form.get('aula','').strip() or None
            l.note       = request.form.get('note','').strip() or None
            db.session.commit()
            flash('Lezione aggiornata.', 'success')

        elif azione == 'elimina':
            lid = int(request.form['id'])
            l   = RecuperoLezione.query.get_or_404(lid)
            db.session.delete(l)
            db.session.commit()
            flash('Lezione eliminata.', 'warning')

        elif azione == 'elimina_giorno':
            from datetime import date as _date
            data_str = request.form.get('data','')
            if data_str:
                data_d = _date.fromisoformat(data_str)
                gruppi_ids = [g.id for g in RecuperoGruppo.query
                    .join(RecuperoDocente)
                    .filter(RecuperoDocente.anno_scol == ANNO).all()]
                n = RecuperoLezione.query.filter(
                    RecuperoLezione.id_gruppo.in_(gruppi_ids),
                    RecuperoLezione.data == data_d
                ).delete(synchronize_session=False)
                db.session.commit()
                flash(f'Eliminate {n} lezioni del {data_d.strftime("%d/%m/%Y")}.', 'warning')

        elif azione == 'elimina_tutto':
            gruppi_ids = [g.id for g in RecuperoGruppo.query
                .join(RecuperoDocente)
                .filter(RecuperoDocente.anno_scol == ANNO).all()]
            n = RecuperoLezione.query.filter(
                RecuperoLezione.id_gruppo.in_(gruppi_ids)
            ).delete(synchronize_session=False)
            db.session.commit()
            flash(f'Calendario azzerato: {n} lezioni eliminate.', 'warning')

        elif azione == 'completa_bozza':
            # Genera lezioni solo per i gruppi che non ne hanno ancora
            from datetime import timedelta
            gruppi_incompleti = [g for g in (RecuperoGruppo.query
                .join(RecuperoDocente)
                .filter(RecuperoDocente.anno_scol == ANNO)
                .all()) if len(g.lezioni) == 0]

            if not gruppi_incompleti:
                flash('Tutti i gruppi hanno già lezioni pianificate.', 'info')
                return redirect(url_for('recupero.calendario'))

            date_disp = []
            cur = DATA_INIZIO
            while cur <= DATA_FINE:
                if cur.weekday() < 5:
                    date_disp.append(cur)
                cur += timedelta(days=1)

            def _t(s):
                try: h,m = map(int,s.split(':')); return h*60+m
                except: return 0
            def _sovrappone(d, ini, fin, occupied):
                ini_m, fin_m = _t(ini), _t(fin)
                for od, oi, of in occupied:
                    if od == d and oi < fin_m and of > ini_m:
                        return True
                return False

            # Carica slot già occupati da alunni E docenti
            slot_alunni  = {}
            slot_docente2 = {}
            for g in RecuperoGruppo.query.join(RecuperoDocente).filter(
                    RecuperoDocente.anno_scol == ANNO).all():
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
                        if v.data_inizio and data < v.data_inizio: continue
                        if v.data_fine   and data > v.data_fine:   continue
                        if v.giorno is not None and v.giorno != wd: continue
                        try:
                            h1,m1 = map(int,v.ora_inizio.split(':'))
                            h2,m2 = map(int,v.ora_fine.split(':'))
                            ore_disp += (h2*60+m2 - h1*60-m1) / 60
                        except Exception:
                            pass
                if not vincoli: ore_disp = 999
                return (1.0/(ore_disp+1))*3 + (len(g.alunni)/50.0)*2 + (len(vincoli)/20.0)

            gruppi_incompleti = sorted(gruppi_incompleti, key=_priorita_c, reverse=True)

            inserite = 0
            saltati  = []
            for g in gruppi_incompleti:
                vincoli_doc = g.docente_rec.vincoli
                ha_vincoli  = bool(vincoli_doc)

                def _slot_per_data_c(data):
                    wd = data.weekday()
                    if not ha_vincoli:
                        return [('08:00','13:00')]
                    classi_g = {x.strip().upper() for x in g.classi.split(',')}
                    slots = []
                    for v in vincoli_doc:
                        if v.data_inizio and data < v.data_inizio: continue
                        if v.data_fine   and data > v.data_fine:   continue
                        if v.giorno is not None and v.giorno != wd: continue
                        if v.classi_vincolo:
                            cv = {x.strip().upper() for x in v.classi_vincolo.split(',')}
                            if not classi_g.intersection(cv): continue
                        slots.append((v.ora_inizio, v.ora_fine))
                    return slots or []

                max_ore_tot  = g.max_ore or 10
                max_ore_g    = g.max_ore_giorno or 2
                ore_pian     = 0
                ore_per_data = {}
                alunni_g     = g.alunni

                for data in date_disp:
                    if ore_pian >= max_ore_tot: break
                    ore_ok = _slot_per_data_c(data)
                    if not ore_ok: continue
                    ore_oggi = ore_per_data.get(data, 0)
                    if ore_oggi >= max_ore_g: continue

                    for fascia_ini, fascia_fin in ore_ok:
                        durata_h = min(
                            (_t(fascia_fin) - _t(fascia_ini)) / 60,
                            max_ore_g - ore_oggi,
                            max_ore_tot - ore_pian, 2)
                        if durata_h <= 0: continue
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
                        if conflitto: continue

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
                msg += f' ⚠ {len(saltati)} gruppi ancora senza slot: ' +                        ', '.join(g.materia[:15] for g in saltati)
            flash(msg, 'success' if not saltati else 'warning')

        return redirect(url_for('recupero.calendario'))

    # Genera lista date lavorative 18/6-1/7
    date_disponibili = []
    cur = DATA_INIZIO
    while cur <= DATA_FINE:
        if cur.weekday() < 5:  # lun-ven
            date_disponibili.append(cur)
        cur += timedelta(days=1)

    gruppi_list = (RecuperoGruppo.query
                   .join(RecuperoDocente)
                   .filter(RecuperoDocente.anno_scol == ANNO)
                   .order_by(RecuperoGruppo.materia)
                   .all())

    # Sincronizza alunni da staging (aderenti) per ogni gruppo — sync differenziale
    from models.recupero import RecuperoImport
    _FAMIGLIE_SYNC = [
        {'LATINO', 'LINGUA LATINA', 'LINGUA E CULTURA LATINA'},
        {'ITALIANO', 'LINGUA E LETTERATURA ITALIANA', 'LINGUA E CULTURA ITALIANA'},
        {'MATEMATICA', 'MATEMATICA CON INFORMATICA', 'MATEMATICA E COMPLEMENTI DI MATEMATICA'},
        {'STORIA', 'STORIA E GEOGRAFIA'},
        {'FISICA', 'SCIENZE INTEGRATE (FISICA)'},
        {'INGLESE', 'LINGUA INGLESE', 'LINGUA E CULTURA STRANIERA (INGLESE)'},
        {'TEDESCO', 'LINGUA TEDESCA', 'LINGUA E CULTURA STRANIERA TEDESCO'},
    ]
    def _match_sync(m1, m2):
        m1u,m2u = m1.strip().upper(),m2.strip().upper()
        if m1u==m2u: return True
        for f in _FAMIGLIE_SYNC:
            fs={x.upper() for x in f}
            if m1u in fs and m2u in fs: return True
        return False

    imports_all = RecuperoImport.query.filter_by(anno_scol=ANNO).all()

    # Indice staging: (cognome, nome, classe, materia_norm) → stato_adesione
    staging_idx = {}
    for imp in imports_all:
        for f in _FAMIGLIE_SYNC:
            fs = {x.upper() for x in f}
            if imp.materia_norm and imp.materia_norm.upper() in fs:
                # Memorizza per ogni variante della famiglia
                for variante in fs:
                    staging_idx[(imp.cognome, imp.nome, imp.classe.upper(), variante)] = imp.stato_adesione
                break
        # Salva anche con la materia esatta
        staging_idx[(imp.cognome, imp.nome, imp.classe.upper(), (imp.materia_norm or '').upper())] = imp.stato_adesione

    for g in gruppi_list:
        classi_g = {cl.strip().upper() for cl in g.classi.split(',')}

        # 1. Aggiungi nuovi aderenti
        for imp in imports_all:
            if imp.classe.upper() not in classi_g: continue
            if not _match_sync(g.materia, imp.materia_norm or ''): continue
            if imp.stato_adesione not in ('aderisce', 'sconosciuto'): continue
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
            # Cerca lo stato attuale nello staging
            mat_up = g.materia.upper()
            stato = staging_idx.get((al.cognome, al.nome, al.classe.upper(), mat_up))
            if stato is None:
                # Prova con le famiglie
                for f in _FAMIGLIE_SYNC:
                    fs = {x.upper() for x in f}
                    if mat_up in fs:
                        for variante in fs:
                            stato = staging_idx.get((al.cognome, al.nome, al.classe.upper(), variante))
                            if stato: break
                        break
            if stato in ('non_aderisce', 'studio_ind'):
                db.session.delete(al)

    db.session.commit()

    # Organizza lezioni per data
    lezioni_per_data = {}
    for g in gruppi_list:
        for l in g.lezioni:
            lezioni_per_data.setdefault(l.data, []).append((l, g))

    # ── Calcolo conflitti ──────────────────────────────────────────────
    def _t2(s):
        try: h,m = map(int,s.split(':')); return h*60+m
        except: return 0

    conflitti = []  # lista di dict con tipo, descrizione, lezioni coinvolte

    # Raggruppa tutte le lezioni per data
    for data, coppie in lezioni_per_data.items():
        # Conflitto docente: stesso docente in fasce sovrapposte
        doc_lezioni = {}
        for l,g in coppie:
            doc_id = g.id_rec_docente
            doc_lezioni.setdefault(doc_id, []).append((l,g))
        for doc_id, ll in doc_lezioni.items():
            for i in range(len(ll)):
                for j in range(i+1, len(ll)):
                    l1,g1 = ll[i]; l2,g2 = ll[j]
                    if _t2(l1.ora_inizio) < _t2(l2.ora_fine) and _t2(l2.ora_inizio) < _t2(l1.ora_fine):
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
            for j in range(i+1, len(coppie)):
                l1,g1 = coppie[i]; l2,g2 = coppie[j]
                if g1.id == g2.id: continue
                sovrappone = _t2(l1.ora_inizio) < _t2(l2.ora_fine) and _t2(l2.ora_inizio) < _t2(l1.ora_fine)
                if not sovrappone: continue

                # Metodo 1: alunni espliciti in comune
                al1 = {(a.cognome,a.nome,a.classe) for a in g1.alunni}
                al2 = {(a.cognome,a.nome,a.classe) for a in g2.alunni}
                comuni = al1 & al2
                if comuni:
                    nomi = ', '.join(f'{a[0]} {a[1]}' for a in list(comuni)[:2])
                    conflitti.append({
                        'tipo': 'alunno',
                        'data': data,
                        'msg': f'{nomi} in due lezioni: {g1.materia[:15]} {l1.ora_inizio}-{l1.ora_fine} / {g2.materia[:15]} {l2.ora_inizio}-{l2.ora_fine}',
                        'ids': [l1.id, l2.id],
                    })


    # Set di id lezioni con conflitti (per evidenziare nel template)
    conflitti_ids = set()
    for cf in conflitti:
        for lid in cf['ids']:
            conflitti_ids.add(lid)

    return render_template('recupero/calendario.html',
        gruppi=gruppi_list,
        date_disponibili=date_disponibili,
        lezioni_per_data=lezioni_per_data,
        conflitti=conflitti,
        conflitti_ids=conflitti_ids,
    )


# ── CIRCOLARE ─────────────────────────────────────────────────────────
@recupero_bp.route('/recupero/circolare')
def circolare():
    gruppi_list = (RecuperoGruppo.query
                   .join(RecuperoDocente)
                   .filter(RecuperoDocente.anno_scol == ANNO)
                   .order_by(RecuperoGruppo.materia)
                   .all())

    # Organizza per data
    lezioni_per_data = {}
    for g in gruppi_list:
        for l in g.lezioni:
            lezioni_per_data.setdefault(l.data, []).append((l, g))

    date_ordinate = sorted(lezioni_per_data.keys())
    GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica']
    MESI   = ['','Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno',
              'Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre']

    return render_template('recupero/circolare.html',
        lezioni_per_data=lezioni_per_data,
        date_ordinate=date_ordinate,
        gruppi=gruppi_list,
        GIORNI=GIORNI, MESI=MESI,
    )


# ── API: classi di un docente ─────────────────────────────────────────
@recupero_bp.route('/recupero/api/classi-docente/<int:id_docente>')
def api_classi_docente(id_docente):
    from flask import jsonify
    from models.orario_docente import OrarioDocente
    classi = sorted(set(
        r.classe for r in OrarioDocente.query.filter_by(id_docente=id_docente).all()
        if r.classe and r.classe not in ('---', '-x-', 'POTENZIAMENTO')
    ))
    return jsonify(classi)


# ── EXPORT XLSX ───────────────────────────────────────────────────────
@recupero_bp.route('/recupero/export-xlsx')
def export_xlsx():
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from flask import send_file

    gruppi_list = (RecuperoGruppo.query
                   .join(RecuperoDocente)
                   .filter(RecuperoDocente.anno_scol == ANNO)
                   .order_by(RecuperoGruppo.materia)
                   .all())

    GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica']
    MESI   = ['','Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno',
              'Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre']

    def fmt_data(d):
        return f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month]}"

    # Stili
    BLU   = PatternFill('solid', start_color='1e3a5f')
    AZZUR = PatternFill('solid', start_color='dbeafe')
    VERDE = PatternFill('solid', start_color='dcfce7')
    GRAY  = PatternFill('solid', start_color='f3f4f6')
    BOLD  = Font(bold=True)
    BOLD_W= Font(bold=True, color='FFFFFF')
    THIN  = Border(
        left=Side(style='thin', color='d1d5db'),
        right=Side(style='thin', color='d1d5db'),
        top=Side(style='thin', color='d1d5db'),
        bottom=Side(style='thin', color='d1d5db'),
    )
    CENTER = Alignment(horizontal='center', vertical='center')
    WRAP   = Alignment(wrap_text=True, vertical='center')

    wb = Workbook()

    # ── FOGLIO FAMIGLIE ───────────────────────────────────────────────
    wsF = wb.active
    wsF.title = 'Famiglie'

    wsF.append([])
    wsF['A1'] = 'IIS "Leonardo da Vinci" — Chiavenna'
    wsF['A1'].font = Font(bold=True, size=13)
    wsF['A2'] = f'CALENDARIO CORSI DI RECUPERO — A.S. {ANNO}'
    wsF['A2'].font = Font(bold=True, size=11)
    wsF['A3'] = 'Periodo: 18 giugno – 1 luglio 2026'
    wsF['A3'].font = Font(italic=True, color='6b7280')
    wsF.append([])

    # Raggruppa lezioni per materia
    from collections import defaultdict
    per_materia = defaultdict(list)
    for g in gruppi_list:
        for l in g.lezioni:
            per_materia[g.materia].append((l, g))

    row = 5
    for materia in sorted(per_materia.keys()):
        lezioni = sorted(per_materia[materia], key=lambda x: (x[0].data, x[0].ora_inizio))

        # Header materia
        wsF.merge_cells(f'A{row}:E{row}')
        wsF[f'A{row}'] = materia.upper()
        wsF[f'A{row}'].font = BOLD_W
        wsF[f'A{row}'].fill = BLU
        wsF[f'A{row}'].alignment = CENTER
        row += 1

        # Header colonne
        for col, h in enumerate(['Giorno', 'Data', 'Orario', 'Durata', 'Classi'], 1):
            cell = wsF.cell(row=row, column=col, value=h)
            cell.font = BOLD
            cell.fill = AZZUR
            cell.alignment = CENTER
            cell.border = THIN
        row += 1

        for l, g in lezioni:
            vals = [
                GIORNI[l.data.weekday()],
                l.data.strftime('%d/%m/%Y'),
                f'{l.ora_inizio}–{l.ora_fine}',
                f'{l.durata_ore}h',
                g.classi,
            ]
            for col, v in enumerate(vals, 1):
                cell = wsF.cell(row=row, column=col, value=v)
                cell.border = THIN
                cell.alignment = WRAP
            row += 1

        row += 1  # spazio tra materie

    # Larghezze famiglie
    for i, w in enumerate([14, 14, 14, 8, 30], 1):
        wsF.column_dimensions[get_column_letter(i)].width = w

    # ── FOGLIO DOCENTI ────────────────────────────────────────────────
    wsD = wb.create_sheet('Docenti')

    wsD['A1'] = 'IIS "Leonardo da Vinci" — Chiavenna'
    wsD['A1'].font = Font(bold=True, size=13)
    wsD['A2'] = f'CALENDARIO CORSI DI RECUPERO — A.S. {ANNO} — USO INTERNO'
    wsD['A2'].font = Font(bold=True, size=11, color='dc2626')
    wsD.append([])
    wsD.append([])

    # Indice staging: (cognome, nome, classe, materia_norm) → stato_adesione
    from models.recupero import RecuperoImport
    _FAM_EXP = [
        {'LATINO', 'LINGUA LATINA', 'LINGUA E CULTURA LATINA'},
        {'ITALIANO', 'LINGUA E LETTERATURA ITALIANA', 'LINGUA E CULTURA ITALIANA'},
        {'MATEMATICA', 'MATEMATICA CON INFORMATICA', 'MATEMATICA E COMPLEMENTI DI MATEMATICA'},
        {'STORIA', 'STORIA E GEOGRAFIA'},
        {'FISICA', 'SCIENZE INTEGRATE (FISICA)'},
        {'INGLESE', 'LINGUA INGLESE', 'LINGUA E CULTURA STRANIERA (INGLESE)'},
        {'TEDESCO', 'LINGUA TEDESCA', 'LINGUA E CULTURA STRANIERA TEDESCO'},
    ]
    def _fam_match_exp(m1, m2):
        m1u,m2u = m1.strip().upper(), m2.strip().upper()
        if m1u == m2u: return True
        for f in _FAM_EXP:
            fs = {x.upper() for x in f}
            if m1u in fs and m2u in fs: return True
        return False

    # Carica tutti gli alunni con debito in questa materia+classe dallo staging
    imports_all_exp = RecuperoImport.query.filter_by(anno_scol=ANNO).all()

    STATO_LABEL = {
        'aderisce':     '✓ aderisce',
        'sconosciuto':  '✓ aderisce',
        'non_risposto': '❓ non risposto',
        'non_aderisce': '✗ non aderisce',
        'studio_ind':   '📚 studio ind.',
    }
    STATO_COLOR = {
        'aderisce':     '166534',  # verde scuro
        'sconosciuto':  '166534',
        'non_risposto': 'dc2626',  # rosso
        'non_aderisce': '6b7280',  # grigio
        'studio_ind':   '92400e',  # arancio
    }
    STATO_BG = {
        'aderisce':     'dcfce7',
        'sconosciuto':  'dcfce7',
        'non_risposto': 'fee2e2',
        'non_aderisce': 'f3f4f6',
        'studio_ind':   'fef9c3',
    }

    row = 5
    for materia in sorted(per_materia.keys()):
        lezioni = sorted(per_materia[materia], key=lambda x: (x[0].data, x[0].ora_inizio))
        # Gruppi di questa materia
        gruppi_mat = list({g.id: g for (l,g) in lezioni}.values())

        wsD.merge_cells(f'A{row}:I{row}')
        wsD[f'A{row}'] = materia.upper()
        wsD[f'A{row}'].font = BOLD_W
        wsD[f'A{row}'].fill = BLU
        wsD[f'A{row}'].alignment = CENTER
        row += 1

        for col, h in enumerate(['Giorno','Data','Orario','Docente','Classe','Cognome','Nome','Aula','Adesione'], 1):
            cell = wsD.cell(row=row, column=col, value=h)
            cell.font = BOLD
            cell.fill = VERDE
            cell.alignment = CENTER
            cell.border = THIN
        row += 1

        for l, g in lezioni:
            doc = g.docente
            nome_doc = f'{doc.cognome} {doc.nome or ""}'.strip() if doc else '—'
            classi_g = {cl.strip().upper() for cl in g.classi.split(',')}

            # Tutti gli alunni con debito in questa materia+classi dallo staging
            alunni_staging = [
                imp for imp in imports_all_exp
                if imp.classe.upper() in classi_g
                and _fam_match_exp(materia, imp.materia_norm or '')
            ]
            # Ordina: prima aderiscono, poi non risposto, poi non aderisce, poi studio_ind
            ordine = {'aderisce':0,'sconosciuto':0,'non_risposto':1,'non_aderisce':2,'studio_ind':3}
            alunni_staging = sorted(alunni_staging,
                key=lambda a: (ordine.get(a.stato_adesione,9), a.classe, a.cognome))

            row_inizio_blocco = row

            if alunni_staging:
                for i_al, al in enumerate(alunni_staging):
                    stato = al.stato_adesione or 'sconosciuto'
                    label = STATO_LABEL.get(stato, stato)
                    col_t = STATO_COLOR.get(stato, '374151')
                    col_b = STATO_BG.get(stato, 'ffffff')

                    # Colonne 1-4 (Giorno/Data/Orario/Docente) solo sulla prima riga,
                    # verranno unite verticalmente dopo il ciclo
                    vals = [
                        GIORNI[l.data.weekday()] if i_al == 0 else None,
                        l.data.strftime('%d/%m/%Y') if i_al == 0 else None,
                        f'{l.ora_inizio}–{l.ora_fine}' if i_al == 0 else None,
                        nome_doc if i_al == 0 else None,
                        al.classe,
                        al.cognome,
                        al.nome,
                        l.aula or '—',
                        label,
                    ]
                    for col, v in enumerate(vals, 1):
                        cell = wsD.cell(row=row, column=col, value=v)
                        cell.border = THIN
                        cell.alignment = WRAP
                        if col == 9:  # Adesione: colorata per stato
                            cell.font = Font(bold=True, color=col_t, name='Arial', size=9)
                            cell.fill = PatternFill('solid', start_color=col_b)
                            cell.alignment = Alignment(horizontal='center', vertical='center')
                        elif col <= 4:
                            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                            cell.fill = PatternFill('solid', start_color='fdebd3')
                        elif i_al % 2 == 1:
                            cell.fill = PatternFill('solid', start_color='f8fafc')
                    row += 1

                # Merge verticale colonne Giorno/Data/Orario/Docente per tutto il blocco
                if row - 1 > row_inizio_blocco:
                    for col_letter in ('A', 'B', 'C', 'D'):
                        wsD.merge_cells(f'{col_letter}{row_inizio_blocco}:{col_letter}{row-1}')
            else:
                # Nessun alunno dallo staging — mostra la lezione vuota
                vals = [
                    GIORNI[l.data.weekday()],
                    l.data.strftime('%d/%m/%Y'),
                    f'{l.ora_inizio}–{l.ora_fine}',
                    nome_doc, g.classi, '—', '—', l.aula or '—', '—',
                ]
                for col, v in enumerate(vals, 1):
                    cell = wsD.cell(row=row, column=col, value=v)
                    cell.border = THIN
                    if col <= 4:
                        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                        cell.fill = PatternFill('solid', start_color='fdebd3')
                row += 1

        row += 1

    for i, w in enumerate([12, 12, 12, 22, 10, 18, 16, 8, 14], 1):
        wsD.column_dimensions[get_column_letter(i)].width = w

    # ── FOGLIO GIORNATE ───────────────────────────────────────────────
    # Una sezione per ogni giorno — solo materie e orari, senza nomi
    from collections import defaultdict

    # Raggruppa lezioni per data
    lezioni_per_data = defaultdict(list)
    for g in gruppi_list:
        for l in g.lezioni:
            lezioni_per_data[l.data].append((l, g))

    if lezioni_per_data:
        wsG = wb.create_sheet('Giornate')
        wsG['A1'] = 'IIS "Leonardo da Vinci" — Chiavenna'
        wsG['A1'].font = Font(bold=True, size=13)
        wsG['A2'] = f'CALENDARIO GIORNALIERO — CORSI DI RECUPERO — A.S. {ANNO}'
        wsG['A2'].font = Font(bold=True, size=11)
        wsG.append([])

        row_g = 4
        for data in sorted(lezioni_per_data.keys()):
            coppie = sorted(lezioni_per_data[data], key=lambda x: x[0].ora_inizio)

            # Header giorno
            giorno_str = f'{GIORNI[data.weekday()]} {data.strftime("%d/%m/%Y")}'
            wsG.merge_cells(f'A{row_g}:G{row_g}')
            wsG[f'A{row_g}'] = giorno_str.upper()
            wsG[f'A{row_g}'].font = BOLD_W
            wsG[f'A{row_g}'].fill = BLU
            wsG[f'A{row_g}'].alignment = CENTER
            wsG[f'A{row_g}'].border = THIN
            row_g += 1

            # Intestazioni colonne
            for col, h in enumerate(['Orario','Materia','Docente','Classi','N. alunni','Ore','Aula'], 1):
                cell = wsG.cell(row=row_g, column=col, value=h)
                cell.font = BOLD
                cell.fill = VERDE
                cell.alignment = CENTER
                cell.border = THIN
            row_g += 1

            # Righe lezioni
            for i_r, (l, g) in enumerate(coppie):
                doc = g.docente
                nome_doc = f'{doc.cognome} {(doc.nome or "")[0]}.' if doc else '—'
                n_alunni = len(g.alunni) or '—'
                try:
                    h1,m1 = map(int, l.ora_inizio.split(':'))
                    h2,m2 = map(int, l.ora_fine.split(':'))
                    ore_h = (h2*60+m2 - h1*60-m1) / 60
                    ore_str = f'{ore_h:.1f}h'.replace('.0h','h')
                except Exception:
                    ore_str = '—'

                vals = [
                    f'{l.ora_inizio}–{l.ora_fine}',
                    g.materia,
                    nome_doc,
                    g.classi,
                    n_alunni,
                    ore_str,
                    l.aula or '—',
                ]
                for col, v in enumerate(vals, 1):
                    cell = wsG.cell(row=row_g, column=col, value=v)
                    cell.border = THIN
                    cell.alignment = Alignment(vertical='center',
                                               wrap_text=(col == 2))
                    if i_r % 2 == 1:
                        cell.fill = PatternFill('solid', start_color='f0f4ff')
                row_g += 1

            row_g += 1  # spazio tra giorni

        for i, w in enumerate([14, 35, 18, 22, 10, 8, 10], 1):
            wsG.column_dimensions[get_column_letter(i)].width = w
        wsG.freeze_panes = 'A4'

    # ── FOGLIO RIEPILOGO ORE ──────────────────────────────────────────
    # Una riga per docente+materia, con ore totali per materia e per docente.
    # Ogni sessione (data+orario+docente) è contata una sola volta.
    wsR = wb.create_sheet('Riepilogo Ore')
    wsR['A1'] = 'IIS "Leonardo da Vinci" — Chiavenna'
    wsR['A1'].font = Font(bold=True, size=13)
    wsR['A2'] = f'RIEPILOGO ORE CORSI DI RECUPERO — A.S. {ANNO}'
    wsR['A2'].font = Font(bold=True, size=11)
    wsR.append([])

    for col, h in enumerate(['DOCENTE', 'MATERIA', 'ORE (per materia)', 'ORE TOTALI'], 1):
        cell = wsR.cell(row=4, column=col, value=h)
        cell.font = BOLD_W
        cell.fill = BLU
        cell.alignment = CENTER
        cell.border = THIN

    # Calcola ore per docente+materia: conta sessioni unique (data, ora_inizio, ora_fine, id_gruppo)
    ore_per_doc_mat = defaultdict(float)  # (docente_id, materia) -> ore
    nome_docente_map = {}
    for g in gruppi_list:
        if not g.docente: continue
        sessioni_viste = set()
        for l in g.lezioni:
            key = (l.data, l.ora_inizio, l.ora_fine, g.id)
            if key in sessioni_viste: continue
            sessioni_viste.add(key)
            try:
                h1,m1 = map(int, l.ora_inizio.split(':'))
                h2,m2 = map(int, l.ora_fine.split(':'))
                ore = (h2*60+m2 - h1*60-m1) / 60
            except Exception:
                ore = 0
            ore_per_doc_mat[(g.docente.id, g.materia)] += ore
        nome_docente_map[g.docente.id] = f'{g.docente.cognome} {g.docente.nome or ""}'.strip()

    # Raggruppa per docente, ordina materie
    per_doc = defaultdict(list)
    for (doc_id, materia), ore in ore_per_doc_mat.items():
        per_doc[doc_id].append((materia, ore))

    row_r = 5
    totale_generale = 0
    for doc_id in sorted(per_doc.keys(), key=lambda d: nome_docente_map.get(d, '')):
        materie = sorted(per_doc[doc_id])
        tot_doc = sum(o for _, o in materie)
        totale_generale += tot_doc
        for i_m, (materia, ore) in enumerate(materie):
            vals = [
                nome_docente_map.get(doc_id, '?') if i_m == 0 else None,
                materia,
                int(ore) if ore == int(ore) else ore,
                tot_doc if i_m == 0 else None,
            ]
            for col, v in enumerate(vals, 1):
                cell = wsR.cell(row=row_r, column=col, value=v)
                cell.border = THIN
                if col in (1, 4):
                    cell.font = BOLD
                cell.alignment = Alignment(horizontal='left' if col<=2 else 'center', vertical='center')
            row_r += 1

    # Riga totale generale
    wsR.merge_cells(f'A{row_r}:C{row_r}')
    wsR[f'A{row_r}'] = 'TOTALE GENERALE'
    wsR[f'A{row_r}'].font = BOLD_W
    wsR[f'A{row_r}'].fill = PatternFill('solid', start_color='1f3864')
    cell_tot = wsR.cell(row=row_r, column=4, value=int(totale_generale) if totale_generale==int(totale_generale) else totale_generale)
    cell_tot.font = BOLD_W
    cell_tot.fill = PatternFill('solid', start_color='1f3864')
    cell_tot.alignment = CENTER
    row_r += 2

    wsR.cell(row=row_r, column=1, value=(
        'Nota: ogni sessione (data + orario + docente) è contata una sola volta, '
        'indipendentemente dal numero di studenti o classi presenti.'
    )).font = Font(italic=True, size=9, color='6b7280')

    for i, w in enumerate([22, 42, 16, 14], 1):
        wsR.column_dimensions[get_column_letter(i)].width = w

    # Salva in memoria e invia
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name=f'corsi_recupero_{ANNO}.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


def _genera_scheda_docente_xlsx(docente, gruppi_docente, anno_scol):
    """
    Genera un workbook XLSX con la scheda calendario di un singolo docente:
    sessioni (data+orario+materia) con elenco alunni e stato adesione.
    Replica lo stile della scheda di esempio fornita da Roberto.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from models.recupero import RecuperoImport

    GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica']

    _FAM_SCHEDA = [
        {'LATINO', 'LINGUA LATINA', 'LINGUA E CULTURA LATINA'},
        {'ITALIANO', 'LINGUA E LETTERATURA ITALIANA', 'LINGUA E CULTURA ITALIANA'},
        {'MATEMATICA', 'MATEMATICA CON INFORMATICA', 'MATEMATICA E COMPLEMENTI DI MATEMATICA'},
        {'STORIA', 'STORIA E GEOGRAFIA'},
        {'FISICA', 'SCIENZE INTEGRATE (FISICA)'},
        {'INGLESE', 'LINGUA INGLESE', 'LINGUA E CULTURA STRANIERA (INGLESE)'},
        {'TEDESCO', 'LINGUA TEDESCA', 'LINGUA E CULTURA STRANIERA TEDESCO'},
    ]
    def _match_scheda(m1, m2):
        m1u,m2u = m1.strip().upper(), m2.strip().upper()
        if m1u == m2u: return True
        for f in _FAM_SCHEDA:
            fs = {x.upper() for x in f}
            if m1u in fs and m2u in fs: return True
        return False

    STATO_LABEL = {
        'aderisce':'✓ aderisce', 'sconosciuto':'✓ aderisce',
        'non_risposto':'❓ non risposto', 'non_aderisce':'✗ non aderisce',
        'studio_ind':'📚 studio ind.',
    }
    STATO_FILL = {
        'aderisce':'C6E0B4', 'sconosciuto':'C6E0B4',
        'non_risposto':'FFE699', 'non_aderisce':'F4B6B6',
        'studio_ind':'FFF2CC',
    }

    imports_all = RecuperoImport.query.filter_by(anno_scol=anno_scol).all()

    # Stili
    BLU_FILL   = PatternFill('solid', start_color='2F4F8C')
    HDR_FILL   = PatternFill('solid', start_color='D9E1F2')
    COLHDR_FILL= PatternFill('solid', start_color='EDEDED')
    TOT_FILL   = PatternFill('solid', start_color='1F3864')
    ROW_ALT    = PatternFill('solid', start_color='F4F7FC')
    WHITE_FILL = PatternFill('solid', start_color='FFFFFF')
    BOLD_W     = Font(bold=True, color='FFFFFF', size=11)
    BOLD_W10   = Font(bold=True, color='FFFFFF', size=10)
    BOLD       = Font(bold=True, size=9)
    NORMAL     = Font(size=9)
    THIN_SIDE  = Side(style='thin', color='B0B8CC')
    THIN       = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)
    CENTER     = Alignment(horizontal='center', vertical='center')
    LEFT       = Alignment(horizontal='left', vertical='center')

    wb = Workbook()
    ws = wb.active
    ws.title = 'Calendario'

    nome_doc = f'{docente.cognome} {docente.nome or ""}'.strip()

    ws.merge_cells('A1:H1')
    ws['A1'] = 'IIS "Leonardo da Vinci" — Chiavenna'
    ws['A1'].font = BOLD_W; ws['A1'].fill = BLU_FILL; ws['A1'].alignment = CENTER

    ws.merge_cells('A2:H2')
    ws['A2'] = f'CALENDARIO CORSI DI RECUPERO — A.S. {anno_scol}'
    ws['A2'].font = BOLD_W10; ws['A2'].fill = BLU_FILL; ws['A2'].alignment = CENTER

    ws.merge_cells('A3:H3')
    ws['A3'] = f'Docente: {nome_doc}'
    ws['A3'].font = BOLD_W10; ws['A3'].fill = BLU_FILL; ws['A3'].alignment = CENTER

    ws.row_dimensions[1].height = 20
    ws.row_dimensions[2].height = 18
    ws.row_dimensions[3].height = 18
    ws.row_dimensions[4].height = 6

    # Raccogli tutte le sessioni (data, ora_inizio, ora_fine, materia, gruppo)
    sessioni = []
    for g in gruppi_docente:
        for l in g.lezioni:
            sessioni.append((l.data, l.ora_inizio, l.ora_fine, g.materia, g, l))
    sessioni.sort(key=lambda x: (x[0], x[1]))

    row = 5
    ore_totali_docente = 0.0

    for data, ora_ini, ora_fine, materia, g, l in sessioni:
        try:
            h1,m1 = map(int, ora_ini.split(':'))
            h2,m2 = map(int, ora_fine.split(':'))
            durata_h = (h2*60+m2 - h1*60-m1) / 60
        except Exception:
            durata_h = 0
        ore_totali_docente += durata_h

        ws.row_dimensions[row].height = 16
        ws.merge_cells(f'A{row}:H{row}')
        header_str = (f'{GIORNI[data.weekday()]} {data.strftime("%d/%m/%Y")}   '
                      f'{ora_ini}–{ora_fine}   ({durata_h:.1f}h)   —   {materia.upper()}')
        ws[f'A{row}'] = header_str
        ws[f'A{row}'].font = BOLD; ws[f'A{row}'].fill = HDR_FILL; ws[f'A{row}'].alignment = LEFT
        row += 1

        # Header colonne (E:H)
        ws.row_dimensions[row].height = 14
        for col, h in zip(['E','F','G','H'], ['Classe','Cognome','Nome','Adesione']):
            cell = ws[f'{col}{row}']
            cell.value = h
            cell.font = BOLD; cell.fill = COLHDR_FILL; cell.alignment = CENTER
            cell.border = THIN
        row += 1

        # Alunni: tutti quelli con debito in questa materia+classi, dallo staging
        classi_g = {cl.strip().upper() for cl in g.classi.split(',')}
        alunni_sess = [
            imp for imp in imports_all
            if imp.classe.upper() in classi_g
            and _match_scheda(materia, imp.materia_norm or '')
        ]
        ordine = {'aderisce':0,'sconosciuto':0,'non_risposto':1,'non_aderisce':2,'studio_ind':3}
        alunni_sess.sort(key=lambda a: (ordine.get(a.stato_adesione,9), a.classe, a.cognome))

        for i_al, al in enumerate(alunni_sess):
            ws.row_dimensions[row].height = 14
            stato = al.stato_adesione or 'sconosciuto'
            bg = STATO_FILL.get(stato, 'FFFFFF')
            label = STATO_LABEL.get(stato, stato)
            row_fill = ROW_ALT if i_al % 2 == 1 else WHITE_FILL

            vals = [al.classe, al.cognome, al.nome, label]
            for col, v in zip(['E','F','G','H'], vals):
                cell = ws[f'{col}{row}']
                cell.value = v
                cell.border = THIN
                cell.alignment = CENTER if col in ('E','H') else LEFT
                cell.font = NORMAL
                cell.fill = PatternFill('solid', start_color=bg) if col == 'H' else row_fill
            row += 1

        row += 1  # riga vuota tra sessioni

    # Riga totale ore
    ws.merge_cells(f'A{row}:G{row}')
    ws[f'A{row}'] = 'TOTALE ORE DOCENTE'
    ws[f'A{row}'].font = BOLD_W; ws[f'A{row}'].fill = TOT_FILL; ws[f'A{row}'].alignment = LEFT
    cell_tot = ws[f'H{row}']
    cell_tot.value = int(ore_totali_docente) if ore_totali_docente == int(ore_totali_docente) else ore_totali_docente
    cell_tot.font = BOLD_W; cell_tot.fill = TOT_FILL; cell_tot.alignment = CENTER
    row += 2

    # Legenda
    ws[f'A{row}'] = 'Legenda:'
    ws[f'A{row}'].font = Font(bold=True, size=9)
    row += 1
    legenda = [('A','✓ aderisce','C6E0B4'), ('B','❓ non risposto','FFE699'), ('C','✗ non aderisce','F4B6B6')]
    for col, label, color in legenda:
        cell = ws[f'{col}{row}']
        cell.value = label
        cell.fill = PatternFill('solid', start_color=color)
        cell.font = Font(size=9)

    # Larghezze colonne
    for col, w in zip(['A','B','C','D','E','F','G','H'], [12,12,13,32,9,18,18,16]):
        ws.column_dimensions[col].width = w

    ws.freeze_panes = 'A5'

    return wb


@recupero_bp.route('/recupero/export-schede-docenti')
def export_schede_docenti():
    """
    Genera un file ZIP con una scheda XLSX per ciascun docente che ha
    almeno una lezione pianificata — calendario individuale + alunni + stato adesione.
    """
    import io, zipfile
    from flask import send_file
    from collections import defaultdict

    gruppi_list = (RecuperoGruppo.query
                   .join(RecuperoDocente)
                   .filter(RecuperoDocente.anno_scol == ANNO)
                   .order_by(RecuperoGruppo.materia)
                   .all())

    # Raggruppa gruppi per docente
    gruppi_per_docente = defaultdict(list)
    for g in gruppi_list:
        if g.docente and g.lezioni:
            gruppi_per_docente[g.docente.id].append(g)

    if not gruppi_per_docente:
        flash('Nessuna lezione pianificata: genera prima il calendario.', 'warning')
        return redirect(url_for('recupero.calendario'))

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for doc_id, gruppi_doc in gruppi_per_docente.items():
            docente = gruppi_doc[0].docente
            wb_doc = _genera_scheda_docente_xlsx(docente, gruppi_doc, ANNO)
            file_buf = io.BytesIO()
            wb_doc.save(file_buf)
            file_buf.seek(0)
            cognome_safe = docente.cognome.replace(' ', '_')
            nome_safe = (docente.nome or '').split()[0] if docente.nome else ''
            filename = f'{cognome_safe}_{nome_safe}.xlsx'.strip('_')
            zf.writestr(filename, file_buf.read())

    zip_buf.seek(0)
    return send_file(zip_buf, as_attachment=True,
                     download_name=f'schede_docenti_recupero_{ANNO}.zip',
                     mimetype='application/zip')


# ── VINCOLI DOCENTE ───────────────────────────────────────────────────
@recupero_bp.route('/recupero/vincoli', methods=['GET', 'POST'])
def vincoli():
    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione in ('aggiungi', 'aggiungi_multi'):
            from datetime import date as _date
            id_recdoc  = int(request.form['id_rec_docente'])
            giorni     = [int(g) for g in request.form.getlist('giorni')]
            if not giorni and 'giorno' in request.form:
                giorni = [int(request.form['giorno'])]
            ora_ini    = request.form.get('ora_inizio','08:00').strip()
            ora_fin    = request.form.get('ora_fine','13:00').strip()
            note       = request.form.get('note','').strip() or None
            # Vincolo date
            d_ini_s    = request.form.get('data_inizio','').strip()
            d_fin_s    = request.form.get('data_fine','').strip()
            d_ini = _date.fromisoformat(d_ini_s) if d_ini_s else None
            d_fin = _date.fromisoformat(d_fin_s) if d_fin_s else None

            if not giorni:
                # Nessun giorno selezionato → vincolo solo su date (tutti i gg)
                giorni = [None]

            # classi_vincolo può arrivare come checkbox multipli o testo libero
            classi_list = request.form.getlist('classi_vincolo_cb')
            if classi_list:
                classi_v = ','.join(c.strip().upper() for c in classi_list if c.strip()) or None
            else:
                raw = request.form.get('classi_vincolo','').strip()
                classi_v = ','.join(c.strip().upper() for c in raw.split(',') if c.strip()) or None
            materia_v  = request.form.get('materia_vincolo','').strip() or None
            for giorno in giorni:
                db.session.add(RecuperoVincolo(
                    id_rec_docente=id_recdoc, anno_scol=ANNO,
                    giorno=giorno, ora_inizio=ora_ini,
                    ora_fine=ora_fin, note=note,
                    data_inizio=d_ini, data_fine=d_fin,
                    classi_vincolo=classi_v,
                    materia_vincolo=materia_v,
                ))
            db.session.commit()
            n = len([g for g in giorni if g is not None]) or 1
            flash(f'{"Fascia aggiunta" if n==1 else str(n)+" fasce aggiunte"}.', 'success')

        elif azione == 'elimina':
            vid = int(request.form['id'])
            v = RecuperoVincolo.query.get_or_404(vid)
            db.session.delete(v)
            db.session.commit()
            flash('Fascia eliminata.', 'warning')

        elif azione == 'modifica':
            from datetime import date as _date
            vid      = int(request.form['id'])
            v        = RecuperoVincolo.query.get_or_404(vid)
            v.ora_inizio  = request.form.get('ora_inizio','08:00').strip()
            v.ora_fine    = request.form.get('ora_fine','13:00').strip()
            d_ini_s  = request.form.get('data_inizio','').strip()
            d_fin_s  = request.form.get('data_fine','').strip()
            v.data_inizio = _date.fromisoformat(d_ini_s) if d_ini_s else None
            v.data_fine   = _date.fromisoformat(d_fin_s) if d_fin_s else None
            v.note           = request.form.get('note','').strip() or None
            classi_list2 = request.form.getlist('classi_vincolo_cb')
            if classi_list2:
                v.classi_vincolo = ','.join(c.strip().upper() for c in classi_list2 if c.strip()) or None
            else:
                raw2 = request.form.get('classi_vincolo','').strip()
                v.classi_vincolo = ','.join(c.strip().upper() for c in raw2.split(',') if c.strip()) or None
            v.materia_vincolo = request.form.get('materia_vincolo','').strip() or None
            db.session.commit()
            flash('Fascia aggiornata.', 'success')

        elif azione == 'elimina_tutti':
            id_recdoc = int(request.form['id_rec_docente'])
            RecuperoVincolo.query.filter_by(id_rec_docente=id_recdoc).delete()
            db.session.commit()
            flash('Disponibilità azzerata — il sistema userà il default (tutti i giorni 08:00–13:00).', 'info')

        # Torna al box del docente modificato
        anchor = ''
        if 'id_rec_docente' in request.form:
            anchor = f'#docente-{request.form["id_rec_docente"]}'
        elif 'id' in request.form:
            vid = request.form.get('id','')
            if vid.isdigit():
                vobj = RecuperoVincolo.query.get(int(vid))
                if vobj: anchor = f'#docente-{vobj.id_rec_docente}'
        return redirect(url_for('recupero.vincoli') + anchor)

    disponibili = (RecuperoDocente.query.filter_by(anno_scol=ANNO)
                   .join(Docente).order_by(Docente.cognome).all())
    GIORNI_NOMI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì']

    # Mappa id_recdoc → classi con debiti nelle materie che il docente può coprire
    from models.recupero import RecuperoImport
    from collections import defaultdict

    classi_per_docente = {}
    for rd in disponibili:
        # Materie coperte: principale (può essere "ITALIANO, STORIA") + extra
        mat_principale_raw = (rd.docente.materia or '').strip().upper()
        # Splitta materie multiple nella colonna principale (es. "ITALIANO, STORIA")
        mat_principali = [m.strip() for m in mat_principale_raw.split(',') if m.strip()]
        materie_extra  = [m.strip().upper() for m in rd.materie_extra.split(',')
                          if m.strip()] if rd.materie_extra else []
        materie_coperte = mat_principali + materie_extra

        # Carica una volta sola tutte le combinazioni classe+materia
        tutti = (RecuperoImport.query
                 .filter_by(anno_scol=ANNO)
                 .with_entities(RecuperoImport.classe, RecuperoImport.materia_norm)
                 .distinct().all())

        # Sinonimi: materia breve/DB → varianti presenti nel registro elettronico
        # Aggiornati sulle materie effettive del file importato
        _SINONIMI = {
            # Italiano
            'ITALIANO':        ('LINGUA E LETTERATURA ITALIANA','LETTERATURA ITALIANA','ITALIANA'),
            'LETTERATURA':     ('LINGUA E LETTERATURA ITALIANA','LETTERATURA ITALIANA','ITALIANA'),
            # Latino
            'LATINO':          ('LINGUA E CULTURA LATINA','LINGUA LATINA'),
            'LINGUA LATINA':   ('LINGUA E CULTURA LATINA','LINGUA LATINA'),
            # Storia
            'STORIA':          ('STORIA','STORIA E GEOGRAFIA'),
            'STORIA E GEOGRAFIA': ('STORIA','STORIA E GEOGRAFIA'),
            # Filosofia
            'FILOSOFIA':       ('FILOSOFIA',),
            # Matematica
            'MATEMATICA':      ('MATEMATICA','MATEMATICA E COMPLEMENTI DI MATEMATICA',
                                'MATEMATICA CON INFORMATICA'),
            # Fisica
            'FISICA':          ('FISICA','SCIENZE INTEGRATE (FISICA)'),
            # Scienze
            'SCIENZE':         ('SCIENZE NATURALI','BIOLOGIA','CHIMICA',
                                'SCIENZE INTEGRATE'),
            'SCIENZE NATURALI':('SCIENZE NATURALI','BIOLOGIA','CHIMICA'),
            'BIOLOGIA':        ('SCIENZE NATURALI','BIOLOGIA','CHIMICA'),
            'CHIMICA':         ('SCIENZE NATURALI','BIOLOGIA','CHIMICA'),
            # Inglese
            'INGLESE':         ('LINGUA E CULTURA STRANIERA (INGLESE)','LINGUA INGLESE','INGLESE'),
            'LINGUA INGLESE':  ('LINGUA E CULTURA STRANIERA (INGLESE)','LINGUA INGLESE','INGLESE'),
            # Tedesco
            'TEDESCO':         ('LINGUA E CULTURA STRANIERA TEDESCO','LINGUA TEDESCA','TEDESCO'),
            'LINGUA TEDESCA':  ('LINGUA E CULTURA STRANIERA TEDESCO','LINGUA TEDESCA','TEDESCO'),
            # Francese / Spagnolo
            'FRANCESE':        ('LINGUA FRANCESE','FRANCESE'),
            'SPAGNOLO':        ('LINGUA SPAGNOLA','SPAGNOLO'),
            # Informatica
            'INFORMATICA':     ('INFORMATICA','TECNOLOGIE INFORMATICHE',
                                'MATEMATICA CON INFORMATICA'),
            'TECNOLOGIE INFORMATICHE': ('INFORMATICA','TECNOLOGIE INFORMATICHE'),
            # Economia / Diritto / Estimo
            'ECONOMIA':        ('ECONOMIA','GEOPEDOLOGIA, ECONOMIA ED ESTIMO'),
            'ESTIMO':          ('GEOPEDOLOGIA, ECONOMIA ED ESTIMO',),
            'GEOPEDOLOGIA':    ('GEOPEDOLOGIA, ECONOMIA ED ESTIMO',),
            # Topografia
            'TOPOGRAFIA':      ('TOPOGRAFIA',),
            # Arte
            'ARTE':            ('ARTE','STORIA ARTE','DISEGNO'),
        }

        def _match_materie(mat_doc, mat_imp):
            md = mat_doc.strip().upper()
            mi = mat_imp.strip().upper()
            # Match diretto sottostringa
            if md in mi or mi in md:
                return True
            # Match tramite sinonimi
            for chiave, varianti in _SINONIMI.items():
                # Se la materia del docente è questa chiave o una variante
                doc_match = chiave in md or any(v in md for v in varianti)
                # E la materia dell'import è questa chiave o una variante
                imp_match = chiave in mi or any(v in mi for v in varianti)
                if doc_match and imp_match:
                    return True
            return False

        classi = set()
        for mat in materie_coperte:
            for cls, mat_imp in tutti:
                if cls and mat_imp and _match_materie(mat, mat_imp):
                    classi.add(cls)

        classi_per_docente[rd.id] = sorted(classi)

    return render_template('recupero/vincoli.html',
        disponibili=disponibili, GIORNI=GIORNI_NOMI,
        classi_per_docente=classi_per_docente, enumerate=enumerate)


# ── ALUNNI: import XLSX ───────────────────────────────────────────────
@recupero_bp.route('/recupero/alunni', methods=['GET', 'POST'])
def alunni():
    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione == 'modifica_stato':
            imp_id = request.form.get('id')
            nuovo_stato = request.form.get('stato_adesione')
            stati_validi = ('aderisce','studio_ind','non_risposto','non_aderisce','sconosciuto')
            if imp_id and nuovo_stato in stati_validi:
                from models.recupero import RecuperoImport
                imp = RecuperoImport.query.get(int(imp_id))
                if imp:
                    imp.stato_adesione = nuovo_stato
                    db.session.commit()
            return redirect(url_for('recupero.alunni'))

        if azione == 'import':
            f = request.files.get('file_xlsx')
            if not f:
                flash('Nessun file selezionato.', 'warning')
                return redirect(url_for('recupero.alunni'))

            import pandas as pd, io
            from openpyxl import load_workbook
            from models.recupero import RecuperoImport

            file_bytes = f.read()

            # Leggi la formattazione (colori/barrato) con openpyxl
            wb = load_workbook(io.BytesIO(file_bytes))
            ws = wb.active
            # Mappa riga_excel → stato_adesione
            stati_per_riga = {}
            for i, row in enumerate(ws.iter_rows(min_row=2), start=2):
                cell = row[1]  # colonna B = cognome
                strike = cell.font.strike if cell.font else False
                fill   = cell.fill
                rgb    = fill.fgColor.rgb if fill and fill.fgColor and fill.fgColor.type == 'rgb' else None
                tema   = fill.fgColor.theme if fill and fill.fgColor and fill.fgColor.type == 'theme' else None
                if strike:
                    stato = 'non_aderisce'
                elif rgb == 'FFFF0000':
                    stato = 'non_risposto'
                elif tema == 9:
                    stato = 'aderisce'
                elif tema == 7:
                    stato = 'studio_ind'
                else:
                    stato = 'sconosciuto'
                stati_per_riga[i] = stato

            # Leggi dati con pandas (tutte le righe, non solo corso di recupero)
            df = pd.read_excel(io.BytesIO(file_bytes))

            # Svuota staging precedente
            RecuperoImport.query.filter_by(anno_scol=ANNO).delete()
            db.session.commit()

            def _primo_cognome(s):
                # "VALENA SARA" → cognome="VALENA", nome_ini="S"
                s = str(s).strip().upper()
                s = s.split(',')[0].strip()
                parts = s.split()
                return parts[0] if parts else ''

            def _primo_nome_ini(s):
                # "VALENA SARA" → "S"
                s = str(s).strip().upper()
                s = s.split(',')[0].strip()
                parts = s.split()
                return parts[1][0] if len(parts) > 1 else ''

            def _norm_materia(s):
                return str(s).strip().upper()[:100]

            inseriti = {'aderisce':0,'studio_ind':0,'non_risposto':0,'non_aderisce':0,'sconosciuto':0}
            for idx, row in df.iterrows():
                # idx è 0-based, riga excel = idx+2
                riga_excel = idx + 2
                stato = stati_per_riga.get(riga_excel, 'sconosciuto')

                classe   = str(row['classe']).strip().upper()
                cognome  = str(row['cognome']).strip().upper()
                nome     = str(row['nome']).strip()
                recupero = str(row.get('recupero','')).strip().lower()
                materia  = _norm_materia(row['materia'])
                doc_raw  = str(row.get('docente','')).strip()
                cogn_doc = _primo_cognome(doc_raw)
                cf       = str(row.get('codice_fisc','')).strip() or None
                email    = str(row.get('email','')).strip() or None
                if email and '@' not in email: email = None

                nome_ini_doc = _primo_nome_ini(doc_raw)
                db.session.add(RecuperoImport(
                    anno_scol=ANNO, classe=classe,
                    cognome=cognome, nome=nome,
                    codice_fisc=cf, email=email,
                    materia_raw=str(row['materia']).strip(),
                    materia_norm=materia,
                    docente_raw=doc_raw,
                    cognome_docente=cogn_doc,
                    nome_ini_docente=nome_ini_doc,
                    stato_adesione=stato,
                ))
                inseriti[stato] = inseriti.get(stato, 0) + 1

            db.session.commit()
            flash(
                f'Importati {sum(inseriti.values())} alunni — '
                f'✓ {inseriti["aderisce"]} aderiscono, '
                f'📚 {inseriti["studio_ind"]} studio individuale, '
                f'❓ {inseriti["non_risposto"]} non hanno risposto, '
                f'✗ {inseriti["non_aderisce"]} non aderiscono.',
                'success'
            )

        elif azione == 'elimina_tutti':
            from models.recupero import RecuperoImport
            RecuperoImport.query.filter_by(anno_scol=ANNO).delete()
            anno_ids = [rd.id for rd in RecuperoDocente.query.filter_by(anno_scol=ANNO).all()]
            gruppi_ids = [g.id for g in RecuperoGruppo.query.filter(RecuperoGruppo.id_rec_docente.in_(anno_ids)).all()]
            n = RecuperoAlunno.query.filter(RecuperoAlunno.id_gruppo.in_(gruppi_ids)).delete(synchronize_session=False)
            db.session.commit()
            flash(f'Eliminati {n} alunni e staging pulito.', 'warning')

        elif azione == 'elimina':
            aid = int(request.form['id'])
            a   = RecuperoAlunno.query.get_or_404(aid)
            db.session.delete(a)
            db.session.commit()

        return redirect(url_for('recupero.alunni'))

    # GET: mostra alunni dallo staging (RecuperoImport)
    from models.recupero import RecuperoImport
    from collections import defaultdict

    imports = (RecuperoImport.query
               .filter_by(anno_scol=ANNO)
               .order_by(RecuperoImport.materia_norm, RecuperoImport.cognome)
               .all())

    # Raggruppa per materia+docente per visualizzazione
    per_materia = defaultdict(list)
    for imp in imports:
        key = (imp.materia_norm, imp.cognome_docente)
        per_materia[key].append(imp)

    tot = len(imports)
    # Conteggi per stato
    conteggi = {'aderisce':0,'studio_ind':0,'non_risposto':0,'non_aderisce':0,'sconosciuto':0}
    for imp in imports:
        conteggi[imp.stato_adesione] = conteggi.get(imp.stato_adesione, 0) + 1

    return render_template('recupero/alunni.html',
        per_materia=per_materia, tot=tot, conteggi=conteggi)


# ── GENERA BOZZA CALENDARIO ───────────────────────────────────────────
@recupero_bp.route('/recupero/genera-bozza', methods=['POST'])
def genera_bozza():
    """
    Genera automaticamente una bozza di calendario che:
    - Rispetta i vincoli di disponibilità di ogni docente
    - Garantisce che nessun alunno abbia due lezioni sovrapposte
    - Rispetta max 2h/giorno per gruppo e max ore totali per gruppo
    """
    import json
    from datetime import timedelta

    # Elimina lezioni esistenti (solo bozza)
    conferma = request.form.get('conferma_elimina') == '1'
    if not conferma:
        flash('Seleziona la casella di conferma prima di generare la bozza.', 'warning')
        return redirect(url_for('recupero.calendario'))

    # Elimina tutte le lezioni dell'anno
    anno_ids = [rd.id for rd in RecuperoDocente.query.filter_by(anno_scol=ANNO).all()]
    gruppi_ids = [g.id for g in RecuperoGruppo.query.filter(
        RecuperoGruppo.id_rec_docente.in_(anno_ids)).all()]
    RecuperoLezione.query.filter(
        RecuperoLezione.id_gruppo.in_(gruppi_ids)).delete(synchronize_session=False)
    db.session.commit()

    gruppi = (RecuperoGruppo.query
              .join(RecuperoDocente)
              .filter(RecuperoDocente.anno_scol == ANNO)
              .all())

    # Date disponibili (lun-ven, 18/6-1/7)
    date_disp = []
    cur = DATA_INIZIO
    while cur <= DATA_FINE:
        if cur.weekday() < 5:
            date_disp.append(cur)
        cur += timedelta(days=1)

    # Slot già occupati per alunno: {(cf o nome_classe): set di (data, ora_ini, ora_fine)}
    slot_alunni = {}  # chiave: (cognome, nome, classe) → set di (data, ini_min, fin_min)

    def _t(s):
        try:
            h, m = map(int, s.split(':'))
            return h * 60 + m
        except Exception:
            return 0

    def _sovrappone(d, ini, fin, occupied):
        ini_m, fin_m = _t(ini), _t(fin)
        for od, oi, of in occupied:
            if od == d and oi < fin_m and of > ini_m:
                return True
        return False

    def _priorita_gruppo(g):
        """
        Calcola punteggio di priorità (più alto = più difficile = va schedulato prima).
        Criteri:
          1. Vincoli più stretti: meno ore disponibili totali nel periodo
          2. Numero alunni aderenti: più alunni = più urgente
          3. Numero di vincoli: più vincoli = meno flessibilità
        """
        vincoli = g.docente_rec.vincoli if g.docente_rec else []

        # Ore disponibili totali nel periodo = somma delle finestre orarie per data
        ore_disp_totali = 0.0
        giorni_disp = set()
        for data in date_disp:
            wd = data.weekday()
            for v in vincoli:
                if v.data_inizio and data < v.data_inizio: continue
                if v.data_fine   and data > v.data_fine:   continue
                if v.giorno is not None and v.giorno != wd: continue
                try:
                    h1,m1 = map(int,v.ora_inizio.split(':'))
                    h2,m2 = map(int,v.ora_fine.split(':'))
                    ore_disp_totali += (h2*60+m2 - h1*60-m1) / 60
                    giorni_disp.add(data)
                except Exception:
                    pass
        if not vincoli:
            # Nessun vincolo = massima disponibilità → bassa priorità
            ore_disp_totali = 999
            giorni_disp = set(date_disp)

        n_alunni   = len(g.alunni)
        n_vincoli  = len(vincoli)

        # Score: meno ore disponibili → score alto; più alunni → score alto
        # Usiamo inverso delle ore disponibili normalizzato
        score_ore      = 1.0 / (ore_disp_totali + 1)    # alto se poche ore
        score_alunni   = n_alunni / 50.0                  # normalizzato su 50
        score_vincoli  = n_vincoli / 20.0                 # normalizzato su 20

        # Peso: ore_disponibili conta di più
        return score_ore * 3 + score_alunni * 2 + score_vincoli * 1

    # Ordina gruppi: priorità decrescente (più difficile prima)
    gruppi_ordinati = sorted(gruppi, key=_priorita_gruppo, reverse=True)

    inserite = 0
    saltati  = []
    # Tracking slot occupati per docente: {id_rec_docente: {data: fine_ultima_lezione_min}}
    slot_docente = {}
    for g in gruppi_ordinati:
        vincoli_doc = g.docente_rec.vincoli
        ha_vincoli = bool(vincoli_doc)

        def _slot_per_data(data):
            # Restituisce [(ora_ini, ora_fine)] validi per questa data e questo gruppo
            wd = data.weekday()
            if not ha_vincoli:
                return [('08:00','13:00')]
            classi_gruppo = {c.strip().upper() for c in g.classi.split(',')}
            slots = []
            for v in vincoli_doc:
                # Controlla vincolo date
                if v.data_inizio and data < v.data_inizio: continue
                if v.data_fine   and data > v.data_fine:   continue
                # Controlla giorno
                if v.giorno is not None and v.giorno != wd: continue
                # Controlla vincolo classi
                if v.classi_vincolo:
                    classi_v = {cv.strip().upper() for cv in v.classi_vincolo.split(',')}
                    if not classi_gruppo.intersection(classi_v):
                        continue
                # Controlla vincolo materia
                if v.materia_vincolo:
                    mat_v = v.materia_vincolo.strip().upper()
                    mat_g = g.materia.strip().upper()
                    if mat_v not in mat_g and mat_g not in mat_v:
                        continue
                slots.append((v.ora_inizio, v.ora_fine))
            return slots if slots else []

        max_ore_tot  = g.max_ore or 10
        max_ore_g    = g.max_ore_giorno or 2
        ore_pian     = 0
        ore_per_data = {}

        alunni_g = g.alunni

        for data in date_disp:
            if ore_pian >= max_ore_tot:
                break
            wd = data.weekday()
            ore_ok = _slot_per_data(data)
            if not ore_ok:
                continue

            ore_oggi = ore_per_data.get(data, 0)
            if ore_oggi >= max_ore_g:
                continue

            # Prova ogni fascia disponibile per questo giorno
            for fascia_ini, fascia_fin in ore_ok:
                fascia_durata = (_t(fascia_fin) - _t(fascia_ini)) / 60
                if fascia_durata <= 0:
                    continue

                durata_h = min(fascia_durata, max_ore_g - ore_oggi,
                               max_ore_tot - ore_pian, 2)
                if durata_h <= 0:
                    continue

                # Ora di inizio: dopo l'ultima lezione del docente in questa data
                doc_id = g.id_rec_docente
                fine_doc = slot_docente.get(doc_id, {}).get(data, _t(fascia_ini))
                # Se il docente ha già una lezione, inizia subito dopo (con pausa 30min)
                if fine_doc > _t(fascia_ini):
                    ini_m = fine_doc + 30
                else:
                    ini_m = _t(fascia_ini)

                # Verifica che rimanga dentro la fascia
                fin_max = _t(fascia_fin)
                durata_m = int(durata_h * 60)
                if ini_m + durata_m > fin_max:
                    continue

                ini = f'{ini_m // 60:02d}:{ini_m % 60:02d}'
                fin_m_val = ini_m + durata_m
                fin = f'{fin_m_val // 60:02d}:{fin_m_val % 60:02d}'

                # Verifica no sovrapposizione alunni
                conflitto = False
                for al in alunni_g:
                    key = (al.cognome, al.nome, al.classe)
                    if _sovrappone(data, ini, fin, slot_alunni.get(key, set())):
                        conflitto = True
                        break

                if conflitto:
                    continue

                db.session.add(RecuperoLezione(
                    id_gruppo=g.id, data=data,
                    ora_inizio=ini, ora_fine=fin,
                ))
                ore_pian += durata_h
                ore_per_data[data] = ore_per_data.get(data, 0) + durata_h
                inserite += 1

                # Aggiorna slot alunni e slot docente
                for al in alunni_g:
                    key = (al.cognome, al.nome, al.classe)
                    slot_alunni.setdefault(key, set()).add((data, ini_m, fin_m_val))
                slot_docente.setdefault(doc_id, {})[data] = fin_m_val
                break  # una fascia per giorno per questo gruppo

                break  # già gestito sotto
            else:
                # Nessuna fascia andata a buon fine per questa data → continua
                pass

        if ore_pian == 0:
            saltati.append(g)

    db.session.commit()

    msg = f'Bozza generata: {inserite} lezioni inserite.'
    if saltati:
        nomi = ', '.join(f'{g.materia[:20]} ({g.docente.cognome if g.docente else "?"})' for g in saltati)
        msg += f' ⚠ {len(saltati)} gruppi senza slot: {nomi}.'
    flash(msg, 'success' if not saltati else 'warning')
    return redirect(url_for('recupero.calendario'))


# ── TABELLA STAGING IMPORT ────────────────────────────────────────────
# (usata da proposte e import alunni)

# ── PROPOSTE GRUPPI DA RECUPERI IMPORTATI ────────────────────────────
@recupero_bp.route('/recupero/proposte')
def proposte():
    from collections import defaultdict
    from models.recupero import RecuperoImport

    imports = RecuperoImport.query.filter_by(anno_scol=ANNO).all()
    disponibili = (RecuperoDocente.query.filter_by(anno_scol=ANNO)
                   .join(Docente).order_by(Docente.cognome).all())

    if not imports:
        return render_template('recupero/proposte.html',
            proposte=[], disponibili=disponibili, anno=ANNO)

    per_gruppo = defaultdict(lambda: {
        'classi': set(), 'alunni': [], 'docente_raw': '',
        'n_non_risposto': 0, 'n_non_aderisce': 0
    })
    for imp in imports:
        key = (imp.materia_norm, imp.cognome_docente)
        per_gruppo[key]['classi'].add(imp.classe)
        per_gruppo[key]['alunni'].append(imp)
        per_gruppo[key]['docente_raw'] = imp.docente_raw
        if imp.stato_adesione == 'non_risposto':
            per_gruppo[key]['n_non_risposto'] += 1
        elif imp.stato_adesione == 'non_aderisce':
            per_gruppo[key]['n_non_aderisce'] += 1

    def trova_disponibile(cognome_doc, nome_ini=''):
        cogn = cognome_doc.upper()
        ini  = nome_ini.upper()
        # Match preciso cognome + iniziale
        if ini:
            for rd in disponibili:
                rc = rd.docente.cognome.upper()
                rn_ini = (rd.docente.nome or '').strip().upper()[:1]
                if rc == cogn and rn_ini == ini:
                    return rd
        # Fallback solo cognome se non ambiguo
        trovati = [rd for rd in disponibili if rd.docente.cognome.upper() == cogn]
        if len(trovati) == 1:
            return trovati[0]
        # Ultimo tentativo: cognome contenuto
        for rd in disponibili:
            if rd.docente.cognome.upper() in cogn or cogn in rd.docente.cognome.upper():
                return rd
        return None

    gruppi_esistenti = {}
    for g in (RecuperoGruppo.query.join(RecuperoDocente)
              .filter(RecuperoDocente.anno_scol == ANNO).all()):
        gruppi_esistenti[(g.materia.upper(), g.id_rec_docente)] = g

    proposte_list = []
    for (materia, cogn_doc), dati in sorted(per_gruppo.items()):
        rd_sug = trova_disponibile(cogn_doc)
        alunni_aderiscono = [a for a in dati['alunni']
                              if a.stato_adesione in ('aderisce','sconosciuto','studio_ind')]
        proposte_list.append({
            'materia':          materia,
            'docente_raw':      dati['docente_raw'],
            'cognome_doc':      cogn_doc,
            'classi':           ', '.join(sorted(dati['classi'])),
            'n_alunni':         len(alunni_aderiscono),
            'n_tot':            len(dati['alunni']),
            'n_non_risposto':   dati['n_non_risposto'],
            'n_non_aderisce':   dati['n_non_aderisce'],
            'rd_suggerito':     rd_sug,
            'gruppo_esistente': gruppi_esistenti.get(
                (materia.upper(), rd_sug.id)) if rd_sug else None,
        })

    return render_template('recupero/proposte.html',
        proposte=proposte_list, disponibili=disponibili, anno=ANNO)


@recupero_bp.route('/recupero/proposte/crea', methods=['POST'])
def crea_da_proposta():
    from models.recupero import RecuperoImport

    materia     = request.form.get('materia','').strip()
    cognome_doc = request.form.get('cognome_doc','').strip()
    classi      = request.form.get('classi','').strip()
    id_recdoc   = int(request.form['id_rec_docente'])
    max_ore     = int(request.form.get('max_ore', 10) or 10)
    max_ore_g   = int(request.form.get('max_ore_giorno', 2) or 2)

    # Permette gruppi multipli per stessa materia+docente (turni)
    g = RecuperoGruppo(
        id_rec_docente=id_recdoc, materia=materia,
        classi=classi, max_ore=max_ore, max_ore_giorno=max_ore_g,
    )
    db.session.add(g)
    db.session.flush()
    flash(f'Gruppo creato: {materia} ({classi}).', 'success')

    imports = RecuperoImport.query.filter_by(
        anno_scol=ANNO, materia_norm=materia,
        cognome_docente=cognome_doc).all()

    for imp in imports:
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
    return redirect(url_for('recupero.proposte'))


# ── VERIFICA COPERTURA ────────────────────────────────────────────────
def _export_copertura_xlsx(righe, titolo):
    from openpyxl import Workbook
    from openpyxl.styles import (Font, PatternFill, Alignment,
                                  Border, Side, PatternFill)
    from openpyxl.utils import get_column_letter
    import io

    wb = Workbook()
    ws = wb.active
    ws.title = 'Copertura'

    # Stili
    BLU     = '1e3a5f'
    VERDE   = 'dcfce7'; VERDE_T  = '166534'
    ROSSO   = 'fee2e2'; ROSSO_T  = 'dc2626'
    GIALLO  = 'fef9c3'; GIALLO_T = '92400e'
    GRIGIO  = 'f3f4f6'

    def fill(hex_bg):
        return PatternFill('solid', start_color=hex_bg, fgColor=hex_bg)
    def border():
        s = Side(style='thin', color='d1d5db')
        return Border(left=s, right=s, top=s, bottom=s)
    def hdr_font():
        return Font(bold=True, color='FFFFFF', name='Arial', size=9)
    def cell_font(bold=False, color='000000'):
        return Font(bold=bold, color=color, name='Arial', size=9)

    # Riga titolo
    ws.merge_cells('A1:H1')
    ws['A1'] = titolo or 'Verifica copertura recuperi'
    ws['A1'].font = Font(bold=True, color='FFFFFF', name='Arial', size=12)
    ws['A1'].fill = fill(BLU)
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 22

    # Intestazioni
    hdrs = ['Classe', 'Cognome', 'Nome', 'Materia', 'Docente assegnante',
            'Gruppo abbinato', 'Stato', 'Firma']
    for col, h in enumerate(hdrs, 1):
        cell = ws.cell(row=2, column=col, value=h)
        cell.font   = hdr_font()
        cell.fill   = fill(BLU)
        cell.alignment = Alignment(horizontal='center', vertical='center',
                                   wrap_text=True)
        cell.border = border()
    ws.row_dimensions[2].height = 18

    # Colori per stato
    GRIGIO2  = 'f3f4f6'; GRIGIO2_T = '6b7280'
    STATO_CFG = {
        'ok':           (VERDE,   VERDE_T,   '✓ ok'),
        'no_gruppo':    (ROSSO,   ROSSO_T,   '✗ no gruppo'),
        'non_iscritto': (ROSSO,   ROSSO_T,   '❓ non iscritto'),
        'no_corso':     (GIALLO,  GIALLO_T,  '📚 no corso'),
        'non_aderisce': (GRIGIO2, GRIGIO2_T, '✗ non aderisce'),
    }

    for i, r in enumerate(righe, 3):
        stato = r.get('stato', '')
        bg, fg, label = STATO_CFG.get(stato, (GRIGIO, '374151', stato))

        vals = [
            r['imp'].classe,
            r['imp'].cognome,
            r['imp'].nome,
            r['imp'].materia_raw[:60] if r['imp'].materia_raw else '',
            r['imp'].docente_raw[:40] if r['imp'].docente_raw else '',
            (r['gruppo'].materia[:35] + ' — ' + (r['gruppo'].docente.cognome if r['gruppo'] and r['gruppo'].docente else ''))
                if r.get('gruppo') else '',
            label,
            '',  # Firma (vuoto per foglio firme)
        ]

        row_fill = fill(bg) if stato != 'ok' else None

        for col, val in enumerate(vals, 1):
            cell = ws.cell(row=i, column=col, value=val)
            cell.border = border()
            cell.alignment = Alignment(vertical='center', wrap_text=(col == 4))
            if col == 7:  # Stato
                cell.font = Font(bold=True, color=fg, name='Arial', size=9)
                cell.fill = fill(bg)
                cell.alignment = Alignment(horizontal='center', vertical='center')
            elif col == 8:  # Firma
                cell.fill = fill('FFFFFF')
            else:
                cell.font = cell_font(bold=(col == 2))
                if row_fill:
                    cell.fill = fill(GRIGIO)
        ws.row_dimensions[i].height = 15

    # Larghezze colonne
    widths = [8, 18, 16, 35, 28, 30, 14, 18]
    for col, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(col)].width = w

    # Freeze intestazioni
    ws.freeze_panes = 'A3'

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


@recupero_bp.route('/recupero/copertura')
def copertura():
    from models.recupero import RecuperoImport
    from collections import defaultdict
    from flask import send_file

    # Tutti gli alunni importati
    imports = RecuperoImport.query.filter_by(anno_scol=ANNO).order_by(
        RecuperoImport.cognome, RecuperoImport.nome,
        RecuperoImport.materia_norm).all()

    if not imports:
        return render_template('recupero/copertura.html',
            righe=[], n_ok=0, n_no=0, n_no_gruppo=0)

    # Mappa alunno+materia → gruppo → lezioni
    righe = []
    n_ok = n_no = n_no_gruppo = 0

    # Famiglie sinonimi per copertura
    _FAM_COV = [
        {'LATINO', 'LINGUA LATINA', 'LINGUA E CULTURA LATINA'},
        {'ITALIANO', 'LINGUA E LETTERATURA ITALIANA', 'LINGUA E CULTURA ITALIANA'},
        {'MATEMATICA', 'MATEMATICA CON INFORMATICA', 'MATEMATICA E COMPLEMENTI DI MATEMATICA'},
        {'STORIA', 'STORIA E GEOGRAFIA'},
        {'FISICA', 'SCIENZE INTEGRATE (FISICA)'},
        {'INGLESE', 'LINGUA INGLESE', 'LINGUA E CULTURA STRANIERA (INGLESE)'},
        {'TEDESCO', 'LINGUA TEDESCA', 'LINGUA E CULTURA STRANIERA TEDESCO'},
    ]
    def _match_cov(m1, m2):
        m1u,m2u = m1.strip().upper(), m2.strip().upper()
        if m1u == m2u: return True
        for f in _FAM_COV:
            fs = {x.upper() for x in f}
            if m1u in fs and m2u in fs: return True
        return False

    tutti_gruppi_cov = (RecuperoGruppo.query.join(RecuperoDocente)
                        .filter(RecuperoDocente.anno_scol == ANNO).all())

    n_ok = n_no_corso = n_no_iscritto = n_no_gruppo = 0

    for imp in imports:
        # Determina stato in base al colore nel file originale
        adesione = imp.stato_adesione  # aderisce|studio_ind|non_risposto|non_aderisce|sconosciuto

        # Rosso (non_risposto) → non iscritto: non ha risposto, non possiamo contarci
        if adesione == 'non_risposto':
            stato = 'non_iscritto'
            n_no_iscritto += 1
            righe.append({'imp': imp, 'gruppo': None, 'stato': stato, 'n_lezioni': 0})
            continue

        # Giallo (studio_ind) → no corso: ha scelto studio individuale
        if adesione == 'studio_ind':
            stato = 'no_corso'
            n_no_corso += 1
            righe.append({'imp': imp, 'gruppo': None, 'stato': stato, 'n_lezioni': 0})
            continue

        # Barrato (non_aderisce) → includi con stato dedicato
        if adesione == 'non_aderisce':
            righe.append({'imp': imp, 'gruppo': None, 'stato': 'non_aderisce', 'n_lezioni': 0})
            continue

        # Verde (aderisce|sconosciuto) → cerca gruppo
        gruppo = None
        for g in tutti_gruppi_cov:
            if not _match_cov(g.materia, imp.materia_norm or ''): continue
            classi_g = {cl.strip().upper() for cl in g.classi.split(',')}
            if imp.classe.upper() in classi_g:
                gruppo = g
                break

        n_lezioni = len(gruppo.lezioni) if gruppo else 0

        if not gruppo:
            stato = 'no_gruppo'
            n_no_gruppo += 1
        else:
            stato = 'ok'
            n_ok += 1

        righe.append({'imp': imp, 'gruppo': gruppo, 'stato': stato, 'n_lezioni': n_lezioni})

    # Export XLSX
    titolo = request.args.get('titolo', 'Verifica copertura recuperi')
    if request.args.get('export') == 'xlsx':
        buf = _export_copertura_xlsx(righe, titolo)
        return send_file(
            buf,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='copertura_recuperi.xlsx'
        )

    n_non_aderisce = sum(1 for r in righe if r['stato'] == 'non_aderisce')
    return render_template('recupero/copertura.html',
        righe=righe, n_ok=n_ok,
        n_no_corso=n_no_corso,
        n_no_iscritto=n_no_iscritto,
        n_no_gruppo=n_no_gruppo,
        n_non_aderisce=n_non_aderisce)


# ══════════════════════════════════════════════════════════════════════
# PROVE DI AGOSTO
# ══════════════════════════════════════════════════════════════════════

ANNO_AGO     = '2025-2026'
PERIODO_AGO  = 'prove_agosto'
CONTRATTI_OK = ('TI', 'TD_annuale', 'TD_GS')  # TI + TD annuale/GS (fine agosto)

TIPO_PROVA_LABEL = {
    'scritto':       '✏️ Scritto',
    'orale':         '🗣 Orale',
    'pratico':       '🔧 Pratico',
    'scritto_orale': '✏️🗣 Scritto + Orale',
}


def _parse_tipo_prova(s):
    """Normalizza il tipo prova dal file registro."""
    s = str(s).strip().lower()
    if 'orale' in s and 'scritt' in s:
        return 'scritto_orale'
    if 'orale' in s:
        return 'orale'
    if 'pratico' in s or 'pratica' in s:
        return 'pratico'
    return 'scritto'


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


@recupero_bp.route('/recupero/agosto/proposte')
def agosto_proposte():
    """Proposte gruppi prove da recuperi importati (tutti, non solo corsi)."""
    from collections import defaultdict
    from models.recupero import RecuperoImport

    imports = RecuperoImport.query.filter_by(anno_scol=ANNO_AGO).all()
    disponibili = (RecuperoDocente.query.filter_by(anno_scol=ANNO_AGO)
                   .join(Docente).order_by(Docente.cognome).all())

    if not imports:
        return render_template('recupero/agosto_proposte.html',
            proposte=[], disponibili=[], anno=ANNO_AGO)

    per_gruppo = defaultdict(lambda: {
        'classi': set(), 'alunni': [], 'docente_raw': '',
        'tipo_prova': 'scritto'
    })
    for imp in imports:
        key = (imp.materia_norm, imp.cognome_docente)
        per_gruppo[key]['classi'].add(imp.classe)
        per_gruppo[key]['alunni'].append(imp)
        per_gruppo[key]['docente_raw'] = imp.docente_raw
        # tipo prova dal file
        if hasattr(imp, 'tipo_prova_raw') and imp.tipo_prova_raw:
            per_gruppo[key]['tipo_prova'] = _parse_tipo_prova(imp.tipo_prova_raw)

    def trova_disponibile(cognome_doc):
        for rd in disponibili:
            if rd.docente.cognome.upper() in cognome_doc.upper():
                return rd
        return None

    gruppi_esistenti = {
        (g.materia.upper(), g.id_rec_docente): g
        for g in RecuperoGruppo.query
            .join(RecuperoDocente)
            .filter(RecuperoDocente.anno_scol == ANNO_AGO,
                    RecuperoGruppo.periodo_codice == PERIODO_AGO).all()
    }

    proposte_list = []
    for (materia, cogn_doc), dati in sorted(per_gruppo.items()):
        ini_doc = ''
        if dati['alunni']: ini_doc = getattr(dati['alunni'][0],'nome_ini_docente','') or ''
        rd_sug = trova_disponibile(cogn_doc, ini_doc)
        proposte_list.append({
            'materia':          materia,
            'docente_raw':      dati['docente_raw'],
            'cognome_doc':      cogn_doc,
            'classi':           ', '.join(sorted(dati['classi'])),
            'n_alunni':         len(dati['alunni']),
            'tipo_prova':       dati['tipo_prova'],
            'rd_suggerito':     rd_sug,
            'gruppo_esistente': gruppi_esistenti.get(
                (materia.upper(), rd_sug.id)) if rd_sug else None,
        })

    return render_template('recupero/agosto_proposte.html',
        proposte=proposte_list, disponibili=disponibili,
        TIPO_PROVA_LABEL=TIPO_PROVA_LABEL, anno=ANNO_AGO)


@recupero_bp.route('/recupero/agosto/proposte/crea', methods=['POST'])
def agosto_crea_da_proposta():
    from models.recupero import RecuperoImport

    materia     = request.form.get('materia', '').strip()
    cognome_doc = request.form.get('cognome_doc', '').strip()
    classi      = request.form.get('classi', '').strip()
    id_recdoc   = int(request.form['id_rec_docente'])
    tipo_prova  = request.form.get('tipo_prova', 'scritto')
    durata_ore  = float(request.form.get('durata_ore', 2.0) or 2.0)

    esistente = RecuperoGruppo.query.filter_by(
        id_rec_docente=id_recdoc, materia=materia,
        periodo_codice=PERIODO_AGO).first()

    if esistente:
        esistente.classi     = classi
        esistente.tipo_prova = tipo_prova
        esistente.durata_ore = durata_ore
        g = esistente
        flash(f'Gruppo aggiornato: {materia}.', 'info')
    else:
        g = RecuperoGruppo(
            id_rec_docente=id_recdoc, materia=materia,
            classi=classi, periodo_codice=PERIODO_AGO,
            tipo_prova=tipo_prova, durata_ore=durata_ore,
            max_ore=durata_ore, max_ore_giorno=durata_ore,
        )
        db.session.add(g)
        db.session.flush()
        flash(f'Gruppo creato: {materia}.', 'success')

    # Collega alunni — tutti (non solo corso di recupero)
    imports = RecuperoImport.query.filter_by(
        anno_scol=ANNO_AGO, materia_norm=materia,
        cognome_docente=cognome_doc).all()

    for imp in imports:
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
    return redirect(url_for('recupero.agosto_proposte'))


@recupero_bp.route('/recupero/agosto/calendario', methods=['GET', 'POST'])
def agosto_calendario():
    from models.recupero import RecuperoPeriodo
    from datetime import timedelta

    periodo = RecuperoPeriodo.query.filter_by(
        anno_scol=ANNO_AGO, codice=PERIODO_AGO).first()

    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione == 'aggiungi':
            id_gruppo  = int(request.form['id_gruppo'])
            data_str   = request.form.get('data', '')
            ora_inizio = request.form.get('ora_inizio', '08:00')
            ora_fine   = request.form.get('ora_fine', '10:00')
            id_comm    = request.form.get('id_commissario') or None
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
                    # Conflitto docenti (titolare + commissario + sorvegliante)
                    doc_ids_g  = set(filter(None,[g.id_rec_docente,g.id_commissario,g.id_sorvegliante]))
                    doc_ids_ag = set(filter(None,[ag.id_rec_docente,ag.id_commissario,ag.id_sorvegliante]))
                    comuni_doc = doc_ids_g & doc_ids_ag
                    for did in comuni_doc:
                        from models import Docente as _D
                        d = _D.query.get(did)
                        errori.append(f'👨‍🏫 {d.cognome if d else "?"} già impegnato in {ag.materia[:15]}')

            if errori:
                flash('⚠ NON salvato — ' + ' | '.join(errori[:3]), 'danger')
                return redirect(url_for('recupero.agosto_calendario'))

            # Aggiorna commissario sul gruppo
            if id_comm:
                g.id_commissario = int(id_comm)

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
        # Conflitto docente (include titolare, commissario e sorvegliante)
        doc_ll = {}
        for l,g in coppie:
            for doc_id in filter(None, [g.id_rec_docente, g.id_commissario, g.id_sorvegliante]):
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

    # Docenti validi per commissario
    commissari_validi = Docente.query.filter(
        Docente.attivo == True,
        Docente.tipo_contratto.in_(CONTRATTI_OK)
    ).order_by(Docente.cognome).all()

    return render_template('recupero/agosto_calendario.html',
        periodo=periodo, gruppi=gruppi,
        date_disponibili=date_disp,
        lezioni_per_data=lezioni_per_data,
        commissari_validi=commissari_validi,
        TIPO_PROVA_LABEL=TIPO_PROVA_LABEL,
        conflitti=conflitti_ago,
        conflitti_ids=conflitti_ids_ago)


def _genera_bozza_agosto():
    """Genera bozza calendario prove agosto."""
    from datetime import timedelta
    from models.recupero import RecuperoPeriodo

    periodo = RecuperoPeriodo.query.filter_by(
        anno_scol=ANNO_AGO, codice=PERIODO_AGO).first()
    if not periodo:
        return

    gruppi = (RecuperoGruppo.query
              .join(RecuperoDocente)
              .filter(RecuperoDocente.anno_scol == ANNO_AGO,
                      RecuperoGruppo.periodo_codice == PERIODO_AGO).all())

    # Elimina lezioni esistenti
    for g in gruppi:
        RecuperoLezione.query.filter_by(id_gruppo=g.id).delete()
    db.session.commit()

    # Date: 24-27 agosto per scritti, 28 per orali
    date_scritti = []
    date_orali   = []
    cur = periodo.data_inizio
    while cur <= periodo.data_fine:
        if cur.weekday() < 5:
            if cur == periodo.data_fine:
                date_orali.append(cur)
            else:
                date_scritti.append(cur)
        cur += timedelta(days=1)

    def _t(s):
        try: h,m = map(int,s.split(':')); return h*60+m
        except: return 0

    # Slot occupati: {data: [(ini_min, fin_min, id_gruppo)]}
    slot_per_data = {}
    # Slot alunni: {(cogn, nome, classe): set di (data, ini, fin)}
    slot_alunni = {}

    def _libero_per_alunni(data, ini, fin, g):
        ini_m, fin_m = _t(ini), _t(fin)
        for al in g.alunni:
            key = (al.cognome, al.nome, al.classe)
            for od, oi, of in slot_alunni.get(key, set()):
                if od == data and oi < fin_m and of > ini_m:
                    return False
        return True

    for g in sorted(gruppi, key=lambda x: x.materia):
        tipo = g.tipo_prova or 'scritto'
        durata_h = g.durata_ore or 2.0
        durata_m = int(durata_h * 60)

        # Scegli pool date
        date_pool = date_orali if tipo == 'orale' else date_scritti

        # Ora di inizio: parto da 08:00 e cerco slot libero
        ora_ini_base_m = _t(periodo.ora_inizio)
        ora_fin_max_m  = _t(periodo.ora_fine)

        assegnata = False
        for data in date_pool:
            # Cerca primo slot libero nella giornata
            occupati = slot_per_data.get(data, [])
            occupati_sorted = sorted(occupati, key=lambda x: x[0])

            ini_m = ora_ini_base_m
            while ini_m + durata_m <= ora_fin_max_m:
                fin_m = ini_m + durata_m
                # Conflitto con altri gruppi stessa data?
                sovr = any(oi < fin_m and of > ini_m
                           for oi, of, _ in occupati_sorted)
                if sovr:
                    ini_m = max(of for oi, of, _ in occupati_sorted if of > ini_m)
                    continue
                # Conflitto alunni?
                ini_s = f'{ini_m//60:02d}:{ini_m%60:02d}'
                fin_s = f'{fin_m//60:02d}:{fin_m%60:02d}'
                if not _libero_per_alunni(data, ini_s, fin_s, g):
                    ini_m += 30
                    continue

                # Slot trovato
                db.session.add(RecuperoLezione(
                    id_gruppo=g.id, data=data,
                    ora_inizio=ini_s, ora_fine=fin_s,
                ))
                slot_per_data.setdefault(data, []).append((ini_m, fin_m, g.id))
                for al in g.alunni:
                    key = (al.cognome, al.nome, al.classe)
                    slot_alunni.setdefault(key, set()).add((data, ini_m, fin_m))

                # Proponi commissario (titolare materia corso di recupero se disponibile)
                # e sorvegliante (secondo docente libero)
                commissario, sorvegliante = _suggerisci_docenti_agosto(g, data, ini_s, fin_s)
                if commissario:
                    g.id_commissario = commissario.id
                if sorvegliante:
                    g.id_sorvegliante = sorvegliante.id

                assegnata = True
                break

            if assegnata:
                break

    db.session.commit()


def _suggerisci_docenti_agosto(gruppo, data, ora_ini, ora_fine):
    """
    Propone commissario e sorvegliante per una prova agosto.
    Commissario: preferibilmente il docente che ha svolto il corso di recupero
    (stesso cognome + materia), poi chiunque libero.
    Sorvegliante: secondo docente libero diverso dal commissario.
    Entrambi devono essere TI o TD_annuale/TD_GS.
    """
    def _t(s):
        try: h,m = map(int,s.split(':')); return h*60+m
        except: return 0

    ini_m, fin_m = _t(ora_ini), _t(ora_fine)
    titolare_id = gruppo.docente_rec.id_docente if gruppo.docente_rec else None

    def _doc_libero(escludi_ids):
        for d in Docente.query.filter(
            Docente.attivo==True,
            Docente.tipo_contratto.in_(CONTRATTI_OK),
            ~Docente.id.in_(escludi_ids)
        ).order_by(Docente.cognome).all():
            impegnato = False
            # Controlla commissario
            for g2 in RecuperoGruppo.query.filter_by(
                    id_commissario=d.id, periodo_codice=PERIODO_AGO).all():
                for l in g2.lezioni:
                    if l.data==data and _t(l.ora_inizio)<fin_m and _t(l.ora_fine)>ini_m:
                        impegnato=True; break
                if impegnato: break
            if impegnato: continue
            # Controlla sorvegliante
            for g2 in RecuperoGruppo.query.filter_by(
                    id_sorvegliante=d.id, periodo_codice=PERIODO_AGO).all():
                for l in g2.lezioni:
                    if l.data==data and _t(l.ora_inizio)<fin_m and _t(l.ora_fine)>ini_m:
                        impegnato=True; break
                if impegnato: break
            if impegnato: continue
            # Controlla se è titolare in altra prova nello stesso slot
            for g2 in RecuperoGruppo.query.join(RecuperoDocente).filter(
                    RecuperoDocente.id_docente==d.id,
                    RecuperoGruppo.periodo_codice==PERIODO_AGO).all():
                for l in g2.lezioni:
                    if l.data==data and _t(l.ora_inizio)<fin_m and _t(l.ora_fine)>ini_m:
                        impegnato=True; break
                if impegnato: break
            if not impegnato:
                return d
        return None

    # Trova commissario: preferibilmente il docente del corso giugno
    commissario = None
    escludi = set(filter(None, [titolare_id]))

    # Prima prova: docente che ha fatto il recupero giugno (stesso cognome, stessa materia)
    if gruppo.docente_rec:
        cogn_titolare = gruppo.docente_rec.docente.cognome.upper() if gruppo.docente_rec.docente else ''
        for d in Docente.query.filter(
            Docente.attivo==True,
            Docente.tipo_contratto.in_(CONTRATTI_OK),
            Docente.id != titolare_id
        ).all():
            if d.cognome.upper() == cogn_titolare:
                # È lo stesso docente del recupero giugno (diverso ruolo)
                # Verifica disponibilità
                test = _doc_libero({titolare_id} - {d.id} | escludi - {d.id})
                if test and test.id == d.id:
                    commissario = d
                    break

    if not commissario:
        commissario = _doc_libero(escludi)

    escludi_sorv = set(filter(None, [titolare_id, commissario.id if commissario else None]))
    sorvegliante = _doc_libero(escludi_sorv)

    return commissario, sorvegliante


@recupero_bp.route('/recupero/agosto/commissario', methods=['POST'])
def agosto_set_commissario():
    """Aggiorna commissario e/o sorvegliante di un gruppo agosto."""
    id_gruppo = int(request.form['id_gruppo'])
    g = RecuperoGruppo.query.get_or_404(id_gruppo)
    if 'id_commissario' in request.form:
        id_comm = request.form.get('id_commissario') or None
        g.id_commissario = int(id_comm) if id_comm else None
    if 'id_sorvegliante' in request.form:
        id_sorv = request.form.get('id_sorvegliante') or None
        g.id_sorvegliante = int(id_sorv) if id_sorv else None
    db.session.commit()
    return redirect(url_for('recupero.agosto_calendario'))


# ── COPERTURA AGOSTO ──────────────────────────────────────────────────
@recupero_bp.route('/recupero/agosto/copertura')
def agosto_copertura():
    from models.recupero import RecuperoImport
    from flask import send_file

    imports = RecuperoImport.query.filter_by(anno_scol=ANNO_AGO).order_by(
        RecuperoImport.materia_norm, RecuperoImport.cognome).all()

    tutti_gruppi_cov = (RecuperoGruppo.query.join(RecuperoDocente)
                        .filter(RecuperoDocente.anno_scol == ANNO_AGO,
                                RecuperoGruppo.periodo_codice == PERIODO_AGO).all())

    _FAM_COV_AGO = [
        {'LATINO', 'LINGUA LATINA', 'LINGUA E CULTURA LATINA'},
        {'ITALIANO', 'LINGUA E LETTERATURA ITALIANA', 'LINGUA E CULTURA ITALIANA'},
        {'MATEMATICA', 'MATEMATICA CON INFORMATICA', 'MATEMATICA E COMPLEMENTI DI MATEMATICA'},
        {'STORIA', 'STORIA E GEOGRAFIA'},
        {'FISICA', 'SCIENZE INTEGRATE (FISICA)'},
        {'INGLESE', 'LINGUA INGLESE', 'LINGUA E CULTURA STRANIERA (INGLESE)'},
        {'TEDESCO', 'LINGUA TEDESCA', 'LINGUA E CULTURA STRANIERA TEDESCO'},
    ]
    def _match_cov_ago(m1, m2):
        m1u,m2u = m1.strip().upper(), m2.strip().upper()
        if m1u == m2u: return True
        for f in _FAM_COV_AGO:
            fs = {x.upper() for x in f}
            if m1u in fs and m2u in fs: return True
        return False

    righe = []
    n_ok = n_no_corso = n_no_iscritto = n_no_gruppo = 0

    for imp in imports:
        # Per agosto: tutti gli alunni sospesi vanno considerati
        # indipendentemente dallo stato_adesione
        adesione = imp.stato_adesione

        if adesione == 'studio_ind':
            stato = 'no_corso'; n_no_corso += 1
            righe.append({'imp': imp, 'gruppo': None, 'stato': stato, 'n_lezioni': 0})
            continue
        if adesione == 'non_aderisce':
            righe.append({'imp': imp, 'gruppo': None, 'stato': 'non_aderisce', 'n_lezioni': 0})
            continue

        gruppo = None
        for g in tutti_gruppi_cov:
            if not _match_cov_ago(g.materia, imp.materia_norm or ''): continue
            classi_g = {cl.strip().upper() for cl in g.classi.split(',')}
            if imp.classe.upper() in classi_g:
                gruppo = g; break

        n_lezioni = len(gruppo.lezioni) if gruppo else 0

        if not gruppo:
            stato = 'no_gruppo'; n_no_gruppo += 1
        else:
            stato = 'ok'; n_ok += 1

        righe.append({'imp': imp, 'gruppo': gruppo, 'stato': stato, 'n_lezioni': n_lezioni})

    n_non_aderisce = sum(1 for r in righe if r['stato'] == 'non_aderisce')

    if request.args.get('export') == 'xlsx':
        buf = _export_copertura_xlsx(righe, 'Verifica copertura prove agosto')
        return send_file(buf,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True, download_name='copertura_agosto.xlsx')

    return render_template('recupero/copertura.html',
        righe=righe, n_ok=n_ok,
        n_no_corso=n_no_corso,
        n_no_iscritto=n_no_iscritto,
        n_no_gruppo=n_no_gruppo,
        n_non_aderisce=n_non_aderisce,
        titolo='Verifica copertura prove agosto',
        back_url=url_for('recupero.agosto_index'))


# ── EXPORT XLSX AGOSTO ────────────────────────────────────────────────
@recupero_bp.route('/recupero/agosto/export-xlsx')
def agosto_export_xlsx():
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from flask import send_file

    gruppi = (RecuperoGruppo.query.join(RecuperoDocente)
              .filter(RecuperoDocente.anno_scol == ANNO_AGO,
                      RecuperoGruppo.periodo_codice == PERIODO_AGO)
              .order_by(RecuperoGruppo.materia).all())

    GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica']
    MESI   = ['','Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno',
              'Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre']
    TIPO_LABEL = {'scritto':'Scritto','orale':'Orale',
                  'pratico':'Pratico','scritto_orale':'Scritto+Orale'}

    BLU   = PatternFill('solid', start_color='1e3a5f')
    AZZUR = PatternFill('solid', start_color='dbeafe')
    VERDE = PatternFill('solid', start_color='dcfce7')
    BOLD  = Font(bold=True)
    BOLD_W= Font(bold=True, color='FFFFFF')
    THIN  = Border(left=Side(style='thin',color='d1d5db'),
                   right=Side(style='thin',color='d1d5db'),
                   top=Side(style='thin',color='d1d5db'),
                   bottom=Side(style='thin',color='d1d5db'))
    CENTER = Alignment(horizontal='center', vertical='center')
    WRAP   = Alignment(wrap_text=True, vertical='center')

    wb = Workbook()
    ws_fam = wb.active
    ws_fam.title = 'Famiglie'
    ws_doc = wb.create_sheet('Docenti')

    def sheet_header(ws, titolo, interno=False):
        ws['A1'] = 'IIS "Leonardo da Vinci" — Chiavenna'
        ws['A1'].font = Font(bold=True, size=13)
        ws['A2'] = f'CALENDARIO PROVE DI RECUPERO — A.S. {ANNO_AGO}'
        ws['A2'].font = Font(bold=True, size=11,
                             color='dc2626' if interno else '000000')
        ws.append([])
        ws.append([])

    sheet_header(ws_fam)
    sheet_header(ws_doc, interno=True)

    for g in gruppi:
        lezioni = sorted(g.lezioni, key=lambda l: (l.data, l.ora_inizio))
        if not lezioni:
            continue

        doc = g.docente
        nome_doc = f'{doc.cognome} {doc.nome or ""}'.strip() if doc else '—'
        comm = g.commissario
        nome_comm = f'{comm.cognome} {comm.nome or ""}'.strip() if comm else '—'
        tipo_str = TIPO_LABEL.get(g.tipo_prova or 'scritto', '—')

        # ── Foglio Famiglie: una riga per prova ──────────────────────
        # Header materia
        row_f = ws_fam.max_row + 1
        ws_fam.merge_cells(f'A{row_f}:E{row_f}')
        ws_fam[f'A{row_f}'] = f'{g.materia.upper()} — {tipo_str}'
        ws_fam[f'A{row_f}'].font = BOLD_W
        ws_fam[f'A{row_f}'].fill = BLU
        ws_fam[f'A{row_f}'].alignment = CENTER
        row_f += 1
        for col, h in enumerate(['Giorno','Data','Orario','Durata','Classi'], 1):
            c = ws_fam.cell(row=row_f, column=col, value=h)
            c.font = BOLD; c.fill = AZZUR; c.alignment = CENTER; c.border = THIN
        row_f += 1
        for l in lezioni:
            vals = [GIORNI[l.data.weekday()], l.data.strftime('%d/%m/%Y'),
                    f'{l.ora_inizio}–{l.ora_fine}', f'{l.durata_ore}h', g.classi]
            for col, v in enumerate(vals, 1):
                c = ws_fam.cell(row=row_f, column=col, value=v)
                c.border = THIN; c.alignment = WRAP
            row_f += 1
        ws_fam.append([])  # spazio

        # ── Foglio Docenti: una riga per alunno per prova ────────────
        row_d = ws_doc.max_row + 1
        ws_doc.merge_cells(f'A{row_d}:H{row_d}')
        ws_doc[f'A{row_d}'] = f'{g.materia.upper()} — {tipo_str} — Titolare: {nome_doc} — Commissario: {nome_comm}'
        ws_doc[f'A{row_d}'].font = BOLD_W
        ws_doc[f'A{row_d}'].fill = BLU
        ws_doc[f'A{row_d}'].alignment = CENTER
        row_d += 1
        for col, h in enumerate(['Giorno','Data','Orario','Titolare','Commissario','Classe','Cognome','Nome'], 1):
            c = ws_doc.cell(row=row_d, column=col, value=h)
            c.font = BOLD; c.fill = VERDE; c.alignment = CENTER; c.border = THIN
        row_d += 1
        for l in lezioni:
            alunni_g = sorted(g.alunni, key=lambda a: (a.classe, a.cognome))
            for i_al, al in enumerate(alunni_g):
                vals = [GIORNI[l.data.weekday()], l.data.strftime('%d/%m/%Y'),
                        f'{l.ora_inizio}–{l.ora_fine}', nome_doc, nome_comm,
                        al.classe, al.cognome, al.nome]
                for col, v in enumerate(vals, 1):
                    c = ws_doc.cell(row=row_d, column=col, value=v)
                    c.border = THIN; c.alignment = WRAP
                    if i_al % 2 == 1:
                        c.fill = PatternFill('solid', start_color='f8fafc')
                row_d += 1
        ws_doc.append([])

    # Larghezze
    for i, w in enumerate([12,12,12,28,12], 1):
        ws_fam.column_dimensions[get_column_letter(i)].width = w
    for i, w in enumerate([12,12,12,22,22,10,18,16], 1):
        ws_doc.column_dimensions[get_column_letter(i)].width = w

    buf = io.BytesIO()
    wb.save(buf); buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name=f'prove_recupero_agosto_{ANNO_AGO}.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
