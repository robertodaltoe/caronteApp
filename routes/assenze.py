from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from models import db
from models.assenza import Assenza
from models.docente import Docente
from models.supplenza import Supplenza
from models.movimento_banca_ore import MovimentoBancaOre
from datetime import date, timedelta

# Business logic di registrazione/supporto assenze estratta in un modulo
# dedicato (era tutta qui dentro, appesantendo le route): vedi
# modules/assenze_registrazione.py per i dettagli e il perché.
from modules.assenze_registrazione import (
    is_sospensione, GIORNI_SETTIMANA,
    _sync_presenza_ist, _ripristina_presenza_ist,
    _sync_presenza_ist_assoluto, _sync_presenza_ist_parziale,
    _genera_supplenze, registra_assenze_form, contesto_form_nuova,
    contesto_form_assenza, modifica_assenza,
)
from modules.auto_sync import registra_eliminazione

assenze_bp = Blueprint('assenze', __name__)



@assenze_bp.route('/assenze/nuova', methods=['GET', 'POST'])
def nuova():
    if request.method == 'POST':
        risultato = registra_assenze_form(request.form)
        db.session.commit()

        docente          = risultato['docente']
        motivo           = request.form.get('motivo', 'malattia')
        assenze_create   = risultato['assenze_create']
        supplenze_create = risultato['supplenze_create']
        data_inizio      = risultato['data_inizio']
        data_fine_d       = risultato['data_fine_d']

        from routes.auth import log as auth_log
        auth_log('crea_assenza',
            f'{docente.cognome} {docente.nome} — {motivo} '
            f'({assenze_create} giorno/i, dal {data_inizio.strftime("%d/%m/%Y")} '
            f'al {data_fine_d.strftime("%d/%m/%Y")})')

        if assenze_create == 1:
            msg = f'Registrato: {docente.cognome} — {motivo}.'
        else:
            msg = (f'Registrate {assenze_create} assenze: {docente.cognome} — {motivo} '
                   f'dal {data_inizio.strftime("%d/%m")} al {data_fine_d.strftime("%d/%m/%Y")}.')
        if supplenze_create:
            msg += f' Generate {supplenze_create} variazioni.'
        flash(msg, 'success')
        return redirect(url_for('dashboard.index', data=risultato['data_str']))

    oggi     = date.today()
    data_str = request.args.get('data', oggi.isoformat())
    from flask import session
    ruolo = session.get('ruolo', 'segreteria')

    ctx = contesto_form_nuova(data_str, ruolo=ruolo)

    return render_template('assenza_form.html',
        docenti=ctx['docenti'],
        data_sel=data_str,
        ore_list=range(1, 10),
        tipi_visivi=ctx['tipi_visivi'],
        orari_docenti_json=ctx['orari_docenti_json'],
        utilizzi_ccnl=ctx['utilizzi_ccnl'],
        ruolo_utente=ruolo,
        eventi_ist_giorno=ctx['eventi_ist_giorno'],
        date_sospese=ctx['date_sospese'],
        sospensione_oggi=ctx['sospensione_oggi'],
    )


@assenze_bp.route('/assenze/<int:id>/elimina', methods=['POST'])
def elimina(id):
    a = Assenza.query.get_or_404(id)
    data_str   = a.data.isoformat()
    id_docente = a.id_docente
    docente_ref = a.docente
    _log_desc = (f'{docente_ref.cognome} {docente_ref.nome} — {a.motivo} '
                 f'({a.data.strftime("%d/%m/%Y")})') if docente_ref else f'id_docente={id_docente} ({a.data.strftime("%d/%m/%Y")})'

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
    utente_corrente = g.utente.username if getattr(g, 'utente', None) else None
    for s in auto:
        registra_eliminazione('supplenze', {
            'data': s.data.isoformat(), 'ora': s.ora,
            'classe': s.classe, 'id_assente': s.id_assente,
        }, utente=utente_corrente)
        db.session.delete(s)

    # Ripristina presenze istituzionali collegate a questa assenza
    _ripristina_presenza_ist(id_docente, [a.data], id_assenza=id)

    # Lapide PRIMA di eliminare: altrimenti il sync automatico la
    # rimetterebbe al giro successivo trovandola ancora sull'altra
    # macchina (vedi DEVLOG Task 46, segnalato da Roberto dopo aver
    # cancellato un'assenza di prova solo da una postazione).
    registra_eliminazione('assenze', {
        'id_docente': id_docente, 'data': a.data.isoformat(),
        'ora_inizio': a.ora_inizio, 'ora_fine': a.ora_fine,
    }, utente=utente_corrente)

    db.session.delete(a)
    db.session.commit()

    from routes.auth import log as auth_log
    auth_log('elimina_assenza', _log_desc)

    flash(f'Assenza rimossa.' + (f' Rimosse {n} variazioni collegate.' if n else ''), 'warning')
    return redirect(url_for('dashboard.index', data=data_str))


@assenze_bp.route('/assenze/<int:id>/modifica', methods=['GET', 'POST'])
def modifica(id):
    a = Assenza.query.get_or_404(id)

    if request.method == 'POST':
        risultato = modifica_assenza(a, request.form)
        db.session.commit()

        from routes.auth import log as auth_log
        nuovo_doc = risultato['nuovo_doc']
        new_motivo = risultato['new_motivo']
        new_data = risultato['new_data']
        auth_log('modifica_assenza',
            f'{nuovo_doc.cognome if nuovo_doc else a.id_docente} — {new_motivo} '
            f'({new_data.strftime("%d/%m/%Y")})')

        msg = "Assenza aggiornata."
        if risultato['n_sup']:
            msg += f" Rigenerate {risultato['n_sup']} variazioni supplenze."
        flash(msg, "success")
        next_url = request.form.get("next") or url_for("dashboard.index", data=new_data.isoformat())
        return redirect(next_url)

    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()
    from flask import session
    ruolo = session.get('ruolo', 'segreteria')

    ctx = contesto_form_assenza(a.data.isoformat(), escludi_assenza_id=a.id, ruolo=ruolo)

    from models.assenza import motivo_visibile
    return render_template("assenza_form.html",
        assenza=a,
        motivo_visibile=motivo_visibile(a.motivo, ruolo),
        docenti=docenti,
        data_sel=a.data.isoformat(),
        ore_list=range(1, 10),
        tipi_visivi=ctx['tipi_visivi'],
        orari_docenti_json=ctx['orari_docenti_json'],
        utilizzi_ccnl=ctx['utilizzi_ccnl'],
        ruolo_utente=ruolo,
        eventi_ist_giorno=ctx['eventi_ist_giorno'],
        date_sospese=ctx['date_sospese'],
        sospensione_oggi=ctx['sospensione_oggi'],
        next=request.args.get("next", ""))
