from config_anno import get_anno_corrente
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db
from models.docente import Docente
from models.materia import Materia, DocenteMateria, Dipartimento
from models.colloqui_eccezione import ColloquiEccezione
from datetime import date

docenti_bp = Blueprint('docenti', __name__)

GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato']


def _sync_materia_roster(docente, materie_ids, anno):
    """Sincronizza le materie selezionate nella scheda docente con il roster."""
    DocenteMateria.query.filter_by(id_docente=docente.id, anno_scol=anno).delete()
    for mid in materie_ids:
        if mid.isdigit():
            db.session.add(DocenteMateria(
                id_docente=docente.id, id_materia=int(mid), anno_scol=anno))
    # Aggiorna anche il campo materia testuale (prima materia selezionata)
    if materie_ids:
        prima = Materia.query.get(int(materie_ids[0]))
        if prima:
            docente.materia = prima.nome


@docenti_bp.route('/docenti')
def lista():
    docenti = Docente.query.order_by(Docente.cognome).all()
    return render_template('docenti.html', docenti=docenti)

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
            altra_scuola   = (request.form.get('altra_scuola','').strip() or None) if request.form.get('tipo_servizio') == 'multi_sede' else None,
            giorni_presenza= (','.join(request.form.getlist('giorni_presenza')) or None) if request.form.get('tipo_servizio') == 'multi_sede' else None,
            attivo         = True
        )
        id_tit_rif = request.form.get('id_titolare_riferimento', '').strip()
        d.id_titolare_riferimento = int(id_tit_rif) if (d.ruolo == 'itp' and id_tit_rif) else None
        d.nome_display = f"{d.cognome} {d.nome[0]}." if d.nome else d.cognome
        db.session.add(d)
        db.session.commit()
        flash(f"Docente {d.nome_completo} aggiunto. Ora assegna la sua classe di concorso e le materie.", 'success')
        return redirect(url_for('docenti.modifica', id=d.id))
    titolari_disponibili = Docente.query.filter(
        Docente.attivo == True, Docente.ruolo == 'titolare').order_by(Docente.cognome).all()
    return render_template('docente_form.html', docente=None, giorni=list(enumerate(GIORNI)), eccezioni=[],
        titolari_disponibili=titolari_disponibili)

@docenti_bp.route('/docenti/<int:id>/modifica', methods=['GET', 'POST'])
def modifica(id):
    d = Docente.query.get_or_404(id)
    if request.method == 'POST':
        d.cognome        = request.form['cognome'].strip().upper()
        d.nome           = request.form['nome'].strip().title()
        d.ore_contratto  = int(request.form.get('ore_contratto', 18) or 0)
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
        flash(f"Docente {d.nome_completo} aggiornato.", 'success')
        return redirect(url_for('docenti.lista'))

    eccezioni = ColloquiEccezione.query.filter_by(id_docente=d.id)\
        .order_by(ColloquiEccezione.data).all()
    # Navigazione prev/next tra docenti attivi (ordine alfabetico)
    tutti = [doc.id for doc in Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()]
    idx   = tutti.index(id) if id in tutti else -1
    id_prev = tutti[idx - 1] if idx > 0            else None
    id_next = tutti[idx + 1] if idx < len(tutti)-1 else None
    materie = Materia.query.join(Dipartimento).order_by(Dipartimento.ordine, Materia.nome).all()
    mat_assegnate = {dm.id_materia for dm in DocenteMateria.query.filter_by(
        id_docente=id, anno_scol=get_anno_corrente()).all()}
    titolari_disponibili = (Docente.query
        .filter(Docente.attivo == True, Docente.ruolo == 'titolare', Docente.id != d.id)
        .order_by(Docente.cognome).all())

    from models.docente import CoppiaDocenteItp
    abbinamenti_itp = (CoppiaDocenteItp.query
        .filter_by(id_itp=d.id, attiva=True).all())

    return render_template('docente_form.html', docente=d,
                           materie=materie, mat_assegnate=mat_assegnate,
        giorni=list(enumerate(GIORNI)), eccezioni=eccezioni,
        id_prev=id_prev, id_next=id_next,
        titolari_disponibili=titolari_disponibili,
        abbinamenti_itp=abbinamenti_itp)

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
            f'⚠ {nome} ha dati collegati (banca ore: {n_bk}, assenze: {n_as}, '
            f'supplenze: {n_sup}). Conferma l\'eliminazione definitiva.',
            'warning'
        )
        return redirect(url_for('docenti.lista') + f'?conferma_elimina={id}')
    ColloquiEccezione.query.filter_by(id_docente=id).delete()
    OrarioDocente.query.filter_by(id_docente=id).delete()
    db.session.delete(d)
    db.session.commit()
    flash(f'Docente {nome} eliminato definitivamente.', 'success')
    return redirect(url_for('docenti.lista'))


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
