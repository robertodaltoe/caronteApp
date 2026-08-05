"""
Dashboard anno scolastico — vista riepilogativa.
"""
from flask import Blueprint, render_template, request
from models import db
from models.docente import Docente
from models.piano_studi import PianoStudi, ClasseSezione, CalcoloOrganico
from models.classe_concorso import ClasseConcorso, CattedraOrganico, DocenteClasseConcorso
from models.assegnazione import AssegnazioneDocente
from models.incarico import IncaricaDocente, TipoIncarico
from models.materia import Dipartimento
from config_anno import get_anno_corrente

dashboard_anno_bp = Blueprint('dashboard_anno', __name__)


@dashboard_anno_bp.route('/dashboard-anno')
def index():
    anno = request.args.get('anno', get_anno_corrente())

    # ── Classi ────────────────────────────────────────────────────
    classi_attive = ClasseSezione.query.filter_by(anno_scol=anno, attiva=True).all()
    n_classi = len(classi_attive)
    indirizzi = sorted({c.indirizzo for c in classi_attive})

    # ── Docenti ───────────────────────────────────────────────────
    from routes.impostazione_anno import _docenti_per_anno
    docenti = _docenti_per_anno(anno)
    n_docenti = len(docenti)
    n_ti = sum(1 for d in docenti if d.tipo_contratto == 'TI')
    n_td = n_docenti - n_ti
    n_aspettativa = sum(1 for d in docenti if d.status_presenza == 'aspettativa')
    n_ap_uscente  = sum(1 for d in docenti if d.status_presenza == 'ap_uscente')
    n_ap_entrante = sum(1 for d in docenti if d.status_presenza == 'ap_entrante')

    # ── CC senza TI collegati ──────────────────────────────────────
    cc_con_calc = (ClasseConcorso.query
                   .join(CalcoloOrganico,
                         (CalcoloOrganico.id_classe_concorso == ClasseConcorso.id) &
                         (CalcoloOrganico.anno_scol == anno))
                   .filter(CalcoloOrganico.ore_totali_calcolate > 0)
                   .all())
    ids_con_cc = {r.id_classe_concorso
                  for r in DocenteClasseConcorso.query.all()}

    # ── Assegnazioni ───────────────────────────────────────────────
    n_assegnazioni = AssegnazioneDocente.query.filter_by(anno_scol=anno).count()

    # CC con almeno un'assegnazione
    cc_assegnate = {a.id_classe_concorso
                    for a in AssegnazioneDocente.query.filter_by(anno_scol=anno).all()}
    n_cc_totali = len(cc_con_calc)
    n_cc_assegnate = len(cc_assegnate)
    perc_assegnazioni = int(n_cc_assegnate / n_cc_totali * 100) if n_cc_totali else 0

    # ── Incarichi ──────────────────────────────────────────────────
    n_incarichi = IncaricaDocente.query.filter_by(anno_scol=anno).count()

    # Tipi strutturali collegati a classe — quanti ne mancano
    tipo_coord = TipoIncarico.query.filter_by(nome='Coordinatore di classe').first()
    n_coord_assegnati = IncaricaDocente.query.filter_by(
        anno_scol=anno, id_tipo_incarico=tipo_coord.id).count() if tipo_coord else 0
    n_coord_mancanti = max(0, n_classi - n_coord_assegnati)

    tipo_ref = TipoIncarico.query.filter_by(nome='Referente di dipartimento').first()
    n_dip = Dipartimento.query.filter(Dipartimento.sigla != '—').count()
    n_ref_assegnati = IncaricaDocente.query.filter_by(
        anno_scol=anno, id_tipo_incarico=tipo_ref.id).count() if tipo_ref else 0
    n_ref_mancanti = max(0, n_dip - n_ref_assegnati)

    # ── Piano studi ────────────────────────────────────────────────
    n_materie_no_mat = PianoStudi.query.filter(
        PianoStudi.anno_scol == anno,
        PianoStudi.id_materia == None).count()

    # ── Organico: confronto TI vs DOC ─────────────────────────────
    # Preferisce l'organico di fatto (dotazione reale, dopo le
    # iscrizioni) e ricade su quello di diritto solo se il fatto non è
    # ancora stato inserito — stessa precedenza usata in
    # routes/assegnazioni.py::_budget() e nelle pagine di confronto di
    # impostazione_anno.py. Prima filtrava su
    # tipo.in_(['fatto','diritto']) senza ordinamento esplicito: quale
    # dei due risultasse "first()" dipendeva dall'ordine casuale/di
    # inserimento nel DB, non garantiva la preferenza per il fatto.
    confronto_cc = []
    for cc in cc_con_calc:
        cat = None
        for tipo_tentativo in ('fatto', 'diritto'):
            cat = CattedraOrganico.query.filter_by(
                anno_scol=anno, tipo=tipo_tentativo, id_classe_concorso=cc.id).first()
            if cat:
                break
        n_usr = cat.n_docenti if cat else 0
        n_ti_cc = (db.session.query(db.func.count(DocenteClasseConcorso.id))
                   .join(Docente, DocenteClasseConcorso.id_docente == Docente.id)
                   .filter(DocenteClasseConcorso.id_classe_concorso == cc.id,
                           Docente.attivo == True, Docente.tipo_contratto == 'TI')
                   .scalar() or 0)
        tipo_usr = cat.tipo if cat else None
        scarto = n_ti_cc - n_usr
        if scarto != 0:
            confronto_cc.append({
                'cc': cc, 'n_ti': n_ti_cc, 'n_usr': n_usr,
                'tipo_usr': tipo_usr, 'scarto': scarto})

    # ── Aule mancanti ─────────────────────────────────────────────
    from models.aula import Aula
    classi_labels = {f'{s.anno_corso}{s.sezione} {s.indirizzo}' for s in classi_attive}
    aule_assegnate = {a.classe for a in Aula.query.filter_by(anno_scol=anno).all()}
    n_aule_mancanti = len(classi_labels - aule_assegnate)

    anni = sorted({r.anno_scol for r in CalcoloOrganico.query.all()}, reverse=True)
    if anno not in anni:
        anni.insert(0, anno)

    classi_sezioni = ClasseSezione.query.filter_by(
        anno_scol=anno, attiva=True).order_by(
        ClasseSezione.indirizzo, ClasseSezione.anno_corso,
        ClasseSezione.sezione).all()

    return render_template('dashboard_anno/index.html',
        anno=anno, anni_disponibili=anni,
        n_classi=n_classi, indirizzi=indirizzi,
        n_docenti=n_docenti, n_ti=n_ti, n_td=n_td,
        n_aspettativa=n_aspettativa, n_ap_uscente=n_ap_uscente,
        n_ap_entrante=n_ap_entrante,
        n_assegnazioni=n_assegnazioni,
        n_cc_totali=n_cc_totali, n_cc_assegnate=n_cc_assegnate,
        perc_assegnazioni=perc_assegnazioni,
        n_incarichi=n_incarichi,
        n_coord_assegnati=n_coord_assegnati, n_coord_mancanti=n_coord_mancanti,
        n_ref_assegnati=n_ref_assegnati, n_ref_mancanti=n_ref_mancanti,
        n_materie_no_mat=n_materie_no_mat,
        confronto_cc=confronto_cc,
        n_aule_mancanti=n_aule_mancanti,
        classi_sezioni=classi_sezioni)


@dashboard_anno_bp.route('/classe/<path:label>')
def scheda_classe(label):
    """Vista web scheda classe: docenti, materie, incarichi."""
    import re
    from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse
    from models.incarico import IncaricaDocente
    from models.materia import Materia
    from models.aula import Aula
    from collections import defaultdict

    anno = request.args.get('anno', get_anno_corrente())
    m = re.match(r'(\d+)([AB]?)\s+(.+)', label)
    if not m:
        from flask import abort
        abort(400)
    anno_corso = int(m.group(1))
    sezione    = m.group(2) or 'A'
    indirizzo  = m.group(3).strip()

    # Aula
    aula = Aula.query.filter_by(
        anno_scol=anno, classe=f'{anno_corso}{sezione} {indirizzo}').first()

    # Assegnazioni docenti
    assegnazioni_classe = (AssegnazioneClasse.query
        .filter_by(indirizzo=indirizzo, anno_corso=anno_corso, sezione=sezione)
        .join(AssegnazioneDocente,
              AssegnazioneClasse.id_assegnazione == AssegnazioneDocente.id)
        .filter(AssegnazioneDocente.anno_scol == anno).all())

    doc_map = defaultdict(list)
    for ac in assegnazioni_classe:
        mat = Materia.query.get(ac.id_materia) if ac.id_materia else None
        doc_map[ac.assegnazione].append({
            'materia': (mat.nome_breve or mat.nome) if mat else '—',
            'ore': ac.ore
        })

    # Incarichi di classe
    incarichi = IncaricaDocente.query.filter_by(
        anno_scol=anno, indirizzo=indirizzo,
        anno_corso=anno_corso, sezione=sezione).all()

    # Piano studi per questa classe
    piano = (PianoStudi.query
             .filter_by(anno_scol=anno, indirizzo=indirizzo,
                        anno_corso=anno_corso, compresenza=False)
             .all())

    anni = sorted({s.anno_scol for s in ClasseSezione.query.all()}, reverse=True)

    return render_template('dashboard_anno/scheda_classe.html',
        anno=anno, anni_disponibili=anni,
        label=label, anno_corso=anno_corso,
        sezione=sezione, indirizzo=indirizzo,
        aula=aula, doc_map=doc_map, incarichi=incarichi, piano=piano)


@dashboard_anno_bp.route('/incarichi-docenti')
def incarichi_docenti():
    """Vista trasversale: per ogni docente, tutti gli incarichi dell'anno."""
    anno = request.args.get('anno', get_anno_corrente())

    nomine = (IncaricaDocente.query
              .filter_by(anno_scol=anno)
              .join(Docente, IncaricaDocente.id_docente == Docente.id)
              .order_by(Docente.cognome, Docente.nome)
              .all())

    # Raggruppa per docente
    from collections import defaultdict
    per_doc = defaultdict(list)
    for n in nomine:
        per_doc[n.docente].append(n)

    anni = sorted({r.anno_scol for r in IncaricaDocente.query.all()}, reverse=True)
    if not anni:
        anni = [anno]

    return render_template('dashboard_anno/incarichi_docenti.html',
        anno=anno, anni_disponibili=anni, per_doc=per_doc)
