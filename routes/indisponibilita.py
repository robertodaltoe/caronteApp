from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db
from models.indisponibilita import Indisponibilita
from models.indisponibilita_ricorrente import IndisponibilitaRicorrente
from models.docente import Docente
from datetime import date, timedelta

indisp_bp = Blueprint('indisponibilita', __name__)

GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato']

MOTIVI = [
    ('colloqui',   '👨‍👩‍👧 Colloqui con famiglie'),
    ('consiglio',  '🏫 Consiglio di classe'),
    ('uscita',     '🚌 Uscita didattica'),
    ('progetto',   '📐 Progetto / attività'),
    ('gara',       '🏆 Gara sportiva'),
    ('formazione', '🎓 Formazione'),
    ('riunione',   '🏫 Riunione / commissione'),
    ('altro',      '📌 Altro'),
]


def _date_da_modalita(tipo, form, idx):
    """Ritorna la lista di date per la riga i-esima."""
    if tipo == 'singola':
        d = form.get(f'data[{idx}]', '')
        return [date.fromisoformat(d)] if d else []
    elif tipo == 'intervallo':
        di = form.get(f'data_inizio[{idx}]', '')
        df = form.get(f'data_fine[{idx}]', '')
        if not di or not df:
            return []
        start = date.fromisoformat(di)
        end   = date.fromisoformat(df)
        result = []
        cur = start
        while cur <= end:
            if cur.weekday() < 6:
                result.append(cur)
            cur += timedelta(days=1)
        return result
    elif tipo == 'settimanale':
        # Supporta più giorni (checkbox multipli)
        giorni_sel = form.getlist(f'giorno_sett[{idx}][]')
        di = form.get(f'sett_inizio[{idx}]', '')
        df = form.get(f'sett_fine[{idx}]', '')
        if not giorni_sel or not di or not df:
            return []
        giorni_int = [int(g) for g in giorni_sel]
        start = date.fromisoformat(di)
        end   = date.fromisoformat(df)
        result = []
        cur = start
        while cur <= end:
            if cur.weekday() in giorni_int:
                result.append(cur)
            cur += timedelta(days=1)
        return result
    return []


@indisp_bp.route('/indisponibilita/nuova', methods=['GET', 'POST'])
def nuova():
    if request.method == 'POST':
        n_righe   = int(request.form.get('n_righe', 1))
        inseriti  = 0
        prima_data = None

        for idx in range(n_righe):
            id_doc_s = request.form.get(f'id_docente[{idx}]', '')
            if not id_doc_s:
                continue
            id_docente = int(id_doc_s)
            tipo       = request.form.get(f'tipo[{idx}]', 'singola')
            motivo     = request.form.get(f'motivo[{idx}]', 'altro')
            note       = request.form.get(f'note[{idx}]', '').strip()
            ore_sel    = request.form.getlist(f'ore[{idx}][]')
            # ore_sel è lista di stringhe es. ['1','3','5'] — None = tutta la giornata

            date_list = _date_da_modalita(tipo, request.form, idx)
            if not date_list:
                continue

            for data in date_list:
                if prima_data is None:
                    prima_data = data
                if ore_sel:
                    for o in ore_sel:
                        o_int = int(o) if o else None
                        # Evita duplicati
                        gia = Indisponibilita.query.filter_by(
                            id_docente=id_docente, data=data, ora=o_int
                        ).first()
                        if not gia:
                            db.session.add(Indisponibilita(
                                id_docente=id_docente, data=data,
                                ora=o_int, motivo=motivo, note=note
                            ))
                            inseriti += 1
                else:
                    # Tutta la giornata
                    gia = Indisponibilita.query.filter_by(
                        id_docente=id_docente, data=data, ora=None
                    ).first()
                    if not gia:
                        db.session.add(Indisponibilita(
                            id_docente=id_docente, data=data,
                            ora=None, motivo=motivo, note=note
                        ))
                        inseriti += 1

        db.session.commit()
        flash(f'Registrate {inseriti} indisponibilità.', 'success')
        return redirect(url_for('dashboard.index',
            data=(prima_data or date.today()).isoformat()))

    oggi     = date.today()
    data_str = request.args.get('data', oggi.isoformat())
    docenti  = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()

    import json
    docenti_json = json.dumps({
        d.id: d.cognome + (f' {d.nome[0]}.' if d.nome else '')
        for d in docenti
    })
    return render_template('indisponibilita_form.html',
        docenti=docenti, data_sel=data_str,
        docenti_json=docenti_json,
        ore_list=range(1, 10), motivi=MOTIVI,
        giorni=list(enumerate(GIORNI)))


@indisp_bp.route('/indisponibilita/ricorrenti')
def lista_ricorrenti():
    ricorrenti = (IndisponibilitaRicorrente.query
                  .filter_by(attiva=True)
                  .order_by(IndisponibilitaRicorrente.giorno,
                             IndisponibilitaRicorrente.ora)
                  .all())
    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    return render_template('indisponibilita_ricorrenti.html',
        ricorrenti=ricorrenti, docenti=docenti,
        motivi=MOTIVI, giorni=list(enumerate(GIORNI)),
        ore_list=range(1, 10))


@indisp_bp.route('/indisponibilita/ricorrente/<int:id>/disattiva', methods=['POST'])
def disattiva_ricorrente(id):
    ir = IndisponibilitaRicorrente.query.get_or_404(id)
    ir.attiva = False
    db.session.commit()
    flash(f'Disattivata: {ir.docente.cognome} — {ir.giorno_nome}.', 'warning')
    return redirect(url_for('indisponibilita.lista_ricorrenti'))


@indisp_bp.route('/indisponibilita/<int:id>/modifica', methods=['GET', 'POST'])
def modifica(id):
    i = Indisponibilita.query.get_or_404(id)
    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()

    if request.method == 'POST':
        i.id_docente = int(request.form['id_docente'])
        i.data       = date.fromisoformat(request.form['data'])
        ora_s        = request.form.get('ora') or None
        i.ora        = int(ora_s) if ora_s else None
        i.motivo     = request.form.get('motivo', i.motivo)
        i.note       = request.form.get('note', '').strip()
        db.session.commit()
        flash('Indisponibilità aggiornata.', 'success')
        next_url = request.form.get('next') or url_for('dashboard.index', data=i.data.isoformat())
        return redirect(next_url)

    return render_template('modifica_indisponibilita.html',
        indisp=i, docenti=docenti,
        ore_list=range(1, 10), motivi=MOTIVI,
        next=request.args.get('next', ''))
