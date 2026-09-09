"""
modules/genera_docx_fse.py — Conversione dei documenti FSE/FESR
generati (vedi routes/progetti_fse.py) dall'HTML stampabile già usato
per il PDF (WeasyPrint) a un file .docx modificabile in Word, per chi
preferisce ricevere/archiviare il documento in quel formato invece del
PDF.

Non è un convertitore HTML->DOCX generico: riconosce solo il
sottoinsieme di markup usato nei template di
templates/progetti_fse/documenti/ (div con classi note, p, h2.articolo,
table, img, b, br) — è la stessa scelta già fatta per l'incorporazione
dei loghi come base64 in modules/dati_istituto.py, dove si preferisce
un meccanismo mirato e verificabile a una libreria generica di
conversione che non si può controllare riga per riga.
"""
import base64
import io

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor
from lxml import html as lxml_html

_ALLINEAMENTO_PER_CLASSE = {
    'oggetto': WD_ALIGN_PARAGRAPH.JUSTIFY,
    'protocollo': WD_ALIGN_PARAGRAPH.LEFT,
    'data-luogo': WD_ALIGN_PARAGRAPH.RIGHT,
    'qualifica': WD_ALIGN_PARAGRAPH.CENTER,
    'atto': WD_ALIGN_PARAGRAPH.CENTER,
    'firma': WD_ALIGN_PARAGRAPH.RIGHT,
    'firma-nota': WD_ALIGN_PARAGRAPH.RIGHT,
    'nota-generazione': WD_ALIGN_PARAGRAPH.LEFT,
}
_GRASSETTO_PER_CLASSE = {'atto', 'qualifica'}
_PICCOLO_PER_CLASSE = {'firma-nota', 'nota-generazione', 'protocollo', 'data-luogo', 'estremi', 'oggetto'}


def _decodifica_data_uri(src):
    if not src or not src.startswith('data:'):
        return None
    try:
        _, b64data = src.split(',', 1)
        return base64.b64decode(b64data)
    except (ValueError, base64.binascii.Error):
        return None


def _classi(el):
    return (el.get('class') or '').split()


def _scrivi_run_inline(paragraph, el):
    """Scrive il testo di un elemento inline (p, div "di testo", td, h2)
    preservando <b> come grassetto e <br> come interruzione di riga —
    l'unico markup inline usato nei nostri template."""
    def aggiungi(testo, grassetto):
        if not testo:
            return
        run = paragraph.add_run(testo)
        run.bold = grassetto

    def cammina(nodo, grassetto):
        aggiungi(nodo.text, grassetto)
        for figlio in nodo:
            if figlio.tag == 'br':
                paragraph.add_run().add_break()
            elif figlio.tag == 'b':
                cammina(figlio, True)
            else:
                cammina(figlio, grassetto)
            aggiungi(figlio.tail, grassetto)

    cammina(el, False)


def _applica_stile_paragrafo(paragraph, classi):
    for classe in classi:
        if classe in _ALLINEAMENTO_PER_CLASSE:
            paragraph.alignment = _ALLINEAMENTO_PER_CLASSE[classe]
    grassetto_diffuso = any(c in _GRASSETTO_PER_CLASSE for c in classi)
    piccolo_diffuso = any(c in _PICCOLO_PER_CLASSE for c in classi)
    if grassetto_diffuso or piccolo_diffuso:
        for run in paragraph.runs:
            if grassetto_diffuso:
                run.bold = True
            if piccolo_diffuso:
                run.font.size = Pt(9.5)
                run.font.color.rgb = RGBColor(0x55, 0x55, 0x55) if 'nota' in classi or 'firma-nota' in classi else run.font.color.rgb


def _rendi_tabella(doc, el):
    righe = el.findall('tr')
    if not righe:
        return
    n_colonne = max(len(r.findall('td') + r.findall('th')) for r in righe)
    tabella = doc.add_table(rows=0, cols=n_colonne)
    tabella.style = 'Table Grid'
    tabella.alignment = WD_TABLE_ALIGNMENT.CENTER
    for riga_html in righe:
        celle_html = [c for c in riga_html if c.tag in ('td', 'th')]
        riga_docx = tabella.add_row()
        for i, cella_html in enumerate(celle_html):
            if i >= n_colonne:
                break
            cella_docx = riga_docx.cells[i]
            paragrafo = cella_docx.paragraphs[0]
            _scrivi_run_inline(paragrafo, cella_html)
            for run in paragrafo.runs:
                run.font.size = Pt(9)
                if cella_html.tag == 'th':
                    run.bold = True
    doc.add_paragraph()


def _e_contenitore_di_blocchi(el):
    return any(figlio.tag in ('p', 'table', 'h2', 'div') for figlio in el)


def html_a_docx(html_content, larghezza_intestazione_cm=17, larghezza_footer_cm=10):
    """Converte l'HTML stampabile di un documento FSE/FESR (vedi
    templates/progetti_fse/documenti/) in un file .docx equivalente nei
    contenuti — non pixel-identico alla resa PDF, ma con lo stesso
    testo, tabelle, intestazione (solo prima pagina) e banner PN/UE
    (ogni pagina, tramite footer di sezione nativo di Word). Ritorna i
    byte del file .docx pronto per il download."""
    albero = lxml_html.fromstring(html_content)
    corpo = albero.find('body')

    doc = Document()
    stile_normale = doc.styles['Normal']
    stile_normale.font.name = 'Times New Roman'
    stile_normale.font.size = Pt(11)

    sezione = doc.sections[0]
    sezione.page_width = Cm(21)
    sezione.page_height = Cm(29.7)
    sezione.left_margin = sezione.right_margin = Cm(2)
    sezione.top_margin = sezione.bottom_margin = Cm(2.4)

    intestazione_bytes = None
    footer_bytes = None

    def cammina(el):
        nonlocal intestazione_bytes, footer_bytes
        classi = _classi(el)
        tag = el.tag

        if tag == 'div' and 'intestazione-istituto' in classi:
            img = el.find('.//img')
            if img is not None:
                intestazione_bytes = _decodifica_data_uri(img.get('src'))
            return
        if tag == 'div' and 'footer-ue' in classi:
            img = el.find('.//img')
            if img is not None:
                footer_bytes = _decodifica_data_uri(img.get('src'))
            return
        if tag == 'table':
            _rendi_tabella(doc, el)
            return
        if tag == 'h2':
            paragrafo = doc.add_paragraph()
            _scrivi_run_inline(paragrafo, el)
            for run in paragrafo.runs:
                run.bold = True
                run.font.size = Pt(11.5)
            return
        if tag == 'p':
            paragrafo = doc.add_paragraph()
            _scrivi_run_inline(paragrafo, el)
            _applica_stile_paragrafo(paragrafo, classi)
            return
        if tag == 'div' and not _e_contenitore_di_blocchi(el):
            paragrafo = doc.add_paragraph()
            _scrivi_run_inline(paragrafo, el)
            _applica_stile_paragrafo(paragrafo, classi)
            return
        for figlio in el:
            cammina(figlio)

    cammina(corpo)

    if intestazione_bytes or footer_bytes:
        sezione.different_first_page_header_footer = True
    if intestazione_bytes:
        intestazione = sezione.first_page_header
        paragrafo = intestazione.paragraphs[0]
        paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragrafo.add_run().add_picture(io.BytesIO(intestazione_bytes), width=Cm(larghezza_intestazione_cm))
    if footer_bytes:
        for footer in ({sezione.footer, sezione.first_page_footer} if intestazione_bytes else {sezione.footer}):
            paragrafo = footer.paragraphs[0]
            paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragrafo.add_run().add_picture(io.BytesIO(footer_bytes), width=Cm(larghezza_footer_cm))

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
