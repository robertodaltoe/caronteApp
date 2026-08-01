"""
concorrenza.py — controllo di concorrenza ottimistico su modifiche
concorrenti allo stesso record.

Contesto: più persone (segreteria, collaboratore, DSGA) possono avere
aperta la stessa scheda docente o la stessa dashboard supplenze
contemporaneamente. Senza alcun controllo, chi salva per ultimo
sovrascrive in silenzio le modifiche di chi ha salvato per primo, senza
che nessuno dei due se ne accorga — un problema reale con 3-4 persone
che lavorano sugli stessi dati in un ufficio di segreteria.

Non serve un vero locking (nessuno "blocca" il record): basta accorgersi
che qualcosa è cambiato da quando l'utente ha caricato la pagina, e
avvisarlo invece di applicare la modifica alla cieca. Per questo
bastano i campi 'modificato_il' già presenti (o aggiunti) sui modelli
interessati (Supplenza, Docente), passati come campo nascosto nel form
e ricontrollati al salvataggio.

USO:
    # nel render del form:
    versione = versione_str(oggetto.modificato_il)
    # <input type="hidden" name="versione" value="{{ versione }}">

    # nella route POST, PRIMA di modificare l'oggetto:
    if versione_cambiata(oggetto.modificato_il, request.form.get('versione')):
        flash('Questo record è stato modificato da un altro utente nel '
              'frattempo. Ricontrolla i dati aggiornati prima di salvare '
              'di nuovo.', 'error')
        return redirect(...)  # torna al form, con i dati freschi dal DB
"""


def versione_str(dt):
    """Rappresentazione stabile di un timestamp 'modificato_il' da usare
    come token di versione in un campo nascosto del form. Stringa vuota
    se il record non ha ancora un timestamp (creato prima di questa
    funzionalità, o appena creato senza modifiche)."""
    return dt.isoformat(timespec='microseconds') if dt else ''


def versione_cambiata(dt_attuale, versione_form):
    """
    True se la versione inviata dal form (letta al caricamento della
    pagina) non coincide più con quella attuale nel DB — cioè qualcun
    altro ha salvato una modifica nel frattempo.

    Il confronto va fatto leggendo dt_attuale PRIMA di applicare le
    modifiche del form corrente all'oggetto (altrimenti si confronta
    sempre con se stesso).
    """
    return versione_str(dt_attuale) != (versione_form or '')
