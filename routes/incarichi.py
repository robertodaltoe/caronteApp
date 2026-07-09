from flask import (Blueprint, render_template, request,
                   redirect, url_for, flash, jsonify)
from models import db
from models.incarico import TipoIncarico, IncaricaDocente
from models.docente import Docente
from models.materia import Dipartimento
from models.piano_studi import ClasseSezione
from config_anno import get_anno_corrente

incarichi_bp = Blueprint('incarichi', __name__)

CAT_LABEL = {
    'strutturale':          'Incarichi strutturali',
    'funzione_strumentale': 'Funzioni strumentali',
    'fis':                  'FIS — Fondo istituto',
    'mof':                  'MOF',
}
CAT_COLOR = {
    'strutturale':          '#1e40af',
    'funzione_strumentale': '#0369a1',
    'fis':                  '#15803d',
    'mof':                  '#7c3aed',
}


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

    return render_template('incarichi/index.html',
        anno=anno, anni_disponibili=anni,
        per_cat=per_cat, tipi=tipi,
        docenti=docenti, classi=classi,
        dipartimenti=dipartimenti,
        cat_label=CAT_LABEL, cat_color=CAT_COLOR)


@incarichi_bp.route('/incarichi/salva', methods=['POST'])
def salva():
    anno     = request.form.get('anno_scol', get_anno_corrente())
    id_tipo  = request.form.get('id_tipo', type=int)
    id_doc   = request.form.get('id_docente', type=int)
    if not id_tipo or not id_doc:
        flash('Tipo incarico e docente sono obbligatori.', 'danger')
        return redirect(url_for('incarichi.index', anno=anno))

    tipo = db.session.get(TipoIncarico, id_tipo)

    # Contesto
    indirizzo   = request.form.get('indirizzo', '').strip() or None
    anno_corso  = request.form.get('anno_corso', type=int)
    sezione     = request.form.get('sezione', '').strip() or None
    id_dip      = request.form.get('id_dipartimento', type=int)

    # Compenso
    ore     = request.form.get('ore', type=float)
    importo = request.form.get('importo', type=float)
    note    = request.form.get('note', '').strip() or None

    # Evita duplicati
    esiste = IncaricaDocente.query.filter_by(
        anno_scol=anno, id_tipo_incarico=id_tipo,
        id_docente=id_doc,
        indirizzo=indirizzo, anno_corso=anno_corso,
        sezione=sezione, id_dipartimento=id_dip).first()
    if esiste:
        flash('Incarico già presente.', 'warning')
        return redirect(url_for('incarichi.index', anno=anno))

    db.session.add(IncaricaDocente(
        anno_scol=anno, id_tipo_incarico=id_tipo,
        id_docente=id_doc,
        indirizzo=indirizzo, anno_corso=anno_corso,
        sezione=sezione, id_dipartimento=id_dip,
        ore=ore, importo=importo, note=note))
    db.session.commit()

    doc = db.session.get(Docente, id_doc)
    flash(f'{tipo.nome} → {doc.cognome} {doc.nome} salvato.', 'success')
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
    return render_template('incarichi/tipi.html',
        tipi=tipi_list, cat_label=CAT_LABEL, cat_color=CAT_COLOR)


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
