"""
modules/prospetto_supplenze.py — Roberto (15/09/2026): generando il
prospetto dalla dashboard, i nominativi comparivano nella tabella
firme in fondo al foglio ma non nelle celle ore/classi. Causa reale
trovata verificando i dati veri: il codice era ancorato al foglio
'MATRICE 25_26' (anno scorso) con una mappa fissa classe->riga in
Python, mentre il template reale ha anche un foglio aggiornato
'MATRICE 26_27' con righe in più per le sezioni B aggiunte quest'anno
(1B CAT, 1B AFM, 1B LSU, 3B LSC, 3B RIM) — quelle classi non esistevano
affatto nella mappa fissa. In più, molte classi nei dati reali sono
salvate senza lo spazio fra sezione e indirizzo (es. "1ACAT" invece di
"1A CAT"), mai gestito dalla normalizzazione precedente.

Il fix legge la struttura (righe classi, tabella firme) direttamente
dal foglio del template invece di un dizionario fisso, e sceglie il
foglio giusto in base all'anno scolastico corrente. Questi test
costruiscono un template minimo a mano (via openpyxl), per non
dipendere dal file reale data/prospetto_template.xlsx (non versionato
nel repo, come database.db).
"""
from datetime import date
from types import SimpleNamespace

from openpyxl import Workbook

from modules.prospetto_supplenze import (
    genera_prospetto, _scegli_foglio, _righe_classi, _righe_firme,
    _trova_riga, _norm, _norm_compatto, ORA_COLS, FIRME_COLS,
)


def _foglio_minimo(wb, nome, classi, riga_docente):
    """Crea un foglio che replica solo la struttura che il modulo
    legge davvero: colonna B con le etichette classe (righe 9 in poi,
    con un buco per imitare la seconda intestazione del template
    reale) e l'intestazione "DOCENTE" della tabella firme."""
    ws = wb.create_sheet(nome)
    riga = 9
    for i, classe in enumerate(classi):
        if i == len(classi) // 2:
            riga += 2  # buco fra sezioni, come nel template reale
        ws.cell(riga, 2).value = classe
        riga += 1
    ws.cell(riga_docente - 2, 2).value = 'FIRMA DOCENTI INTERESSATI'
    ws.cell(riga_docente, 2).value = 'DOCENTE'
    # estende le dimensioni del foglio di 5 righe sotto l'intestazione,
    # come le righe vuote della tabella firme nel template reale
    # (un valore vuoto, non None: solo un valore reale fa espandere
    # ws.max_row in openpyxl).
    ws.cell(riga_docente + 5, 30).value = ' '
    return ws


def _template_con_due_anni():
    wb = Workbook()
    del wb['Sheet']
    _foglio_minimo(wb, 'MATRICE 25_26',
                    ['1A AFM', '2A AFM', '2B AFM', '1A CAT', '2A CAT'], riga_docente=20)
    _foglio_minimo(wb, 'MATRICE 26_27',
                    ['1A AFM', '1B AFM', '2A AFM', '1A  CAT', '1B  CAT', '2A CAT'], riga_docente=22)
    return wb


def _docente(cognome):
    return SimpleNamespace(cognome=cognome)


def _supplenza(classe, ora, assente=None, sostituto=None, tipo=None, stato='assegnata'):
    return SimpleNamespace(
        classe=classe, ora=ora, stato=stato, tipo=tipo,
        assente=_docente(assente) if assente else None,
        sostituto=_docente(sostituto) if sostituto else None,
    )


# ── _norm / _norm_compatto ───────────────────────────────────────────

def test_norm_compatto_toglie_lo_spazio_oltre_a_normalizzarlo():
    assert _norm(' 1a   cat ') == '1A CAT'
    assert _norm_compatto('1ACAT') == '1ACAT'
    assert _norm_compatto('1A CAT') == '1ACAT'
    assert _norm_compatto('1a  cat') == '1ACAT'


# ── _scegli_foglio ────────────────────────────────────────────────────

def test_scegli_foglio_usa_quello_dell_anno_corrente(monkeypatch):
    """Se il foglio per l'anno scolastico corrente esiste, va scelto
    lui -- non il primo foglio "MATRICE" trovato nel workbook."""
    import config_anno
    monkeypatch.setattr(config_anno, 'get_anno_corrente', lambda app=None: '2026-2027')
    wb = _template_con_due_anni()

    nome, corrisponde = _scegli_foglio(wb)

    assert nome == 'MATRICE 26_27'
    assert corrisponde is True


def test_scegli_foglio_ricade_sul_piu_recente_se_manca_anno_esatto(monkeypatch):
    """Roberto non ha ancora preparato il foglio per l'anno prossimo:
    deve ripiegare sul più recente disponibile, segnalando che non
    corrisponde esattamente (secondo valore False), non fallire."""
    import config_anno
    monkeypatch.setattr(config_anno, 'get_anno_corrente', lambda app=None: '2027-2028')
    wb = _template_con_due_anni()

    nome, corrisponde = _scegli_foglio(wb)

    assert nome == 'MATRICE 26_27'
    assert corrisponde is False


# ── _righe_classi / _righe_firme ─────────────────────────────────────

def test_righe_classi_legge_dal_foglio_saltando_il_buco(monkeypatch):
    import config_anno
    monkeypatch.setattr(config_anno, 'get_anno_corrente', lambda app=None: '2026-2027')
    wb = _template_con_due_anni()
    ws = wb['MATRICE 26_27']

    righe = _righe_classi(ws)

    # Le 4 sole righe che il modulo deve conoscere per l'anno 26/27,
    # incluse le due nuove sezioni B che nel foglio 25_26 non esistono.
    assert righe['1A AFM'] == 9
    assert righe['1B AFM'] == 10
    assert righe['1A CAT'] == 14  # dopo il buco di 2 righe inserito da _foglio_minimo
    assert righe['1B CAT'] == 15
    assert 'FIRMA DOCENTI INTERESSATI' not in righe  # non è una classe


def test_righe_firme_trova_intestazione_docente():
    wb = _template_con_due_anni()
    ws = wb['MATRICE 26_27']

    inizio, fine = _righe_firme(ws)

    assert ws.cell(inizio - 1, 2).value == 'DOCENTE'


# ── _trova_riga ───────────────────────────────────────────────────────

def test_trova_riga_recupera_forma_compatta_senza_spazio():
    righe_classi = {'1A CAT': 16, '1B CAT': 17}
    non_trovate = set()

    assert _trova_riga('1ACAT', righe_classi, non_trovate) == 16
    assert _trova_riga('1BCAT', righe_classi, non_trovate) == 17
    assert not non_trovate


def test_trova_riga_segnala_classe_davvero_assente_dal_template():
    """Una classe che non esiste nel template (né con spazio né senza)
    deve finire in non_trovate, non sparire silenziosamente."""
    righe_classi = {'1A CAT': 16}
    non_trovate = set()

    riga = _trova_riga('9Z INESISTENTE', righe_classi, non_trovate)

    assert riga is None
    assert '9Z INESISTENTE' in non_trovate


# ── genera_prospetto (end-to-end sul modulo, con app/db per la query
#    delle indisponibilità) ────────────────────────────────────────────

def _salva_template(tmp_path, wb):
    path = tmp_path / 'template.xlsx'
    wb.save(path)
    return str(path)


def test_genera_prospetto_compila_la_griglia_per_classe_con_e_senza_spazio(app, db_session, monkeypatch, tmp_path):
    """Il caso segnalato da Roberto: una supplenza sulla nuova sezione
    B, scritta in un modo qualsiasi (con o senza spazio), deve finire
    nella cella della griglia corrispondente -- non solo nella tabella
    firme in fondo."""
    import config_anno
    monkeypatch.setattr(config_anno, 'get_anno_corrente', lambda app=None: '2026-2027')
    template_path = _salva_template(tmp_path, _template_con_due_anni())

    supplenze = [
        _supplenza('1BCAT', 3, assente='Rossi', sostituto='Verdi', tipo='recupero'),
        _supplenza('1B CAT', 4, assente='Bianchi', sostituto='Neri', tipo='pagamento'),
    ]

    xlsx_bytes, non_trovate, avviso_foglio = genera_prospetto(date(2026, 9, 15), supplenze, template_path)

    assert non_trovate == []
    assert avviso_foglio is None

    import io
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(xlsx_bytes))
    ws = wb[wb.sheetnames[0]]
    riga_1bcat = _righe_classi(ws)['1B CAT']
    ca3, cs3 = ORA_COLS[3]
    ca4, cs4 = ORA_COLS[4]
    assert ws.cell(riga_1bcat, ca3).value == 'Rossi'
    assert ws.cell(riga_1bcat, cs3).value == 'Verdi (R)'
    assert ws.cell(riga_1bcat, ca4).value == 'Bianchi'
    assert ws.cell(riga_1bcat, cs4).value == 'Neri (€)'


def test_genera_prospetto_segnala_classe_non_riconosciuta_ma_non_blocca(app, db_session, monkeypatch, tmp_path):
    """Una classe davvero non presente nel template non deve far
    fallire la generazione -- il file va comunque prodotto (con la
    supplenza visibile in tabella firme), e la classe va restituita
    perché la route la segnali a Roberto."""
    import config_anno
    monkeypatch.setattr(config_anno, 'get_anno_corrente', lambda app=None: '2026-2027')
    template_path = _salva_template(tmp_path, _template_con_due_anni())

    supplenze = [_supplenza('9Z INESISTENTE', 1, assente='Rossi', sostituto='Verdi')]

    xlsx_bytes, non_trovate, avviso_foglio = genera_prospetto(date(2026, 9, 15), supplenze, template_path)

    assert non_trovate == ['9Z INESISTENTE']
    assert xlsx_bytes  # il file viene comunque prodotto


def test_genera_prospetto_tabella_firme_indipendente_dal_riconoscimento_classe(app, db_session, monkeypatch, tmp_path):
    """Il supplente deve comparire nella tabella firme anche se la sua
    classe non viene riconosciuta -- è esattamente il comportamento
    che ha nascosto il problema finora (il nome in fondo c'era, quindi
    sembrava tutto a posto)."""
    import config_anno
    monkeypatch.setattr(config_anno, 'get_anno_corrente', lambda app=None: '2026-2027')
    template_path = _salva_template(tmp_path, _template_con_due_anni())

    supplenze = [_supplenza('9Z INESISTENTE', 1, assente='Rossi', sostituto='Verdi', tipo='recupero')]

    xlsx_bytes, non_trovate, _ = genera_prospetto(date(2026, 9, 15), supplenze, template_path)

    assert non_trovate == ['9Z INESISTENTE']

    import io
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(xlsx_bytes))
    ws = wb[wb.sheetnames[0]]
    col_doc = FIRME_COLS[0][0]
    inizio, _fine = _righe_firme(ws)
    assert ws.cell(inizio, col_doc).value == 'Verdi'


def test_genera_prospetto_avvisa_se_usa_foglio_di_un_altro_anno(app, db_session, monkeypatch, tmp_path):
    """Se il foglio dell'anno scolastico corrente non esiste ancora
    nel template, la generazione deve comunque procedere (ripiegando
    sul più recente) ma restituire un avviso, non fallire né
    procedere in silenzio con un foglio potenzialmente sbagliato."""
    import config_anno
    monkeypatch.setattr(config_anno, 'get_anno_corrente', lambda app=None: '2027-2028')
    template_path = _salva_template(tmp_path, _template_con_due_anni())

    xlsx_bytes, non_trovate, avviso_foglio = genera_prospetto(date(2027, 9, 15), [], template_path)

    assert avviso_foglio is not None
    assert 'MATRICE 26_27' in avviso_foglio
