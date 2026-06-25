"""
Test per genera_bozza(): il generatore di calendario per i corsi di
recupero di giugno. Diversamente dagli altri due generatori (agosto,
rientro), questa è una route Flask vera (richiede request.form,
flash, redirect) e usa vincoli di disponibilità per docente
(RecuperoVincolo) invece di un semplice controllo titolare/assistente.

Verifica i comportamenti critici:
- senza conferma_elimina, non genera nulla (richiede la checkbox)
- nessuna sovrapposizione tra alunni che condividono più gruppi
- i vincoli orari del docente vengono rispettati
- elimina solo le lezioni dei corsi di giugno, mai quelle di agosto
"""
from datetime import date
from models import db
from models.docente import Docente
from models.recupero import (RecuperoDocente, RecuperoGruppo, RecuperoLezione,
                              RecuperoAlunno, RecuperoVincolo)

from tests.conftest import crea_docente

ANNO = '2025-2026'


def _crea_rec_docente(docente, anno_scol=ANNO):
    rd = RecuperoDocente(id_docente=docente.id, anno_scol=anno_scol)
    db.session.add(rd)
    db.session.commit()
    return rd


def _crea_gruppo_giugno(rec_docente, materia, classi, n_alunni=2, max_ore=10, max_ore_giorno=2):
    g = RecuperoGruppo(id_rec_docente=rec_docente.id, materia=materia, classi=classi,
                        periodo_codice='corsi_giugno', max_ore=max_ore,
                        max_ore_giorno=max_ore_giorno)
    db.session.add(g)
    db.session.commit()
    for i in range(n_alunni):
        db.session.add(RecuperoAlunno(id_gruppo=g.id, classe=classi.split(',')[0].strip(),
                                       cognome=f'ALUNNO{i}', nome='Test'))
    db.session.commit()
    return g


def _posta_genera_bozza(client, conferma=True):
    data = {'conferma_elimina': '1'} if conferma else {}
    return client.post('/recupero/genera-bozza', data=data, follow_redirects=False)


def test_senza_conferma_non_genera_nulla(app_con_blueprint, db_session):
    """Senza la spunta di conferma, la route deve fare solo un redirect
    e non toccare nessuna lezione."""
    doc = crea_docente('ROSSI')
    rd = _crea_rec_docente(doc)
    g = _crea_gruppo_giugno(rd, 'MATEMATICA', '3ALSP')

    client = app_con_blueprint.test_client()
    resp = _posta_genera_bozza(client, conferma=False)

    assert resp.status_code == 302
    g_dopo = db.session.get(RecuperoGruppo, g.id)
    assert len(g_dopo.lezioni) == 0


def test_piazza_gruppo_senza_vincoli(app_con_blueprint, db_session):
    """Un gruppo senza vincoli orari per il docente deve essere
    piazzato (default 08:00-13:00 ogni giorno feriale del periodo)."""
    doc = crea_docente('ROSSI')
    rd = _crea_rec_docente(doc)
    g = _crea_gruppo_giugno(rd, 'MATEMATICA', '3ALSP')

    client = app_con_blueprint.test_client()
    resp = _posta_genera_bozza(client)

    assert resp.status_code == 302
    g_dopo = db.session.get(RecuperoGruppo, g.id)
    assert len(g_dopo.lezioni) >= 1


def test_rispetta_vincolo_giorno_docente(app_con_blueprint, db_session):
    """Se il docente ha un vincolo che lo rende disponibile solo il
    lunedì (giorno=0), tutte le lezioni generate devono cadere di
    lunedì."""
    doc = crea_docente('ROSSI')
    rd = _crea_rec_docente(doc)
    g = _crea_gruppo_giugno(rd, 'MATEMATICA', '3ALSP', max_ore=20, max_ore_giorno=2)

    db.session.add(RecuperoVincolo(id_rec_docente=rd.id, anno_scol=ANNO,
                                    giorno=0, ora_inizio='08:00', ora_fine='13:00'))
    db.session.commit()

    client = app_con_blueprint.test_client()
    resp = _posta_genera_bozza(client)
    assert resp.status_code == 302

    g_dopo = db.session.get(RecuperoGruppo, g.id)
    assert len(g_dopo.lezioni) >= 1
    for lez in g_dopo.lezioni:
        assert lez.data.weekday() == 0, f'lezione il {lez.data} (weekday={lez.data.weekday()}), non lunedì'


def test_due_gruppi_stesso_alunno_non_si_sovrappongono(app_con_blueprint, db_session):
    """Se lo stesso alunno (stesso cognome+nome+classe) è iscritto a due
    gruppi diversi, le lezioni dei due gruppi non devono mai avere
    lo stesso giorno+orario sovrapposto."""
    doc1 = crea_docente('ROSSI')
    doc2 = crea_docente('NERI')
    rd1 = _crea_rec_docente(doc1)
    rd2 = _crea_rec_docente(doc2)

    g1 = RecuperoGruppo(id_rec_docente=rd1.id, materia='MATEMATICA', classi='3ALSP',
                         periodo_codice='corsi_giugno', max_ore=10, max_ore_giorno=2)
    db.session.add(g1)
    db.session.commit()
    db.session.add(RecuperoAlunno(id_gruppo=g1.id, classe='3ALSP', cognome='COMUNE', nome='Studente'))

    g2 = RecuperoGruppo(id_rec_docente=rd2.id, materia='FISICA', classi='3ALSP',
                         periodo_codice='corsi_giugno', max_ore=10, max_ore_giorno=2)
    db.session.add(g2)
    db.session.commit()
    db.session.add(RecuperoAlunno(id_gruppo=g2.id, classe='3ALSP', cognome='COMUNE', nome='Studente'))
    db.session.commit()

    client = app_con_blueprint.test_client()
    resp = _posta_genera_bozza(client)
    assert resp.status_code == 302

    g1_dopo = db.session.get(RecuperoGruppo, g1.id)
    g2_dopo = db.session.get(RecuperoGruppo, g2.id)

    def _to_min(s):
        h, m = map(int, s.split(':'))
        return h * 60 + m

    for l1 in g1_dopo.lezioni:
        for l2 in g2_dopo.lezioni:
            if l1.data == l2.data:
                ini1, fin1 = _to_min(l1.ora_inizio), _to_min(l1.ora_fine)
                ini2, fin2 = _to_min(l2.ora_inizio), _to_min(l2.ora_fine)
                assert fin1 <= ini2 or fin2 <= ini1, \
                    f'sovrapposizione il {l1.data}: {l1.ora_inizio}-{l1.ora_fine} vs {l2.ora_inizio}-{l2.ora_fine}'


def test_non_tocca_lezioni_agosto(app_con_blueprint, db_session):
    """genera_bozza() deve eliminare/rigenerare solo le lezioni dei
    corsi di giugno: un gruppo con periodo_codice='prove_agosto' (anche
    con lo stesso id_rec_docente/anno_scol) non deve essere toccato."""
    doc = crea_docente('ROSSI')
    rd = _crea_rec_docente(doc)

    g_giugno = _crea_gruppo_giugno(rd, 'MATEMATICA', '3ALSP')

    g_agosto = RecuperoGruppo(id_rec_docente=rd.id, materia='MATEMATICA', classi='3ALSP',
                               periodo_codice='prove_agosto', tipo_prova='scritto', durata_ore=2.0)
    db.session.add(g_agosto)
    db.session.commit()
    db.session.add(RecuperoLezione(id_gruppo=g_agosto.id, data=date(2026, 8, 24),
                                    ora_inizio='09:00', ora_fine='11:00'))
    db.session.commit()

    client = app_con_blueprint.test_client()
    resp = _posta_genera_bozza(client)
    assert resp.status_code == 302

    g_agosto_dopo = db.session.get(RecuperoGruppo, g_agosto.id)
    assert len(g_agosto_dopo.lezioni) == 1
    assert g_agosto_dopo.lezioni[0].data == date(2026, 8, 24)
    assert g_agosto_dopo.lezioni[0].ora_inizio == '09:00'


def test_export_xlsx_funziona_dopo_lo_split(app_con_blueprint, db_session):
    """Verifica che export_xlsx() (spostata in recupero_export.py durante
    lo split del modulo) sia ancora raggiungibile e produca un file XLSX
    valido, senza errori di import circolare o riferimenti rotti."""
    doc = crea_docente('ROSSI')
    rd = _crea_rec_docente(doc)
    g = _crea_gruppo_giugno(rd, 'MATEMATICA', '3ALSP')
    db.session.add(RecuperoLezione(id_gruppo=g.id, data=date(2026, 6, 18),
                                    ora_inizio='09:00', ora_fine='11:00'))
    db.session.commit()

    client = app_con_blueprint.test_client()
    resp = client.get('/recupero/export-xlsx')

    assert resp.status_code == 200
    assert resp.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    assert len(resp.get_data()) > 0
