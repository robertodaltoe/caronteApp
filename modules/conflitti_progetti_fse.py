"""
Verifica sovrapposizioni tra le sessioni di calendario dei Progetti
FSE/FESR (es. Piano Estate) e gli impegni istituzionali già
programmati (AttivitaIst — consigli di classe, scrutini, esami
integrativi, colloqui di rientro...) per uno stesso docente.

Nasce da una richiesta esplicita di Roberto: l'area "Progetti FSE/FESR"
è volutamente isolata dal Piano delle Attività didattico (non ne
condivide le tabelle), ma le date dei moduli devono comunque poter
essere incrociate con gli impegni didattici per accorgersi se un
docente incaricato come esperto/tutor è anche atteso a una riunione
istituzionale nello stesso giorno/ora — le attività estive di questi
progetti si accavallano tipicamente proprio con scrutini differiti,
esami integrativi e colloqui di rientro dall'estero, tutti concentrati
nello stesso periodo.

Non confronta con OrarioDocente (le attività FSE si svolgono per bando
in orario extracurricolare, quindi un conflitto con una lezione
ordinaria non è il caso realistico da segnalare qui) — solo con
AttivitaIst, sullo stesso modello di modules/verifica_orario_riunioni.py.
"""


def trova_conflitti_progetti_fse(data_da=None, data_a=None):
    """
    Ritorna una lista di dict, uno per ogni sovrapposizione trovata tra
    una SessioneFSE (con orario valorizzato) e un evento istituzionale
    (AttivitaIst, con orario valorizzato) che condividono un docente
    incaricato/partecipante nello stesso giorno con orari sovrapposti:
        {sessione, modulo, progetto, docente, evento}
    """
    from models.progetto_fse import SessioneFSE, IncaricoFSE
    from models.attivita_ist import AttivitaIst
    from models.docente import Docente

    q = SessioneFSE.query.filter(
        SessioneFSE.ora_inizio.isnot(None), SessioneFSE.ora_fine.isnot(None))
    if data_da:
        q = q.filter(SessioneFSE.data >= data_da)
    if data_a:
        q = q.filter(SessioneFSE.data <= data_a)
    sessioni = q.order_by(SessioneFSE.data, SessioneFSE.ora_inizio).all()
    if not sessioni:
        return []

    docenti_map = {d.id: d for d in Docente.query.all()}
    conflitti = []

    for sess in sessioni:
        modulo = sess.modulo
        docenti_ids = {i.id_docente for i in modulo.incarichi if i.id_docente}
        if not docenti_ids:
            continue

        eventi = (AttivitaIst.query
                  .filter(AttivitaIst.data == sess.data,
                          AttivitaIst.ora_inizio.isnot(None),
                          AttivitaIst.ora_fine.isnot(None))
                  .all())
        for ev in eventi:
            partecipanti_ids = {p.id_docente for p in ev.partecipanti if p.id_docente}
            comuni = docenti_ids & partecipanti_ids
            if not comuni:
                continue
            if not (sess.ora_inizio < ev.ora_fine and sess.ora_fine > ev.ora_inizio):
                continue
            for id_doc in comuni:
                conflitti.append({
                    'sessione': sess,
                    'modulo': modulo,
                    'progetto': modulo.progetto,
                    'docente': docenti_map.get(id_doc),
                    'evento': ev,
                })

    return conflitti
