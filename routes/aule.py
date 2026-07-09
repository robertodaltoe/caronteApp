from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db
from models.aula import Aula, SEDI, AULE_LIST
from models.aula_override import AulaOverride
from models.supplenza import Supplenza
from models.orario_docente import OrarioDocente
from models.piano_studi import ClasseSezione
from config_anno import get_anno_corrente

aule_bp = Blueprint('aule', __name__)


def _classi_per_anno(anno_scol):
    """
    Restituisce lista ordinata di etichette classe (es. "1A AFM")
    per l'anno scolastico dato, basandosi sulle ClasseSezione attive.
    Fallback sull'orario importato se non ci sono sezioni configurate.
    """
    sezioni = ClasseSezione.query.filter_by(
        anno_scol=anno_scol, attiva=True).order_by(
        ClasseSezione.indirizzo, ClasseSezione.anno_corso,
        ClasseSezione.sezione).all()
    if sezioni:
        return [f'{s.anno_corso}{s.sezione} {s.indirizzo}' for s in sezioni]
    # Fallback: orario importato (anno corrente)
    classi_raw = db.session.query(OrarioDocente.classe).distinct().all()
    return sorted(set(
        c[0] for c in classi_raw
        if c[0] and c[0] not in ('---', '-x-', '')
        and c[0][0].isdigit()
    ))


def _anni_disponibili():
    """Anni con sezioni configurate, anni con aule assegnate, + anno corrente."""
    anni = set()
    anni.update(cs.anno_scol for cs in ClasseSezione.query.all())
    anni.update(a.anno_scol for a in Aula.query.all())
    anni.add(get_anno_corrente())
    return sorted(anni, reverse=True)


@aule_bp.route('/aule')
def lista():
    anno = request.args.get('anno', get_anno_corrente())

    # Rimozione rapida
    rimuovi = request.args.get('rimuovi')
    if rimuovi:
        a = Aula.query.filter_by(anno_scol=anno,
                                  classe=rimuovi.upper()).first()
        if a:
            db.session.delete(a)
            db.session.commit()
            flash(f'Aula rimossa per {rimuovi.upper()} ({anno}).', 'warning')
        return redirect(url_for('aule.lista', anno=anno))

    aule = Aula.query.filter_by(anno_scol=anno).order_by(Aula.classe).all()
    classi_anno = _classi_per_anno(anno)
    classi_assegnate = {a.classe for a in aule}
    classi_mancanti = [c for c in classi_anno if c not in classi_assegnate]
    anni_disponibili = _anni_disponibili()

    return render_template('aule/lista.html',
        aule=aule, classi_mancanti=classi_mancanti,
        sedi=SEDI, aule_list=AULE_LIST,
        anno=anno, anni_disponibili=anni_disponibili)


@aule_bp.route('/aule/salva', methods=['POST'])
def salva():
    anno   = request.form.get('anno_scol', get_anno_corrente())
    classe = request.form.get('classe', '').strip().upper()
    aula   = request.form.get('aula', '').strip()
    sede   = request.form.get('sede', '').strip()
    if not classe or not aula or not sede:
        flash('Classe, aula e sede sono obbligatori.', 'error')
        return redirect(url_for('aule.lista', anno=anno))

    a = Aula.query.filter_by(anno_scol=anno, classe=classe).first()
    if a:
        a.aula = aula
        a.sede = sede
    else:
        db.session.add(Aula(anno_scol=anno, classe=classe,
                            aula=aula, sede=sede))
    db.session.commit()
    flash(f'Aula {aula} ({sede}) → {classe} per {anno}.', 'success')
    return redirect(url_for('aule.lista', anno=anno))


@aule_bp.route('/aule/copia', methods=['POST'])
def copia_anno():
    """Copia le assegnazioni aule da un anno all'altro."""
    anno_da  = request.form.get('anno_da', '').strip()
    anno_a   = request.form.get('anno_a', '').strip()
    if not anno_da or not anno_a or anno_da == anno_a:
        flash('Seleziona due anni diversi.', 'danger')
        return redirect(url_for('aule.lista', anno=anno_a or get_anno_corrente()))

    sorgenti = Aula.query.filter_by(anno_scol=anno_da).all()
    n_copiate = n_saltate = 0
    for s in sorgenti:
        esiste = Aula.query.filter_by(anno_scol=anno_a,
                                       classe=s.classe).first()
        if esiste:
            n_saltate += 1
        else:
            db.session.add(Aula(anno_scol=anno_a, classe=s.classe,
                                aula=s.aula, sede=s.sede))
            n_copiate += 1
    db.session.commit()
    msg = f'Copiate {n_copiate} aule da {anno_da} a {anno_a}'
    if n_saltate:
        msg += f' ({n_saltate} già presenti, saltate)'
    flash(msg, 'success')
    return redirect(url_for('aule.lista', anno=anno_a))


@aule_bp.route('/aule/override/<int:id_supplenza>', methods=['GET', 'POST'])
def override(id_supplenza):
    """Override temporaneo aula per una supplenza specifica."""
    s = Supplenza.query.get_or_404(id_supplenza)
    anno = get_anno_corrente()
    aula_std = Aula.query.filter_by(anno_scol=anno, classe=s.classe).first()
    ov = AulaOverride.query.filter_by(id_supplenza=id_supplenza).first()

    if request.method == 'POST':
        aula_ov = request.form.get('aula', '').strip()
        sede_ov = request.form.get('sede', '').strip()
        note_ov = request.form.get('note', '').strip()

        if request.form.get('rimuovi'):
            if ov:
                db.session.delete(ov)
                db.session.commit()
                flash('Override rimosso.', 'warning')
            return redirect(request.form.get('next') or url_for('dashboard.index'))

        if not aula_ov or not sede_ov:
            flash('Seleziona aula e sede.', 'error')
            return redirect(url_for('aule.override', id_supplenza=id_supplenza))

        if ov:
            ov.aula = aula_ov
            ov.sede = sede_ov
            ov.note = note_ov
        else:
            db.session.add(AulaOverride(
                id_supplenza=id_supplenza,
                aula=aula_ov, sede=sede_ov, note=note_ov))
        db.session.commit()
        flash(f'Aula temporanea: Aula {aula_ov} — {sede_ov}', 'success')
        return redirect(request.form.get('next') or url_for('dashboard.index'))

    return render_template('aule/override.html',
        supplenza=s, aula_std=aula_std, override=ov,
        sedi=SEDI, aule_list=AULE_LIST,
        next=request.args.get('next', ''))
