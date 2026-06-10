from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db
from models.supplenza import Supplenza
from models.docente import Docente
from models.movimento_banca_ore import MovimentoBancaOre
from models.orario_docente import OrarioDocente
from models.attivita_fuori_aula import AttivitaFuoriAula, AttivitaClasse
from models.assenza import Assenza
from models.indisponibilita import Indisponibilita
from sqlalchemy import func
from datetime import date

supplenze_bp = Blueprint('supplenze', __name__)

ORA_LABEL = {
    1: '1ª  7:45–8:40',   2: '2ª  8:40–9:35',
    3: '3ª  9:35–10:40',  4: '4ª 10:40–11:30',
    5: '5ª 11:30–12:25',  6: '6ª 12:25–13:25',
    7: '7ª 13:25–14:25',  8: '8ª 14:25–15:25',
    9: '9ª 15:25–16:25',
}

# Tipi che alimentano la banca ore in positivo
TIPI_CON_RECUPERO = {'recupero'}


# ── NUOVA SUPPLENZA ──────────────────────────────────────────
@supplenze_bp.route('/supplenze/nuova', methods=['GET', 'POST'])
def nuova():
    if request.method == 'POST':
        data_str      = request.form['data']
        ora           = int(request.form['ora'])
        classe        = request.form['classe'].strip().upper()
        id_assente    = request.form.get('id_assente') or None
        id_sost       = request.form.get('id_sostituto') or None
        tipo          = request.form.get('tipo', '') or None
        note          = request.form.get('note', '')
        classe_scoperta = request.form.get('classe_scoperta') == '1'
        nota_display  = request.form.get('note_display', '').strip()
        data_ins      = date.fromisoformat(data_str)

        if classe_scoperta:
            tipo  = 'non_assegnabile'
            stato = 'non_assegnabile'
            if not nota_display:
                nota_display = 'NON ASSEGNABILE'
        else:
            stato = 'assegnata' if id_sost else 'scoperta'

        s = Supplenza(
            data         = data_ins,
            ora          = ora,
            classe       = classe,
            id_assente   = int(id_assente) if id_assente else None,
            id_sostituto = int(id_sost)    if id_sost    else None,
            tipo         = tipo,
            stato        = stato,
            note_display = nota_display,
            note         = note,
            origine      = 'manuale',
        )
        db.session.add(s)
        db.session.flush()

        if id_sost and tipo in TIPI_CON_RECUPERO:
            _registra_movimento(int(id_sost), data_ins, tipo, s.id)

        db.session.commit()
        flash('Supplenza registrata.', 'success')
        return redirect(url_for('dashboard.index', data=data_str))

    oggi     = date.today()
    data_str = request.args.get('data', oggi.isoformat())
    docenti  = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    return render_template('supplenza_form.html',
        docenti=docenti, data_sel=data_str, ore=ORA_LABEL)


# ── ASSEGNA SOSTITUTO (form inline dashboard) ─────────────────
@supplenze_bp.route('/supplenze/<int:id>/assegna', methods=['POST'])
def assegna(id):
    s       = Supplenza.query.get_or_404(id)
    id_sost = request.form.get('id_sostituto')
    tipo    = request.form.get('tipo', s.tipo or '') or None

    if not id_sost:
        flash('Seleziona un sostituto.', 'warning')
        return redirect(url_for('dashboard.index', data=s.data.isoformat()))

    # Rimuovi vecchio movimento se c'era già un sostituto
    if s.id_sostituto:
        MovimentoBancaOre.query.filter_by(id_supplenza=s.id).delete()

    s.id_sostituto = int(id_sost)
    s.tipo         = tipo
    s.stato        = 'assegnata'

    # Registra movimento solo se tipo = recupero
    if tipo in TIPI_CON_RECUPERO:
        _registra_movimento(int(id_sost), s.data, tipo, s.id)

    db.session.commit()
    docente = Docente.query.get(int(id_sost))
    flash(f'Assegnato: {docente.cognome} — {tipo}.', 'success')
    return redirect(url_for('dashboard.index', data=s.data.isoformat()))


# ── ANNULLA ───────────────────────────────────────────────────
@supplenze_bp.route('/supplenze/<int:id>/annulla', methods=['POST'])
def annulla(id):
    s = Supplenza.query.get_or_404(id)
    s.stato = 'annullata'
    MovimentoBancaOre.query.filter_by(id_supplenza=s.id).delete()
    db.session.commit()
    flash('Supplenza annullata.', 'warning')
    return redirect(url_for('dashboard.index', data=s.data.isoformat()))


# ── API SUGGERIMENTI ──────────────────────────────────────────
@supplenze_bp.route('/api/suggerimenti')
def api_suggerimenti():
    """
    GET /api/suggerimenti?data=2026-05-26&ora=2&id_assente=5
    Ritorna JSON con i gruppi di candidati ordinati per debito banca ore.
    """
    data_str   = request.args.get('data', date.today().isoformat())
    ora        = int(request.args.get('ora', 1))
    id_assente = request.args.get('id_assente', type=int)
    classe_sup = request.args.get('classe', '')

    try:
        data_sel = date.fromisoformat(data_str)
    except ValueError:
        return jsonify({'error': 'data non valida'}), 400

    giorno = data_sel.weekday()  # 0=lun … 5=sab
    if giorno > 5:
        return jsonify({'gruppi': [], 'msg': 'Domenica — nessuna lezione'})

    # ── Docenti esclusi ──────────────────────────────────────
    from models.indisponibilita_ricorrente import IndisponibilitaRicorrente

    # Tutte le assenze del giorno per questo docente
    assenze_giorno = Assenza.query.filter_by(data=data_sel).all()

    # 1a. Assenti per TUTTO il giorno (malattia, permesso giornaliero, ecc.)
    #     → motivo non è permesso_orario, oppure coprono tutte le ore
    #     In pratica: se l'assenza non ha ora_inizio/fine definite, o copre un arco
    #     molto ampio → escludi da tutte le ore
    assenti_tutto_giorno_ids = set()
    assenti_ora_ids = set()
    for a in assenze_giorno:
        # Assenza senza range orario = tutto il giorno
        if a.ora_inizio is None or a.ora_fine is None:
            assenti_tutto_giorno_ids.add(a.id_docente)
        # Assenza che copre tutto il giorno (range 1-9 o simile)
        elif a.ora_inizio <= 1 and a.ora_fine >= 8:
            assenti_tutto_giorno_ids.add(a.id_docente)
        elif a.ora_inizio <= ora <= a.ora_fine:
            # Permesso orario: copre solo alcune ore
            assenti_ora_ids.add(a.id_docente)
    assenti_ids = assenti_tutto_giorno_ids | assenti_ora_ids

    # 2. Già assegnati come sostituto nella stessa ora
    sups_stessa_ora = (Supplenza.query
        .filter_by(data=data_sel, ora=ora)
        .filter(Supplenza.stato.in_(['assegnata', 'scoperta']))
        .filter(Supplenza.id_sostituto.isnot(None))
        .all())
    # Chi copre POTENZIAMENTO è occupato in quell'ora MA resta visibile
    # nel gruppo potenziamento (non impegnato su una classe vera)
    occupati_ids     = {s.id_sostituto for s in sups_stessa_ora
                        if s.tipo != 'potenziamento'}
    occupati_pot_ids = {s.id_sostituto for s in sups_stessa_ora
                        if s.tipo == 'potenziamento'}
    # 3. Indisponibili in quella specifica ora — singole
    indisp_ids = {
        i.id_docente for i in
        Indisponibilita.query.filter_by(data=data_sel)
        .filter(
            db.or_(Indisponibilita.ora.is_(None), Indisponibilita.ora == ora)
        ).all()
    }
    # 4. Indisponibili — ricorrenti (colloqui fissi dalla scheda docente)
    indisp_ids |= {
        ir.id_docente for ir in
        IndisponibilitaRicorrente.query.filter_by(
            giorno=giorno, attiva=True
        ).filter(
            db.or_(IndisponibilitaRicorrente.ora.is_(None),
                   IndisponibilitaRicorrente.ora == ora)
        ).all()
    }
    # 5. Colloqui fissi dal profilo docente
    #    ma escludi docenti con eccezione colloqui per questa data
    from models.colloqui_eccezione import ColloquiEccezione
    eccezioni_colloqui = {
        e.id_docente for e in
        ColloquiEccezione.query.filter_by(data=data_sel).all()
    }
    for d in Docente.query.filter_by(attivo=True).all():
        if d.id in eccezioni_colloqui:
            continue  # colloquio spostato al pomeriggio — disponibile
        if (d.colloqui_giorno == giorno and
            d.colloqui_ora_inizio is not None and
            d.colloqui_ora_fine is not None and
            d.colloqui_ora_inizio <= ora <= d.colloqui_ora_fine):
            indisp_ids.add(d.id)
    # Applica anche le eccezioni alle indisponibilità ricorrenti
    indisp_ids -= eccezioni_colloqui
    # 4. Il docente assente stesso
    if id_assente:
        assenti_ids.add(id_assente)

    esclusi = assenti_ids | occupati_ids | indisp_ids

    # ── Saldo banca ore per docente — effettivo e previsto ──
    oggi_q = date.today()
    # Effettivo: movimenti <= oggi
    saldi_eff_raw = db.session.query(
        MovimentoBancaOre.id_docente,
        func.sum(MovimentoBancaOre.minuti).label('totale')
    ).filter(MovimentoBancaOre.data <= oggi_q
    ).group_by(MovimentoBancaOre.id_docente).all()
    saldi_eff = {r.id_docente: r.totale or 0 for r in saldi_eff_raw}

    # Previsto: movimenti > oggi
    saldi_prev_raw = db.session.query(
        MovimentoBancaOre.id_docente,
        func.sum(MovimentoBancaOre.minuti).label('totale')
    ).filter(MovimentoBancaOre.data > oggi_q
    ).group_by(MovimentoBancaOre.id_docente).all()
    saldi_prev = {r.id_docente: r.totale or 0 for r in saldi_prev_raw}

    # Totale per ordinamento
    saldi = {doc_id: saldi_eff.get(doc_id, 0) for doc_id in
             set(list(saldi_eff.keys()) + list(saldi_prev.keys()))}
    for doc_id in saldi_prev:
        saldi.setdefault(doc_id, 0)

    # ── Tutti i docenti attivi non esclusi ───────────────────
    tutti = {
        d.id: d for d in
        Docente.query.filter_by(attivo=True).all()
        if d.id not in esclusi
    }

    # ── Slot orario di tutti i docenti in quel giorno ────────
    slots_giorno = OrarioDocente.query.filter_by(giorno=giorno).all()

    # Mappa id_docente -> lista slot del giorno
    slots_per_doc = {}
    for s in slots_giorno:
        slots_per_doc.setdefault(s.id_docente, []).append(s)

    # ── Costruisce gruppi ────────────────────────────────────
    gruppo_pot    = []  # Potenziamento nell'ora
    gruppo_comp   = []  # Compresenza nell'ora
    gruppo_adj    = []  # Liberi nell'ora con ora adiacente
    gruppo_liberi = []  # Liberi nell'ora senza adiacenza

    for doc_id, doc in tutti.items():
        slots = slots_per_doc.get(doc_id, [])
        slot_ora = next((s for s in slots if s.ora == ora), None)
        saldo    = saldi.get(doc_id, 0)

        # Controlla se il docente ha lezione nella classe della supplenza
        docente_della_classe = False
        if classe_sup:
            docente_della_classe = any(
                s.classe == classe_sup for s in slots
            )

        saldo_eff  = saldi_eff.get(doc_id, 0)
        saldo_prev = saldi_prev.get(doc_id, 0)
        saldo_tot  = saldo_eff + saldo_prev
        saldo_label = _fmt_saldo(saldo_eff)
        if saldo_prev != 0:
            saldo_label += f' → {_fmt_saldo(saldo_tot)}'

        # Verifica compresenza con l'assente
        # Un docente è in compresenza reale solo se:
        # 1. ha lo stesso slot (classe+ora) dell'assente
        # 2. l'assente ha una vera assenza (non solo indisponibilità BIM/FSL)
        # 3. il candidato NON è assente né indisponibile in quell'ora
        from modules.compresenze import get_compresenze, compagni_presenti
        compresenza_con_assente = False
        partner_ids = []
        if id_assente and classe_sup:
            for slot_ass in OrarioDocente.query.filter_by(
                    id_docente=id_assente, giorno=giorno).all():
                if slot_ass.ora == ora and slot_ass.classe == classe_sup:
                    tutti = get_compresenze(giorno, ora, classe_sup)
                    if doc_id in tutti:
                        # Assente ha vera assenza su quella classe?
                        # Esclude assenze AUTO da attività (accompagnatore BIM/FSL ecc.)
                        # — in quel caso la classe è scoperta, non coperta dal compagno
                        ass_reale = Assenza.query.filter_by(
                            id_docente=id_assente, data=data_sel
                        ).filter(
                            Assenza.ora_inizio <= ora,
                            Assenza.ora_fine   >= ora,
                            ~Assenza.note_interne.like('Auto — %')
                        ).first()
                        if ass_reale:
                            # Il candidato è presente (non assente né indisponibile)?
                            cand_indisp = Indisponibilita.query.filter_by(
                                id_docente=doc_id, data=data_sel, ora=ora
                            ).first()
                            cand_ass = Assenza.query.filter_by(
                                id_docente=doc_id, data=data_sel
                            ).filter(
                                Assenza.ora_inizio<=ora, Assenza.ora_fine>=ora
                            ).first()
                            if not cand_indisp and not cand_ass:
                                compresenza_con_assente = True
                                # Partner = altri compagni presenti (esclude assente e candidato)
                                partner_ids = [c for c in compagni_presenti(
                                    id_assente, giorno, ora, classe_sup, data_sel)
                                    if c != doc_id]
                    break

        # Badge visivo per tipo disponibilità
        badge_tipo = None
        if doc.ruolo == 'itp' if hasattr(doc,'ruolo') else False:
            badge_tipo = {'label': 'ITP', 'color': '#7c3aed', 'bg': '#f5f3ff'}
        # Multi-sede: verifica se la supplenza è in un giorno fuori presenza
        giorni_pres = getattr(doc, 'giorni_presenza_list', [])
        multi_sede  = getattr(doc, 'multi_sede', False)
        fuori_sede  = multi_sede and bool(giorni_pres) and (giorno not in giorni_pres)
        entry = {
            'id':      doc_id,
            'cognome': doc.cognome,
            'nome':    doc.nome or '',
            'materia': doc.materia or '',
            'saldo_min':      saldo_eff,
            'saldo_prev_min': saldo_prev,
            'saldo_label':    saldo_label,
            'docente_classe': docente_della_classe,
            'compresenza': compresenza_con_assente,
            'partner_ids': partner_ids,
            'badge_tipo': badge_tipo,
            'ruolo': getattr(doc, 'ruolo', 'titolare') or 'titolare',
            'multi_sede': multi_sede,
            'altra_scuola': getattr(doc, 'altra_scuola', None) or '',
            'fuori_sede': fuori_sede,
        }

        if slot_ora:
            if slot_ora.tipo_ora == 'potenziamento':
                # Escludi chi è già occupato come sostituto in quell'ora
                # sia su classe reale che su potenziamento
                if doc_id in occupati_ids or doc_id in occupati_pot_ids:
                    pass  # già impiegato — non mostrare
                else:
                    entry['dettaglio'] = 'Potenziamento'
                    entry['docente_classe'] = docente_della_classe
                    gruppo_pot.append(entry)
            elif slot_ora.tipo_ora == 'compresenza':
                # Verifica che il compagno di compresenza sia presente
                from modules.compresenze import compagni_presenti as _cp
                compagni_pres = _cp(doc_id, giorno, ora, slot_ora.classe, data_sel)
                if not compagni_pres:
                    # Compagno assente/indisponibile (BIM, FSL…) → il docente è
                    # effettivamente LIBERO in quell'ora (la compresenza non è attiva)
                    # → trattalo come libero con ora adiacente
                    ore_occupate = {s.ora for s in slots}
                    ha_adiacente = (ora - 1) in ore_occupate or (ora + 1) in ore_occupate
                    if ha_adiacente:
                        entry['dettaglio'] = f'Libero — compresenza inattiva ({slot_ora.classe})'
                        gruppo_adj.append(entry)
                    else:
                        entry['dettaglio'] = f'Libero — compresenza inattiva ({slot_ora.classe})'
                        gruppo_liberi.append(entry)
                else:
                    entry['dettaglio'] = f'Compresenza {slot_ora.classe}'
                    entry['docente_classe'] = docente_della_classe
                    gruppo_comp.append(entry)
            # Se ha lezione propria → non disponibile (già in classe)
        else:
            # Libero in quell'ora — controlla adiacenza
            ore_occupate = {s.ora for s in slots}
            ha_adiacente = (ora - 1) in ore_occupate or (ora + 1) in ore_occupate
            ha_giorno    = len(ore_occupate) > 0

            if ha_giorno and ha_adiacente:
                entry['dettaglio'] = 'Libero (ora adiacente)'
                gruppo_adj.append(entry)
            elif ha_giorno:
                entry['dettaglio'] = 'Libero (no ora adiacente)'
                gruppo_liberi.append(entry)
            # Se non ha nessuna ora nel giorno → non è in servizio → escluso

    # Ordina ogni gruppo per saldo crescente (più debito = priorità)
    for g in [gruppo_pot, gruppo_comp, gruppo_adj, gruppo_liberi]:
        g.sort(key=lambda x: x['saldo_min'])

    # ── Mappa orario completo (tutti i giorni) per il badge "sua classe" ──
    slots_tutti_giorni = OrarioDocente.query.all()
    slots_per_doc_full = {}
    for s in slots_tutti_giorni:
        slots_per_doc_full.setdefault(s.id_docente, []).append(s)

    # Aggiorna docente_della_classe nei gruppi già costruiti usando l'orario completo
    if classe_sup:
        for gruppo in [gruppo_adj, gruppo_liberi, gruppo_pot, gruppo_comp]:
            for entry in gruppo:
                entry['docente_classe'] = any(
                    s.classe == classe_sup
                    for s in slots_per_doc_full.get(entry['id'], [])
                )

    # ── Gruppo docenti liberi per classe fuori aula ─────────
    gruppo_fuori_aula = []
    attivita_oggi = AttivitaFuoriAula.query.filter(
        AttivitaFuoriAula.data_inizio <= data_sel,
        AttivitaFuoriAula.data_fine   >= data_sel,
        AttivitaFuoriAula.stato == 'attiva',
    ).all()

    # classi_fuori_per_ora: {classe: set di ore in cui è fuori}
    classi_fuori_per_ora = {}
    for att in attivita_oggi:
        if att.ricorrenza == 'settimanale':
            if giorno not in att.giorni_sett_list:
                continue
        for c in att.classi:
            if c.classe not in classi_fuori_per_ora:
                classi_fuori_per_ora[c.classe] = set()
            if att.ora_inizio and att.ora_fine:
                classi_fuori_per_ora[c.classe].update(range(att.ora_inizio, att.ora_fine+1))
            else:
                # Tutta la giornata
                classi_fuori_per_ora[c.classe].update(range(1, 10))
    classi_fuori = set(classi_fuori_per_ora.keys())

    # Il gruppo potenziamento usa sempre tipo P — è il ruolo del docente, non la giornata

    if classi_fuori:
        # Per il gruppo fuori aula usa TUTTI i docenti (anche assenti per altre attività)
        # ma escludi solo chi è già occupato come sostituto o indisponibile
        # Escludi chi è assente per motivo reale (non AUTO da attività)
        # Le assenze AUTO significano che il docente è impegnato nell'attività
        # e la sua classe è fuori aula — quindi è un candidato valido per completamento
        # Ma chi ha permesso/malattia/ecc. non è disponibile
        # Assenti reali: tutto giorno O coprono quest'ora
        # (escludi assenze AUTO da attività che sono solo indisponibilità operative)
        assenti_reali_ids = set()
        for a in Assenza.query.filter_by(data=data_sel).filter(
            ~Assenza.note_interne.like('Auto — %')
        ).all():
            if a.ora_inizio is None or a.ora_fine is None:
                assenti_reali_ids.add(a.id_docente)  # tutto giorno
            elif a.ora_inizio <= 1 and a.ora_fine >= 8:
                assenti_reali_ids.add(a.id_docente)  # range 1-9 = tutto giorno
            elif a.ora_inizio <= ora <= a.ora_fine:
                assenti_reali_ids.add(a.id_docente)  # permesso orario ora specifica
        esclusi_fuori = occupati_ids | indisp_ids | assenti_reali_ids
        tutti_incluso_assenti = {
            d.id: d for d in Docente.query.filter_by(attivo=True).all()
            if d.id not in esclusi_fuori and d.id != id_assente
        }
        for doc_id, doc in tutti_incluso_assenti.items():
            slots = slots_per_doc.get(doc_id, [])
            slot_ora = next((s for s in slots if s.ora == ora), None)
            if slot_ora and slot_ora.classe in classi_fuori_per_ora and ora in classi_fuori_per_ora[slot_ora.classe]:
                saldo = saldi.get(doc_id, 0)
                gruppo_fuori_aula.append({
                    'id':      doc_id,
                    'cognome': doc.cognome,
                    'nome':    doc.nome or '',
                    'materia': doc.materia or '',
                    'saldo_min':   saldi_eff.get(doc_id, 0),
                    'saldo_label': _fmt_saldo(saldi_eff.get(doc_id,0)) +
                                   (f' → {_fmt_saldo(saldi_eff.get(doc_id,0)+saldi_prev.get(doc_id,0))}'
                                    if saldi_prev.get(doc_id,0) != 0 else ''),
                    'dettaglio': f'Classe fuori aula ({slot_ora.classe})',
                    'docente_classe': bool(classe_sup) and any(
                        s.classe == classe_sup
                        for s in slots_per_doc_full.get(doc_id, [])
                    ),
                })
        gruppo_fuori_aula.sort(key=lambda x: x['saldo_min'])

    gruppi = []
    if gruppo_fuori_aula:
        gruppi.append({'label': '🏫 Liberi (classe fuori aula)', 'key': 'fuori',
                       'note': 'Tipo supplenza consigliato: C — Completamento, non conta per recupero',
                       'docenti': gruppo_fuori_aula})
    if gruppo_pot:
        gruppi.append({'label': '🟡 Potenziamento', 'key': 'pot',
                       'tipo_chiave': 'potenziamento',
                       'note': 'Tipo supplenza: P — Potenziamento',
                       'docenti': gruppo_pot})
    if gruppo_comp:
        gruppi.append({'label': '🔵 Compresenza disponibile', 'key': 'comp',
                       'note': 'Tipo supplenza consigliato: C — completamento orario',
                       'docenti': gruppo_comp})
    if gruppo_adj:
        gruppi.append({'label': '🟢 Liberi (ora adiacente)', 'key': 'adj',
                       'note': 'Tipo consigliato: R — conta come recupero',
                       'docenti': gruppo_adj})
    if gruppo_liberi:
        gruppi.append({'label': '⚪ Liberi (ora non adiacente)', 'key': 'lib',
                       'note': 'Verificare disponibilità',
                       'docenti': gruppo_liberi})

    return jsonify({
        'gruppi': gruppi,
        'ora': ora,
        'data': data_str,
        'totale_candidati': sum(len(g['docenti']) for g in gruppi)
    })


# ── CAMBIA TIPO INLINE ───────────────────────────────────────
@supplenze_bp.route('/supplenze/<int:id>/cambia-tipo', methods=['POST'])
def cambia_tipo(id):
    from flask import jsonify, request as req
    s = Supplenza.query.get_or_404(id)
    data_in = req.get_json()
    nuovo_tipo = data_in.get('tipo')
    if not nuovo_tipo:
        return jsonify({'ok': False}), 400

    vecchio_tipo = s.tipo

    # Aggiorna movimento banca ore se cambia tra recupero e altro
    if s.id_sostituto:
        MovimentoBancaOre.query.filter_by(id_supplenza=s.id).delete()
        if nuovo_tipo in TIPI_CON_RECUPERO:
            _registra_movimento(s.id_sostituto, s.data, nuovo_tipo, s.id)

    s.tipo = nuovo_tipo
    db.session.commit()
    return jsonify({'ok': True})


# ── HELPERS ───────────────────────────────────────────────────
def _registra_movimento(id_docente, data, tipo, id_supplenza):
    """Crea movimento banca ore — solo per tipo recupero."""
    if tipo not in TIPI_CON_RECUPERO:
        return
    m = MovimentoBancaOre(
        id_docente   = id_docente,
        data         = data,
        minuti       = 60,
        tipo         = f'supplenza_{tipo}',
        descrizione  = f'Supplenza {tipo}',
        id_supplenza = id_supplenza,
    )
    db.session.add(m)

def _fmt_saldo(minuti):
    """Formatta saldo in ore con segno."""
    ore  = abs(minuti) // 60
    mins = abs(minuti) % 60
    segno = '+' if minuti >= 0 else '-'
    if mins:
        return f"{segno}{ore}h{mins:02d}"
    return f"{segno}{ore}h"


@supplenze_bp.route('/supplenze/<int:id>/modifica', methods=['GET', 'POST'])
def modifica(id):
    s = Supplenza.query.get_or_404(id)
    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()

    if request.method == 'POST':
        s.data         = date.fromisoformat(request.form['data'])
        s.ora          = int(request.form['ora'])
        s.classe       = request.form['classe'].strip().upper()
        id_assente     = request.form.get('id_assente') or None
        id_sost        = request.form.get('id_sostituto') or None
        tipo_nuovo     = request.form.get('tipo', s.tipo)
        s.id_assente   = int(id_assente) if id_assente else None
        s.note_display = request.form.get('note_display', '').strip()
        s.note         = request.form.get('note', '').strip()

        # Se cambia sostituto o tipo, ricalcola banca ore
        if s.id_sostituto != (int(id_sost) if id_sost else None) or s.tipo != tipo_nuovo:
            MovimentoBancaOre.query.filter_by(id_supplenza=s.id).delete()
            s.id_sostituto = int(id_sost) if id_sost else None
            s.tipo = tipo_nuovo
            if s.id_sostituto and tipo_nuovo in TIPI_CON_RECUPERO:
                _registra_movimento(s.id_sostituto, s.data, tipo_nuovo, s.id)
            s.stato = 'assegnata' if s.id_sostituto else 'scoperta'
        else:
            s.tipo = tipo_nuovo

        db.session.commit()
        flash('Supplenza aggiornata.', 'success')
        next_url = request.form.get('next') or url_for('dashboard.index', data=s.data.isoformat())
        return redirect(next_url)

    return render_template('modifica_supplenza.html',
        supplenza=s, docenti=docenti,
        ore=ORA_LABEL,
        next=request.args.get('next', ''))
