from config_anno import get_anno_corrente
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from models import db
from models.docente import Docente
from models.materia import Materia, DocenteMateria, Dipartimento
from models.colloqui_eccezione import ColloquiEccezione
from datetime import date

docenti_bp = Blueprint('docenti', __name__)

GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato']


def _sync_materia_roster(docente, materie_ids, anno):
    """
    Sincronizza le materie selezionate nella scheda docente. Tocca solo
    le righe 'manuale' (dichiarate qui): non cancella mai le righe
    'auto' sincronizzate da Assegnazioni classi -> docenti — altrimenti
    ogni modifica dell'anagrafica (anche solo email o telefono) avrebbe
    silenziosamente cancellato le materie derivate dalle ore assegnate.
    """
    DocenteMateria.query.filter_by(
        id_docente=docente.id, anno_scol=anno, origine='manuale').delete()
    for mid in materie_ids:
        if mid.isdigit():
            esiste = DocenteMateria.query.filter_by(
                id_docente=docente.id, id_materia=int(mid), anno_scol=anno).first()
            if not esiste:
                db.session.add(DocenteMateria(
                    id_docente=docente.id, id_materia=int(mid),
                    anno_scol=anno, origine='manuale'))
    # Aggiorna anche il campo materia testuale (prima materia selezionata)
    if materie_ids:
        prima = Materia.query.get(int(materie_ids[0]))
        if prima:
            docente.materia = prima.nome


def _shift_anno(anno_scol, n):
    """'2026-2027' + 1 -> '2027-2028' (idem con n negativo)."""
    a1, a2 = anno_scol.split('-')
    return f"{int(a1)+n}-{int(a2)+n}"


def _docenti_non_in_servizio(anno_scol):
    """
    Docenti non in servizio nell'anno indicato: disattivati (attivo=False),
    usciti (trasferimento/pensionamento/fine_td, segnalati dal passo 7 con
    anno_scol_uscita <= anno_scol) o segnalati come AP uscente/in
    aspettativa (status_presenza — vedi routes/impostazione_anno.py::
    docenti_anno). Questi ultimi due gruppi restano 'attivo=True' — sono
    ancora titolari della scuola secondo il resto dell'app — ma qui vanno
    comunque mostrati perché "potrebbero tornare".

    Nota: status_presenza e motivo_uscita non sono per-singolo-anno (sono
    lo stato più recente noto, stessa approssimazione già usata altrove
    nell'app, es. dashboard_anno) — quindi qui non filtriamo per
    anno_scol su questi due campi, mostriamo lo stato attuale.
    """
    from sqlalchemy import or_, and_
    return (Docente.query.filter(or_(
        Docente.attivo == False,
        and_(Docente.anno_scol_uscita != None, Docente.anno_scol_uscita <= anno_scol),
        Docente.status_presenza.in_(['ap_uscente', 'aspettativa']),
    )).order_by(Docente.cognome).all())


@docenti_bp.route('/docenti')
def lista():
    from config_anno import get_anno_corrente
    from routes.impostazione_anno import _docenti_per_anno
    from models.piano_studi import PianoStudi, ClasseSezione

    # Anno operativo reale (calendario/config — lo stesso usato da
    # assegnazioni, banca ore, ecc.), NON _anno_default_piano(): quello è
    # pensato per il wizard "Impostazione Anno" e punta subito all'anno che
    # si sta preparando, anche prima del cambio effettivo a settembre.
    anno_default = get_anno_corrente()
    anno_sel = request.args.get('anno', anno_default)

    # Finestra fissa di anni (indipendente dai dati già inseriti, altrimenti
    # con un solo anno di Piano di Studi in archivio il selettore sparirebbe)
    # unita a qualunque anno con dati reali già presenti.
    anni_disponibili = ({_shift_anno(anno_default, n) for n in (-1, 0, 1, 2)} |
        {r.anno_scol for r in PianoStudi.query.with_entities(PianoStudi.anno_scol).distinct()} |
        {r.anno_scol for r in ClasseSezione.query.with_entities(ClasseSezione.anno_scol).distinct()} |
        {anno_sel})
    anni_disponibili = sorted(anni_disponibili, reverse=True)

    docenti = _docenti_per_anno(anno_sel)
    docenti = sorted(docenti, key=lambda d: d.cognome)

    mostra_inattivi = request.args.get('mostra') == 'inattivi'
    docenti_inattivi = _docenti_non_in_servizio(anno_sel) if mostra_inattivi else []

    # Stato Piano Attività Personale (Sessione 57), solo per i docenti
    # che devono compilarlo nell'anno mostrato (cattedra non completa,
    # o IRC anche a cattedra piena — vedi models/piano_attivita_
    # personale.py::deve_compilare_piano) — per tutti gli altri
    # piano_personale_stato resta assente (nessun badge in tabella).
    from models.piano_attivita_personale import deve_compilare_piano, PianoAttivitaPersonale
    coinvolti_ids = {d.id for d in docenti if deve_compilare_piano(d, anno_sel)}
    piani_stato = {p.id_docente: p.stato for p in PianoAttivitaPersonale.query.filter(
        PianoAttivitaPersonale.anno_scol == anno_sel,
        PianoAttivitaPersonale.id_docente.in_(coinvolti_ids)).all()} if coinvolti_ids else {}
    piano_personale_stato = {did: piani_stato.get(did, 'nessuno') for did in coinvolti_ids}

    # Contratto DI QUESTO anno (storico se registrato, altrimenti il
    # corrente) — l'anagrafica è filtrata per anno_sel, l'etichetta del
    # contratto deve rifletterlo: un TI ora che nell'anno mostrato era
    # ancora TD (es. Agrò) va etichettato col contratto che aveva
    # ALLORA. Vedi models.docente.DocenteContrattoAnno.
    from models.docente import DocenteContrattoAnno, TIPO_CONTRATTO_LABELS, TIPO_CONTRATTO_LABELS_BREVI
    contratti_anno_map = {
        c.id_docente: c.tipo_contratto for c in
        DocenteContrattoAnno.query.filter_by(anno_scol=anno_sel).all()
    }

    return render_template('docenti.html', docenti=docenti,
                           anno_sel=anno_sel, anni_disponibili=anni_disponibili,
                           anno_default=anno_default,
                           mostra_inattivi=mostra_inattivi,
                           docenti_inattivi=docenti_inattivi,
                           piano_personale_stato=piano_personale_stato,
                           contratti_anno_map=contratti_anno_map,
                           tipo_contratto_labels=TIPO_CONTRATTO_LABELS,
                           tipo_contratto_labels_brevi=TIPO_CONTRATTO_LABELS_BREVI)


@docenti_bp.route('/docenti/<int:id>/riattiva', methods=['POST'])
def riattiva(id):
    """
    Riattiva un docente non più attivo sulla STESSA scheda (non ne crea una
    nuova) — evita la duplicazione di anagrafiche vista in passato (es. caso
    Agrò, id 2/102 unificati manualmente). Imposta l'anno di rientro e
    ripulisce i segnali di uscita precedenti.
    """
    d = Docente.query.get_or_404(id)
    if d.motivo_uscita == 'pensionamento':
        flash(f'{d.nome_completo} risulta pensionato: non riattivabile da qui.', 'error')
        return redirect(url_for('docenti.lista', mostra='inattivi'))

    anno_rientro = request.form.get('anno_rientro', '').strip()
    if not anno_rientro:
        flash('Indica l\'anno scolastico di rientro prima di riattivare.', 'error')
        return redirect(url_for('docenti.lista', mostra='inattivi'))

    d.attivo = True
    d.anno_scol_inizio = anno_rientro
    d.anno_scol_uscita = None
    d.motivo_uscita = None
    # Ripulisce anche lo stato di presenza (AP uscente/aspettativa) —
    # vedi routes/impostazione_anno.py::docenti_anno() "annulla_status".
    d.status_presenza = 'presente'
    d.scuola_ap = None
    db.session.commit()
    from routes.attivita_ist import iscrivi_docente_a_obbligatori
    iscrivi_docente_a_obbligatori(d)
    from routes.auth import log as auth_log
    auth_log('riattiva_docente', f'{d.nome_completo} (dal {anno_rientro})')
    flash(f"{d.nome_completo} riattivato dall'a.s. {anno_rientro}. "
          f"Controlla e completa la scheda.", 'success')
    return redirect(url_for('docenti.modifica', id=d.id))

@docenti_bp.route('/docenti/nuovo', methods=['GET', 'POST'])
def nuovo():
    if request.method == 'POST':
        d = Docente(
            cognome        = request.form['cognome'].strip().upper(),
            nome           = request.form['nome'].strip().title(),
            materia        = request.form.get('materia', '').strip(),
            ore_contratto  = int(request.form.get('ore_contratto', 18) or 0),
            email          = request.form.get('email', '').strip(),
            tipo_contratto = request.form.get('tipo_contratto', '').strip(),
            ruolo          = request.form.get('ruolo', 'titolare').strip(),
            part_time      = (request.form.get('tipo_servizio') == 'part_time'),
            ore_contratto_pt= int(request.form.get('ore_contratto_pt') or 0) or None,
            ore_max_anno   = int(request.form.get('ore_max_anno') or 0) or None,
            altra_scuola   = (request.form.get('altra_scuola','').strip() or None) if request.form.get('tipo_servizio') == 'multi_sede' else None,
            giorni_presenza= (','.join(request.form.getlist('giorni_presenza')) or None) if request.form.get('tipo_servizio') == 'multi_sede' else None,
            attivo         = True
        )
        id_tit_rif = request.form.get('id_titolare_riferimento', '').strip()
        d.id_titolare_riferimento = int(id_tit_rif) if (d.ruolo == 'itp' and id_tit_rif) else None
        d.nome_display = f"{d.cognome} {d.nome[0]}." if d.nome else d.cognome
        db.session.add(d)
        db.session.commit()
        from routes.attivita_ist import iscrivi_docente_a_obbligatori
        iscrivi_docente_a_obbligatori(d)
        from routes.auth import log as auth_log
        auth_log('crea_docente', f'{d.nome_completo} (ore_contratto={d.ore_contratto})')
        flash(f"Docente {d.nome_completo} aggiunto. Ora assegna la sua classe di concorso e le materie.", 'success')
        return redirect(url_for('docenti.modifica', id=d.id))
    titolari_disponibili = Docente.query.filter(
        Docente.attivo == True, Docente.ruolo == 'titolare').order_by(Docente.cognome).all()
    anni_ore_max_n = ['2025-2026', '2026-2027', '2027-2028']
    return render_template('docente_form.html', docente=None, giorni=list(enumerate(GIORNI)), eccezioni=[],
                           anni_disponibili_ore_max=anni_ore_max_n,
        titolari_disponibili=titolari_disponibili)

@docenti_bp.route('/docenti/<int:id>/modifica', methods=['GET', 'POST'])
def modifica(id):
    from config_anno import get_anno_corrente
    d = Docente.query.get_or_404(id)
    if request.method == 'POST':
        from concorrenza import versione_cambiata
        if versione_cambiata(d.modificato_il, request.form.get('versione')):
            flash(
                f'⚠︎ La scheda di {d.nome_completo} è stata modificata da un '
                f'altro utente nel frattempo. Ricarica la pagina per vedere '
                f'i dati aggiornati prima di salvare di nuovo.', 'error')
            return redirect(url_for('docenti.modifica', id=id))

        d.cognome        = request.form['cognome'].strip().upper()
        d.nome           = request.form['nome'].strip().title()
        d.ore_contratto  = int(request.form.get('ore_contratto', 18) or 0)
        d.ore_max_anno   = int(request.form.get('ore_max_anno') or 0) or None
        # L'anno a cui si riferisce ore_max_anno non veniva mai salvato:
        # il form invia anche "anno_scol_ore_max", ma la route leggeva
        # solo il numero — l'override restava sempre inefficace perché
        # ore_max_effettive_per_anno() lo confronta con l'anno richiesto
        # e non trovava mai corrispondenza (segnalato da Roberto: caso
        # Palermo, l'override a 9h per il 2025-2026 non aveva mai effetto).
        d.anno_scol_ore_max = (request.form.get('anno_scol_ore_max', '').strip()
                               or None) if d.ore_max_anno else None
        d.email          = request.form.get('email', '').strip()
        d.tipo_contratto = request.form.get('tipo_contratto', '').strip()
        d.ruolo          = request.form.get('ruolo', 'titolare').strip()

        # Abbinamenti titolare+materia (un ITP può affiancare più titolari
        # su materie/laboratori diversi). Sostituisce sempre l'elenco
        # completo con quello inviato dal form.
        from models.docente import CoppiaDocenteItp
        CoppiaDocenteItp.query.filter_by(id_itp=d.id).delete()
        if d.ruolo == 'itp':
            id_titolari = request.form.getlist('abbinamento_id_titolare[]')
            materie_abb = request.form.getlist('abbinamento_materia[]')
            primo_titolare = None
            for i, id_tit_str in enumerate(id_titolari):
                id_tit_str = id_tit_str.strip()
                if not id_tit_str:
                    continue
                id_tit = int(id_tit_str)
                materia_abb = materie_abb[i].strip() if i < len(materie_abb) else ''
                db.session.add(CoppiaDocenteItp(
                    id_titolare=id_tit, id_itp=d.id,
                    materia=materia_abb or None, attiva=True))
                if primo_titolare is None:
                    primo_titolare = id_tit
            # Campo singolo mantenuto in sync con il primo abbinamento,
            # per eventuale codice legacy che lo legge ancora.
            d.id_titolare_riferimento = primo_titolare
        else:
            d.id_titolare_riferimento = None
        tipo_serv = request.form.get('tipo_servizio', 'full')
        d.part_time      = (tipo_serv == 'part_time')
        d.altra_scuola   = (request.form.get('altra_scuola', '').strip() or None) if tipo_serv == 'multi_sede' else None
        d.giorni_presenza= (','.join(request.form.getlist('giorni_presenza')) or None) if tipo_serv == 'multi_sede' else None
        if tipo_serv == 'part_time':
            d.ore_contratto_pt = int(request.form.get('ore_contratto_pt') or 0) or None
        else:
            d.ore_contratto_pt = None

        # Cambio di regime part-time programmato per un anno futuro (vedi
        # Docente.part_time_effettivo_per_anno) — non tocca part_time/
        # ore_contratto_pt correnti, usati dall'anno in corso.
        anno_prog = request.form.get('anno_scol_part_time_prog', '').strip()
        if anno_prog:
            tipo_prog = request.form.get('tipo_servizio_prog', 'full')
            d.anno_scol_part_time_prog = anno_prog
            d.part_time_prog = (tipo_prog == 'part_time')
            d.ore_contratto_pt_prog = (
                int(request.form.get('ore_contratto_pt_prog') or 0) or None
                if tipo_prog == 'part_time' else None)
        else:
            d.anno_scol_part_time_prog = None
            d.part_time_prog = None
            d.ore_contratto_pt_prog = None
        if tipo_serv == 'multi_sede':
            import json as _json
            ou = {}
            for g in range(6):
                v = request.form.get(f'ora_uscita_{g}', '').strip()
                if v and v.isdigit():
                    ou[str(g)] = int(v)
            d.ora_uscita_json = _json.dumps(ou) if ou else None
        else:
            d.ora_uscita_json = None
        cg = request.form.get('colloqui_giorno', '').strip()
        d.colloqui_giorno     = int(cg) if cg != '' else None
        ci = request.form.get('colloqui_ora_inizio', '').strip()
        d.colloqui_ora_inizio = int(ci) if ci else None
        cf = request.form.get('colloqui_ora_fine', '').strip()
        d.colloqui_ora_fine   = int(cf) if cf else None
        d.attivo         = 'attivo' in request.form
        d.nome_display   = f"{d.cognome} {d.nome[0]}." if d.nome else d.cognome

        # Gestione eccezioni colloqui (range settimanali)
        ColloquiEccezione.query.filter_by(id_docente=d.id).delete()
        date_ini_l   = request.form.getlist('eccezione_data[]')
        date_fine_l  = request.form.getlist('eccezione_data_fine[]')
        note_ecc_l   = request.form.getlist('eccezione_note[]')
        for i, data_str in enumerate(date_ini_l):
            if not data_str.strip(): continue
            try:
                data_i = date.fromisoformat(data_str.strip())
                df_s   = date_fine_l[i] if i < len(date_fine_l) else ''
                data_f = date.fromisoformat(df_s.strip()) if df_s.strip() else None
                note_e = note_ecc_l[i].strip() if i < len(note_ecc_l) else ''
                db.session.add(ColloquiEccezione(
                    id_docente = d.id,
                    data       = data_i,
                    data_fine  = data_f,
                    note       = note_e,
                ))
            except ValueError:
                continue

        _sync_materia_roster(d, request.form.getlist('materie_ids'), get_anno_corrente())
        db.session.commit()
        from routes.auth import log as auth_log
        auth_log('modifica_docente', f'{d.nome_completo}')
        flash(f"Docente {d.nome_completo} aggiornato.", 'success')
        return redirect(url_for('docenti.lista'))

    eccezioni = ColloquiEccezione.query.filter_by(id_docente=d.id)\
        .order_by(ColloquiEccezione.data).all()
    # Navigazione prev/next tra docenti attivi (ordine alfabetico)
    tutti = [doc.id for doc in Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()]
    idx   = tutti.index(id) if id in tutti else -1
    id_prev = tutti[idx - 1] if idx > 0            else None
    id_next = tutti[idx + 1] if idx < len(tutti)-1 else None
    # Mostra solo le materie insegnabili dal docente (filtrate per le sue CC)
    # Se non ha CC collegate, lista vuota con messaggio.
    from models.classe_concorso import MateriaClasseConcorso, DocenteClasseConcorso
    cc_ids = [r.id_classe_concorso for r in
              DocenteClasseConcorso.query.filter_by(id_docente=id).all()]
    if cc_ids:
        materie_ids_per_cc = {r.id_materia for r in
                              MateriaClasseConcorso.query.filter(
                                  MateriaClasseConcorso.id_classe_concorso.in_(cc_ids)).all()}
        materie = (Materia.query
                   .join(Dipartimento)
                   .filter(Materia.id.in_(materie_ids_per_cc))
                   .order_by(Dipartimento.ordine, Materia.nome).all())
    else:
        materie = []
    # "Materie insegnate" e' per anno_scol (assegnate da Assegnazioni): di
    # default mostra l'anno corrente, ma Roberto vuole poter risalire anche
    # agli anni passati/futuri — selettore anno accanto al box, valorizzato
    # da querystring cosi' i link prev/next della scheda non lo perdono.
    anni_materie = sorted(
        {r.anno_scol for r in DocenteMateria.query.with_entities(DocenteMateria.anno_scol)
         .filter_by(id_docente=id).distinct().all()} | {get_anno_corrente()},
        reverse=True)
    anno_sel_materie = request.args.get('anno_materie') or get_anno_corrente()
    if anno_sel_materie not in anni_materie:
        anni_materie = sorted(set(anni_materie) | {anno_sel_materie}, reverse=True)
    mat_assegnate = {dm.id_materia for dm in DocenteMateria.query.filter_by(
        id_docente=id, anno_scol=anno_sel_materie).all()}
    titolari_disponibili = (Docente.query
        .filter(Docente.attivo == True, Docente.ruolo == 'titolare', Docente.id != d.id)
        .order_by(Docente.cognome).all())

    from models.docente import CoppiaDocenteItp
    abbinamenti_itp = (CoppiaDocenteItp.query
        .filter_by(id_itp=d.id, attiva=True).all())

    # Anni disponibili per il campo ore_max_anno
    from models.piano_studi import PianoStudi as PS2, ClasseSezione as CS2
    anni_ore_max = sorted(
        {r.anno_scol for r in PS2.query.with_entities(PS2.anno_scol).distinct()} |
        {r.anno_scol for r in CS2.query.with_entities(CS2.anno_scol).distinct()} |
        {get_anno_corrente()},
        reverse=True)

    # Incarichi: anno corrente in evidenza, resto come storico (sola
    # lettura — si assegnano/modificano dalla pagina Incarichi, non da qui).
    from models.incarico import IncaricaDocente
    anno_c = get_anno_corrente()
    tutti_incarichi = (d.incarichi
                        .order_by(IncaricaDocente.anno_scol.desc()).all())
    incarichi_corrente = [i for i in tutti_incarichi if i.anno_scol == anno_c]
    incarichi_storico = {}
    for i in tutti_incarichi:
        if i.anno_scol != anno_c:
            incarichi_storico.setdefault(i.anno_scol, []).append(i)

    # Piano Attività Personale (Sessione 57): solo se il docente deve
    # compilarlo nell'anno corrente — cattedra non completa, o IRC anche
    # a cattedra piena (vedi models/piano_attivita_personale.py::
    # deve_compilare_piano) — altrimenti il riquadro non compare.
    piano_personale = None
    if d.attivo:
        from models.piano_attivita_personale import (
            deve_compilare_piano, frazione_cattedra, quota_ore_bucket, PianoAttivitaPersonale,
        )
        if deve_compilare_piano(d, anno_c):
            piano = PianoAttivitaPersonale.query.filter_by(
                id_docente=d.id, anno_scol=anno_c).first()
            quota_a, quota_b = quota_ore_bucket(d, anno_c)
            ore_a, ore_b = piano.ore_scelte_bucket() if piano else (0.0, 0.0)
            piano_personale = {
                'piano': piano, 'anno': anno_c,
                'frazione': frazione_cattedra(d, anno_c),
                'quota_a': quota_a, 'quota_b': quota_b,
                'ore_a': ore_a, 'ore_b': ore_b,
                'eventi_scelti': sorted(
                    (v.attivita for v in piano.voci if v.attivita), key=lambda e: e.data
                ) if piano else [],
            }

    return render_template('docente_form.html', docente=d,
                           materie=materie, mat_assegnate=mat_assegnate,
        anni_materie=anni_materie, anno_sel_materie=anno_sel_materie,
        anno_corrente_materie=get_anno_corrente(),
        giorni=list(enumerate(GIORNI)), eccezioni=eccezioni,
        id_prev=id_prev, id_next=id_next,
        titolari_disponibili=titolari_disponibili,
        abbinamenti_itp=abbinamenti_itp,
        anni_disponibili_ore_max=anni_ore_max,
        anno_corrente_incarichi=anno_c,
        incarichi_corrente=incarichi_corrente,
        incarichi_storico=incarichi_storico,
        piano_personale=piano_personale)

@docenti_bp.route('/docenti/<int:id>/anonimizza', methods=['POST'])
def anonimizza(id):
    """
    Anonimizza un docente su richiesta (art. 17 GDPR).
    Conserva i dati operativi (supplenze, banca ore) per obblighi contabili
    ma sostituisce i dati identificativi con un codice anonimo.
    """
    from models.log_accesso import LogAccesso
    from routes.auth import log as auth_log
    d = Docente.query.get_or_404(id)
    codice = f'ANONIMO_{id:04d}'
    nome_orig = f'{d.cognome} {d.nome}'

    d.cognome      = codice
    d.nome         = ''
    d.nome_display = codice
    d.email        = None
    d.note         = None
    d.attivo       = False
    db.session.commit()

    # Anonimizza anche nei log accessi se era utente del sistema
    from models.utente import Utente
    u = Utente.query.filter(
        Utente.cognome.ilike(d.cognome) | Utente.nome.ilike(d.nome or '')
    ).first()

    auth_log('anonimizzazione', f'{nome_orig} -> {codice} (art.17 GDPR)')
    flash(f'Docente anonimizzato come {codice}. I dati operativi sono conservati.', 'success')
    return redirect(url_for('docenti.lista'))


@docenti_bp.route('/docenti/<int:id>/elimina', methods=['POST'])
def elimina(id):
    from models.orario_docente import OrarioDocente
    from models.movimento_banca_ore import MovimentoBancaOre
    from models.assenza import Assenza
    from models.supplenza import Supplenza

    d = Docente.query.get_or_404(id)
    nome = d.cognome
    n_or  = OrarioDocente.query.filter_by(id_docente=id).count()
    n_bk  = MovimentoBancaOre.query.filter_by(id_docente=id).count()
    n_as  = Assenza.query.filter_by(id_docente=id).count()
    n_sup = Supplenza.query.filter(
        db.or_(Supplenza.id_assente==id, Supplenza.id_sostituto==id)
    ).count()
    forza = request.form.get('forza') == '1'
    if (n_bk > 0 or n_as > 0 or n_sup > 0) and not forza:
        flash(
            f'⚠︎ {nome} ha dati collegati (banca ore: {n_bk}, assenze: {n_as}, '
            f'supplenze: {n_sup}). Conferma l\'eliminazione definitiva.',
            'warning'
        )
        return redirect(url_for('docenti.lista') + f'?conferma_elimina={id}')
    ColloquiEccezione.query.filter_by(id_docente=id).delete()
    OrarioDocente.query.filter_by(id_docente=id).delete()
    db.session.delete(d)
    db.session.commit()
    from routes.auth import log as auth_log
    auth_log('elimina_docente',
        f'{nome} (banca_ore:{n_bk} assenze:{n_as} supplenze:{n_sup} forzato:{forza})')
    flash(f'Docente {nome} eliminato definitivamente.', 'success')
    return redirect(url_for('docenti.lista'))


@docenti_bp.route('/docenti/<int:id>/esporta-dati')
def esporta_dati(id):
    """
    Esporta in un unico documento tutti i dati personali collegati a un
    docente — a supporto delle richieste di accesso ex art. 15 GDPR
    (diritto dell'interessato a ricevere copia dei propri dati).

    Copre le tabelle principali che contengono dati riferiti a un
    docente specifico: anagrafica, orario (lezione + sostegno), assenze,
    supplenze (come assente e come sostituto), banca ore, indisponibilità,
    assegnazioni cattedre/classi, eccezioni colloqui.
    """
    import io
    from datetime import date as _date
    from models.orario_docente import OrarioDocente
    from models.orario_sostegno import OrarioSostegno
    from models.assenza import Assenza, LABEL_INTERNE
    from models.supplenza import Supplenza
    from models.movimento_banca_ore import MovimentoBancaOre
    from models.indisponibilita import Indisponibilita
    from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse

    d = Docente.query.get_or_404(id)

    orario_lezione = (OrarioDocente.query.filter_by(id_docente=id)
                       .order_by(OrarioDocente.giorno, OrarioDocente.ora).all())
    orario_sostegno = (OrarioSostegno.query.filter_by(id_docente=id)
                        .order_by(OrarioSostegno.giorno, OrarioSostegno.ora).all())
    assenze = (Assenza.query.filter_by(id_docente=id)
               .order_by(Assenza.data.desc()).all())
    supplenze_come_assente = (Supplenza.query.filter_by(id_assente=id)
                               .order_by(Supplenza.data.desc()).all())
    for s in supplenze_come_assente:
        s.sostituto_obj = Docente.query.get(s.id_sostituto) if s.id_sostituto else None
    supplenze_come_sostituto = (Supplenza.query.filter_by(id_sostituto=id)
                                 .order_by(Supplenza.data.desc()).all())
    for s in supplenze_come_sostituto:
        s.assente_obj = Docente.query.get(s.id_assente) if s.id_assente else None
    movimenti_banca_ore = (MovimentoBancaOre.query.filter_by(id_docente=id)
                            .order_by(MovimentoBancaOre.data.desc()).all())
    indisponibilita = (Indisponibilita.query.filter_by(id_docente=id)
                        .order_by(Indisponibilita.data.desc()).all())
    assegnazioni = (AssegnazioneDocente.query.filter_by(id_docente=id).all())
    for a in assegnazioni:
        a.classi_ore = AssegnazioneClasse.query.filter_by(id_assegnazione=a.id).all()
    colloqui_eccezioni = (ColloquiEccezione.query.filter_by(id_docente=id)
                           .order_by(ColloquiEccezione.data.desc()).all())

    html_content = render_template('docenti/esporta_dati.html',
        docente=d, oggi=_date.today(),
        orario_lezione=orario_lezione, orario_sostegno=orario_sostegno,
        assenze=assenze, label_assenza=LABEL_INTERNE,
        supplenze_come_assente=supplenze_come_assente,
        supplenze_come_sostituto=supplenze_come_sostituto,
        movimenti_banca_ore=movimenti_banca_ore,
        indisponibilita=indisponibilita,
        assegnazioni=assegnazioni,
        colloqui_eccezioni=colloqui_eccezioni,
    )

    from routes.auth import log as auth_log
    auth_log('esporta_dati_docente',
        f'{d.cognome} {d.nome or ""} (art.15 GDPR)')

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html_content).write_pdf()
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'dati_personali_{d.cognome}_{_date.today().isoformat()}.pdf'
        )
    except ImportError:
        return html_content


@docenti_bp.route('/docenti/eccezioni-istituto', methods=['GET', 'POST'])
def eccezioni_istituto():
    if request.method == 'POST':
        azione = request.form.get('azione', '')

        if azione == 'salva_istituto':
            date_ini  = request.form.getlist('eccezione_data[]')
            date_fine = request.form.getlist('eccezione_data_fine[]')
            note_l    = request.form.getlist('eccezione_note[]')
            periodi = []
            for i, ds in enumerate(date_ini):
                if not ds.strip(): continue
                try:
                    di = date.fromisoformat(ds.strip())
                    df_s = date_fine[i] if i < len(date_fine) else ''
                    df   = date.fromisoformat(df_s.strip()) if df_s.strip() else None
                    ne   = note_l[i].strip() if i < len(note_l) else ''
                    periodi.append((di, df, ne))
                except ValueError:
                    continue
            docenti_con_colloqui = Docente.query.filter(
                Docente.attivo == True,
                Docente.colloqui_giorno != None
            ).all()
            n = 0
            for doc in docenti_con_colloqui:
                ColloquiEccezione.query.filter_by(id_docente=doc.id).delete()
                for di, df, ne in periodi:
                    db.session.add(ColloquiEccezione(
                        id_docente=doc.id, data=di, data_fine=df, note=ne))
                n += 1
            db.session.commit()
            flash(f'Periodi salvati per {n} docenti con colloqui configurati.', 'success')
            return redirect(url_for('docenti.eccezioni_istituto'))

    # GET — prendi le eccezioni del primo docente come riferimento
    docenti_con_colloqui = Docente.query.filter(
        Docente.attivo == True,
        Docente.colloqui_giorno != None
    ).order_by(Docente.cognome).all()
    eccezioni_ref = []
    if docenti_con_colloqui:
        eccezioni_ref = ColloquiEccezione.query.filter_by(
            id_docente=docenti_con_colloqui[0].id
        ).order_by(ColloquiEccezione.data).all()
    return render_template('eccezioni_istituto.html',
        docenti=docenti_con_colloqui, eccezioni=eccezioni_ref)
