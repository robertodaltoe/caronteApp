"""
Calendario degli impegni — raccoglie in un'unica lista le fonti che
oggi vivono ognuna nella propria pagina, per mostrarle in una vista a
calendario (giorno/settimana/mese) e per esportarle in iCal.

Fonti:
  piano       -> AttivitaIst (riunioni e attivita' del Piano delle attivita')
  formazione  -> AttivitaIst con tipo='formazione' (Piano della formazione)
  progetti    -> SessioneFSE (Progetti FSE/FESR)
  assenza     -> Assenza (solo "Assenza <cognome>": il motivo non esce mai
                 da qui, e' un dato riservato)
  lezione     -> OrarioDocente, solo quando si guarda un singolo docente

Le sovrapposizioni NON hanno logica propria: si riusano i controlli gia'
usati dalla pagina "Verifica sovrapposizioni" (modules/
verifica_sovrapposizioni_riunioni.py, conflitti_progetti_fse.py,
verifica_orario_riunioni.py) e si marcano gli impegni coinvolti.

Ogni impegno e' un dict:
  {id, fonte, titolo, data (ISO), ora_inizio, ora_fine (HH:MM o None),
   docenti [cognomi], classe, url, conflitti [messaggi]}
"""
from datetime import timedelta

FONTI = {
    'piano':      'Piano delle attività',
    'formazione': 'Formazione',
    'progetti':   'Progetti FSE/FESR',
    'assenza':    'Assenze',
    'lezione':    'Lezioni',
}

# I tre calendari esportabili in iCal (nessuna lezione, nessuna assenza).
CALENDARI_ICAL = {
    'piano':      'Caronte – Piano delle attività',
    'formazione': 'Caronte – Formazione',
    'progetti':   'Caronte – Progetti',
}

# Numero d'ora -> (inizio, fine). Stessa tabella di templates/display.html
# e orario_globale.html.
ORE_FASCE = {
    1: ('07:45', '08:40'), 2: ('08:40', '09:35'), 3: ('09:35', '10:40'),
    4: ('10:40', '11:30'), 5: ('11:30', '12:25'), 6: ('12:25', '13:25'),
    7: ('13:25', '14:25'), 8: ('14:25', '15:25'), 9: ('15:25', '16:25'),
}

_CLASSI_NON_REALI = {None, '', '---', '-x-', 'POTENZIAMENTO'}
_TIPI_ORA_REALI = {'lezione', 'compresenza'}


def _fascia_ore(ora_inizio, ora_fine):
    """Ore (1-9) di un'assenza -> (HH:MM inizio, HH:MM fine)."""
    i = min(max(ora_inizio or 1, 1), 9)
    f = min(max(ora_fine or 9, i), 9)
    return ORE_FASCE[i][0], ORE_FASCE[f][1]


def _conflitti(data_da, data_a):
    """
    {chiave: [messaggi]} con le sovrapposizioni gia' calcolate dai
    controlli esistenti. Chiavi:
      ('ist', id_attivita, data) | ('fse', id_sessione)
      | ('lez', id_docente, data, ora)
    """
    from modules.verifica_sovrapposizioni_riunioni import (
        trova_sovrapposizioni_riunioni, trova_sovrapposizioni_classe,
        trova_sovrapposizioni_ds)
    from modules.conflitti_progetti_fse import trova_conflitti_progetti_fse
    from modules.verifica_orario_riunioni import trova_conflitti_orario_riunioni

    out = {}

    def segna(chiave, msg):
        lista = out.setdefault(chiave, [])
        if msg not in lista:
            lista.append(msg)

    for s in trova_sovrapposizioni_riunioni(data_da, data_a):
        nome = s['docente'].cognome if s['docente'] else '?'
        segna(('ist', s['evento1'].id, s['data']),
              f"{nome} è convocato/a anche a «{s['evento2'].titolo}» ({s['ora2'][0]}–{s['ora2'][1]})")
        segna(('ist', s['evento2'].id, s['data']),
              f"{nome} è convocato/a anche a «{s['evento1'].titolo}» ({s['ora1'][0]}–{s['ora1'][1]})")
    for s in trova_sovrapposizioni_classe(data_da, data_a):
        segna(('ist', s['evento1'].id, s['data']),
              f"Stessa classe {s['classe']} di «{s['evento2'].titolo}»")
        segna(('ist', s['evento2'].id, s['data']),
              f"Stessa classe {s['classe']} di «{s['evento1'].titolo}»")
    for s in trova_sovrapposizioni_ds(data_da, data_a):
        segna(('ist', s['evento1'].id, s['data']),
              f"Il DS è richiesto anche a «{s['evento2'].titolo}»")
        segna(('ist', s['evento2'].id, s['data']),
              f"Il DS è richiesto anche a «{s['evento1'].titolo}»")
    for c in trova_conflitti_progetti_fse(data_da, data_a):
        nome = c['docente'].cognome if c['docente'] else '?'
        segna(('fse', c['sessione'].id),
              f"{nome} è convocato/a a «{c['evento'].titolo}» ({c['evento'].ora_inizio}–{c['evento'].ora_fine})")
        segna(('ist', c['evento'].id, c['sessione'].data),
              f"{nome} è atteso/a alla sessione FSE «{c['modulo'].titolo}»")
    for c in trova_conflitti_orario_riunioni(data_da, data_a):
        if not c['docente']:
            continue
        segna(('ist', c['evento'].id, c['data']),
              f"{c['docente'].cognome} ha lezione alla {c['ora_lezione']}ª ora "
              f"({c['ora_lezione_clock']}, {c['classe_lezione']})")
        segna(('lez', c['docente'].id, c['data'], c['ora_lezione']),
              f"Si sovrappone a «{c['evento'].titolo}»")
    return out


def _giorni(data_da, data_a):
    d = data_da
    while d <= data_a:
        yield d
        d += timedelta(days=1)


def raccogli_impegni(data_da, data_a, id_docente=None, fonti=None):
    """
    Impegni nell'intervallo [data_da, data_a] (date incluse).
    id_docente: se indicato, solo gli impegni di quel docente e, in piu',
    le sue lezioni; altrimenti la vista d'istituto (senza lezioni).
    fonti: sottoinsieme di FONTI da includere (None = tutte).
    """
    from models.attivita_ist import AttivitaIst, TIPI_ATTIVITA
    from models.assenza import Assenza
    from models.progetto_fse import SessioneFSE
    from models.orario_docente import OrarioDocente
    from models.sospensione import SospensioneDidattica

    fonti = set(fonti) if fonti is not None else set(FONTI)
    conf = _conflitti(data_da, data_a)
    impegni = []

    def aggiungi(chiave, sid, fonte, titolo, d, a, b, docenti, classe, url, ds=False):
        impegni.append({
            'id': sid, 'fonte': fonte, 'titolo': titolo, 'data': d.isoformat(),
            'ora_inizio': a, 'ora_fine': b, 'docenti': sorted(docenti),
            'classe': classe, 'url': url, 'ds': bool(ds),
            'conflitti': conf.get(chiave, []),
        })

    # ── Piano delle attivita' + Formazione ────────────────────────────
    if fonti & {'piano', 'formazione'}:
        for ev in AttivitaIst.query.order_by(AttivitaIst.data, AttivitaIst.id).all():
            fonte = 'formazione' if ev.tipo == 'formazione' else 'piano'
            if fonte not in fonti:
                continue
            if id_docente is not None and id_docente not in ev.partecipanti_convocati_ids:
                continue
            fasce = ([(s.data, s.ora_inizio, s.ora_fine) for s in ev.sessioni]
                     if ev.sessioni else [(ev.data, ev.ora_inizio, ev.ora_fine)])
            nomi = [p.docente.cognome for p in ev.partecipanti
                    if p.docente and p.id_docente in ev.partecipanti_convocati_ids]
            tipo = TIPI_ATTIVITA.get(ev.tipo, {}).get('label', ev.tipo)
            for d, a, b in fasce:
                if d < data_da or d > data_a:
                    continue
                if not (a and b):
                    a = b = None
                aggiungi(('ist', ev.id, d), f'ist-{ev.id}-{d.isoformat()}', fonte,
                         ev.titolo, d, a, b, nomi, ev.classe,
                         f'/attivita-ist/{ev.id}/modifica', ds=ev.richiede_ds)
                impegni[-1]['tipo'] = tipo

    # ── Progetti FSE/FESR ─────────────────────────────────────────────
    if 'progetti' in fonti:
        sessioni = (SessioneFSE.query
                    .filter(SessioneFSE.data >= data_da, SessioneFSE.data <= data_a)
                    .order_by(SessioneFSE.data, SessioneFSE.ora_inizio).all())
        for s in sessioni:
            mod = s.modulo
            ids = {i.id_docente for i in mod.incarichi if i.id_docente}
            if id_docente is not None and id_docente not in ids:
                continue
            nomi = [i.docente.cognome for i in mod.incarichi if i.id_docente and i.docente]
            nomi += [i.nome_esterno for i in mod.incarichi if not i.id_docente and i.nome_esterno]
            a, b = (s.ora_inizio, s.ora_fine) if s.ora_inizio and s.ora_fine else (None, None)
            titolo = f'{mod.progetto.titolo} · {mod.titolo}' if mod.progetto else mod.titolo
            aggiungi(('fse', s.id), f'fse-{s.id}', 'progetti', titolo, s.data, a, b,
                     nomi, None, f'/progetti-fse/moduli/{mod.id}/calendario')

    # ── Assenze ───────────────────────────────────────────────────────
    if 'assenza' in fonti:
        q = Assenza.query.filter(Assenza.data >= data_da, Assenza.data <= data_a)
        if id_docente is not None:
            q = q.filter(Assenza.id_docente == id_docente)
        for ass in q.order_by(Assenza.data).all():
            if ass.ora_ist_inizio and ass.ora_ist_fine:
                a, b = ass.ora_ist_inizio, ass.ora_ist_fine
            else:
                a, b = _fascia_ore(ass.ora_inizio, ass.ora_fine)
            cogn = ass.docente.cognome if ass.docente else '?'
            aggiungi(('ass', ass.id), f'ass-{ass.id}', 'assenza', f'Assenza {cogn}',
                     ass.data, a, b, [cogn], None, f'/assenze/{ass.id}/modifica')

    # ── Lezioni (solo vista per docente) ──────────────────────────────
    if 'lezione' in fonti and id_docente is not None:
        sospese = set()
        for s in SospensioneDidattica.query.filter(
                SospensioneDidattica.data_inizio <= data_a,
                SospensioneDidattica.data_fine >= data_da).all():
            sospese.update(_giorni(max(s.data_inizio, data_da), min(s.data_fine, data_a)))
        righe = OrarioDocente.query.filter_by(id_docente=id_docente).all()
        for d in _giorni(data_da, data_a):
            if d.weekday() > 5 or d in sospese:
                continue
            per_ora = {}
            for r in righe:
                if r.giorno != d.weekday() or r.classe in _CLASSI_NON_REALI \
                        or r.tipo_ora not in _TIPI_ORA_REALI or r.ora not in ORE_FASCE:
                    continue
                if (r.data_inizio_validita and d < r.data_inizio_validita) or \
                   (r.data_fine_validita and d > r.data_fine_validita):
                    continue
                # Un orario con periodo di validita' proprio (provvisorio)
                # prevale su quello "sempre valido" per la stessa ora.
                prec = per_ora.get(r.ora)
                if prec is None or (r.data_inizio_validita or r.data_fine_validita):
                    per_ora[r.ora] = r
            for ora, r in sorted(per_ora.items()):
                a, b = ORE_FASCE[ora]
                cogn = r.docente.cognome if r.docente else ''
                aggiungi(('lez', id_docente, d, ora), f'lez-{id_docente}-{d.isoformat()}-{ora}',
                         'lezione', f"{r.materia or 'Lezione'} {r.classe}".strip(),
                         d, a, b, [cogn], r.classe, '/orario/globale')

    impegni.sort(key=lambda e: (e['data'], e['ora_inizio'] or '', e['titolo']))
    return impegni


# ── iCal ──────────────────────────────────────────────────────────────
def _esc(t):
    return (str(t).replace('\\', '\\\\').replace(';', '\\;')
            .replace(',', '\\,').replace('\r', '').replace('\n', '\\n'))


def _piega(riga):
    """RFC 5545: righe max 75 byte, continuazione con CRLF + spazio."""
    dati = riga.encode('utf-8')
    if len(dati) <= 75:
        return riga
    pezzi, cur = [], b''
    for ch in riga:
        b = ch.encode('utf-8')
        limite = 75 if not pezzi else 74
        if len(cur) + len(b) > limite:
            pezzi.append(cur)
            cur = b''
        cur += b
    pezzi.append(cur)
    return '\r\n '.join(p.decode('utf-8') for p in pezzi)


def genera_ics(nome_calendario, impegni, adesso, mostra_docenti=True):
    """Testo iCal (CRLF). Orari "floating" (senza fuso): Google Calendar li
    legge nel fuso del calendario di destinazione. Gli impegni senza
    orario diventano eventi di giornata."""
    stamp = adesso.strftime('%Y%m%dT%H%M%SZ')
    righe = ['BEGIN:VCALENDAR', 'VERSION:2.0',
             'PRODID:-//CaronteApp//Calendario impegni//IT', 'CALSCALE:GREGORIAN',
             'METHOD:PUBLISH', f'X-WR-CALNAME:{_esc(nome_calendario)}']
    for e in impegni:
        d = e['data'].replace('-', '')
        righe += ['BEGIN:VEVENT', f"UID:{e['id']}@caronteapp", f'DTSTAMP:{stamp}']
        if e['ora_inizio'] and e['ora_fine']:
            righe.append(f"DTSTART:{d}T{e['ora_inizio'].replace(':', '')}00")
            righe.append(f"DTEND:{d}T{e['ora_fine'].replace(':', '')}00")
        else:
            righe.append(f'DTSTART;VALUE=DATE:{d}')
        righe.append(f"SUMMARY:{_esc(e['titolo'])}")
        desc = []
        if e.get('tipo'):
            desc.append(e['tipo'])
        if e['classe']:
            desc.append(f"Classe {e['classe']}")
        if mostra_docenti and e['docenti']:
            desc.append('Docenti: ' + ', '.join(e['docenti']))
        if desc:
            righe.append(f"DESCRIPTION:{_esc(chr(10).join(desc))}")
        righe.append('END:VEVENT')
    righe.append('END:VCALENDAR')
    return '\r\n'.join(_piega(r) for r in righe) + '\r\n'
