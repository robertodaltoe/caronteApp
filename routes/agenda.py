from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from models import db
from models.indisponibilita import Indisponibilita
from models.assenza import Assenza
from models.supplenza import Supplenza
from models.scambio_ore import ScambioOre
from models.docente import Docente
from datetime import date, timedelta
from collections import defaultdict
from modules.auto_sync import registra_eliminazione

agenda_bp = Blueprint('agenda', __name__)


def _accorpa_indisponibilita(indisp_list):
    """
    Raggruppa le indisponibilità per (docente, data, motivo) e
    produce una lista di ore compatta come "1ª, 3ª–5ª".
    """
    gruppi = defaultdict(list)
    for i in indisp_list:
        key = (i.id_docente, i.data, i.motivo)
        gruppi[key].append(i)

    risultati = []
    for (id_doc, data, motivo), items in sorted(
        gruppi.items(), key=lambda x: (x[0][1], x[0][0])
    ):
        ore = sorted(i.ora for i in items if i.ora is not None)
        tutta = any(i.ora is None for i in items)
        ids   = [i.id for i in items]

        if tutta:
            ore_label = 'Tutta la giornata'
        elif ore:
            ore_label = _ore_a_label(ore)
        else:
            ore_label = '—'

        doc = items[0].docente
        risultati.append({
            'id_docente': id_doc,
            'cognome':    doc.cognome if doc else '?',
            'data':       data,
            'motivo':     motivo,
            'ore_label':  ore_label,
            'note':       items[0].note,
            'ids':        ids,
            'prima_id':   ids[0],
            'auto':       (items[0].note or '').startswith('Auto'),
        })
    return risultati


def _ore_a_label(ore):
    """Converte lista di ore in label leggibile: [1,2,3,5] -> '1ª–3ª, 5ª'"""
    if not ore:
        return '—'
    gruppi = []
    start = ore[0]
    end   = ore[0]
    for o in ore[1:]:
        if o == end + 1:
            end = o
        else:
            gruppi.append((start, end))
            start = end = o
    gruppi.append((start, end))

    parti = []
    for s, e in gruppi:
        if s == e:
            parti.append(f'{s}ª')
        else:
            parti.append(f'{s}ª–{e}ª')
    return ', '.join(parti)


@agenda_bp.route('/agenda')
def index():
    oggi = date.today()
    # Mostra 30 giorni in avanti di default
    fino_a = oggi + timedelta(days=60)

    # Indisponibilità future
    indisp_future = (Indisponibilita.query
                     .filter(Indisponibilita.data >= oggi)
                     .order_by(Indisponibilita.data,
                                Indisponibilita.id_docente)
                     .all())
    indisp_accorpate = _accorpa_indisponibilita(indisp_future)

    # Assenze future (non auto)
    assenze_future = (Assenza.query
                      .filter(Assenza.data >= oggi)
                      .order_by(Assenza.data, Assenza.id_docente)
                      .all())

    # Supplenze future assegnate
    supplenze_future = (Supplenza.query
                        .filter(Supplenza.data >= oggi)
                        .filter(Supplenza.stato.in_(['assegnata','scoperta']))
                        .order_by(Supplenza.data, Supplenza.ora)
                        .all())

    # Cambi quadro futuri aperti
    cambi_futuri = (ScambioOre.query
                    .filter(ScambioOre.data_cessione >= oggi)
                    .filter(ScambioOre.stato == 'aperto')
                    .order_by(ScambioOre.data_cessione, ScambioOre.ora_cessione)
                    .all())

    return render_template('agenda.html',
        oggi=oggi,
        indisp_accorpate=indisp_accorpate,
        assenze_future=assenze_future,
        supplenze_future=supplenze_future,
        cambi_futuri=cambi_futuri,
        ore_a_label=_ore_a_label,
    )


@agenda_bp.route('/agenda/indisp/gruppo/elimina', methods=['POST'])
def elimina_gruppo_indisp():
    """Elimina un gruppo di indisponibilità e, se AUTO, anche assenze e supplenze collegate."""
    ids_str = request.form.get('ids', '')
    ids = [int(x) for x in ids_str.split(',') if x.strip()]

    utente_corrente = g.utente.username if getattr(g, 'utente', None) else None

    # Raccogli info prima di eliminare
    rimossi = []
    for id_ in ids:
        i = Indisponibilita.query.get(id_)
        if i:
            rimossi.append((i.id_docente, i.data, i.ora, i.note or ''))
            registra_eliminazione('indisponibilita', {
                'id_docente': i.id_docente, 'data': i.data.isoformat(), 'ora': i.ora,
            }, utente=utente_corrente)
            db.session.delete(i)

    # Se erano AUTO, rimuovi anche assenze e supplenze scoperte collegate
    for id_docente, data, ora, note in rimossi:
        if not note.startswith('Auto'):
            continue
        # Assenze AUTO dello stesso docente in quella data e ora
        assenze = Assenza.query.filter_by(
            id_docente=id_docente, data=data,
            ora_inizio=ora, ora_fine=ora
        ).filter(Assenza.note_interne.like('Auto%')).all()
        for a in assenze:
            registra_eliminazione('assenze', {
                'id_docente': a.id_docente, 'data': a.data.isoformat(),
                'ora_inizio': a.ora_inizio, 'ora_fine': a.ora_fine,
            }, utente=utente_corrente)
            db.session.delete(a)

        # Supplenze AUTO scoperte per il docente in quella data e ora
        sups = Supplenza.query.filter_by(
            data=data, id_assente=id_docente, ora=ora,
            origine='automatica'
        ).filter(Supplenza.stato.in_(['scoperta', 'non_assegnabile'])).all()
        for s in sups:
            registra_eliminazione('supplenze', {
                'data': s.data.isoformat(), 'ora': s.ora,
                'classe': s.classe, 'id_assente': s.id_assente,
            }, utente=utente_corrente)
            db.session.delete(s)

    db.session.commit()
    flash(f'{len(ids)} indisponibilità eliminate (con assenze e variazioni collegate).', 'warning')
    return redirect(url_for('agenda.index'))
