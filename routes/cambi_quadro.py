from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from models import db
from models.scambio_ore import ScambioOre
from models.supplenza import Supplenza
from models.docente import Docente
from models.orario_docente import classi_attive as _classi_attive
from datetime import date

cambi_bp = Blueprint('cambi', __name__)

TIPI_SCAMBIO = [
    ('scambio',               '↻︎ Scambio ore tra docenti'),
    ('ferie_concordate',      ' Ferie / permesso concordato'),
    ('ferie_concordate',      ' Ferie / permesso concordato'),
    ('sorveglianza',          '✎︎ Sorveglianza prove'),
    ('simulazione',           '▤︎ Simulazione esame'),
    ('attivita_alternativa',  '▨︎ Attività alternativa (INVALSI, commissioni)'),
    ('altro',                 '◆︎ Altro'),
]

@cambi_bp.route('/cambi-quadro')
def lista():
    """Storico scambi — mostra aperti in evidenza."""
    oggi = date.today()

    aperti = ScambioOre.query.filter_by(stato='aperto')\
        .order_by(ScambioOre.data_cessione.desc()).all()
    chiusi = ScambioOre.query.filter(ScambioOre.stato != 'aperto')\
        .order_by(ScambioOre.data_cessione.desc()).limit(30).all()

    return render_template('cambi_quadro.html',
        aperti=aperti, chiusi=chiusi, oggi=oggi,
        classi_attive=_classi_attive())

@cambi_bp.route('/cambi-quadro/nuovo', methods=['GET', 'POST'])
def nuovo():
    if request.method == 'POST':
        # Legge i campi come liste (form multi-riga)
        data_str      = request.form.get('data_comune', date.today().isoformat())
        tipo_comune   = request.form.get('tipo_comune', 'scambio')
        data_ins      = date.fromisoformat(data_str)

        ore_list_v      = request.form.getlist('ora[]')
        cede_list       = request.form.getlist('id_docente_cede[]')
        copre_list      = request.form.getlist('id_docente_copre[]')
        classi_list_v   = request.form.getlist('classe[]')
        rest_list       = request.form.getlist('data_restituzione[]')
        note_disp_list  = request.form.getlist('note_display[]')

        n_righe  = len(ore_list_v)
        registrati = 0

        for i in range(n_righe):
            ora      = int(ore_list_v[i]) if i < len(ore_list_v) and ore_list_v[i] else None
            id_cede  = int(cede_list[i])  if i < len(cede_list) and cede_list[i] else None
            id_copre = copre_list[i]       if i < len(copre_list) and copre_list[i] else None
            classe   = classi_list_v[i].strip().upper() if i < len(classi_list_v) else ''
            data_rest_str = rest_list[i].strip() if i < len(rest_list) else ''
            note_disp     = note_disp_list[i].strip() if i < len(note_disp_list) else ''

            if not ora or not id_cede:
                continue

            data_rest = date.fromisoformat(data_rest_str) if data_rest_str else None

            sc = ScambioOre(
                id_docente_cede            = id_cede,
                id_docente_copre           = int(id_copre) if id_copre else None,
                data_cessione              = data_ins,
                ora_cessione               = ora,
                classe                     = classe,
                tipo                       = tipo_comune,
                data_restituzione_prevista = data_rest,
                stato                      = 'aperto',
                note_display               = note_disp,
            )
            db.session.add(sc)
            db.session.flush()

            # Se ferie/permesso concordato →︎ docente indisponibile tutta la giornata
            if tipo_comune == 'ferie_concordate':
                from models.indisponibilita import Indisponibilita
                gia = Indisponibilita.query.filter_by(
                    id_docente=id_cede, data=data_ins, ora=None
                ).first()
                if not gia:
                    db.session.add(Indisponibilita(
                        id_docente = id_cede,
                        data       = data_ins,
                        ora        = None,
                        motivo     = 'ferie',
                        note       = f'Auto — ferie/permesso concordato',
                        creato_da  = g.utente.username if getattr(g, 'utente', None) else None,
                    ))

            # Genera supplenza se c'è coprente e classe
            if id_copre and classe:
                s = Supplenza(
                    data         = data_ins,
                    ora          = ora,
                    classe       = classe,
                    id_assente   = id_cede,
                    id_sostituto = int(id_copre),
                    tipo         = 'scambio',
                    stato        = 'assegnata',
                    origine      = 'manuale',
                    note_display = note_disp,
                    note         = f'Scambio ore — {tipo_comune}',
                    creato_da    = g.utente.username if getattr(g, 'utente', None) else None,
                )
                db.session.add(s)
                db.session.flush()
                sc.id_supplenza = s.id

            registrati += 1

        db.session.commit()

        if registrati == 1:
            flash(f'Scambio registrato il {data_ins.strftime("%d/%m/%Y")}.', 'success')
        else:
            flash(f'{registrati} scambi registrati il {data_ins.strftime("%d/%m/%Y")}.', 'success')
        return redirect(url_for('cambi.lista'))

    oggi     = date.today()
    data_str = request.args.get('data', oggi.isoformat())
    docenti  = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    ore_list = range(1, 10)

    from models.orario_docente import OrarioDocente
    from collections import defaultdict
    classi_raw = db.session.query(OrarioDocente.classe).distinct().all()
    classi_list = sorted(set(
        c[0] for c in classi_raw
        if c[0] and c[0] not in ('---', '-x-', '') and c[0][0].isdigit()
    ))
    # Aggiungi POTENZIAMENTO in cima
    classi_list = ['POTENZIAMENTO'] + classi_list

    return render_template('cambio_form.html',
        docenti=docenti, data_sel=data_str,
        ore_list=ore_list, tipi=TIPI_SCAMBIO,
        classi=classi_list)

@cambi_bp.route('/cambi-quadro/<int:id>/restituito', methods=['POST'])
def segna_restituito(id):
    sc = ScambioOre.query.get_or_404(id)

    data_str  = request.form.get('data_restituzione', date.today().isoformat())
    ora_rest  = request.form.get('ora_restituzione')
    classe_rest = request.form.get('classe_restituzione', '').strip().upper()

    sc.stato                      = 'restituito'
    sc.data_restituzione_effettiva= date.fromisoformat(data_str)
    sc.ora_restituzione           = int(ora_rest) if ora_rest else None
    sc.classe_restituzione        = classe_rest or None
    db.session.commit()

    flash('Scambio segnato come restituito.', 'success')
    return redirect(url_for('cambi.lista'))

@cambi_bp.route('/cambi-quadro/<int:id>/annulla', methods=['POST'])
def annulla(id):
    from models.indisponibilita import Indisponibilita
    sc = ScambioOre.query.get_or_404(id)
    # Rimuovi indisponibilità automatica se era ferie
    if sc.tipo == 'ferie_concordate':
        Indisponibilita.query.filter_by(
            id_docente = sc.id_docente_cede,
            data       = sc.data_cessione,
            ora        = None,
            motivo     = 'ferie',
        ).delete()
    sc.stato = 'annullato'
    db.session.commit()
    flash('Scambio annullato.', 'warning')
    return redirect(url_for('cambi.lista'))


@cambi_bp.route('/cambi-quadro/<int:id>/modifica', methods=['GET', 'POST'])
def modifica(id):
    scambio = ScambioOre.query.get_or_404(id)
    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()

    if request.method == 'POST':
        scambio.id_docente_cede  = int(request.form['id_docente_cede'])
        scambio.id_docente_copre = request.form.get('id_docente_copre') or None
        if scambio.id_docente_copre:
            scambio.id_docente_copre = int(scambio.id_docente_copre)
        scambio.data_cessione    = date.fromisoformat(request.form['data_cessione'])
        scambio.ora_cessione     = int(request.form['ora_cessione'])
        scambio.classe           = request.form.get('classe', '').strip().upper()
        scambio.tipo             = request.form.get('tipo', scambio.tipo)
        scambio.note_display     = request.form.get('note_display', '').strip()
        scambio.note_interne     = request.form.get('note_interne', '').strip()

        # Restituzione
        data_rest = request.form.get('data_restituzione_prevista') or None
        scambio.data_restituzione_prevista = date.fromisoformat(data_rest) if data_rest else None
        ora_rest = request.form.get('ora_restituzione') or None
        scambio.ora_restituzione = int(ora_rest) if ora_rest else None
        scambio.classe_restituzione = request.form.get('classe_restituzione', '').strip().upper() or None

        db.session.commit()
        flash('Cambio quadro aggiornato.', 'success')
        next_url = request.form.get('next') or url_for('cambi.lista')
        return redirect(next_url)

    from models.orario_docente import OrarioDocente
    classi_raw = db.session.query(OrarioDocente.classe).distinct().all()
    classi_list = sorted(set(
        c[0] for c in classi_raw
        if c[0] and c[0] not in ('---', '-x-', '') and c[0][0].isdigit()
    ))
    classi_list = ['POTENZIAMENTO'] + classi_list

    return render_template('cambio_modifica.html',
        scambio=scambio, docenti=docenti,
        ore_list=range(1, 10),
        classi=classi_list,
        next=request.args.get('next', ''))
