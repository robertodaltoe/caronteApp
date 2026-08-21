"""
routes/banca_ore.py

Vista dedicata "Banca Ore": elenco saldi di tutti i docenti + dettaglio
movimenti per singolo docente. Riusa la logica di calcolo già esistente
in routes/report.py (get_saldi_docente, get_storico_settimanale,
get_ore_ist_docente) invece di duplicarla — stessa fonte di verità dei
saldi usata anche dal report per il Dirigente e dalle bozze email.

Gli export PDF/XLSX per singolo docente e l'export XLSX globale restano
sulle route storiche in report.py (report.singolo_pdf, report.singolo_xlsx,
report.globale_xlsx): niente di nuovo da mantenere per la stessa funzione.
"""
from flask import Blueprint, render_template, session, request
from models.docente import Docente
from models.movimento_banca_ore import MovimentoBancaOre
from models import db
from config_anno import get_anno_corrente
from datetime import date

banca_ore_bp = Blueprint("banca_ore", __name__)


def _anni_disponibili():
    """Anni scolastici con almeno un movimento registrato, + l'anno corrente
    (anche se ancora senza movimenti), più recenti prima — per il selettore
    'archivio' nella pagina Banca Ore."""
    anni = {row[0] for row in db.session.query(MovimentoBancaOre.anno_scol).distinct()
            if row[0]}
    anni.add(get_anno_corrente())
    return sorted(anni, reverse=True)


@banca_ore_bp.route("/banca-ore")
def index():
    from routes.report import get_saldi_docente, get_ore_ist_docente

    anno_corrente = get_anno_corrente()
    anno = request.args.get('anno', anno_corrente)

    from routes.impostazione_anno import _docenti_per_anno
    docenti = _docenti_per_anno(anno)

    saldi = {}
    for d in docenti:
        s = get_saldi_docente(d.id, anno_scol=anno)
        lordo_eff   = s['sup_svolte'] - s['perm_svolte'] - s['civ_svolte']
        netto_eff   = lordo_eff - s['pagamento']
        lordo_prev  = s['sup_prev'] - s['perm_prev'] - s['civ_prev']
        saldo_lordo = s['supplenze'] - s['permessi'] - s['civica']
        saldo_netto = saldo_lordo - s['pagamento']
        saldi[d.id] = {**s,
            'lordo': saldo_lordo, 'netto': saldo_netto,
            'netto_eff': netto_eff, 'lordo_eff': lordo_eff,
            'netto_prev': lordo_prev,
        }

    # Costo ora supplenza — configurabile in Impostazioni > Dati istituto
    from config_istituto import get_costo_ora
    COSTO_ORA = get_costo_ora()

    ruolo_utente = session.get('ruolo', 'collaboratore')
    ore_ist_idx = {}
    if ruolo_utente in ('ds', 'dsga', 'segreteria'):
        for d in docenti:
            ore_ist_idx[d.id] = get_ore_ist_docente(d.id, anno=anno)

    return render_template('banca_ore/index.html',
        docenti=docenti, saldi=saldi, oggi=date.today(),
        costo_ora=COSTO_ORA,
        ore_ist_idx=ore_ist_idx,
        ruolo_utente=ruolo_utente,
        anno=anno, anno_corrente=anno_corrente,
        anni_disponibili=_anni_disponibili())


@banca_ore_bp.route('/banca-ore/docente/<int:id>')
def singolo(id):
    from routes.report import get_saldi_docente, get_storico_settimanale, get_ore_ist_docente
    from models.supplenza import Supplenza
    from models.orario_docente import OrarioDocente

    anno_corrente = get_anno_corrente()
    anno = request.args.get('anno', anno_corrente)

    d = Docente.query.get_or_404(id)
    saldi   = get_saldi_docente(id, anno_scol=anno)
    storico = get_storico_settimanale(id, anno_scol=anno)

    saldo_lordo_eff  = saldi['sup_svolte'] - saldi['perm_svolte'] - saldi['civ_svolte']
    saldo_netto_eff  = saldo_lordo_eff - saldi['pagamento']

    saldo_lordo_prev = saldi['sup_prev'] - saldi['perm_prev'] - saldi['civ_prev']
    saldo_netto_prev = saldo_lordo_prev

    saldo_lordo   = saldi['supplenze'] - saldi['permessi'] - saldi.get('perm_ist', 0) - saldi['civica']
    saldo_netto   = saldo_lordo - saldi['pagamento']

    # Supplenza non ha una colonna anno_scol propria: la filtriamo per
    # l'intervallo di date dell'anno scolastico visualizzato, così l'elenco
    # resta coerente con il saldo mostrato sopra (prima mostrava sempre
    # tutte le supplenze di ogni anno, indipendentemente da quale anno si
    # stesse consultando).
    from config_anno import intervallo_anno_scolastico
    _inizio_anno, _fine_anno = intervallo_anno_scolastico(anno)
    supplenze = (Supplenza.query
                 .filter_by(id_sostituto=id)
                 .filter(Supplenza.stato == 'assegnata')
                 .filter(Supplenza.data >= _inizio_anno, Supplenza.data <= _fine_anno)
                 .order_by(Supplenza.data)
                 .all())

    GIORNI = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato']
    slots = OrarioDocente.query.filter_by(id_docente=id).order_by(
        OrarioDocente.giorno, OrarioDocente.ora).all()
    orario = {}
    ore_usate = set()
    for s in slots:
        if s.classe and s.classe not in ('---', '-x-', ''):
            orario.setdefault(s.giorno, {})[s.ora] = s
            ore_usate.add(s.ora)
    ore_list = sorted(ore_usate) if ore_usate else list(range(1, 6))
    giorni_usati = sorted(set(s.giorno for s in slots))

    ruolo_utente = session.get('ruolo', 'collaboratore')
    ore_ist = None
    if ruolo_utente in ('ds', 'dsga', 'segreteria'):
        ore_ist = get_ore_ist_docente(id, anno=anno)

    from models.docente import tipo_contratto_label_per_anno
    return render_template('banca_ore/singolo.html',
        docente=d,
        contratto_label_anno=tipo_contratto_label_per_anno(d, anno),
        anno=anno, anno_corrente=anno_corrente,
        anni_disponibili=_anni_disponibili(),
        saldi=saldi,
        saldo_lordo=saldo_lordo,
        saldo_netto=saldo_netto,
        saldo_lordo_eff=saldo_lordo_eff,
        saldo_netto_eff=saldo_netto_eff,
        saldo_lordo_prev=saldo_lordo_prev,
        saldo_netto_prev=saldo_netto_prev,
        storico=storico,
        supplenze=supplenze,
        orario=orario,
        ore_list=ore_list,
        giorni_usati=giorni_usati,
        giorni_nomi=GIORNI,
        oggi=date.today(),
        ore_ist=ore_ist,
        ruolo_utente=ruolo_utente,
    )
