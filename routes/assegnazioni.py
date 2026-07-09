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
    return sorted(classi)


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

        piano = {c: _ore_piano_per_classe(anno_scol, cc.id, c)
                 for c in classi}
        budget = _budget(anno_scol, cc.id)
        assegnazioni = AssegnazioneDocente.query.filter_by(
            anno_scol=anno_scol, id_classe_concorso=cc.id).all()

        ore_doc_classe = {}
        tot_doc        = {}
        ore_per_classe = {c: 0 for c in classi}

        for a in assegnazioni:
            ore_doc_classe[a.id] = {}
            for ac in a.classi:
                lbl = ac.label_classe
                ore_doc_classe[a.id][lbl] = ac.ore
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
                    ~Docente.id.in_(id_gia_assegnati) if id_gia_assegnati
                    else True)
            .order_by(Docente.cognome).all()
        )

        blocks.append({
            'cc':                 cc,
            'classi':             classi,
            'piano':              piano,
            'budget':             budget,
            'assegnazioni':       assegnazioni,
            'ore_doc_classe':     ore_doc_classe,
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
    aree_data = []
    for area in AREE:
        blocks = _build_area(anno, area)
        if blocks:
            aree_data.append({'nome': area['nome'], 'blocks': blocks})

    from routes.impostazione_anno import _docenti_per_anno
    docenti_anno = _docenti_per_anno(anno)

    return render_template('assegnazioni/index.html',
        anno=anno, anni_disponibili=anni,
        aree_data=aree_data,
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

    import re
    classi_ore = {}
    for key, val in request.form.items():
        if key.startswith('ore_') and val and val != '0':
            try:
                classi_ore[key[4:]] = int(val)
            except ValueError:
                pass

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

    for lbl, ore in classi_ore.items():
        m = re.match(r'(\d)([AB]?)\s+(.+)', lbl)
        if m:
            db.session.add(AssegnazioneClasse(
                id_assegnazione=asgn.id,
                indirizzo=m.group(3).strip(),
                anno_corso=int(m.group(1)),
                sezione=m.group(2) or 'A',
                ore=ore))

    db.session.commit()
    flash(f'Assegnazione {asgn.display_name} salvata.', 'success')
    return redirect(url_for('assegnazioni.index', anno=anno))


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
        flash(f'Nominato: {doc.cognome} {doc.nome}.', 'success')
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
