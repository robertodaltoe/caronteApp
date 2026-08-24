"""
Bug reale trovato mentre Roberto chiedeva di ripulire le sostituzioni
del 31/08: 6 righe avevano n_protocollo/note impostati alla STRINGA
letterale "None" (4 caratteri), non NULL. Causa: in
templates/attivita_ist/sostituzioni_scrutinio.html il valore
dell'input veniva scritto come
`{{ riga.sostituzione.n_protocollo if riga.sostituzione else '' }}` —
quando la sostituzione esisteva ma il campo era ancora vuoto (Python
None, non stringa vuota), Jinja renderizza None come testo letterale
"None" nell'attributo value dell'input. Se il form veniva risalvato
senza pulire quel campo preriempito, "None" finiva scritto per davvero
nel database.
"""
from jinja2 import Template


class _FintaSostituzione:
    def __init__(self, n_protocollo=None, note=None):
        self.n_protocollo = n_protocollo
        self.note = note


def test_valore_none_non_produce_testo_letterale_none():
    tpl_vecchio = Template('{{ riga_sostituzione.n_protocollo if riga_sostituzione else "" }}')
    tpl_nuovo   = Template('{{ (riga_sostituzione.n_protocollo if riga_sostituzione else "") or "" }}')

    sost = _FintaSostituzione(n_protocollo=None)

    # Il pattern vecchio riproduce esattamente il bug: renderizza "None".
    assert tpl_vecchio.render(riga_sostituzione=sost) == 'None'
    # Il pattern nuovo (quello ora in uso nel template) non lo riproduce.
    assert tpl_nuovo.render(riga_sostituzione=sost) == ''


def test_valore_valorizzato_non_viene_toccato():
    tpl_nuovo = Template('{{ (riga_sostituzione.n_protocollo if riga_sostituzione else "") or "" }}')
    sost = _FintaSostituzione(n_protocollo='1234/2026')
    assert tpl_nuovo.render(riga_sostituzione=sost) == '1234/2026'
