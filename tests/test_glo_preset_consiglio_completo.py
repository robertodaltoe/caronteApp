"""
Roberto, su "GLO 1 LSC": "se provo a risincronizzare le presenze [...]
mi dice che vanno rimossi tutti e gli otto partecipanti membri del
consiglio indicati da assegnazioni. come mai?" — e a chiarimento:
"anche perchè nei glo partecipa il consiglio di classe completo del
docente di sostegno (già assegnato correttamente alla classe come un
docenti titolare)".

Causa: _preset_partecipanti() per tipo=='glo' ritornava sempre lista
vuota ("solo manuale", pensato perché la composizione di un GLO
dipenderebbe dall'alunno seguito) — mentre nella pratica reale un GLO
coinvolge tutto il consiglio di classe, sostegno compreso, esattamente
come consiglio_classe/scrutinio. La risincronizzazione confronta
l'elenco congelato con questo preset "adesso": essendo sempre vuoto per
i GLO, proponeva SEMPRE di rimuovere tutti i partecipanti reali, per
qualunque evento GLO.

Fix: il branch 'glo' di _preset_partecipanti() ora usa lo stesso
calcolo di consiglio_classe/scrutinio (OrarioDocente.classe +
_docenti_sostegno_per_classe), così la risincronizzazione torna
utilizzabile e non propone più di svuotare un GLO correttamente
popolato.
"""
from datetime import date, timedelta
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
from models.classe_concorso import ClasseConcorso
from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse
from models.orario_docente import OrarioDocente
from tests.conftest import crea_docente

FUTURO = date.today() + timedelta(days=30)
ANNO = f'{FUTURO.year}-{FUTURO.year+1}' if FUTURO.month >= 9 else f'{FUTURO.year-1}-{FUTURO.year}'


def _registra_blueprint(app):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)


def _assegna_sostegno(docente, anno_corso, indirizzo, sezione='A', ore=9):
    cc = ClasseConcorso.query.filter_by(codice='ADSS').first()
    if not cc:
        cc = ClasseConcorso(codice='ADSS', nome='Sostegno', tipo_posto='sostegno')
        db.session.add(cc)
        db.session.commit()
    asgn = AssegnazioneDocente(anno_scol=ANNO, id_classe_concorso=cc.id,
                                id_docente=docente.id, tipo='titolare')
    db.session.add(asgn)
    db.session.flush()
    db.session.add(AssegnazioneClasse(id_assegnazione=asgn.id, indirizzo=indirizzo,
                                       anno_corso=anno_corso, sezione=sezione, ore=ore))
    db.session.commit()
    return asgn


def test_preset_glo_coincide_con_consiglio_di_classe_completo(app, db_session):
    curricolare = crea_docente('Rossi')
    db.session.add(OrarioDocente(id_docente=curricolare.id, classe='1A LSC',
                                  giorno='lun', ora=1))
    sos = crea_docente('Ferrari')
    _assegna_sostegno(sos, 1, 'LSC', sezione='A')
    db.session.commit()

    from routes.attivita_ist import _preset_partecipanti
    ev_glo = AttivitaIst(tipo='glo', titolo='GLO 1A LSC', classe='1A LSC',
                          data=FUTURO, origine='manuale')
    ev_cdc = AttivitaIst(tipo='consiglio_classe', titolo='CdC 1A LSC', classe='1A LSC',
                          data=FUTURO, origine='manuale')
    db.session.add_all([ev_glo, ev_cdc])
    db.session.flush()

    ids_glo = set(_preset_partecipanti(ev_glo))
    ids_cdc = set(_preset_partecipanti(ev_cdc))

    assert curricolare.id in ids_glo
    assert sos.id in ids_glo
    assert ids_glo == ids_cdc


def test_risincronizza_non_propone_di_svuotare_un_glo_popolato_da_assegnazioni(app, db_session, monkeypatch):
    _registra_blueprint(app)

    docenti = [crea_docente(f'Doc{i}') for i in range(3)]
    for d in docenti:
        db.session.add(OrarioDocente(id_docente=d.id, classe='1A LSC', giorno='lun', ora=1))
    sos = crea_docente('Ferrari')
    _assegna_sostegno(sos, 1, 'LSC', sezione='A')
    db.session.commit()

    ev = AttivitaIst(tipo='glo', titolo='GLO 1A LSC', classe='1A LSC',
                      data=FUTURO, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    for d in docenti + [sos]:
        db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d.id, preset=True))
    db.session.commit()

    import routes.attivita_ist as mod
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev.id}/risincronizza')
        assert r.status_code == 200

    assert catturato['kwargs']['da_rimuovibili'] == []
    assert catturato['kwargs']['non_rimovibili'] == []
