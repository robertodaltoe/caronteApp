"""
Test per modules/parser_orario.py — nessuna copertura esisteva prima
(sessione del 2026-09-11, motivata dall'aver trovato una seconda
variante del file di export dell'orario, "ORARIO SETTIMANA
1B_teachers_ti", diversa da quella storica su cui il parser era
scritto: niente colonna A con le etichette CLASSE/MATERIE/COMPRESENZA,
cognome del docente e classe sulla stessa riga, materia sulla riga
sotto; giorni abbreviati (LUN/MAR/...) invece che per esteso
(Lunedì/Martedì/...); nome del foglio diverso
("<periodo>_teachers_ti" invece di sempre
"7_ORARIO DEFINITIVO_teachers_ti").

I workbook di test sono costruiti in memoria con openpyxl, non i file
reali di Roberto (che restano fuori dal repository e contengono nomi
di persone) — bastano pochi docenti/celle per riprodurre entrambi i
formati e i casi limite (potenziamento, compresenza).
"""
import datetime
import io

import pytest
from openpyxl import Workbook

from modules.parser_orario import parse_file, build_col_map, _trova_foglio_orario


def _tempfile_da_workbook(wb, tmp_path, nome='orario.xlsx'):
    percorso = tmp_path / nome
    wb.save(percorso)
    return str(percorso)


def _crea_workbook_formato_a_tag(nome_foglio='7_ORARIO DEFINITIVO_teachers_ti'):
    wb = Workbook()
    ws = wb.active
    ws.title = nome_foglio
    ws.cell(1, 2, 'Titolo di prova')
    ws.cell(2, 3, 'Lunedì')
    ws.cell(2, 6, 'Martedì')
    ws.cell(3, 3, datetime.time(8, 0))
    ws.cell(3, 4, datetime.time(9, 0))
    ws.cell(3, 6, datetime.time(8, 0))
    ws.cell(3, 7, datetime.time(9, 0))
    # ROSSI: lezione lunedì 1a ora, potenziamento martedì 1a ora
    ws.cell(4, 1, 'CLASSE'); ws.cell(4, 2, 'ROSSI')
    ws.cell(4, 3, '2ALSC'); ws.cell(4, 4, '---')
    ws.cell(4, 6, 'POTENZIAMENTO'); ws.cell(4, 7, '---')
    ws.cell(5, 1, 'MATERIE')
    ws.cell(5, 3, 'MATEMATICA')
    # BIANCHI in compresenza con VERDI il lunedì alla 2a ora
    ws.cell(6, 1, 'CLASSE'); ws.cell(6, 2, 'BIANCHI')
    ws.cell(6, 3, '---'); ws.cell(6, 4, '3BLSC')
    ws.cell(7, 1, 'MATERIE')
    ws.cell(7, 4, 'INGLESE')
    ws.cell(8, 1, 'COMPRESENZA')
    ws.cell(8, 4, 'VERDI|GIALLI')  # il formato a tag elenca i cognomi separati da '|'
    return wb


def _crea_workbook_formato_orizzontale(nome_foglio='ORARIO SETTIMANA 1B_teachers_ti', giorni_brevi=True):
    wb = Workbook()
    ws = wb.active
    ws.title = nome_foglio
    ws.cell(1, 2, 'Titolo di prova')
    etichetta_lun = 'LUN' if giorni_brevi else 'Lunedì'
    etichetta_mar = 'MAR' if giorni_brevi else 'Martedì'
    ws.cell(2, 3, etichetta_lun)
    ws.cell(2, 6, etichetta_mar)
    ws.cell(3, 3, datetime.time(8, 0))
    ws.cell(3, 4, datetime.time(9, 0))
    ws.cell(3, 6, datetime.time(8, 0))
    ws.cell(3, 7, datetime.time(9, 0))
    # ROSSI: cognome e classe sulla stessa riga, materia sotto -- niente
    # colonna A di servizio.
    ws.cell(4, 2, 'ROSSI')
    ws.cell(4, 3, '2ALSC'); ws.cell(4, 4, '---')
    ws.cell(4, 6, 'POTENZIAMENTO'); ws.cell(4, 7, '---')
    ws.cell(5, 3, 'MATEMATICA')
    # BIANCHI in compresenza con VERDI il lunedì alla 2a ora: la nota
    # "BIANCHI, VERDI" sostituisce la classe su quella sola colonna,
    # classe/materia vere restano sulle due righe sotto.
    ws.cell(6, 2, 'BIANCHI')
    ws.cell(6, 3, '---'); ws.cell(6, 4, 'BIANCHI, VERDI')
    ws.cell(7, 4, '3BLSC')
    ws.cell(8, 4, 'INGLESE')
    return wb


def test_build_col_map_riconosce_giorni_per_esteso_e_abbreviati():
    """Il formato 'a tag' storico scrive 'Lunedì' per esteso, quello
    'orizzontale' scoperto il 2026-09-11 scrive 'LUN' abbreviato --
    build_col_map deve riconoscere entrambi (bug reale: il controllo
    originale funzionava solo in un verso, 'Lunedì' in 'lunedì', e
    falliva silenziosamente per 'lun' in 'lunedì')."""
    wb = Workbook()
    ws = wb.active
    ws.cell(2, 1, 'LUN')
    ws.cell(3, 1, datetime.time(8, 0))
    ws.cell(2, 5, 'Martedì')
    ws.cell(3, 5, datetime.time(8, 0))

    col_map = build_col_map(ws)
    assert col_map[1] == (0, 1)  # Lunedì abbreviato
    assert col_map[5] == (1, 1)  # Martedì per esteso


def test_trova_foglio_per_suffisso_quando_il_nome_e_diverso(tmp_path):
    wb = _crea_workbook_formato_orizzontale(nome_foglio='ORARIO SETTIMANA 1B_teachers_ti')
    percorso = _tempfile_da_workbook(wb, tmp_path)
    from openpyxl import load_workbook
    wb_letto = load_workbook(percorso)
    ws = _trova_foglio_orario(wb_letto)
    assert ws.title == 'ORARIO SETTIMANA 1B_teachers_ti'


def test_trova_foglio_alza_errore_chiaro_se_nessun_foglio_combacia(tmp_path):
    wb = Workbook()
    wb.active.title = 'Foglio1'
    percorso = _tempfile_da_workbook(wb, tmp_path)
    from openpyxl import load_workbook
    wb_letto = load_workbook(percorso)
    with pytest.raises(KeyError):
        _trova_foglio_orario(wb_letto)


def test_parse_file_formato_a_tag_lezione_potenziamento_compresenza(tmp_path):
    wb = _crea_workbook_formato_a_tag()
    percorso = _tempfile_da_workbook(wb, tmp_path)
    parsed = parse_file(percorso)
    slots = {(s['cognome_file'], s['giorno'], s['ora']): s for s in parsed['slots']}

    assert slots[('ROSSI', 0, 1)]['classe'] == '2ALSC'
    assert slots[('ROSSI', 0, 1)]['tipo_ora'] == 'lezione'
    assert slots[('ROSSI', 1, 1)]['tipo_ora'] == 'potenziamento'
    assert ('ROSSI', 1, 2) not in slots  # '---' -> nessuno slot

    assert slots[('BIANCHI', 0, 2)]['classe'] == '3BLSC'
    for collega in ('VERDI', 'GIALLI'):
        assert slots[(collega, 0, 2)]['classe'] == '3BLSC'
        assert slots[(collega, 0, 2)]['materia'] == 'INGLESE'
        assert slots[(collega, 0, 2)]['tipo_ora'] == 'compresenza'


def test_parse_file_formato_orizzontale_con_giorni_abbreviati(tmp_path):
    """Il formato scoperto il 2026-09-11: nessuna colonna CLASSE/MATERIE
    di servizio, cognome e classe sulla stessa riga, materia sotto,
    giorni abbreviati -- deve dare lo STESSO risultato del formato a
    tag per lo stesso identico orario."""
    wb = _crea_workbook_formato_orizzontale()
    percorso = _tempfile_da_workbook(wb, tmp_path)
    parsed = parse_file(percorso)
    slots = {(s['cognome_file'], s['giorno'], s['ora']): s for s in parsed['slots']}

    assert slots[('ROSSI', 0, 1)]['classe'] == '2ALSC'
    assert slots[('ROSSI', 0, 1)]['materia'] == 'MATEMATICA'
    assert slots[('ROSSI', 0, 1)]['tipo_ora'] == 'lezione'
    assert slots[('ROSSI', 1, 1)]['tipo_ora'] == 'potenziamento'
    assert ('ROSSI', 1, 2) not in slots


def test_parse_file_formato_orizzontale_compresenza_e_autosufficiente(tmp_path):
    """La nota 'BIANCHI, VERDI' al posto della classe non richiede di
    andare a leggere il blocco dell'altro docente: classe e materia
    vere stanno gia' sulle righe successive dello stesso blocco
    (verificato sui casi reali MAY/STRAMBINI in 'ORARIO SETTIMANA
    1B_teachers_ti', non recuperabile incrociando le righe come si
    farebbe nel formato a tag)."""
    wb = _crea_workbook_formato_orizzontale()
    percorso = _tempfile_da_workbook(wb, tmp_path)
    parsed = parse_file(percorso)
    slots = {(s['cognome_file'], s['giorno'], s['ora']): s for s in parsed['slots']}

    assert slots[('BIANCHI', 0, 2)]['classe'] == '3BLSC'
    assert slots[('BIANCHI', 0, 2)]['materia'] == 'INGLESE'
    assert slots[('BIANCHI', 0, 2)]['tipo_ora'] == 'compresenza'
    # In questo formato la nota compare solo sul blocco del docente
    # proprietario della riga: non genera automaticamente uno slot
    # anche per VERDI (a differenza del formato a tag, dove la riga
    # COMPRESENZA lo fa esplicitamente) -- e' un limite noto, non
    # affrontato perché nei file reali visti finora ogni docente in
    # compresenza ha comunque il proprio blocco con classe/materia.
    assert ('VERDI', 0, 2) not in slots


def test_parse_file_sceglie_il_formato_giusto_in_base_alla_colonna_a(tmp_path):
    """Un file 'orizzontale' non deve mai essere scambiato per uno 'a
    tag' solo perché il nome del foglio termina per '_teachers_ti' --
    la scelta si basa sul contenuto (colonna A), non sul nome file."""
    wb = _crea_workbook_formato_orizzontale(nome_foglio='QUALSIASI NOME_teachers_ti')
    percorso = _tempfile_da_workbook(wb, tmp_path)
    parsed = parse_file(percorso)
    assert len(parsed['slots']) > 0
