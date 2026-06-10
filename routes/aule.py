from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db
from models.aula import Aula, SEDI, AULE_LIST
from models.aula_override import AulaOverride
from models.supplenza import Supplenza
from models.orario_docente import OrarioDocente

aule_bp = Blueprint('aule', __name__)


def _classi_da_orario():
    """Restituisce lista ordinata di classi presenti nell'orario."""
    classi_raw = db.session.query(OrarioDocente.classe).distinct().all()
    return sorted(set(
        c[0] for c in classi_raw
        if c[0] and c[0] not in ('---', '-x-', '')
        and c[0][0].isdigit()
    ))


@aule_bp.route('/aule')
def lista():
    # Rimozione rapida via query string
    rimuovi = request.args.get('rimuovi')
    if rimuovi:
        a = Aula.query.filter_by(classe=rimuovi.upper()).first()
        if a:
            db.session.delete(a)
            db.session.commit()
            flash(f'Aula rimossa per {rimuovi.upper()}.', 'warning')
        from flask import redirect
        return redirect(url_for('aule.lista'))
    aule = Aula.query.order_by(Aula.classe).all()
    classi_orario = _classi_da_orario()
    # Classi senza aula assegnata
    classi_assegnate = {a.classe for a in aule}
    classi_mancanti  = [c for c in classi_orario if c not in classi_assegnate]
    return render_template('aule/lista.html',
        aule=aule, classi_mancanti=classi_mancanti,
        sedi=SEDI, aule_list=AULE_LIST)


@aule_bp.route('/aule/salva', methods=['POST'])
def salva():
    """Salva o aggiorna l'aula per una classe."""
    classe = request.form.get('classe', '').strip().upper()
    aula   = request.form.get('aula', '').strip()
    sede   = request.form.get('sede', '').strip()
    if not classe or not aula or not sede:
        flash('Classe, aula e sede sono obbligatori.', 'error')
        return redirect(url_for('aule.lista'))

    a = Aula.query.filter_by(classe=classe).first()
    if a:
        a.aula = aula
        a.sede = sede
    else:
        db.session.add(Aula(classe=classe, aula=aula, sede=sede))
    db.session.commit()
    flash(f'Aula {aula} ({sede}) assegnata a {classe}.', 'success')
    return redirect(url_for('aule.lista'))


@aule_bp.route('/aule/<int:id>/elimina', methods=['POST'])
def elimina(id):
    a = Aula.query.get_or_404(id)
    classe = a.classe
    db.session.delete(a)
    db.session.commit()
    flash(f'Aula rimossa per {classe}.', 'warning')
    return redirect(url_for('aule.lista'))


@aule_bp.route('/aule/override/<int:id_supplenza>', methods=['GET', 'POST'])
def override(id_supplenza):
    """Override temporaneo aula per una supplenza specifica."""
    s = Supplenza.query.get_or_404(id_supplenza)
    # Aula standard della classe
    aula_std = Aula.query.filter_by(classe=s.classe).first()
    # Override esistente
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
                aula=aula_ov, sede=sede_ov, note=note_ov
            ))
        db.session.commit()
        flash(f'Aula temporanea impostata: Aula {aula_ov} — {sede_ov}', 'success')
        next_url = request.form.get('next') or url_for('dashboard.index')
        return redirect(next_url)

    return render_template('aule/override.html',
        supplenza=s, aula_std=aula_std, override=ov,
        sedi=SEDI, aule_list=AULE_LIST,
        next=request.args.get('next', ''))
