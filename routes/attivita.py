from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db
from models.attivita_fuori_aula import AttivitaFuoriAula, AttivitaClasse
from models.migrazione_slot import MigrazioneSlot
from models.docente import Docente
from models.orario_docente import OrarioDocente
from models.indisponibilita import Indisponibilita
from models.assenza import Assenza
from models.supplenza import Supplenza
from models.movimento_banca_ore import MovimentoBancaOre
from datetime import date, timedelta
from collections import defaultdict

attivita_bp = Blueprint('attivita', __name__)

GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato']
FINE_ANNO = date(2026, 6, 6)
ORA_MAX_6GIUGNO = 3
TIPI   = [('gita','✈ Gita istruzione'),
          ('progetto','📐 Progetto'),
          ('fsl','🏫 FSL — Formazione Scuola Lavoro'),
          ('simulazione','📝 Simulazione Esame / Prova per Competenze'),
          ('migrazione_gruppo','🔀 Migrazione Gruppo (classe parzialmente fuori aula)')]

def _date_attivita(att):
    lst, cur = [], att.data_inizio
    while cur <= att.data_fine:
        if att.ricorrenza == 'settimanale':
            if cur.weekday() in att.giorni_sett_list: lst.append(cur)
        else:
            if cur.weekday() < 6: lst.append(cur)
        cur += timedelta(days=1)
    return lst

def genera_effetti(attivita):
    from flask import g as _g
    _utente = _g.utente.username if getattr(_g, 'utente', None) else None
    stats = {'indisp':0,'assenze':0,'docenti_liberi':set()}
    IS_SIM      = attivita.tipo == 'simulazione'
    IS_GRUPPO_R = getattr(attivita, 'gruppo_rimanente', False)
    # Gruppo rimanente: docenti sono indisponibili nelle ore dell'attività
    # ma le classi dell'attività NON generano supplenze scoperte (sono gestite)
    date_list  = _date_attivita(attivita)
    classi_att = set(attivita.classi_list)

    from models.attivita_accompagnatore import AttivitaAccompagnatore
    slots_det = AttivitaAccompagnatore.query.filter_by(id_attivita=attivita.id).all()

    if slots_det:
        # FSL/Progetto con calendario dettagliato
        for slot in slots_det:
            doc    = slot.docente
            data   = slot.data
            giorno = data.weekday()
            ore_list = ([int(o) for o in slot.ore_json.split(',') if o.strip()]
                        if slot.ore_json
                        else list(range(slot.ora_inizio, slot.ora_fine+1)))
            ore_set = set(ore_list)
            for ora_ind in ore_list:
                if not Indisponibilita.query.filter_by(id_docente=doc.id,data=data,ora=ora_ind).first():
                    db.session.add(Indisponibilita(
                        id_docente=doc.id,data=data,ora=ora_ind,
                        motivo=attivita.tipo,
                        note=f'Auto — {attivita.tipo} {attivita.descrizione or ""} [{attivita.id}]',
                        creato_da=_utente))
                    stats['indisp']+=1
            for s in OrarioDocente.query.filter_by(id_docente=doc.id,giorno=giorno).all():
                if (s.tipo_ora=='lezione' and s.ora in ore_set
                        and s.classe not in classi_att
                        and s.classe not in ('POTENZIAMENTO','---','-x-','',None)):
                    if not Assenza.query.filter_by(id_docente=doc.id,data=data,
                                                   ora_inizio=s.ora,ora_fine=s.ora).first():
                        db.session.add(Assenza(id_docente=doc.id,data=data,
                            ora_inizio=s.ora,ora_fine=s.ora,motivo='progetto',
                            note_interne=f'Auto — {attivita.tipo_label} {attivita.descrizione or ""} [{attivita.id}] (accompagnatore)',
                            creato_da=_utente))
                        if not Supplenza.query.filter_by(data=data,id_assente=doc.id,
                                                         ora=s.ora,classe=s.classe).first():
                            # Salta se la classe è fuori aula:
                            # 1. per l'attività corrente stessa (es. BIM: i suoi acc. non lasciano
                            #    supplenze nelle classi del BIM)
                            # 2. per un'altra attività attiva in quel giorno
                            from modules.attivita_effetti import classe_e_gia_fuori_aula
                            if classe_e_gia_fuori_aula(s.classe, classi_att, data, attivita.id, s.ora):
                                continue
                            # Compresenza: salta se c'è un compagno presente
                            from modules.compresenze import ha_compagno_presente as _hcp
                            if _hcp(doc.id, giorno, s.ora, s.classe, data):
                                continue
                            db.session.add(Supplenza(data=data,ora=s.ora,classe=s.classe,
                                id_assente=doc.id,tipo='recupero',stato='scoperta',
                                origine='automatica',
                                note=f'Auto — {attivita.tipo_label} {attivita.descrizione or ""} [{attivita.id}]',
                                creato_da=_utente))
                            stats['assenze']+=1
    else:
        # Generica (simulazione, gita, progetto senza calendario)
        for docente in attivita.accompagnatori:
            for data in date_list:
                giorno = data.weekday()
                slots_g = OrarioDocente.query.filter_by(id_docente=docente.id,giorno=giorno).all()
                if not slots_g: continue
                att_altre = AttivitaFuoriAula.query.filter(
                    AttivitaFuoriAula.data_inizio<=data,
                    AttivitaFuoriAula.data_fine>=data,
                    AttivitaFuoriAula.stato=='attiva',
                    AttivitaFuoriAula.id!=attivita.id
                ).all()
                cfpo = {}
                for _a in att_altre:
                    if _a.ora_inizio and _a.ora_fine:
                        for _o in range(_a.ora_inizio,_a.ora_fine+1):
                            cfpo.setdefault(_o,set()).update(_a.classi_list)
                ore_att = (set(range(attivita.ora_inizio,attivita.ora_fine+1))
                           if (attivita.ora_inizio and attivita.ora_fine) else set(range(1,10)))
                ore_cop = [s.ora for s in slots_g
                           if s.tipo_ora=='lezione' and s.ora in ore_att
                           and s.classe not in classi_att
                           and s.classe not in cfpo.get(s.ora,set())]
                for ora_ind in ore_att:
                    if not Indisponibilita.query.filter_by(id_docente=docente.id,data=data,ora=ora_ind).first():
                        db.session.add(Indisponibilita(id_docente=docente.id,data=data,ora=ora_ind,
                            motivo=attivita.tipo,
                            note=f'Auto — {attivita.tipo} {attivita.descrizione or ""} [{attivita.id}]',
                            creato_da=_utente))
                        stats['indisp']+=1
                for ora in ore_cop:
                    if not Assenza.query.filter_by(id_docente=docente.id,data=data,
                                                   ora_inizio=ora,ora_fine=ora).first():
                        mot = 'viaggio' if attivita.tipo=='gita' else 'progetto'
                        db.session.add(Assenza(id_docente=docente.id,data=data,
                            ora_inizio=ora,ora_fine=ora,motivo=mot,
                            note_interne=f'Auto — {attivita.tipo_label} {attivita.descrizione or ""} [{attivita.id}] (classe {attivita.classi_list} fuori aula)',
                            creato_da=_utente))
                        stats['assenze']+=1
                        slot_ora = next((s for s in slots_g if s.ora==ora and s.tipo_ora=='lezione'),None)
                        if slot_ora and slot_ora.classe not in ('POTENZIAMENTO','---','-x-','',None):
                            if not Supplenza.query.filter_by(data=data,id_assente=docente.id,
                                                             ora=ora,classe=slot_ora.classe).first():
                                # Classe fuori aula: o è nelle classi_att dell'attività
                                # corrente, o è in un'altra attività attiva quel giorno
                                from modules.attivita_effetti import classe_e_gia_fuori_aula
                                if classe_e_gia_fuori_aula(slot_ora.classe, classi_att, data, attivita.id, ora):
                                    continue
                                # Gruppo rimanente: la classe è gestita dai docenti dell'attività
                                # →︎ non generare supplenza scoperta
                                if IS_GRUPPO_R:
                                    continue
                                # Compresenza: salta se c'è un compagno presente
                                from modules.compresenze import ha_compagno_presente as _hcp
                                if _hcp(docente.id, giorno, ora, slot_ora.classe, data):
                                    continue
                                db.session.add(Supplenza(data=data,ora=ora,classe=slot_ora.classe,
                                    id_assente=docente.id,tipo='recupero',stato='scoperta',
                                    origine='automatica',
                                    note=f'Auto — {attivita.tipo_label} {attivita.descrizione or ""} [{attivita.id}]',
                                    creato_da=_utente))

    # Docenti liberi per classi coinvolte
    acc_ids = {d.id for d in attivita.accompagnatori}
    for data in date_list:
        giorno  = data.weekday()
        ore_att = (list(range(attivita.ora_inizio,attivita.ora_fine+1))
                   if (attivita.ora_inizio and attivita.ora_fine) else None)
        for classe in classi_att:
            for slot in OrarioDocente.query.filter(
                    OrarioDocente.giorno==giorno, OrarioDocente.classe==classe).all():
                if slot.id_docente not in acc_ids:
                    if ore_att is None or slot.ora in ore_att:
                        stats['docenti_liberi'].add(slot.id_docente)
        if IS_SIM:
            for ora in (ore_att or []):
                for ps in OrarioDocente.query.filter(
                        OrarioDocente.giorno==giorno, OrarioDocente.ora==ora,
                        OrarioDocente.tipo_ora=='potenziamento').all():
                    stats['docenti_liberi'].add(ps.id_docente)

    # Sorveglianza: accredita ore fuori servizio
    if attivita.riconosci_ore_acc:
        if slots_det:
            # Con calendario dettagliato: usa ore_json di ogni slot (ore esatte selezionate)
            for slot in AttivitaAccompagnatore.query.filter_by(id_attivita=attivita.id).all():
                if not slot.ore_json:
                    continue
                ore_credito = [int(o) for o in slot.ore_json.split(',') if o.strip()]
                if not ore_credito:
                    continue
                n_ore = len(ore_credito)
                from modules.attivita_effetti import marker_sorveglianza
                marker = marker_sorveglianza(attivita.tipo_label, attivita.descrizione,
                                              slot.ore_json, attivita.id, slot.data)
                if not MovimentoBancaOre.query.filter_by(
                        id_docente=slot.id_docente, data=slot.data,
                        descrizione=marker).first():
                    db.session.add(MovimentoBancaOre(
                        id_docente=slot.id_docente, data=slot.data,
                        minuti=n_ore*60, tipo='supplenza_recupero',
                        descrizione=marker))
                    stats['assenze'] += 1
        elif (attivita.ore_acc_inizio and attivita.ore_acc_fine
              and attivita.accompagnatori):
            # Senza calendario: usa il range globale ore_acc_inizio–fine
            # MA conta solo le ore in cui il docente NON è già in servizio
            ore_range = list(range(attivita.ore_acc_inizio, attivita.ore_acc_fine + 1))
            for doc in attivita.accompagnatori:
                for data in date_list:
                    giorno_d = data.weekday()
                    # Ore in cui il docente ha già lezione in quel giorno
                    ore_in_servizio = {
                        s.ora for s in OrarioDocente.query.filter_by(
                            id_docente=doc.id, giorno=giorno_d
                        ).all()
                        if s.tipo_ora in ('lezione', 'potenziamento', 'compresenza')
                    }
                    # Accredita solo le ore FUORI servizio
                    ore_credito = [o for o in ore_range if o not in ore_in_servizio]
                    if not ore_credito:
                        continue
                    n_ore = len(ore_credito)
                    ore_str = ','.join(str(o) for o in ore_credito)
                    from modules.attivita_effetti import marker_sorveglianza
                    marker = marker_sorveglianza(attivita.tipo_label, attivita.descrizione,
                                                  ore_str, attivita.id, data)
                    if not MovimentoBancaOre.query.filter_by(id_docente=doc.id,data=data,
                                                              descrizione=marker).first():
                        db.session.add(MovimentoBancaOre(id_docente=doc.id,data=data,
                            minuti=n_ore*60,tipo='supplenza_recupero',descrizione=marker))
                        stats['assenze']+=1

    stats['docenti_liberi'] = len(stats['docenti_liberi'])
    return stats

def _pulisci_effetti(att):
    # Pulisce per [id] — funziona anche se tipo/descrizione sono cambiati
    id_marker = f'[{att.id}]'

    Indisponibilita.query.filter(
        Indisponibilita.note.like(f'%{id_marker}%')
    ).delete(synchronize_session=False)
    Assenza.query.filter(
        Assenza.note_interne.like(f'%{id_marker}%')
    ).delete(synchronize_session=False)
    mc_id = f'Sorveglianza {att.tipo_label} {att.descrizione or ""} [{att.id}]'.strip()
    MovimentoBancaOre.query.filter(
        MovimentoBancaOre.descrizione.like(f'%[{att.id}]%'),
        MovimentoBancaOre.tipo=='supplenza_recupero'
    ).delete(synchronize_session=False)
    classi_att = set(att.classi_list)
    id_marker = f'[{att.id}]'
    for data in _date_attivita(att):
        for s in Supplenza.query.filter_by(data=data,origine='automatica').filter(
                Supplenza.stato.in_(['scoperta','non_assegnabile'])).all():
            if s.note and id_marker in s.note:
                db.session.delete(s)

# ── API: docente per classe/ora/giorno ─────────────────────────
@attivita_bp.route('/api/docente-classe-ora')
def api_docente_classe_ora():
    from flask import jsonify, request as req
    from models.assenza import Assenza
    from models.indisponibilita import Indisponibilita
    classe   = req.args.get('classe','').strip().upper()
    ora      = req.args.get('ora', type=int)
    giorno   = req.args.get('giorno', type=int)  # 0=lun
    data_str = req.args.get('data','')
    id_att   = req.args.get('id_attivita', type=int)  # per escludere accompagnatori
    if not classe or ora is None or giorno is None:
        return jsonify({'docente': None})
    slot = OrarioDocente.query.filter_by(classe=classe, ora=ora, giorno=giorno).filter(
        OrarioDocente.tipo_ora.in_(['lezione','compresenza'])
    ).first()
    if not slot:
        return jsonify({'docente': None, 'motivo': 'nessun docente in orario'})
    doc = db.session.get(Docente, slot.id_docente)
    if not doc:
        return jsonify({'docente': None})
    # Verifica disponibilità nella data
    disponibile = True
    motivo_non_disp = None
    if data_str:
        try:
            data_d = date.fromisoformat(data_str)
            # Assente?
            ass = Assenza.query.filter_by(id_docente=doc.id, data=data_d).filter(
                Assenza.ora_inizio<=ora, Assenza.ora_fine>=ora).first()
            if ass:
                disponibile = False
                motivo_non_disp = f'assente ({ass.motivo})'
            # Indisponibile?
            if disponibile:
                ind = Indisponibilita.query.filter_by(id_docente=doc.id, data=data_d, ora=ora).first()
                if ind:
                    disponibile = False
                    motivo_non_disp = f'indisponibile ({ind.motivo})'
            # È accompagnatore dell'attività principale?
            if disponibile and id_att:
                att_p = db.session.get(AttivitaFuoriAula, id_att)
                if att_p and doc in att_p.accompagnatori:
                    disponibile = False
                    motivo_non_disp = 'accompagnatore attività principale'
        except ValueError:
            pass
    return jsonify({
        'docente': {'id': doc.id, 'cognome': doc.cognome, 'nome': doc.nome or '',
                    'materia': slot.materia or ''},
        'disponibile': disponibile,
        'motivo': motivo_non_disp
    })

# ── API: ore libere ────────────────────────────────────────────
@attivita_bp.route('/api/ore-libere-accompagnatori')
def api_ore_libere():
    from flask import jsonify, request as req
    acc_ids_str = req.args.get('acc_ids','')
    data_inizio = req.args.get('data_inizio','')
    data_fine   = req.args.get('data_fine','')
    ricorrenza  = req.args.get('ricorrenza','giornaliera')
    giorni_str  = req.args.get('giorni_sett','')
    id_att      = req.args.get('id_attivita', type=int)
    if not acc_ids_str or not data_inizio or not data_fine:
        return jsonify({'docenti':[]})
    try:
        d_ini = date.fromisoformat(data_inizio)
        d_fin = date.fromisoformat(data_fine)
    except ValueError:
        return jsonify({'docenti':[]})
    acc_ids = [int(x) for x in acc_ids_str.split(',') if x.strip()]
    gs = [int(g) for g in giorni_str.split(',') if g.strip()] if giorni_str else []
    date_list,cur = [],d_ini
    while cur<=d_fin and len(date_list)<20:
        if ricorrenza=='settimanale':
            if cur.weekday() in gs: date_list.append(cur)
        else:
            if cur.weekday()<6: date_list.append(cur)
        cur+=timedelta(days=1)
    risultati=[]
    for doc_id in acc_ids:
        doc = db.session.get(Docente, doc_id)
        if not doc: continue
        olpg={}
        for data in date_list:
            g = data.weekday()
            slots = OrarioDocente.query.filter_by(id_docente=doc_id,giorno=g).all()
            os_ = {s.ora for s in slots if s.tipo_ora in('lezione','potenziamento')
                   and s.classe not in('---','-x-','',None)}
            ol = sorted(set(range(1,10))-os_)
            if ol: olpg[data.isoformat()]=ol
        oc=(set.intersection(*[set(v) for v in olpg.values()]) if olpg else set())
        risultati.append({'id':doc_id,'cognome':doc.cognome,'nome':doc.nome or '',
            'ore_libere_comuni':sorted(oc),'ore_per_giorno':olpg})
    return jsonify({'docenti':risultati})

# ── API: slot accompagnatori ───────────────────────────────────
@attivita_bp.route('/attivita/<int:id>/slot-accompagnatori', methods=['GET','POST'])
def slot_accompagnatori(id):
    from models.attivita_accompagnatore import AttivitaAccompagnatore
    from flask import jsonify, request as req
    att = db.session.get(AttivitaFuoriAula, id)
    if not att: return jsonify({'error':'non trovato'}),404
    if req.method=='GET':
        slots=AttivitaAccompagnatore.query.filter_by(id_attivita=id).all()
        return jsonify([{'id':s.id,'id_docente':s.id_docente,'cognome':s.docente.cognome,
            'data':s.data.isoformat(),'ora_inizio':s.ora_inizio,'ora_fine':s.ora_fine,
            'ore_json':s.ore_json or ''} for s in slots])
    data_in=req.get_json()
    if not data_in: return jsonify({'error':'Nessun dato'}),400
    AttivitaAccompagnatore.query.filter_by(id_attivita=id).delete()
    for slot in data_in.get('slots',[]):
        try:
            ore_exact=slot.get('ore_exact','') or ''
            db.session.add(AttivitaAccompagnatore(
                id_attivita=id, id_docente=int(slot['id_docente']),
                data=date.fromisoformat(slot['data']),
                ora_inizio=int(slot['ora_inizio']), ora_fine=int(slot['ora_fine']),
                ore_json=ore_exact if ore_exact else None))
        except (KeyError,ValueError): continue
    db.session.commit()
    _pulisci_effetti(att)
    genera_effetti(att)
    db.session.commit()
    return jsonify({'ok':True,'n':len(data_in.get('slots',[]))})

# ── Calendario FSL ─────────────────────────────────────────────
@attivita_bp.route('/attivita/<int:id>/calendario')
def calendario_fsl(id):
    from models.attivita_accompagnatore import AttivitaAccompagnatore
    att=db.session.get(AttivitaFuoriAula,id)
    if not att: from flask import abort; abort(404)
    date_list=_date_attivita(att)
    docenti=sorted(att.accompagnatori,key=lambda d:d.cognome)
    slots=AttivitaAccompagnatore.query.filter_by(id_attivita=id).all()
    slot_map={f'{s.id_docente}_{s.data.isoformat()}':s for s in slots}
    return render_template('attivita/calendario_fsl.html',
        attivita=att,date_list=date_list,docenti=docenti,slot_map=slot_map)

# ── Lista ──────────────────────────────────────────────────────
@attivita_bp.route('/attivita')
def lista():
    oggi = date.today()
    future = (AttivitaFuoriAula.query
              .filter_by(stato='attiva')
              .filter(AttivitaFuoriAula.data_fine >= oggi)
              .order_by(AttivitaFuoriAula.data_inizio.asc()).all())
    passate = (AttivitaFuoriAula.query
               .filter_by(stato='attiva')
               .filter(AttivitaFuoriAula.data_fine < oggi)
               .order_by(AttivitaFuoriAula.data_inizio.desc()).all())
    return render_template('attivita/lista.html',
        future=future, passate=passate, oggi=oggi)

# ── Nuova ──────────────────────────────────────────────────────
@attivita_bp.route('/attivita/nuova', methods=['GET','POST'])
def nuova():
    if request.method=='POST':
        tipo=request.form['tipo']
        descr=request.form.get('descrizione','').strip()
        di=date.fromisoformat(request.form['data_inizio'])
        df=date.fromisoformat(request.form['data_fine'])
        ric=request.form.get('ricorrenza','giornaliera')
        oi=request.form.get('ora_inizio') or None
        of=request.form.get('ora_fine') or None
        note=request.form.get('note','').strip()
        gs=request.form.getlist('giorni_settimana')
        tutte=','.join(filter(None,[request.form.get('classi','').strip(),
            ','.join(request.form.getlist('classi_sel')),
            request.form.get('classi_manual','').strip().replace(' ',',')]))
        cl=list(dict.fromkeys(c.strip().upper() for c in tutte.split(',') if c.strip()))
        acc_str=request.form.get('accompagnatori_ids','').strip()
        if df<di: flash('Data fine deve essere successiva alla data inizio.','error'); return redirect(url_for('attivita.nuova'))
        if not cl: flash('Inserisci almeno una classe.','error'); return redirect(url_for('attivita.nuova'))
        ai=request.form.get('ore_acc_inizio') or None
        af=request.form.get('ore_acc_fine') or None
        # Gruppo rimanente: collega o crea attività correlata
        gr = 'gruppo_rimanente' in request.form
        id_att_gruppo = None
        if gr:
            mode = request.form.get('gruppo_att_mode','nuova')
            id_att_gr_sel = request.form.get('id_attivita_gruppo','').strip()
            if mode == 'esistente' and id_att_gr_sel:
                id_att_gruppo = int(id_att_gr_sel)
            elif mode == 'nuova':
                gruppo_tipo  = request.form.get('gruppo_tipo','progetto')
                gruppo_descr = request.form.get('gruppo_descrizione','').strip()
                gruppo_acc   = request.form.get('gruppo_accompagnatori_ids','').strip()
                if gruppo_descr or gruppo_acc:
                    att_gr = AttivitaFuoriAula(
                        tipo=gruppo_tipo, descrizione=gruppo_descr or 'Gruppo rimanente',
                        data_inizio=di, data_fine=df, ricorrenza=ric,
                        giorni_sett=','.join(gs),
                        ora_inizio=int(oi) if oi else None,
                        ora_fine=int(of) if of else None)
                    for cc in cl: att_gr.classi.append(AttivitaClasse(classe=cc))
                    for ida in (gruppo_acc.split(',') if gruppo_acc else []):
                        if ida.strip():
                            dg = db.session.get(Docente, int(ida.strip()))
                            if dg: att_gr.accompagnatori.append(dg)
                    db.session.add(att_gr); db.session.flush()
                    id_att_gruppo = att_gr.id

        # Ore singole non consecutive
        ore_sing = [int(o) for o in request.form.getlist('ore_singole') if str(o).isdigit()]
        ore_sing_json = ','.join(str(o) for o in sorted(ore_sing)) if ore_sing else None

        att=AttivitaFuoriAula(tipo=tipo,descrizione=descr,data_inizio=di,data_fine=df,
            ricorrenza=ric,giorni_sett=','.join(gs),
            ora_inizio=int(oi) if oi else None,ora_fine=int(of) if of else None,note=note,
            riconosci_ore_acc='riconosci_ore_acc' in request.form,
            ore_acc_inizio=int(ai) if ai else None,ore_acc_fine=int(af) if af else None,
            gruppo_rimanente=gr,
            id_attivita_gruppo=id_att_gruppo,
            ore_singole_json=ore_sing_json)
        for c in cl: att.classi.append(AttivitaClasse(classe=c))
        for ida in (acc_str.split(',') if acc_str else []):
            if ida.strip():
                d=db.session.get(Docente,int(ida.strip()))
                if d: att.accompagnatori.append(d)
        db.session.add(att); db.session.flush()
        # Salva slot migrazione gruppo per ora/data
        if gr:
            # Raccoglie tutte le chiavi mig_ora_{ora}_{data} dai campi hidden
            for key, val in request.form.items():
                if key.startswith('mig_classe_') and val.strip():
                    suffix = key[len('mig_classe_'):]   # es. '3_2026-06-05'
                    parts  = suffix.split('_', 1)
                    if len(parts) != 2: continue
                    try:
                        ora_m  = int(parts[0])
                        data_m = date.fromisoformat(parts[1])
                    except (ValueError, TypeError): continue
                    classe_d = val.strip().upper()
                    usa_auto = request.form.get(f'mig_auto_{suffix}','0') == '1'
                    id_doc_m = request.form.get(f'mig_doc_{suffix}','').strip()
                    db.session.add(MigrazioneSlot(
                        id_attivita=att.id, ora=ora_m, classe_dest=classe_d,
                        usa_docente_automatico=usa_auto,
                        id_docente_assegnato=int(id_doc_m) if id_doc_m else None))
        genera_effetti(att); db.session.commit()
        flash(f'Attività registrata: {att.tipo_label} {", ".join(cl)}.','success')
        return redirect(url_for('attivita.lista'))
    oggi=date.today()
    docenti=Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    classi_raw=db.session.query(OrarioDocente.classe).distinct().all()
    classi_tutte=sorted(set(c[0] for c in classi_raw
        if c[0] and c[0] not in('---','-x-','','POTENZIAMENTO') and c[0][0].isdigit()))
    cpind=defaultdict(list)
    for c in classi_tutte:
        p=c.split(); cpind[p[-1] if len(p)>1 else 'ALTRO'].append(c)
    attivita_esistenti = AttivitaFuoriAula.query.filter_by(stato='attiva').order_by(
        AttivitaFuoriAula.data_inizio.desc()).all()
    return render_template('attivita/form.html',docenti=docenti,oggi=oggi,tipi=TIPI,
        giorni=list(enumerate(GIORNI)),ore_list=range(1,10),
        classi_per_ind=dict(sorted(cpind.items())),
        attivita_esistenti=attivita_esistenti,
        migrazione_slots=[])

# ── Annulla ────────────────────────────────────────────────────
@attivita_bp.route('/attivita/<int:id>/annulla', methods=['POST'])
def annulla(id):
    att=db.session.get(AttivitaFuoriAula,id)
    if not att: from flask import abort; abort(404)
    _pulisci_effetti(att); att.stato='annullata'; db.session.commit()
    flash(f'Attività annullata: {att.tipo_label}.','warning')
    return redirect(url_for('attivita.lista'))

# ── Modifica ───────────────────────────────────────────────────
@attivita_bp.route('/attivita/<int:id>/modifica', methods=['GET','POST'])
def modifica(id):
    att=db.session.get(AttivitaFuoriAula,id)
    if not att: from flask import abort; abort(404)
    if request.method=='POST':
        att.tipo=request.form['tipo']
        att.descrizione=request.form.get('descrizione','').strip()
        att.data_inizio=date.fromisoformat(request.form['data_inizio'])
        att.data_fine=date.fromisoformat(request.form['data_fine'])
        att.ricorrenza=request.form.get('ricorrenza','giornaliera')
        att.note=request.form.get('note','').strip()
        oi=request.form.get('ora_inizio') or None; of=request.form.get('ora_fine') or None
        att.ora_inizio=int(oi) if oi else None; att.ora_fine=int(of) if of else None
        ai=request.form.get('ore_acc_inizio') or None; af=request.form.get('ore_acc_fine') or None
        att.riconosci_ore_acc='riconosci_ore_acc' in request.form
        att.ore_acc_inizio=int(ai) if ai else None; att.ore_acc_fine=int(af) if af else None
        att.gruppo_rimanente='gruppo_rimanente' in request.form
        # Ore singole non consecutive
        ore_sing = [int(o) for o in request.form.getlist('ore_singole') if str(o).isdigit()]
        att.ore_singole_json = ','.join(str(o) for o in sorted(ore_sing)) if ore_sing else None
        gs=request.form.getlist('giorni_settimana'); att.giorni_sett=','.join(gs)
        for c in att.classi: db.session.delete(c)
        tutte=','.join(filter(None,[request.form.get('classi','').strip(),
            ','.join(request.form.getlist('classi_sel')),
            request.form.get('classi_manual','').strip().replace(' ',',')]))
        cl=list(dict.fromkeys(c.strip().upper() for c in tutte.split(',') if c.strip()))
        for c in cl: att.classi.append(AttivitaClasse(classe=c))
        att.accompagnatori.clear()
        acc_str=request.form.get('accompagnatori_ids','').strip()
        for ida in (acc_str.split(',') if acc_str else []):
            if ida.strip():
                d=db.session.get(Docente,int(ida.strip()))
                if d: att.accompagnatori.append(d)
        # Aggiorna slot migrazione
        MigrazioneSlot.query.filter_by(id_attivita=att.id).delete(synchronize_session=False)
        if att.gruppo_rimanente:
            for key, val in request.form.items():
                if key.startswith('mig_classe_') and val.strip():
                    suffix = key[len('mig_classe_'):]
                    parts  = suffix.split('_', 1)
                    if len(parts) != 2: continue
                    try:
                        ora_m  = int(parts[0])
                        data_m = date.fromisoformat(parts[1])
                    except (ValueError, TypeError): continue
                    classe_d = val.strip().upper()
                    usa_auto = request.form.get(f'mig_auto_{suffix}','0') == '1'
                    id_doc_m = request.form.get(f'mig_doc_{suffix}','').strip()
                    db.session.add(MigrazioneSlot(
                        id_attivita=att.id, ora=ora_m, classe_dest=classe_d,
                        usa_docente_automatico=usa_auto,
                        id_docente_assegnato=int(id_doc_m) if id_doc_m else None))
        _pulisci_effetti(att); db.session.flush()
        stats=genera_effetti(att); db.session.commit()
        flash(f'Attività aggiornata. {stats["indisp"]} indisp, {stats["assenze"]} assenze.','success')
        return redirect(url_for('attivita.lista'))
    oggi=date.today()
    docenti=Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    classi_raw=db.session.query(OrarioDocente.classe).distinct().all()
    classi_tutte=sorted(set(c[0] for c in classi_raw
        if c[0] and c[0] not in('---','-x-','','POTENZIAMENTO') and c[0][0].isdigit()))
    cpind=defaultdict(list)
    for c in classi_tutte:
        p=c.split(); cpind[p[-1] if len(p)>1 else 'ALTRO'].append(c)
    attivita_esistenti = AttivitaFuoriAula.query.filter(
        AttivitaFuoriAula.stato=='attiva', AttivitaFuoriAula.id!=att.id
    ).order_by(AttivitaFuoriAula.data_inizio.desc()).all()
    migrazione_slots = MigrazioneSlot.query.filter_by(id_attivita=att.id).order_by(MigrazioneSlot.ora).all()
    return render_template('attivita/form.html',attivita=att,docenti=docenti,oggi=oggi,tipi=TIPI,
        giorni=list(enumerate(GIORNI)),ore_list=range(1,10),
        classi_per_ind=dict(sorted(cpind.items())),
        attivita_esistenti=attivita_esistenti,
        migrazione_slots=migrazione_slots)
