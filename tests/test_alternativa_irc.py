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


# ── Assenza del docente dell'alternativa -> supplenza ────────────────

def _con_docente_assegnato():
    g = _scenario()
    doc = crea_docente('Incaricato')
    _slot(doc, 0, 1, '1ACAT')
    db.session.add(AlternativaIrcDisponibilita(anno_scol=ANNO, id_docente=doc.id))
    db.session.commit()
    assert air.assegna(g, id_docente=doc.id)[0]
    return g, doc


def _tabelle_supplenze(app):
    with app.app_context():
        from models.attivita_fuori_aula import AttivitaFuoriAula, AttivitaClasse  # noqa
        db.create_all()


def test_assenza_del_docente_genera_supplenza_per_il_gruppo(app, db_session):
    from models.supplenza import Supplenza
    from modules.assenze_registrazione import _genera_supplenze
    _tabelle_supplenze(app)
    g, doc = _con_docente_assegnato()
    martedi = date(2026, 9, 22)
    n = _genera_supplenze(doc.id, martedi, 1, 9, True, note_display='')
    db.session.commit()
    sup = Supplenza.query.filter_by(id_assente=doc.id, data=martedi).all()
    assert n == 1 and len(sup) == 1
    assert (sup[0].ora, sup[0].classe, sup[0].stato) == (3, 'ALT. IRC', 'scoperta')
    assert '3A LLI' in sup[0].note and '3B LLI' in sup[0].note
    # idempotente
    assert _genera_supplenze(doc.id, martedi, 1, 9, True, note_display='') == 0


def test_supplenza_solo_nelle_ore_dell_assenza_e_nel_giorno_giusto(app, db_session):
    from modules.assenze_registrazione import _genera_supplenze
    _tabelle_supplenze(app)
    g, doc = _con_docente_assegnato()
    assert _genera_supplenze(doc.id, date(2026, 9, 22), 1, 2, True, note_display='') == 0  # ora 3 fuori
    assert _genera_supplenze(doc.id, date(2026, 9, 23), 1, 9, True, note_display='') == 0  # mercoledì


def test_ricalcolo_periodo_non_cancella_la_supplenza_dell_alternativa(app, db_session):
    from models.assenza import Assenza
    from models.supplenza import Supplenza
    from modules.assenze_registrazione import _genera_supplenze, ricalcola_supplenze_periodo
    _tabelle_supplenze(app)
    g, doc = _con_docente_assegnato()
    martedi = date(2026, 9, 22)
    db.session.add(Assenza(id_docente=doc.id, data=martedi, ora_inizio=1, ora_fine=9, motivo='malattia'))
    db.session.commit()
    _genera_supplenze(doc.id, martedi, 1, 9, True, note_display='')
    db.session.commit()
    esito = ricalcola_supplenze_periodo(martedi, martedi, oggi=date(2026, 9, 1))
    assert esito['cancellate'] == 0
    assert Supplenza.query.filter_by(id_assente=doc.id, classe='ALT. IRC').count() == 1


# ── Nessun limite fisso su classi e gruppi ───────────────────────────

def test_fino_a_quaranta_gruppi_e_tutte_le_classi_in_elenco(app, db_session):
    doc = crea_docente('Religione')
    n_classi = 40
    for i in range(n_classi):
        cl = f'{(i % 5) + 1}{chr(65 + i // 5)}CAT'
        _slot(doc, i % 6, (i // 6) + 1, cl, 'RELIGIONE')
        db.session.add(AlternativaIrcAdesione(anno_scol=ANNO, classe=cl, n_con_docente=2))
    db.session.commit()
    esito = air.genera_gruppi(ANNO)
    assert esito['creati'] == AlternativaIrcGruppo.query.count() == n_classi


def test_classi_senza_ora_di_religione_in_orario_compaiono_comunque(app, db_session):
    doc = crea_docente('Religione')
    _slot(doc, 0, 1, '1ACAT', 'RELIGIONE')
    altro = crea_docente('Altro')
    _slot(altro, 0, 2, '2BCAT', 'MATEMATICA')    # 2BCAT: religione non ancora in orario
    db.session.commit()
    righe = {r['classe']: r for r in air.classi_con_adesione(ANNO)}
    assert righe['1ACAT']['n_slot'] == 1
    assert righe['2BCAT']['n_slot'] == 0
