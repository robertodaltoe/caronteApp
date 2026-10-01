"""
routes/contrattazione.py — Contrattazione integrativa d'istituto, area
per la segreteria/ufficio contabilità (vedi models/contrattazione.py
per il flusso completo: economie -> fondo -> quota DSGA -> capitoli ->
assegnazioni ai docenti -> eventuali spostamenti tra capitoli).

La generazione della lettera di incarico non è ancora in questo modulo:
Roberto fornirà il modello usato dal Dirigente, con riferimenti diversi
da quelli dei Progetti FSE/FESR — da aggiungere in un passo successivo.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db
from models.contrattazione import (
    FondoContrattazione, CapitoloContrattazione, AssegnazioneContrattazione,
    StoricoSpostamentoCapitolo, STATI_ASSEGNAZIONE, STATI_ASSEGNAZIONE_LABEL,
)
from models.docente import Docente
from config_anno import get_anno_corrente

contrattazione_bp = Blueprint('contrattazione', __name__)


def _float(v, default=0.0):
    try:
        return float(str(v).replace(',', '.').strip())
    except (TypeError, ValueError):
        return default


def _utente_corrente():
    from flask import g
    return g.utente.username if getattr(g, 'utente', None) else None


@contrattazione_bp.route('/contrattazione')
def index():
    anno = request.args.get('anno') or get_anno_corrente()
    anni = [r[0] for r in db.session.query(FondoContrattazione.anno_scol).distinct()
            .order_by(FondoContrattazione.anno_scol.desc()).all()]
    if anno not in anni:
        anni = [anno] + anni
    fondi = (FondoContrattazione.query.filter_by(anno_scol=anno)
             .order_by(FondoContrattazione.nome).all())
    return render_template('contrattazione/index.html', fondi=fondi, anno=anno, anni=anni,
                           stati_label=STATI_ASSEGNAZIONE_LABEL)


@contrattazione_bp.route('/contrattazione/fondo/nuovo', methods=['GET', 'POST'])
@contrattazione_bp.route('/contrattazione/fondo/<int:id>/modifica', methods=['GET', 'POST'])
def fondo_form(id=None):
    fondo = FondoContrattazione.query.get_or_404(id) if id else None
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        anno = request.form.get('anno_scol', '').strip() or get_anno_corrente()
        if not nome:
            flash('Il nome del fondo è obbligatorio.', 'error')
            return redirect(request.url)
        if fondo is None:
            fondo = FondoContrattazione(anno_scol=anno, creato_da=_utente_corrente())
            db.session.add(fondo)
        fondo.nome               = nome
        fondo.anno_scol          = anno
        fondo.economie_pregresse = _float(request.form.get('economie_pregresse'))
        fondo.importo_assegnato  = _float(request.form.get('importo_assegnato'))
        fondo.quota_dsga         = _float(request.form.get('quota_dsga'))
        fondo.note               = request.form.get('note', '').strip() or None
        db.session.commit()
        flash(f'Fondo "{fondo.nome}" salvato.', 'success')
        return redirect(url_for('contrattazione.index', anno=fondo.anno_scol))
    return render_template('contrattazione/fondo_form.html', fondo=fondo,
                           anno=get_anno_corrente() if fondo is None else fondo.anno_scol)


@contrattazione_bp.route('/contrattazione/fondo/<int:id>/elimina', methods=['POST'])
def fondo_elimina(id):
    fondo = FondoContrattazione.query.get_or_404(id)
    anno = fondo.anno_scol
    nome = fondo.nome
    db.session.delete(fondo)
    db.session.commit()
    flash(f'Fondo "{nome}" eliminato (con tutti i suoi capitoli e assegnazioni).', 'warning')
    return redirect(url_for('contrattazione.index', anno=anno))


@contrattazione_bp.route('/contrattazione/fondo/<int:id_fondo>/capitolo/nuovo', methods=['GET', 'POST'])
@contrattazione_bp.route('/contrattazione/capitolo/<int:id>/modifica', methods=['GET', 'POST'])
def capitolo_form(id_fondo=None, id=None):
    capitolo = CapitoloContrattazione.query.get_or_404(id) if id else None
    fondo = capitolo.fondo if capitolo else FondoContrattazione.query.get_or_404(id_fondo)
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        if not nome:
            flash('Il nome del capitolo è obbligatorio.', 'error')
            return redirect(request.url)
        if capitolo is None:
            capitolo = CapitoloContrattazione(id_fondo=fondo.id)
            db.session.add(capitolo)
        capitolo.nome              = nome
        capitolo.importo_assegnato = _float(request.form.get('importo_assegnato'))
        capitolo.note              = request.form.get('note', '').strip() or None
        db.session.commit()
        flash(f'Capitolo "{capitolo.nome}" salvato.', 'success')
        return redirect(url_for('contrattazione.index', anno=fondo.anno_scol))
    return render_template('contrattazione/capitolo_form.html', capitolo=capitolo, fondo=fondo)


@contrattazione_bp.route('/contrattazione/capitolo/<int:id>/elimina', methods=['POST'])
def capitolo_elimina(id):
    capitolo = CapitoloContrattazione.query.get_or_404(id)
    anno = capitolo.fondo.anno_scol
    nome = capitolo.nome
    if capitolo.assegnazioni:
        flash(f'Impossibile eliminare "{nome}": ha {len(capitolo.assegnazioni)} assegnazione/i. '
              'Spostale o eliminale prima.', 'error')
        return redirect(url_for('contrattazione.index', anno=anno))
    db.session.delete(capitolo)
    db.session.commit()
    flash(f'Capitolo "{nome}" eliminato.', 'warning')
    return redirect(url_for('contrattazione.index', anno=anno))


@contrattazione_bp.route('/contrattazione/capitolo/<int:id_capitolo>/assegnazione/nuova', methods=['GET', 'POST'])
@contrattazione_bp.route('/contrattazione/assegnazione/<int:id>/modifica', methods=['GET', 'POST'])
def assegnazione_form(id_capitolo=None, id=None):
    asg = AssegnazioneContrattazione.query.get_or_404(id) if id else None
    capitolo = asg.capitolo if asg else CapitoloContrattazione.query.get_or_404(id_capitolo)
    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    if request.method == 'POST':
        id_doc = request.form.get('id_docente', type=int)
        descrizione = request.form.get('descrizione', '').strip()
        if not id_doc or not descrizione:
            flash('Docente e descrizione dell\'incarico sono obbligatori.', 'error')
            return redirect(request.url)
        if asg is None:
            asg = AssegnazioneContrattazione(id_capitolo=capitolo.id, creato_da=_utente_corrente())
            db.session.add(asg)
        asg.id_docente  = id_doc
        asg.descrizione = descrizione
        asg.unita       = _float(request.form.get('unita'), None) if request.form.get('unita') else None
        asg.importo     = _float(request.form.get('importo'))
        asg.stato       = request.form.get('stato') if request.form.get('stato') in dict(STATI_ASSEGNAZIONE) else 'previsto'
        asg.note        = request.form.get('note', '').strip() or None
        db.session.commit()
        if capitolo.sforato:
            flash(f'Attenzione: il capitolo "{capitolo.nome}" ha superato l\'importo assegnato di '
                  f'{abs(capitolo.saldo_residuo):.2f}€.', 'warning')
        flash('Assegnazione salvata.', 'success')
        return redirect(url_for('contrattazione.index', anno=capitolo.fondo.anno_scol))
    return render_template('contrattazione/assegnazione_form.html', asg=asg, capitolo=capitolo,
                           docenti=docenti, stati=STATI_ASSEGNAZIONE)


@contrattazione_bp.route('/contrattazione/assegnazione/<int:id>/elimina', methods=['POST'])
def assegnazione_elimina(id):
    asg = AssegnazioneContrattazione.query.get_or_404(id)
    anno = asg.capitolo.fondo.anno_scol
    db.session.delete(asg)
    db.session.commit()
    flash('Assegnazione eliminata.', 'warning')
    return redirect(url_for('contrattazione.index', anno=anno))


@contrattazione_bp.route('/contrattazione/assegnazione/<int:id>/sposta', methods=['POST'])
def assegnazione_sposta(id):
    """Sposta un'assegnazione in un altro capitolo (stesso fondo o un
    fondo diverso) registrando lo storico — niente lettera di
    rettifica, ma la segreteria deve sempre poter vedere da dove
    arriva un'assegnazione (Roberto, vedi models/contrattazione.py)."""
    asg = AssegnazioneContrattazione.query.get_or_404(id)
    id_nuovo = request.form.get('id_capitolo_nuovo', type=int)
    motivo = request.form.get('motivo', '').strip() or None
    nuovo_capitolo = CapitoloContrattazione.query.get_or_404(id_nuovo)
    vecchio_capitolo = asg.capitolo
    anno = vecchio_capitolo.fondo.anno_scol

    if nuovo_capitolo.id == vecchio_capitolo.id:
        flash('L\'assegnazione è già in questo capitolo.', 'error')
        return redirect(url_for('contrattazione.index', anno=anno))

    db.session.add(StoricoSpostamentoCapitolo(
        id_assegnazione=asg.id,
        id_capitolo_precedente=vecchio_capitolo.id,
        id_capitolo_nuovo=nuovo_capitolo.id,
        importo_al_momento=asg.importo,
        motivo=motivo,
        utente=_utente_corrente(),
    ))
    asg.id_capitolo = nuovo_capitolo.id
    db.session.commit()
    if nuovo_capitolo.sforato:
        flash(f'Spostato in "{nuovo_capitolo.nome}" — attenzione: questo capitolo ora supera '
              f'l\'importo assegnato di {abs(nuovo_capitolo.saldo_residuo):.2f}€.', 'warning')
    else:
        flash(f'Assegnazione spostata da "{vecchio_capitolo.nome}" a "{nuovo_capitolo.nome}".', 'success')
    return redirect(url_for('contrattazione.index', anno=nuovo_capitolo.fondo.anno_scol))
