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


def _nome_docente(d):
    if not d:
        return '?'
    return f'{d.cognome} {d.nome or ""}'.strip()


def genera_xlsx_sovrapposizioni(sovrapposizioni, conflitti_fse):
    """Export Excel delle due tabelle mostrate nella pagina
    (routes/attivita_ist.py::verifica_sovrapposizioni), un foglio per
    fonte -- stessa scelta di 'un foglio per report' già usata altrove
    nel progetto (es. modules/export_piano_xlsx.py)."""
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment

    wb = openpyxl.Workbook()

    FONT_HDR = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
    FILL_HDR = PatternFill("solid", fgColor="7A1C17")
    WRAP = Alignment(vertical="top", wrap_text=True)

    def _intesta(ws, colonne):
        ws.append(colonne)
        for cella in ws[1]:
            cella.font = FONT_HDR
            cella.fill = FILL_HDR
        ws.freeze_panes = 'A2'

    ws1 = wb.active
    ws1.title = 'Riunione - riunione'
    _intesta(ws1, ['Data', '1ª riunione', 'Orario 1ª', '2ª riunione', 'Orario 2ª', 'Docente'])
    for s in sovrapposizioni:
        ws1.append([
            s['evento1'].data.strftime('%d/%m/%Y'),
            s['evento1'].titolo + (f' ({s["evento1"].classe})' if s['evento1'].classe else ''),
            f'{s["evento1"].ora_inizio}–{s["evento1"].ora_fine}',
            s['evento2'].titolo + (f' ({s["evento2"].classe})' if s['evento2'].classe else ''),
            f'{s["evento2"].ora_inizio}–{s["evento2"].ora_fine}',
            _nome_docente(s['docente']),
        ])
    larghezze1 = [12, 42, 14, 42, 14, 24]
    for col, larg in zip('ABCDEF', larghezze1):
        ws1.column_dimensions[col].width = larg
    for riga in ws1.iter_rows(min_row=2):
        for cella in riga:
            cella.alignment = WRAP

    ws2 = wb.create_sheet('Riunione - sessione FSE-FESR')
    _intesta(ws2, ['Data', 'Riunione', 'Orario riunione', 'Progetto', 'Modulo', 'Orario sessione', 'Docente'])
    for c in conflitti_fse:
        ws2.append([
            c['evento'].data.strftime('%d/%m/%Y'),
            c['evento'].titolo + (f' ({c["evento"].classe})' if c['evento'].classe else ''),
            f'{c["evento"].ora_inizio}–{c["evento"].ora_fine}',
            c['progetto'].titolo,
            c['modulo'].titolo,
            f'{c["sessione"].ora_inizio}–{c["sessione"].ora_fine}',
            _nome_docente(c['docente']),
        ])
    larghezze2 = [12, 34, 14, 28, 28, 14, 24]
    for col, larg in zip('ABCDEFG', larghezze2):
        ws2.column_dimensions[col].width = larg
    for riga in ws2.iter_rows(min_row=2):
        for cella in riga:
            cella.alignment = WRAP

    return wb
