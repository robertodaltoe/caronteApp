"""
Generatore Consigli di Classe — Piano Annuale delle Attività, Fase 3.

Principio guida (Fase 4 del project plan, coerente con
genera_bozza_agosto già in app): genera una bozza modificabile, mai un
piano imposto. Questo modulo calcola solo la proposta — la scrittura
degli AttivitaIst reali resta alla route chiamante, dopo eventuale
correzione manuale.

Regole implementate (decise con Roberto durante l'analisi):
1. Due classi possono stare nello stesso slot se e solo se non
   condividono docenti reali — nessun vincolo di "stesso anno" o
   "stesso indirizzo" (quello resta solo una preferenza secondaria,
   punto 4).
2. Gli insiemi docenti per classe vengono dalle Assegnazioni
   (AssegnazioneClasse/AssegnazioneDocente), non dall'orario — si
   stabilizzano molto prima nell'anno.
3. Vincoli orario fissi (VincoloOrarioClasse, es. rientro pomeridiano)
   escludono a priori certi slot per un indirizzo/anno di corso.
4. A parità di condizioni, preferisce accorpare classi dello stesso
   indirizzo nello stesso slot — mai a scapito della regola 1.
5. Vincoli manuali (VincoloGeneratoreCdc) impostabili PRIMA di
   generare: scadenza ("entro il 20") o slot fisso (data+ora esatte).
6. Presenza del Dirigente Scolastico (classi_richiedono_ds) come
   vincolo forte: due classi che la richiedono non possono mai stare
   nello stesso slot, indipendentemente dai docenti condivisi.
"""
import re
from datetime import date, timedelta

_RE_CLASSE = re.compile(r'(\d+)([AB]?)\s+(.+)')


def _parse_classe(label):
    """'3A LLI' -> (3, 'LLI'). None se il formato non è riconosciuto
    (es. potenziamento, classi speciali) — quella classe non ha vincoli
    orario applicabili, solo il controllo sui docenti condivisi."""
    m = _RE_CLASSE.match(label or '')
    if not m:
        return None, None
    return int(m.group(1)), m.group(3).strip()


def docenti_reali_per_classe(anno_scol):
    """{classe_label: set(id_docente)} dalle Assegnazioni — solo
    docenti reali (id_docente valorizzato), i placeholder non hanno un
    insieme di ore-condivise noto finché non vengono nominati."""
    from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse

    righe = (AssegnazioneClasse.query
             .join(AssegnazioneDocente,
                   AssegnazioneDocente.id == AssegnazioneClasse.id_assegnazione)
             .filter(AssegnazioneDocente.anno_scol == anno_scol,
                     AssegnazioneDocente.id_docente.isnot(None))
             .all())
    out = {}
    for ac in righe:
        out.setdefault(ac.label_classe, set()).add(ac.assegnazione.id_docente)
    return out


def docenti_per_dipartimento(anno_scol):
    """{id_dipartimento: set(id_docente)} da DocenteMateria — usata solo
    per popolare i partecipanti delle riunioni di dipartimento/materia,
    NON per uno scheduling con controllo sovrapposizioni: dipartimenti
    diversi non condividono mai docenti per definizione (un docente
    appartiene a un dipartimento tramite le sue materie), quindi non
    serve — a differenza dei Consigli di classe — nessun motore che
    eviti conflitti. Le riunioni di dipartimento vanno solo piazzate in
    data (routes/generatore_cdc.py::dipartimenti), senza generare nulla."""
    from models.materia import DocenteMateria, Materia

    righe = (DocenteMateria.query
             .join(Materia, Materia.id == DocenteMateria.id_materia)
             .filter(DocenteMateria.anno_scol == anno_scol)
             .all())
    out = {}
    for dm in righe:
        out.setdefault(dm.materia.id_dipartimento, set()).add(dm.id_docente)
    return out


def referenti_per_dipartimento(anno_scol):
    """{id_dipartimento: set(id_docente)} dei soli docenti nominati
    'Referente di dipartimento' (IncaricaDocente) per l'anno indicato —
    a differenza della riunione di dipartimento/materia (tutti i
    docenti del dipartimento), la riunione dei referenti è riservata a
    chi ha l'incarico di capodipartimento: conta diversamente nel
    computo ore proprio per questo, va tenuta distinta e non confusa
    con 'dipartimento'/'riunione_materia' (segnalato da Roberto)."""
    from models.incarico import IncaricaDocente, TipoIncarico

    tipo_ref = TipoIncarico.query.filter_by(nome='Referente di dipartimento').first()
    if not tipo_ref:
        return {}
    nomine = IncaricaDocente.query.filter_by(
        anno_scol=anno_scol, id_tipo_incarico=tipo_ref.id).all()
    out = {}
    for n in nomine:
        if n.id_dipartimento:
            out.setdefault(n.id_dipartimento, set()).add(n.id_docente)
    return out


def coordinatori_di_classe(anno_scol):
    """set(id_docente) dei coordinatori di classe (IncaricaDocente) per
    l'anno indicato — un docente per classe, usato per l'opzione
    'solo i coordinatori' degli incontri scuola-famiglia."""
    from models.incarico import IncaricaDocente, TipoIncarico

    tipo_coord = TipoIncarico.query.filter_by(nome='Coordinatore di classe').first()
    if not tipo_coord:
        return set()
    nomine = IncaricaDocente.query.filter_by(
        anno_scol=anno_scol, id_tipo_incarico=tipo_coord.id).all()
    return {n.id_docente for n in nomine}


def _to_min(hhmm):
    h, m = map(int, hhmm.split(':'))
    return h * 60 + m


def _to_hhmm(minuti):
    return f'{minuti // 60:02d}:{minuti % 60:02d}'


def giorni_lavorativi(data_inizio, data_fine):
    """Giorni feriali (lun-sab) nel periodo, esclusi quelli coperti da
    una SospensioneDidattica — non genera nulla nei giorni di sospensione
    delle lezioni."""
    from models.sospensione import SospensioneDidattica

    sospesi = set()
    for s in SospensioneDidattica.query.filter(
            SospensioneDidattica.data_fine >= data_inizio,
            SospensioneDidattica.data_inizio <= data_fine).all():
        cur = max(s.data_inizio, data_inizio)
        fine = min(s.data_fine, data_fine)
        while cur <= fine:
            sospesi.add(cur)
            cur += timedelta(days=1)

    giorni = []
    cur = data_inizio
    while cur <= data_fine:
        if cur.weekday() < 6 and cur not in sospesi:  # 0=lunedì .. 5=sabato, 6=domenica esclusa
            giorni.append(cur)
        cur += timedelta(days=1)
    return giorni


def _slot_libero_per_classe(classe, giorno, ora_inizio_min, durata_min, vincoli_orario):
    """False se un VincoloOrarioClasse applicabile a questa classe si
    sovrappone allo slot (es. rientro pomeridiano del suo indirizzo)."""
    anno_corso, indirizzo = _parse_classe(classe)
    if indirizzo is None:
        return True
    giorno_sett = giorno.weekday()
    ora_fine_min = ora_inizio_min + durata_min
    for v in vincoli_orario:
        if v.giorno_settimana != giorno_sett:
            continue
        if not v.si_applica_a(indirizzo, anno_corso):
            continue
        v_ini, v_fin = _to_min(v.ora_inizio), _to_min(v.ora_fine)
        if ora_inizio_min < v_fin and ora_fine_min > v_ini:
            return False
    return True


def genera_bozza_cdc(anno_scol, classi, data_inizio, data_fine,
                      ora_inizio_giorno, ora_fine_giorno, durata_min=60,
                      classi_richiedono_ds=None):
    """
    Calcola una proposta di calendarizzazione per le classi indicate,
    senza scrivere nulla sul DB.

    Ritorna una lista di dict, uno per classe:
    {classe, data, ora_inizio, ora_fine, conflitto, motivo}
    — se conflitto=True, data/ora_inizio/ora_fine sono None e va
    piazzata a mano (nessuno slot valido trovato nel periodo).
    """
    from models.generatore_cdc import VincoloOrarioClasse, VincoloGeneratoreCdc

    classi_richiedono_ds = set(classi_richiedono_ds or ())
    giorni = giorni_lavorativi(data_inizio, data_fine)
    ini_min, fin_min = _to_min(ora_inizio_giorno), _to_min(ora_fine_giorno)

    slots = []
    for g in giorni:
        t = ini_min
        while t + durata_min <= fin_min:
            slots.append((g, t))
            t += durata_min

    vincoli_orario = VincoloOrarioClasse.query.all()
    vincoli_cdc = {v.classe: v for v in
                   VincoloGeneratoreCdc.query.filter_by(anno_scol=anno_scol)
                   .filter(VincoloGeneratoreCdc.classe.in_(classi)).all()}
    docenti_map = docenti_reali_per_classe(anno_scol)

    def _slot_valido(classe, slot):
        return _slot_libero_per_classe(classe, slot[0], slot[1], durata_min, vincoli_orario)

    def _slot_validi_per_classe(classe):
        vincolo = vincoli_cdc.get(classe)
        base = slots
        if vincolo and vincolo.tipo == 'entro_data' and vincolo.scadenza:
            base = [s for s in slots if s[0] <= vincolo.scadenza]
        return [s for s in base if _slot_valido(classe, s)]

    # Ordine di assegnazione: prima gli slot fissi (già decisi, occupano
    # subito), poi le classi più vincolate (meno slot validi possibili)
    # — euristica CSP standard, riduce il rischio di conflitti tardivi —
    # a parità la scadenza più vicina, poi alfabetico per determinismo.
    fisse = [c for c in classi
             if vincoli_cdc.get(c) and vincoli_cdc[c].tipo == 'fissa'
             and vincoli_cdc[c].data_fissa and vincoli_cdc[c].ora_fissa]
    altre = [c for c in classi if c not in fisse]
    altre.sort(key=lambda c: (
        len(_slot_validi_per_classe(c)),
        vincoli_cdc[c].scadenza if vincoli_cdc.get(c) and vincoli_cdc[c].scadenza else date.max,
        c,
    ))
    ordine = fisse + altre

    assegnazioni = {}   # slot -> [{'classe', 'docenti', 'indirizzo'}]
    ds_occupati = set()
    risultato = []

    for classe in ordine:
        docenti_c = docenti_map.get(classe, set())
        _, indirizzo = _parse_classe(classe)
        richiede_ds_c = classe in classi_richiedono_ds
        vincolo = vincoli_cdc.get(classe)

        def _conflitto(slot):
            if not _slot_valido(classe, slot):
                return True
            for altra in assegnazioni.get(slot, []):
                if docenti_c & altra['docenti']:
                    return True
            if richiede_ds_c and slot in ds_occupati:
                return True
            return False

        slot = None
        if classe in fisse:
            candidato = (vincolo.data_fissa, _to_min(vincolo.ora_fissa))
            if candidato[0] < data_inizio or candidato[0] > data_fine or _conflitto(candidato):
                risultato.append(dict(
                    classe=classe, data=None, ora_inizio=None, ora_fine=None,
                    conflitto=True,
                    motivo='Slot fisso richiesto non disponibile (fuori periodo o in conflitto)'))
                continue
            slot = candidato
        else:
            candidati = [s for s in _slot_validi_per_classe(classe) if not _conflitto(s)]
            if not candidati:
                risultato.append(dict(
                    classe=classe, data=None, ora_inizio=None, ora_fine=None,
                    conflitto=True,
                    motivo='Nessuno slot libero nel periodo senza sovrapposizioni'))
                continue

            def _punteggio(s):
                # Preferisce impacchettare classi compatibili nello
                # stesso slot (massima classi-in-parallelo per fascia,
                # l'obiettivo primario) — tra slot già occupati,
                # preferisce quelli con classi dello stesso indirizzo
                # (preferenza secondaria di Roberto). Uno slot vuoto è
                # l'ultima scelta, apre solo capacità se serve.
                occupanti = assegnazioni.get(s, [])
                if not occupanti:
                    livello = 2
                elif any(o['indirizzo'] == indirizzo for o in occupanti):
                    livello = 0
                else:
                    livello = 1
                return (livello, s[0], s[1])

            candidati.sort(key=_punteggio)
            slot = candidati[0]

        assegnazioni.setdefault(slot, []).append(
            dict(classe=classe, docenti=docenti_c, indirizzo=indirizzo))
        if richiede_ds_c:
            ds_occupati.add(slot)
        risultato.append(dict(
            classe=classe, data=slot[0], ora_inizio=_to_hhmm(slot[1]),
            ora_fine=_to_hhmm(slot[1] + durata_min), conflitto=False, motivo=None))

    risultato.sort(key=lambda r: (
        r['data'] if r['data'] else date.max,
        r['ora_inizio'] if r['ora_inizio'] else '99:99',
        r['classe']))
    return risultato
