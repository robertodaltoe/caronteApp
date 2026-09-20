"""
routes/alternativa_irc.py — pianificazione dell'attività alternativa
all'IRC (nota MIM prot. 11814 del 06/05/2026, punto 3.7). Flusso:
1. adesioni (numero di studenti per classe), 2. disponibilità dei
docenti, 3. gruppi per slot, 4. assegnazione (docente fisso per tutto
l'anno), 5. griglia settimanale + export. La logica sta in
modules/alternativa_irc.py.
"""
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file

from models import db
from config_anno import get_anno_corrente
from models.alternativa_irc import (
    AlternativaIrcDisponibilita, AlternativaIrcGruppo, TIPI_DISPONIBILITA,
)
from modules import alternativa_irc as air

alternativa_irc_bp = Blueprint('alternativa_irc', __name__)


def _int(v, default=0):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


@alternativa_irc_bp.route('/alternativa-irc')
def index():
    anno = get_anno_corrente()
    return render_template('alternativa_irc/index.html', anno=anno,
                           riep=air.riepilogo(anno))


@alternativa_irc_bp.route('/alternativa-irc/adesioni', methods=['GET', 'POST'])
def adesioni():
    anno = get_anno_corrente()
    if request.method == 'POST':
        valori = {}
        for r in air.classi_con_adesione(anno):
            cl = r['classe']
            valori[cl] = (_int(request.form.get(f'con_{cl}')),
                          _int(request.form.get(f'altre_{cl}')),
                          request.form.get(f'note_{cl}', ''))
        air.salva_adesioni(anno, valori)
        flash('Adesioni salvate. Aggiorna i gruppi per ricalcolare le ore da coprire.', 'success')
        return redirect(url_for('alternativa_irc.adesioni'))
    righe = air.classi_con_adesione(anno)
    return render_template('alternativa_irc/adesioni.html', anno=anno, righe=righe,
                           giorni=air.GIORNI,
                           tot_con=sum(r['n_con_docente'] for r in righe),
                           tot_altre=sum(r['n_altre'] for r in righe))


@alternativa_irc_bp.route('/alternativa-irc/disponibilita', methods=['GET', 'POST'])
def disponibilita():
    anno = get_anno_corrente()
    ctx = air.Contesto(anno)
    if request.method == 'POST':
        scelti = set()
        for did in ctx.docenti:
            if request.form.get(f'disp_{did}'):
                scelti.add(did)
                riga = AlternativaIrcDisponibilita.query.filter_by(
                    anno_scol=anno, id_docente=did).first()
                if not riga:
                    riga = AlternativaIrcDisponibilita(anno_scol=anno, id_docente=did)
                    db.session.add(riga)
                tipo = request.form.get(f'tipo_{did}', 'ore_eccedenti')
                riga.tipo = tipo if tipo in dict(TIPI_DISPONIBILITA) else 'ore_eccedenti'
                mo = _int(request.form.get(f'max_{did}'), None)
                riga.max_ore = mo if mo and mo > 0 else None
                riga.note = request.form.get(f'note_{did}', '').strip() or None
        for riga in AlternativaIrcDisponibilita.query.filter_by(anno_scol=anno).all():
            if riga.id_docente not in scelti:
                db.session.delete(riga)
        db.session.commit()
        flash('Disponibilità salvate.', 'success')
        return redirect(url_for('alternativa_irc.disponibilita'))
    salvate = {d.id_docente: d for d in
               AlternativaIrcDisponibilita.query.filter_by(anno_scol=anno)}
    docenti = sorted(ctx.docenti.values(), key=lambda d: (d.cognome, d.nome or ''))
    return render_template('alternativa_irc/disponibilita.html', anno=anno,
                           docenti=docenti, salvate=salvate, tipi=TIPI_DISPONIBILITA)


@alternativa_irc_bp.route('/alternativa-irc/gruppi')
def gruppi():
    anno = get_anno_corrente()
    return render_template('alternativa_irc/gruppi.html', anno=anno,
                           righe=air.gruppi_dettaglio(anno), livelli=air.LIVELLI,
                           giorni=air.GIORNI, soglia=air.SOGLIA_GRUPPO)


@alternativa_irc_bp.route('/alternativa-irc/gruppi/genera', methods=['POST'])
def genera():
    esito = air.genera_gruppi(get_anno_corrente())
    flash(f'Gruppi aggiornati: {esito["creati"]} nuovi, {esito["aggiornati"]} confermati, '
          f'{esito["rimossi"]} rimossi.', 'success')
    if esito['senza_classi']:
        flash(f'{esito["senza_classi"]} gruppo/i con docente non hanno più classi in quello slot '
              f'(orario cambiato o adesioni azzerate): verifica e riassegna.', 'warning')
    if esito['classi_senza_slot']:
        flash('Classi con studenti ma senza ore di religione in orario: '
              + ', '.join(air.label_classe(c) for c in esito['classi_senza_slot']), 'warning')
    return redirect(url_for('alternativa_irc.gruppi'))


@alternativa_irc_bp.route('/alternativa-irc/gruppi/<int:id>/assegna', methods=['POST'])
def assegna(id):
    g = AlternativaIrcGruppo.query.get_or_404(id)
    scelta = request.form.get('scelta', 'nessuno')
    g.aula = request.form.get('aula', '').strip() or None
    g.note = request.form.get('note', '').strip() or None
    if scelta.startswith('docente:'):
        ok, msg = air.assegna(g, id_docente=_int(scelta.split(':', 1)[1]))
    elif scelta == 'da_nominare':
        ok, msg = air.assegna(g, da_nominare=True)
    else:
        ok, msg = air.assegna(g)
    flash(msg, 'success' if ok else 'error')
    return redirect(url_for('alternativa_irc.gruppi') + f'#g{g.id}')


@alternativa_irc_bp.route('/alternativa-irc/orario')
def orario():
    anno = get_anno_corrente()
    righe = air.gruppi_dettaglio(anno)
    griglia = {}
    for r in righe:
        griglia.setdefault(r['gruppo'].ora, {}).setdefault(r['gruppo'].giorno, []).append(r)
    return render_template('alternativa_irc/orario.html', anno=anno, griglia=griglia,
                           ore=sorted(griglia), giorni=air.GIORNI)


@alternativa_irc_bp.route('/alternativa-irc/xlsx')
def xlsx():
    anno = get_anno_corrente()
    buf = io.BytesIO()
    air.genera_xlsx(anno).save(buf)
    buf.seek(0)
    return send_file(
        buf, as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        download_name=f'alternativa_irc_{anno}.xlsx')
