"""
Attività alternativa all'IRC (nota MIM 11814/2026, punto 3.7): fabbisogno
dalle ore di religione in orario, gruppi per slot, candidati nell'ordine
di priorità della circolare e regole di esclusione volute da Roberto
(potenziamento no, chi completa l'orario sì, solo chi ha dato
disponibilità per le ore eccedenti, giorni presso altra scuola come
indisponibilità, docente fisso per tutto l'anno).
"""
from datetime import date

from models import db
from models.alternativa_irc import (AlternativaIrcAdesione, AlternativaIrcDisponibilita,
                                    AlternativaIrcGruppo)
from models.indisponibilita_ricorrente import IndisponibilitaRicorrente
from models.orario_docente import OrarioDocente
from modules import alternativa_irc as air
from tests.conftest import crea_docente

ANNO = '2026-2027'


def _slot(doc, giorno, ora, classe, materia='X', tipo='lezione'):
    db.session.add(OrarioDocente(id_docente=doc.id, giorno=giorno, ora=ora,
                                  classe=classe, materia=materia, tipo_ora=tipo))


def _scenario():
    """Due classi con religione martedì 3ª ora (Ghezzi), 5 e 4 studenti."""
    ghezzi = crea_docente('Ghezzi', materia='Religione')
    _slot(ghezzi, 1, 3, '3ALLI', 'RELIGIONE')
    _slot(ghezzi, 1, 3, '3BLLI', 'RELIGIONE')
    db.session.add(AlternativaIrcAdesione(anno_scol=ANNO, classe='3ALLI', n_con_docente=5))
    db.session.add(AlternativaIrcAdesione(anno_scol=ANNO, classe='3BLLI', n_con_docente=4))
    db.session.commit()
    air.genera_gruppi(ANNO)
    return AlternativaIrcGruppo.query.filter_by(anno_scol=ANNO).one()


def _ids(cand, livello):
    return [v['docente'].id for v in cand['livelli'][livello]]


def test_gruppo_per_slot_con_classi_e_studenti(app, db_session):
    g = _scenario()
    assert (g.giorno, g.ora) == (1, 3)
    assert g.classi_list == ['3ALLI', '3BLLI']
    assert air.n_studenti_gruppo(g) == 9


def test_classe_senza_studenti_non_genera_gruppo(app, db_session):
    d = crea_docente('Ghezzi')
    _slot(d, 0, 2, '1ACAT', 'RELIGIONE')
    db.session.add(AlternativaIrcAdesione(anno_scol=ANNO, classe='1ACAT', n_con_docente=0, n_altre=3))
    db.session.commit()
    assert air.genera_gruppi(ANNO)['creati'] == 0


def test_rigenerare_non_perde_il_docente_assegnato(app, db_session):
    g = _scenario()
    doc = crea_docente('Disponibile')
    _slot(doc, 0, 1, '1ACAT')
    db.session.add(AlternativaIrcDisponibilita(anno_scol=ANNO, id_docente=doc.id))
    db.session.commit()
    ok, _ = air.assegna(g, id_docente=doc.id)
    assert ok
    air.genera_gruppi(ANNO)
    assert AlternativaIrcGruppo.query.one().id_docente == doc.id


def test_priorita_1_a_disposizione_e_completamento_orario(app, db_session):
    g = _scenario()
    a_disp = crea_docente('Adisposizione')
    _slot(a_disp, 1, 3, 'DISPOSIZIONE', tipo='disposizione')
    _slot(a_disp, 0, 1, '1ACAT')
    completa = crea_docente('Completa')   # 18 ore di contratto, ne ha 1
    _slot(completa, 0, 1, '1ACAT')
    db.session.commit()
    cand = air.candidati(g)
    assert _ids(cand, 1)[0] == a_disp.id
    assert completa.id in _ids(cand, 1)
    assert _ids(cand, 2) == []


def test_docente_con_orario_completo_non_e_candidato_senza_disponibilita(app, db_session):
    g = _scenario()
    pieno = crea_docente('Pieno')
    for i in range(18):
        _slot(pieno, i % 6 if i % 6 != 1 else 2, (i // 6) + 4, '1ACAT')
    db.session.commit()
    cand = air.candidati(g)
    tutti = _ids(cand, 1) + _ids(cand, 2)
    assert pieno.id not in tutti


def test_priorita_2_solo_chi_ha_dato_disponibilita(app, db_session):
    g = _scenario()
    volontario = crea_docente('Volontario', ruolo='titolare')
    non_volontario = crea_docente('Altro')
    for d in (volontario, non_volontario):
        for i in range(18):
            _slot(d, i % 6 if i % 6 != 1 else 2, (i // 6) + 4, '1ACAT')
    db.session.add(AlternativaIrcDisponibilita(anno_scol=ANNO, id_docente=volontario.id,
                                               tipo='ore_eccedenti'))
    db.session.commit()
    cand = air.candidati(g)
    assert _ids(cand, 2) == [volontario.id]


def test_potenziamento_non_e_disponibile(app, db_session):
    g = _scenario()
    pot = crea_docente('Potenziamento')
    _slot(pot, 1, 3, 'POTENZIAMENTO', tipo='potenziamento')
    db.session.add(AlternativaIrcDisponibilita(anno_scol=ANNO, id_docente=pot.id))
    db.session.commit()
    cand = air.candidati(g)
    assert pot.id not in _ids(cand, 1) + _ids(cand, 2)
    assert any(e['docente'].id == pot.id for e in cand['esclusi'])


def test_esclude_chi_insegna_in_una_classe_del_gruppo(app, db_session):
    g = _scenario()
    prof = crea_docente('Prof3A')
    _slot(prof, 3, 5, '3ALLI', 'MATEMATICA')   # altro giorno, ma stessa classe
    db.session.add(AlternativaIrcDisponibilita(anno_scol=ANNO, id_docente=prof.id))
    db.session.commit()
    cand = air.candidati(g)
    assert prof.id not in _ids(cand, 1) + _ids(cand, 2)
    assert 'insegna nella classe 3A LLI' in [e['dettaglio'] for e in cand['esclusi']
                                               if e['docente'].id == prof.id][0]


def test_giorno_presso_altra_scuola_e_indisponibilita(app, db_session):
    g = _scenario()
    multi = crea_docente('Multisede')
    multi.altra_scuola = 'IIS Altrove'
    multi.giorni_presenza = '0,2,4'      # martedì (1) è presso l'altra scuola
    _slot(multi, 0, 1, '1ACAT')
    db.session.add(AlternativaIrcDisponibilita(anno_scol=ANNO, id_docente=multi.id))
    db.session.commit()
    cand = air.candidati(g)
    assert multi.id not in _ids(cand, 1) + _ids(cand, 2)
    assert 'altra scuola' in cand['esclusi'][0]['dettaglio']


def test_indisponibilita_ricorrente_esclude(app, db_session):
    g = _scenario()
    d = crea_docente('Colloqui')
    _slot(d, 0, 1, '1ACAT')
    db.session.add(IndisponibilitaRicorrente(id_docente=d.id, giorno=1, ora=3))
    db.session.commit()
    assert d.id not in _ids(air.candidati(g), 1)


def test_non_si_assegna_un_docente_non_candidabile(app, db_session):
    g = _scenario()
    intruso = crea_docente('Intruso')
    for i in range(18):
        _slot(intruso, i % 6 if i % 6 != 1 else 2, (i // 6) + 4, '1ACAT')
    db.session.commit()
    ok, msg = air.assegna(g, id_docente=intruso.id)
    assert not ok
    assert AlternativaIrcGruppo.query.one().id_docente is None


def test_da_nominare_e_riepilogo(app, db_session):
    g = _scenario()
    air.assegna(g, da_nominare=True)
    riep = air.riepilogo(ANNO)
    assert riep['n_gruppi'] == 1 and riep['n_da_nominare'] == 1 and riep['n_scoperti'] == 0
    assert riep['n_studenti'] == 9


def test_stesso_docente_non_su_due_gruppi_alla_stessa_ora(app, db_session):
    g = _scenario()
    doc = crea_docente('Doppio')
    _slot(doc, 0, 1, '1ACAT')
    db.session.add(AlternativaIrcDisponibilita(anno_scol=ANNO, id_docente=doc.id))
    db.session.commit()
    assert air.assegna(g, id_docente=doc.id)[0]
    # un secondo gruppo nello stesso slot (manuale) non può riusarlo
    g2 = AlternativaIrcGruppo(anno_scol=ANNO, giorno=1, ora=3)
    db.session.add(g2)
    db.session.commit()
    assert doc.id not in _ids(air.candidati(g2), 1) + _ids(air.candidati(g2), 2)


def test_docente_assegnato_e_occupato_nelle_supplenze(app, db_session):
    from modules.suggerimenti_supplenza import docenti_occupati_stessa_ora
    g = _scenario()
    doc = crea_docente('Incaricato')
    _slot(doc, 0, 1, '1ACAT')
    db.session.add(AlternativaIrcDisponibilita(anno_scol=ANNO, id_docente=doc.id))
    db.session.commit()
    air.assegna(g, id_docente=doc.id)
    martedi = date(2026, 9, 22)          # martedì dell'anno 2026-2027
    assert martedi.weekday() == 1
    assert doc.id in docenti_occupati_stessa_ora(martedi, 3)[0]
    assert doc.id not in docenti_occupati_stessa_ora(martedi, 4)[0]
    assert doc.id not in docenti_occupati_stessa_ora(date(2026, 9, 21), 3)[0]


def test_xlsx_contiene_gruppi_e_adesioni(app, db_session):
    _scenario()
    wb = air.genera_xlsx(ANNO)
    assert wb.sheetnames == ['Gruppi', 'Adesioni']
    assert wb['Gruppi'].cell(2, 1).value == 'Martedì'
    assert wb['Gruppi'].cell(2, 4).value == 9
