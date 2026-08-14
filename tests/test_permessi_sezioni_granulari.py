"""
Test di regressione per la Sessione 53: sezioni permessi scorporate in
sotto-sezioni singole (prima erano raggruppate, es. 'attivita' copriva
insieme fuori aula/istituzionali/differite) + nuova sezione 'orario_globale'
(prima hardcoded ds/dsga, mai passata dalla matrice permessi).

Verifica soprattutto la migrazione (_migra_split_sezioni_permessi): su
un'installazione già in uso, le sezioni nuove devono ereditare il livello
già salvato per la sezione genitore, non ripartire da 'esclusa' — altrimenti
un accesso che funzionava prima dello scorporo sparirebbe di colpo.
"""
from models import db
from models.permesso_ruolo import (
    PermessoRuolo, SPLIT_DA, DEFAULT_MATRICE,
    BLUEPRINT_DSGA_ONLY_ECCEZIONI, matrice_permessi, invalida_cache,
    _migra_split_sezioni_permessi,
)


def _crea_permesso(ruolo, sezione, livello):
    db.session.add(PermessoRuolo(ruolo=ruolo, sezione=sezione, livello=livello))
    db.session.commit()


def _crea_tabella(app):
    with app.app_context():
        db.create_all()


def test_sezione_figlia_eredita_livello_gia_salvato_della_madre(app, db_session):
    _crea_tabella(app)
    with app.app_context():
        # Simula una configurazione già personalizzata dal DS prima dello
        # scorporo: 'attivita' aveva 'modifica' per il collaboratore,
        # diverso dal default ('modifica' anche di default qui, quindi
        # usiamo 'supplenze' che di default è 'visualizza' per la segreteria
        # ma il DS lo aveva alzato a 'modifica' — un caso dove copiare il
        # default sarebbe SBAGLIATO e dimostra che la migrazione legge la
        # riga reale, non DEFAULT_MATRICE.
        _crea_permesso('segreteria', 'supplenze', 'modifica')

        invalida_cache()
        _migra_split_sezioni_permessi()

        m = matrice_permessi()
        # 'cambi' e 'agenda' sono scorporate da 'supplenze' (vedi SPLIT_DA)
        assert m['segreteria']['cambi'] == 'modifica'
        assert m['segreteria']['agenda'] == 'modifica'
        # Il default di DEFAULT_MATRICE per segreteria/supplenze sarebbe
        # 'visualizza': se la migrazione avesse usato il default invece
        # della riga reale, questo test fallirebbe.
        assert DEFAULT_MATRICE['supplenze']['segreteria'] == 'visualizza'


def test_migrazione_non_sovrascrive_sezione_gia_configurata(app, db_session):
    _crea_tabella(app)
    with app.app_context():
        _crea_permesso('collaboratore', 'attivita', 'modifica')
        # Il DS ha già configurato a mano 'attivita_istituzionali' con un
        # valore diverso da quello che avrebbe ereditato dal genitore.
        _crea_permesso('collaboratore', 'attivita_istituzionali', 'esclusa')

        invalida_cache()
        _migra_split_sezioni_permessi()

        m = matrice_permessi()
        assert m['collaboratore']['attivita_istituzionali'] == 'esclusa'


def test_migrazione_idempotente(app, db_session):
    _crea_tabella(app)
    with app.app_context():
        _migra_split_sezioni_permessi()
        n1 = PermessoRuolo.query.count()
        _migra_split_sezioni_permessi()
        n2 = PermessoRuolo.query.count()
        assert n1 == n2


def test_orario_globale_seed_indipendente_da_orario_sostegno(app, db_session):
    """orario_globale non e' nato da uno scorporo (prima era hardcoded
    ds/dsga): non deve ereditare da 'orario' (orario di sostegno, un
    concetto diverso), ma usare il proprio default dedicato."""
    _crea_tabella(app)
    with app.app_context():
        _crea_permesso('collaboratore', 'orario', 'modifica')
        invalida_cache()
        _migra_split_sezioni_permessi()

        m = matrice_permessi()
        assert m['collaboratore']['orario'] == 'modifica'
        assert m['collaboratore']['orario_globale'] == 'esclusa'
        assert m['ds']['orario_globale'] == 'modifica'
        assert 'orario_globale' not in SPLIT_DA


def test_tutte_le_sezioni_figlie_hanno_un_genitore_valido():
    codici_default = set(DEFAULT_MATRICE.keys())
    for figlia, madre in SPLIT_DA.items():
        assert madre in codici_default, f"genitore '{madre}' di '{figlia}' non in DEFAULT_MATRICE"
        assert figlia in codici_default


def test_import_modifica_orario_resta_fuori_dalle_eccezioni_dsga_only():
    """sync.index/sync.importa (sovrascrivono l'orario) devono restare
    hardcoded DSGA/DS — solo la vista di sola lettura orario_globale
    puo' diventare configurabile dalla matrice."""
    assert 'sync.orario_globale' in BLUEPRINT_DSGA_ONLY_ECCEZIONI
    assert 'sync.index' not in BLUEPRINT_DSGA_ONLY_ECCEZIONI
    assert 'sync.importa' not in BLUEPRINT_DSGA_ONLY_ECCEZIONI
