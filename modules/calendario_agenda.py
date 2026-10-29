"""
Calendario personale mensile di un docente: PDF in stile agenda (lista per
giorno, testo mai troncato) e file .ics importabile in Google, Outlook, Apple.

Include solo gli impegni del docente da Piano delle attivita', Formazione e
Progetti FSE/FESR; mai lezioni, assenze o sovrapposizioni (dato interno).
"""
import calendar
from datetime import date, datetime

from modules.calendario_impegni import raccogli_impegni, genera_ics

FONTI_PERSONALI = ['piano', 'formazione', 'progetti']
MESI = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio',
        'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre']
GIORNI_BREVI = ['lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom']
GIORNI_LUNGHI = ['lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica']
ETICHETTA_FONTE = {'piano': 'Piano delle attività', 'formazione': 'Formazione',
                   'progetti': 'Progetti FSE/FESR'}


def nome_mese(mese):
    return f'{MESI[mese.month - 1]} {mese.year}'


def impegni_mese(docente, mese):
    """Impegni personali del mese (mese = primo giorno)."""
    ultimo = date(mese.year, mese.month, calendar.monthrange(mese.year, mese.month)[1])
    return raccogli_impegni(mese, ultimo, id_docente=docente.id, fonti=FONTI_PERSONALI, con_conflitti=False)


def impegni_mese_tutti(mese):
    """{id_docente: [impegni]} per tutto il mese con una sola raccolta
    (la pagina d'invio la usa per tutti i docenti insieme)."""
    ultimo = date(mese.year, mese.month, calendar.monthrange(mese.year, mese.month)[1])
    out = {}
    for e in raccogli_impegni(mese, ultimo, fonti=FONTI_PERSONALI, con_conflitti=False):
        for i in e['id_docenti']:
            out.setdefault(i, []).append(e)
    return out


def ics_mese(docente, mese, impegni=None):
    imp = impegni_mese(docente, mese) if impegni is None else impegni
    return genera_ics(f'Caronte – impegni {nome_mese(mese)} ({docente.cognome})',
                      imp, datetime.utcnow(), mostra_docenti=False).encode('utf-8')


def _giorni_agenda(impegni):
    """[(date, [impegno...])] in ordine, con i campi pronti per la stampa."""
    out = {}
    for e in impegni:
        d = date.fromisoformat(e['data'])
        e = dict(e)
        e['orario'] = (f"{e['ora_inizio']}–{e['ora_fine']}" if e['ora_inizio'] and e['ora_fine']
                       else 'tutto il giorno')
        e['etichetta'] = e.get('tipo') or ETICHETTA_FONTE.get(e['fonte'], e['fonte'])
        out.setdefault(d, []).append(e)
    return sorted(out.items())


def _settimane(mese, giorni_con_impegni):
    """Griglia del mese (lun-dom) per il mini calendario: 0 = fuori mese."""
    return calendar.Calendar(firstweekday=0).monthdayscalendar(mese.year, mese.month)


def agenda_html(docente, mese, impegni=None):
    from flask import render_template
    from modules.pdf_fonts import contesto_open_sans
    imp = impegni_mese(docente, mese) if impegni is None else impegni
    giorni = _giorni_agenda(imp)
    con = {d.day for d, _ in giorni}
    return render_template('report/agenda_mensile_print.html',
        docente=docente, mese_nome=nome_mese(mese), giorni=giorni,
        settimane=_settimane(mese, con), con_impegni=con, giorni_brevi=GIORNI_BREVI,
        giorni_lunghi=GIORNI_LUNGHI, n_impegni=len(imp), oggi=date.today(),
        **contesto_open_sans())


def agenda_pdf_bytes(docente, mese, impegni=None):
    """Solleva se WeasyPrint non e' disponibile."""
    from weasyprint import HTML
    return HTML(string=agenda_html(docente, mese, impegni)).write_pdf()
