"""
modules/export_piano_xlsx.py — export Excel del Piano Annuale nello
stile esatto del foglio originale di Roberto (banner colorati, colonna
mese verticale, foglio Riepilogo ore). Test unitari sul modulo puro,
senza Flask/DB: costruiamo a mano oggetti-evento con gli stessi
attributi che routes.attivita_ist._righe_piano_annuale() assegna
(col_indirizzo, col_classe, col_categoria, tipo, titolo, ora_inizio,
ora_fine, durata_ore).
"""
from datetime import date
from types import SimpleNamespace

from modules.export_piano_xlsx import genera_xlsx_piano_annuale

ANNO = '2026-2027'


def _ev(tipo, titolo, ora_inizio='10:00', ora_fine='11:00',
        col_indirizzo='', col_classe='', durata_ore=1.0):
    return SimpleNamespace(
        tipo=tipo, titolo=titolo, ora_inizio=ora_inizio, ora_fine=ora_fine,
        col_indirizzo=col_indirizzo, col_classe=col_classe,
        col_categoria=titolo if tipo == 'formazione' else tipo, durata_ore=durata_ore)


def _sospensione(descrizione, data_inizio, data_fine, tipo_label='Vacanza'):
    return SimpleNamespace(descrizione=descrizione, data_inizio=data_inizio,
                            data_fine=data_fine, tipo_label=tipo_label)


def test_un_foglio_per_mese_piu_riepilogo():
    mesi = [
        ('settembre 2026', [(date(2026, 9, 1), 'eventi', [_ev('collegio', 'Collegio docenti')])]),
        ('ottobre 2026', [(date(2026, 10, 1), 'eventi', [_ev('collegio', 'Collegio docenti')])]),
    ]
    wb = genera_xlsx_piano_annuale(mesi, [], ANNO)
    assert wb.sheetnames == ['settembre 2026', 'ottobre 2026', 'Riepilogo ore']


def test_evento_singolo_collegio_riga_unica_con_fill_pink():
    mesi = [('settembre 2026', [
        (date(2026, 9, 1), 'eventi', [_ev('collegio', 'Collegio docenti', '08:30', '13:00')]),
    ])]
    ws = genera_xlsx_piano_annuale(mesi, [], ANNO)['settembre 2026']
    # riga4 = banner giorno, riga5 = evento (titolo in B, fill collegio)
    assert ws['B4'].value == 'MARTEDÌ 1'
    assert ws['B5'].value == 'Collegio docenti'
    assert ws['B5'].fill.fgColor.rgb == '00EAD1DC'
    assert ws['E5'].value.strftime('%H:%M') == '08:30'
    assert ws['G5'].value == '=(F5-E5)*24'


def test_piu_eventi_stesso_tipo_stesso_giorno_hanno_sottogruppo():
    eventi = [_ev('consiglio_classe', f'Consiglio {i}', col_classe='1A', col_indirizzo='AFM')
              for i in range(3)]
    mesi = [('settembre 2026', [(date(2026, 9, 18), 'eventi', eventi)])]
    ws = genera_xlsx_piano_annuale(mesi, [], ANNO)['settembre 2026']
    # riga4 = banner giorno, riga5 = sottogruppo (fill grigio-blu), righe 6-8 = eventi senza titolo in B
    assert ws['B5'].value == 'consiglio_classe'
    assert ws['B5'].fill.fgColor.rgb == '006C7A96'
    assert ws['B6'].value is None
    assert ws['D6'].value == '1A'
    assert ws['C6'].value == 'AFM'
    assert ws['D7'].value == '1A'
    assert ws['D8'].value == '1A'


def test_sospensione_multigiorno_verde_singolo_giorno_rosso():
    mesi = [('dicembre 2026', [
        (date(2026, 12, 23), 'sospensione',
         _sospensione('Vacanze natalizie', date(2026, 12, 23), date(2027, 1, 6))),
        (date(2026, 11, 1), 'sospensione',
         _sospensione('Tutti i Santi', date(2026, 11, 1), date(2026, 11, 1))),
    ])]
    ws = genera_xlsx_piano_annuale(mesi, [], ANNO)['dicembre 2026']
    assert 'Vacanze natalizie' in ws['B4'].value
    assert ws['B4'].fill.fgColor.rgb == '00375623'
    assert 'Tutti i Santi' in ws['B5'].value
    assert ws['B5'].fill.fgColor.rgb == '00C00000'


def test_termine_lezioni_banner_verde():
    mesi = [('giugno 2027', [(date(2027, 6, 8), 'termine_lezioni', None)])]
    ws = genera_xlsx_piano_annuale(mesi, [], ANNO)['giugno 2027']
    assert 'Termine lezioni' in ws['B4'].value
    assert ws['B4'].fill.fgColor.rgb == '00375623'


def test_riepilogo_ore_elenca_le_classi_passate():
    classi_ore = [('AFM', '1A', 2.5, 1.0), ('CAT', '1B', 0.0, 0.0)]
    ws = genera_xlsx_piano_annuale([], classi_ore, ANNO)['Riepilogo ore']
    assert ws['A5'].value == 'AFM'
    assert ws['B5'].value == '1A'
    assert ws['C5'].value == 2.5
    assert ws['D5'].value == 1.0
    assert ws['E5'].value == '=C5+D5'
    assert ws['A6'].value == 'CAT'
