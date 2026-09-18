"""
Verifica sovrapposizioni fra riunioni istituzionali (AttivitaIst) per
uno stesso docente partecipante — nasce da una richiesta esplicita di
Roberto dopo aver aggiornato le date di alcune attività nel Piano delle
Attività: voleva un modo per controllare se lo spostamento aveva
creato un doppio impegno per qualcuno (due riunioni nello stesso
giorno con orari che si accavallano).

Stesso identico approccio a coppie/intervalli già usato in
modules/verifica_orario_riunioni.py e modules/conflitti_progetti_fse.py
(quest'ultimo già copre riunione-vs-sessione-Progetti-FSE/FESR — vedi
routes/attivita_ist.py::verifica_sovrapposizioni() che combina
entrambi in un'unica pagina).
"""
from collections import defaultdict


def trova_sovrapposizioni_riunioni(data_da=None, data_a=None):
    """
    Ritorna una lista di dict, uno per ogni coppia di eventi
    istituzionali che si sovrappongono nello stesso giorno condividendo
    un docente partecipante:
        {evento1, evento2, docente}
    Ogni coppia riportata una sola volta per docente coinvolto
    (evento1.id < evento2.id, cosi' la stessa sovrapposizione non
    compare due volte scambiando l'ordine).
    """
    from models.attivita_ist import AttivitaIst
    from models.docente import Docente

    q = AttivitaIst.query.filter(
        AttivitaIst.ora_inizio.isnot(None), AttivitaIst.ora_fine.isnot(None))
    if data_da:
        q = q.filter(AttivitaIst.data >= data_da)
    if data_a:
        q = q.filter(AttivitaIst.data <= data_a)
    eventi = q.order_by(AttivitaIst.data, AttivitaIst.ora_inizio, AttivitaIst.id).all()
    if not eventi:
        return []

    docenti_map = {d.id: d for d in Docente.query.all()}

    per_giorno = defaultdict(list)
    for ev in eventi:
        per_giorno[ev.data].append(ev)

    sovrapposizioni = []
    for lista in per_giorno.values():
        for i in range(len(lista)):
            ev1 = lista[i]
            for j in range(i + 1, len(lista)):
                ev2 = lista[j]
                if not (ev1.ora_inizio < ev2.ora_fine and ev1.ora_fine > ev2.ora_inizio):
                    continue
                p1 = {p.id_docente for p in ev1.partecipanti if p.id_docente}
                p2 = {p.id_docente for p in ev2.partecipanti if p.id_docente}
                for id_doc in sorted(p1 & p2):
                    sovrapposizioni.append({
                        'evento1': ev1,
                        'evento2': ev2,
                        'docente': docenti_map.get(id_doc),
                    })

    return sovrapposizioni
