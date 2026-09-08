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
import io
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, send_file
from models import db
from models.progetto_fse import (
    ProgettoFSE, ModuloFSE, IncaricoFSE, SessioneFSE, PresenzaFSE, DocumentoFSE,
    STATI_PROGETTO, STATI_MODULO, RUOLI_INCARICO, RUOLI_INCARICO_LABEL,
    TIPI_RAPPORTO, TIPI_COSTO, STATI_DOCUMENTO,
    TIPI_DOCUMENTO_GENERABILI, TIPI_DOCUMENTO_GENERABILI_LABEL,
)
from models.docente import Docente
from modules import dati_istituto

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
            premesse_specifiche=request.form.get('premesse_specifiche', '').strip() or None,
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
        p.premesse_specifiche = request.form.get('premesse_specifiche', '').strip() or None
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
            luogo_nascita=request.form.get('luogo_nascita', '').strip() or None,
            data_nascita=_data(request.form, 'data_nascita'),
            codice_fiscale=request.form.get('codice_fiscale', '').strip().upper() or None,
            indirizzo_residenza=request.form.get('indirizzo_residenza', '').strip() or None,
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
        inc.luogo_nascita = request.form.get('luogo_nascita', '').strip() or None
        inc.data_nascita = _data(request.form, 'data_nascita')
        inc.codice_fiscale = request.form.get('codice_fiscale', '').strip().upper() or None
        inc.indirizzo_residenza = request.form.get('indirizzo_residenza', '').strip() or None
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


# ── GENERAZIONE DOCUMENTI ────────────────────────────────────────────
# I quattro modelli coprono il ciclo bandi -> nomina -> incarico
# richiesto: avviso di selezione interna, decreto di nomina, lettera di
# incarico (personale interno/altra scuola) e contratto di lavoro
# autonomo (esterni). Le circa 20 premesse normative generiche comuni a
# qualunque progetto FSE+/FESR sono fisse nel template
# (_premesse_normative.html); tutto il resto (dati progetto, moduli,
# incarichi, riferimenti a protocolli di documenti già generati) è
# variabile e viene passato dalla route.
#
# Il collegamento fra documenti successivi (es. il decreto di nomina
# cita il protocollo dell'avviso di selezione; il contratto cita quello
# del decreto) è automatico: quando un documento generato viene
# protocollato (route modifica_documento), il suo protocollo/data resta
# registrato sul DocumentoFSE e viene riletto per comporre la frase
# "prot. n. X del Y" nei documenti successivi dello stesso progetto —
# evitare di ridigitare a mano gli estremi riduce il rischio di errori
# di trascrizione nei riferimenti incrociati fra atti.
def _riferimento_documento(progetto, tipo):
    """Cerca l'ultimo DocumentoFSE protocollato di un certo tipo per il
    progetto e ne compone la stringa "prot. n. X del gg/mm/aaaa" da
    citare nei documenti successivi. None se non ancora protocollato."""
    doc = (DocumentoFSE.query
           .filter_by(id_progetto=progetto.id, tipo=tipo)
           .filter(DocumentoFSE.protocollo.isnot(None))
           .order_by(DocumentoFSE.data_documento.desc().nullslast(), DocumentoFSE.id.desc())
           .first())
    if not doc:
        return None
    if doc.data_documento:
        return f'prot. n. {doc.protocollo} del {doc.data_documento.strftime("%d/%m/%Y")}'
    return f'prot. n. {doc.protocollo}'


def _rendi_pdf_o_html(html_content, nome_file):
    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html_content).write_pdf()
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=False,
            download_name=f'{nome_file}.pdf',
        )
    except (ImportError, OSError):
        # ImportError: WeasyPrint non installato. OSError: WeasyPrint è
        # installato ma non trova le librerie di sistema (pango/cairo/
        # gdk-pixbuf) — stesso caso pratico già documentato per la
        # sandbox Linux (vedi CLAUDE.md), non un bug: fallback HTML con
        # CSS di stampa, stampabile comunque dal browser.
        return html_content


@progetti_fse_bp.route('/progetti-fse/<int:id_progetto>/documenti')
def documenti_progetto(id_progetto):
    p = ProgettoFSE.query.get_or_404(id_progetto)
    documenti = sorted(p.documenti, key=lambda d: d.creato_il, reverse=True)
    return render_template('progetti_fse/documenti_index.html', progetto=p,
        documenti=documenti, tipi_label=TIPI_DOCUMENTO_GENERABILI_LABEL,
        stati_label=dict(STATI_DOCUMENTO))


@progetti_fse_bp.route('/progetti-fse/documenti/<int:id>/modifica', methods=['GET', 'POST'])
def modifica_documento(id):
    doc = DocumentoFSE.query.get_or_404(id)
    if request.method == 'POST':
        doc.protocollo = request.form.get('protocollo', '').strip() or None
        doc.data_documento = _data(request.form, 'data_documento')
        doc.stato = request.form.get('stato', doc.stato)
        doc.note = request.form.get('note', '').strip() or None
        db.session.commit()
        flash('Documento aggiornato.', 'success')
        return redirect(url_for('progetti_fse.documenti_progetto', id_progetto=doc.id_progetto))

    return render_template('progetti_fse/documento_form.html', documento=doc,
        stati=STATI_DOCUMENTO, tipi_label=TIPI_DOCUMENTO_GENERABILI_LABEL)


@progetti_fse_bp.route('/progetti-fse/documenti/<int:id>/elimina', methods=['POST'])
def elimina_documento(id):
    doc = DocumentoFSE.query.get_or_404(id)
    id_progetto = doc.id_progetto
    db.session.delete(doc)
    db.session.commit()
    flash('Documento eliminato dall\'elenco (il file eventualmente scaricato non viene toccato).', 'warning')
    return redirect(url_for('progetti_fse.documenti_progetto', id_progetto=id_progetto))


@progetti_fse_bp.route('/progetti-fse/<int:id_progetto>/documenti/avviso-selezione', methods=['GET', 'POST'])
def genera_avviso_selezione(id_progetto):
    p = ProgettoFSE.query.get_or_404(id_progetto)
    requisito_esperto_default = (
        "Il requisito di accesso per il conferimento dell'incarico di Docente Esperto è la Laurea "
        "magistrale o Vecchio Ordinamento o specialistica oppure l'abilitazione all'insegnamento, nelle "
        "materie afferenti le tematiche e/o le attività oggetto del percorso per il quale ci si candida."
    )
    requisito_tutor_default = (
        "Il requisito di accesso per il conferimento dell'incarico di Docente Tutor è il diploma di scuola "
        "secondaria superiore oppure l'abilitazione all'insegnamento."
    )
    vincoli_default = (
        "I moduli saranno attivati entro l'anno scolastico in corso e conclusi entro il termine previsto "
        "dall'Autorità di gestione. I moduli potranno non essere attivati qualora non si raggiunga il "
        "numero minimo di partecipanti previsto e saranno revocati qualora il numero di frequentanti non "
        "consenta il raggiungimento del target."
    )
    if request.method == 'POST':
        html_content = render_template('progetti_fse/documenti/avviso_selezione.html',
            progetto=p, data_generazione=date.today(),
            scadenza_data=_data(request.form, 'scadenza_data'),
            scadenza_ora=request.form.get('scadenza_ora', '').strip() or '____',
            requisiti_esperto=request.form.get('requisiti_esperto', '').strip() or requisito_esperto_default,
            requisiti_tutor=request.form.get('requisiti_tutor', '').strip() or requisito_tutor_default,
            vincoli_attivazione=request.form.get('vincoli_attivazione', '').strip() or vincoli_default,
            istituto=dati_istituto.DENOMINAZIONE, comune=dati_istituto.COMUNE,
            peo=dati_istituto.PEO, sito_web=dati_istituto.SITO_WEB,
            ds_titolo=dati_istituto.DS_TITOLO, ds_nome=dati_istituto.DS_NOME_COGNOME,
            regolamento_incarichi=dati_istituto.REGOLAMENTO_INCARICHI_INDIVIDUALI,
        )
        doc = DocumentoFSE(id_progetto=p.id, tipo='avviso_selezione', fase='selezione',
            titolo=f'Avviso di selezione — {p.titolo}', stato='bozza',
            note=request.form.get('note_documento', '').strip() or None)
        db.session.add(doc)
        db.session.commit()
        flash('Avviso di selezione generato. Ricorda di registrare protocollo e data dopo la '
              'protocollazione.', 'success')
        return _rendi_pdf_o_html(html_content, f'avviso_selezione_{p.id}')

    return render_template('progetti_fse/documenti/genera_avviso.html', progetto=p,
        requisito_esperto_default=requisito_esperto_default,
        requisito_tutor_default=requisito_tutor_default,
        vincoli_default=vincoli_default)


@progetti_fse_bp.route('/progetti-fse/<int:id_progetto>/documenti/decreto-nomina', methods=['GET', 'POST'])
def genera_decreto_nomina(id_progetto):
    p = ProgettoFSE.query.get_or_404(id_progetto)
    incarichi_disponibili = [i for m in p.moduli for i in m.incarichi if i.stato == 'incaricato']

    if request.method == 'POST':
        ids_scelti = {int(v) for v in request.form.getlist('id_incarico')}
        incarichi = [i for i in incarichi_disponibili if i.id in ids_scelti]
        if not incarichi:
            flash('Seleziona almeno un incarico da nominare.', 'error')
            return redirect(url_for('progetti_fse.genera_decreto_nomina', id_progetto=p.id))

        riferimento_bando = _riferimento_documento(p, 'avviso_selezione') or p.riferimento_bando_interno
        html_content = render_template('progetti_fse/documenti/decreto_nomina.html',
            progetto=p, data_generazione=date.today(), incarichi=incarichi,
            ruoli_label=RUOLI_INCARICO_LABEL, riferimento_bando=riferimento_bando,
            note_aggiuntive=request.form.get('note_aggiuntive', '').strip() or None,
            sito_web=dati_istituto.SITO_WEB,
            ds_titolo=dati_istituto.DS_TITOLO, ds_nome=dati_istituto.DS_NOME_COGNOME,
        )
        doc = DocumentoFSE(id_progetto=p.id, tipo='decreto_nomina', fase='nomina',
            titolo=f'Decreto di nomina — {p.titolo}', stato='bozza',
            note=request.form.get('note_documento', '').strip() or None)
        db.session.add(doc)
        db.session.commit()
        flash('Decreto di nomina generato. Ricorda di registrare protocollo e data dopo la '
              'protocollazione.', 'success')
        return _rendi_pdf_o_html(html_content, f'decreto_nomina_{p.id}')

    return render_template('progetti_fse/documenti/genera_decreto.html', progetto=p,
        incarichi_disponibili=incarichi_disponibili, ruoli_label=RUOLI_INCARICO_LABEL)


@progetti_fse_bp.route('/progetti-fse/incarichi/<int:id_incarico>/documenti/lettera-incarico', methods=['GET', 'POST'])
def genera_lettera_incarico(id_incarico):
    inc = IncaricoFSE.query.get_or_404(id_incarico)
    p = inc.modulo.progetto

    if request.method == 'POST':
        riferimento_bando = _riferimento_documento(p, 'avviso_selezione') or p.riferimento_bando_interno
        riferimento_decreto = _riferimento_documento(p, 'decreto_nomina')
        riferimento_graduatoria = request.form.get('riferimento_graduatoria', '').strip() or None
        html_content = render_template('progetti_fse/documenti/lettera_incarico.html',
            progetto=p, incarico=inc, data_generazione=date.today(),
            ruoli_label=RUOLI_INCARICO_LABEL, istituto=dati_istituto.DENOMINAZIONE,
            comune=dati_istituto.COMUNE, sito_web=dati_istituto.SITO_WEB,
            riferimento_bando=riferimento_bando, riferimento_decreto=riferimento_decreto,
            riferimento_graduatoria=riferimento_graduatoria,
            ds_titolo=dati_istituto.DS_TITOLO, ds_nome=dati_istituto.DS_NOME_COGNOME,
        )
        doc = DocumentoFSE(id_progetto=p.id, id_modulo=inc.id_modulo, id_incarico=inc.id,
            tipo='lettera_incarico', fase='incarico',
            titolo=f'Lettera di incarico — {inc.nome_completo}', stato='bozza',
            note=request.form.get('note_documento', '').strip() or None)
        db.session.add(doc)
        db.session.commit()
        flash('Lettera di incarico generata. Ricorda di registrare protocollo e data dopo la '
              'protocollazione.', 'success')
        return _rendi_pdf_o_html(html_content, f'lettera_incarico_{inc.id}')

    return render_template('progetti_fse/documenti/genera_incarico.html', incarico=inc,
        tipo_documento='lettera_incarico',
        riferimento_graduatoria_default='')


@progetti_fse_bp.route('/progetti-fse/incarichi/<int:id_incarico>/documenti/contratto-autonomo', methods=['GET', 'POST'])
def genera_contratto_autonomo(id_incarico):
    inc = IncaricoFSE.query.get_or_404(id_incarico)
    p = inc.modulo.progetto

    if request.method == 'POST':
        riferimento_bando = _riferimento_documento(p, 'avviso_selezione') or p.riferimento_bando_interno
        riferimento_decreto = _riferimento_documento(p, 'decreto_nomina')
        riferimento_graduatoria = request.form.get('riferimento_graduatoria', '').strip() or None
        html_content = render_template('progetti_fse/documenti/contratto_autonomo.html',
            progetto=p, incarico=inc, data_generazione=date.today(),
            ruoli_label=RUOLI_INCARICO_LABEL, istituto=dati_istituto.DENOMINAZIONE,
            comune=dati_istituto.COMUNE, provincia=dati_istituto.PROVINCIA,
            istituto_cf=dati_istituto.CODICE_FISCALE, istituto_indirizzo=dati_istituto.INDIRIZZO,
            istituto_cuf=dati_istituto.CODICE_UNIVOCO_FATTURAZIONE,
            foro_competente=dati_istituto.FORO_COMPETENTE,
            riferimento_bando=riferimento_bando, riferimento_decreto=riferimento_decreto,
            riferimento_graduatoria=riferimento_graduatoria,
            ds_titolo=dati_istituto.DS_TITOLO, ds_nome=dati_istituto.DS_NOME_COGNOME,
        )
        doc = DocumentoFSE(id_progetto=p.id, id_modulo=inc.id_modulo, id_incarico=inc.id,
            tipo='contratto_autonomo', fase='incarico',
            titolo=f'Contratto di lavoro autonomo — {inc.nome_completo}', stato='bozza',
            note=request.form.get('note_documento', '').strip() or None)
        db.session.add(doc)
        db.session.commit()
        flash('Contratto di lavoro autonomo generato. Ricorda di registrare protocollo e data dopo '
              'la protocollazione.', 'success')
        return _rendi_pdf_o_html(html_content, f'contratto_autonomo_{inc.id}')

    if not inc.codice_fiscale or not inc.luogo_nascita or not inc.indirizzo_residenza:
        flash('Attenzione: mancano alcuni dati anagrafici dell\'incaricato (luogo/data di nascita, '
              'codice fiscale, indirizzo di residenza). Il contratto verrà generato con i campi mancanti '
              'vuoti: completali dalla scheda incarico prima di inviarlo.', 'error')

    return render_template('progetti_fse/documenti/genera_incarico.html', incarico=inc,
        tipo_documento='contratto_autonomo',
        riferimento_graduatoria_default='')
