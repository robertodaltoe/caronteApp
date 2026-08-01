"""
modules/attivita_effetti.py — logica di business estratta da
routes/attivita.py::genera_effetti(), la funzione che calcola gli
effetti di gite/progetti/FSL/simulazioni sulle indisponibilità, le
assenze automatiche e le supplenze scoperte generate di conseguenza.

genera_effetti() resta nel suo file (è profondamente intrecciata con
scritture dirette al DB con controlli di idempotenza a ogni passo — un
vero "separare la logica pura dall'I/O" richiederebbe una riscrittura
più ampia, rischiosa da fare senza una ragione concreta). Qui isoliamo
solo le due regole che erano duplicate identiche in due punti della
funzione (calendario dettagliato vs generico), in modo da avere un solo
posto dove capirle/cambiarle invece di due copie da tenere allineate a
mano.
"""


def classe_e_gia_fuori_aula(classe, classi_attivita_corrente, data,
                             id_attivita_corrente, ora):
    """
    True se 'classe' in quell'ora/data è già "fuori aula" per un motivo
    diverso dall'attività che stiamo processando — quindi NON va
    generata una supplenza scoperta per l'assenza dell'accompagnatore
    (la classe non c'è, non serve un sostituto):

    1. la classe è tra quelle dell'attività corrente stessa (es. i suoi
       stessi accompagnatori non lasciano supplenze scoperte per le
       classi del BIM/FSL che stanno accompagnando), oppure
    2. la classe è tra quelle di un'ALTRA attività fuori-aula attiva in
       quella data, nell'ora indicata.

    Richiede import locali dei modelli per evitare un import circolare
    con routes/attivita.py (che importa già questi stessi modelli).
    """
    if classe in classi_attivita_corrente:
        return True

    from models.attivita_fuori_aula import AttivitaFuoriAula
    from models.attivita_accompagnatore import AttivitaAccompagnatore

    for altra in AttivitaFuoriAula.query.filter(
            AttivitaFuoriAula.data_inizio <= data,
            AttivitaFuoriAula.data_fine >= data,
            AttivitaFuoriAula.stato == 'attiva',
            AttivitaFuoriAula.id != id_attivita_corrente).all():
        if classe not in altra.classi_list:
            continue
        if AttivitaAccompagnatore.query.filter_by(id_attivita=altra.id).count() > 0:
            if AttivitaAccompagnatore.query.filter_by(id_attivita=altra.id, data=data).first():
                return True
        elif not altra.ora_inizio:
            return True
        elif altra.ora_inizio <= ora <= altra.ora_fine:
            return True

    return False


def marker_sorveglianza(tipo_label, descrizione, ore_str, id_attivita, data):
    """PURA — nessuna query. Costruisce la stringa 'descrizione' usata
    sia per creare il movimento banca ore di sorveglianza sia per
    verificarne l'idempotenza (query .filter_by(descrizione=marker)) —
    deve restare identica in entrambi i punti, prima duplicata a mano
    con lo stesso formato in due punti della funzione."""
    return (f'Sorveglianza {tipo_label} '
            f'{descrizione or ""} '
            f'ore {ore_str} '
            f'[{id_attivita}] ({data.isoformat()})').strip()
