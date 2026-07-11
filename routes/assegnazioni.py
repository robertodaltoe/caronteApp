"""
Modulo assegnazione nominativa classi → docenti.
Vista per area disciplinare, identica alla struttura del file ASSEGNAZIONI CLASSI.
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


def _sync_docente_materie(id_docente, asgn, anno_scol):
    """Crea DocenteMateria per le materie dell'assegnazione, se non esistono."""
    from models.materia import DocenteMateria

    materie_ids = {ac.id_materia for ac in asgn.classi if ac.id_materia}
    if not materie_ids:
        return

    for id_mat in materie_ids:
        esiste = DocenteMateria.query.filter_by(
            id_docente=id_docente,
            id_materia=id_mat,
            anno_scol=anno_scol).first()
        if not esiste:
            db.session.add(DocenteMateria(
                id_docente=id_docente,
                id_materia=id_mat,
                anno_scol=anno_scol))
    db.session.commit()

# ── Aree disciplinari e CC (dal file ASSEGNAZIONI CLASSI) ─────────────
AREE = [
    {'nome': 'Area Umanistica',
     'cc':   ['A-11', 'A-12', 'A-18', 'A-19']},
    {'nome': 'Matematica e Scienze',
     'cc':   ['A-20', 'A-26', 'A-27', 'A-34', 'A-41', 'A-47', 'A-50']},
    {'nome': 'Tecnici Geo/Cost',
     'cc':   ['A-37', 'A-51', 'B-14', 'B-17']},
    {'nome': 'Lingue',
     'cc':   ['A-22-ING', 'A-22-TED', 'A-22-SPA',
               'B-02-ING', 'B-02-TED', 'B-02-SPA']},
    {'nome': 'Economia e Sc. Giuridiche',
     'cc':   ['A-45', 'A-46']},
    {'nome': "Storia dell'Arte",
     'cc':   ['A-01']},
    {'nome': 'Motorie e Sportive',
     'cc':   ['A-48']},
    {'nome': 'Religione',
     'cc':   ['IRC']},
]

TIPO_DISPLAY = {
    'titolare':    'TI',
    'coe_entrata': 'COE ←',
    'coe_uscita':  'COE →',
    'supplente':   'Supp.',
    'part_time':   'PT',
    'eccedenza':   '+ore',
}


def _anno_default():
    anni = sorted({r.anno_scol for r in CalcoloOrganico.query.all()}, reverse=True)
    return anni[0] if anni else get_anno_corrente()


def _classi_per_cc(anno_scol, cc_id):
    """
    Restituisce lista ordinata di label classe (es. '1A AFM')
    per cui il piano studi prevede ore in quella CC (non compresenza).
    """
    righe = (PianoStudi.query
             .filter_by(anno_scol=anno_scol,
                        id_classe_concorso=cc_id,
                        compresenza=False)
             .all())
    classi = []
    for p in righe:
        sezioni = ClasseSezione.query.filter_by(
            anno_scol=anno_scol, indirizzo=p.indirizzo,
            anno_corso=p.anno_corso, attiva=True).all()
        for s in sezioni:
            lbl = f'{p.anno_corso}{s.sezione} {p.indirizzo}'
            if lbl not in classi:
                classi.append(lbl)
    import re as _re_sort
    IND_ORDER = {'AFM':0,'RIM':1,'CAT':2,'LLI':3,'LSC':4,'LSP':5,'LSU':6,'SOS':7}
    def _sort_key(lbl):
        m = _re_sort.match(r'(\d+)([AB]?)\s+(.+)', lbl)
        if m:
            ind = m.group(3).strip()
            return (IND_ORDER.get(ind, 99), ind, int(m.group(1)), m.group(2))
        return (99, lbl, 0, '')
    return sorted(classi, key=_sort_key)


def _ore_piano_per_classe(anno_scol, cc_id, label_classe):
    """Ore previste dal piano studi per una classe specifica."""
    import re
    m = re.match(r'(\d)([AB]?)\s+(.+)', label_classe)
    if not m:
        return 0
    anno_corso = int(m.group(1))
    indirizzo  = m.group(3).strip()
    p = PianoStudi.query.filter_by(
        anno_scol=anno_scol, id_classe_concorso=cc_id,
        anno_corso=anno_corso, indirizzo=indirizzo,
        compresenza=False).first()
    return p.ore_settimanali if p else 0


def _budget(anno_scol, cc_id):
    for tipo in ('fatto', 'diritto'):
        cat = CattedraOrganico.query.filter_by(
            anno_scol=anno_scol, id_classe_concorso=cc_id, tipo=tipo).first()
        if cat:
            return cat
    return None


def _build_area(anno_scol, area):
    """
    Costruisce la struttura dati per una area disciplinare.
    Ritorna dict con cc_blocks, ciascuno con:
      - cc: ClasseConcorso
      - classi: [label_classe]
      - piano: {label: ore_prev}
      - budget: CattedraOrganico
      - assegnazioni: [AssegnazioneDocente]
      - ore_doc_classe: {id_asgn: {label: ore}}
      - tot_doc: {id_asgn: int}
      - ore_per_classe: {label: ore_coperte}
    """
    blocks = []
    for codice in area['cc']:
        cc = ClasseConcorso.query.filter_by(codice=codice).first()
        if not cc:
            continue
        classi = _classi_per_cc(anno_scol, cc.id)
        if not classi:
            continue  # CC senza classi attive, salta

        # piano: {label_classe: ore_totali}
        # piano_materie: {label_classe: [{nome, ore, id_materia}]}
        # multi_materia: {label_classe: bool}  — True se >1 materia
        import re as _re
        piano = {}
        piano_materie = {}
        for c in classi:
            m = _re.match(r'(\d+)([AB]?)\s+(.+)', c)
            if not m:
                piano[c] = 0
                piano_materie[c] = []
                continue
            ac = int(m.group(1))
            ind = m.group(3).strip()
            righe_p = PianoStudi.query.filter_by(
                anno_scol=anno_scol, id_classe_concorso=cc.id,
                anno_corso=ac, indirizzo=ind, compresenza=False).all()
            piano[c] = sum(r.ore_settimanali for r in righe_p)
            piano_materie[c] = [
                {'nome': r.nome_materia_locale,
                 'ore':  r.ore_settimanali,
                 'id':   r.id}
                for r in righe_p
            ]
        multi_materia = {c: len(piano_materie[c]) > 1 for c in classi}
        budget = _budget(anno_scol, cc.id)
        assegnazioni = AssegnazioneDocente.query.filter_by(
            anno_scol=anno_scol, id_classe_concorso=cc.id).all()

        # ore_doc_classe[asgn_id][label_classe] = ore totali
        # ore_doc_mat[asgn_id][label_classe][id_materia] = ore per materia
        # ore_per_classe[label_classe] = ore coperte totali
        ore_doc_classe = {}
        ore_doc_mat    = {}
        tot_doc        = {}
        ore_per_classe = {c: 0 for c in classi}

        for a in assegnazioni:
            ore_doc_classe[a.id] = {}
            ore_doc_mat[a.id]    = {}
            for ac in a.classi:
                lbl = ac.label_classe
                ore_doc_classe[a.id][lbl] = (
                    ore_doc_classe[a.id].get(lbl, 0) + ac.ore)
                if lbl not in ore_doc_mat[a.id]:
                    ore_doc_mat[a.id][lbl] = {}
                mat_key = ac.id_materia or 0
                ore_doc_mat[a.id][lbl][mat_key] = (
                    ore_doc_mat[a.id][lbl].get(mat_key, 0) + ac.ore)
                if lbl in ore_per_classe:
                    ore_per_classe[lbl] += ac.ore
            tot_doc[a.id] = sum(ore_doc_classe[a.id].values())

        # Docenti con questa CC già collegata (passo 8) ma non ancora assegnati
        # — vengono mostrati in tabella con 0h come riga "disponibile"
        from models.classe_concorso import DocenteClasseConcorso
        id_gia_assegnati = {a.id_docente for a in assegnazioni if a.id_docente}
        docenti_cc_precaricati = (
            Docente.query
            .join(DocenteClasseConcorso,
                  DocenteClasseConcorso.id_docente == Docente.id)
            .filter(DocenteClasseConcorso.id_classe_concorso == cc.id,
                    Docente.attivo == True,
                    # Escludi chi non è fisicamente presente
                    Docente.status_presenza.notin_(
                        ['aspettativa', 'ap_uscente']),
                    ~Docente.id.in_(id_gia_assegnati) if id_gia_assegnati
                    else True)
            .order_by(Docente.cognome).all()
        )

        blocks.append({
            'cc':                 cc,
            'classi':             classi,
            'piano':              piano,
            'piano_materie':      piano_materie,
            'multi_materia':      multi_materia,
            'budget':             budget,
            'assegnazioni':       assegnazioni,
            'ore_doc_classe':     ore_doc_classe,
            'ore_doc_mat':        ore_doc_mat,
            'tot_doc':            tot_doc,
            'ore_per_classe':     ore_per_classe,
            'docenti_precaricati': docenti_cc_precaricati,
        })
    return blocks


@assegnazioni_bp.route('/assegnazioni')
def index():
    anno = request.args.get('anno', _anno_default())

    # Anni disponibili
    anni = sorted({r.anno_scol for r in CalcoloOrganico.query.all()}, reverse=True)
    if anno not in anni:
        anni.insert(0, anno)

    # Costruisce tutte le aree
    import re as _re_ind2
    aree_data = []
    for area in AREE:
        blocks = _build_area(anno, area)
        if blocks:
            inds = set()
            for blk in blocks:
                for lbl in blk['classi']:
                    m = _re_ind2.match(r'\d+[AB]?\s+(.+)', lbl)
                    if m:
                        inds.add(m.group(1).strip())
            aree_data.append({
                'nome': area['nome'],
                'blocks': blocks,
                'indirizzi': sorted(inds),
            })

    from routes.impostazione_anno import _docenti_per_anno
    # Per le assegnazioni: solo docenti fisicamente presenti a scuola.
    # Escludi aspettativa e AP uscenti (non insegnano qui).
    _tutti = _docenti_per_anno(anno)
    docenti_anno = [
        d for d in _tutti
        if d.status_presenza not in ('aspettativa', 'ap_uscente')
    ]

    _IND_ORD = {'AFM':0,'RIM':1,'CAT':2,'LLI':3,'LSC':4,'LSP':5,'LSU':6,'SOS':7}
    indirizzi_attivi = sorted(
        {s.indirizzo for s in ClasseSezione.query.filter_by(anno_scol=anno, attiva=True).all()},
        key=lambda x: _IND_ORD.get(x, 99))

    return render_template('assegnazioni/index.html',
        anno=anno, anni_disponibili=anni,
        aree_data=aree_data,
        indirizzi_attivi=indirizzi_attivi,
        docenti_anno=docenti_anno,
        tipo_display=TIPO_DISPLAY)


@assegnazioni_bp.route('/assegnazioni/salva', methods=['POST'])
def salva():
    anno      = request.form.get('anno_scol', get_anno_corrente())
    cc_id     = int(request.form.get('id_cc'))
    tipo      = request.form.get('tipo', 'titolare')
    note      = request.form.get('note', '').strip() or None
    id_doc    = request.form.get('id_docente')
    id_doc    = int(id_doc) if id_doc and id_doc.isdigit() else None
    placeholder = request.form.get('nome_placeholder', '').strip() or None

    if not id_doc and not placeholder:
        flash('Seleziona un docente o inserisci un nome placeholder.', 'danger')
        return redirect(url_for('assegnazioni.index', anno=anno))

    import re as _re2
    # Raccoglie ore dal form:
    # formato singolo:  ore_{label_classe}
    # formato materia:  ore_{label_classe}_{id_mat}
    classi_ore = {}  # {(lbl, id_mat_or_None): ore}
    for key, val in request.form.items():
        if not key.startswith('ore_') or not val or val == '0':
            continue
        try:
            ore_v = int(val)
        except ValueError:
            continue
        if ore_v <= 0:
            continue
        raw = key[4:]
        idx_ = raw.rfind('_')
        if idx_ > 0:
            try:
                id_mat = int(raw[idx_+1:])
                lbl = raw[:idx_]
            except ValueError:
                id_mat = None
                lbl = raw
        else:
            id_mat = None
            lbl = raw
        classi_ore[(lbl, id_mat)] = ore_v

    if not classi_ore:
        flash('Inserisci almeno un\'ora su una classe.', 'warning')
        return redirect(url_for('assegnazioni.index', anno=anno))

    # Verifica ore max
    if id_doc:
        doc = db.session.get(Docente, id_doc)
        tot_nuove = sum(classi_ore.values())
        ore_gia = sum(
            sum(c.ore for c in a.classi)
            for a in AssegnazioneDocente.query.filter_by(
                anno_scol=anno, id_docente=id_doc).all())
        if ore_gia + tot_nuove > doc.ore_max_effettive:
            flash(
                f'{doc.cognome} {doc.nome}: '
                f'ore totali ({ore_gia + tot_nuove}h) superano '
                f'il massimo ({doc.ore_max_effettive}h).', 'danger')
            return redirect(url_for('assegnazioni.index', anno=anno))

    asgn = AssegnazioneDocente(
        anno_scol=anno, id_classe_concorso=cc_id,
        id_docente=id_doc, nome_placeholder=placeholder,
        tipo=tipo, note=note)
    db.session.add(asgn)
    db.session.flush()

    for (lbl, id_mat), ore in classi_ore.items():
        m = _re2.match(r'(\d+)([AB]?)\s+(.+)', lbl)
        if m:
            db.session.add(AssegnazioneClasse(
                id_assegnazione=asgn.id,
                indirizzo=m.group(3).strip(),
                anno_corso=int(m.group(1)),
                sezione=m.group(2) or 'A',
                ore=ore,
                id_materia=id_mat))

    db.session.commit()

    # Sincronizza DocenteMateria se è un docente reale
    if id_doc:
        _sync_docente_materie(id_doc, asgn, anno)

    flash(f'Assegnazione {asgn.display_name} salvata.', 'success')
    return redirect(url_for('assegnazioni.index', anno=anno))


@assegnazioni_bp.route('/assegnazioni/crea-e-assegna', methods=['POST'])
def crea_e_assegna():
    """AJAX: crea AssegnazioneDocente per un precaricato e restituisce l'id."""
    from flask import jsonify
    data  = request.json or {}
    anno  = data.get('anno')
    cc_id = int(data.get('cc_id', 0))
    id_doc= int(data.get('id_doc', 0))

    if not all([anno, cc_id, id_doc]):
        return jsonify(ok=False, msg='Parametri mancanti'), 400

    # Cerca assegnazione esistente
    asgn = AssegnazioneDocente.query.filter_by(
        anno_scol=anno, id_classe_concorso=cc_id,
        id_docente=id_doc).first()

    if not asgn:
        asgn = AssegnazioneDocente(
            anno_scol=anno, id_classe_concorso=cc_id,
            id_docente=id_doc, tipo='TI')
        db.session.add(asgn)
        db.session.commit()

    return jsonify(ok=True, asgn_id=asgn.id)


@assegnazioni_bp.route('/assegnazioni/<int:asgn_id>/aggiorna-ore', methods=['POST'])
def aggiorna_ore(asgn_id):
    """AJAX: aggiorna/crea ore per una specifica classe+materia di un'assegnazione."""
    from flask import jsonify
    import re as _re3
    asgn = db.session.get(AssegnazioneDocente, asgn_id)
    if not asgn:
        return jsonify(ok=False, msg='Assegnazione non trovata'), 404

    lbl      = request.json.get('classe', '')
    id_mat   = request.json.get('id_materia')  # può essere None
    ore      = request.json.get('ore', 0)

    m = _re3.match(r'(\d+)([AB]?)\s+(.+)', lbl)
    if not m:
        return jsonify(ok=False, msg='Label classe non valida'), 400

    anno_corso = int(m.group(1))
    sezione    = m.group(2) or 'A'
    indirizzo  = m.group(3).strip()

    # Cerca riga esistente
    filtro = dict(id_assegnazione=asgn_id, indirizzo=indirizzo,
                  anno_corso=anno_corso, sezione=sezione, id_materia=id_mat)
    ac = AssegnazioneClasse.query.filter_by(**filtro).first()

    if ore == 0 or ore is None:
        if ac:
            db.session.delete(ac)
            db.session.commit()
        return jsonify(ok=True, ore=0, tot=_tot_ore(asgn_id))

    if ac:
        ac.ore = ore
    else:
        ac = AssegnazioneClasse(ore=ore, **filtro)
        db.session.add(ac)
    db.session.commit()

    # Sincronizza DocenteMateria se docente reale
    if asgn.id_docente and id_mat:
        _sync_docente_materie(asgn.id_docente, asgn, asgn.anno_scol)

    tot = _tot_ore(asgn_id)

    # Controllo ore max docente
    warn_docente = False
    if asgn.docente:
        ore_max = asgn.docente.ore_max_effettive_per_anno(asgn.anno_scol)
        warn_docente = tot > ore_max

    # Controllo ore previste per classe e per materia
    warn_classe  = False
    warn_materia = False
    from models.piano_studi import PianoStudi
    ac_rows = AssegnazioneClasse.query.filter_by(id_assegnazione=asgn_id).all()
    for ac_row in ac_rows:
        # Ore totali previste per questa CC in questa classe
        ps_all = PianoStudi.query.filter_by(
            anno_scol=asgn.anno_scol,
            id_classe_concorso=asgn.id_classe_concorso,
            indirizzo=ac_row.indirizzo,
            anno_corso=ac_row.anno_corso).all()
        ore_previste_tot = sum(p.ore_settimanali for p in ps_all if not p.compresenza)

        # Ore assegnate a questa classe da questo docente (tutte le materie)
        ore_asgn_classe = sum(
            r.ore for r in ac_rows
            if r.indirizzo==ac_row.indirizzo
            and r.anno_corso==ac_row.anno_corso
            and r.sezione==ac_row.sezione)
        if ore_asgn_classe > ore_previste_tot:
            warn_classe = True

        # Controllo per singola materia (se id_materia valorizzato)
        if ac_row.id_materia:
            ps_mat = next((p for p in ps_all
                           if p.id_materia == ac_row.id_materia), None)
            if ps_mat:
                # Ore assegnate a TUTTI i docenti per questa materia+classe
                from models.assegnazione import AssegnazioneDocente as AD2
                ore_mat_totali = 0
                for a2 in AD2.query.filter_by(
                        anno_scol=asgn.anno_scol,
                        id_classe_concorso=asgn.id_classe_concorso).all():
                    for r2 in AssegnazioneClasse.query.filter_by(
                            id_assegnazione=a2.id,
                            indirizzo=ac_row.indirizzo,
                            anno_corso=ac_row.anno_corso,
                            sezione=ac_row.sezione,
                            id_materia=ac_row.id_materia).all():
                        ore_mat_totali += r2.ore
                if ore_mat_totali > ps_mat.ore_settimanali:
                    warn_materia = True

    return jsonify(ok=True, ore=ore, tot=tot,
                   warn_docente=warn_docente,
                   warn_classe=warn_classe,
                   warn_materia=warn_materia)


def _tot_ore(asgn_id):
    return sum(ac.ore for ac in AssegnazioneClasse.query.filter_by(
        id_assegnazione=asgn_id).all())


@assegnazioni_bp.route('/assegnazioni/<int:asgn_id>/elimina', methods=['POST'])
def elimina(asgn_id):
    asgn = db.session.get(AssegnazioneDocente, asgn_id)
    if not asgn:
        flash('Non trovata.', 'danger')
        return redirect(url_for('assegnazioni.index'))
    anno = asgn.anno_scol
    nome = asgn.display_name
    db.session.delete(asgn)
    db.session.commit()
    flash(f'Assegnazione {nome} eliminata.', 'warning')
    return redirect(url_for('assegnazioni.index', anno=anno))


@assegnazioni_bp.route('/assegnazioni/<int:asgn_id>/nomina', methods=['POST'])
def nomina(asgn_id):
    asgn   = db.session.get(AssegnazioneDocente, asgn_id)
    id_doc = request.form.get('id_docente', type=int)
    if not asgn or not id_doc:
        flash('Dati mancanti.', 'danger')
        return redirect(url_for('assegnazioni.index'))
    doc = db.session.get(Docente, id_doc)
    tot = sum(c.ore for c in asgn.classi)
    ore_gia = sum(
        sum(c.ore for c in a.classi)
        for a in AssegnazioneDocente.query.filter(
            AssegnazioneDocente.anno_scol == asgn.anno_scol,
            AssegnazioneDocente.id_docente == id_doc,
            AssegnazioneDocente.id != asgn_id).all())
    if ore_gia + tot > doc.ore_max_effettive:
        flash(f'{doc.cognome} {doc.nome}: ore eccessive '
              f'({ore_gia + tot}h > {doc.ore_max_effettive}h).', 'danger')
    else:
        asgn.id_docente = id_doc
        asgn.nome_placeholder = None
        db.session.commit()
        # Il docente nominato eredita le materie del placeholder
        _sync_docente_materie(id_doc, asgn, asgn.anno_scol)
        flash(f'Nominato: {doc.cognome} {doc.nome} — materie sincronizzate.', 'success')
    return redirect(url_for('assegnazioni.index', anno=asgn.anno_scol))


@assegnazioni_bp.route('/assegnazioni/api/verifica', methods=['POST'])
def api_verifica():
    data      = request.get_json(force=True)
    anno      = data.get('anno_scol', get_anno_corrente())
    id_doc    = data.get('id_docente')
    classi_ore = data.get('classi_ore', {})
    avvisi    = []
    if id_doc:
        doc = db.session.get(Docente, int(id_doc))
        if doc:
            tot_nuove = sum(classi_ore.values())
            ore_gia   = sum(
                sum(c.ore for c in a.classi)
                for a in AssegnazioneDocente.query.filter_by(
                    anno_scol=anno, id_docente=int(id_doc)).all())
            tot = ore_gia + tot_nuove
            max_ore = doc.ore_max_effettive
            if tot > max_ore:
                avvisi.append({'livello': 'error',
                               'msg': f'⚠ {tot}h / {max_ore}h — supera il massimo'})
            elif tot == max_ore:
                avvisi.append({'livello': 'ok',
                               'msg': f'✓ Cattedra completa: {tot}h / {max_ore}h'})
            else:
                avvisi.append({'livello': 'info',
                               'msg': f'{tot}h / {max_ore}h — mancano {max_ore - tot}h'})
    return jsonify(avvisi=avvisi)
