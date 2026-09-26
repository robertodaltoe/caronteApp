from types import SimpleNamespace as NS
from modules.parser_orario import _marca_compresenze_itp


def _r(giorno, ora, classe, tipo='lezione'):
    return NS(giorno=giorno, ora=ora, classe=classe, tipo_ora=tipo)


def test_itp_con_titolare_diventa_compresenza():
    tit, itp = NS(id=1, ruolo='titolare'), NS(id=2, ruolo='itp')
    r_tit, r_itp = _r(0, 1, '3ACAT'), _r(0, 1, '3ACAT')
    _marca_compresenze_itp([(tit, r_tit), (itp, r_itp)])
    assert r_itp.tipo_ora == 'compresenza' and r_tit.tipo_ora == 'lezione'


def test_itp_da_solo_resta_lezione():
    itp = NS(id=2, ruolo='itp')
    r = _r(0, 3, '5ACAT')
    _marca_compresenze_itp([(itp, r)])
    assert r.tipo_ora == 'lezione'


def test_due_titolari_o_due_itp_non_cambiano():
    a, b = NS(id=1, ruolo='titolare'), NS(id=2, ruolo='titolare')
    c, d = NS(id=3, ruolo='itp'), NS(id=4, ruolo='itp')
    ra, rb, rc, rd = _r(0, 1, '1A'), _r(0, 1, '1A'), _r(0, 2, '1A'), _r(0, 2, '1A')
    _marca_compresenze_itp([(a, ra), (b, rb), (c, rc), (d, rd)])
    assert {ra.tipo_ora, rb.tipo_ora, rc.tipo_ora, rd.tipo_ora} == {'lezione'}
