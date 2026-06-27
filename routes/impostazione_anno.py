"""
Impostazione anno scolastico: classi di concorso, collegamento con le
materie esistenti, e organico (diritto/fatto) per anno scolastico.

Pensata come area di ingresso unica per tutto cio' che riguarda
l'avvio del nuovo anno — in futuro qui confluiranno anche docenti,
orario, periodi, dati istituto.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db
from models.classe_concorso import ClasseConcorso, CattedraOrganico
from models.materia import Materia, Dipartimento, DocenteMateria
from models.docente import Docente
from datetime import date

impostazione_anno_bp = Blueprint('impostazione_anno', __name__)


def _anno_scolastico_corrente():
    oggi = date.today()
    if oggi.month >= 9:
        return f'{oggi.year}-{oggi.year + 1}'
    return f'{oggi.year - 1}-{oggi.year}'


@impostazione_anno_bp.route('/impostazione-anno')
def index():
    n_classi = ClasseConcorso.query.filter_by(attiva=True).count()
    n_materie_collegate = Materia.query.filter(Materia.id_classe_concorso.isnot(None)).count()
    n_materie_tot = Materia.query.count()
    anni_organico = sorted({r.anno_scol for r in CattedraOrganico.query.all()}, reverse=True)
    return render_template('impostazione_anno/index.html',
        n_classi=n_classi, n_materie_collegate=n_materie_collegate,
        n_materie_tot=n_materie_tot, anni_organico=anni_organico,
        anno_corrente=_anno_scolastico_corrente())


# ── CLASSI DI CONCORSO ──────────────────────────────────────────────
@impostazione_anno_bp.route('/impostazione-anno/classi-concorso', methods=['GET', 'POST'])
def classi_concorso():
    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione == 'aggiungi':
            codice = request.form.get('codice', '').strip().upper()
            nome = request.form.get('nome', '').strip()
            tipo_posto = request.form.get('tipo_posto', 'cattedra')
            note = request.form.get('note', '').strip() or None
            if not (codice and nome):
                flash('Codice e nome sono obbligatori.', 'warning')
                return redirect(url_for('impostazione_anno.classi_concorso'))
            esiste = ClasseConcorso.query.filter_by(codice=codice).first()
            if esiste:
                flash(f'Esiste già una classe di concorso con codice "{codice}".', 'warning')
                return redirect(url_for('impostazione_anno.classi_concorso'))
            db.session.add(ClasseConcorso(codice=codice, nome=nome,
                                           tipo_posto=tipo_posto, note=note))
            db.session.commit()
            flash(f'Classe di concorso {codice} creata.', 'success')

        elif azione == 'modifica':
            cc_id = int(request.form.get('id', 0))
            cc = ClasseConcorso.query.get_or_404(cc_id)
            cc.nome = request.form.get('nome', cc.nome).strip()
            cc.tipo_posto = request.form.get('tipo_posto', cc.tipo_posto)
            cc.note = request.form.get('note', '').strip() or None
            db.session.commit()
            flash('Classe di concorso aggiornata.', 'success')

        elif azione == 'disattiva':
            cc_id = int(request.form.get('id', 0))
            cc = ClasseConcorso.query.get_or_404(cc_id)
            cc.attiva = False
            db.session.commit()
            flash(f'{cc.codice} disattivata.', 'warning')

        elif azione == 'riattiva':
            cc_id = int(request.form.get('id', 0))
            cc = ClasseConcorso.query.get_or_404(cc_id)
            cc.attiva = True
            db.session.commit()
            flash(f'{cc.codice} riattivata.', 'success')

        return redirect(url_for('impostazione_anno.classi_concorso'))

    classi = ClasseConcorso.query.order_by(ClasseConcorso.codice).all()
    return render_template('impostazione_anno/classi_concorso.html', classi=classi)


# ── COLLEGAMENTO MATERIE ↔ CLASSI DI CONCORSO (multiple) ──────────────
@impostazione_anno_bp.route('/impostazione-anno/materie-classi-concorso', methods=['GET', 'POST'])
def materie_classi_concorso():
    """
    Una materia può essere insegnata da PIÙ classi di concorso (es.
    Filosofia da A018 e A019, secondo l'indirizzo) — il sistema distingue
    collegamenti 'normativa' (regola generale, valida ovunque) da
    eventuali 'eccezione_istituto' (casi atipici di questa scuola,
    documentati con una nota). La prima classe selezionata nel form
    diventa quella 'normativa' principale e resta sincronizzata sul
    campo legacy Materia.id_classe_concorso.
    """
    from models.classe_concorso import MateriaClasseConcorso

    if request.method == 'POST':
        for m in Materia.query.all():
            key = f'cc_materia_{m.id}'
            ids_selezionati = request.form.getlist(key)
            ids_validi = [int(i) for i in ids_selezionati if i.isdigit()]

            esistenti = {r.id_classe_concorso: r for r in
                         MateriaClasseConcorso.query.filter_by(id_materia=m.id).all()}
            nuove = set(ids_validi)

            # Rimuove i collegamenti 'normativa' non più selezionati — non
            # tocca mai le 'eccezione_istituto', che vanno gestite a parte
            # (non si cancellano per sbaglio spuntando/togliendo checkbox).
            for cc_id, riga in esistenti.items():
                if riga.fonte == 'normativa' and cc_id not in nuove:
                    db.session.delete(riga)

            for cc_id in nuove:
                if cc_id not in esistenti:
                    db.session.add(MateriaClasseConcorso(
                        id_materia=m.id, id_classe_concorso=cc_id, fonte='normativa'))

            m.id_classe_concorso = ids_validi[0] if ids_validi else None

        db.session.commit()
        flash('Collegamenti materia → classi di concorso aggiornati.', 'success')
        return redirect(url_for('impostazione_anno.materie_classi_concorso'))

    materie = Materia.query.join(Dipartimento).order_by(
        Dipartimento.ordine, Materia.nome).all()
    classi = ClasseConcorso.query.filter_by(attiva=True).order_by(ClasseConcorso.codice).all()
    return render_template('impostazione_anno/materie_classi_concorso.html',
        materie=materie, classi=classi)


# ── ORGANICO (DIRITTO / FATTO) ───────────────────────────────────────
@impostazione_anno_bp.route('/impostazione-anno/organico', methods=['GET', 'POST'])
def organico():
    anno = request.args.get('anno', _anno_scolastico_corrente())
    tipo = request.args.get('tipo', 'diritto')

    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione == 'aggiungi':
            id_cc = int(request.form.get('id_classe_concorso', 0))
            anno_f = request.form.get('anno_scol', anno).strip()
            tipo_f = request.form.get('tipo', tipo)
            if not id_cc:
                flash('Seleziona una classe di concorso.', 'warning')
                return redirect(url_for('impostazione_anno.organico', anno=anno_f, tipo=tipo_f))
            esiste = CattedraOrganico.query.filter_by(
                anno_scol=anno_f, tipo=tipo_f, id_classe_concorso=id_cc).first()
            if esiste:
                flash('Esiste già una riga organico per questa classe di concorso, anno e tipo: modificala invece.', 'warning')
                return redirect(url_for('impostazione_anno.organico', anno=anno_f, tipo=tipo_f))

            def _int_or_none(v):
                v = (v or '').strip()
                return int(v) if v else None

            db.session.add(CattedraOrganico(
                anno_scol=anno_f, tipo=tipo_f, id_classe_concorso=id_cc,
                n_docenti=_int_or_none(request.form.get('n_docenti')) or 0,
                n_coi=_int_or_none(request.form.get('n_coi')) or 0,
                n_coe=_int_or_none(request.form.get('n_coe')) or 0,
                coe_direzione=request.form.get('coe_direzione') or None,
                coe_scuola=request.form.get('coe_scuola', '').strip() or None,
                coe_ore=_int_or_none(request.form.get('coe_ore')),
                ore_residue=_int_or_none(request.form.get('ore_residue')) or 0,
                n_potenziamento=_int_or_none(request.form.get('n_potenziamento')) or 0,
                note=request.form.get('note', '').strip() or None,
            ))
            db.session.commit()
            flash('Riga organico aggiunta.', 'success')
            return redirect(url_for('impostazione_anno.organico', anno=anno_f, tipo=tipo_f))

        elif azione == 'modifica':
            row_id = int(request.form.get('id', 0))
            r = CattedraOrganico.query.get_or_404(row_id)

            def _int_or_none(v):
                v = (v or '').strip()
                return int(v) if v else None

            r.n_docenti = _int_or_none(request.form.get('n_docenti')) or 0
            r.n_coi = _int_or_none(request.form.get('n_coi')) or 0
            r.n_coe = _int_or_none(request.form.get('n_coe')) or 0
            r.coe_direzione = request.form.get('coe_direzione') or None
            r.coe_scuola = request.form.get('coe_scuola', '').strip() or None
            r.coe_ore = _int_or_none(request.form.get('coe_ore'))
            r.ore_residue = _int_or_none(request.form.get('ore_residue')) or 0
            r.n_potenziamento = _int_or_none(request.form.get('n_potenziamento')) or 0
            r.note = request.form.get('note', '').strip() or None
            db.session.commit()
            flash('Riga organico aggiornata.', 'success')
            return redirect(url_for('impostazione_anno.organico', anno=anno, tipo=tipo))

        elif azione == 'elimina':
            row_id = int(request.form.get('id', 0))
            r = CattedraOrganico.query.get_or_404(row_id)
            db.session.delete(r)
            db.session.commit()
            flash('Riga organico eliminata.', 'warning')
            return redirect(url_for('impostazione_anno.organico', anno=anno, tipo=tipo))

        elif azione == 'copia_da_diritto':
            # Inizializza l'organico di fatto copiando tutte le righe
            # dell'organico di diritto dello stesso anno, come punto di
            # partenza da poi correggere con gli aggiustamenti reali.
            righe_diritto = CattedraOrganico.query.filter_by(
                anno_scol=anno, tipo='diritto').all()
            n_copiate = 0
            for r in righe_diritto:
                esiste = CattedraOrganico.query.filter_by(
                    anno_scol=anno, tipo='fatto', id_classe_concorso=r.id_classe_concorso).first()
                if esiste:
                    continue
                db.session.add(CattedraOrganico(
                    anno_scol=anno, tipo='fatto', id_classe_concorso=r.id_classe_concorso,
                    n_docenti=r.n_docenti, n_coi=r.n_coi, n_coe=r.n_coe,
                    coe_direzione=r.coe_direzione, coe_scuola=r.coe_scuola, coe_ore=r.coe_ore,
                    ore_residue=r.ore_residue, n_potenziamento=r.n_potenziamento,
                    note='Copiato da organico di diritto — da verificare',
                ))
                n_copiate += 1
            db.session.commit()
            flash(f'{n_copiate} righe copiate da organico di diritto a organico di fatto.', 'success')
            return redirect(url_for('impostazione_anno.organico', anno=anno, tipo='fatto'))

    righe = (CattedraOrganico.query
             .filter_by(anno_scol=anno, tipo=tipo)
             .join(ClasseConcorso)
             .order_by(ClasseConcorso.codice)
             .all())
    classi_disponibili = ClasseConcorso.query.filter_by(attiva=True).order_by(ClasseConcorso.codice).all()

    tot_residue = sum(r.ore_residue or 0 for r in righe)
    tot_potenziamento = sum(r.n_potenziamento or 0 for r in righe)

    anni_esistenti = sorted({r.anno_scol for r in CattedraOrganico.query.all()}, reverse=True)
    if anno not in anni_esistenti:
        anni_esistenti.insert(0, anno)

    return render_template('impostazione_anno/organico.html',
        righe=righe, classi_disponibili=classi_disponibili,
        anno=anno, tipo=tipo, anni_esistenti=anni_esistenti,
        tot_residue=tot_residue, tot_potenziamento=tot_potenziamento)


# ── DOCENTI ↔ CLASSI DI CONCORSO (multiple) ───────────────────────────
@impostazione_anno_bp.route('/impostazione-anno/docenti-classi-concorso', methods=['GET', 'POST'])
def docenti_classi_concorso():
    """
    Assegna a ciascun docente UNA O PIÙ classi di concorso (es. A026 +
    A050, per chi è abilitato su entrambe e riceve ore da entrambe).
    Stabile negli anni — non cambia ogni anno scolastico. Il multi-select
    mostra solo le classi di concorso esistenti, mai testo libero.

    La prima classe selezionata viene marcata 'principale' e sincronizzata
    sul campo legacy Docente.id_classe_concorso (usato altrove per badge
    rapidi); le altre restano abilitazioni aggiuntive.
    """
    from models.classe_concorso import DocenteClasseConcorso

    if request.method == 'POST':
        for docente in Docente.query.filter_by(attivo=True).all():
            key = f'cc_docente_{docente.id}'
            ids_selezionati = request.form.getlist(key)
            ids_validi = [int(i) for i in ids_selezionati if i.isdigit()]

            vecchie = {a.id_classe_concorso for a in docente.abilitazioni}
            nuove = set(ids_validi)

            if vecchie != nuove:
                # Cambiando le abilitazioni, le materie assegnate in
                # precedenza potrebbero non essere più ammesse: le
                # rimuove, cosi' non restano incoerenze silenziose.
                DocenteMateria.query.filter_by(id_docente=docente.id).delete()

            DocenteClasseConcorso.query.filter_by(id_docente=docente.id).delete()
            for i, cc_id in enumerate(ids_validi):
                db.session.add(DocenteClasseConcorso(
                    id_docente=docente.id, id_classe_concorso=cc_id,
                    principale=(i == 0)))
            # Campo legacy in sync con la principale (prima selezionata)
            docente.id_classe_concorso = ids_validi[0] if ids_validi else None

        db.session.commit()
        flash('Abilitazioni docente → classi di concorso aggiornate.', 'success')
        return redirect(url_for('impostazione_anno.docenti_classi_concorso'))

    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    classi = ClasseConcorso.query.filter_by(attiva=True).order_by(ClasseConcorso.codice).all()
    return render_template('impostazione_anno/docenti_classi_concorso.html',
        docenti=docenti, classi=classi)


# ── DOCENTI ↔ MATERIE (filtrate per TUTTE le classi di concorso) ─────
@impostazione_anno_bp.route('/impostazione-anno/docenti-materie', methods=['GET', 'POST'])
def docenti_materie():
    """
    Assegna a ciascun docente le materie che insegna, per anno
    scolastico — il multi-select mostra l'UNIONE delle materie ammesse
    da TUTTE le classi di concorso del docente (es. un docente abilitato
    su A026+A050 vede sia le materie di Matematica sia quelle di Scienze
    Naturali): niente testo libero, niente materie fuori abilitazione.
    """
    from models.classe_concorso import MateriaClasseConcorso

    anno = request.args.get('anno', '2025-2026')

    def _materie_ammesse_per_classi(cc_ids):
        """Unione delle materie collegate (normativa O eccezione_istituto)
        a una qualsiasi delle classi di concorso passate."""
        if not cc_ids:
            return []
        id_materie = {r.id_materia for r in MateriaClasseConcorso.query.filter(
            MateriaClasseConcorso.id_classe_concorso.in_(cc_ids)).all()}
        if not id_materie:
            return []
        return Materia.query.filter(
            Materia.id.in_(id_materie), Materia.attiva == True
        ).order_by(Materia.nome).all()

    if request.method == 'POST':
        anno_f = request.form.get('anno_scol', anno)
        for docente in Docente.query.filter_by(attivo=True).all():
            cc_ids = [a.id_classe_concorso for a in docente.abilitazioni]
            if not cc_ids:
                continue  # senza classe di concorso non c'e' nulla da assegnare qui
            key = f'materie_docente_{docente.id}'
            ids_selezionati = request.form.getlist(key)
            # Vincolo di sicurezza: anche se il form venisse manomesso,
            # accetta solo id di materie effettivamente ammesse da una
            # delle sue classi di concorso (via MateriaClasseConcorso,
            # normativa o eccezione_istituto) — mai testo libero, mai
            # materie fuori da ogni sua abilitazione.
            ids_ammessi = {m.id for m in _materie_ammesse_per_classi(cc_ids)}
            ids_validi = [int(i) for i in ids_selezionati if i.isdigit() and int(i) in ids_ammessi]

            DocenteMateria.query.filter_by(id_docente=docente.id, anno_scol=anno_f).delete()
            for mid in ids_validi:
                db.session.add(DocenteMateria(id_docente=docente.id, id_materia=mid, anno_scol=anno_f))
        db.session.commit()
        flash('Materie dei docenti aggiornate.', 'success')
        return redirect(url_for('impostazione_anno.docenti_materie', anno=anno_f))

    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()

    # Per ogni docente: l'unione delle materie ammesse da tutte le sue
    # classi di concorso, e quelle già assegnate per l'anno scelto.
    righe = []
    for d in docenti:
        cc_ids = [a.id_classe_concorso for a in d.abilitazioni]
        materie_ammesse = _materie_ammesse_per_classi(cc_ids)
        assegnate_ids = {dm.id_materia for dm in DocenteMateria.query.filter_by(
            id_docente=d.id, anno_scol=anno).all()}
        righe.append({
            'docente': d,
            'materie_ammesse': materie_ammesse,
            'assegnate_ids': assegnate_ids,
        })

    return render_template('impostazione_anno/docenti_materie.html',
        righe=righe, anno=anno)
