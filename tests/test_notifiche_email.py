from datetime import date, timedelta

import pytest

from models import db
from models.docente import Docente
from models.supplenza import Supplenza
from models.email_uscita import EmailUscita
from modules import notifiche_email as ne

MAIL = 'mario.rossi@davincichiavenna.edu.it'


def _doc(cognome='Rossi', email=MAIL):
    d = Docente(cognome=cognome, nome='Mario', email=email, attivo=True)
    db.session.add(d)
    db.session.flush()
    return d


def _supp(giorno, sost, ass, ora=3, classe='3A', stato='assegnata'):
    s = Supplenza(data=giorno, ora=ora, classe=classe, id_assente=ass.id,
                  id_sostituto=sost.id if sost else None, stato=stato)
    db.session.add(s)
    db.session.commit()
    return s


def _setup(giorni=3):
    g = date.today() + timedelta(days=giorni)
    sost, ass = _doc(), _doc('Bianchi', 'a.b@davincichiavenna.edu.it')
    _supp(g, sost, ass, ora=3)
    _supp(g, sost, ass, ora=5, classe='4B')
    return g, sost, ass


def test_giorno_default_si_lavora_il_sabato():
    assert ne.giorno_default(date(2026, 10, 23)) == date(2026, 10, 24)  # ven -> sab
    assert ne.giorno_default(date(2026, 10, 24)) == date(2026, 10, 26)  # sab -> lun
    assert ne.giorno_default(date(2026, 10, 25)) == date(2026, 10, 26)  # dom -> lun
    assert ne.giorno_default(date(2026, 10, 26)) == date(2026, 10, 27)


def test_un_messaggio_per_docente_con_tutte_le_supplenze(app):
    with app.test_request_context():
        g, sost, _ = _setup()
        p = ne.proposte_supplenze(g)
        assert len(p) == 1 and p[0]['variante'] == 'nuova'
        c = p[0]['corpo']
        assert '3A' in c and '4B' in c
        assert 'Bianchi' not in c  # dato potenzialmente sensibile
        assert c.startswith('Gentile collega,')


def test_off_non_registra(app, monkeypatch):
    monkeypatch.delenv('CARONTE_EMAIL_MODE', raising=False)
    with app.test_request_context():
        g, sost, _ = _setup()
        ne.invia_supplenze(g, [sost.id])
        assert EmailUscita.query.count() == 0


def test_simulato_poi_gia_inviata_poi_variazione_poi_annullamento(app, monkeypatch):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'simulato')
    with app.test_request_context():
        g, sost, ass = _setup()
        assert ne.invia_supplenze(g, [sost.id])[0][1] == 'simulata'
        assert ne.proposte_supplenze(g)[0]['variante'] == 'gia_inviata'
        assert ne.invia_supplenze(g, [sost.id])[0][1] == 'saltata'
        # nuova supplenza -> variazione
        _supp(g, sost, ass, ora=6)
        p = ne.proposte_supplenze(g)[0]
        assert p['variante'] == 'variazione' and p['oggetto'].startswith('VARIAZIONE')
        ne.invia_supplenze(g, [sost.id])
        # tutte annullate -> annullamento
        for s in Supplenza.query.all():
            s.stato = 'annullata'
        db.session.commit()
        p = ne.proposte_supplenze(g)[0]
        assert p['variante'] == 'annullamento' and p['righe'] == []


@pytest.mark.parametrize('email,motivo', [
    (None, 'email mancante'), ('x@gmail.com', 'fuori dominio')])
def test_indirizzi_non_inviabili(app, monkeypatch, email, motivo):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'simulato')
    with app.test_request_context():
        g = date.today() + timedelta(days=2)
        sost, ass = _doc(email=email), _doc('Bianchi')
        _supp(g, sost, ass)
        r = ne.invia_supplenze(g, [sost.id])
        assert r[0][1] == 'saltata' and motivo in r[0][2]


def test_reale_rispetta_lista_di_prova_e_registra_errori(app, monkeypatch):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'reale')
    monkeypatch.setenv('CARONTE_EMAIL_SOLO_A', 'altro@davincichiavenna.edu.it')
    inviati = []
    monkeypatch.setattr('modules.gmail_invio.invia', lambda *a, **k: inviati.append(a))
    with app.test_request_context():
        g, sost, _ = _setup()
        assert ne.invia_supplenze(g, [sost.id])[0] == ('Rossi', 'saltata', 'fuori lista di prova')
        assert inviati == []
        monkeypatch.setenv('CARONTE_EMAIL_SOLO_A', MAIL)
        assert ne.invia_supplenze(g, [sost.id])[0][1] == 'inviata'
        assert inviati and inviati[0][0] == MAIL


def test_reale_errore_gmail_non_segna_come_inviata(app, monkeypatch):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'reale')
    def boom(*a, **k):
        raise RuntimeError('manca gmail_token.json')
    monkeypatch.setattr('modules.gmail_invio.invia', boom)
    with app.test_request_context():
        g, sost, _ = _setup()
        assert ne.invia_supplenze(g, [sost.id])[0][1] == 'errore'
        assert ne.proposte_supplenze(g)[0]['variante'] == 'nuova'  # reinviabile


def test_non_si_invia_per_giorni_passati(app, monkeypatch):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'simulato')
    with app.test_request_context():
        g, sost, _ = _setup(giorni=-1)
        assert ne.invia_supplenze(g, [sost.id])[0][1] == 'errore'


def test_messaggio_gmail_senza_from_e_con_destinatario():
    from modules.gmail_invio import costruisci
    m = costruisci(MAIL, 'Oggetto', 'Corpo')
    assert m['To'] == MAIL and m['From'] is None


def test_impostazione_salvata_vince_sulla_variabile(app, monkeypatch):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'reale')
    with app.test_request_context():
        assert ne.modalita() == 'reale'
        ne.imposta('simulato', 'a@davincichiavenna.edu.it; b@davincichiavenna.edu.it')
        assert ne.modalita() == 'simulato'
        assert ne._solo_a() == {'a@davincichiavenna.edu.it', 'b@davincichiavenna.edu.it'}
        with pytest.raises(ValueError):
            ne.imposta('boh')


def test_banca_ore_tutti_i_docenti_un_invio_al_mese(app, monkeypatch):
    from models.movimento_banca_ore import MovimentoBancaOre
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'simulato')
    monkeypatch.setattr('routes.report.get_saldi_docente',
                        lambda i, anno_scol=None: dict(supplenze=5, permessi=1, civica=0, pagamento=1))
    monkeypatch.setattr('config_anno.get_anno_corrente', lambda: '2026-2027')
    with app.test_request_context():
        a, b = _doc(), _doc('Verdi', None)
        db.session.commit()
        mese = ne.primo_del_mese()
        p = ne.proposte_banca_ore(mese)
        assert len(p) == 2 and 'Saldo netto: 3 h' in p[1]['corpo'] + p[0]['corpo']
        r = dict((n, s) for n, s, _ in ne.invia_banca_ore(mese, [a.id, b.id]))
        assert r == {'Rossi': 'simulata', 'Verdi': 'saltata'}
        assert ne.proposte_banca_ore(mese)[0]['variante'] == 'gia_inviata'
        # saldi cambiati -> aggiornamento
        monkeypatch.setattr('routes.report.get_saldi_docente',
                            lambda i, anno_scol=None: dict(supplenze=9, permessi=1, civica=0, pagamento=1))
        p = ne.proposte_banca_ore(mese)
        assert p[0]['variante'] == 'aggiornamento' and p[0]['oggetto'].startswith('AGGIORNAMENTO')


def test_banca_ore_reale_senza_pdf_invia_comunque_il_testo(app, monkeypatch):
    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'reale')
    monkeypatch.setattr('routes.report.get_saldi_docente',
                        lambda i, anno_scol=None: dict(supplenze=2, permessi=0, civica=0, pagamento=0))
    monkeypatch.setattr('config_anno.get_anno_corrente', lambda: '2026-2027')
    monkeypatch.setattr(ne, '_pdf_banca_ore', lambda d: (_ for _ in ()).throw(RuntimeError('no weasyprint')))
    inviati = []
    monkeypatch.setattr('modules.gmail_invio.invia', lambda *a, **k: inviati.append(a))
    with app.test_request_context():
        a = _doc()
        db.session.commit()
        r = ne.invia_banca_ore(ne.primo_del_mese(), [a.id])
        assert r == [('Rossi', 'inviata', 'inviato senza PDF')]
        assert inviati and inviati[0][3] == []


def test_riga_con_materia_e_tipo_ora(app):
    from models.orario_docente import OrarioDocente
    with app.test_request_context():
        g, sost, ass = _setup()
        db.session.add(OrarioDocente(id_docente=ass.id, giorno=g.weekday(), ora=3,
                                     classe='3A', materia='Italiano'))
        for s in Supplenza.query.filter_by(ora=3):
            s.tipo = 'recupero'
        db.session.commit()
        c = ne.proposte_supplenze(g)[0]['corpo']
        assert 'classe 3A, Italiano (recupero)' in c


def test_modello_personalizzabile_con_default(app):
    with app.test_request_context():
        g, sost, _ = _setup()
        ne.imposta_modello('Ciao {NOME}!', 'Per {GIORNO}:', 'Fine.')
        c = ne.proposte_supplenze(g)[0]['corpo']
        assert c.startswith('Ciao Mario!') and 'Per ' in c and c.rstrip().endswith('Fine.')
        ne.imposta_modello('', '', '')
        assert ne.proposte_supplenze(g)[0]['corpo'].startswith('Gentile collega,')
