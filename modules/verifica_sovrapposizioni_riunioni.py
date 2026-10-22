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


def fasce_evento(ev):
    """
    Elenco (data, ora_inizio, ora_fine) in cui l'evento occupa davvero
    i partecipanti: le sessioni se l'evento e' multi-giorno (la prima
    rispecchia gia' data/ora dell'evento, vedi AttivitaIstSessione),
    altrimenti i suoi campi data/ora_inizio/ora_fine. Fasce senza
    orario completo sono escluse (non confrontabili).
    """
    if ev.sessioni:
        fasce = [(s.data, s.ora_inizio, s.ora_fine) for s in ev.sessioni]
    else:
        fasce = [(ev.data, ev.ora_inizio, ev.ora_fine)]
    return [f for f in fasce if f[1] and f[2]]


def _eventi_con_fasce(data_da, data_a):
    """Tutti gli AttivitaIst che hanno almeno una fascia confrontabile
    nell'intervallo, per la verifica sovrapposizioni."""
    from models.attivita_ist import AttivitaIst
    eventi = AttivitaIst.query.order_by(AttivitaIst.data, AttivitaIst.id).all()
    out = []
    for ev in eventi:
        fasce = [f for f in fasce_evento(ev)
                 if (not data_da or f[0] >= data_da) and (not data_a or f[0] <= data_a)]
        if fasce:
            out.append((ev, fasce))
    return out


def _coppie_sovrapposte(data_da=None, data_a=None):
    """Genera (ev1, ev2, data, fascia1, fascia2) per ogni coppia di
    eventi diversi (ev1.id < ev2.id) con fasce che si intersecano nello
    stesso giorno. fascia = (ora_inizio, ora_fine)."""
    per_giorno = defaultdict(list)
    for ev, fasce in _eventi_con_fasce(data_da, data_a):
        for d, ini, fine in fasce:
            per_giorno[d].append((ev, ini, fine))
    visti = set()
    for d in sorted(per_giorno):
        lista = per_giorno[d]
        for i in range(len(lista)):
            for j in range(i + 1, len(lista)):
                a, b = lista[i], lista[j]
                if a[0].id == b[0].id or not (a[1] < b[2] and a[2] > b[1]):
                    continue
                if a[0].id > b[0].id:
                    a, b = b, a
                chiave = (a[0].id, b[0].id, d)
                if chiave in visti:
                    continue
                visti.add(chiave)
                yield a[0], b[0], d, (a[1], a[2]), (b[1], b[2])


def trova_sovrapposizioni_riunioni(data_da=None, data_a=None):
    """
    Ritorna una lista di dict, uno per ogni coppia di eventi
    istituzionali che si sovrappongono nello stesso giorno condividendo
    un docente partecipante:
        {evento1, evento2, docente, data, ora1, ora2}
    Ogni coppia riportata una sola volta per docente coinvolto
    (evento1.id < evento2.id). Considera anche le giornate delle
    attivita' multi-giorno (sessioni).
    """
    from models.docente import Docente
    docenti_map = {d.id: d for d in Docente.query.all()}
    sovrapposizioni = []
    for ev1, ev2, d, f1, f2 in _coppie_sovrapposte(data_da, data_a):
        for id_doc in sorted(ev1.partecipanti_convocati_ids & ev2.partecipanti_convocati_ids):
            sovrapposizioni.append({
                'evento1': ev1, 'evento2': ev2, 'docente': docenti_map.get(id_doc),
                'data': d, 'ora1': f1, 'ora2': f2,
            })
    return sovrapposizioni


def trova_sovrapposizioni_classe(data_da=None, data_a=None):
    """
    Due eventi sulla stessa classe (es. CdC e scrutinio, o due CdC)
    che si accavallano, anche senza docenti in comune:
        {evento1, evento2, classe, data, ora1, ora2}
    """
    from modules.classi import stessa_classe, etichetta_classe
    return [{'evento1': e1, 'evento2': e2, 'classe': etichetta_classe(e1.classe),
             'data': d, 'ora1': f1, 'ora2': f2}
            for e1, e2, d, f1, f2 in _coppie_sovrapposte(data_da, data_a)
            if stessa_classe(e1.classe, e2.classe)]


def trova_sovrapposizioni_ds(data_da=None, data_a=None):
    """Due eventi che richiedono entrambi la presenza del DS
    (richiede_ds) e si accavallano:
        {evento1, evento2, data, ora1, ora2}"""
    return [{'evento1': e1, 'evento2': e2, 'data': d, 'ora1': f1, 'ora2': f2}
            for e1, e2, d, f1, f2 in _coppie_sovrapposte(data_da, data_a)
            if e1.richiede_ds and e2.richiede_ds]


def _nome_docente(d):
    if not d:
        return '?'
    return f'{d.cognome} {d.nome or ""}'.strip()


def _data(s, chiave='evento1'):
    return (s.get('data') or s[chiave].data).strftime('%d/%m/%Y')


def _orario(s, chiave_ora, chiave_ev):
    ini, fine = s.get(chiave_ora) or (s[chiave_ev].ora_inizio, s[chiave_ev].ora_fine)
    return f'{ini}–{fine}'


def genera_xlsx_sovrapposizioni(sovrapposizioni, conflitti_fse, conflitti_lezioni=(),
                                sovrapposizioni_classe=(), sovrapposizioni_ds=()):
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
            _data(s, 'evento1'),
            s['evento1'].titolo + (f' ({s["evento1"].classe})' if s['evento1'].classe else ''),
            _orario(s, 'ora1', 'evento1'),
            s['evento2'].titolo + (f' ({s["evento2"].classe})' if s['evento2'].classe else ''),
            _orario(s, 'ora2', 'evento2'),
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

    def _titolo(ev):
        return ev.titolo + (f' ({ev.classe})' if ev.classe else '')

    def _foglio(titolo, colonne, larghezze, righe):
        ws = wb.create_sheet(titolo)
        _intesta(ws, colonne)
        for r in righe:
            ws.append(r)
        for i, larg in enumerate(larghezze):
            ws.column_dimensions[chr(65 + i)].width = larg
        for riga in ws.iter_rows(min_row=2):
            for cella in riga:
                cella.alignment = WRAP

    _foglio('Riunione - lezione',
            ['Data', 'Riunione', 'Orario riunione', 'Docente', 'Ora di lezione', 'Classe', 'Materia'],
            [12, 38, 14, 24, 24, 12, 24],
            [[(c.get('data') or c['evento'].data).strftime('%d/%m/%Y'),
              _titolo(c['evento']),
              '–'.join(c['fascia']) if c.get('fascia') else f'{c["evento"].ora_inizio}–{c["evento"].ora_fine}',
              _nome_docente(c['docente']),
              f'{c["ora_lezione"]}ª ({c["ora_lezione_clock"]})',
              c['classe_lezione'] or '', c['materia_lezione'] or '']
             for c in conflitti_lezioni])
    _foglio('Stessa classe',
            ['Data', 'Classe', '1ª riunione', 'Orario 1ª', '2ª riunione', 'Orario 2ª'],
            [12, 12, 42, 14, 42, 14],
            [[_data(s), s['classe'], _titolo(s['evento1']), _orario(s, 'ora1', 'evento1'),
              _titolo(s['evento2']), _orario(s, 'ora2', 'evento2')]
             for s in sovrapposizioni_classe])
    _foglio('Presenza DS',
            ['Data', '1ª riunione', 'Orario 1ª', '2ª riunione', 'Orario 2ª'],
            [12, 42, 14, 42, 14],
            [[_data(s), _titolo(s['evento1']), _orario(s, 'ora1', 'evento1'),
              _titolo(s['evento2']), _orario(s, 'ora2', 'evento2')]
             for s in sovrapposizioni_ds])

    return wb
