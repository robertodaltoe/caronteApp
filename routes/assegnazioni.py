"""
Modulo assegnazione nominativa classi →︎ docenti.
Vista per area disciplinare, identica alla struttura del file ASSEGNAZIONI CLASSI.
"""
from flask import (Blueprint, render_template, request,
                   redirect, url_for, flash, jsonify)
from models import db
from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse, CattedraPotenziamento
from models.docente import Docente
from models.classe_concorso import (ClasseConcorso, CattedraOrganico,
                                    MateriaClasseConcorso)
from models.piano_studi import PianoStudi, ClasseSezione, CalcoloOrganico
from config_anno import get_anno_corrente

assegnazioni_bp = Blueprint('assegnazioni', __name__)


def _righe_piano(anno_scol, cc_id, anno_corso=None, indirizzo=None):
    """
    Righe di PianoStudi per una classe di concorso (opzionalmente filtrate
    per anno_corso/indirizzo), con priorità alle ore "proprie" (non di
    compresenza). Se per quella CC esistono SOLO righe di compresenza —
    es. B-02 (conversazione lingue), B-03/B-12/B-14/B-16/B-17 (laboratori
    tecnici): non hanno mai un titolare "principale" con ore proprie,
    esistono solo come ore di compresenza affiancate a un'altra CC — usa
    quelle. Altrimenti queste CC non avrebbero mai nessuna classe/ora da
    mostrare e sparirebbero dalla pagina Assegnazioni nonostante siano
    nel piano di studi (bug segnalato per B-02/B-03/B-12/B-14/B-16/B-17).
    """
    base = PianoStudi.query.filter_by(anno_scol=anno_scol, id_classe_concorso=cc_id)
    if anno_corso is not None:
        base = base.filter_by(anno_corso=anno_corso)
    if indirizzo is not None:
        base = base.filter_by(indirizzo=indirizzo)
    righe = base.filter_by(compresenza=False).all()
    if not righe:
        righe = base.filter_by(compresenza=True).all()
    return righe


def _resolve_id_materia(anno_scol, cc_id, label):
    """
    Se la classe ha un'unica materia associata a questa classe di
    concorso nel piano studi, ritorna il suo id — è il caso "materia
    singola" del form di Assegnazioni, che non chiede esplicitamente
    quale materia (non c'è ambiguità) e quindi non la passa nel campo
    ore_<classe>. Prima di questa funzione, in quel caso
    AssegnazioneClasse.id_materia restava NULL, con due conseguenze:
    _sync_docente_materie() non aveva modo di sapere quale materia
    sincronizzare in DocenteMateria, e l'export "scheda classe" mostrava
    il tipo di contratto al posto del nome materia. Se le materie sono
    più di una (caso multi-materia, già gestito esplicitamente dal form)
    o zero, ritorna None senza indovinare.
    """
    import re as _re5
    m = _re5.match(r'(\d+)([AB]?)\s+(.+)', label)
    if not m:
        return None
    anno_corso = int(m.group(1))
    indirizzo  = m.group(3).strip()
    righe = _righe_piano(anno_scol, cc_id, anno_corso, indirizzo)
    if len(righe) == 1:
        # id_materia, non id: AssegnazioneClasse.id_materia è FK verso la
        # tabella Materia, non verso PianoStudi (sono due entità diverse
        # con id indipendenti — vedi nota in _build_area più sotto).
        return righe[0].id_materia
    return None


def _sync_docente_materie(id_docente, asgn, anno_scol):
    """
    Crea DocenteMateria per le materie dell'assegnazione, se non
    esistono già (origine='auto' — vedi _pulisci_docente_materie_orfane
    per la pulizia simmetrica quando le ore vengono tolte). Non tocca
    mai righe già presenti, nemmeno per cambiarne l'origine: se una
    materia era già stata aggiunta a mano (origine='manuale') resta tale.
    """
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
                anno_scol=anno_scol,
                origine='auto'))
    db.session.commit()


def _pulisci_docente_materie_orfane(id_docente, anno_scol):
    """
    Rimuove da DocenteMateria le materie con origine='auto' che non sono
    più coperte da nessuna AssegnazioneClasse del docente per l'anno
    (es. le ore su quella materia sono state azzerate o l'assegnazione
    è stata eliminata). Le materie con origine='manuale' non vengono mai
    toccate qui: sono una dichiarazione esplicita di chi usa l'app, non
    un derivato delle assegnazioni.
    """
    if not id_docente:
        return
    from models.materia import DocenteMateria

    materie_coperte = {
        ac.id_materia
        for a in AssegnazioneDocente.query.filter_by(
            anno_scol=anno_scol, id_docente=id_docente).all()
        for ac in a.classi if ac.id_materia
    }

    orfane = DocenteMateria.query.filter_by(
        id_docente=id_docente, anno_scol=anno_scol, origine='auto').filter(
        ~DocenteMateria.id_materia.in_(materie_coperte) if materie_coperte
        else True).all()
    for dm in orfane:
        db.session.delete(dm)
    if orfane:
        db.session.commit()

# ── Aree disciplinari e CC (dal file ASSEGNAZIONI CLASSI) ─────────────
AREE = [
    {'nome': 'Area Umanistica',
     'cc':   ['A-11', 'A-12', 'A-18', 'A-19']},
    {'nome': 'Matematica e Scienze',
     'cc':   ['A-20', 'A-26', 'A-27', 'A-34', 'A-41', 'A-47', 'A-50']},
    {'nome': 'Tecnici Geo/Cost',
     'cc':   ['A-37', 'A-51', 'B-03', 'B-12', 'B-14', 'B-16', 'B-17']},
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
    'coe_entrata': 'COE ←︎',
    'coe_uscita':  'COE →︎',
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
    per cui il piano studi prevede ore in quella CC — vedi _righe_piano
    per il fallback sulle CC che esistono solo come compresenza.
    """
    righe = _righe_piano(anno_scol, cc_id)
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
    righe = _righe_piano(anno_scol, cc_id, anno_corso, indirizzo)
    return righe[0].ore_settimanali if righe else 0


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
            righe_p = _righe_piano(anno_scol, cc.id, ac, ind)
            piano[c] = sum(r.ore_settimanali for r in righe_p)
            # 'id' qui DEVE essere r.id_materia (la FK verso la tabella
            # Materia, quella che AssegnazioneClasse.id_materia referenzia
            # davvero) — non r.id (la chiave primaria della riga di
            # PianoStudi, un'entità diversa). Erano stati scambiati: il
            # form multi-materia mandava r.id come "id_materia" nel campo
            # ore_<classe>_<id>, che veniva salvato così com'è in
            # AssegnazioneClasse.id_materia — puntando quindi a una
            # materia sbagliata ogni volta che l'id numerico della riga
            # di piano studi coincideva (per caso) con l'id di un'altra
            # materia nella tabella Materia. Vedi DEVLOG Task 19undecies
            # e scripts/backfill_id_materia.py per la correzione dei dati
            # già salvati in modo sbagliato.
            piano_materie[c] = [
                {'nome': r.nome_materia_locale,
                 'ore':  r.ore_settimanali,
                 'id':   r.id_materia}
                for r in righe_p if r.id_materia
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

        # Potenziamento per questa CC
        pot = CattedraPotenziamento.query.filter_by(
            anno_scol=anno_scol, id_classe_concorso=cc.id).first()
        ore_pot_doc = {}
        if pot:
            for a in assegnazioni:
                ac_pot = AssegnazioneClasse.query.filter_by(
                    id_assegnazione=a.id,
                    indirizzo='POT', anno_corso=0, sezione='A').first()
                ore_pot_doc[a.id] = ac_pot.ore if ac_pot else 0
            for d in docenti_cc_precaricati:
                a_pre = AssegnazioneDocente.query.filter_by(
                    anno_scol=anno_scol, id_classe_concorso=cc.id,
                    id_docente=d.id).first()
                if a_pre:
                    ac_pot = AssegnazioneClasse.query.filter_by(
                        id_assegnazione=a_pre.id,
                        indirizzo='POT', anno_corso=0, sezione='A').first()
                    ore_pot_doc[d.id] = ac_pot.ore if ac_pot else 0

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
            'potenziamento':      pot,
            'ore_pot_doc':        ore_pot_doc,
            'ore_pot_totali':     sum(ore_pot_doc.values()),
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

    if not classi_ore and not placeholder:
        flash('Inserisci almeno un\'ora su una classe (oppure, se è un '
              'placeholder da completare più avanti, inserisci solo il nome).', 'warning')
        return redirect(url_for('assegnazioni.index', anno=anno))
    # I placeholder possono essere inseriti anche senza ore — riga
    # "riservata" da completare quando si conoscono i dettagli, o da
    # nominare direttamente (vedi assegnazioni.nomina) quando arriva
    # il docente reale.

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
            # Caso "materia singola": il form non passa id_mat perché
            # non c'è ambiguità — la risolviamo comunque dal piano studi,
            # invece di lasciare id_materia NULL (vedi _resolve_id_materia).
            if id_mat is None and lbl != '__POT__':
                id_mat = _resolve_id_materia(anno, cc_id, lbl)
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
    ancora = request.form.get('ancora', '')
    url = url_for('assegnazioni.index', anno=anno)
    return redirect(url + ('#area-' + ancora if ancora else ''))


@assegnazioni_bp.route('/assegnazioni/blocco-cc/<int:cc_id>')
def blocco_cc(cc_id):
    """AJAX: restituisce l'HTML aggiornato del blocco CC per una specifica area."""
    from flask import jsonify
    anno = request.args.get('anno', get_anno_corrente())
    from models.classe_concorso import ClasseConcorso
    cc = db.session.get(ClasseConcorso, cc_id)
    if not cc:
        return jsonify(ok=False), 404

    # Trova l'area di questa CC
    area_trovata = None
    for area in AREE:
        if cc.codice in area['cc']:
            area_trovata = area
            break
    if not area_trovata:
        return jsonify(ok=False), 404

    blocks = _build_area(anno, area_trovata)
    blk = next((b for b in blocks if b['cc'].id == cc_id), None)
    if not blk:
        return jsonify(ok=False), 404

    from flask import render_template_string
    # Render del solo blocco CC
    html = render_template('assegnazioni/_blocco_cc.html',
        blk=blk, cc=blk['cc'], classi=blk['classi'], anno=anno,
        TIPO_DISPLAY={})
    return jsonify(ok=True, html=html)


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

    # Gestione speciale per potenziamento
    if lbl == '__POT__':
        anno_corso = 0
        sezione    = 'A'
        indirizzo  = 'POT'
    else:
        m = _re3.match(r'(\d+)([AB]?)\s+(.+)', lbl)
        if not m:
            return jsonify(ok=False, msg='Label classe non valida'), 400
        anno_corso = int(m.group(1))
        sezione    = m.group(2) or 'A'
        indirizzo  = m.group(3).strip()
        # Caso "materia singola": il form non passa id_mat, la risolviamo
        # comunque dal piano studi (vedi _resolve_id_materia) invece di
        # lasciare id_materia NULL sulla riga.
        if id_mat is None:
            id_mat = _resolve_id_materia(asgn.anno_scol, asgn.id_classe_concorso, lbl)

    # Cerca riga esistente
    filtro = dict(id_assegnazione=asgn_id, indirizzo=indirizzo,
                  anno_corso=anno_corso, sezione=sezione, id_materia=id_mat)
    ac = AssegnazioneClasse.query.filter_by(**filtro).first()

    if ore == 0 or ore is None:
        if ac:
            db.session.delete(ac)
            db.session.commit()
            # La materia potrebbe non essere più coperta da nessuna ora
            # di questo docente: ripulisce l'eventuale voce automatica
            # ormai orfana in DocenteMateria (mai quelle manuali).
            if asgn.id_docente:
                _pulisci_docente_materie_orfane(asgn.id_docente, asgn.anno_scol)
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
        # Il potenziamento (indirizzo fittizio 'POT') non è nel piano di
        # studi — non ha senso confrontarlo con PianoStudi (darebbe sempre
        # "0 ore previste" e quindi un falso avviso ad ogni inserimento).
        # Il suo budget è invece CattedraPotenziamento.ore, controllato
        # separatamente più sotto.
        if ac_row.indirizzo == 'POT':
            continue

        # Ore totali previste per questa CC in questa classe (vedi
        # _righe_piano per il fallback sulle CC solo-compresenza)
        ps_all = _righe_piano(asgn.anno_scol, asgn.id_classe_concorso,
                               ac_row.anno_corso, ac_row.indirizzo)
        ore_previste_tot = sum(p.ore_settimanali for p in ps_all)

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
    id_doc = asgn.id_docente
    db.session.delete(asgn)
    db.session.commit()
    if id_doc:
        _pulisci_docente_materie_orfane(id_doc, anno)
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
                               'msg': f'⚠︎ {tot}h / {max_ore}h — supera il massimo'})
            elif tot == max_ore:
                avvisi.append({'livello': 'ok',
                               'msg': f'✓︎ Cattedra completa: {tot}h / {max_ore}h'})
            else:
                avvisi.append({'livello': 'info',
                               'msg': f'{tot}h / {max_ore}h — mancano {max_ore - tot}h'})
    return jsonify(avvisi=avvisi)
