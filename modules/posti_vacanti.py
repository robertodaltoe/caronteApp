"""
modules/posti_vacanti.py — orario dei docenti non ancora nominati.

- salva_slot_posti(): chiamata dall'import orario, conserva le righe dei
  nomi non riconosciuti come docenti (vedi models/posto_vacante.py).
- ricalcola_supplenze_posti(): per i posti collegati, genera da oggi le
  supplenze "da assegnare" (id_assente NULL, note 'POSTO_VACANTE|<chiave>')
  e toglie quelle non piu' coerenti. Solo da oggi in poi.
- nomina_posto(): quando arriva il docente vero, le ore passano al suo
  orario e le supplenze future del posto si cancellano (e' in servizio).

Le supplenze dei posti non hanno id_assente: non contano come ore di un
assente in statistiche/banca ore finche' non c'e' un sostituto. Il marcatore
sta in 'note' (colonna gia' sincronizzata da auto_sync) e non in una colonna
nuova, per non rompere il merge tra postazioni.
"""
from datetime import date, timedelta

from models import db
from models.posto_vacante import (
    AliasPostoVacante, OrarioPlaceholder, PREFISSO_NOTE_SUPPLENZA)
from models.supplenza import Supplenza

ORIZZONTE_GIORNI = 28  # solo se l'orario non ha una validita' con data finale
_NON_CLASSI = ('---', '-x-', '', 'POTENZIAMENTO')


def classe_reale(c):
    return bool(c) and c not in _NON_CLASSI and c[0].isdigit()


def alias_map():
    return {a.nome_file.upper(): a for a in AliasPostoVacante.query.all()}


def salva_slot_posti(slots_non_risolti, v_ini=None, v_fine=None):
    """slots_non_risolti: dict-slot del parser di nomi senza docente.
    Ricrea l'intera tabella (come OrarioDocente a ogni import)."""
    OrarioPlaceholder.query.delete()
    seen = set()
    n = 0
    for s in slots_non_risolti:
        nome = s['cognome_file'].upper().strip()
        key = (nome, s['giorno'], s['ora'],
               'comp' if s['tipo_ora'] == 'compresenza' else 'norm')
        if key in seen:
            continue
        seen.add(key)
        db.session.add(OrarioPlaceholder(
            nome_file=nome, giorno=s['giorno'], ora=s['ora'],
            classe=s['classe'], materia=s['materia'], tipo_ora=s['tipo_ora'],
            data_inizio_validita=v_ini, data_fine_validita=v_fine))
        n += 1
    return n


def posti_collegati():
    """{chiave_posto: {'nome', 'alias': [AliasPostoVacante], 'slots': [...]}}
    solo per alias non ignorati."""
    posti = {}
    for a in AliasPostoVacante.query.filter_by(ignora=False).order_by(
            AliasPostoVacante.nome_file).all():
        p = posti.setdefault(a.chiave_posto, {
            'chiave': a.chiave_posto, 'nome': a.nome_posto,
            'id_assegnazione': a.id_assegnazione, 'alias': [], 'slots': []})
        p['alias'].append(a)
    for p in posti.values():
        nomi = [a.nome_file.upper() for a in p['alias']]
        p['slots'] = OrarioPlaceholder.query.filter(
            OrarioPlaceholder.nome_file.in_(nomi)).all()
    return posti


def nomi_in_attesa():
    """Nomi presenti nell'ultimo orario senza docente e senza collegamento:
    [(nome_file, n_slot, [classi])]."""
    noti = {a.nome_file.upper() for a in AliasPostoVacante.query.all()}
    per_nome = {}
    for r in OrarioPlaceholder.query.all():
        if r.nome_file in noti:
            continue
        d = per_nome.setdefault(r.nome_file, {'n': 0, 'classi': set()})
        d['n'] += 1
        if classe_reale(r.classe):
            d['classi'].add(r.classe)
    return [(n, d['n'], sorted(d['classi'])) for n, d in sorted(per_nome.items())]


def _festivo_o_sospeso(d):
    from modules.assenze_registrazione import is_sospensione, GIORNI_SETTIMANA
    return GIORNI_SETTIMANA.get(d.weekday()) is None or bool(is_sospensione(d))


def _classe_fuori_aula(d, classe, ora):
    from models.attivita_fuori_aula import AttivitaFuoriAula
    for att in AttivitaFuoriAula.query.filter(
            AttivitaFuoriAula.data_inizio <= d,
            AttivitaFuoriAula.data_fine >= d,
            AttivitaFuoriAula.stato == 'attiva').all():
        if classe not in att.classi_list:
            continue
        if att.ricorrenza == 'settimanale' and d.weekday() not in att.giorni_sett_list:
            continue
        if att.ora_inizio and att.ora_fine and not (att.ora_inizio <= ora <= att.ora_fine):
            continue
        return True
    return False


def _elimina_supplenza(s):
    from models.movimento_banca_ore import MovimentoBancaOre
    from modules.auto_sync import registra_eliminazione
    MovimentoBancaOre.query.filter_by(id_supplenza=s.id).delete()
    registra_eliminazione('supplenze', {
        'data': s.data.isoformat(), 'ora': s.ora, 'classe': s.classe,
        'id_assente': s.id_assente})
    db.session.delete(s)


def elimina_supplenze_posto_scoperte(data, ora, classe):
    """Toglie la supplenza di un posto vacante su (data, ora, classe) se e'
    ancora scoperta; una gia' assegnata a un sostituto non si tocca."""
    for s in Supplenza.query.filter(
            Supplenza.data == data, Supplenza.ora == ora, Supplenza.classe == classe,
            Supplenza.id_assente.is_(None), Supplenza.stato == 'scoperta',
            Supplenza.note.like(PREFISSO_NOTE_SUPPLENZA + '%')).all():
        _elimina_supplenza(s)


def _supplenze_posti(da):
    return [s for s in Supplenza.query.filter(
        Supplenza.id_assente.is_(None), Supplenza.data >= da,
        Supplenza.note.like(PREFISSO_NOTE_SUPPLENZA + '%')).all()]


def ricalcola_supplenze_posti(oggi=None):
    """Allinea le supplenze dei posti vacanti all'orario. Ritorna
    {'create': n, 'cancellate': n}. Commit incluso."""
    from modules.compresenze import ha_compagno_presente, invalida_cache
    invalida_cache()
    oggi = oggi or date.today()
    posti = posti_collegati()

    attese = {}  # (data, ora, classe) -> (chiave, nome, materia)
    for p in posti.values():
        for r in p['slots']:
            if r.tipo_ora != 'lezione' or not classe_reale(r.classe):
                continue
            ini = max(oggi, r.data_inizio_validita) if r.data_inizio_validita else oggi
            fine = r.data_fine_validita or (oggi + timedelta(days=ORIZZONTE_GIORNI))
            d = ini
            while d <= fine:
                # Compagno presente nella stessa classe/ora (titolare, ITP o
                # sostegno): la classe e' gia' coperta, niente supplenza.
                # Id 0 = "nessun docente" (non e' mai un docente reale).
                if d.weekday() == r.giorno and not _festivo_o_sospeso(d) \
                        and not _classe_fuori_aula(d, r.classe, r.ora) \
                        and not ha_compagno_presente(0, r.giorno, r.ora, r.classe, d):
                    attese.setdefault((d, r.ora, r.classe),
                                      (p['chiave'], p['nome'], r.materia))
                d += timedelta(days=1)

    cancellate = create = 0
    esistenti = {}
    for s in _supplenze_posti(oggi):
        k = (s.data, s.ora, s.classe)
        chiave = s.note[len(PREFISSO_NOTE_SUPPLENZA):].split('|')[0]
        if k in attese and attese[k][0] == chiave:
            esistenti[k] = s
        else:
            _elimina_supplenza(s)
            cancellate += 1

    for (d, ora, classe), (chiave, nome, materia) in sorted(attese.items()):
        if (d, ora, classe) in esistenti:
            continue
        if Supplenza.query.filter_by(data=d, ora=ora, classe=classe).filter(
                Supplenza.stato != 'annullata').first():
            continue  # classe gia' con una supplenza (es. titolare assente)
        db.session.add(Supplenza(
            data=d, ora=ora, classe=classe, id_assente=None, id_sostituto=None,
            tipo='recupero', stato='scoperta', origine='automatica',
            note_display=f'Posto vacante: {nome}',
            note=f'{PREFISSO_NOTE_SUPPLENZA}{chiave}|{materia or ""}',
            creato_da='sistema'))
        create += 1
    db.session.commit()
    return {'create': create, 'cancellate': cancellate}


def collega_nome(nome_file, scelta):
    """scelta: 'ignora' | 'nuovo' | 'asg:<id>'. Crea/aggiorna l'alias."""
    nome = nome_file.upper().strip()
    a = AliasPostoVacante.query.filter_by(nome_file=nome).first()
    if a is None:
        a = AliasPostoVacante(nome_file=nome)
        db.session.add(a)
    a.ignora = scelta == 'ignora'
    a.id_assegnazione = None
    if scelta.startswith('asg:'):
        a.id_assegnazione = int(scelta[4:])
    db.session.commit()
    return a


def nomina_posto(chiave, id_docente, oggi=None):
    """Il docente nominato prende le ore del posto; le supplenze da oggi in
    poi di quel posto si cancellano (qualunque stato: e' in servizio).
    Ritorna {'ore': n, 'supplenze_cancellate': n}."""
    from models.orario_docente import OrarioDocente
    oggi = oggi or date.today()
    p = posti_collegati().get(chiave)
    if not p:
        return {'ore': 0, 'supplenze_cancellate': 0}

    gia = {(r.giorno, r.ora) for r in OrarioDocente.query.filter_by(id_docente=id_docente).all()}
    ore = 0
    for r in p['slots']:
        if (r.giorno, r.ora) not in gia and r.tipo_ora != 'altro':
            db.session.add(OrarioDocente(
                id_docente=id_docente, giorno=r.giorno, ora=r.ora, classe=r.classe,
                materia=r.materia, tipo_ora=r.tipo_ora,
                data_inizio_validita=r.data_inizio_validita,
                data_fine_validita=r.data_fine_validita))
            gia.add((r.giorno, r.ora))
            ore += 1
        db.session.delete(r)

    canc = 0
    for s in _supplenze_posti(oggi):
        if s.note[len(PREFISSO_NOTE_SUPPLENZA):].split('|')[0] == chiave:
            _elimina_supplenza(s)
            canc += 1
    for a in p['alias']:
        db.session.delete(a)
    db.session.commit()
    return {'ore': ore, 'supplenze_cancellate': canc}
