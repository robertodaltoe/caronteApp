"""
Business logic per la registrazione delle assenze docenti, estratta dalla
route routes/assenze.py::nuova() (che era arrivata a ~320 righe mescolando
parsing del form, scrittura sul DB e preparazione della pagina).

Contiene anche le funzioni di supporto già usate da nuova()/elimina()/
modifica() (sincronizzazione presenze istituzionali, generazione
supplenze scoperte): erano già a livello di modulo in routes/assenze.py,
solo spostate qui insieme alla logica che le usa.
"""
from datetime import date, timedelta
from models import db
from models.assenza import (
    Assenza, cat_impatta_banca, cat_colonna_banca, cat_genera_supplenza, cat_assegnabile,
    MOTIVI_RISERVATI, RUOLI_MOTIVO_SPECIFICO,
)
from models.movimento_banca_ore import MovimentoBancaOre
from models.orario_docente import OrarioDocente
from models.scambio_orario import ScambioOrario, ScambioSlot
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante, AttivitaIstPresenza
from models.supplenza import Supplenza
from modules.auto_sync import registra_eliminazione

GIORNI_SETTIMANA = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5}  # weekday -> giorno orario


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


def _sync_presenza_ist(id_docente, date_list, stato, id_assenza=None):
    """
    Per ogni data in date_list, se il docente è partecipante a un'attività
    istituzionale il cui orario si sovrappone all'assenza, aggiorna solo la sua
    presenza — senza toccare le presenze degli altri partecipanti.
    """
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
            if ass_ora_ini and ass_ora_fine and ev.ora_inizio and ev.ora_fine:
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
                    if ass_fin_m <= ev_ini_m or ass_ini_m >= ev_fin_m:
                        continue

            part = AttivitaIstPartecipante.query.filter_by(
                id_attivita=ev.id, id_docente=id_docente).first()
            if not part:
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

        if ev.ora_inizio and ev.ora_fine:
            ev_ini = _t(ev.ora_inizio)
            ev_fin = _t(ev.ora_fine)
            if ev_ini is not None and ev_fin is not None:
                perm_ini_min = (ora_perm_ini - 1) * 60 + 480
                perm_fin_min = ora_perm_fine * 60 + 480
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
    if is_sospensione(data):
        return 0
    giorno_num = GIORNI_SETTIMANA.get(data.weekday())
    if giorno_num is None:
        return 0

    if ore_singole:
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

    from models.docente import Docente as _Doc
    _doc = _Doc.query.get(id_docente)
    ora_uscita_map = (_doc.ora_uscita_map if _doc and hasattr(_doc, 'ora_uscita_map') else {}) or {}
    ora_max = ora_uscita_map.get(giorno_num)
    if ora_max is not None:
        slots = [s for s in slots if s.ora <= ora_max]

    stato = 'scoperta' if assegnabile else 'non_assegnabile'
    count = 0

    from models.attivita_fuori_aula import AttivitaFuoriAula
    att_oggi = AttivitaFuoriAula.query.filter(
        AttivitaFuoriAula.data_inizio <= data,
        AttivitaFuoriAula.data_fine   >= data,
        AttivitaFuoriAula.stato == 'attiva'
    ).all()

    for slot in slots:
        if not slot.classe or slot.classe in ('---', '-x-', '', 'POTENZIAMENTO') or slot.tipo_ora == 'potenziamento':
            continue

        classe_coperta = False
        for att in att_oggi:
            if slot.classe not in att.classi_list:
                continue
            if att.ricorrenza == 'settimanale':
                if data.weekday() not in att.giorni_sett_list:
                    continue
            from models.attivita_accompagnatore import AttivitaAccompagnatore
            slots_det = AttivitaAccompagnatore.query.filter_by(id_attivita=att.id).first()
            if slots_det:
                classe_coperta = True
                break
            if att.ora_inizio and att.ora_fine:
                if att.ora_inizio <= slot.ora <= att.ora_fine:
                    classe_coperta = True
                    break
            else:
                classe_coperta = True
                break
        if classe_coperta:
            continue

        for att in att_oggi:
            if slot.classe in att.classi_list:
                continue  # già gestito sopra
            acc_ids = {d.id for d in att.accompagnatori}
            if id_docente not in acc_ids:
                continue
            if att.ora_inizio and att.ora_fine:
                if not (att.ora_inizio <= slot.ora <= att.ora_fine):
                    continue
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
            continue

        if Supplenza.query.filter_by(
            data=data, id_assente=id_docente, ora=slot.ora
        ).first():
            continue

        from flask import g as _g
        _utente = _g.utente.username if getattr(_g, 'utente', None) else None
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
            creato_da    = _utente,
        )
        db.session.add(s)
        count += 1

    return count


def _gestisci_scambio_orario(form, id_docente, note):
    """
    Motivo 'scambio_orario': crea ScambioOrario + ScambioSlot per ogni riga
    del form, con la supplenza per la classe ceduta già assegnata al collega
    (non passa dal generatore automatico di supplenze scoperte).
    """
    cede_date    = form.getlist('scambio_cede_data[]')
    cede_ore     = form.getlist('scambio_cede_ora[]')
    cede_classi  = form.getlist('scambio_cede_classe[]')
    doc_b_ids    = form.getlist('scambio_doc_b[]')
    rec_date     = form.getlist('scambio_rec_data[]')
    rec_ore      = form.getlist('scambio_rec_ora[]')
    rec_classi   = form.getlist('scambio_rec_classe[]')

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

        slot_cede = ScambioSlot(
            id_scambio = sc.id,
            tipo_slot  = 'cede',
            data       = date.fromisoformat(cede_d),
            ora        = int(cede_ore[i]),
            classe     = cede_classi[i] if cede_classi[i:i+1] else '',
        )
        db.session.add(slot_cede)

        dup = Supplenza.query.filter_by(
            data=slot_cede.data, id_assente=id_docente, ora=slot_cede.ora
        ).first()
        if not dup:
            db.session.add(Supplenza(
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


def registra_assenze_form(form):
    """
    Orchestrazione completa della registrazione di una o più assenze dal
    form di routes/assenze.py::nuova() (POST): parsing delle date (singolo/
    range/periodico), creazione delle righe Assenza, movimenti banca ore,
    eventuale scambio orario, generazione supplenze scoperte automatiche,
    sincronizzazione delle presenze istituzionali collegate.

    Non fa commit né logging di audit: quello resta alla route chiamante,
    che ha anche il compito di costruire il messaggio flash e il redirect.

    Ritorna un dict con: data_str, data_inizio, data_fine_d, assenze_create,
    supplenze_create, docente.
    """
    data_str      = (form.get('data') or
                     form.get('data_range_ini') or
                     form.get('data_per_ini') or '')
    data_fine_str = (form.get('data_fine') or
                     form.get('data_range_fin') or
                     form.get('data_per_fin') or
                     data_str)
    giorni_sett_raw = form.getlist('giorni_sett')
    giorni_sett = [int(g) for g in giorni_sett_raw if g.isdigit()]
    id_docente      = int(form['id_docente'])
    ore_scelte_raw  = form.getlist('ore_scelte')
    if ore_scelte_raw:
        ore_scelte  = sorted(int(o) for o in ore_scelte_raw if str(o).isdigit())
        ora_inizio  = ore_scelte[0]
        ora_fine    = ore_scelte[-1]
    else:
        ore_scelte  = []
        ora_inizio  = int(form.get('ora_inizio', 1))
        ora_fine    = int(form.get('ora_fine', 9))
    motivo          = form.get('motivo', 'malattia')
    from flask import g as _g_ruolo
    _ruolo_reg = _g_ruolo.utente.ruolo if getattr(_g_ruolo, 'utente', None) else None
    if motivo in MOTIVI_RISERVATI and motivo != 'non_recuperabile' and _ruolo_reg not in RUOLI_MOTIVO_SPECIFICO:
        # Difesa lato server (oltre al form, che già non mostra queste
        # opzioni a chi non ha titolo — vedi contesto_form_assenza):
        # un ruolo non autorizzato non può registrare un motivo
        # specifico riservato, nemmeno forzando la richiesta POST.
        motivo = 'non_recuperabile'
    note            = form.get('note', '').strip()
    note_disp       = form.get('note_display', '').strip()
    ora_ist_ini     = form.get('ora_ist_inizio', '').strip() or None
    ora_ist_fine_v  = form.get('ora_ist_fine', '').strip() or None
    data_inizio     = date.fromisoformat(data_str)
    data_fine_d     = date.fromisoformat(data_fine_str)

    if data_fine_d < data_inizio:
        data_fine_d = data_inizio
    date_list = []
    cur = data_inizio
    while cur <= data_fine_d:
        wd = cur.weekday()
        if wd < 6:
            if not giorni_sett or (wd + 1) in giorni_sett:
                date_list.append(cur)
        cur += timedelta(days=1)

    assenze_create = 0
    supplenze_create = 0
    from models.docente import Docente
    docente = Docente.query.get(id_docente)

    from flask import g as _g
    _utente = _g.utente.username if getattr(_g, 'utente', None) else None

    for data_ins in date_list:
        sosp = is_sospensione(data_ins)
        classe_libera = 'classe_libera' in form or motivo == 'classe_libera'
        giorno_ins = data_ins.weekday()
        a = Assenza(
            id_docente    = id_docente,
            data          = data_ins,
            ora_inizio    = ora_inizio,
            ora_fine      = ora_fine,
            motivo        = motivo,
            classe_libera = classe_libera,
            note_interne  = note,
            ora_ist_inizio= ora_ist_ini if motivo == 'permesso_orario' else None,
            ora_ist_fine  = ora_ist_fine_v if motivo == 'permesso_orario' else None,
            creato_da     = _utente,
        )
        db.session.add(a)
        db.session.flush()
        assenze_create += 1

        n_ore_eff = len(ore_scelte) if ore_scelte else (ora_fine - ora_inizio + 1)

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

        if cat_genera_supplenza(motivo):
            assegnabile = cat_assegnabile(motivo)
            supplenze_create += _genera_supplenze(
                id_docente, data_ins, ora_inizio, ora_fine,
                assegnabile, note_disp,
                ore_singole=ore_scelte if ore_scelte else None
            )

    if motivo == 'scambio_orario':
        _gestisci_scambio_orario(form, id_docente, note)

    # Marca automaticamente giustificato nelle attività istituzionali del giorno
    assenze_create_map = {a.data: a.id for a in Assenza.query.filter(
        Assenza.id_docente == id_docente,
        Assenza.data.in_(date_list)
    ).all()}
    for data_sing in date_list:
        ass_id = assenze_create_map.get(data_sing)
        if motivo == 'permesso_orario':
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

    return {
        'data_str': data_str,
        'data_inizio': data_inizio,
        'data_fine_d': data_fine_d,
        'assenze_create': assenze_create,
        'supplenze_create': supplenze_create,
        'docente': docente,
    }


def contesto_form_nuova(data_str, ruolo=None):
    """Alias storico: pagina 'Nuova assenza' (nessuna assenza da escludere dal CCNL)."""
    return contesto_form_assenza(data_str, ruolo=ruolo)


# Motivi specifici "riservati" (vedi models/assenza.py::MOTIVI_RISERVATI):
# mostrati come pulsanti solo a chi ha titolo a conoscerli (DS/DSGA/
# segreteria). Chi non ha titolo (es. collaboratore del DS) vede al loro
# posto un solo pulsante generico 'non_recuperabile'.
_TIPI_VISIVI_SPECIFICI = [
    ('malattia',             '🤒', 'Malattia'),
    ('permesso_personale',   '📄', 'Permesso'),
    ('lutto',                '🕯', 'Lutto'),
    ('matrimonio',           '💍', 'Matrimonio'),
    ('permesso_sindacale',   '🗣', 'Sindacale'),
]
_TIPI_VISIVI_RISERVATO = [
    ('non_recuperabile',     '🔒', 'Non recuperabile'),
]
# Non sensibili: nessun problema di privacy, visibili identici a tutti.
_TIPI_VISIVI_COMUNI = [
    ('permesso_orario',      '📋', 'Perm. orario'),
    ('ferie',                '🏖', 'Ferie'),
    ('classe_libera',        '🚫', 'Cl. libera'),
    ('scambio_orario',       '🔄', 'Scambio ore'),
    ('ed_civica',            '📚', 'Ed. Civica'),
    ('formazione',           '🎓', 'Formazione'),
    ('attivita_istituzionale','🏫', 'Att. ist.'),
]


def contesto_form_assenza(data_str, escludi_assenza_id=None, ruolo=None):
    """
    Prepara tutti i dati necessari alla pagina del form assenza, sia in
    creazione (routes/assenze.py::nuova(), escludi_assenza_id=None) sia in
    modifica (routes/assenze.py::modifica(), escludi_assenza_id=id
    dell'assenza in modifica — così il suo stesso utilizzo CCNL non viene
    contato due volte nel conteggio dei limiti): elenco docenti, tipi
    visivi, orari per il JS, utilizzi CCNL dell'anno corrente, sospensioni
    didattiche, eventi istituzionali del giorno selezionato.

    ruolo: ruolo di chi apre il form — determina se i pulsanti/contatori
    per i motivi riservati (malattia, lutto, ...) sono quelli specifici
    o il generico 'non_recuperabile' (vedi models/assenza.py::
    RUOLI_MOTIVO_SPECIFICO). Il default (None) tratta il chiamante come
    NON autorizzato, per non rischiare di esporre lo specifico se qualche
    punto di chiamata dimenticasse di passarlo.
    """
    from models.docente import Docente
    from models.assenza import LIMITI_CCNL, MOTIVI_RISERVATI, RUOLI_MOTIVO_SPECIFICO

    oggi = date.today()
    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()

    vede_specifico = ruolo in RUOLI_MOTIVO_SPECIFICO
    tipi_visivi = ((_TIPI_VISIVI_SPECIFICI if vede_specifico else _TIPI_VISIVI_RISERVATO)
                   + _TIPI_VISIVI_COMUNI)

    orari_docenti = {}
    for slot in OrarioDocente.query.all():
        key = f'{slot.id_docente}_{slot.giorno}'
        orari_docenti.setdefault(key, [])
        if slot.ora not in orari_docenti[key]:
            orari_docenti[key].append(slot.ora)

    anno = oggi.year if oggi.month >= 9 else oggi.year - 1
    inizio_as = date(anno, 9, 1)
    fine_as   = date(anno + 1, 8, 31)
    utilizzi_ccnl = {}
    for motivo_k, limiti in LIMITI_CCNL.items():
        if motivo_k in MOTIVI_RISERVATI and not vede_specifico:
            # Non incorporare nemmeno i CONTATORI nel JSON della pagina:
            # chi non ha titolo non deve poter dedurre "questo docente ha
            # già usato 2/3 permessi personali" guardando il sorgente,
            # anche se il pulsante specifico non è mostrato.
            continue
        limite_ref  = list(limiti.values())[0] if limiti else {}
        unita       = limite_ref.get('u', 'giorni') if isinstance(limite_ref, dict) else 'giorni'
        query = Assenza.query.filter(
            Assenza.motivo == motivo_k,
            Assenza.data >= inizio_as,
            Assenza.data <= fine_as
        )
        if escludi_assenza_id is not None:
            query = query.filter(Assenza.id != escludi_assenza_id)
        for a in query.all():
            if unita == 'ore':
                chiave = f'{a.id_docente}_{motivo_k}_{a.data.isoformat()}'
                n_ore = a.n_ore if hasattr(a, 'n_ore') else (a.ora_fine - a.ora_inizio + 1)
                utilizzi_ccnl[chiave] = utilizzi_ccnl.get(chiave, 0) + n_ore
            else:
                chiave = f'{a.id_docente}_{motivo_k}'
                utilizzi_ccnl[chiave] = utilizzi_ccnl.get(chiave, 0) + 1

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

    sospensione_oggi = date_sospese.get(data_str)

    try:
        eventi_ist_giorno = AttivitaIst.query.filter_by(
            data=date.fromisoformat(data_str)).all()
    except Exception:
        eventi_ist_giorno = []

    return {
        'docenti': docenti,
        'tipi_visivi': tipi_visivi,
        'orari_docenti_json': orari_docenti,
        'utilizzi_ccnl': utilizzi_ccnl,
        'date_sospese': date_sospese,
        'sospensione_oggi': sospensione_oggi,
        'eventi_ist_giorno': eventi_ist_giorno,
    }


def modifica_assenza(a, form):
    """
    Orchestrazione completa della modifica di un'assenza esistente dal
    form di routes/assenze.py::modifica() (POST): pulizia dei movimenti
    banca ore e delle supplenze automatiche legate ai vecchi valori,
    aggiornamento della riga Assenza, ricreazione del movimento banca ore
    e delle supplenze scoperte con i nuovi valori, ripristino/sync delle
    presenze istituzionali collegate.

    `a` è l'istanza Assenza già recuperata dalla route (get_or_404).
    Non fa commit né logging di audit: restano alla route chiamante.

    Ritorna un dict con: n_sup (supplenze rigenerate), new_motivo, new_data,
    nuovo_doc (Docente aggiornato, per il messaggio di log).
    """
    old_docente    = a.id_docente
    old_data       = a.data

    new_docente   = int(form["id_docente"])
    new_data      = date.fromisoformat(form["data"])
    ore_scelte_raw = form.getlist("ore_scelte")
    if ore_scelte_raw:
        new_ore_scelte  = sorted(int(o) for o in ore_scelte_raw if str(o).isdigit())
        new_ora_inizio  = new_ore_scelte[0]
        new_ora_fine    = new_ore_scelte[-1]
    else:
        new_ore_scelte  = []
        new_ora_inizio  = int(form.get("ora_inizio", 1))
        new_ora_fine    = int(form.get("ora_fine", 9))
    new_motivo    = form.get("motivo", a.motivo)
    from flask import g as _g_ruolo
    _ruolo_mod = _g_ruolo.utente.ruolo if getattr(_g_ruolo, 'utente', None) else None
    if _ruolo_mod not in RUOLI_MOTIVO_SPECIFICO:
        if new_motivo in MOTIVI_RISERVATI and new_motivo != 'non_recuperabile':
            # Un ruolo non autorizzato non può assegnare un motivo
            # specifico riservato, nemmeno forzando la richiesta POST.
            new_motivo = 'non_recuperabile'
        if a.motivo in MOTIVI_RISERVATI and a.motivo != 'non_recuperabile':
            # Né può "declassare" un'assenza già classificata nello
            # specifico da chi ha titolo (DS/DSGA/segreteria) — il form
            # gliela mostra mascherata, ma modificare altri campi
            # (orario, note, docente) non deve cancellare la
            # classificazione già fatta.
            new_motivo = a.motivo
    new_note      = form.get("note_interne", "").strip()
    note_disp     = form.get("note_display", "").strip()

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
    from flask import g as _g
    _utente = _g.utente.username if getattr(_g, 'utente', None) else None
    for s in auto_old:
        # Lapide prima di eliminare, come in routes/assenze.py::elimina —
        # altrimenti il sync automatico la rimetterebbe trovandola ancora
        # sull'altra macchina.
        registra_eliminazione('supplenze', {
            'data': s.data.isoformat(), 'ora': s.ora,
            'classe': s.classe, 'id_assente': s.id_assente,
        }, utente=_utente)
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

    from models.docente import Docente
    nuovo_doc = Docente.query.get(new_docente)

    return {
        'n_sup': n_sup,
        'new_motivo': new_motivo,
        'new_data': new_data,
        'nuovo_doc': nuovo_doc,
    }
