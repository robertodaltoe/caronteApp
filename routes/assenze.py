from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db
from models.assenza import (Assenza, CATEGORIE, CATEGORIE_FORM, LABEL_INTERNE,
    LIMITI_CCNL, cat_impatta_banca, cat_colonna_banca,
    cat_genera_supplenza, cat_assegnabile)
from models.docente import Docente
from models.supplenza import Supplenza
from models.movimento_banca_ore import MovimentoBancaOre
from models.orario_docente import OrarioDocente
from models.scambio_orario import ScambioOrario, ScambioSlot
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante, AttivitaIstPresenza
from datetime import date, timedelta

assenze_bp = Blueprint('assenze', __name__)


def is_sospensione(data):
    """Restituisce la descrizione della sospensione se la data è sospesa, None altrimenti."""
    try:
        from models.sospensione import SospensioneDidattica
        s = SospensioneDidattica.query.filter(
            SospensioneDidattica.data_inizio <= data,
            SospensioneDidattica.data_fine   >= data,
        ).first()
        return s.descrizione if s else None
    except Exception:
        return None

GIORNI_SETTIMANA = {0:0, 1:1, 2:2, 3:3, 4:4, 5:5}  # weekday -> giorno orario



@assenze_bp.route('/assenze/nuova', methods=['GET', 'POST'])
def nuova():
    if request.method == 'POST':
        # Normalizza date in base al tipo di durata inviato dal form.
        # Il template manda campi diversi a seconda del pulsante durata selezionato:
        #   singolo   -> name="data"
        #   range     -> name="data_range_ini" + name="data_range_fin"
        #   periodico -> name="data_per_ini"   + name="data_per_fin"  + name="giorni_sett"
        data_str      = (request.form.get('data') or
                         request.form.get('data_range_ini') or
                         request.form.get('data_per_ini') or '')
        data_fine_str = (request.form.get('data_fine') or
                         request.form.get('data_range_fin') or
                         request.form.get('data_per_fin') or
                         data_str)
        giorni_sett_raw = request.form.getlist('giorni_sett')   # es. ['1','3','5'] per periodicita
        giorni_sett = [int(g) for g in giorni_sett_raw if g.isdigit()]  # 1=lun ... 6=sab
        id_docente      = int(request.form['id_docente'])
        # Ore singole non consecutive dal nuovo form
        ore_scelte_raw  = request.form.getlist('ore_scelte')
        if ore_scelte_raw:
            ore_scelte  = sorted(int(o) for o in ore_scelte_raw if str(o).isdigit())
            ora_inizio  = ore_scelte[0]
            ora_fine    = ore_scelte[-1]
        else:
            # Intera giornata (nessuna selezione o "Tutta")
            ore_scelte  = []
            ora_inizio  = int(request.form.get('ora_inizio', 1))
            ora_fine    = int(request.form.get('ora_fine', 9))
        motivo          = request.form.get('motivo', 'malattia')
        note            = request.form.get('note', '').strip()
        note_disp       = request.form.get('note_display', '').strip()
        # Permesso orario per att. istituzionali — campi HH:MM opzionali
        ora_ist_ini     = request.form.get('ora_ist_inizio', '').strip() or None
        ora_ist_fine_v  = request.form.get('ora_ist_fine', '').strip() or None
        data_inizio     = date.fromisoformat(data_str)
        data_fine_d     = date.fromisoformat(data_fine_str)

        # Costruisce lista di date lavorative nel periodo
        if data_fine_d < data_inizio:
            data_fine_d = data_inizio
        date_list = []
        cur = data_inizio
        while cur <= data_fine_d:
            wd = cur.weekday()  # 0=lun, 6=dom
            if wd < 6:  # escludi domenica
                # Per periodicita: includi solo i giorni selezionati (1=lun...6=sab weekday+1)
                if not giorni_sett or (wd + 1) in giorni_sett:
                    date_list.append(cur)
            cur += timedelta(days=1)

        assenze_create = 0
        supplenze_create = 0
        docente = Docente.query.get(id_docente)

        for data_ins in date_list:
            # Sospensione didattica: non genera supplenze ma permette l'assenza
            sosp = is_sospensione(data_ins)
            classe_libera = 'classe_libera' in request.form or motivo == 'classe_libera'
            # Per periodicità: filtra ore_scelte in base all'orario del docente quel giorno
            giorno_ins = data_ins.weekday()
            a = Assenza(
                id_docente    = id_docente,
                data          = data_ins,
                ora_inizio    = ora_inizio,
                ora_fine      = ora_fine,
                motivo        = motivo,
                motivo_interno= request.form.get('motivo_interno','').strip() or None,
                classe_libera = classe_libera,
                note_interne  = note,
                ora_ist_inizio= ora_ist_ini if motivo == 'permesso_orario' else None,
                ora_ist_fine  = ora_ist_fine_v if motivo == 'permesso_orario' else None,
            )
            db.session.add(a)
            db.session.flush()
            assenze_create += 1

            # N ore effettive: quelle singole selezionate, o il range
            n_ore_eff = len(ore_scelte) if ore_scelte else (ora_fine - ora_inizio + 1)

            # Movimento banca ore (solo cat.1)
            # Se permesso_orario con HH:MM istituzionale → non creare movimento standard
            # (verrà creato il permesso_ist con durata precisa subito dopo)
            if cat_impatta_banca(motivo) and not (motivo == 'permesso_orario' and ora_ist_ini and ora_ist_fine_v):
                colonna = cat_colonna_banca(motivo)
                m = MovimentoBancaOre(
                    id_docente  = id_docente,
                    data        = data_ins,
                    minuti      = -(n_ore_eff * 60),
                    tipo        = colonna,
                    descrizione = f'{motivo} — {n_ore_eff}h ({data_ins.isoformat()})',
                )
                db.session.add(m)

            # Permesso orario su att. istituzionali → movimento separato permesso_ist
            if motivo == 'permesso_orario' and ora_ist_ini and ora_ist_fine_v:
                try:
                    h_ini, m_ini = map(int, ora_ist_ini.split(':'))
                    h_fin, m_fin = map(int, ora_ist_fine_v.split(':'))
                    minuti_ist = (h_fin * 60 + m_fin) - (h_ini * 60 + m_ini)
                    if minuti_ist > 0:
                        db.session.add(MovimentoBancaOre(
                            id_docente  = id_docente,
                            data        = data_ins,
                            minuti      = -minuti_ist,
                            tipo        = 'permesso_ist',
                            descrizione = f'Permesso att.ist. {ora_ist_ini}–{ora_ist_fine_v}',
                        ))
                except Exception:
                    pass

            # Supplenze scoperte automatiche
            if cat_genera_supplenza(motivo):
                assegnabile = cat_assegnabile(motivo)
                supplenze_create += _genera_supplenze(
                    id_docente, data_ins, ora_inizio, ora_fine,
                    assegnabile, note_disp,
                    ore_singole=ore_scelte if ore_scelte else None
                )

        # Scambio orario: crea ScambioOrario + ScambioSlot (non genera supplenza standard)
        if motivo == 'scambio_orario':
            cede_date    = request.form.getlist('scambio_cede_data[]')
            cede_ore     = request.form.getlist('scambio_cede_ora[]')
            cede_classi  = request.form.getlist('scambio_cede_classe[]')
            doc_b_ids    = request.form.getlist('scambio_doc_b[]')
            rec_date     = request.form.getlist('scambio_rec_data[]')
            rec_ore      = request.form.getlist('scambio_rec_ora[]')
            rec_classi   = request.form.getlist('scambio_rec_classe[]')

            for i, cede_d in enumerate(cede_date):
                if not cede_d or not cede_ore[i:i+1]:
                    continue
                id_b = int(doc_b_ids[i]) if doc_b_ids[i:i+1] and doc_b_ids[i] else None
                if not id_b:
                    continue
                sc = ScambioOrario(
                    id_docente_a = id_docente,
                    id_docente_b = id_b,
                    tipo         = 'scambio',
                    note         = note,
                )
                db.session.add(sc)
                db.session.flush()

                # Slot cede
                slot_cede = ScambioSlot(
                    id_scambio = sc.id,
                    tipo_slot  = 'cede',
                    data       = date.fromisoformat(cede_d),
                    ora        = int(cede_ore[i]),
                    classe     = cede_classi[i] if cede_classi[i:i+1] else '',
                )
                db.session.add(slot_cede)

                # Supplenza con sostituto già nominato
                from models.supplenza import Supplenza as _Sup
                dup = _Sup.query.filter_by(
                    data=slot_cede.data, id_assente=id_docente, ora=slot_cede.ora
                ).first()
                if not dup:
                    db.session.add(_Sup(
                        data         = slot_cede.data,
                        ora          = slot_cede.ora,
                        classe       = slot_cede.classe,
                        id_assente   = id_docente,
                        id_sostituto = id_b,
                        tipo         = 'scambio',
                        stato        = 'assegnata',
                        origine      = 'scambio',
                        note         = f'Scambio id={sc.id}',
                    ))

                # Slot recupero (opzionale)
                r_d = rec_date[i] if rec_date[i:i+1] else ''
                r_o = rec_ore[i]  if rec_ore[i:i+1]  else ''
                if r_d and r_o:
                    db.session.add(ScambioSlot(
                        id_scambio = sc.id,
                        tipo_slot  = 'recupero',
                        data       = date.fromisoformat(r_d),
                        ora        = int(r_o),
                        classe     = rec_classi[i] if rec_classi[i:i+1] else '',
                    ))

        # Marca automaticamente giustificato nelle attività istituzionali del giorno
        # Recupera gli id delle assenze appena create per il collegamento
        assenze_create_map = {a.data: a.id for a in Assenza.query.filter(
            Assenza.id_docente == id_docente,
            Assenza.data.in_(date_list)
        ).all()}
        for data_sing in date_list:
            ass_id = assenze_create_map.get(data_sing)
            if motivo == 'permesso_orario':
                # Usa orario assoluto HH:MM se disponibile (att. istituzionali)
                # altrimenti usa i chip numerici (ore scolastiche mattutine)
                if ora_ist_ini and ora_ist_fine_v:
                    _sync_presenza_ist_assoluto(
                        id_docente, data_sing,
                        ora_ist_ini, ora_ist_fine_v,
                        'giustificato', id_assenza=ass_id
                    )
                else:
                    _sync_presenza_ist_parziale(
                        id_docente, data_sing, ora_inizio, ora_fine,
                        'giustificato', id_assenza=ass_id
                    )
            else:
                _sync_presenza_ist(id_docente, [data_sing], 'giustificato',
                                   id_assenza=ass_id)

        db.session.commit()

        if assenze_create == 1:
            msg = f'Registrato: {docente.cognome} — {motivo}.'
        else:
            msg = (f'Registrate {assenze_create} assenze: {docente.cognome} — {motivo} '
                   f'dal {data_inizio.strftime("%d/%m")} al {data_fine_d.strftime("%d/%m/%Y")}.')
        if supplenze_create:
            msg += f' Generate {supplenze_create} variazioni.'
        flash(msg, 'success')
        return redirect(url_for('dashboard.index', data=data_str))

    oggi     = date.today()
    data_str = request.args.get('data', oggi.isoformat())
    docenti  = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    from flask import session
    ruolo = session.get('ruolo', 'segreteria')

    # Tipi visivi per i pulsanti del form
    # (valore, emoji, etichetta)
    tipi_visivi = [
        ('malattia',             '🤒', 'Malattia'),
        ('permesso_personale',   '📄', 'Permesso'),
        ('lutto',                '🕯', 'Lutto'),
        ('matrimonio',           '💍', 'Matrimonio'),
        ('permesso_sindacale',   '🗣', 'Sindacale'),
        ('permesso_orario',      '📋', 'Perm. orario'),
        ('ferie',                '🏖', 'Ferie'),
        ('classe_libera',        '🚫', 'Cl. libera'),
        ('scambio_orario',       '🔄', 'Scambio ore'),
        ('ed_civica',            '📚', 'Ed. Civica'),
        ('formazione',           '🎓', 'Formazione'),
        ('attivita_istituzionale','🏫', 'Att. ist.'),
    ]

    # Orari docenti per JS: { "id_giorno": [ore] }
    from models.orario_docente import OrarioDocente
    orari_docenti = {}
    for slot in OrarioDocente.query.all():
        key = f'{slot.id_docente}_{slot.giorno}'
        orari_docenti.setdefault(key, [])
        if slot.ora not in orari_docenti[key]:
            orari_docenti[key].append(slot.ora)

    # Utilizzi CCNL anno scolastico corrente
    anno = oggi.year if oggi.month >= 9 else oggi.year - 1
    inizio_as = date(anno, 9, 1)
    fine_as   = date(anno + 1, 8, 31)
    utilizzi_ccnl = {}
    for motivo_k, limiti in LIMITI_CCNL.items():
        # Determina l'unità del limite per questo motivo
        # Se il limite è in 'ore' contiamo le ore, altrimenti i giorni
        limite_ref  = list(limiti.values())[0] if limiti else {}
        unita       = limite_ref.get('u', 'giorni') if isinstance(limite_ref, dict) else 'giorni'
        for a in Assenza.query.filter(
            Assenza.motivo == motivo_k,
            Assenza.data >= inizio_as,
            Assenza.data <= fine_as
        ).all():
            if unita == 'ore':
                # Limite giornaliero: chiave include la data per confronto intragiornaliero
                chiave = f'{a.id_docente}_{motivo_k}_{a.data.isoformat()}'
                n_ore = a.n_ore if hasattr(a, 'n_ore') else (a.ora_fine - a.ora_inizio + 1)
                utilizzi_ccnl[chiave] = utilizzi_ccnl.get(chiave, 0) + n_ore
            else:
                chiave = f'{a.id_docente}_{motivo_k}'
                utilizzi_ccnl[chiave] = utilizzi_ccnl.get(chiave, 0) + 1

    # Sospensioni: passa set di date sospese per avviso JS nel form
    try:
        from models.sospensione import SospensioneDidattica
        sosp_list = SospensioneDidattica.query.all()
        date_sospese = {}
        for s in sosp_list:
            cur = s.data_inizio
            while cur <= s.data_fine:
                date_sospese[cur.isoformat()] = s.descrizione
                cur += timedelta(days=1)
    except Exception:
        date_sospese = {}

    # Sospensione del giorno selezionato
    sospensione_oggi = date_sospese.get(data_str)

    # Eventi istituzionali del giorno selezionato (per alert nel form)
    try:
        eventi_ist_giorno = AttivitaIst.query.filter_by(
            data=date.fromisoformat(data_str)).all()
    except Exception:
        eventi_ist_giorno = []

    return render_template('assenza_form.html',
        docenti=docenti,
        data_sel=data_str,
        ore_list=range(1, 10),
        tipi_visivi=tipi_visivi,
        orari_docenti_json=orari_docenti,
        utilizzi_ccnl=utilizzi_ccnl,
        ruolo_utente=ruolo,
        eventi_ist_giorno=eventi_ist_giorno,
        date_sospese=date_sospese,
        sospensione_oggi=sospensione_oggi,
    )


@assenze_bp.route('/assenze/<int:id>/elimina', methods=['POST'])
def elimina(id):
    a = Assenza.query.get_or_404(id)
    data_str   = a.data.isoformat()
    id_docente = a.id_docente

    # Rimuovi movimenti banca ore collegati a questa assenza
    # Cerca per id_docente + data + tipi negativi (non supplenze)
    TIPI_ASSENZA = ('permesso', 'assenza', 'permesso_orario', 'permesso_ist', 'civica',
                    'ed_civica', 'malattia', 'assemblea', 'formazione',
                    'viaggio', 'progetto', 'riunione', 'sciopero', 'altro')
    MovimentoBancaOre.query.filter(
        MovimentoBancaOre.id_docente == id_docente,
        MovimentoBancaOre.data == a.data,
        MovimentoBancaOre.tipo.in_(TIPI_ASSENZA),
        MovimentoBancaOre.minuti < 0
    ).delete(synchronize_session=False)

    # Annulla supplenze generate automaticamente
    auto = Supplenza.query.filter_by(
        data=a.data, id_assente=id_docente, origine='automatica'
    ).filter(Supplenza.stato.in_(['scoperta', 'non_assegnabile'])).all()
    n = len(auto)
    for s in auto:
        db.session.delete(s)

    # Ripristina presenze istituzionali collegate a questa assenza
    _ripristina_presenza_ist(id_docente, [a.data], id_assenza=id)

    db.session.delete(a)
    db.session.commit()

    flash(f'Assenza rimossa.' + (f' Rimosse {n} variazioni collegate.' if n else ''), 'warning')
    return redirect(url_for('dashboard.index', data=data_str))


def _sync_presenza_ist(id_docente, date_list, stato, id_assenza=None):
    """
    Per ogni data in date_list, se il docente è partecipante a un'attività
    istituzionale il cui orario si sovrappone all'assenza, aggiorna solo la sua
    presenza — senza toccare le presenze degli altri partecipanti.
    """
    # Recupera l'assenza per conoscere le ore coperte
    ass_ora_ini = ass_ora_fine = None
    if id_assenza:
        from models.assenza import Assenza as AssenzaM
        a = AssenzaM.query.get(id_assenza)
        if a:
            ass_ora_ini = a.ora_inizio
            ass_ora_fine = a.ora_fine

    for data in date_list:
        eventi = AttivitaIst.query.filter_by(data=data).all()
        for ev in eventi:
            # Verifica sovrapposizione: assenza a ore scolastiche (1-9)
            # vs evento a orario HH:MM
            if ass_ora_ini and ass_ora_fine and ev.ora_inizio and ev.ora_fine:
                # Mappa ora scolastica → HH:MM (ora N inizia alle 8:00 + (N-1)*55min)
                def _ora_to_min(n):
                    return 480 + (n - 1) * 60  # approssimazione: 8:00 + (N-1)h
                def _hhmm_to_min(s):
                    try:
                        h, m = map(int, s.split(':'))
                        return h * 60 + m
                    except Exception:
                        return None
                ass_ini_m = _ora_to_min(ass_ora_ini)
                ass_fin_m = _ora_to_min(ass_ora_fine + 1)
                ev_ini_m  = _hhmm_to_min(ev.ora_inizio)
                ev_fin_m  = _hhmm_to_min(ev.ora_fine)
                if ev_ini_m and ev_fin_m:
                    # Nessuna sovrapposizione → non toccare
                    if ass_fin_m <= ev_ini_m or ass_ini_m >= ev_fin_m:
                        continue

            # Verifica che il docente sia partecipante
            part = AttivitaIstPartecipante.query.filter_by(
                id_attivita=ev.id, id_docente=id_docente).first()
            if not part:
                continue

            # Aggiorna SOLO la presenza di questo docente
            pres = AttivitaIstPresenza.query.filter_by(
                id_attivita=ev.id, id_docente=id_docente).first()
            if pres:
                pres.stato = stato
                if id_assenza:
                    pres.id_assenza_collegata = id_assenza
            else:
                db.session.add(AttivitaIstPresenza(
                    id_attivita=ev.id,
                    id_docente=id_docente,
                    stato=stato,
                    note='Auto — assenza registrata',
                    id_assenza_collegata=id_assenza,
                ))


def _ripristina_presenza_ist(id_docente, date_list, id_assenza=None):
    """
    Ripristina 'presente' nelle presenze istituzionali collegate a questa assenza.
    Chiamata quando un'assenza viene cancellata o spostata di data.
    """
    for data in date_list:
        eventi = AttivitaIst.query.filter_by(data=data).all()
        for ev in eventi:
            pres = AttivitaIstPresenza.query.filter_by(
                id_attivita=ev.id, id_docente=id_docente).first()
            if not pres:
                continue
            # Ripristina solo se la presenza era stata marcata automaticamente
            # da questa assenza (o da qualsiasi assenza se id_assenza non specificato)
            if id_assenza is None or pres.id_assenza_collegata == id_assenza:
                pres.stato = 'presente'
                pres.id_assenza_collegata = None
                pres.note = None


def _sync_presenza_ist_assoluto(id_docente, data, ini_str, fin_str,
                                   stato, id_assenza=None):
    """
    Marca presenze istituzionali usando orario assoluto HH:MM.
    Più preciso di _parziale: confronto diretto con l'orario dell'evento.
    """
    def _t(s):
        try:
            h, m = map(int, s.split(':'))
            return h * 60 + m
        except Exception:
            return None

    perm_ini = _t(ini_str)
    perm_fin = _t(fin_str)
    if perm_ini is None or perm_fin is None:
        return

    eventi = AttivitaIst.query.filter_by(data=data).all()
    for ev in eventi:
        part = AttivitaIstPartecipante.query.filter_by(
            id_attivita=ev.id, id_docente=id_docente).first()
        if not part:
            continue
        if ev.ora_inizio and ev.ora_fine:
            ev_ini = _t(ev.ora_inizio)
            ev_fin = _t(ev.ora_fine)
            if ev_ini is not None and ev_fin is not None:
                if perm_fin <= ev_ini or perm_ini >= ev_fin:
                    continue  # nessuna sovrapposizione
        pres = AttivitaIstPresenza.query.filter_by(
            id_attivita=ev.id, id_docente=id_docente).first()
        if pres:
            pres.stato = stato
            if id_assenza:
                pres.id_assenza_collegata = id_assenza
        else:
            db.session.add(AttivitaIstPresenza(
                id_attivita=ev.id,
                id_docente=id_docente,
                stato=stato,
                note=f'Auto — permesso ist. {ini_str}–{fin_str}',
                id_assenza_collegata=id_assenza,
            ))


def _sync_presenza_ist_parziale(id_docente, data, ora_perm_ini,
                                  ora_perm_fine, stato, id_assenza=None):
    """
    Come _sync_presenza_ist ma solo per le attività istituzionali
    il cui orario si sovrappone alle ore del permesso.
    Usato per permesso_orario: non tocca le riunioni pomeridiane
    se il permesso è solo mattutino.
    """
    def _t(ora_str):
        """Converte stringa 'HH:MM' in minuti dall'inizio giornata."""
        try:
            h, m = map(int, ora_str.split(':'))
            return h * 60 + m
        except Exception:
            return None

    eventi = AttivitaIst.query.filter_by(data=data).all()
    for ev in eventi:
        part = AttivitaIstPartecipante.query.filter_by(
            id_attivita=ev.id, id_docente=id_docente).first()
        if not part:
            continue

        # Verifica sovrapposizione oraria
        # Le ore del permesso sono in numeri d'ora (1-9)
        # L'orario dell'evento è in formato HH:MM
        # Mappa semplice: ora 1=8:00, ora 2=9:00, ... ora 9=16:00
        # Se l'evento non ha orario → considera che si sovrappone (cautela)
        if ev.ora_inizio and ev.ora_fine:
            ev_ini = _t(ev.ora_inizio)
            ev_fin = _t(ev.ora_fine)
            if ev_ini is not None and ev_fin is not None:
                # Converti ore permesso in minuti (ora 1 = 8:00 = 480 min)
                perm_ini_min = (ora_perm_ini - 1) * 60 + 480
                perm_fin_min = ora_perm_fine * 60 + 480
                # Nessuna sovrapposizione → non toccare
                if perm_fin_min <= ev_ini or perm_ini_min >= ev_fin:
                    continue

        pres = AttivitaIstPresenza.query.filter_by(
            id_attivita=ev.id, id_docente=id_docente).first()
        if pres:
            pres.stato = stato
            if id_assenza:
                pres.id_assenza_collegata = id_assenza
        else:
            db.session.add(AttivitaIstPresenza(
                id_attivita=ev.id,
                id_docente=id_docente,
                stato=stato,
                note='Auto — permesso orario sovrapposto',
                id_assenza_collegata=id_assenza,
            ))


def _genera_supplenze(id_docente, data, ora_inizio, ora_fine,
                       assegnabile, note_display, ore_singole=None):
    """ore_singole: lista di ore specifiche (non consecutive); None = usa range."""
    # Non generare supplenze in giorni di sospensione didattica
    if is_sospensione(data):
        return 0
    giorno_num = GIORNI_SETTIMANA.get(data.weekday())
    if giorno_num is None:
        return 0

    if ore_singole:
        # Ore specifiche selezionate — prendi solo quelle nell'orario
        slots = OrarioDocente.query.filter_by(
            id_docente=id_docente, giorno=giorno_num
        ).filter(
            OrarioDocente.ora.in_(ore_singole)
        ).all()
    else:
        slots = OrarioDocente.query.filter_by(
            id_docente=id_docente, giorno=giorno_num
        ).filter(
            OrarioDocente.ora >= ora_inizio,
            OrarioDocente.ora <= ora_fine,
        ).all()

    # Orario spezzato: esclude ore dopo l'uscita anticipata del docente
    from models.docente import Docente as _Doc
    _doc = _Doc.query.get(id_docente)
    ora_uscita_map = (_doc.ora_uscita_map if _doc and hasattr(_doc, 'ora_uscita_map') else {}) or {}
    ora_max = ora_uscita_map.get(giorno_num)  # None = nessun limite
    if ora_max is not None:
        slots = [s for s in slots if s.ora <= ora_max]

    stato = 'scoperta' if assegnabile else 'non_assegnabile'
    count = 0

    # Recupera attività attive quel giorno
    from models.attivita_fuori_aula import AttivitaFuoriAula
    att_oggi = AttivitaFuoriAula.query.filter(
        AttivitaFuoriAula.data_inizio <= data,
        AttivitaFuoriAula.data_fine   >= data,
        AttivitaFuoriAula.stato == 'attiva'
    ).all()

    for slot in slots:
        if not slot.classe or slot.classe in ('---', '-x-', '', 'POTENZIAMENTO') or slot.tipo_ora == 'potenziamento':
            continue

        # Se la classe di questo slot è fuori aula in quell'ora → non serve sostituto
        classe_coperta = False
        for att in att_oggi:
            if slot.classe not in att.classi_list:
                continue
            if att.ricorrenza == 'settimanale':
                if data.weekday() not in att.giorni_sett_list:
                    continue
            # Verifica slot dettagliati FSL (ore per accompagnatore)
            from models.attivita_accompagnatore import AttivitaAccompagnatore
            slots_det = AttivitaAccompagnatore.query.filter_by(id_attivita=att.id).first()
            if slots_det:
                # Ha calendario dettagliato — la classe è fuori aula tutto il periodo
                classe_coperta = True
                break
            if att.ora_inizio and att.ora_fine:
                if att.ora_inizio <= slot.ora <= att.ora_fine:
                    classe_coperta = True
                    break
            else:
                # Nessuna ora definita = tutta la giornata
                classe_coperta = True
                break
        if classe_coperta:
            continue

        # Controlla anche se il docente è accompagnatore e ha LA STESSA classe in quell'ora
        # (es. CANTARELLA accompagna 5A RIM ed ha 5A RIM alla 1a ora -> non serve sostituto)
        for att in att_oggi:
            if slot.classe in att.classi_list:
                continue  # già gestito sopra
            # Il docente è accompagnatore di questa attività?
            acc_ids = {d.id for d in att.accompagnatori}
            if id_docente not in acc_ids:
                continue
            # Il docente ha la classe fuori aula in quell'ora?
            if att.ora_inizio and att.ora_fine:
                if not (att.ora_inizio <= slot.ora <= att.ora_fine):
                    continue
            # Il docente ha UNA QUALSIASI classe fuori aula in quell'ora
            ha_classe_fuori = any(
                s2.classe in att.classi_list
                for s2 in (OrarioDocente.query.filter_by(
                    id_docente=id_docente, giorno=GIORNI_SETTIMANA.get(data.weekday(), 0),
                    ora=slot.ora
                ).all())
            )
            if ha_classe_fuori:
                classe_coperta = True
                break
        if classe_coperta:
            continue

        # ── COMPRESENZA: salta se c'è un compagno presente (non assente né indisponibile)
        from modules.compresenze import ha_compagno_presente
        if ha_compagno_presente(id_docente, giorno_num, slot.ora, slot.classe, data):
            continue  # c'è ancora un docente in aula — non serve sostituto

        # Evita duplicati
        if Supplenza.query.filter_by(
            data=data, id_assente=id_docente, ora=slot.ora
        ).first():
            continue

        s = Supplenza(
            data         = data,
            ora          = slot.ora,
            classe       = slot.classe,
            id_assente   = id_docente,
            tipo         = 'recupero',
            stato        = stato,
            origine      = 'automatica',
            note_display = note_display or (
                'NON ASSEGNABILE' if not assegnabile else ''
            ),
            note         = f'Auto — {slot.materia or ""}',
        )
        db.session.add(s)
        count += 1

    return count


@assenze_bp.route('/assenze/<int:id>/modifica', methods=['GET', 'POST'])
def modifica(id):
    a = Assenza.query.get_or_404(id)
    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()

    if request.method == 'POST':
        # Salva i valori vecchi per pulizia
        old_docente   = a.id_docente
        old_data      = a.data
        old_ora_inizio = a.ora_inizio
        old_ora_fine  = a.ora_fine
        old_motivo    = a.motivo

        # Nuovi valori dal form
        new_docente   = int(request.form["id_docente"])
        # Anche in modifica il form usa "data" (sempre singolo giorno) — gestito correttamente
        new_data      = date.fromisoformat(request.form["data"])
        # Ore singole non consecutive
        ore_scelte_raw = request.form.getlist("ore_scelte")
        if ore_scelte_raw:
            new_ore_scelte  = sorted(int(o) for o in ore_scelte_raw if str(o).isdigit())
            new_ora_inizio  = new_ore_scelte[0]
            new_ora_fine    = new_ore_scelte[-1]
        else:
            new_ore_scelte  = []
            new_ora_inizio  = int(request.form.get("ora_inizio", 1))
            new_ora_fine    = int(request.form.get("ora_fine", 9))
        new_motivo    = request.form.get("motivo", a.motivo)
        new_note      = request.form.get("note_interne", "").strip()
        note_disp     = request.form.get("note_display", "").strip()

        TIPI_ASSENZA = ("permesso", "assenza", "permesso_orario", "permesso_ist", "civica",
                        "ed_civica", "malattia", "assemblea", "formazione",
                        "viaggio", "progetto", "riunione", "sciopero", "altro")

        # 1. Elimina movimenti banca ore vecchi collegati
        MovimentoBancaOre.query.filter(
            MovimentoBancaOre.id_docente == old_docente,
            MovimentoBancaOre.data == old_data,
            MovimentoBancaOre.tipo.in_(TIPI_ASSENZA),
            MovimentoBancaOre.minuti < 0
        ).delete(synchronize_session=False)

        # 2. Elimina supplenze automatiche vecchie (scoperte / non_assegnabili)
        auto_old = Supplenza.query.filter_by(
            data=old_data, id_assente=old_docente, origine="automatica"
        ).filter(Supplenza.stato.in_(["scoperta", "non_assegnabile"])).all()
        for s in auto_old:
            db.session.delete(s)

        # 3. Aggiorna l'assenza con i nuovi valori
        a.id_docente   = new_docente
        a.data         = new_data
        a.ora_inizio   = new_ora_inizio
        a.ora_fine     = new_ora_fine
        a.motivo       = new_motivo
        a.note_interne = new_note
        db.session.flush()

        # 4. Ricrea movimento banca ore se necessario
        if cat_impatta_banca(new_motivo):
            colonna = cat_colonna_banca(new_motivo)
            n_ore = len(new_ore_scelte) if new_ore_scelte else (new_ora_fine - new_ora_inizio + 1)
            db.session.add(MovimentoBancaOre(
                id_docente  = new_docente,
                data        = new_data,
                minuti      = -(n_ore * 60),
                tipo        = colonna,
                descrizione = f"{new_motivo} — {n_ore}h ({new_data.isoformat()})",
            ))

        # 5. Rigenera supplenze automatiche
        n_sup = 0
        if cat_genera_supplenza(new_motivo):
            assegnabile = cat_assegnabile(new_motivo)
            n_sup = _genera_supplenze(
                new_docente, new_data, new_ora_inizio, new_ora_fine,
                assegnabile, note_disp,
                ore_singole=new_ore_scelte if new_ore_scelte else None
            )

        # Ripristina presenze sulla vecchia data se la data è cambiata o assenza rimossa
        vecchia_assenza = Assenza.query.filter_by(
            id_docente=old_docente, data=old_data).first()
        if old_data != new_data or old_docente != new_docente:
            _ripristina_presenza_ist(old_docente, [old_data],
                                     id_assenza=vecchia_assenza.id if vecchia_assenza else None)
        # Marca giustificato sulla nuova data
        nuova_ass = Assenza.query.filter_by(
            id_docente=new_docente, data=new_data).first()
        ass_id_new = nuova_ass.id if nuova_ass else None
        if new_motivo == 'permesso_orario':
            _sync_presenza_ist_parziale(
                new_docente, new_data, new_ora_inizio, new_ora_fine,
                'giustificato', id_assenza=ass_id_new
            )
        else:
            _sync_presenza_ist(new_docente, [new_data], 'giustificato',
                               id_assenza=ass_id_new)
        db.session.commit()
        msg = "Assenza aggiornata."
        if n_sup:
            msg += f" Rigenerate {n_sup} variazioni supplenze."
        flash(msg, "success")
        next_url = request.form.get("next") or url_for("dashboard.index", data=new_data.isoformat())
        return redirect(next_url)

    from flask import session
    ruolo = session.get('ruolo', 'segreteria')
    tipi_visivi = [
        ('malattia',             '🤒', 'Malattia'),
        ('permesso_personale',   '📄', 'Permesso'),
        ('lutto',                '🕯', 'Lutto'),
        ('matrimonio',           '💍', 'Matrimonio'),
        ('permesso_sindacale',   '🗣', 'Sindacale'),
        ('permesso_orario',      '📋', 'Perm. orario'),
        ('ferie',                '🏖', 'Ferie'),
        ('classe_libera',        '🚫', 'Cl. libera'),
        ('scambio_orario',       '🔄', 'Scambio ore'),
        ('ed_civica',            '📚', 'Ed. Civica'),
        ('formazione',           '🎓', 'Formazione'),
        ('attivita_istituzionale','🏫', 'Att. ist.'),
    ]
    orari_docenti = {}
    for slot in OrarioDocente.query.all():
        key = f'{slot.id_docente}_{slot.giorno}'
        orari_docenti.setdefault(key, [])
        if slot.ora not in orari_docenti[key]:
            orari_docenti[key].append(slot.ora)
    anno = date.today().year if date.today().month >= 9 else date.today().year - 1
    utilizzi_ccnl = {}
    for motivo_k, limiti in LIMITI_CCNL.items():
        limite_ref = list(limiti.values())[0] if limiti else {}
        unita      = limite_ref.get('u', 'giorni') if isinstance(limite_ref, dict) else 'giorni'
        for ass in Assenza.query.filter(
            Assenza.motivo == motivo_k,
            Assenza.id != a.id,
            Assenza.data >= date(anno, 9, 1),
            Assenza.data <= date(anno + 1, 8, 31)
        ).all():
            if unita == 'ore':
                chiave = f'{ass.id_docente}_{motivo_k}_{ass.data.isoformat()}'
                n_ore = ass.n_ore if hasattr(ass, 'n_ore') else (ass.ora_fine - ass.ora_inizio + 1)
                utilizzi_ccnl[chiave] = utilizzi_ccnl.get(chiave, 0) + n_ore
            else:
                chiave = f'{ass.id_docente}_{motivo_k}'
                utilizzi_ccnl[chiave] = utilizzi_ccnl.get(chiave, 0) + 1

    # Sospensioni: passa set di date sospese per avviso JS nel form
    try:
        from models.sospensione import SospensioneDidattica
        sosp_list = SospensioneDidattica.query.all()
        date_sospese = {}
        for s in sosp_list:
            cur = s.data_inizio
            while cur <= s.data_fine:
                date_sospese[cur.isoformat()] = s.descrizione
                cur += timedelta(days=1)
    except Exception:
        date_sospese = {}

    # Sospensione del giorno selezionato
    sospensione_oggi = date_sospese.get(a.data.isoformat())

    # Eventi istituzionali del giorno selezionato (per alert nel form)
    try:
        eventi_ist_giorno = AttivitaIst.query.filter_by(data=a.data).all()
    except Exception:
        eventi_ist_giorno = []

    return render_template("assenza_form.html",
        assenza=a,
        docenti=docenti,
        data_sel=a.data.isoformat(),
        ore_list=range(1, 10),
        tipi_visivi=tipi_visivi,
        orari_docenti_json=orari_docenti,
        utilizzi_ccnl=utilizzi_ccnl,
        ruolo_utente=ruolo,
        eventi_ist_giorno=eventi_ist_giorno,
        date_sospese=date_sospese,
        sospensione_oggi=sospensione_oggi,
        next=request.args.get("next", ""))
