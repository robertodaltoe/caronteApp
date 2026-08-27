"""
Verifica sovrapposizioni tra riunioni istituzionali già programmate
(AttivitaIst, es. Consiglio di classe/scrutinio) e l'orario REALE dei
docenti (OrarioDocente), una volta importato.

Nasce da una richiesta di Roberto: le riunioni pomeridiane vengono
programmate con le Assegnazioni (routes/generatore_cdc.py), che si
stabilizzano molto prima nell'orario — quando l'orario arriva davvero,
potrebbe smentire una riunione già fissata (un docente coinvolto ha in
realtà lezione in quell'ora). Prima di questo modulo non c'era nessun
controllo: né automatico, né a richiesta.

OrarioDocente non memorizza orari reali, solo il numero d'ora (1-9) —
serve una corrispondenza numero-ora → orario reale per confrontarlo con
gli orari (stringhe "HH:MM") delle riunioni. MAPPA_ORE_POMERIDIANE è
quella corrispondenza, fornita da Roberto per la sua scuola — sono
esplicitamente solo le ore pomeridiane (le uniche che possono
sovrapporsi a una riunione istituzionale, mai la mattina): se in futuro
cambia il suono della campanella, o si aggiungono/tolgono ore, va
aggiornata qui.
"""

# {numero_ora: (ora_inizio, ora_fine)} — solo le ore pomeridiane, le
# uniche rilevanti per le riunioni istituzionali (mai al mattino).
MAPPA_ORE_POMERIDIANE = {
    6: ('12:25', '13:25'),
    7: ('13:25', '14:25'),
    8: ('14:25', '15:25'),
}

# tipo_ora che rappresentano un impegno reale del docente in classe —
# esclude 'disposizione'/'potenziamento'/'altro' (non è una lezione
# fissa con una classe specifica, non un conflitto certo) e le classi
# "vuote" (buco/potenziamento), stesso filtro già usato altrove
# nell'app (routes/display.py) per individuare le ore realmente
# occupate di un docente.
_CLASSI_NON_REALI = {None, '', '---', '-x-', 'POTENZIAMENTO'}
_TIPI_ORA_REALI = {'lezione', 'compresenza'}


def trova_conflitti_orario_riunioni(data_da=None, data_a=None):
    """
    Ritorna una lista di dict, uno per ogni sovrapposizione trovata tra
    una riunione istituzionale con orario (AttivitaIst.ora_inizio/
    ora_fine valorizzati) e una lezione reale (OrarioDocente) di un suo
    partecipante:
        {evento, docente, ora_lezione, ora_lezione_clock,
         classe_lezione, materia_lezione}

    data_da/data_a: se indicati, limitano il controllo a un intervallo
    (es. da oggi in poi — non ha senso segnalare conflitti su riunioni
    già svolte).
    """
    from models.attivita_ist import AttivitaIst
    from models.orario_docente import OrarioDocente
    from models.docente import Docente

    q = AttivitaIst.query.filter(
        AttivitaIst.ora_inizio.isnot(None), AttivitaIst.ora_fine.isnot(None))
    if data_da:
        q = q.filter(AttivitaIst.data >= data_da)
    if data_a:
        q = q.filter(AttivitaIst.data <= data_a)
    eventi = q.order_by(AttivitaIst.data, AttivitaIst.ora_inizio).all()

    docenti_map = {d.id: d for d in Docente.query.all()}
    conflitti = []

    for ev in eventi:
        partecipanti_ids = {p.id_docente for p in ev.partecipanti if p.id_docente}
        if not partecipanti_ids:
            continue
        giorno = ev.data.weekday()
        slots = OrarioDocente.query.filter(
            OrarioDocente.giorno == giorno,
            OrarioDocente.id_docente.in_(partecipanti_ids),
            OrarioDocente.ora.in_(MAPPA_ORE_POMERIDIANE.keys()),
        ).all()
        for s in slots:
            if s.classe in _CLASSI_NON_REALI or s.tipo_ora not in _TIPI_ORA_REALI:
                continue
            ora_ini, ora_fin = MAPPA_ORE_POMERIDIANE[s.ora]
            if ev.ora_inizio < ora_fin and ev.ora_fine > ora_ini:
                conflitti.append({
                    'evento': ev,
                    'docente': docenti_map.get(s.id_docente),
                    'ora_lezione': s.ora,
                    'ora_lezione_clock': f'{ora_ini}–{ora_fin}',
                    'classe_lezione': s.classe,
                    'materia_lezione': s.materia,
                })

    return conflitti
