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
   punto 4). Vale anche per i placeholder (supplenti non ancora
   nominati, vedi docenti_e_placeholder_per_classe): due classi coperte
   dallo STESSO placeholder non possono sovrapporsi, perché sarà
   comunque una sola persona a doverle seguire entrambe — segnalato da
   Roberto.
2. Gli insiemi docenti per classe vengono dalle Assegnazioni
   (AssegnazioneClasse/AssegnazioneDocente), non dall'orario — si
   stabilizzano molto prima nell'anno.
3. Vincoli orario fissi (VincoloOrarioClasse, es. rientro pomeridiano)
   escludono a priori certi slot per un indirizzo/anno di corso.
4. A parità di condizioni, preferisce accorpare classi dello stesso
   indirizzo nello stesso slot — mai a scapito della regola 1. Anche
   l'ORDINE con cui le classi vengono processate (che diventa l'ordine
   cronologico finale quando, come per gli scrutini con DS sempre
   richiesto, ogni slot può contenere una sola classe) raggruppa prima
   per indirizzo e poi per anno di corso — priorità esplicita di
   Roberto: stessa giornata, stesso indirizzo, anni in ordine
   crescente.
5. Vincoli manuali (VincoloGeneratoreCdc) impostabili PRIMA di
   generare: scadenza ("entro il 20") o slot fisso (data+ora esatte).
6. Presenza del Dirigente Scolastico (classi_richiedono_ds) come
   vincolo forte: due classi che la richiedono non possono mai stare
   nello stesso slot, indipendentemente dai docenti condivisi.
"""
import re
from datetime import date, timedelta

_RE_CLASSE = re.compile(r'(\d+)([AB]?)\s+(.+)')

# Ordine "canonico" degli indirizzi, stesso usato altrove nell'app
# (es. routes/assegnazioni.py) per presentazioni/ordinamenti coerenti.
# Come lista (non solo dict) perché genera_bozza_cdc la ruota per far
# partire un turno da un indirizzo diverso su richiesta di Roberto —
# SOS resta sempre fuori dalla rotazione, ultimo per definizione.
_IND_SEQUENCE = ['AFM', 'RIM', 'CAT', 'LLI', 'LSC', 'LSP', 'LSU']
_IND_ORDER = {ind: i for i, ind in enumerate(_IND_SEQUENCE)}
_IND_ORDER['SOS'] = len(_IND_SEQUENCE)


def _ordine_indirizzi_ruotato(indirizzo_iniziale):
    """{indirizzo: posizione} con la sequenza canonica ruotata per far
    partire indirizzo_iniziale — se non è uno dei 7 indirizzi principali
    (None, valore vuoto/sbagliato, o SOS), ritorna l'ordine invariato."""
    if indirizzo_iniziale not in _IND_SEQUENCE:
        return _IND_ORDER
    i = _IND_SEQUENCE.index(indirizzo_iniziale)
    ruotato = _IND_SEQUENCE[i:] + _IND_SEQUENCE[:i]
    ordine = {ind: pos for pos, ind in enumerate(ruotato)}
    ordine['SOS'] = len(_IND_SEQUENCE)
    return ordine


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
    insieme di ore-condivise noto finché non vengono nominati.

    Esclude il potenziamento (indirizzo fittizio 'POT', anno_corso=0,
    sezione='A' — vedi routes/assegnazioni.py): è un contenitore di
    bookkeeping per le ore di potenziamento, non una classe reale con
    studenti — comparire come "0A POT" nell'elenco selezionabile del
    Generatore Consigli di classe non ha senso, non esiste nessun
    Consiglio di classe da tenere per una classe che non esiste
    (segnalato da Roberto)."""
    from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse

    righe = (AssegnazioneClasse.query
             .join(AssegnazioneDocente,
                   AssegnazioneDocente.id == AssegnazioneClasse.id_assegnazione)
             .filter(AssegnazioneDocente.anno_scol == anno_scol,
                     AssegnazioneDocente.id_docente.isnot(None),
                     AssegnazioneClasse.indirizzo != 'POT')
             .all())
    out = {}
    for ac in righe:
        out.setdefault(ac.label_classe, set()).add(ac.assegnazione.id_docente)
    return out


def docenti_e_placeholder_per_classe(anno_scol):
    """
    Come docenti_reali_per_classe(), ma include anche i placeholder
    (supplenti non ancora nominati): un placeholder con ore su una
    classe rappresenta comunque un impegno reale — qualcuno, chiunque
    sia, dovrà seguire quella classe — quindi due classi coperte dallo
    STESSO placeholder non possono avere Consiglio di classe/scrutinio
    sovrapposti, esattamente come per un docente reale (segnalato da
    Roberto: "se il placeholder ha classi assegnate, di fatto è un
    docente che è in quella classe").

    Ogni riga AssegnazioneDocente placeholder (id_docente NULL) diventa
    una chiave sintetica 'ph-<id_assegnazione>' — stessa riga = stesso
    futuro supplente = stesso vincolo di non-sovrapposizione tra le
    classi che copre; placeholder DIVERSI restano invece indipendenti
    tra loro (non c'è modo di sapere se diventeranno la stessa persona,
    quindi nessun conflitto presunto).

    Usata SOLO per il calcolo delle sovrapposizioni nel generatore
    (genera_bozza_cdc) e per l'elenco classi selezionabili — MAI per
    creare un AttivitaIstPartecipante reale: un placeholder non è un
    id_docente valido (nessuna riga corrispondente in Docente), quindi
    non deve mai finire scritto come partecipante. Per quello resta
    docenti_reali_per_classe(), usata da routes/generatore_cdc.py in
    fase di conferma.
    """
    from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse

    righe = (AssegnazioneClasse.query
             .join(AssegnazioneDocente,
                   AssegnazioneDocente.id == AssegnazioneClasse.id_assegnazione)
             .filter(AssegnazioneDocente.anno_scol == anno_scol,
                     AssegnazioneClasse.indirizzo != 'POT')
             .all())
    out = {}
    for ac in righe:
        asgn = ac.assegnazione
        chiave = asgn.id_docente if asgn.id_docente is not None else f'ph-{asgn.id}'
        out.setdefault(ac.label_classe, set()).add(chiave)
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
                      classi_richiedono_ds=None,
                      indirizzo_iniziale=None, ordine_anno='crescente'):
    """
    Calcola una proposta di calendarizzazione per le classi indicate,
    senza scrivere nulla sul DB.

    indirizzo_iniziale/ordine_anno: rotazione di chi "apre" il turno —
    richiesta esplicita di Roberto per distribuire nel tempo l'onere di
    essere sempre i primi (es. scrutini del I periodo che partono dalla
    1ª di un indirizzo, quelli del II periodo che partono invece dalla
    5ª dello stesso, o turni di CdC successivi che cambiano l'indirizzo
    di apertura). Riguardano solo l'ORDINE in cui le classi vengono
    processate (vedi commento sopra "ordine di assegnazione" più sotto)
    — nessun impatto sulle regole 1/2/3/5/6 (docenti condivisi, vincoli
    orario, DS...), che restano identiche. indirizzo_iniziale=None (o
    un valore non riconosciuto) mantiene l'ordine canonico consueto;
    ordine_anno='decrescente' inverte solo il criterio anno di corso.
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
    docenti_map = docenti_e_placeholder_per_classe(anno_scol)

    def _slot_valido(classe, slot):
        return _slot_libero_per_classe(classe, slot[0], slot[1], durata_min, vincoli_orario)

    def _slot_validi_per_classe(classe):
        vincolo = vincoli_cdc.get(classe)
        base = slots
        if vincolo and vincolo.tipo == 'entro_data' and vincolo.scadenza:
            base = [s for s in slots if s[0] <= vincolo.scadenza]
        return [s for s in base if _slot_valido(classe, s)]

    # Ordine di assegnazione: prima gli slot fissi (già decisi, occupano
    # subito), poi le altre classi raggruppate per indirizzo (in ordine
    # canonico) e, dentro lo stesso indirizzo, per anno di corso —
    # priorità esplicita di Roberto: quando (tipicamente per gli
    # scrutini, con la presenza del DS richiesta per ogni classe — vedi
    # regola 6) ogni slot può contenere una sola classe, l'ORDINE con
    # cui le classi vengono processate È l'ordine finale in cui
    # occupano gli slot in sequenza cronologica (_punteggio più sotto,
    # a parità di livello di riempimento, sceglie sempre lo slot libero
    # più vicino) — prima si processava per "classe più vincolata"
    # (meno slot validi) con fallback alfabetico sull'etichetta, che
    # nella pratica raggruppava per ANNO di corso (il primo carattere
    # dell'etichetta, es. "1A AFM" prima di "2A AFM") invece che per
    # indirizzo, il contrario di quanto Roberto vuole in giornata. Il
    # numero di slot validi resta comunque un criterio di sotto-priorità
    # (classe più vincolata prima, così un vincolo orario stretto non
    # finisce senza slot residui), a parità la scadenza più vicina, poi
    # alfabetico per determinismo finale.
    fisse = [c for c in classi
             if vincoli_cdc.get(c) and vincoli_cdc[c].tipo == 'fissa'
             and vincoli_cdc[c].data_fissa and vincoli_cdc[c].ora_fissa]
    altre = [c for c in classi if c not in fisse]
    ordine_indirizzi = _ordine_indirizzi_ruotato(indirizzo_iniziale)
    segno_anno = -1 if ordine_anno == 'decrescente' else 1
    altre.sort(key=lambda c: (
        ordine_indirizzi.get(_parse_classe(c)[1], 99),
        segno_anno * (_parse_classe(c)[0] or 0),
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
