"""
Impostazione anno scolastico: classi di concorso, collegamento con le
materie esistenti, e organico (diritto/fatto) per anno scolastico.

Pensata come area di ingresso unica per tutto cio' che riguarda
l'avvio del nuovo anno — in futuro qui confluiranno anche docenti,
orario, periodi, dati istituto.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db
from models.classe_concorso import ClasseConcorso, CattedraOrganico
from models.assegnazione import CattedraPotenziamento
from models.materia import Materia, Dipartimento, DocenteMateria
from models.docente import Docente
from models.piano_studi import ClasseSezione, PianoStudi, CalcoloOrganico
from datetime import date

impostazione_anno_bp = Blueprint('impostazione_anno', __name__)


# ── BARRA DI NAVIGAZIONE A PASSI (breadcrumb + prev/next + tessere) ───
# Iniettata in ogni pagina della sezione tramite templates/impostazione_anno/
# _step_nav.html. Elenco unico qui: se cambia l'ordine o si aggiunge un
# passo, si aggiorna solo questa lista e tutte le pagine si allineano.
# 'own'=False per i passi che vivono in un altro blueprint (Aule,
# Assegnazioni): restano cliccabili nella fila di tessere ma sono esclusi
# dal conteggio prev/next, che si muove solo tra le pagine di QUESTA
# sezione (altrimenti "avanti" da una pagina Aule tornerebbe qui dentro
# in modo confuso, dato che Aule/Assegnazioni hanno una loro navigazione).
def _nav_steps(anno_corrente=None):
    ap = anno_corrente or _anno_default_piano()
    return [
        {'num': '1',  'label': 'Classi di concorso',
         'endpoint': 'impostazione_anno.classi_concorso', 'kwargs': {},
         'color': '#0369a1', 'own': True},
        {'num': '2',  'label': 'Piano di studi',
         'endpoint': 'impostazione_anno.piano_studi', 'kwargs': {'anno': ap},
         'color': '#7c3aed', 'own': True},
        {'num': '3',  'label': 'Materie ↔︎ Classi di concorso',
         'endpoint': 'impostazione_anno.materie_classi_concorso', 'kwargs': {},
         'color': '#6366f1', 'own': True},
        {'num': '4',  'label': 'Classi attive',
         'endpoint': 'impostazione_anno.classi_attive', 'kwargs': {'anno': ap},
         'color': '#0891b2', 'own': True},
        {'num': '4b', 'label': 'Aule per classe',
         'endpoint': 'aule.lista', 'kwargs': {},
         'color': '#0891b2', 'own': False},
        {'num': '5',  'label': 'Calcolo organico richiesto',
         'endpoint': 'impostazione_anno.calcolo_organico', 'kwargs': {'anno': ap},
         'color': '#0891b2', 'own': True},
        {'num': '6',  'label': 'Organico USR',
         'endpoint': 'impostazione_anno.organico',
         'kwargs': {'anno': ap, 'tipo': 'diritto'},
         'color': '#166534', 'own': True},
        {'num': '6b', 'label': 'Cattedre di potenziamento',
         'endpoint': 'impostazione_anno.cattedre_potenziamento', 'kwargs': {'anno': ap},
         'color': '#7c3aed', 'own': True},
        {'num': '7',  'label': 'Docenti per anno scolastico',
         'endpoint': 'impostazione_anno.docenti_anno', 'kwargs': {'anno': ap},
         'color': '#dc2626', 'own': True},
        {'num': '8',  'label': 'Docenti ↔︎ Classe di concorso',
         'endpoint': 'impostazione_anno.docenti_classi_concorso', 'kwargs': {},
         'color': '#b45309', 'own': True},
        {'num': '8b', 'label': 'Verifica TI ↔︎ Organico USR',
         'endpoint': 'impostazione_anno.confronto_organico', 'kwargs': {'anno': ap},
         'color': '#7c3aed', 'own': True},
        {'num': '9',  'label': 'Assegnazioni classi →︎ docenti',
         'endpoint': 'assegnazioni.index', 'kwargs': {'anno': ap},
         'color': '#6366f1', 'own': False},
        {'num': '10', 'label': 'Docenti ↔︎ Materie',
         'endpoint': 'impostazione_anno.docenti_materie', 'kwargs': {},
         'color': '#be185d', 'own': True},
    ]


# Nota: registrato globalmente su tutta l'app (in app.py), non solo su
# questo blueprint — serve anche nelle pagine "4b. Aule" e "9. Assegnazioni",
# che vivono in routes/aule.py e routes/assegnazioni.py (blueprint diversi,
# altrimenti un context_processor di blueprint non li raggiungerebbe e la
# barra risulterebbe assente proprio su quei due passi).


def _docenti_per_anno(anno_scol):
    """
    Restituisce i docenti "sulla pianta organica" per un dato anno
    scolastico (include AP uscenti e in aspettativa — sono ancora
    titolari della scuola: dashboard_anno/assegnazioni li contano e poi
    li filtrano ulteriormente da soli dove serve, vedi rispettivamente
    i conteggi n_aspettativa/n_ap_uscente e il filtro status_presenza
    in routes/assegnazioni.py).

    I limiti anno_scol_inizio/anno_scol_uscita si applicano SEMPRE, non
    solo per gli anni futuri: altrimenti un docente già inserito con
    anno_scol_inizio dell'anno prossimo comparirebbe anche nell'anno
    corrente/passato (bug osservato: nuovi docenti 2026-2027 visibili
    anche nel 2025-2026).

    Per gli anni futuri (anno_scol > anno_scol_corrente) si applica
    inoltre un filtro aggiuntivo: i TD/supplenti senza anno_scol_inizio
    esplicito non sono ancora nominati e non compaiono.
    """
    from sqlalchemy import or_
    from config_anno import get_anno_corrente

    anno_corrente = get_anno_corrente()  # fonte di verità: DB

    base = Docente.query.filter_by(attivo=True).filter(
        # Non ancora arrivato (TI storico senza data = sempre incluso)
        or_(
            Docente.anno_scol_inizio == None,
            Docente.anno_scol_inizio <= anno_scol,
        ),
        # Non ha una data di uscita, o esce dopo quell'anno
        or_(
            Docente.anno_scol_uscita == None,
            Docente.anno_scol_uscita > anno_scol,
        ),
    )

    if anno_scol > anno_corrente:
        # Anno futuro: i TD/supplenti/IRC senza data inizio esplicita
        # non sono ancora nominati per quell'anno, non compaiono.
        # Le AP uscenti compaiono comunque (sono TI titolari della scuola).
        base = base.filter(or_(
            Docente.tipo_contratto.in_(['TI', 'IRC']),
            Docente.anno_scol_inizio != None,
        ))

    return base.order_by(Docente.cognome).all()


def _anno_scolastico_corrente():
    """Restituisce l'anno scolastico corrente nel senso del calendario."""
    oggi = date.today()
    if oggi.month >= 9:
        return f'{oggi.year}-{oggi.year + 1}'
    return f'{oggi.year - 1}-{oggi.year}'


def _anno_default_piano():
    """
    Anno da usare come default nelle pagine del piano studi / calcolo
    organico: l'anno piu' recente con righe effettive nel piano studi
    o nel calcolo organico. Le sezioni 'tutte inattive' (anno preparato
    ma non ancora configurato) non contano — si guarda solo agli anni
    con almeno una riga di piano studi o un calcolo con ore > 0.
    Fallback: anno scolastico corrente se nessun dato esiste ancora.
    """
    anni_piano = {p.anno_scol for p in PianoStudi.query.all()}
    anni_calc  = {c.anno_scol for c in CalcoloOrganico.query
                  .filter(CalcoloOrganico.ore_totali_calcolate > 0).all()}
    tutti = anni_piano | anni_calc
    if tutti:
        return max(tutti)
    return _anno_scolastico_corrente()


@impostazione_anno_bp.route('/impostazione-anno')
def index():
    from models.classe_concorso import MateriaClasseConcorso
    anno_corrente = _anno_scolastico_corrente()
    n_classi = ClasseConcorso.query.filter_by(attiva=True).count()
    # Fonte di verità: la tabella MateriaClasseConcorso (collegamenti
    # 'normativa' o 'eccezione_istituto'), non il campo legacy
    # Materia.id_classe_concorso — quel campo è solo una cache del primo
    # collegamento 'normativa' e può disallinearsi (visto per Geografia
    # Economica e TIC, Task 22: righe presenti ma legacy rimasto NULL).
    ids_materie_collegate = {r.id_materia for r in MateriaClasseConcorso.query.all()}
    n_materie_collegate = len(ids_materie_collegate)
    n_materie_tot = Materia.query.count()
    materie_non_collegate = Materia.query.filter(
        ~Materia.id.in_(ids_materie_collegate)).order_by(Materia.nome).all()
    anni_organico = sorted({r.anno_scol for r in CattedraOrganico.query.all()}, reverse=True)
    anno_piano = _anno_default_piano()  # anno su cui si sta lavorando davvero
    # KPI piano studi — riferiti ad anno_piano (l'anno con dati reali,
    # cioè quello su cui si sta effettivamente lavorando), NON a
    # anno_corrente: anno_corrente è calcolato solo dal calendario
    # (cambia il 1° settembre) e a inizio anno solare risulterebbe
    # ancora l'anno vecchio anche se si sta già impostando quello nuovo
    # — prima di questa correzione i box mostravano i dati dell'anno
    # sbagliato mentre tutti i link sotto puntavano già ad anno_piano.
    n_sezioni_attive = ClasseSezione.query.filter_by(anno_scol=anno_piano, attiva=True).count()
    n_piano_righe   = PianoStudi.query.filter_by(anno_scol=anno_piano).count()
    n_calcolo_ok    = CalcoloOrganico.query.filter_by(anno_scol=anno_piano, confermato=True).count()
    n_calcolo_tot   = CalcoloOrganico.query.filter_by(anno_scol=anno_piano).filter(
        CalcoloOrganico.ore_totali_calcolate > 0).count()
    return render_template('impostazione_anno/index.html',
        n_classi=n_classi, n_materie_collegate=n_materie_collegate,
        n_materie_tot=n_materie_tot, materie_non_collegate=materie_non_collegate,
        anni_organico=anni_organico,
        anno_corrente=anno_corrente,
        anno_piano=anno_piano,
        n_sezioni_attive=n_sezioni_attive, n_piano_righe=n_piano_righe,
        n_calcolo_ok=n_calcolo_ok, n_calcolo_tot=n_calcolo_tot)


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
    from models.assegnazione import AssegnazioneClasse, AssegnazioneDocente

    if request.method == 'POST':
        # Raccoglie i collegamenti materia↔CC che vengono rimossi in questo
        # salvataggio, per poter controllare DOPO se esistono già ore
        # assegnate (Assegnazioni classi → docenti) su quella coppia —
        # il collegamento passo 3 non ha effetto a cascata su quanto già
        # assegnato, quindi rimuoverlo senza controllo lascerebbe
        # un'incoerenza silenziosa (ore assegnate su una CC che secondo
        # la normativa/eccezione non insegna più quella materia).
        rimossi = []  # [(id_materia, id_classe_concorso), ...]

        for m in Materia.query.all():
            # Aggiorna nome_breve e alias se presenti nel form
            nb = request.form.get(f'nome_breve_{m.id}', '').strip()
            al = request.form.get(f'alias_{m.id}', '').strip().upper()
            if nb:
                m.nome_breve = nb
            if al:
                m.alias = al

            key = f'cc_materia_{m.id}'
            ids_selezionati = request.form.getlist(key)
            ids_validi = [int(i) for i in ids_selezionati if i.isdigit()]

            esistenti = {r.id_classe_concorso: r for r in
                         MateriaClasseConcorso.query.filter_by(id_materia=m.id).all()}
            nuove = set(ids_validi)

            for cc_id, riga in esistenti.items():
                if riga.fonte == 'normativa' and cc_id not in nuove:
                    rimossi.append((m.id, cc_id))
                    db.session.delete(riga)

            for cc_id in nuove:
                if cc_id not in esistenti:
                    db.session.add(MateriaClasseConcorso(
                        id_materia=m.id, id_classe_concorso=cc_id, fonte='normativa'))

            m.id_classe_concorso = ids_validi[0] if ids_validi else None

        db.session.commit()

        # Controllo di coerenza: per ogni coppia rimossa, ci sono ore già
        # assegnate in Assegnazioni su quella materia per quella CC?
        avvisi = []
        for id_materia, cc_id in rimossi:
            righe = (AssegnazioneClasse.query
                     .join(AssegnazioneDocente,
                           AssegnazioneClasse.id_assegnazione == AssegnazioneDocente.id)
                     .filter(AssegnazioneClasse.id_materia == id_materia,
                             AssegnazioneDocente.id_classe_concorso == cc_id,
                             AssegnazioneClasse.ore > 0)
                     .all())
            if righe:
                materia = Materia.query.get(id_materia)
                cc = ClasseConcorso.query.get(cc_id)
                docenti = sorted({r.assegnazione.display_name for r in righe})
                avvisi.append(
                    f'"{materia.nome if materia else id_materia}" scollegata da '
                    f'{cc.codice if cc else cc_id}, ma risultano ancora ore assegnate '
                    f'in Assegnazioni per: {", ".join(docenti)}. Le ore NON sono state '
                    f'toccate — verificale in Assegnazioni classi → docenti.')

        if avvisi:
            flash('Materie e collegamenti CC aggiornati, ma sono state trovate '
                  'incoerenze: ' + ' | '.join(avvisi), 'warning')
        else:
            flash('Materie e collegamenti CC aggiornati.', 'success')
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


# ── CATTEDRE DI POTENZIAMENTO (ore POT per CC/anno) ────────────────────
@impostazione_anno_bp.route('/impostazione-anno/cattedre-potenziamento', methods=['GET', 'POST'])
def cattedre_potenziamento():
    """
    Gestisce le ore di potenziamento assegnate a ciascuna classe di
    concorso per anno scolastico (tabella cattedre_potenziamento).
    Sono le ore che poi vengono distribuite ai docenti nel modulo
    Assegnazioni tramite la colonna POT.
    """
    anno = request.args.get('anno', _anno_scolastico_corrente())

    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione == 'aggiungi':
            id_cc = int(request.form.get('id_classe_concorso', 0))
            anno_f = request.form.get('anno_scol', anno).strip()
            ore = request.form.get('ore', '').strip()
            ore = int(ore) if ore else 18
            note = request.form.get('note', '').strip() or None
            if not id_cc:
                flash('Seleziona una classe di concorso.', 'warning')
                return redirect(url_for('impostazione_anno.cattedre_potenziamento', anno=anno_f))
            esiste = CattedraPotenziamento.query.filter_by(
                anno_scol=anno_f, id_classe_concorso=id_cc).first()
            if esiste:
                flash('Esiste già una cattedra di potenziamento per questa classe di concorso e anno: modificala invece.', 'warning')
                return redirect(url_for('impostazione_anno.cattedre_potenziamento', anno=anno_f))
            db.session.add(CattedraPotenziamento(
                anno_scol=anno_f, id_classe_concorso=id_cc, ore=ore, note=note))
            db.session.commit()
            flash('Cattedra di potenziamento aggiunta.', 'success')
            return redirect(url_for('impostazione_anno.cattedre_potenziamento', anno=anno_f))

        elif azione == 'modifica':
            row_id = int(request.form.get('id', 0))
            r = CattedraPotenziamento.query.get_or_404(row_id)
            ore = request.form.get('ore', '').strip()
            r.ore = int(ore) if ore else r.ore
            r.note = request.form.get('note', '').strip() or None
            db.session.commit()
            flash('Cattedra di potenziamento aggiornata.', 'success')
            return redirect(url_for('impostazione_anno.cattedre_potenziamento', anno=anno))

        elif azione == 'elimina':
            row_id = int(request.form.get('id', 0))
            r = CattedraPotenziamento.query.get_or_404(row_id)
            db.session.delete(r)
            db.session.commit()
            flash('Cattedra di potenziamento eliminata.', 'warning')
            return redirect(url_for('impostazione_anno.cattedre_potenziamento', anno=anno))

    righe = (CattedraPotenziamento.query
             .filter_by(anno_scol=anno)
             .join(ClasseConcorso)
             .order_by(ClasseConcorso.codice)
             .all())
    classi_disponibili = ClasseConcorso.query.filter_by(attiva=True).order_by(ClasseConcorso.codice).all()

    tot_ore = sum(r.ore or 0 for r in righe)

    anni_esistenti = sorted({r.anno_scol for r in CattedraPotenziamento.query.all()}, reverse=True)
    if anno not in anni_esistenti:
        anni_esistenti.insert(0, anno)

    return render_template('impostazione_anno/cattedre_potenziamento.html',
        righe=righe, classi_disponibili=classi_disponibili,
        anno=anno, anni_esistenti=anni_esistenti, tot_ore=tot_ore)


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

    anno = request.args.get('anno', request.form.get('anno_scol', _anno_default_piano()))

    if request.method == 'POST':
        anno_f = request.form.get('anno_scol', anno)
        for docente in _docenti_per_anno(anno_f):
            key = f'cc_docente_{docente.id}'
            ids_selezionati = request.form.getlist(key)
            ids_validi = [int(i) for i in ids_selezionati if i.isdigit()]

            vecchie = {a.id_classe_concorso for a in docente.abilitazioni}
            nuove = set(ids_validi)

            if vecchie != nuove:
                DocenteMateria.query.filter_by(id_docente=docente.id).delete()

            DocenteClasseConcorso.query.filter_by(id_docente=docente.id).delete()
            for i, cc_id in enumerate(ids_validi):
                db.session.add(DocenteClasseConcorso(
                    id_docente=docente.id, id_classe_concorso=cc_id,
                    principale=(i == 0)))
            docente.id_classe_concorso = ids_validi[0] if ids_validi else None

        db.session.commit()
        flash('Abilitazioni docente → classi di concorso aggiornate.', 'success')
        return redirect(url_for('impostazione_anno.docenti_classi_concorso', anno=anno_f))

    docenti = _docenti_per_anno(anno)
    classi = ClasseConcorso.query.filter_by(attiva=True).order_by(ClasseConcorso.codice).all()
    anni_disponibili = sorted(
        {p.anno_scol for p in PianoStudi.query.all()} |
        {cs.anno_scol for cs in ClasseSezione.query.all()},
        reverse=True)
    if anno not in anni_disponibili:
        anni_disponibili.insert(0, anno)

    # Confronto TI collegati vs DOC organico USR — inline nella pagina.
    # Stessa precedenza fatto→diritto usata in confronto_organico() e in
    # routes/assegnazioni.py::_budget(): l'organico di fatto è la
    # dotazione reale (dopo le iscrizioni), quello di diritto è solo un
    # ripiego se il fatto non è ancora stato inserito. Niente join fisso
    # su tipo='diritto' per raccogliere le CC (duplicherebbe la CC se
    # esistono sia la riga 'diritto' sia la riga 'fatto').
    from models.classe_concorso import CattedraOrganico, DocenteClasseConcorso
    ids_con_cattedra = {c.id_classe_concorso for c in
                         CattedraOrganico.query.filter_by(anno_scol=anno)
                         .filter(CattedraOrganico.n_docenti > 0).all()}
    cc_con_dati = (ClasseConcorso.query
        .filter(ClasseConcorso.id.in_(ids_con_cattedra))
        .order_by(ClasseConcorso.codice).all())

    from models.docente import tipo_contratto_per_anno
    confronto = []
    for cc in cc_con_dati:
        # Contratto DI QUESTO anno (storico se registrato) — vedi
        # DocenteContrattoAnno: un TD che entra in ruolo l'anno dopo non
        # va contato come TI negli anni in cui non lo era ancora.
        docenti_cc = (Docente.query
            .join(DocenteClasseConcorso, DocenteClasseConcorso.id_docente == Docente.id)
            .filter(DocenteClasseConcorso.id_classe_concorso == cc.id,
                    Docente.attivo == True).all())
        n_ti = sum(1 for d in docenti_cc if tipo_contratto_per_anno(d, anno) == 'TI')
        cat = None
        for tipo_tentativo in ('fatto', 'diritto'):
            cat = CattedraOrganico.query.filter_by(
                anno_scol=anno, tipo=tipo_tentativo, id_classe_concorso=cc.id).first()
            if cat:
                break
        n_usr = cat.n_docenti if cat and cat.n_docenti else 0
        tipo_usr = cat.tipo if cat else None
        scarto = n_ti - n_usr
        sem = 'verde' if scarto == 0 else ('giallo' if abs(scarto) == 1 else 'rosso')
        confronto.append({'cc': cc, 'n_ti_app': n_ti,
                          'n_doc_usr': n_usr, 'tipo_usr': tipo_usr,
                          'scarto': scarto, 'semaforo': sem})

    return render_template('impostazione_anno/docenti_classi_concorso.html',
        docenti=docenti, classi=classi, anno=anno, anni_disponibili=anni_disponibili,
        confronto=confronto)


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

    anno = request.args.get('anno', _anno_default_piano())

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
        for docente in _docenti_per_anno(anno_f):
            cc_ids = [a.id_classe_concorso for a in docente.abilitazioni]
            if not cc_ids:
                continue
            key = f'materie_docente_{docente.id}'
            ids_selezionati = request.form.getlist(key)
            # Vincolo di sicurezza: anche se il form venisse manomesso,
            # accetta solo id di materie effettivamente ammesse da una
            # delle sue classi di concorso (via MateriaClasseConcorso,
            # normativa o eccezione_istituto) — mai testo libero. Unica
            # eccezione: le materie GIA' presenti in DocenteMateria prima
            # di questo salvataggio (es. sincronizzate da Assegnazioni su
            # una classe di concorso non ancora collegata al passo 8) —
            # senza questa eccezione un salvataggio qualsiasi da questa
            # pagina le avrebbe cancellate in silenzio, anche restando
            # spuntate in schermata (vedi 'materie_extra' nella GET).
            # Non introduce testo libero: resta un id_materia già esistito
            # nel DB per questo docente, mai un valore arbitrario del form.
            ids_gia_presenti = {dm.id_materia for dm in DocenteMateria.query.filter_by(
                id_docente=docente.id, anno_scol=anno_f).all()}
            ids_ammessi = {m.id for m in _materie_ammesse_per_classi(cc_ids)} | ids_gia_presenti
            ids_validi = [int(i) for i in ids_selezionati if i.isdigit() and int(i) in ids_ammessi]

            DocenteMateria.query.filter_by(id_docente=docente.id, anno_scol=anno_f).delete()
            for mid in ids_validi:
                db.session.add(DocenteMateria(id_docente=docente.id, id_materia=mid, anno_scol=anno_f))
        db.session.commit()
        flash('Materie dei docenti aggiornate.', 'success')
        return redirect(url_for('impostazione_anno.docenti_materie', anno=anno_f))

    docenti = _docenti_per_anno(anno)

    # Per ogni docente: l'unione delle materie ammesse da tutte le sue
    # classi di concorso, e quelle già assegnate per l'anno scelto.
    righe = []
    for d in docenti:
        cc_ids = [a.id_classe_concorso for a in d.abilitazioni]
        materie_ammesse = _materie_ammesse_per_classi(cc_ids)
        dm_esistenti = DocenteMateria.query.filter_by(
            id_docente=d.id, anno_scol=anno).all()
        assegnate_ids = {dm.id_materia for dm in dm_esistenti}
        # origine ('auto' = da Assegnazioni, 'manuale' = da questa pagina
        # o dalla scheda docente) — solo per il badge informativo, non
        # limita in alcun modo cosa si può togliere da qui.
        origine_map = {dm.id_materia: dm.origine for dm in dm_esistenti}

        # Materie già assegnate al docente (in DocenteMateria, quindi
        # anche quelle sincronizzate da Assegnazioni) ma NON coperte da
        # nessuna sua classe di concorso abilitata (passo 8): senza
        # questo controllo restavano invisibili qui — il checkbox non
        # veniva mai renderizzato perché il loop scorre solo
        # materie_ammesse. Le mostriamo comunque, separate, con un
        # avviso: segnalano quasi sempre una classe di concorso mancante
        # al passo 8, non un dato sbagliato da correggere qui.
        ids_ammesse = {m.id for m in materie_ammesse}
        ids_extra = assegnate_ids - ids_ammesse
        materie_extra = (Materia.query.filter(Materia.id.in_(ids_extra))
                          .order_by(Materia.nome).all()) if ids_extra else []

        righe.append({
            'docente': d,
            'materie_ammesse': materie_ammesse,
            'materie_extra': materie_extra,
            'assegnate_ids': assegnate_ids,
            'origine_map': origine_map,
        })

    anni_disponibili = sorted(
        {p.anno_scol for p in PianoStudi.query.all()} |
        {cs.anno_scol for cs in ClasseSezione.query.all()},
        reverse=True)
    if anno not in anni_disponibili:
        anni_disponibili.insert(0, anno)

    return render_template('impostazione_anno/docenti_materie.html',
        righe=righe, anno=anno, anni_disponibili=anni_disponibili)


# ── CLASSI ATTIVE ─────────────────────────────────────────────────────
@impostazione_anno_bp.route('/impostazione-anno/classi-attive', methods=['GET', 'POST'])
def classi_attive():
    """
    Gestisce quali sezioni sono attive per anno scolastico — il dato
    variabile da confermare ogni anno prima di tutto il resto.
    Modifica del flag 'attiva' ricalcola automaticamente CalcoloOrganico.
    """
    anno = request.args.get('anno', _anno_default_piano())

    # Template completo di tutte le sezioni possibili per ogni indirizzo.
    # AFM-RIM: le sezioni A e B per ogni anno (1-2 AFM, 3-5 RIM).
    # LSP: una sola sezione per anno (solo A).
    # Tutti gli altri: A e B per tutti gli anni 1-5.
    SEZIONI_TEMPLATE = {
        'AFM': [(1,'A'),(1,'B'),(2,'A'),(2,'B')],
        'RIM': [(3,'A'),(3,'B'),(4,'A'),(4,'B'),(5,'A'),(5,'B')],
        'CAT': [(1,'A'),(1,'B'),(2,'A'),(2,'B'),(3,'A'),(3,'B'),(4,'A'),(4,'B'),(5,'A'),(5,'B')],
        'LSU': [(1,'A'),(1,'B'),(2,'A'),(2,'B'),(3,'A'),(3,'B'),(4,'A'),(4,'B'),(5,'A'),(5,'B')],
        'LSC': [(1,'A'),(1,'B'),(2,'A'),(2,'B'),(3,'A'),(3,'B'),(4,'A'),(4,'B'),(5,'A'),(5,'B')],
        'LLI': [(1,'A'),(1,'B'),(2,'A'),(2,'B'),(3,'A'),(3,'B'),(4,'A'),(4,'B'),(5,'A'),(5,'B')],
        'LSP': [(1,'A'),(2,'A'),(3,'A'),(4,'A'),(5,'A')],
    }
    INDIRIZZI_ORDINE = ['AFM', 'RIM', 'CAT', 'LSU', 'LSC', 'LLI', 'LSP']

    if request.method == 'POST':
        azione = request.form.get('azione', 'salva')
        anno_f = request.form.get('anno_scol', anno)

        if azione == 'prepara_anno':
            # Crea tutte le sezioni del template per il nuovo anno, tutte inattive.
            # Quelle già esistenti vengono ignorate (idempotente).
            n_create = 0
            for ind, sezioni in SEZIONI_TEMPLATE.items():
                for ac, sez in sezioni:
                    esiste = ClasseSezione.query.filter_by(
                        anno_scol=anno_f, indirizzo=ind,
                        anno_corso=ac, sezione=sez).first()
                    if not esiste:
                        db.session.add(ClasseSezione(
                            anno_scol=anno_f, indirizzo=ind,
                            anno_corso=ac, sezione=sez, attiva=False))
                        n_create += 1
            db.session.commit()
            flash(f'Anno {anno_f} preparato: {n_create} sezioni create (tutte inattive — spunta quelle che attiverai).', 'success')
            return redirect(url_for('impostazione_anno.classi_attive', anno=anno_f))

        # Salva checkbox per ogni sezione esistente
        for cs in ClasseSezione.query.filter_by(anno_scol=anno_f).all():
            cs.attiva = request.form.get(f'cs_{cs.id}') == '1'
        db.session.commit()
        _ricalcola_organico(anno_f)
        flash('Classi attive aggiornate e organico ricalcolato.', 'success')
        return redirect(url_for('impostazione_anno.classi_attive', anno=anno_f))

    classi = ClasseSezione.query.filter_by(anno_scol=anno).order_by(
        ClasseSezione.anno_corso, ClasseSezione.sezione).all()

    struttura = {}
    for cs in classi:
        struttura.setdefault(cs.indirizzo, {}).setdefault(cs.anno_corso, []).append(cs)

    anni_disponibili = sorted({cs.anno_scol for cs in ClasseSezione.query.all()}, reverse=True)
    if anno not in anni_disponibili:
        anni_disponibili.insert(0, anno)

    # Lista classi attive per export
    sezioni_attive_list = sorted([
        f'{s.anno_corso}{s.sezione} {s.indirizzo}'
        for s in ClasseSezione.query.filter_by(anno_scol=anno, attiva=True).all()
    ])

    return render_template('impostazione_anno/classi_attive.html',
        struttura=struttura, anno=anno,
        indirizzi_ordine=INDIRIZZI_ORDINE,
        sezioni_template=SEZIONI_TEMPLATE,
        anni_disponibili=anni_disponibili,
        sezioni_attive_list=sezioni_attive_list)


def _ricalcola_organico(anno):
    """
    Ricalcola CalcoloOrganico per tutte le CC in un anno scolastico.
    Tiene conto degli override per-sezione (PianoStudiOverride):
    se una sezione ha un override con CC diversa, le sue ore vanno
    alla CC dell'override, non a quella del piano generale.
    """
    from models.piano_studi import PianoStudiOverride

    # Pre-carica tutti gli override dell'anno: {id_piano_studi: {sezione: id_cc}}
    tutti_override = {}
    for ov in (PianoStudiOverride.query
               .join(PianoStudi, PianoStudiOverride.id_piano_studi == PianoStudi.id)
               .filter(PianoStudi.anno_scol == anno).all()):
        tutti_override.setdefault(ov.id_piano_studi, {})[ov.sezione] = ov.id_cc_override

    # Accumula ore per CC: {id_cc: ore_totali}
    ore_per_cc = {}

    for p in PianoStudi.query.filter_by(anno_scol=anno).all():
        # Le ore in compresenza non generano cattedre autonome —
        # sono già incluse nelle ore della materia principale.
        # Vengono però conteggiate nell'organico dell'ITP (B-xx).
        sezioni_attive = ClasseSezione.query.filter_by(
            anno_scol=anno, indirizzo=p.indirizzo,
            anno_corso=p.anno_corso, attiva=True).all()

        override_sez = tutti_override.get(p.id, {})

        for cs in sezioni_attive:
            cc_id = override_sez.get(cs.sezione, p.id_classe_concorso)
            ore_per_cc[cc_id] = ore_per_cc.get(cc_id, 0) + p.ore_settimanali

    cc_ids = [r.id for r in ClasseConcorso.query.all()]
    for cc_id in cc_ids:
        totale = ore_per_cc.get(cc_id, 0)

        n_coi = totale // 18 if totale else 0
        resto  = totale % 18 if totale else 0
        if totale == 0:
            tipo = None
        elif resto == 0:
            tipo = 'COI'
        elif resto >= 8:
            tipo = 'COE'
        else:
            tipo = 'residue'

        riga = CalcoloOrganico.query.filter_by(anno_scol=anno, id_classe_concorso=cc_id).first()
        if riga:
            # Non tocca tipo_confermato né note_eccezione (sovrascritture manuali)
            riga.ore_totali_calcolate = totale
            riga.n_coi_calcolato = n_coi
            riga.ore_resto_calcolato = resto
            riga.tipo_calcolato = tipo
        else:
            if totale > 0:
                db.session.add(CalcoloOrganico(
                    anno_scol=anno, id_classe_concorso=cc_id,
                    ore_totali_calcolate=totale, n_coi_calcolato=n_coi,
                    ore_resto_calcolato=resto, tipo_calcolato=tipo))
    db.session.commit()


# ── PIANO DI STUDI ────────────────────────────────────────────────────
@impostazione_anno_bp.route('/impostazione-anno/piano-studi', methods=['GET', 'POST'])
def piano_studi():
    """
    Visualizza e modifica il piano di studi per anno scolastico.
    Stabile ma confermabile anno per anno. Consente inserimento delle
    ore mancanti (es. classi prime AFM e CAT 2026/27).
    """
    anno = request.args.get('anno', _anno_default_piano())
    indirizzo_sel = request.args.get('indirizzo', 'AFM')
    INDIRIZZI = ['AFM', 'RIM', 'CAT', 'LSU', 'LSC', 'LLI', 'LSP']

    if request.method == 'POST':
        anno_f      = request.form.get('anno_scol', anno)
        indirizzo_f = request.form.get('indirizzo', indirizzo_sel)
        # Aggiorna le righe esistenti — ore e nome materia
        # Prima costruisce un dizionario id→nuovo_nome dalle chiavi nome_<id>
        nuovi_nomi = {}
        for key, val in request.form.items():
            if key.startswith('nome_') and val.strip():
                try:
                    nuovi_nomi[int(key.replace('nome_', ''))] = val.strip()
                except ValueError:
                    pass

        for key, val in request.form.items():
            if not key.startswith('ore_'):
                continue
            try:
                ps_id = int(key.replace('ore_', ''))
            except ValueError:
                continue
            ps = db.session.get(PianoStudi, ps_id)
            if not ps:
                continue
            try:
                ps.ore_settimanali = int(val) if val else 0
            except ValueError:
                pass
            # Se il nome per questo id è presente, aggiorna tutte le righe
            # con lo stesso vecchio nome nella stessa CC/indirizzo/anno (mantenendo
            # la coerenza: tutte le sezioni di quella materia cambiano nome insieme)
            if ps_id in nuovi_nomi:
                nuovo_nome = nuovi_nomi[ps_id]
                vecchio_nome = ps.nome_materia_locale
                if nuovo_nome != vecchio_nome:
                    # Aggiorna tutte le righe con lo stesso vecchio nome nella stessa CC
                    righe_stessa_materia = PianoStudi.query.filter_by(
                        anno_scol=anno_f, indirizzo=indirizzo_f,
                        id_classe_concorso=ps.id_classe_concorso,
                        nome_materia_locale=vecchio_nome).all()
                    for r in righe_stessa_materia:
                        r.nome_materia_locale = nuovo_nome

        # Gestisce cambio CC (atipicità): campo cc_<id> → nuova CC per quella
        # riga specifica (singolo anno di corso). Non propaga ad altri anni.
        for key, val in request.form.items():
            if not key.startswith('cc_') or not val.isdigit():
                continue
            try:
                ps_id = int(key.replace('cc_', ''))
            except ValueError:
                continue
            ps = db.session.get(PianoStudi, ps_id)
            if ps:
                nuova_cc_id = int(val)
                ps.id_classe_concorso = nuova_cc_id
                # Atipica = True se la CC scelta diverge dal default normativo
                ps.atipica = (nuova_cc_id != ps.id_cc_default)

        db.session.commit()
        _ricalcola_organico(anno_f)
        flash('Piano di studi aggiornato e organico ricalcolato.', 'success')
        return redirect(url_for('impostazione_anno.piano_studi', anno=anno_f, indirizzo=indirizzo_f))

    # Carica le righe per l'indirizzo selezionato, raggruppate per CC e anno_corso
    righe = (PianoStudi.query
             .filter_by(anno_scol=anno, indirizzo=indirizzo_sel)
             .join(ClasseConcorso, PianoStudi.id_classe_concorso == ClasseConcorso.id)
             .order_by(ClasseConcorso.codice, PianoStudi.nome_materia_locale, PianoStudi.anno_corso)
             .all())

    # Raggruppa per CC, poi per materia — pre-elaborato in Python
    # per evitare problemi con il groupby Jinja2 su sequenze non contigue.
    # Struttura: da_cc[cc_cod] = {'cc': ClasseConcorso, 'materie': {nome: [righe per anno]}}
    da_cc_raw = {}
    for r in righe:
        cc_cod = r.classe_concorso.codice
        if cc_cod not in da_cc_raw:
            da_cc_raw[cc_cod] = {'cc': r.classe_concorso, 'materie': {}}
        nome = r.nome_materia_locale
        if nome not in da_cc_raw[cc_cod]['materie']:
            da_cc_raw[cc_cod]['materie'][nome] = []
        da_cc_raw[cc_cod]['materie'][nome].append(r)
    # Converte in lista ordinata per il template.
    # Per ogni materia costruisce anche 'righe_per_anno': dict anno_corso→riga
    # cosi' il template accede direttamente per chiave senza selectattr.
    da_cc = {}
    for cc_cod, val in da_cc_raw.items():
        materie_list = []
        for nome, rr in val['materie'].items():
            rr_ord = sorted(rr, key=lambda r: r.anno_corso)
            materie_list.append({
                'nome': nome,
                'righe': rr_ord,
                'prima_riga': rr_ord[0],
                'righe_per_anno': {r.anno_corso: r for r in rr_ord},
            })
        da_cc[cc_cod] = {'cc': val['cc'], 'materie': materie_list}

    # Anni di corso presenti per questo indirizzo
    anni_corso = sorted({r.anno_corso for r in righe}) if righe else list(range(1, 6))

    # Classi sezioni per evidenziare quelle attive/mancanti
    sezioni_attive = {
        (cs.anno_corso, cs.sezione)
        for cs in ClasseSezione.query.filter_by(anno_scol=anno, indirizzo=indirizzo_sel, attiva=True).all()
    }

    anni_disponibili = sorted({p.anno_scol for p in PianoStudi.query.all()}, reverse=True)
    if anno not in anni_disponibili:
        anni_disponibili.insert(0, anno)

    # Per ogni materia con più CC possibili, costruisce la mappa
    # id_materia → lista di (id_cc, codice_cc) — usata dal template per
    # mostrare il select di scelta CC solo dove ha senso.
    from models.classe_concorso import MateriaClasseConcorso
    materie_multi_cc = {}
    for r in righe:
        if not r.id_materia or r.id_materia in materie_multi_cc:
            continue
        opzioni = (MateriaClasseConcorso.query
                   .filter_by(id_materia=r.id_materia)
                   .join(ClasseConcorso, MateriaClasseConcorso.id_classe_concorso == ClasseConcorso.id)
                   .all())
        if len(opzioni) > 1:
            materie_multi_cc[r.id_materia] = [
                {'id': o.id_classe_concorso, 'codice': o.classe_concorso.codice}
                for o in opzioni
            ]

    tutte_materie = Materia.query.filter_by(attiva=True).order_by(Materia.sigla).all()

    # Totale ore settimanali curricolari per anno (esclude righe in compresenza)
    ore_per_anno = {}
    for ac in anni_corso:
        tot = db.session.query(
            db.func.sum(PianoStudi.ore_settimanali)
        ).filter(
            PianoStudi.anno_scol == anno,
            PianoStudi.indirizzo == indirizzo_sel,
            PianoStudi.anno_corso == ac,
            PianoStudi.compresenza == False
        ).scalar() or 0
        ore_per_anno[ac] = tot

    # CC già presenti nel piano studi per questo indirizzo+anno
    cc_presenti_ids = {r.id_classe_concorso for r in righe}
    # CC non ancora presenti — disponibili per essere aggiunte
    cc_mancanti = (ClasseConcorso.query
                   .filter(ClasseConcorso.attiva == True,
                           ~ClasseConcorso.id.in_(cc_presenti_ids))
                   .order_by(ClasseConcorso.codice).all())

    # Override per-sezione: {id_piano_studi: [{ov}, ...]}
    from models.piano_studi import PianoStudiOverride
    ids_piano = [r.id for r in righe]
    override_map = {}
    if ids_piano:
        for ov in PianoStudiOverride.query.filter(
                PianoStudiOverride.id_piano_studi.in_(ids_piano)).all():
            override_map.setdefault(ov.id_piano_studi, []).append(ov)

    return render_template('impostazione_anno/piano_studi.html',
        anno=anno, indirizzo=indirizzo_sel, indirizzi=INDIRIZZI,
        da_cc=da_cc, anni_corso=anni_corso,
        sezioni_attive=sezioni_attive,
        anni_disponibili=anni_disponibili,
        materie_multi_cc=materie_multi_cc,
        tutte_materie=tutte_materie,
        override_map=override_map,
        cc_mancanti=cc_mancanti,
        ore_per_anno=ore_per_anno)


# ── PIANO STUDI: aggiungi / elimina riga ──────────────────────────────
@impostazione_anno_bp.route('/impostazione-anno/piano-studi/aggiungi', methods=['POST'])
def piano_studi_aggiungi():
    anno      = request.form.get('anno_scol')
    indirizzo = request.form.get('indirizzo')
    # Supporta sia singolo anno (select) che più anni (checkbox: anni_corso[])
    anni_raw  = request.form.getlist('anno_corso')
    if not anni_raw:
        anni_raw = request.form.getlist('anni_corso[]')
    anni_selezionati = sorted(set(int(a) for a in anni_raw if str(a).isdigit()))
    if not anni_selezionati:
        anni_selezionati = [1]  # fallback

    id_cc    = int(request.form.get('id_cc')) if request.form.get('id_cc') else None
    id_mat   = int(request.form.get('id_materia')) if request.form.get('id_materia') else None
    nome_loc = request.form.get('nome_materia_locale', '').strip()
    ore      = int(request.form.get('ore_settimanali') or 0)

    if not (anno and indirizzo and id_cc and nome_loc):
        flash('Compilare tutti i campi obbligatori.', 'danger')
        return redirect(url_for('impostazione_anno.piano_studi', anno=anno, indirizzo=indirizzo))

    cc = db.session.get(ClasseConcorso, id_cc)
    n_aggiunte = 0
    n_esistenti = 0
    for anno_corso in anni_selezionati:
        esiste = PianoStudi.query.filter_by(
            anno_scol=anno, indirizzo=indirizzo, anno_corso=anno_corso,
            id_classe_concorso=id_cc, nome_materia_locale=nome_loc).first()
        if esiste:
            n_esistenti += 1
        else:
            # Controlla anche il vincolo UNIQUE su id_materia (se fornita)
            if id_mat:
                esiste_mat = PianoStudi.query.filter_by(
                    anno_scol=anno, indirizzo=indirizzo, anno_corso=anno_corso,
                    id_classe_concorso=id_cc, id_materia=id_mat).first()
                if esiste_mat:
                    n_esistenti += 1
                    continue
            # Sincronizza MateriaClasseConcorso: se la combinazione materia+CC
            # non esiste ancora, la aggiunge automaticamente come 'normativa'
            if id_mat:
                from models.classe_concorso import MateriaClasseConcorso
                mcc_esiste = MateriaClasseConcorso.query.filter_by(
                    id_materia=id_mat, id_classe_concorso=id_cc).first()
                if not mcc_esiste:
                    db.session.add(MateriaClasseConcorso(
                        id_materia=id_mat, id_classe_concorso=id_cc,
                        fonte='normativa',
                        riferimento='Aggiunta da piano studi'))

            # compresenza automatica: True se la CC è di tipo B (ITP)
            is_compresenza = cc.codice.startswith('B-') if cc else False
            db.session.add(PianoStudi(
                anno_scol=anno, indirizzo=indirizzo, anno_corso=anno_corso,
                id_classe_concorso=id_cc, id_cc_default=id_cc,
                id_materia=id_mat, nome_materia_locale=nome_loc,
                ore_settimanali=ore, atipica=False,
                compresenza=is_compresenza))
            n_aggiunte += 1

    try:
        if n_aggiunte:
            db.session.commit()
            _ricalcola_organico(anno)
            anni_str = ', '.join(f'{a}°' for a in sorted(anni_selezionati))
            msg = f'Aggiunta: {nome_loc} ({cc.codice if cc else "?"}) {indirizzo} anni {anni_str}'
            if n_esistenti:
                msg += f' ({n_esistenti} già presenti, saltati)'
            flash(msg, 'success')
        else:
            flash('Tutte le righe selezionate erano già presenti.', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore: {str(e)[:120]}', 'danger')

    return redirect(url_for('impostazione_anno.piano_studi', anno=anno, indirizzo=indirizzo))


@impostazione_anno_bp.route('/impostazione-anno/piano-studi/elimina/<int:ps_id>', methods=['POST'])
def piano_studi_elimina(ps_id):
    ps = db.session.get(PianoStudi, ps_id)
    if not ps:
        flash('Riga non trovata.', 'danger')
        return redirect(url_for('impostazione_anno.piano_studi'))

    anno      = ps.anno_scol
    indirizzo = ps.indirizzo
    nome      = ps.nome_materia_locale
    ac        = ps.anno_corso
    db.session.delete(ps)
    db.session.commit()
    _ricalcola_organico(anno)
    flash(f'Eliminata: {nome} {indirizzo} {ac}° anno.', 'success')
    return redirect(url_for('impostazione_anno.piano_studi', anno=anno, indirizzo=indirizzo))


@impostazione_anno_bp.route('/impostazione-anno/piano-studi/elimina-multi', methods=['POST'])
def piano_studi_elimina_multi():
    """
    Elimina in un'unica richiesta tutte le righe di piano studi indicate
    (una materia su più anni di corso, o tutte le materie di un gruppo
    multi-materia nella stessa classe di concorso). Sostituisce il vecchio
    pattern JS che inviava più form in sequenza — solo il primo veniva
    eseguito perché il submit di un form causa la navigazione della pagina.
    """
    ids = [int(x) for x in request.form.getlist('ids[]') if x.strip()]
    if not ids:
        flash('Nessuna riga da eliminare.', 'warning')
        return redirect(url_for('impostazione_anno.piano_studi'))

    righe = PianoStudi.query.filter(PianoStudi.id.in_(ids)).all()
    if not righe:
        flash('Righe non trovate.', 'danger')
        return redirect(url_for('impostazione_anno.piano_studi'))

    anno      = righe[0].anno_scol
    indirizzo = righe[0].indirizzo
    nomi = sorted({r.nome_materia_locale for r in righe})
    n = len(righe)
    for r in righe:
        db.session.delete(r)
    db.session.commit()
    _ricalcola_organico(anno)
    flash(f'Eliminate {n} righe ({", ".join(nomi)}) — {indirizzo}.', 'success')
    return redirect(url_for('impostazione_anno.piano_studi', anno=anno, indirizzo=indirizzo))


# ── CALCOLO ORGANICO ──────────────────────────────────────────────────
@impostazione_anno_bp.route('/impostazione-anno/calcolo-organico', methods=['GET', 'POST'])
def calcolo_organico():
    """
    Mostra il calcolo COI/COE/residue per ogni CC. Permette di
    sovrascrivere manualmente il tipo per i casi eccezionali (es. 10
    ore classificate come residue invece di COE) e di confermare il
    calcolo prima di inviare la richiesta all'USR.
    Export XLSX con la struttura pivot originale (Monteore OD).
    """
    anno = request.args.get('anno', _anno_default_piano())

    if request.method == 'POST':
        azione = request.form.get('azione', '')
        anno_f = request.form.get('anno_scol', anno)

        if azione == 'ricalcola':
            _ricalcola_organico(anno_f)
            flash('Organico ricalcolato.', 'success')
            return redirect(url_for('impostazione_anno.calcolo_organico', anno=anno_f))

        if azione == 'conferma_tutto':
            CalcoloOrganico.query.filter_by(anno_scol=anno_f).update({'confermato': True})
            db.session.commit()
            flash('Calcolo confermato per tutte le classi di concorso.', 'success')
            return redirect(url_for('impostazione_anno.calcolo_organico', anno=anno_f))

        # Salva sovrascritture manuali
        for key, val in request.form.items():
            if not key.startswith('tipo_'):
                continue
            co_id = int(key.replace('tipo_', ''))
            co = CalcoloOrganico.query.get(co_id)
            if co:
                co.tipo_confermato = val if val else None
                co.note_eccezione  = request.form.get(f'note_{co_id}', '')
                co.confermato      = bool(request.form.get(f'conf_{co_id}'))
        db.session.commit()
        flash('Sovrascritture salvate.', 'success')
        return redirect(url_for('impostazione_anno.calcolo_organico', anno=anno_f))

    righe = (CalcoloOrganico.query
             .join(ClasseConcorso)
             .filter(CalcoloOrganico.anno_scol == anno)
             .order_by(ClasseConcorso.codice).all())

    # Dividi per tipo effettivo per i contatori in cima
    totale_ore = sum(r.ore_totali_calcolate for r in righe)
    n_confermati = sum(1 for r in righe if r.confermato)
    n_eccezioni  = sum(1 for r in righe if r.tipo_confermato)

    anni_disponibili = sorted({r.anno_scol for r in CalcoloOrganico.query.all()}, reverse=True)
    if anno not in anni_disponibili:
        anni_disponibili.insert(0, anno)

    return render_template('impostazione_anno/calcolo_organico.html',
        righe=righe, anno=anno, anni_disponibili=anni_disponibili,
        totale_ore=totale_ore, n_confermati=n_confermati, n_eccezioni=n_eccezioni)


# ── AUTOSAVE API ──────────────────────────────────────────────────────
@impostazione_anno_bp.route('/impostazione-anno/api/save', methods=['POST'])
def api_save():
    """
    Endpoint atomico per autosave: riceve {campo, id, valore, extra}
    e aggiorna il singolo record corrispondente. Risponde con JSON.
    """
    data   = request.get_json(force=True) or {}
    campo  = data.get('campo', '')
    rec_id = data.get('id')
    valore = data.get('valore')
    extra  = data.get('extra', {})  # parametri aggiuntivi (anno_scol, ecc.)

    try:
        # ── Piano studi: ore settimanali ──────────────────────────────
        if campo == 'ore_piano':
            ps = db.session.get(PianoStudi, int(rec_id))
            if not ps:
                return jsonify(ok=False, msg='Riga non trovata')
            ps.ore_settimanali = int(valore) if valore != '' else 0
            db.session.commit()
            _ricalcola_organico(ps.anno_scol)
            return jsonify(ok=True, msg='Ore aggiornate')

        # ── Piano studi: nome materia locale ─────────────────────────
        elif campo == 'nome_piano':
            ps = db.session.get(PianoStudi, int(rec_id))
            if not ps:
                return jsonify(ok=False, msg='Riga non trovata')
            vecchio_nome = ps.nome_materia_locale
            nuovo_nome   = str(valore).strip()
            if nuovo_nome and nuovo_nome != vecchio_nome:
                # Aggiorna tutte le righe con lo stesso vecchio nome
                # nella stessa CC/indirizzo/anno_scol
                for r in PianoStudi.query.filter_by(
                        anno_scol=ps.anno_scol, indirizzo=ps.indirizzo,
                        id_classe_concorso=ps.id_classe_concorso,
                        nome_materia_locale=vecchio_nome).all():
                    r.nome_materia_locale = nuovo_nome
                db.session.commit()
            return jsonify(ok=True, msg='Nome aggiornato')

        # ── Piano studi: classe di concorso (atipicità) ──────────────
        elif campo == 'cc_piano':
            ps = db.session.get(PianoStudi, int(rec_id))
            if not ps:
                return jsonify(ok=False, msg='Riga non trovata')
            nuova_cc_id = int(valore)
            ps.id_classe_concorso = nuova_cc_id
            ps.atipica = (nuova_cc_id != ps.id_cc_default)
            db.session.commit()
            _ricalcola_organico(ps.anno_scol)
            return jsonify(ok=True, msg='CC aggiornata',
                           atipica=ps.atipica)

        # ── Classi attive: checkbox ───────────────────────────────────
        elif campo == 'cs_attiva':
            cs = db.session.get(ClasseSezione, int(rec_id))
            if not cs:
                return jsonify(ok=False, msg='Sezione non trovata')
            cs.attiva = bool(valore)
            db.session.commit()
            _ricalcola_organico(cs.anno_scol)
            return jsonify(ok=True, msg='Sezione aggiornata')

        # ── Calcolo organico: tipo confermato ────────────────────────
        elif campo == 'tipo_organico':
            co = db.session.get(CalcoloOrganico, int(rec_id))
            if not co:
                return jsonify(ok=False, msg='Riga non trovata')
            co.tipo_confermato = str(valore) if valore else None
            db.session.commit()
            return jsonify(ok=True, msg='Tipo aggiornato')

        # ── Calcolo organico: note eccezione ─────────────────────────
        elif campo == 'note_organico':
            co = db.session.get(CalcoloOrganico, int(rec_id))
            if not co:
                return jsonify(ok=False, msg='Riga non trovata')
            co.note_eccezione = str(valore) if valore else None
            db.session.commit()
            return jsonify(ok=True, msg='Note aggiornate')

        # ── Calcolo organico: confermato ──────────────────────────────
        elif campo == 'conf_organico':
            co = db.session.get(CalcoloOrganico, int(rec_id))
            if not co:
                return jsonify(ok=False, msg='Riga non trovata')
            co.confermato = bool(valore)
            db.session.commit()
            return jsonify(ok=True, msg='Conferma aggiornata')

        # ── Organico USR: ore residue ─────────────────────────────────
        elif campo == 'ore_residue_organico':
            from models.classe_concorso import CattedraOrganico
            co = db.session.get(CattedraOrganico, int(rec_id))
            if not co:
                return jsonify(ok=False, msg='Riga non trovata')
            co.ore_residue = int(valore) if valore != '' else 0
            db.session.commit()
            return jsonify(ok=True, msg='Ore residue aggiornate')

        # ── Piano studi: compresenza (per anno, solo CC B-xx) ──────────
        elif campo == 'compresenza_piano':
            ps = db.session.get(PianoStudi, int(rec_id))
            if not ps:
                return jsonify(ok=False, msg='Riga non trovata')
            ps.compresenza = bool(valore)
            db.session.commit()
            _ricalcola_organico(ps.anno_scol)
            return jsonify(ok=True, msg='Compresenza aggiornata')

        # ── Materia: nome breve ──────────────────────────────────────
        elif campo == 'nome_breve_mat':
            m = db.session.get(Materia, int(rec_id))
            if not m:
                return jsonify(ok=False, msg='Materia non trovata')
            m.nome_breve = str(valore).strip() or None
            db.session.commit()
            return jsonify(ok=True, msg='Nome breve aggiornato')

        # ── Materia: alias ────────────────────────────────────────────
        elif campo == 'alias_mat':
            m = db.session.get(Materia, int(rec_id))
            if not m:
                return jsonify(ok=False, msg='Materia non trovata')
            m.alias = str(valore).strip().upper() or None
            db.session.commit()
            return jsonify(ok=True, msg='Alias aggiornato')

        else:
            return jsonify(ok=False, msg=f'Campo sconosciuto: {campo}')

    except Exception as e:
        db.session.rollback()
        return jsonify(ok=False, msg=str(e))


# ── API cerca CC per codice ──────────────────────────────────────────
@impostazione_anno_bp.route('/impostazione-anno/api/cerca-cc')
def api_cerca_cc():
    codice = request.args.get('codice', '').strip().upper()
    cc = ClasseConcorso.query.filter_by(codice=codice).first()
    if cc:
        return jsonify(id=cc.id, codice=cc.codice, nome=cc.nome)
    return jsonify(id=None)


# ── OVERRIDE PER-SEZIONE ──────────────────────────────────────────────
@impostazione_anno_bp.route('/impostazione-anno/piano-studi/override', methods=['POST'])
def piano_studi_override_salva():
    """
    Crea o aggiorna un override per-sezione.
    Riceve: id_piano_studi, sezione, id_cc_override, note.
    Se esiste già per (id_piano_studi, sezione), lo aggiorna.
    """
    from models.piano_studi import PianoStudiOverride
    id_ps    = request.form.get('id_piano_studi', type=int)
    sezione  = request.form.get('sezione', '').strip().upper()
    id_cc    = request.form.get('id_cc_override', type=int)
    note     = request.form.get('note', '').strip()

    if not (id_ps and sezione and id_cc):
        flash('Compilare tutti i campi.', 'danger')
        return redirect(request.referrer or url_for('impostazione_anno.piano_studi'))

    ps = db.session.get(PianoStudi, id_ps)
    if not ps:
        flash('Riga piano studi non trovata.', 'danger')
        return redirect(request.referrer or url_for('impostazione_anno.piano_studi'))

    ov = PianoStudiOverride.query.filter_by(
        id_piano_studi=id_ps, sezione=sezione).first()
    if ov:
        ov.id_cc_override = id_cc
        ov.atipica = (id_cc != ps.id_cc_default)
        ov.note = note
    else:
        ov = PianoStudiOverride(
            id_piano_studi=id_ps, sezione=sezione,
            id_cc_override=id_cc,
            atipica=(id_cc != ps.id_cc_default),
            note=note)
        db.session.add(ov)

    db.session.commit()
    _ricalcola_organico(ps.anno_scol)
    flash(f'Override sezione {sezione} salvato.', 'success')
    return redirect(url_for('impostazione_anno.piano_studi',
                            anno=ps.anno_scol, indirizzo=ps.indirizzo))


@impostazione_anno_bp.route('/impostazione-anno/piano-studi/override/<int:ov_id>/elimina',
                             methods=['POST'])
def piano_studi_override_elimina(ov_id):
    """Elimina un override per-sezione e ricalcola l'organico."""
    from models.piano_studi import PianoStudiOverride
    ov = db.session.get(PianoStudiOverride, ov_id)
    if not ov:
        flash('Override non trovato.', 'danger')
        return redirect(url_for('impostazione_anno.piano_studi'))

    ps     = db.session.get(PianoStudi, ov.id_piano_studi)
    anno   = ps.anno_scol
    ind    = ps.indirizzo
    sezione = ov.sezione
    db.session.delete(ov)
    db.session.commit()
    _ricalcola_organico(anno)
    flash(f'Override sezione {sezione} eliminato.', 'success')
    return redirect(url_for('impostazione_anno.piano_studi', anno=anno, indirizzo=ind))


# ── VERIFICA COPERTURA ORE ────────────────────────────────────────────
def _verifica_copertura(anno):
    """
    Controlla che ogni riga del piano studi abbia le sue ore interamente
    coperte da qualche CC (generale o override per-sezione), per ogni
    sezione attiva.

    Restituisce lista di dict con le anomalie trovate:
      - tipo 'scoperta': ore del piano non assegnate a nessuna CC
        (non dovrebbe succedere — significherebbe un bug nel calcolo)
      - tipo 'eccesso': ore assegnate superano quelle del piano
        (potrebbe indicare un override errato)

    In condizioni normali la lista è vuota.
    """
    from models.piano_studi import PianoStudiOverride
    anomalie = []

    # Pre-carica override: {id_piano_studi: {sezione: id_cc}}
    tutti_override = {}
    for ov in (PianoStudiOverride.query
               .join(PianoStudi, PianoStudiOverride.id_piano_studi == PianoStudi.id)
               .filter(PianoStudi.anno_scol == anno).all()):
        tutti_override.setdefault(ov.id_piano_studi, {})[ov.sezione] = ov.id_cc_override

    for p in PianoStudi.query.filter_by(anno_scol=anno).all():
        sezioni_attive = ClasseSezione.query.filter_by(
            anno_scol=anno, indirizzo=p.indirizzo,
            anno_corso=p.anno_corso, attiva=True).all()

        if not sezioni_attive:
            continue

        ore_attese   = p.ore_settimanali * len(sezioni_attive)
        ore_coperte  = p.ore_settimanali * len(sezioni_attive)  # per costruzione, sempre coperte
        # (ogni sezione va o alla CC generale o all'override — non esiste "scoperta"
        #  a meno di un bug nel modello; verifichiamo invece la coerenza degli override)

        override_sez = tutti_override.get(p.id, {})

        # Verifica: gli override dichiarano sezioni che non esistono?
        sezioni_esistenti = {cs.sezione for cs in sezioni_attive}
        for sez_ov in override_sez:
            if sez_ov not in sezioni_esistenti:
                anomalie.append({
                    'tipo': 'override_sezione_inattiva',
                    'indirizzo': p.indirizzo,
                    'anno_corso': p.anno_corso,
                    'materia': p.nome_materia_locale,
                    'cc_generale': p.classe_concorso.codice,
                    'sezione': sez_ov,
                    'msg': (f'{p.nome_materia_locale} {p.indirizzo} {p.anno_corso}° anno: '
                            f'override per sezione {sez_ov} ma quella sezione non è attiva')
                })

    # Seconda verifica: il totale ore nel CalcoloOrganico batte con il piano studi?
    # Somma attesa = sum(ore_settimanali × n_sezioni_attive) per ogni riga piano
    ore_attese_per_cc = {}
    for p in PianoStudi.query.filter_by(anno_scol=anno).all():
        sezioni = ClasseSezione.query.filter_by(
            anno_scol=anno, indirizzo=p.indirizzo,
            anno_corso=p.anno_corso, attiva=True).all()
        override_sez = tutti_override.get(p.id, {})
        for cs in sezioni:
            cc_id = override_sez.get(cs.sezione, p.id_classe_concorso)
            ore_attese_per_cc[cc_id] = ore_attese_per_cc.get(cc_id, 0) + p.ore_settimanali

    totale_atteso  = sum(ore_attese_per_cc.values())
    totale_calcolo = sum(
        co.ore_totali_calcolate
        for co in CalcoloOrganico.query.filter_by(anno_scol=anno).all()
    )

    if totale_atteso != totale_calcolo:
        anomalie.append({
            'tipo': 'totale_discordante',
            'msg': (f'Totale ore attese dal piano studi ({totale_atteso}h) '
                    f'≠ totale nel calcolo organico ({totale_calcolo}h). '
                    f'Premi "Ricalcola" per allineare.'),
            'indirizzo': '', 'anno_corso': 0,
            'materia': '', 'cc_generale': '', 'sezione': ''
        })

    return anomalie


@impostazione_anno_bp.route('/impostazione-anno/api/verifica-copertura')
def api_verifica_copertura():
    anno = request.args.get('anno', _anno_default_piano())
    anomalie = _verifica_copertura(anno)
    return jsonify(ok=len(anomalie) == 0, anomalie=anomalie, anno=anno)


# ── PREPARAZIONE ANNO — DOCENTI ──────────────────────────────────────
@impostazione_anno_bp.route('/impostazione-anno/docenti-anno', methods=['GET', 'POST'])
def docenti_anno():
    """
    Gestione pluriennale dei docenti per anno scolastico.
    Gestisce: uscite TI, AP entranti/uscenti, aspettative,
    nuovi TI, IRC, TD/supplenti.
    """
    from config_anno import get_anno_corrente
    anno = request.args.get('anno', _anno_default_piano())

    if request.method == 'POST':
        azione = request.form.get('azione', '')
        anno_f = request.form.get('anno_scol', anno)
        doc_id = request.form.get('id_docente')
        d = db.session.get(Docente, int(doc_id)) if doc_id else None

        if azione == 'segna_uscita' and d:
            d.anno_scol_uscita = anno_f
            d.motivo_uscita    = request.form.get('motivo', 'trasferimento')
            d.status_presenza  = 'presente'
            db.session.commit()
            flash(f'{d.cognome} {d.nome}: segnato come {d.motivo_uscita} da {anno_f}.', 'success')

        elif azione == 'segna_ap_uscente' and d:
            d.status_presenza = 'ap_uscente'
            d.scuola_ap       = request.form.get('scuola_ap', '').strip() or None
            db.session.commit()
            flash(f'{d.cognome} {d.nome}: segnato come AP uscente.', 'success')

        elif azione == 'segna_aspettativa' and d:
            d.status_presenza = 'aspettativa'
            db.session.commit()
            flash(f'{d.cognome} {d.nome}: segnato in aspettativa.', 'success')

        elif azione == 'annulla_status' and d:
            d.status_presenza = 'presente'
            d.scuola_ap       = None
            db.session.commit()
            flash(f'{d.cognome} {d.nome}: status ripristinato a presente.', 'success')

        elif azione == 'conferma_contratti_anno':
            # Conferma cumulativa: un selettore per ogni docente
            # (precompilato col contratto storico se già registrato,
            # altrimenti col corrente), un solo invio per tutti — invece
            # di salvare riga per riga. Registra il contratto DI QUESTO
            # anno_f senza toccare Docente.tipo_contratto (il "corrente"/
            # più recente): serve a preparare il prossimo anno per un
            # docente con contratto annuale che sta per cambiare (es. TD
            # che entra in ruolo, diventa TI) senza perdere il contratto
            # vero dell'anno che si sta ancora chiudendo. Vedi
            # models.docente.DocenteContrattoAnno — segnalato da
            # Roberto, caso Agrò.
            from models.docente import DocenteContrattoAnno
            righe_esistenti = {
                r.id_docente: r for r in
                DocenteContrattoAnno.query.filter_by(anno_scol=anno_f).all()
            }
            n_confermati = 0
            for key, val in request.form.items():
                if not key.startswith('tipo_contratto_') or not val:
                    continue
                try:
                    doc_id = int(key[len('tipo_contratto_'):])
                except ValueError:
                    continue
                riga = righe_esistenti.get(doc_id)
                if riga:
                    riga.tipo_contratto = val
                else:
                    db.session.add(DocenteContrattoAnno(
                        id_docente=doc_id, anno_scol=anno_f, tipo_contratto=val))
                n_confermati += 1
            db.session.commit()
            flash(f'Contratti {anno_f} confermati per {n_confermati} docenti.', 'success')

        elif azione == 'annulla_uscita' and d:
            d.anno_scol_uscita = None
            d.motivo_uscita    = None
            db.session.commit()
            flash(f'{d.cognome} {d.nome}: uscita annullata.', 'success')

        elif azione == 'aggiungi_docente':
            cognome   = request.form.get('cognome', '').strip().upper()
            nome      = request.form.get('nome', '').strip()
            tipo_c    = request.form.get('tipo_contratto', 'TD_annuale')
            ruolo     = request.form.get('ruolo', 'titolare')
            scuola_ap = request.form.get('scuola_ap', '').strip() or None
            if not (cognome and nome):
                flash('Inserisci cognome e nome.', 'danger')
            else:
                # I TI nuovi e gli IRC non hanno anno_scol_inizio futuro —
                # sono immessi in ruolo con decorrenza specifica, trattati
                # come TI storici ma con anno_scol_inizio impostato.
                # Le AP entranti vengono inserite come TI con status ap_entrante
                # e anno_scol_inizio = anno corrente.
                tipo_reale = 'TI' if tipo_c in ('TI', 'IRC', 'ap_entrante') else tipo_c
                status = 'ap_entrante' if tipo_c == 'ap_entrante' else 'presente'
                tipo_contratto_finale = 'IRC' if tipo_c == 'IRC' else tipo_reale
                new_d = Docente(
                    cognome=cognome, nome=nome,
                    tipo_contratto=tipo_contratto_finale,
                    ruolo=ruolo,
                    anno_scol_inizio=anno_f,
                    status_presenza=status,
                    scuola_ap=scuola_ap,
                    attivo=True)
                db.session.add(new_d)
                db.session.commit()
                flash(f'{cognome} {nome} ({tipo_c}) aggiunto per {anno_f}.', 'success')

        return redirect(url_for('impostazione_anno.docenti_anno', anno=anno_f))

    # ── Dati per il template ─────────────────────────────────────────
    # Un solo meccanismo di gestione presenza per anno, valido per
    # QUALUNQUE tipo di contratto (TI e non-TI): un docente compare qui
    # se è attivo, non è già stato segnalato come uscito per questo
    # anno (altrimenti è nella sezione "Uscite" sotto) e non è stato
    # nominato proprio in questo anno (altrimenti è già nella sezione
    # "Docenti inseriti per {{anno}}" sotto, che è puramente informativa
    # — evita di mostrare lo stesso docente in due sezioni; quella
    # sezione include ORA anche i TI, non solo TD/supplenti, altrimenti
    # un TI neoimmesso con anno_scol_inizio == anno finiva escluso da
    # entrambe — vedi commento più sotto).
    # Prima versione (fino a questo Task): la pagina considerava solo i
    # TI, i TD/supplenti restavano esclusi "di proposito" — ma questo
    # rendeva impossibile segnalarne l'uscita quando non più in
    # servizio (es. caso Cantarella, TD annuale senza anno_scol_inizio
    # tracciato: non compariva né qui né altrove). Un tentativo
    # precedente aveva aggiunto una sezione parallela dedicata ai
    # non-TI — creava due meccanismi sovrapposti per lo stesso scopo;
    # su richiesta di Roberto, unificato in un solo meccanismo.
    docenti_gestione = (Docente.query
                 .filter(Docente.attivo == True,
                         db.or_(Docente.anno_scol_uscita == None,
                                Docente.anno_scol_uscita != anno),
                         db.or_(Docente.anno_scol_inizio == None,
                                Docente.anno_scol_inizio != anno))
                 .order_by(Docente.cognome).all())

    # Uscite segnalate per questo anno (qualunque tipo di contratto)
    uscenti = (Docente.query
               .filter_by(attivo=True, anno_scol_uscita=anno)
               .order_by(Docente.cognome).all())

    # AP uscenti (titolari qui che insegnano altrove quest'anno)
    ap_uscenti = (Docente.query
                  .filter_by(attivo=True, status_presenza='ap_uscente')
                  .order_by(Docente.cognome).all())

    # AP entranti (titolari altrove che insegnano qui)
    ap_entranti = (Docente.query
                   .filter_by(attivo=True, status_presenza='ap_entrante')
                   .order_by(Docente.cognome).all())

    # Docenti inseriti per questo anno specifico, di qualunque tipo di
    # contratto (informativo: non hanno bisogno del pulsante "Esce"
    # nello stesso anno in cui sono appena arrivati — sono già esclusi
    # da docenti_gestione sopra). Prima escludeva i TI assumendo che un
    # TI con anno_scol_inizio == anno fosse sempre uno "storico" già
    # tracciato altrove — falso per un neoimmesso in ruolo che entra
    # esattamente in questo anno (es. Di Liberto, 2026-2027): un TI
    # così finiva escluso sia da qui (tipo_contratto == 'TI') sia da
    # docenti_gestione (anno_scol_inizio == anno), invisibile ovunque
    # sulla pagina pur comparendo in Anagrafica docenti — segnalato da
    # Roberto.
    td_anno = (Docente.query
               .filter(Docente.attivo == True,
                       Docente.anno_scol_inizio == anno)
               .order_by(Docente.cognome).all())

    anni_disponibili = sorted(
        {p.anno_scol for p in PianoStudi.query.all()} |
        {cs.anno_scol for cs in ClasseSezione.query.all()},
        reverse=True)
    if anno not in anni_disponibili:
        anni_disponibili.insert(0, anno)

    from models.docente import DocenteContrattoAnno, TIPO_CONTRATTO_LABELS
    contratti_anno_map = {
        c.id_docente: c.tipo_contratto for c in
        DocenteContrattoAnno.query.filter_by(anno_scol=anno).all()
    }

    return render_template('impostazione_anno/docenti_anno.html',
        anno=anno, anni_disponibili=anni_disponibili,
        docenti_gestione=docenti_gestione, uscenti=uscenti,
        ap_uscenti=ap_uscenti, ap_entranti=ap_entranti,
        td_anno=td_anno, contratti_anno_map=contratti_anno_map,
        tipo_contratto_labels=TIPO_CONTRATTO_LABELS)


# ── CONFRONTO TI ↔ ORGANICO USR ──────────────────────────────────────
@impostazione_anno_bp.route('/impostazione-anno/confronto-organico')
def confronto_organico():
    """
    Mette a confronto i TI titolari della scuola collegati a ogni CC
    (da docente_classi_concorso, filtrando solo TI con status non ap_uscente)
    con il numero DOC dell'organico USR (cattedre_organico.n_docenti).

    Il DOC USR = TI titolari inclusi AP uscenti e aspettative.
    I TI presenti fisicamente = TI presenti + aspettativa (esclusi AP uscenti).

    La colonna "in app" conta i TI collegati alla CC, indipendentemente
    dal loro status di presenza — perché l'organico USR li conta tutti.
    """
    from models.classe_concorso import CattedraOrganico, DocenteClasseConcorso
    from config_anno import get_anno_corrente

    anno = request.args.get('anno', _anno_default_piano())
    anno_corrente = get_anno_corrente()

    # Tutte le CC con dati nel calcolo organico o nell'organico USR
    # (di fatto O di diritto — il filtro serve solo a includere la CC
    # nell'elenco, il tipo usato per il confronto vero e proprio è
    # deciso riga per riga più sotto, vedi _budget()). Niente join con
    # CattedraOrganico qui: potendoci essere sia la riga 'diritto' sia
    # la riga 'fatto' per la stessa CC, un join diretto duplicherebbe
    # la CC nell'elenco — si usano invece due sottoquery di id.
    ids_calcolo = {c.id_classe_concorso for c in
                   CalcoloOrganico.query.filter_by(anno_scol=anno)
                   .filter(CalcoloOrganico.ore_totali_calcolate > 0).all()}
    ids_cattedra = {c.id_classe_concorso for c in
                     CattedraOrganico.query.filter_by(anno_scol=anno)
                     .filter(CattedraOrganico.n_docenti > 0).all()}
    cc_list = (ClasseConcorso.query
               .filter(ClasseConcorso.id.in_(ids_calcolo | ids_cattedra))
               .order_by(ClasseConcorso.codice)
               .all())

    righe = []
    n_ok = n_warn = n_err = 0

    for cc in cc_list:
        # TI titolari della scuola collegati a questa CC
        # (tutti i TI, indipendentemente da status_presenza —
        #  perché l'USR li conta tutti nel DOC)
        from models.docente import tipo_contratto_per_anno
        docenti_cc_ti = (Docente.query
            .join(DocenteClasseConcorso, DocenteClasseConcorso.id_docente == Docente.id)
            .filter(DocenteClasseConcorso.id_classe_concorso == cc.id,
                    Docente.attivo == True).all())
        n_ti_app = sum(1 for d in docenti_cc_ti if tipo_contratto_per_anno(d, anno) == 'TI')

        # DOC dall'organico USR — di fatto se presente (è la
        # fotografia più aggiornata e reale della dotazione, calcolata
        # dopo le iscrizioni effettive), altrimenti di diritto come
        # ripiego (bollettino iniziale, spesso rivisto). Stessa
        # precedenza già usata altrove in app per lo stesso motivo
        # (vedi routes/assegnazioni.py::_budget()).
        cat = None
        for tipo_tentativo in ('fatto', 'diritto'):
            cat = CattedraOrganico.query.filter_by(
                anno_scol=anno, tipo=tipo_tentativo,
                id_classe_concorso=cc.id).first()
            if cat:
                break
        n_doc_usr = cat.n_docenti if cat and cat.n_docenti else 0
        tipo_usr = cat.tipo if cat else None

        # Calcolo organico richiesto
        calc = CalcoloOrganico.query.filter_by(
            anno_scol=anno, id_classe_concorso=cc.id).first()
        ore_richieste = calc.ore_totali_calcolate if calc else 0

        # Scarto e semaforo
        scarto = n_ti_app - n_doc_usr
        if n_doc_usr == 0 and n_ti_app == 0:
            semaforo = 'grigio'   # CC senza dati in nessuna delle due fonti
        elif scarto == 0:
            semaforo = 'verde'
            n_ok += 1
        elif abs(scarto) == 1:
            semaforo = 'giallo'   # scarto di 1 — probabile AP o aspettativa
            n_warn += 1
        else:
            semaforo = 'rosso'    # scarto > 1 — da verificare
            n_err += 1

        righe.append({
            'cc': cc,
            'ore_richieste': ore_richieste,
            'n_ti_app': n_ti_app,
            'n_doc_usr': n_doc_usr,
            'tipo_usr': tipo_usr,
            'scarto': scarto,
            'semaforo': semaforo,
            'tipo_organico': calc.tipo_calcolato if calc else '—',
        })

    # Filtra grigi (nessun dato utile)
    righe = [r for r in righe if r['semaforo'] != 'grigio']

    anni_disponibili = sorted(
        {p.anno_scol for p in PianoStudi.query.all()} |
        {c.anno_scol for c in CattedraOrganico.query.all()},
        reverse=True)
    if anno not in anni_disponibili:
        anni_disponibili.insert(0, anno)

    return render_template('impostazione_anno/confronto_organico.html',
        righe=righe, anno=anno, anni_disponibili=anni_disponibili,
        n_ok=n_ok, n_warn=n_warn, n_err=n_err,
        nessun_collegamento=(sum(r['n_ti_app'] for r in righe) == 0))
