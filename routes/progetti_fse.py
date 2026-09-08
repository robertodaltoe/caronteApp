"""
routes/progetti_fse.py — Area amministrativa isolata per i progetti
finanziati da fondi strutturali europei (FSE+/FESR — PN "Scuola e
competenze" 2021-2027, es. Piano Estate, e progetti futuri con lo
stesso iter). Volutamente separata dal Piano delle Attività didattico
(vedi models/progetto_fse.py): qui vive la parte amministrativa
(moduli, incarichi, documenti, stima costi); le sole date dei moduli
confluiscono in sola lettura nell'Agenda per il controllo incrociato
con gli impegni didattici dei docenti incaricati.
"""
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from models import db
from models.progetto_fse import (
    ProgettoFSE, ModuloFSE, IncaricoFSE, SessioneFSE, PresenzaFSE, DocumentoFSE,
    STATI_PROGETTO, STATI_MODULO, RUOLI_INCARICO, TIPI_RAPPORTO, TIPI_COSTO,
)
from models.docente import Docente

progetti_fse_bp = Blueprint('progetti_fse', __name__)


def _utente():
    return g.utente.username if getattr(g, 'utente', None) else None


def _decimal(form, campo):
    v = (form.get(campo) or '').strip().replace(',', '.')
    return float(v) if v else None


def _data(form, campo):
    v = (form.get(campo) or '').strip()
    return date.fromisoformat(v) if v else None


# ── ELENCO PROGETTI ──────────────────────────────────────────────────
@progetti_fse_bp.route('/progetti-fse')
def index():
    progetti = ProgettoFSE.query.order_by(ProgettoFSE.creato_il.desc()).all()
    return render_template('progetti_fse/index.html', progetti=progetti,
        stati_label=dict(STATI_PROGETTO))


@progetti_fse_bp.route('/progetti-fse/nuovo', methods=['GET', 'POST'])
def nuovo():
    if request.method == 'POST':
        p = ProgettoFSE(
            titolo=request.form['titolo'].strip(),
            codice_progetto=request.form.get('codice_progetto', '').strip() or None,
            cup=request.form.get('cup', '').strip() or None,
            programma=request.form.get('programma', '').strip() or None,
            fondo=request.form.get('fondo', '').strip() or None,
            obiettivo_specifico=request.form.get('obiettivo_specifico', '').strip() or None,
            azione=request.form.get('azione', '').strip() or None,
            anno_scol=request.form.get('anno_scol', '').strip() or None,
            importo_autorizzato=_decimal(request.form, 'importo_autorizzato'),
            stato=request.form.get('stato', 'bozza'),
            tipo_costo=request.form.get('tipo_costo', 'ucs'),
            tariffa_esperto=_decimal(request.form, 'tariffa_esperto'),
            tariffa_tutor=_decimal(request.form, 'tariffa_tutor'),
            costo_gestione_ora_partecipante=_decimal(request.form, 'costo_gestione_ora_partecipante'),
            percentuale_costi_indiretti=_decimal(request.form, 'percentuale_costi_indiretti'),
            importo_costi_indiretti_fisso=_decimal(request.form, 'importo_costi_indiretti_fisso'),
            riferimento_avviso=request.form.get('riferimento_avviso', '').strip() or None,
            riferimento_bando_interno=request.form.get('riferimento_bando_interno', '').strip() or None,
            note_ammissibilita=request.form.get('note_ammissibilita', '').strip() or None,
            creato_da=_utente(),
        )
        db.session.add(p)
        db.session.commit()
        flash(f'Progetto "{p.titolo}" creato.', 'success')
        return redirect(url_for('progetti_fse.dettaglio', id=p.id))

    return render_template('progetti_fse/form.html', progetto=None,
        stati=STATI_PROGETTO, tipi_costo=TIPI_COSTO)


@progetti_fse_bp.route('/progetti-fse/<int:id>/modifica', methods=['GET', 'POST'])
def modifica(id):
    p = ProgettoFSE.query.get_or_404(id)
    if request.method == 'POST':
        p.titolo = request.form['titolo'].strip()
        p.codice_progetto = request.form.get('codice_progetto', '').strip() or None
        p.cup = request.form.get('cup', '').strip() or None
        p.programma = request.form.get('programma', '').strip() or None
        p.fondo = request.form.get('fondo', '').strip() or None
        p.obiettivo_specifico = request.form.get('obiettivo_specifico', '').strip() or None
        p.azione = request.form.get('azione', '').strip() or None
        p.anno_scol = request.form.get('anno_scol', '').strip() or None
        p.importo_autorizzato = _decimal(request.form, 'importo_autorizzato')
        p.stato = request.form.get('stato', p.stato)
        p.tipo_costo = request.form.get('tipo_costo', p.tipo_costo)
        p.tariffa_esperto = _decimal(request.form, 'tariffa_esperto')
        p.tariffa_tutor = _decimal(request.form, 'tariffa_tutor')
        p.costo_gestione_ora_partecipante = _decimal(request.form, 'costo_gestione_ora_partecipante')
        p.percentuale_costi_indiretti = _decimal(request.form, 'percentuale_costi_indiretti')
        p.importo_costi_indiretti_fisso = _decimal(request.form, 'importo_costi_indiretti_fisso')
        p.riferimento_avviso = request.form.get('riferimento_avviso', '').strip() or None
        p.riferimento_bando_interno = request.form.get('riferimento_bando_interno', '').strip() or None
        p.note_ammissibilita = request.form.get('note_ammissibilita', '').strip() or None
        db.session.commit()
        flash('Progetto aggiornato.', 'success')
        return redirect(url_for('progetti_fse.dettaglio', id=p.id))

    return render_template('progetti_fse/form.html', progetto=p,
        stati=STATI_PROGETTO, tipi_costo=TIPI_COSTO)


@progetti_fse_bp.route('/progetti-fse/<int:id>')
def dettaglio(id):
    p = ProgettoFSE.query.get_or_404(id)
    riepilogo_moduli = []
    totale_previsto = 0.0
    for m in p.moduli:
        costo_formazione = m.costo_formazione_previsto()
        costo_gestione = m.costo_gestione_stimato()
        costo_stimato = (costo_formazione or 0) + (costo_gestione or 0)
        if costo_formazione is not None or costo_gestione is not None:
            totale_previsto += costo_stimato
        riepilogo_moduli.append({
            'modulo': m,
            'costo_formazione': costo_formazione,
            'costo_gestione': costo_gestione,
            'costo_stimato': costo_stimato,
        })
    # float esplicito: importo_autorizzato è un Numeric (Decimal) e non si
    # può sottrarre direttamente da un float senza un TypeError.
    scostamento = totale_previsto - float(p.importo_autorizzato or 0)

    return render_template('progetti_fse/dettaglio.html', progetto=p,
        riepilogo_moduli=riepilogo_moduli, totale_previsto=totale_previsto,
        scostamento=scostamento)


@progetti_fse_bp.route('/progetti-fse/<int:id>/elimina', methods=['POST'])
def elimina(id):
    p = ProgettoFSE.query.get_or_404(id)
    titolo = p.titolo
    db.session.delete(p)
    db.session.commit()
    flash(f'Progetto "{titolo}" eliminato.', 'warning')
    return redirect(url_for('progetti_fse.index'))


# ── MODULI ────────────────────────────────────────────────────────────
@progetti_fse_bp.route('/progetti-fse/<int:id_progetto>/moduli/nuovo', methods=['GET', 'POST'])
def nuovo_modulo(id_progetto):
    p = ProgettoFSE.query.get_or_404(id_progetto)
    if request.method == 'POST':
        m = ModuloFSE(
            id_progetto=p.id,
            codice_esterno=request.form.get('codice_esterno', '').strip() or None,
            titolo=request.form['titolo'].strip(),
            tipologia=request.form.get('tipologia', '').strip() or None,
            ore=int(request.form.get('ore') or 30),
            n_partecipanti_previsti=int(request.form['n_partecipanti_previsti']) if request.form.get('n_partecipanti_previsti') else None,
            n_partecipanti_minimo=int(request.form.get('n_partecipanti_minimo') or 9),
            importo_autorizzato=_decimal(request.form, 'importo_autorizzato'),
            stato=request.form.get('stato', 'bozza'),
            data_inizio=_data(request.form, 'data_inizio'),
            data_fine=_data(request.form, 'data_fine'),
            note=request.form.get('note', '').strip() or None,
        )
        db.session.add(m)
        db.session.commit()
        flash(f'Modulo "{m.titolo}" aggiunto.', 'success')
        return redirect(url_for('progetti_fse.dettaglio', id=p.id))

    return render_template('progetti_fse/modulo_form.html', progetto=p, modulo=None,
        stati=STATI_MODULO)


@progetti_fse_bp.route('/progetti-fse/moduli/<int:id>/modifica', methods=['GET', 'POST'])
def modifica_modulo(id):
    m = ModuloFSE.query.get_or_404(id)
    if request.method == 'POST':
        m.codice_esterno = request.form.get('codice_esterno', '').strip() or None
        m.titolo = request.form['titolo'].strip()
        m.tipologia = request.form.get('tipologia', '').strip() or None
        m.ore = int(request.form.get('ore') or 30)
        m.n_partecipanti_previsti = int(request.form['n_partecipanti_previsti']) if request.form.get('n_partecipanti_previsti') else None
        m.n_partecipanti_minimo = int(request.form.get('n_partecipanti_minimo') or 9)
        m.importo_autorizzato = _decimal(request.form, 'importo_autorizzato')
        m.stato = request.form.get('stato', m.stato)
        m.data_inizio = _data(request.form, 'data_inizio')
        m.data_fine = _data(request.form, 'data_fine')
        m.note = request.form.get('note', '').strip() or None
        db.session.commit()
        flash('Modulo aggiornato.', 'success')
        return redirect(url_for('progetti_fse.dettaglio', id=m.id_progetto))

    return render_template('progetti_fse/modulo_form.html', progetto=m.progetto, modulo=m,
        stati=STATI_MODULO)


@progetti_fse_bp.route('/progetti-fse/moduli/<int:id>/elimina', methods=['POST'])
def elimina_modulo(id):
    m = ModuloFSE.query.get_or_404(id)
    id_progetto = m.id_progetto
    titolo = m.titolo
    db.session.delete(m)
    db.session.commit()
    flash(f'Modulo "{titolo}" eliminato.', 'warning')
    return redirect(url_for('progetti_fse.dettaglio', id=id_progetto))


# ── INCARICHI ─────────────────────────────────────────────────────────
@progetti_fse_bp.route('/progetti-fse/moduli/<int:id_modulo>/incarichi/nuovo', methods=['GET', 'POST'])
def nuovo_incarico(id_modulo):
    m = ModuloFSE.query.get_or_404(id_modulo)
    if request.method == 'POST':
        id_docente = request.form.get('id_docente') or None
        inc = IncaricoFSE(
            id_modulo=m.id,
            id_docente=int(id_docente) if id_docente else None,
            nome_esterno=request.form.get('nome_esterno', '').strip() or None,
            ruolo=request.form['ruolo'],
            tipo_rapporto=request.form.get('tipo_rapporto') or None,
            tariffa_oraria=_decimal(request.form, 'tariffa_oraria'),
            ore_previste=_decimal(request.form, 'ore_previste'),
            ore_rendicontate=_decimal(request.form, 'ore_rendicontate'),
            stato=request.form.get('stato', 'incaricato'),
            note=request.form.get('note', '').strip() or None,
        )
        db.session.add(inc)
        db.session.commit()
        flash(f'Incarico per {inc.nome_completo} aggiunto.', 'success')
        return redirect(url_for('progetti_fse.dettaglio', id=m.id_progetto))

    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    return render_template('progetti_fse/incarico_form.html', modulo=m, incarico=None,
        docenti=docenti, ruoli=RUOLI_INCARICO, tipi_rapporto=TIPI_RAPPORTO)


@progetti_fse_bp.route('/progetti-fse/incarichi/<int:id>/modifica', methods=['GET', 'POST'])
def modifica_incarico(id):
    inc = IncaricoFSE.query.get_or_404(id)
    if request.method == 'POST':
        id_docente = request.form.get('id_docente') or None
        inc.id_docente = int(id_docente) if id_docente else None
        inc.nome_esterno = request.form.get('nome_esterno', '').strip() or None
        inc.ruolo = request.form['ruolo']
        inc.tipo_rapporto = request.form.get('tipo_rapporto') or None
        inc.tariffa_oraria = _decimal(request.form, 'tariffa_oraria')
        inc.ore_previste = _decimal(request.form, 'ore_previste')
        inc.ore_rendicontate = _decimal(request.form, 'ore_rendicontate')
        inc.stato = request.form.get('stato', inc.stato)
        inc.note = request.form.get('note', '').strip() or None
        db.session.commit()
        flash('Incarico aggiornato.', 'success')
        return redirect(url_for('progetti_fse.dettaglio', id=inc.modulo.id_progetto))

    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    return render_template('progetti_fse/incarico_form.html', modulo=inc.modulo, incarico=inc,
        docenti=docenti, ruoli=RUOLI_INCARICO, tipi_rapporto=TIPI_RAPPORTO)


@progetti_fse_bp.route('/progetti-fse/incarichi/<int:id>/elimina', methods=['POST'])
def elimina_incarico(id):
    inc = IncaricoFSE.query.get_or_404(id)
    id_progetto = inc.modulo.id_progetto
    nome = inc.nome_completo
    db.session.delete(inc)
    db.session.commit()
    flash(f'Incarico di {nome} eliminato.', 'warning')
    return redirect(url_for('progetti_fse.dettaglio', id=id_progetto))


# ── CALENDARIO / SESSIONI ─────────────────────────────────────────────
@progetti_fse_bp.route('/progetti-fse/moduli/<int:id_modulo>/calendario', methods=['GET', 'POST'])
def calendario_modulo(id_modulo):
    m = ModuloFSE.query.get_or_404(id_modulo)
    if request.method == 'POST':
        s = SessioneFSE(
            id_modulo=m.id,
            data=_data(request.form, 'data'),
            ora_inizio=request.form.get('ora_inizio', '').strip() or None,
            ora_fine=request.form.get('ora_fine', '').strip() or None,
            note=request.form.get('note', '').strip() or None,
        )
        db.session.add(s)
        db.session.commit()
        flash('Sessione aggiunta al calendario.', 'success')
        return redirect(url_for('progetti_fse.calendario_modulo', id_modulo=m.id))

    from modules.conflitti_progetti_fse import trova_conflitti_progetti_fse
    conflitti_modulo = [c for c in trova_conflitti_progetti_fse()
                         if c['modulo'].id == m.id]
    conflitti_per_sessione = {}
    for c in conflitti_modulo:
        conflitti_per_sessione.setdefault(c['sessione'].id, []).append(c)

    return render_template('progetti_fse/calendario_modulo.html', modulo=m,
        conflitti_per_sessione=conflitti_per_sessione)


@progetti_fse_bp.route('/progetti-fse/sessioni/<int:id>/elimina', methods=['POST'])
def elimina_sessione(id):
    s = SessioneFSE.query.get_or_404(id)
    id_modulo = s.id_modulo
    db.session.delete(s)
    db.session.commit()
    flash('Sessione eliminata.', 'warning')
    return redirect(url_for('progetti_fse.calendario_modulo', id_modulo=id_modulo))


# ── REGISTRO PRESENZE ─────────────────────────────────────────────────
# Un'unica riga per partecipante con il monte ore CUMULATIVO di presenza
# (non una riga per sessione): è la stessa logica di SIF2127 — "ha
# assoluta rilevanza il numero totale delle ore registrate dal singolo
# partecipante e non il numero totale delle presenze giornaliere"
# (lettera di autorizzazione del progetto reale) — quindi il registro
# tiene un contatore che cresce man mano, non un dettaglio per data.
@progetti_fse_bp.route('/progetti-fse/moduli/<int:id_modulo>/presenze', methods=['GET', 'POST'])
def presenze_modulo(id_modulo):
    m = ModuloFSE.query.get_or_404(id_modulo)
    if request.method == 'POST':
        p = PresenzaFSE(
            id_modulo=m.id,
            cognome=request.form['cognome'].strip().upper(),
            nome=request.form['nome'].strip().title(),
            codice_fiscale=request.form.get('codice_fiscale', '').strip().upper() or None,
            ore_presenza=_decimal(request.form, 'ore_presenza') or 0,
        )
        db.session.add(p)
        db.session.commit()
        flash(f'{p.cognome} {p.nome} aggiunto al registro presenze.', 'success')
        return redirect(url_for('progetti_fse.presenze_modulo', id_modulo=m.id))

    partecipanti = sorted(m.presenze, key=lambda p: p.cognome)
    return render_template('progetti_fse/presenze_modulo.html', modulo=m,
        partecipanti=partecipanti)


@progetti_fse_bp.route('/progetti-fse/presenze/<int:id>/modifica-ore', methods=['POST'])
def modifica_ore_presenza(id):
    p = PresenzaFSE.query.get_or_404(id)
    p.ore_presenza = _decimal(request.form, 'ore_presenza') or 0
    db.session.commit()
    return redirect(url_for('progetti_fse.presenze_modulo', id_modulo=p.id_modulo))


@progetti_fse_bp.route('/progetti-fse/presenze/<int:id>/elimina', methods=['POST'])
def elimina_presenza(id):
    p = PresenzaFSE.query.get_or_404(id)
    id_modulo = p.id_modulo
    nome = f'{p.cognome} {p.nome}'
    db.session.delete(p)
    db.session.commit()
    flash(f'{nome} rimosso dal registro presenze.', 'warning')
    return redirect(url_for('progetti_fse.presenze_modulo', id_modulo=id_modulo))
