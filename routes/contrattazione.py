"""
routes/contrattazione.py — Contrattazione integrativa d'istituto, area
per la segreteria/ufficio contabilità (vedi models/contrattazione.py
per il flusso completo: economie -> fondo -> quota DSGA -> capitoli ->
assegnazioni ai docenti -> eventuali spostamenti tra capitoli).

La lettera di incarico (vedi in fondo al file) segue il modello fornito
dal Dirigente ("Tipologie incarichi.docx"): per ogni destinatario è
CUMULATIVA di tutti gli incarichi assegnati nell'anno, con una tabella
riassuntiva (incarico / riferimento / compenso) seguita dal testo
descrittivo esteso — ma SOLO per gli incarichi davvero assegnati a quel
docente, mai l'intero catalogo. Il testo descrittivo di ciascun tipo di
incarico vive nel catalogo TipoIncaricoContrattazione, che la segreteria
compila/aggiorna a mano (anche con l'import massivo qui sotto) — è testo
contrattuale, non generato né trascritto in automatico da fonti esterne.
"""
import io
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db
from datetime import date
from models.contrattazione import (
    FondoContrattazione, CapitoloContrattazione, AssegnazioneContrattazione,
    StoricoSpostamentoCapitolo, STATI_ASSEGNAZIONE, STATI_ASSEGNAZIONE_LABEL,
    TipoIncaricoContrattazione, ImpostazioniLetteraContrattazione,
    LetteraIncaricoProtocollo,
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
    catalogo = TipoIncaricoContrattazione.query.filter_by(attivo=True).order_by(TipoIncaricoContrattazione.nome).all()
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
        asg.id_tipo_incarico = request.form.get('id_tipo_incarico', type=int) or None
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
                           docenti=docenti, stati=STATI_ASSEGNAZIONE, catalogo=catalogo)


@contrattazione_bp.route('/contrattazione/assegnazione/<int:id>/elimina', methods=['POST'])
def assegnazione_elimina(id):
    asg = AssegnazioneContrattazione.query.get_or_404(id)
    anno = asg.capitolo.fondo.anno_scol
    db.session.delete(asg)
    db.session.commit()
    flash('Assegnazione eliminata.', 'warning')
    return redirect(url_for('contrattazione.index', anno=anno))


@contrattazione_bp.route('/contrattazione/assegnazione/<int:id>/liquida', methods=['POST'])
def assegnazione_liquida(id):
    """Registra l'importo DEFINITIVO di un incarico, senza sovrascrivere
    il previsto (quello già comunicato in lettera) — Roberto: l'importo
    previsto "potrebbe subire variazioni", la differenza deve restare
    visibile. Da qui nascerà (quando ci sarà il modello) il documento
    'Retribuzione fondi MOF'."""
    asg = AssegnazioneContrattazione.query.get_or_404(id)
    anno = asg.capitolo.fondo.anno_scol
    importo_liq = _float(request.form.get('importo_liquidato'), None)
    if importo_liq is None:
        flash('Indica l\'importo liquidato.', 'error')
        return redirect(url_for('contrattazione.index', anno=anno))
    asg.importo_liquidato = importo_liq
    asg.data_liquidazione = date.today()
    asg.stato = 'liquidato'
    db.session.commit()
    diff = round(importo_liq - asg.importo, 2)
    msg = f'"{asg.descrizione}" ({asg.docente.cognome}) liquidato a {importo_liq:.2f}€.'
    if abs(diff) > 0.004:
        msg += f' Differenza rispetto al previsto: {diff:+.2f}€.'
    flash(msg, 'success')
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


# ── Catalogo tipi di incarico (testo descrittivo per la lettera) ───────────

@contrattazione_bp.route('/contrattazione/catalogo')
def catalogo():
    voci = TipoIncaricoContrattazione.query.order_by(TipoIncaricoContrattazione.nome).all()
    return render_template('contrattazione/catalogo.html', voci=voci)


@contrattazione_bp.route('/contrattazione/catalogo/nuovo', methods=['GET', 'POST'])
@contrattazione_bp.route('/contrattazione/catalogo/<int:id>/modifica', methods=['GET', 'POST'])
def catalogo_form(id=None):
    voce = TipoIncaricoContrattazione.query.get_or_404(id) if id else None
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        testo = request.form.get('testo_riferimento', '').strip()
        numero = request.form.get('numero_riferimento', '').strip()
        if not nome or not testo:
            flash('Nome e testo descrittivo sono obbligatori.', 'error')
            return redirect(request.url)
        if voce is None:
            voce = TipoIncaricoContrattazione()
            db.session.add(voce)
        voce.nome               = nome
        voce.numero_riferimento = numero or None
        voce.testo_riferimento  = testo
        voce.attivo             = request.form.get('attivo') == '1'
        db.session.commit()
        flash(f'Voce "{voce.nome}" salvata nel catalogo.', 'success')
        return redirect(url_for('contrattazione.catalogo'))
    return render_template('contrattazione/catalogo_form.html', voce=voce)


@contrattazione_bp.route('/contrattazione/catalogo/<int:id>/elimina', methods=['POST'])
def catalogo_elimina(id):
    voce = TipoIncaricoContrattazione.query.get_or_404(id)
    in_uso = AssegnazioneContrattazione.query.filter_by(id_tipo_incarico=id).count()
    if in_uso:
        flash(f'"{voce.nome}" è collegata a {in_uso} assegnazione/i: non può essere eliminata. '
              'Puoi disattivarla modificandola.', 'error')
        return redirect(url_for('contrattazione.catalogo'))
    db.session.delete(voce)
    db.session.commit()
    flash(f'Voce "{voce.nome}" eliminata dal catalogo.', 'warning')
    return redirect(url_for('contrattazione.catalogo'))


@contrattazione_bp.route('/contrattazione/catalogo/importa', methods=['GET', 'POST'])
def catalogo_importa():
    """Import massivo da testo incollato: blocchi separati da una riga
    '---', prima riga di ogni blocco = nome (con eventuale 'numero:'
    davanti, es. '2 TUTOR DOCENTI NEOIMMESSI'), righe successive = testo
    descrittivo. Nessun parsing euristico del docx originale: il testo
    è materia contrattuale, lo incolla la segreteria con pieno
    controllo di cosa entra nel catalogo."""
    if request.method == 'POST':
        testo = request.form.get('testo', '')
        blocchi = [b.strip() for b in testo.split('\n---\n') if b.strip()]
        # Riconosce un numero/riferimento iniziale sulla prima riga del
        # blocco, se c'è (come nel modello del Dirigente: "2 TUTOR
        # DOCENTI...", "28 bis: REFERENTE FSL CLASSE", "31. COORDINATORE")
        # e lo separa dal nome — ma non è più obbligatorio: un blocco
        # senza numero riconoscibile viene comunque importato, solo con
        # la colonna "Rif." vuota (Roberto: tolto il blocco che
        # impediva l'inserimento senza numero).
        pattern_numero = re.compile(r'^(?P<num>\d+(?:\s*bis)?)\s*[\.:\)]?\s+(?P<nome>.+)$', re.IGNORECASE)
        creati, saltati_senza_numero, saltati_esistenti = 0, 0, 0
        for blocco in blocchi:
            righe = [r for r in blocco.split('\n') if r.strip()]
            if len(righe) < 2:
                continue
            prima_riga = righe[0].strip()
            corpo = '\n'.join(righe[1:]).strip()
            m = pattern_numero.match(prima_riga)
            numero, nome = (m.group('num').strip(), m.group('nome').strip()) if m else (None, prima_riga)
            if TipoIncaricoContrattazione.query.filter_by(nome=nome).first():
                saltati_esistenti += 1
                continue
            if not m:
                saltati_senza_numero += 1
            db.session.add(TipoIncaricoContrattazione(nome=nome, numero_riferimento=numero,
                                                       testo_riferimento=corpo))
            creati += 1
        db.session.commit()
        msg = f'Importate {creati} voci nel catalogo.'
        if saltati_esistenti:
            msg += f' {saltati_esistenti} già esistenti (stesso nome) saltate.'
        if saltati_senza_numero:
            msg += (f' {saltati_senza_numero} importate senza numero di riferimento (la prima riga non '
                    'ne aveva uno riconoscibile) — puoi aggiungerlo in un secondo momento modificando la voce.')
        flash(msg, 'success')
        return redirect(url_for('contrattazione.catalogo'))
    return render_template('contrattazione/catalogo_importa.html')


# ── Impostazioni lettera (riferimenti normativi per anno) ──────────────────

@contrattazione_bp.route('/contrattazione/lettera/impostazioni', methods=['GET', 'POST'])
def impostazioni_lettera():
    anno = request.args.get('anno') or get_anno_corrente()
    imp = ImpostazioniLetteraContrattazione.query.filter_by(anno_scol=anno).first()
    if request.method == 'POST':
        if imp is None:
            imp = ImpostazioniLetteraContrattazione(anno_scol=anno)
            db.session.add(imp)
        imp.riferimento_ccnl     = request.form.get('riferimento_ccnl', '').strip() or None
        imp.riferimento_ptof     = request.form.get('riferimento_ptof', '').strip() or None
        imp.riferimento_delibere = request.form.get('riferimento_delibere', '').strip() or None
        imp.scadenza_relazione   = request.form.get('scadenza_relazione', '').strip() or None
        imp.nota_valorizzazione  = request.form.get('nota_valorizzazione', '').strip() or None
        db.session.commit()
        flash('Impostazioni della lettera di incarico salvate.', 'success')
        return redirect(url_for('contrattazione.impostazioni_lettera', anno=anno))
    return render_template('contrattazione/impostazioni_lettera.html', imp=imp, anno=anno)


# ── Lettera di incarico (cumulativa per docente) ────────────────────────────

@contrattazione_bp.route('/contrattazione/lettere')
def lettere_index():
    """Un docente per riga, con il totale degli incarichi/importi
    dell'anno — solo chi ha almeno un'assegnazione (Roberto: la lettera
    è cumulativa di tutti gli incarichi assegnati a quella persona)."""
    anno = request.args.get('anno') or get_anno_corrente()
    righe = (db.session.query(Docente)
             .join(AssegnazioneContrattazione, AssegnazioneContrattazione.id_docente == Docente.id)
             .join(CapitoloContrattazione, AssegnazioneContrattazione.id_capitolo == CapitoloContrattazione.id)
             .join(FondoContrattazione, CapitoloContrattazione.id_fondo == FondoContrattazione.id)
             .filter(FondoContrattazione.anno_scol == anno)
             .distinct().order_by(Docente.cognome).all())
    protocolli = {p.id_docente: p for p in LetteraIncaricoProtocollo.query.filter_by(anno_scol=anno).all()}
    dettaglio = []
    for d in righe:
        assegnazioni = _assegnazioni_docente(d.id, anno)
        dettaglio.append({'docente': d, 'n_incarichi': len(assegnazioni),
                          'totale': round(sum(a.importo for a in assegnazioni), 2),
                          'n_liquidati': sum(1 for a in assegnazioni if a.stato == 'liquidato'),
                          'protocollo': protocolli.get(d.id)})
    return render_template('contrattazione/lettere_index.html', dettaglio=dettaglio, anno=anno)


@contrattazione_bp.route('/contrattazione/lettere/<int:id_docente>/protocollo', methods=['POST'])
def lettera_protocollo(id_docente):
    """Registra prot./data della lettera di incarico cumulativa di un
    docente per l'anno, DOPO che è stata elaborata (Roberto: "dobbiamo
    tenere traccia dei numeri di protocollo delle lettere di
    assegnazione")."""
    anno = request.form.get('anno') or get_anno_corrente()
    riga = LetteraIncaricoProtocollo.query.filter_by(id_docente=id_docente, anno_scol=anno).first()
    numero = request.form.get('numero_protocollo', '').strip()
    data_s = request.form.get('data_protocollo', '').strip()
    if riga is None:
        riga = LetteraIncaricoProtocollo(id_docente=id_docente, anno_scol=anno)
        db.session.add(riga)
    riga.numero_protocollo = numero or None
    riga.data_protocollo = date.fromisoformat(data_s) if data_s else None
    riga.note = request.form.get('note', '').strip() or None
    db.session.commit()
    flash('Protocollo registrato.', 'success')
    return redirect(url_for('contrattazione.lettere_index', anno=anno))


def _assegnazioni_docente(id_docente, anno_scol):
    return (AssegnazioneContrattazione.query
            .join(CapitoloContrattazione, AssegnazioneContrattazione.id_capitolo == CapitoloContrattazione.id)
            .join(FondoContrattazione, CapitoloContrattazione.id_fondo == FondoContrattazione.id)
            .filter(AssegnazioneContrattazione.id_docente == id_docente,
                    FondoContrattazione.anno_scol == anno_scol)
            .order_by(AssegnazioneContrattazione.id).all())


@contrattazione_bp.route('/contrattazione/lettere/<int:id_docente>')
def lettera_genera(id_docente):
    from routes.progetti_fse import _contesto_istituto, _rendi_documento
    anno = request.args.get('anno') or get_anno_corrente()
    docente = Docente.query.get_or_404(id_docente)
    assegnazioni = _assegnazioni_docente(id_docente, anno)
    if not assegnazioni:
        flash(f'{docente.cognome} non ha incarichi di contrattazione per l\'anno {anno}.', 'error')
        return redirect(url_for('contrattazione.lettere_index', anno=anno))
    imp = ImpostazioniLetteraContrattazione.query.filter_by(anno_scol=anno).first()

    # Elenco descrittivo: solo i tipi di incarico davvero assegnati a
    # QUESTO docente, deduplicati (se ha due assegnazioni dello stesso
    # tipo, il testo compare una sola volta) — mai l'intero catalogo.
    visti = []
    seen = set()
    for a in assegnazioni:
        if a.tipo_incarico and a.tipo_incarico.id not in seen:
            seen.add(a.tipo_incarico.id)
            visti.append(a.tipo_incarico)

    totale = round(sum(a.importo for a in assegnazioni), 2)
    formato = 'docx' if request.args.get('formato') == 'docx' else 'pdf'
    html_content = render_template('contrattazione/lettera_incarico.html',
        docente=docente, anno_scol=anno, assegnazioni=assegnazioni, totale=totale,
        voci_descrittive=visti, impostazioni=imp,
        data_generazione=__import__('datetime').date.today(),
        **_contesto_istituto())
    nome_file = f'Lettera_incarico_{docente.cognome}_{anno}'.replace(' ', '_')
    return _rendi_documento(html_content, nome_file, formato=formato)
