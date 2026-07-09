"""
Modulo assegnazione nominativa classi → docenti.

Flusso:
  1. Scegli anno scolastico e CC
  2. Vedi piano studi (ore richieste per classe) e budget USR (COI/COE/residue)
  3. Assegna docenti reali o placeholder alle classi
  4. Il sistema verifica in tempo reale:
     - ore docente <= ore_max_effettive
     - somma ore per classe = ore piano studi
     - cattedre usate <= budget organico USR
"""
from flask import (Blueprint, render_template, request,
                   redirect, url_for, flash, jsonify)
from models import db
from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse
from models.docente import Docente
from models.classe_concorso import (ClasseConcorso, CattedraOrganico,
                                    MateriaClasseConcorso)
from models.piano_studi import PianoStudi, ClasseSezione, CalcoloOrganico
from config_anno import get_anno_corrente

assegnazioni_bp = Blueprint('assegnazioni', __name__)

TIPO_DISPLAY = {
    'titolare':    'Titolare',
    'coe_entrata': 'COE (entra da altra scuola)',
    'coe_uscita':  'COE (cede ore ad altra scuola)',
    'supplente':   'Supplente / TD',
    'part_time':   'Part-time',
    'eccedenza':   'Ore in eccedenza',
}


def _budget_cc(anno_scol, id_cc):
    """Legge il budget dall'organico USR di fatto per una CC."""
    # Preferisce 'fatto', fallback su 'diritto'
    for tipo in ('fatto', 'diritto'):
        cat = CattedraOrganico.query.filter_by(
            anno_scol=anno_scol, id_classe_concorso=id_cc, tipo=tipo).first()
        if cat:
            return {
                'n_coi':      cat.n_coi or 0,
                'n_coe':      cat.n_coe or 0,
                'ore_residue': cat.ore_residue or 0,
                'n_docenti':  cat.n_docenti or 0,
                'fonte':      tipo,
            }
    return {'n_coi': 0, 'n_coe': 0, 'ore_residue': 0, 'n_docenti': 0, 'fonte': None}


def _stato_assegnazioni(anno_scol, id_cc):
    """
    Calcola lo stato attuale delle assegnazioni per una CC:
    - ore assegnate per docente
    - ore coperte per classe
    - cattedre usate (COI/COE/supplente)
    - eventuali anomalie
    """
    assegnazioni = AssegnazioneDocente.query.filter_by(
        anno_scol=anno_scol, id_classe_concorso=id_cc).all()

    # Ore totali per docente
    ore_per_doc = {}
    for a in assegnazioni:
        tot = sum(c.ore for c in a.classi)
        ore_per_doc[a.id] = tot

    # Ore coperte per classe (label → ore)
    ore_per_classe = {}
    for a in assegnazioni:
        for c in a.classi:
            lbl = c.label_classe
            ore_per_classe[lbl] = ore_per_classe.get(lbl, 0) + c.ore

    # Cattedre usate
    n_coi_usate = sum(1 for a in assegnazioni if a.tipo == 'titolare'
                      and ore_per_doc[a.id] == 18)
    n_coe_usate = sum(1 for a in assegnazioni if a.tipo in ('coe_entrata', 'coe_uscita'))
    n_supplenti  = sum(1 for a in assegnazioni if a.tipo == 'supplente')

    return {
        'assegnazioni': assegnazioni,
        'ore_per_doc': ore_per_doc,
        'ore_per_classe': ore_per_classe,
        'n_coi_usate': n_coi_usate,
        'n_coe_usate': n_coe_usate,
        'n_supplenti': n_supplenti,
    }


def _anomalie(anno_scol, id_cc, stato, budget, piano_classi):
    """
    Verifica la coerenza delle assegnazioni.
    piano_classi: {label_classe: ore_previste}
    Ritorna lista di dict {tipo, msg, livello ('warning'|'error')}
    """
    anomalie = []
    ore_per_doc = stato['ore_per_doc']
    ore_per_classe = stato['ore_per_classe']

    # 1. Ore docente > massimo consentito
    for a in stato['assegnazioni']:
        ore = ore_per_doc[a.id]
        if a.docente:
            max_ore = a.docente.ore_max_effettive
            if ore > max_ore:
                anomalie.append({
                    'tipo': 'ore_eccesso_docente',
                    'livello': 'error',
                    'msg': (f'{a.display_name}: assegnate {ore}h '
                            f'ma max consentito è {max_ore}h')
                })

    # 2. Ore per classe ≠ ore piano studi
    for lbl, ore_prev in piano_classi.items():
        ore_cop = ore_per_classe.get(lbl, 0)
        if ore_cop < ore_prev:
            anomalie.append({
                'tipo': 'classe_scoperta',
                'livello': 'error',
                'msg': (f'{lbl}: previste {ore_prev}h, '
                        f'coperte solo {ore_cop}h '
                        f'({ore_prev - ore_cop}h mancanti)')
            })
        elif ore_cop > ore_prev:
            anomalie.append({
                'tipo': 'classe_sovraccop',
                'livello': 'error',
                'msg': (f'{lbl}: previste {ore_prev}h, '
                        f'assegnate {ore_cop}h '
                        f'({ore_cop - ore_prev}h in eccesso)')
            })

    # 3. COI usate > budget
    if stato['n_coi_usate'] > budget['n_coi']:
        anomalie.append({
            'tipo': 'coi_eccesso',
            'livello': 'error',
            'msg': (f'COI: usate {stato["n_coi_usate"]} '
                    f'ma budget USR è {budget["n_coi"]}')
        })

    # 4. COE usate > budget
    if stato['n_coe_usate'] > budget['n_coe']:
        anomalie.append({
            'tipo': 'coe_eccesso',
            'livello': 'warning',
            'msg': (f'COE: usate {stato["n_coe_usate"]} '
                    f'ma budget USR è {budget["n_coe"]}')
        })

    return anomalie


@assegnazioni_bp.route('/assegnazioni')
def index():
    """Hub: scelta anno e CC."""
    anno = request.args.get('anno', get_anno_corrente())

    # CC con ore nel calcolo organico per quell'anno
    cc_list = (ClasseConcorso.query
               .join(CalcoloOrganico,
                     (CalcoloOrganico.id_classe_concorso == ClasseConcorso.id) &
                     (CalcoloOrganico.anno_scol == anno))
               .filter(CalcoloOrganico.ore_totali_calcolate > 0)
               .order_by(ClasseConcorso.codice).all())

    # Per ogni CC: n. assegnazioni già presenti e stato completamento
    stato_cc = {}
    for cc in cc_list:
        n_asgn = AssegnazioneDocente.query.filter_by(
            anno_scol=anno, id_classe_concorso=cc.id).count()
        budget = _budget_cc(anno, cc.id)
        stato_cc[cc.id] = {
            'n_assegnazioni': n_asgn,
            'budget': budget,
        }

    anni_disponibili = sorted(set(
        r.anno_scol for r in CalcoloOrganico.query.all()
    ), reverse=True)
    if anno not in anni_disponibili:
        anni_disponibili.insert(0, anno)

    return render_template('assegnazioni/index.html',
        anno=anno, cc_list=cc_list,
        stato_cc=stato_cc, anni_disponibili=anni_disponibili)


@assegnazioni_bp.route('/assegnazioni/cc/<int:cc_id>')
def per_cc(cc_id):
    """Vista principale: assegnazioni per una CC."""
    anno = request.args.get('anno', get_anno_corrente())
    cc   = ClasseConcorso.query.get_or_404(cc_id)

    # Piano studi: ore per ogni classe attiva per questa CC
    righe_piano = (PianoStudi.query
                   .filter_by(anno_scol=anno, id_classe_concorso=cc_id)
                   .filter(PianoStudi.compresenza == False)
                   .all())

    # Classi attive con ore in piano studi
    piano_classi = {}  # {label_classe: ore}
    for p in righe_piano:
        sezioni = ClasseSezione.query.filter_by(
            anno_scol=anno, indirizzo=p.indirizzo,
            anno_corso=p.anno_corso, attiva=True).all()
        for s in sezioni:
            lbl = f'{s.anno_corso}{s.sezione} {s.indirizzo}'
            piano_classi[lbl] = p.ore_settimanali

    # Budget organico USR
    budget = _budget_cc(anno, cc_id)

    # Stato assegnazioni correnti
    stato = _stato_assegnazioni(anno, cc_id)

    # Anomalie
    anomalie = _anomalie(anno, cc_id, stato, budget, piano_classi)

    # Docenti disponibili per questa CC (TI + TD con anno_scol_inizio)
    from routes.impostazione_anno import _docenti_per_anno
    tutti_docenti = _docenti_per_anno(anno)
    # Filtra per CC collegata
    docenti_cc = [d for d in tutti_docenti
                  if any(a.id_classe_concorso == cc_id
                         for a in d.abilitazioni)]
    # Più quelli non ancora collegati (per flessibilità)
    docenti_altri = [d for d in tutti_docenti
                     if d not in docenti_cc]

    # CC alternative per placeholder (da MateriaClasseConcorso)
    # Raggruppa per materia: {id_materia: [cc1, cc2]}
    materie_cc = {}
    for p in righe_piano:
        if p.id_materia:
            opzioni = MateriaClasseConcorso.query.filter_by(
                id_materia=p.id_materia).all()
            if len(opzioni) > 1:
                materie_cc[p.id_materia] = [
                    {'id': o.id_classe_concorso,
                     'codice': o.classe_concorso.codice}
                    for o in opzioni]

    classi_ordinate = sorted(piano_classi.keys())

    return render_template('assegnazioni/per_cc.html',
        anno=anno, cc=cc,
        piano_classi=piano_classi,
        classi_ordinate=classi_ordinate,
        budget=budget,
        stato=stato,
        anomalie=anomalie,
        docenti_cc=docenti_cc,
        docenti_altri=docenti_altri,
        tipo_display=TIPO_DISPLAY,
        materie_cc=materie_cc)


@assegnazioni_bp.route('/assegnazioni/salva', methods=['POST'])
def salva():
    """Crea o aggiorna un'assegnazione docente."""
    anno   = request.form.get('anno_scol', get_anno_corrente())
    cc_id  = int(request.form.get('id_cc'))
    tipo   = request.form.get('tipo', 'titolare')
    note   = request.form.get('note', '').strip() or None

    id_doc  = request.form.get('id_docente')
    id_doc  = int(id_doc) if id_doc and id_doc.isdigit() else None
    placeholder = request.form.get('nome_placeholder', '').strip() or None

    if not id_doc and not placeholder:
        flash('Seleziona un docente o inserisci un nome placeholder.', 'danger')
        return redirect(url_for('assegnazioni.per_cc', cc_id=cc_id, anno=anno))

    # Raccoglie le ore per classe dal form
    classi_ore = {}
    for key, val in request.form.items():
        if key.startswith('ore_') and val and val != '0':
            lbl = key[4:]  # es. "ore_1A AFM" → "1A AFM"
            try:
                classi_ore[lbl] = int(val)
            except ValueError:
                pass

    if not classi_ore:
        flash('Inserisci almeno un\'ora su una classe.', 'warning')
        return redirect(url_for('assegnazioni.per_cc', cc_id=cc_id, anno=anno))

    # Verifica ore max docente
    if id_doc:
        doc = db.session.get(Docente, id_doc)
        tot_nuove = sum(classi_ore.values())
        # Somma le ore già assegnate in altre CC
        ore_gia = sum(
            sum(c.ore for c in a.classi)
            for a in AssegnazioneDocente.query.filter_by(
                anno_scol=anno, id_docente=id_doc).all()
        )
        if ore_gia + tot_nuove > doc.ore_max_effettive:
            flash(
                f'{doc.cognome} {doc.nome}: '
                f'ore totali ({ore_gia + tot_nuove}h) superano '
                f'il massimo consentito ({doc.ore_max_effettive}h).',
                'danger')
            return redirect(url_for('assegnazioni.per_cc', cc_id=cc_id, anno=anno))

    # Crea l'assegnazione
    asgn = AssegnazioneDocente(
        anno_scol=anno, id_classe_concorso=cc_id,
        id_docente=id_doc, nome_placeholder=placeholder,
        tipo=tipo, note=note)
    db.session.add(asgn)
    db.session.flush()  # ottieni l'id

    for lbl, ore in classi_ore.items():
        # Parsa "1A AFM" → anno_corso=1, sezione='A', indirizzo='AFM'
        import re
        m = re.match(r'(\d)([AB]?)\s+(.+)', lbl)
        if m:
            db.session.add(AssegnazioneClasse(
                id_assegnazione=asgn.id,
                indirizzo=m.group(3).strip(),
                anno_corso=int(m.group(1)),
                sezione=m.group(2) or 'A',
                ore=ore))

    db.session.commit()
    nome = asgn.display_name
    flash(f'Assegnazione {nome} salvata.', 'success')
    return redirect(url_for('assegnazioni.per_cc', cc_id=cc_id, anno=anno))


@assegnazioni_bp.route('/assegnazioni/<int:asgn_id>/elimina', methods=['POST'])
def elimina(asgn_id):
    asgn = db.session.get(AssegnazioneDocente, asgn_id)
    if not asgn:
        flash('Assegnazione non trovata.', 'danger')
        return redirect(url_for('assegnazioni.index'))
    cc_id = asgn.id_classe_concorso
    anno  = asgn.anno_scol
    nome  = asgn.display_name
    db.session.delete(asgn)
    db.session.commit()
    flash(f'Assegnazione {nome} eliminata.', 'warning')
    return redirect(url_for('assegnazioni.per_cc', cc_id=cc_id, anno=anno))


@assegnazioni_bp.route('/assegnazioni/<int:asgn_id>/nomina', methods=['POST'])
def nomina(asgn_id):
    """Sostituisce un placeholder con un docente reale."""
    asgn   = db.session.get(AssegnazioneDocente, asgn_id)
    if not asgn:
        return jsonify(ok=False, msg='Non trovata')
    id_doc = request.form.get('id_docente', type=int)
    if not id_doc:
        flash('Seleziona un docente.', 'danger')
        return redirect(url_for('assegnazioni.per_cc',
                                cc_id=asgn.id_classe_concorso,
                                anno=asgn.anno_scol))
    doc = db.session.get(Docente, id_doc)

    # Verifica ore max
    tot_ore = sum(c.ore for c in asgn.classi)
    ore_gia_altre = sum(
        sum(c.ore for c in a.classi)
        for a in AssegnazioneDocente.query.filter(
            AssegnazioneDocente.anno_scol == asgn.anno_scol,
            AssegnazioneDocente.id_docente == id_doc,
            AssegnazioneDocente.id != asgn_id).all()
    )
    if ore_gia_altre + tot_ore > doc.ore_max_effettive:
        flash(
            f'{doc.cognome} {doc.nome}: ore totali '
            f'({ore_gia_altre + tot_ore}h) superano il max '
            f'({doc.ore_max_effettive}h).',
            'danger')
    else:
        asgn.id_docente = id_doc
        asgn.nome_placeholder = None
        db.session.commit()
        flash(f'Placeholder sostituito con {doc.cognome} {doc.nome}.', 'success')

    return redirect(url_for('assegnazioni.per_cc',
                            cc_id=asgn.id_classe_concorso,
                            anno=asgn.anno_scol))


@assegnazioni_bp.route('/assegnazioni/api/verifica', methods=['POST'])
def api_verifica():
    """Verifica in tempo reale (chiamata AJAX durante la compilazione)."""
    data   = request.get_json(force=True)
    anno   = data.get('anno_scol', get_anno_corrente())
    cc_id  = int(data.get('id_cc', 0))
    id_doc = data.get('id_docente')
    classi_ore = data.get('classi_ore', {})  # {label: ore}

    avvisi = []

    # Verifica ore max docente
    if id_doc:
        doc = db.session.get(Docente, int(id_doc))
        if doc:
            tot_nuove = sum(classi_ore.values())
            ore_gia = sum(
                sum(c.ore for c in a.classi)
                for a in AssegnazioneDocente.query.filter_by(
                    anno_scol=anno, id_docente=int(id_doc)).all()
            )
            tot = ore_gia + tot_nuove
            max_ore = doc.ore_max_effettive
            if tot > max_ore:
                avvisi.append({
                    'livello': 'error',
                    'msg': f'Totale ore {tot}h supera il massimo {max_ore}h'
                })
            elif tot == max_ore:
                avvisi.append({
                    'livello': 'ok',
                    'msg': f'Cattedra completa: {tot}h / {max_ore}h'
                })
            else:
                avvisi.append({
                    'livello': 'info',
                    'msg': f'{tot}h / {max_ore}h — mancano {max_ore - tot}h'
                })

    return jsonify(avvisi=avvisi)
