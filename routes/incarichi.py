from flask import (Blueprint, render_template, request,
                   redirect, url_for, flash, jsonify)
from models import db
from models.incarico import TipoIncarico, IncaricaDocente, CategoriaIncarico
from models.docente import Docente
from models.materia import Dipartimento
from models.piano_studi import ClasseSezione
from config_anno import get_anno_corrente

incarichi_bp = Blueprint('incarichi', __name__)

def _cat_map():
    """Restituisce (cat_label, cat_color) da DB + codice stringa come fallback."""
    cats = CategoriaIncarico.query.order_by(CategoriaIncarico.ordine).all()
    labels = {c.codice: c.nome   for c in cats}
    colors = {c.codice: c.colore for c in cats}
    return labels, colors, cats


def _anni():
    from models.piano_studi import PianoStudi
    anni = sorted({r.anno_scol for r in PianoStudi.query.all()}, reverse=True)
    return anni or [get_anno_corrente()]


@incarichi_bp.route('/incarichi')
def index():
    anno = request.args.get('anno', get_anno_corrente())
    anni = _anni()
    if anno not in anni:
        anni.insert(0, anno)

    # Incarichi per anno raggruppati per categoria e tipo
    nomine = (IncaricaDocente.query
              .filter_by(anno_scol=anno)
              .join(TipoIncarico)
              .join(Docente, IncaricaDocente.id_docente == Docente.id)
              .order_by(TipoIncarico.ordine,
                        TipoIncarico.nome,
                        Docente.cognome)
              .all())

    # Raggruppa per categoria → tipo
    from collections import defaultdict
    per_cat = defaultdict(lambda: defaultdict(list))
    for n in nomine:
        per_cat[n.tipo.categoria][n.tipo].append(n)

    # Tipi incarico disponibili per il form
    tipi = TipoIncarico.query.filter_by(attivo=True).order_by(
        TipoIncarico.ordine).all()
    docenti = Docente.query.filter_by(attivo=True).order_by(
        Docente.cognome).all()
    classi = ClasseSezione.query.filter_by(
        anno_scol=anno, attiva=True).order_by(
        ClasseSezione.indirizzo,
        ClasseSezione.anno_corso,
        ClasseSezione.sezione).all()
    dipartimenti = Dipartimento.query.filter(
        Dipartimento.sigla != '—').order_by(Dipartimento.ordine).all()

    # Classi raggruppate per indirizzo (senza ripetizioni), per le checkbox
    # multi-classe del form — un indirizzo compare una volta sola come
    # intestazione di gruppo, non una volta per ogni sezione attiva.
    from collections import OrderedDict
    classi_per_indirizzo = OrderedDict()
    for cs in classi:
        classi_per_indirizzo.setdefault(cs.indirizzo, []).append(cs)

    cat_label, cat_color, categorie = _cat_map()
    return render_template('incarichi/index.html',
        anno=anno, anni_disponibili=anni,
        per_cat=per_cat, tipi=tipi,
        docenti=docenti, classi=classi,
        classi_per_indirizzo=classi_per_indirizzo,
        dipartimenti=dipartimenti,
        cat_label=cat_label, cat_color=cat_color,
        categorie=categorie)


@incarichi_bp.route('/incarichi/salva', methods=['POST'])
def salva():
    """
    Salva più incarichi in un colpo solo per UN docente: ogni riga del
    form (tipo incarico + eventuale contesto) può generare più di una
    nomina se sono state selezionate più classi per quella riga.
    """
    anno   = request.form.get('anno_scol', get_anno_corrente())
    id_doc = request.form.get('id_docente', type=int)
    if not id_doc:
        flash('Seleziona un docente.', 'danger')
        return redirect(url_for('incarichi.index', anno=anno))
    doc = db.session.get(Docente, id_doc)

    n_righe = request.form.get('n_righe', type=int) or 0

    salvati = 0
    duplicati = 0
    nomi_tipo = []

    for idx in range(n_righe):
        id_tipo = request.form.get(f'id_tipo[{idx}]', type=int)
        if not id_tipo:
            continue
        tipo = db.session.get(TipoIncarico, id_tipo)

        id_dip  = request.form.get(f'id_dipartimento[{idx}]', type=int)
        ore     = request.form.get(f'ore[{idx}]', type=float)
        importo = request.form.get(f'importo[{idx}]', type=float)
        note    = request.form.get(f'note[{idx}]', '').strip() or None

        # Classi selezionate per questa riga: valori "INDIRIZZO|ANNO|SEZIONE"
        classi_sel = request.form.getlist(f'classi[{idx}][]')

        # Costruisce l'elenco dei contesti da salvare: una nomina per
        # ogni classe selezionata, oppure una sola nomina (senza classe)
        # se l'incarico non è legato a una classe.
        contesti = []
        if classi_sel:
            for val in classi_sel:
                indirizzo, anno_corso_s, sezione = val.split('|')
                contesti.append((indirizzo, int(anno_corso_s), sezione))
        else:
            contesti.append((None, None, None))

        for indirizzo, anno_corso, sezione in contesti:
            esiste = IncaricaDocente.query.filter_by(
                anno_scol=anno, id_tipo_incarico=id_tipo,
                id_docente=id_doc,
                indirizzo=indirizzo, anno_corso=anno_corso,
                sezione=sezione, id_dipartimento=id_dip).first()
            if esiste:
                duplicati += 1
                continue
            db.session.add(IncaricaDocente(
                anno_scol=anno, id_tipo_incarico=id_tipo,
                id_docente=id_doc,
                indirizzo=indirizzo, anno_corso=anno_corso,
                sezione=sezione, id_dipartimento=id_dip,
                ore=ore, importo=importo, note=note))
            salvati += 1
        nomi_tipo.append(tipo.nome)

    db.session.commit()

    if salvati:
        flash(f'{salvati} incarico/hi salvato/i per {doc.cognome} {doc.nome}'
              + (f' ({", ".join(nomi_tipo)})' if nomi_tipo else '') + '.', 'success')
    if duplicati:
        flash(f'{duplicati} incarico/hi già presente/i, saltato/i.', 'warning')
    if not salvati and not duplicati:
        flash('Nessun incarico da salvare: seleziona almeno un tipo incarico.', 'danger')
    return redirect(url_for('incarichi.index', anno=anno))


@incarichi_bp.route('/incarichi/<int:id>/elimina', methods=['POST'])
def elimina(id):
    inc = db.session.get(IncaricaDocente, id)
    if not inc:
        flash('Incarico non trovato.', 'danger')
        return redirect(url_for('incarichi.index'))
    anno = inc.anno_scol
    nome = f'{inc.tipo.nome} → {inc.docente.cognome}'
    db.session.delete(inc)
    db.session.commit()
    flash(f'Incarico "{nome}" eliminato.', 'warning')
    return redirect(url_for('incarichi.index', anno=anno))


@incarichi_bp.route('/incarichi/tipi')
def tipi():
    """Gestione tipi incarico (CRUD)."""
    tipi_list = TipoIncarico.query.order_by(
        TipoIncarico.ordine, TipoIncarico.nome).all()
    cat_label, cat_color, categorie = _cat_map()
    return render_template('incarichi/tipi.html',
        tipi=tipi_list, cat_label=cat_label, cat_color=cat_color,
        categorie=categorie)


@incarichi_bp.route('/incarichi/tipi/salva', methods=['POST'])
def salva_tipo():
    id_t    = request.form.get('id', type=int)
    nome    = request.form.get('nome', '').strip()
    cat     = request.form.get('categoria', 'strutturale')
    coll    = request.form.get('collegato_a', '').strip() or None
    comp    = request.form.get('compenso_tipo', '').strip() or None
    imp     = request.form.get('importo_default', type=float)
    ordine  = request.form.get('ordine', type=int) or 0

    if not nome:
        flash('Il nome è obbligatorio.', 'danger')
        return redirect(url_for('incarichi.tipi'))

    if id_t:
        t = db.session.get(TipoIncarico, id_t)
        t.nome=nome; t.categoria=cat; t.collegato_a=coll
        t.compenso_tipo=comp; t.importo_default=imp; t.ordine=ordine
    else:
        db.session.add(TipoIncarico(
            nome=nome, categoria=cat, collegato_a=coll,
            compenso_tipo=comp, importo_default=imp,
            attivo=True, ordine=ordine))
    db.session.commit()
    flash('Tipo incarico salvato.', 'success')
    return redirect(url_for('incarichi.tipi'))


@incarichi_bp.route('/incarichi/categorie/salva', methods=['POST'])
def salva_categoria():
    id_c   = request.form.get('id', type=int)
    codice = request.form.get('codice', '').strip().lower().replace(' ', '_')
    nome   = request.form.get('nome', '').strip()
    colore = request.form.get('colore', '#1e40af').strip()
    ordine = request.form.get('ordine', type=int) or 0

    if not codice or not nome:
        flash('Codice e nome sono obbligatori.', 'danger')
        return redirect(url_for('incarichi.tipi'))

    if id_c:
        c = db.session.get(CategoriaIncarico, id_c)
        c.nome=nome; c.colore=colore; c.ordine=ordine
    else:
        if CategoriaIncarico.query.filter_by(codice=codice).first():
            flash(f'Categoria "{codice}" già esistente.', 'warning')
            return redirect(url_for('incarichi.tipi'))
        c = CategoriaIncarico(codice=codice, nome=nome, colore=colore, ordine=ordine)
        db.session.add(c)
    db.session.commit()
    flash(f'Categoria "{nome}" salvata.', 'success')
    return redirect(url_for('incarichi.tipi'))
