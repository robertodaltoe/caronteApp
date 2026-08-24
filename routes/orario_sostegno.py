"""
routes/orario_sostegno.py — sezione a parte per l'orario dei docenti di
sostegno. Inserimento manuale (niente file da importare, a differenza
dell'orario principale): un docente di sostegno + giorno + ora + classe
per volta.

Tenuto deliberatamente separato dall'orario principale (OrarioDocente):
vedi models/orario_sostegno.py per il motivo (l'import dell'orario
generale cancella e ricrea per intero OrarioDocente, quindi l'orario di
sostegno andrebbe perso se vivesse nella stessa tabella).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db
from models.docente import Docente
from models.orario_docente import classi_attive as _classi_attive
from models.orario_sostegno import OrarioSostegno, GIORNI

orario_sostegno_bp = Blueprint('orario_sostegno', __name__)

ORE = list(range(1, 10))


@orario_sostegno_bp.route('/orario-sostegno', methods=['GET', 'POST'])
def index():
    from modules.compresenze import invalida_cache
    from routes.auth import log as auth_log

    if request.method == 'POST':
        azione = request.form.get('azione')

        if azione == 'aggiungi':
            id_docente = request.form.get('id_docente', type=int)
            giorno     = request.form.get('giorno', type=int)
            ora        = request.form.get('ora', type=int)
            classe     = request.form.get('classe', '').strip().upper()
            note       = request.form.get('note', '').strip()

            if not (id_docente and giorno is not None and ora and classe):
                flash('Compila docente, giorno, ora e classe.', 'error')
            else:
                doc = Docente.query.get(id_docente)
                conflitto = OrarioSostegno.query.filter_by(
                    id_docente=id_docente, giorno=giorno, ora=ora).first()
                if conflitto:
                    flash(
                        f'{doc.cognome if doc else "Il docente"} ha già uno slot per '
                        f'{GIORNI[giorno]} {ora}ª ora (classe {conflitto.classe}). '
                        f'Modifica o elimina quello esistente prima di aggiungerne un altro.',
                        'error')
                else:
                    db.session.add(OrarioSostegno(
                        id_docente=id_docente, giorno=giorno, ora=ora,
                        classe=classe, note=note or None))
                    db.session.commit()
                    invalida_cache()
                    if doc:
                        auth_log('crea_orario_sostegno',
                            f'{doc.cognome} — {GIORNI[giorno]} {ora}ª ora, cl.{classe}')
                    flash('Slot aggiunto.', 'success')

        elif azione == 'modifica':
            sid = request.form.get('id', type=int)
            s = OrarioSostegno.query.get_or_404(sid)
            giorno = request.form.get('giorno', type=int)
            ora    = request.form.get('ora', type=int)
            classe = request.form.get('classe', '').strip().upper()
            note   = request.form.get('note', '').strip()
            if not (giorno is not None and ora and classe):
                flash('Compila giorno, ora e classe.', 'error')
            else:
                conflitto = OrarioSostegno.query.filter(
                    OrarioSostegno.id_docente == s.id_docente,
                    OrarioSostegno.giorno == giorno,
                    OrarioSostegno.ora == ora,
                    OrarioSostegno.id != s.id).first()
                if conflitto:
                    flash(f'Il docente ha già un altro slot per {GIORNI[giorno]} {ora}ª ora.', 'error')
                else:
                    s.giorno = giorno
                    s.ora = ora
                    s.classe = classe
                    s.note = note or None
                    db.session.commit()
                    invalida_cache()
                    auth_log('modifica_orario_sostegno',
                        f'{s.docente.cognome} — {GIORNI[giorno]} {ora}ª ora, cl.{classe}')
                    flash('Slot aggiornato.', 'success')

        elif azione == 'salva_griglia':
            # Inserimento massivo: una griglia giorno x ora per UN docente,
            # salvata in un solo submit invece di uno slot alla volta.
            # Ogni cella non vuota e' <input name="cella_{giorno}_{ora}">
            # col nome della classe; le celle vuote significano "nessuna
            # lezione quell'ora" (e cancellano lo slot se esisteva).
            id_docente = request.form.get('id_docente', type=int)
            doc = Docente.query.get(id_docente) if id_docente else None
            if not doc:
                flash('Docente non valido.', 'error')
                return redirect(url_for('orario_sostegno.index'))

            esistenti = {
                (s.giorno, s.ora): s
                for s in OrarioSostegno.query.filter_by(id_docente=id_docente).all()
            }

            n_agg = n_mod = n_eli = 0
            for giorno in range(len(GIORNI)):
                for ora in ORE:
                    classe = request.form.get(f'cella_{giorno}_{ora}', '').strip().upper()
                    slot = esistenti.get((giorno, ora))
                    # Il campo nota_* è opzionale e la griglia rapida non lo
                    # invia: se assente dal form si preserva la nota già
                    # presente sullo slot (se c'era), invece di azzerarla.
                    nota_raw = request.form.get(f'nota_{giorno}_{ora}')
                    nota_k = nota_raw.strip() if nota_raw is not None else (slot.note if slot else '') or ''
                    if classe:
                        if slot is None:
                            db.session.add(OrarioSostegno(
                                id_docente=id_docente, giorno=giorno, ora=ora,
                                classe=classe, note=nota_k or None))
                            n_agg += 1
                        elif slot.classe != classe or (slot.note or '') != nota_k:
                            slot.classe = classe
                            slot.note = nota_k or None
                            n_mod += 1
                    elif slot is not None:
                        db.session.delete(slot)
                        n_eli += 1

            if n_agg or n_mod or n_eli:
                db.session.commit()
                invalida_cache()
                auth_log('salva_griglia_orario_sostegno',
                    f'{doc.cognome} — {n_agg} aggiunti, {n_mod} modificati, {n_eli} eliminati')
                flash(f'Griglia salvata: {n_agg} aggiunti, {n_mod} modificati, {n_eli} eliminati.', 'success')
            else:
                flash('Nessuna modifica da salvare.', 'info')

            return redirect(url_for('orario_sostegno.index', id_docente=id_docente))

        elif azione == 'elimina':
            sid = request.form.get('id', type=int)
            s = OrarioSostegno.query.get_or_404(sid)
            desc = f'{s.docente.cognome} — {s.giorno_nome} {s.ora}ª ora, cl.{s.classe}'
            db.session.delete(s)
            db.session.commit()
            invalida_cache()
            auth_log('elimina_orario_sostegno', desc)
            flash('Slot eliminato.', 'warning')

        return redirect(url_for('orario_sostegno.index',
            id_docente=request.args.get('id_docente', '')))

    # Include anche chi ha un incarico di sostegno AGGIUNTIVO (ruolo
    # principale diverso, es. ITP) — segnalato da Roberto: un docente
    # così non compariva qui, quindi non era possibile assegnargli un
    # orario di sostegno nonostante lo svolgesse davvero (caso Luzzi).
    docenti_sostegno = Docente.query.filter(
        Docente.attivo == True,
        db.or_(Docente.ruolo == 'sostegno', Docente.sostegno_aggiuntivo == True)
    ).order_by(Docente.cognome).all()

    filtro_docente = request.args.get('id_docente', type=int)
    query = OrarioSostegno.query
    if filtro_docente:
        query = query.filter_by(id_docente=filtro_docente)
    slots = query.order_by(OrarioSostegno.giorno, OrarioSostegno.ora).all()

    per_docente = {}
    for s in slots:
        per_docente.setdefault(s.id_docente, []).append(s)

    # Griglia giorno_ora -> slot per il docente selezionato, per precompilare
    # la modalita' di inserimento rapido (vedi azione 'salva_griglia').
    griglia = {}
    if filtro_docente:
        for s in OrarioSostegno.query.filter_by(id_docente=filtro_docente).all():
            griglia[f'{s.giorno}_{s.ora}'] = s

    return render_template('orario_sostegno/index.html',
        docenti_sostegno=docenti_sostegno, slots=slots,
        per_docente=per_docente, giorni=list(enumerate(GIORNI)), ore=ORE,
        filtro_docente=filtro_docente, griglia=griglia,
        classi_attive=_classi_attive())
