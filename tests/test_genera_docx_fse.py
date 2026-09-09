"""
Test per modules/genera_docx_fse.py — la conversione dell'HTML
stampabile dei documenti FSE/FESR (vedi templates/progetti_fse/
documenti/) in un file .docx equivalente, offerta come formato
alternativo al PDF su richiesta di Roberto ("vorrei che venissero
generati, a scelta, anche i file in docx").

Usa un Environment Jinja2 puntato direttamente sulla cartella
templates/ reale del progetto (non l'app Flask di test, che non ha un
template_folder reale) cosi' da convertire l'HTML davvero prodotto dai
template, non un frammento inventato.
"""
import io
import os
from datetime import date
from types import SimpleNamespace

import jinja2
from docx import Document

from modules import dati_istituto
from modules.genera_docx_fse import html_a_docx

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'templates')


def _render(nome_template, **contesto):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(_TEMPLATES_DIR))
    return env.get_template(nome_template).render(**contesto)


def _contesto_istituto_test():
    return {
        'istituto': dati_istituto.DENOMINAZIONE,
        'comune': dati_istituto.COMUNE,
        'ds_titolo': dati_istituto.DS_TITOLO,
        'ds_nome': dati_istituto.DS_NOME_COGNOME,
        'sito_web': dati_istituto.SITO_WEB,
        'intestazione_src': dati_istituto.intestazione_data_uri(),
        'footer_ue_src': dati_istituto.footer_ue_data_uri(),
    }


def test_html_a_docx_converte_testo_tabelle_e_intestazione():
    progetto = SimpleNamespace(
        titolo='Menti in Movimento', codice_progetto='ESO4.6.A4.A-FSEPNLO-2026-1482',
        cup='D94D26002650007', riferimento_avviso='Avviso Pubblico prot. n. 0112894 del 11/05/2026',
    )
    html = _render('progetti_fse/documenti/dichiarazione_insussistenza.html',
        progetto=progetto, data_generazione=date(2026, 9, 9), **_contesto_istituto_test())

    docx_bytes = html_a_docx(html)
    assert len(docx_bytes) > 10000  # un .docx con un'immagine incorporata non è mai minuscolo

    doc = Document(io.BytesIO(docx_bytes))
    testo_completo = '\n'.join(p.text for p in doc.paragraphs)
    # Contenuto fisso del documento e dato variabile (nome del progetto)
    # devono essere entrambi presenti nel testo estratto.
    assert 'DICHIARA' in testo_completo
    assert 'Menti in Movimento' in testo_completo
    assert dati_istituto.DS_NOME_COGNOME in testo_completo

    # L'intestazione va SOLO in prima pagina (sezione con header diverso
    # per la prima pagina, e un'immagine incorporata in quell'header).
    sezione = doc.sections[0]
    assert sezione.different_first_page_header_footer
    assert len(sezione.first_page_header.paragraphs[0].runs) > 0
    # Il banner PN/UE va nel footer normale (ripetuto su ogni pagina).
    assert len(sezione.footer.paragraphs[0].runs) > 0


def test_html_a_docx_riporta_tabella_con_intestazioni_in_grassetto():
    progetto = SimpleNamespace(
        titolo='Test Tabella', codice_progetto='COD1', cup='CUP1', importo_autorizzato=1000,
        capitolo_entrata='2.1.1 Test entrata', capitolo_spesa='P.2.11 Test spesa',
        anno_esercizio_finanziario='2026', riferimento_avviso='Avviso di prova',
    )
    html = _render('progetti_fse/documenti/decreto_assunzione_bilancio.html',
        progetto=progetto, data_generazione=date(2026, 9, 9), **_contesto_istituto_test())

    docx_bytes = html_a_docx(html)
    doc = Document(io.BytesIO(docx_bytes))
    testo_completo = '\n'.join(p.text for p in doc.paragraphs)
    assert '2.1.1 Test entrata' in testo_completo
    assert 'P.2.11 Test spesa' in testo_completo
