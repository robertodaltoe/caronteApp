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


# Categorie che generano un movimento negativo in banca ore — usata sia
# dall'eliminazione singola che da quella multipla (vedi sotto), per non
# duplicare l'elenco in due punti.
TIPI_ASSENZA = ('permesso', 'assenza', 'permesso_orario', 'permesso_ist', 'civica',
                'ed_civica', 'malattia', 'assemblea', 'formazione',
                'viaggio', 'progetto', 'riunione', 'sciopero', 'altro')


def _elimina_assenza_righe(a, utente_corrente):
    """
    Cancella dal DB tutto ciò che è collegato a una singola Assenza
    (movimenti banca ore, supplenze automatiche scoperte/non assegnabili,
    presenze istituzionali, lapide di sync) e infine la riga stessa — ma
    non fa commit né audit log, quello resta al chiamante (route singola
    o eliminazione multipla, che aggregano più righe in un'unica
    transazione/messaggio invece di una per ciascuna).

    Ritorna il numero di supplenze automatiche rimosse insieme a questa
    assenza (per il messaggio flash cumulativo del chiamante).
    """
    id_docente = a.id_docente

    MovimentoBancaOre.query.filter(
        MovimentoBancaOre.id_docente == id_docente,
        MovimentoBancaOre.data == a.data,
        MovimentoBancaOre.tipo.in_(TIPI_ASSENZA),
        MovimentoBancaOre.minuti < 0
    ).delete(synchronize_session=False)

    auto = Supplenza.query.filter_by(
        data=a.data, id_assente=id_docente, origine='automatica'
    ).filter(Supplenza.stato.in_(['scoperta', 'non_assegnabile'])).all()
    n = len(auto)
    for s in auto:
        registra_eliminazione('supplenze', {
            'data': s.data.isoformat(), 'ora': s.ora,
            'classe': s.classe, 'id_assente': s.id_assente,
        }, utente=utente_corrente)
        db.session.delete(s)

    _ripristina_presenza_ist(id_docente, [a.data], id_assenza=a.id)

    # Lapide PRIMA di eliminare: altrimenti il sync automatico la
    # rimetterebbe al giro successivo trovandola ancora sull'altra
    # macchina (vedi DEVLOG Task 46, segnalato da Roberto dopo aver
    # cancellato un'assenza di prova solo da una postazione).
    registra_eliminazione('assenze', {
        'id_docente': id_docente, 'data': a.data.isoformat(),
        'ora_inizio': a.ora_inizio, 'ora_fine': a.ora_fine,
    }, utente=utente_corrente)

    db.session.delete(a)
    return n


@assenze_bp.route('/assenze/<int:id>/elimina', methods=['POST'])
def elimina(id):
    a = Assenza.query.get_or_404(id)
    data_str   = a.data.isoformat()
    docente_ref = a.docente
    _log_desc = (f'{docente_ref.cognome} {docente_ref.nome} — {a.motivo} '
                 f'({a.data.strftime("%d/%m/%Y")})') if docente_ref else f'id_docente={a.id_docente} ({a.data.strftime("%d/%m/%Y")})'

    utente_corrente = g.utente.username if getattr(g, 'utente', None) else None
    n = _elimina_assenza_righe(a, utente_corrente)
    db.session.commit()

    from routes.auth import log as auth_log
    auth_log('elimina_assenza', _log_desc)

    flash(f'Assenza rimossa.' + (f' Rimosse {n} variazioni collegate.' if n else ''), 'warning')
    return redirect(url_for('dashboard.index', data=data_str))


@assenze_bp.route('/assenze/elimina-multiple', methods=['POST'])
def elimina_multiple():
    """
    Elimina in un colpo solo più assenze selezionate a mano (checkbox)
    dalla pagina "Assenze del docente" — utile per un periodo di più
    giorni caricato in blocco, che altrimenti andrebbe eliminato riga
    per riga (vedi models/assenza.py: nessun id_gruppo collega le righe
    di un range/periodico, sono indipendenti fin dalla creazione).
    """
    ids = [int(i) for i in request.form.getlist('ids') if i.isdigit()]
    id_docente = request.form.get('id_docente', type=int)
    if not ids:
        flash('Nessuna assenza selezionata.', 'warning')
        return redirect(url_for('assenze.docente', id_docente=id_docente) if id_docente else url_for('dashboard.index'))

    righe = Assenza.query.filter(Assenza.id.in_(ids)).all()
    utente_corrente = g.utente.username if getattr(g, 'utente', None) else None
    n_sup = 0
    n_ass = 0
    docente_ref = righe[0].docente if righe else None
    for a in righe:
        n_sup += _elimina_assenza_righe(a, utente_corrente)
        n_ass += 1
    db.session.commit()

    from routes.auth import log as auth_log
    if docente_ref:
        auth_log('elimina_assenza_multipla',
                  f'{docente_ref.cognome} {docente_ref.nome} — {n_ass} assenze rimosse in blocco')

    msg = f'{n_ass} assenze rimosse.' + (f' Rimosse {n_sup} variazioni collegate.' if n_sup else '')
    flash(msg, 'warning')
    return redirect(url_for('assenze.docente', id_docente=id_docente) if id_docente else url_for('dashboard.index'))


@assenze_bp.route('/assenze/docente/<int:id_docente>')
def docente(id_docente):
    """
    Elenco di tutte le assenze di un docente, con selezione multipla per
    l'eliminazione in blocco — pensata per chi carica un periodo di più
    giorni (range/periodico) e poi deve correggerlo/eliminarlo, senza
    andare a caccia riga per riga nella dashboard giorno per giorno.
    """
    d = Docente.query.get_or_404(id_docente)

    da_str = request.args.get('da', '')
    a_str  = request.args.get('a', '')
    q = Assenza.query.filter_by(id_docente=id_docente)
    if da_str:
        try:
            q = q.filter(Assenza.data >= date.fromisoformat(da_str))
        except ValueError:
            da_str = ''
    if a_str:
        try:
            q = q.filter(Assenza.data <= date.fromisoformat(a_str))
        except ValueError:
            a_str = ''
    assenze = q.order_by(Assenza.data.desc(), Assenza.ora_inizio).all()

    from flask import session
    ruolo = session.get('ruolo', 'segreteria')

    return render_template('assenze/docente_lista.html',
        docente=d, assenze=assenze, da=da_str, a=a_str, ruolo_utente=ruolo)


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
