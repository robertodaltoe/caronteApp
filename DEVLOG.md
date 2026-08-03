# CaronteApp — Diario di sviluppo

> File di log persistente delle sessioni di sviluppo con Claude.
> Va aggiornato alla fine di ogni sessione, aggiungendo una nuova voce
> in cima (ordine cronologico inverso). Non cancellare le voci precedenti.

---

## Sessione 31 — Modulo Esami Integrativi (item 19)

**Contesto:** l'hub "Attività Differite" aveva una terza scheda "Esami
integrativi" (passaggi e trasferimenti di settembre) ferma da tempo come
placeholder disattivato, senza alcun codice dietro. Su richiesta
esplicita, costruito da zero il modulo completo.

### Struttura scelta (chiarita con l'utente prima di implementare)
A differenza di Rientro dall'estero (4 materie uguali per tutta la
classe), qui ogni candidato ha un proprio elenco di materie da
sostenere — chi si trasferisce da un altro indirizzo può avere 2-3
materie diverse dagli altri. Scelto quindi un modello "per candidato →
per materia", con commissione (2 docenti) e calendario indipendenti per
ciascuna materia. Solo organizzazione: l'esito resta verbalizzato a mano
su registro cartaceo, come per Rientro.

### Implementazione
- `models/esami_integrativi.py`: `EsameIntegrativoCandidato` (cognome,
  nome, classe di destinazione, provenienza, note) e
  `EsameIntegrativoMateria` (materia, data/ora, 2 docenti esaminatori),
  con relazione 1→N e cascade delete.
- `routes/esami_integrativi.py`: hub, gestione candidati+materie inline,
  pagina commissione/calendario con proposta automatica dei docenti
  idonei per materia (stesso matching per famiglie di sinonimi già usato
  in Rientro), rilevamento conflitti di sovrapposizione commissione, ed
  export XLSX per giornata (stesso impianto grafico di Rientro/Recuperi).
- Blueprint registrato in `app.py`, permesso `recupero_r` in
  `BLUEPRINT_PERMESSI`.
- Terza scheda dell'hub `att_differite/index.html` riattivata (era un
  `<div>` disattivato, ora un link funzionante).

### Verifica
`db.create_all()` per le due nuove tabelle (nessuna tabella esistente
toccata), pytest 51/51, test funzionale end-to-end (candidato → materia
→ commissione → calendario → export XLSX, tutti 200).

**Nota su un errore commesso e corretto in sessione:** il test
funzionale iniziale ha inavvertitamente scritto un candidato di prova
sul `database.db` reale (create_app() punta lì di default, non a un DB
di test, se non passato esplicitamente). Individuato subito dopo la
verifica, il candidato e la relativa materia sono stati rimossi via
SQL diretto e l'integrità del database confermata (`PRAGMA
integrity_check` → ok). Nessun altro dato è stato toccato.

### Task 19bis — Tipologia prova + autofill classe di destinazione
Su richiesta, aggiunte due migliorie al modulo appena creato:
- Nuovo campo `tipologia` (scritta/orale) su `EsameIntegrativoMateria`,
  impostabile alla creazione della materia e modificabile in seguito
  (select inline sia nella scheda candidato che, come sola visualizzazione
  a badge colorato, nel calendario); incluso anche nell'export XLSX.
- Campo "classe di destinazione" nel form candidato reso autofill con
  `<datalist>` alimentato da `classi_attive()`, stesso pattern già
  esteso a tutti gli altri form dell'app (Task 5, Sessione 30).
- Migrazione additiva `esami_integrativi_materie.tipologia` aggiunta a
  `MIGRATIONS` in `app.py` e applicata al DB reale (colonna nullable,
  nessun dato esistente toccato — a differenza della sessione
  precedente, questa volta la verifica funzionale è stata fatta su una
  copia temporanea del database, non su quello reale).

### Task 19ter — Fix crash _migra_vincolo_aule() su schema molto vecchio
Su un altro Mac ("ministudio"), il download del DB da Drive ha riportato
una tabella `aule` priva della colonna `anno_scol` — schema più vecchio
di quanto previsto — mandando in crash `_migra_vincolo_aule()` con
`no such column: anno_scol` durante l'INSERT della migrazione del
vincolo. Nessun dato perso (l'eccezione ha interrotto la funzione prima
del DROP TABLE, quindi SQLite ha annullato tutto in automatico), ma
l'app non partiva.

Corretto `_migra_vincolo_aule()` in `app.py`: ora verifica prima se la
colonna `anno_scol` esiste su `aule` e, se manca, la aggiunge (con
l'anno scolastico corrente come valore di partenza per le righe
esistenti) prima di procedere con la correzione del vincolo UNIQUE.
Verificato ricreando lo schema vecchio su una copia di prova: nessun
crash, colonna aggiunta, tutte le righe preservate. Pytest 51/51, DB
reale verificato intatto (invariato, dato che lì la colonna era già
presente).

**Nota per la prossima sessione:** il traceback di ministudio mostrava
il crash a un numero di riga diverso da quello attuale in `app.py` —
quel Mac gira su una copia del codice non aggiornata. Il fix va
distribuito anche lì (non solo il database) prima del prossimo avvio.

---

## Sessione 30 — Restyling grafico brand, pulizia emoji, orario sostegno a griglia, fix warning potenziamento

**Contesto:** sessione su quattro fronti distinti, richiesti in sequenza.

### Task 1 — Restyling grafico generale (identità di brand)
Palette bordeaux/crema estratta dal logo ufficiale (`#a5241f`/`#f6f5f1`),
font Open Sans confermato ovunque (scartata una prova con serif, non
gradita). Aggiunto watermark "uomo vitruviano tech" a schermo intero
(trasparenza ricostruita via luminanza, poi ricolorato in bordeaux perché
le linee chiare erano invisibili su sfondo chiaro). Navbar ingrandita
(68px) per ospitare l'icona Caronte quadrata (era ritagliata), icone
sostituite con glifi tipografici eleganti + Variation Selector U+FE0E per
garantire resa monocromatica. Favicon aggiunta. Pagina `display.html`
(cruscotto TV) riallineata alla nuova palette bordeaux (prima era ancora
blu navy).

### Task 2 — Rimozione emoji sito-wide, poi ripristino mirato
Sweep completo su 91 file (glifi + VS15 al posto di ~100 emoji diverse,
incluse sequenze ZWJ). Su richiesta esplicita, ripristinate le emoji
colorate originali solo in tre punti: `/assenze/nuova`,
`/indisponibilita/*`, `/attivita/nuova` — il resto del sito resta con i
glifi tipografici.

### Task 10 — Verifica coerenza con le informative privacy pubblicate dalla scuola
Su richiesta, letta (via browser) la pagina privacy dell'istituto
(davincichiavenna.edu.it/privacy) e i documenti collegati: Informativa
al personale, Informativa sull'uso di Google Workspace, Privacy Policy
generale. Confronto con quanto scritto nel report GDPR di CaronteApp —
nessuna modifica al codice, solo verifica documentale. Emerse alcune
incongruenze da chiarire con il DPO prima di aggiornare il report:

- **Base giuridica**: l'informativa al personale dichiara l'art. 6(1)(e)
  GDPR (compito di interesse pubblico) come base per i dati del
  personale, e art. 9(2)(b)/(g) per i dati particolari — il report
  CaronteApp cita invece art. 6(1)(b)/(c) senza richiamare la base
  istituzionale già dichiarata. Da allineare.
- **Trasferimento extra-UE (punto prioritario)**: l'informativa al
  personale dichiara che "i dati [...] sono conservati su server
  ubicati all'interno dell'Unione Europea e non sono quindi oggetto di
  trasferimento" — affermazione generale che la sincronizzazione
  CaronteApp→Google Drive rende vera solo se il tenant Google Workspace
  ha residenza dati garantita in UE, cosa da confermare esplicitamente
  col DPO, non da presumere.
- **Copertura DPA incompleta**: l'unica "Informativa uso Google
  Workspace" pubblicata riguarda esclusivamente l'uso studenti
  (Classroom, compiti), rivolta a genitori/tutori — nessun documento
  pubblico copre l'uso amministrativo di Google Drive per dati del
  personale. Va fatto confermare/estendere dal DPO.
- **Registro dei trattamenti**: il link dalla pagina privacy porta al
  portale Spaggiari, protetto da login — non verificabile dall'esterno;
  da controllare direttamente se CaronteApp vi compare (nome aggiornato
  + sync Drive come voce esplicita).
- Identificato il DPO nominato: Avv. Emanuela Caricati (contatti
  pubblicati sulla pagina) — da aggiungere al report CaronteApp quando
  verrà aggiornato.

Decisione: **non aggiornare ancora il report GDPR** (rimane v2.2) finché
la scuola non ha un riscontro dal DPO sui punti sopra, in particolare
sulla residenza dati del tenant Google Workspace usato per la
sincronizzazione. Da riprendere come Task 11 una volta ottenuta
conferma.

### Task 9 — Audit di minimizzazione dati (principi minimizzazione/scopo/liceità)
Su domanda esplicita ("sono garantiti minimizzazione, scopo preciso,
liceità?"), controllo sistematico via script di tutte le 442 colonne
nei modelli collegati a docenti, verificando per ciascuna se sia
davvero letta/scritta da qualche route/template/modulo. Trovati 5
campi/strutture senza alcuno scopo attivo: tabella `VariazioneOrario`
(0 righe, mai usata), `Assenza.motivo_interno` (mai valorizzato, nessun
campo form lo scrive), `RecuperoGruppo.id_commissario`/`commissario`/
`sigla_materia` (19 valori storici reali, sostituito nei fatti dal solo
"sorvegliante"), `RientroColloquio.id_membro_ds` (7 valori storici,
già commentato "legacy" nel codice), `TipoIncarico.id_categoria`/
`categoria_obj` (16 valori storici, la categoria è gestita altrove come
stringa). Tre di questi contenevano dati reali non ipotetici — prima di
cancellarli: backup cifrato di sicurezza del database
(`data/backup/database_..._preminimize.db.enc`), conferma esplicita
del Titolare sulla cancellazione definitiva. Rimossi da modelli Python,
da `app.py::_auto_migrate()`, e dallo schema del database reale (`DROP
TABLE`/`ALTER TABLE DROP COLUMN`, con ricostruzione tabella per le due
colonne vincolate da foreign key che SQLite non permette di droppare
direttamente). Verificato `PRAGMA integrity_check`, conteggio righe
invariato sulle tabelle non toccate, smoke test sulle pagine coinvolte
(recupero agosto, rientro, incarichi, assenze) e pytest (51/51).
Documentato come nuova sezione 3 del report GDPR (ora v2.2, con
rinumerazione delle sezioni successive) e raccomandazione di ripetere
l'audit periodicamente.

### Task 8 — Pacchetto di conformità GDPR (in risposta alle raccomandazioni del report v2.0)
Implementate le quattro azioni tecniche derivanti dalla revisione del
report GDPR, per rendere l'app difendibile davanti al DPO:

- **Cifratura del canale Google Drive** (il punto più critico):
  `sync_db.py` ora cifra il database prima di caricarlo su Drive e lo
  decifra dopo averlo scaricato, riusando lo stesso meccanismo Fernet
  del backup locale (nuove funzioni generiche `cifra_file`/`decifra_file`
  in `modules/backup_cifrato.py`). File condiviso rinominato
  `database.db.enc`; storico anch'esso cifrato. Migrazione automatica e
  trasparente per chi aveva ancora il vecchio `database.db` in chiaro su
  Drive (lo `scarica` lo riconosce e lo usa una volta, il primo `carica`
  successivo pubblica la versione cifrata e ripulisce quella vecchia).
  Testato l'intero ciclo carica→scarica→migrazione su una cartella Drive
  simulata, verificando byte per byte che il file su Drive non sia mai
  in chiaro e che il roundtrip sia identico all'originale.
- **Avviso sul campo note assenze**: in `assenza_form.html` e
  `modifica_assenza.html`, sotto "Note interne", un avviso visibile
  scoraggia l'inserimento di dettagli clinici; cambiato anche il
  placeholder di esempio (da "certificato medico" a "numero protocollo").
- **Esportazione dati personali per docente** (art. 15 GDPR): nuova
  route `routes/docenti.py::esporta_dati` + template
  `templates/docenti/esporta_dati.html`, genera un PDF con tutti i dati
  collegati al docente (anagrafica, orario lezione/sostegno, assenze,
  supplenze come assente/sostituto, banca ore, indisponibilità,
  assegnazioni cattedre/classi, eccezioni colloqui). Pulsante nella
  lista docenti; ogni esportazione viene loggata. Verificato il
  rendering PDF pagina per pagina.
- **Archiviazione/cancellazione docenti cessati**: verificato che la
  funzionalità richiesta **esisteva già** (`routes/docenti.py::anonimizza`
  per l'art. 17 GDPR + `::elimina`, pulsanti riservati al ruolo DS in
  `templates/docenti.html`) — nessun nuovo codice necessario, corretta
  solo la valutazione nel report che la dava per assente.

Il report GDPR è stato aggiornato a **versione 2.1** lo stesso giorno,
con box verdi "risolto" sui punti corretti e le raccomandazioni residue
(solo organizzative: DPA con Google, policy scritta sulle note,
periodicità dell'anonimizzazione) isolate in una sezione finale.
Verificato con pytest (51/51) dopo ogni singola modifica.

### Task 7 — Verifica file "grigi" residui + revisione Report GDPR
Controllati i 5 file lasciati in sospeso dalla pulizia precedente:
`sync_db.py` e `setup.py` sono attivi e usati da `avvia_caronte.sh/.bat`
(nessuna azione); `scripts/legacy/` è già correttamente archiviato;
`migrate.py` in radice era invece obsoleto (le sue migrazioni sono un
sottoinsieme di quelle in `_auto_migrate()` di `app.py`, l'unica fonte
da tenere aggiornata) — spostato in `scripts/legacy/` con nota nel
README che lo distingue dagli script "una tantum" (è "superato", non
storico).

Il documento GDPR (`SupplenzeApp_GDPR_Report.docx`) è stato invece
integralmente revisionato: rinominato `CaronteApp_GDPR_Report.docx`,
versione 2.0. Novità principali rispetto alla v1.0: sezione dedicata
alla sincronizzazione via Google Drive introdotta a giugno 2026
(`sync_db.py`) — trasferimento dati verso un responsabile del
trattamento terzo, copia NON cifrata a differenza del backup locale,
segnalato come punto di attenzione prioritario per il DPO (verifica
DPA con Google, valutare cifratura pre-sync); tabella ruoli/permessi
aggiornata sui 5 ruoli attuali; nota su dato particolare art. 9
(assenze per "malattia") con raccomandazione sul campo note libere;
conferma rimozione invio email automatico SMTP; sezione conservazione/
cancellazione e sintesi raccomandazioni con priorità. Verificato il
rendering pagina per pagina prima di consegnarlo.

### Task 6 — Pulizia file obsoleti nella cartella del progetto
Scansione della cartella e rimozione, previo consenso esplicito, di:
cache Python (`__pycache__`, `.pytest_cache` — rigenerate automaticamente,
già escluse da git), `database.db.bak` in radice (copia non cifrata
ridondante: esistono già 58 backup cifrati automatici in
`data/backup/`), il vecchio backup manuale `caronteapp_backup_2026-06-02.db`
e un file temporaneo di Sublime Text dentro `info caronteApp/`, gli
script `avvia_supplenze.sh` e `backup_supplenze.sh` (nome/percorso
obsoleto `~/SupplenzeApp`, non più esistente — sostituiti da
`avvia_caronte.sh` e dal backup automatico integrato in `app.py`), e un
file xlsx duplicato in `data/` (contenuto identico, tenuta la copia
usata dallo script di import). Cartella passata da 287M a 59M
(esclusa venv). Verificato con pytest (51/51) che nulla si sia rotto.

### Task 5 — Autocompletamento classi esteso a tutta l'app
Verificati tutti i form con campo "classe" a testo libero (era già
implementato solo in griglia sostegno e in rientro/candidati). Aggiunto
lo stesso autocomplete (`<datalist>` con le classi attive nell'orario
corrente) anche a: nuova supplenza e modifica supplenza
(`supplenza_form.html`, `modifica_supplenza.html`), aggiunta alunno
manuale in recupero (`recupero/alunni.html`), classe di restituzione nei
cambi quadro orario, sia nel form inline nell'elenco che nella pagina di
modifica (`cambi_quadro.html`, `cambio_modifica.html`). Creato un helper
condiviso `models/orario_docente.py::classi_attive()` per non duplicare
la query in ogni route (usato anche dalla griglia sostegno, che prima
la calcolava localmente).

### Task 3bis — Autocompletamento classi nella griglia sostegno
Aggiunto autocomplete nativo (`<datalist>`) su tutte le caselle "classe"
della griglia rapida orario sostegno (e sui form aggiungi/modifica
singolo slot): digitando qualche carattere il browser propone in
cascata le classi effettivamente attive nell'orario corrente (es. "3a"
→ "3A LSC", "3A AFM", ...), riducendo errori di battitura e uniformando
il formato al resto dell'app.

### Task 3 — Inserimento orario sostegno a griglia
Prima si poteva inserire un solo slot orario alla volta per i docenti di
sostegno; aggiunta una "griglia rapida" (giorno × ora) per un docente
selezionato, con un solo salvataggio che aggiunge/modifica/elimina gli
slot in blocco (`routes/orario_sostegno.py::salva_griglia`,
`templates/orario_sostegno/index.html`). Attenzione particolare a non
perdere le note esistenti sugli slot non toccati dalla griglia.

### Task 4 — Fix falso warning ore potenziamento in Assegnazioni
La colonna "POT" (ore di potenziamento) nella sezione Assegnazioni era
funzionante ma segnalava sempre un avviso fasullo "supera le ore
previste" appena inserite delle ore: il controllo confrontava le ore di
potenziamento con il Piano di Studi ufficiale, che non contempla il
potenziamento come materia (quindi "ore previste" = 0 sempre). Risolto
escludendo la pseudo-classe POT dal controllo basato su PianoStudi in
`routes/assegnazioni.py::aggiorna_ore()` — il budget di potenziamento
resta comunque visibile/tracciato tramite la colonna "POT Xh" (da
`CattedraPotenziamento`). Verificato che un vero sforamento su una classe
reale continui a generare il warning correttamente (nessuna regressione).

---

## Sessione 29 — Consolidamento business logic (parte 8, finale): recupero_agosto.py::_genera_bozza_agosto()

**Contesto:** ultima funzione lunga rimasta — `_genera_bozza_agosto()` (295
righe, la più lunga del progetto), l'algoritmo di generazione automatica
del calendario prove di agosto (priorità materia, piazzamento mattino/
pomeriggio per scritto+orale, assegnazione assistente/sorvegliante libero
con carico minimo), più `agosto_calendario()` (le stesse azioni POST viste
per giugno: aggiungi/modifica/elimina prova, azzeramento giorno/tutto,
genera_bozza, completa_bozza — e la costruzione dati GET con calcolo
conflitti docente/alunni).

**Modifica:** creato `modules/recupero_agosto_calendario.py` con
`azione_aggiungi/modifica/elimina/elimina_giorno/elimina_tutto/
genera_bozza/completa_bozza` (ciascuna ritorna `{'msg':..., 'cat':...}`),
`costruisci_dati_agosto()` per il GET, e `genera_bozza_agosto()` spostata
verbatim con tutti i suoi helper interni. `routes/recupero_agosto.py` è
passato da 1092 a 598 righe, ridotto a dispatch table + render.

Poiché `tests/test_recupero_agosto_bozza.py` importa direttamente
`_genera_bozza_agosto` da `routes.recupero_agosto`, aggiunto un re-export
di compatibilità (`from modules.recupero_agosto_calendario import
genera_bozza_agosto as _genera_bozza_agosto`) per non rompere i test
esistenti.

**Verifica:** copia in `/tmp`, pytest 51/51 (6 fallivano prima del
re-export di compatibilità, per `ImportError`). Ricostruita a mano la
versione pre-modifica del file (come nelle sessioni precedenti, `git show
HEAD` non è affidabile). Confrontata byte-per-byte la pagina GET del
calendario agosto sui dati reali (39 gruppi, calcolo conflitti):
identica. Eseguita sulle due copie la stessa sequenza di azioni reali
(aggiungi prova, modifica, completa_bozza sui gruppi ancora incompleti) e
confrontato lo stato finale di `RecuperoLezione` e `RecuperoGruppo.
id_sorvegliante`: nessuna differenza.

Con questa sessione si chiude l'item #18 (consolidamento business logic
fuori dalle route più lunghe) in tutte le sue 8 parti: export_xlsx,
assenze.py (nuova+modifica), report.py::pianifica_permessi,
recupero_giugno.py e recupero_agosto.py.

---

## Sessione 28 — Consolidamento business logic (parte 7): recupero_giugno.py::calendario()

**Contesto:** la funzione più lunga del progetto (465 righe): gestiva sia
le azioni POST del calendario dei corsi di recupero di giugno (aggiungi/
modifica/elimina lezione, azzeramento giorno/tutto, completamento
automatico bozza per i gruppi ancora senza lezioni) sia la costruzione
dati per la vista GET (sincronizzazione alunni aderenti dallo staging
import, calcolo dei conflitti docente/alunni tra lezioni sovrapposte).

**Modifica:** creato `modules/recupero_giugno_calendario.py` con una
funzione per ciascuna azione (`azione_aggiungi`, `azione_modifica`,
`azione_elimina`, `azione_elimina_giorno`, `azione_elimina_tutto`,
`azione_completa_bozza`) che ritorna `{'msg':..., 'cat':...}` invece di
fare flash/redirect direttamente — così restano testabili isolatamente
e la route si limita a un dispatch table + flash + redirect. La
costruzione dati GET è in `costruisci_dati_calendario()`, con gli helper
interni `_sync_alunni_da_staging()` e `_calcola_conflitti()` estratti a
parte per leggibilità. `routes/recupero_giugno.py::calendario()` è
passata da 465 a poche righe (dispatch + chiamata), il file totale da
1616 a 1178 righe.

**Verifica:** copia in `/tmp`, pytest 51/51. Come nelle sessioni
precedenti, `git show HEAD` non è affidabile per questo file (troppe
sessioni non committate nel mezzo): ricostruita a mano la versione
pre-modifica. Confrontata byte-per-byte la pagina GET del calendario sui
dati reali (18 gruppi attivi, sync da staging import, calcolo conflitti):
nessuna differenza. Eseguita sulle due copie la stessa sequenza di azioni
reali (aggiungi lezione, modifica, completa_bozza, elimina_giorno) e
confrontato lo stato finale di `RecuperoLezione`/`RecuperoAlunno`:
nessuna differenza.

---

## Sessione 27 — Consolidamento business logic (parte 6): assenze.py::modifica()

**Contesto:** naturale prosecuzione di Sessione 25 sullo stesso file.
`modifica()` (188 righe) duplicava quasi per intero la logica già
estratta per `nuova()`: pulizia/ricreazione movimenti banca ore e
supplenze automatiche, sync presenze istituzionali, oltre a una
copia leggermente diversa della preparazione dati per il form GET
(stessa struttura di `contesto_form_nuova`, ma con l'esclusione
dell'assenza in modifica dal conteggio utilizzi CCNL).

**Modifica:** in `modules/assenze_registrazione.py`:
- `contesto_form_nuova(data_str)` generalizzata in
  `contesto_form_assenza(data_str, escludi_assenza_id=None)` — usata sia
  da `nuova()` (senza esclusione) sia da `modifica()` (esclude l'assenza
  stessa dal conteggio CCNL, comportamento identico all'originale).
  `contesto_form_nuova` resta come alias per compatibilità.
- Nuova `modifica_assenza(a, form)`: tutta l'orchestrazione della POST di
  modifica (pulizia vecchi movimenti/supplenze, aggiornamento riga,
  ricreazione movimento e supplenze, sync presenze) — non fa commit né
  audit log, lasciati alla route.

`routes/assenze.py::modifica()` è passata da 188 a poche righe. Rimossi
anche gli import ormai inutilizzati (`OrarioDocente`, `ScambioOrario`,
`ScambioSlot`, `AttivitaIst*`, le costanti/funzioni categoria di
`models.assenza`): il file è sceso da 309 a 157 righe.

**Verifica:** copia in `/tmp`, pytest 51/51. Come già in Sessione 26,
`git show HEAD` non è una base affidabile (troppe sessioni non
committate nel mezzo): ricostruita a mano la versione immediatamente
pre-modifica. Creata la stessa riga Assenza di test su entrambe le
copie (stesso id), eseguita la stessa richiesta di modifica (cambio
docente, data, ore, motivo) via HTTP, poi confrontate riga per riga
`Assenza`, `MovimentoBancaOre`, `Supplenza`, `AttivitaIstPresenza`:
nessuna differenza. Confrontato byte-per-byte anche l'HTML della
pagina GET del form di modifica: nessuna differenza.

---

## Sessione 26 — Consolidamento business logic (parte 5): report.py::pianifica_permessi()

**Contesto:** proseguimento item #18, target scelto insieme all'utente tra
4 opzioni. `routes/report.py::pianifica_permessi()` era arrivata a ~190
righe: un piccolo ramo POST (salvataggio configurazione calendario) e un
grosso calcolo GET (saldi banca ore proiettati, date future disponibili,
per ogni docente le opzioni di permesso con le sequenze consecutive a
inizio/fine giornata) tutto dentro la route.

**Modifica:** creato `modules/pianificazione_permessi.py` con
`calcola_pianificazione(anno_corrente)` — tutto il calcolo di sola
lettura, isolato dalla route e quindi testabile a sé — più
`_opzioni_docente(...)` come funzione interna per il calcolo delle
opzioni di un singolo docente. La route ora fa solo: gestione POST
(salvataggio config), chiamata a `calcola_pianificazione()`, render del
template.

**Nota metodologica:** durante la verifica ho scoperto che `git show
HEAD:routes/report.py` non è una base affidabile per il confronto in
questo file — l'HEAD committato precede di diverse sessioni (incluso il
fix #22 sulla data fine anno) il codice realmente in uso, mai
committato. Ricostruita quindi manualmente la versione immediatamente
pre-modifica incollando il corpo funzione originale (catturato prima di
editare) in una copia pulita, invece di fidarmi del diff con HEAD.

**Verifica:** copia in `/tmp`, pytest 51/51. Confronto byte-per-byte
dell'HTML restituito da `/report/pianifica-permessi` tra versione
originale (ricostruita) e nuova, con utente reale (ruolo segreteria):
prima nello stato attuale del database (calendario non ancora
configurato per l'anno 2025-2026 — un ramo distinto del codice),
poi impostando temporaneamente su entrambe le copie una data di fine
lezioni e rigenerando la pagina completa con tutti i docenti e le
opzioni calcolate (23.749 righe di HTML): nessuna differenza in
entrambi i casi.

---

## Sessione 25 — Consolidamento business logic (parte 4): assenze.py::nuova()

**Contesto:** proseguimento item #18, target scelto insieme all'utente tra
4 opzioni proposte. `routes/assenze.py::nuova()` era arrivata a ~320 righe
in un'unica funzione, mescolando: parsing del form (singolo/range/
periodico), creazione delle righe `Assenza`, movimenti banca ore, gestione
scambio orario, generazione supplenze scoperte automatiche, sincronizza-
zione delle presenze istituzionali, log di audit — più tutta la
preparazione dati per la pagina GET (docenti, orari per il JS, utilizzi
CCNL, sospensioni, eventi istituzionali del giorno).

**Modifica:** creato `modules/assenze_registrazione.py`, che ora contiene:
- `registra_assenze_form(form)`: tutta l'orchestrazione della POST (parsing
  date, creazione assenze, movimenti banca ore, generazione supplenze,
  sync presenze) — non fa commit né audit log, lasciati alla route.
- `_gestisci_scambio_orario(form, id_docente, note)`: estratta a parte per
  isolare la logica di scambio orario dal corpo principale.
- `contesto_form_nuova(data_str)`: prepara tutti i dati per la pagina GET.
- Le funzioni di supporto già esistenti a livello di modulo in
  `routes/assenze.py` (`is_sospensione`, `_sync_presenza_ist*`,
  `_ripristina_presenza_ist`, `_genera_supplenze`), usate anche da
  `elimina()` e `modifica()`, sono state spostate qui e reimportate nella
  route — nessuna duplicazione, stesso comportamento.

`routes/assenze.py::nuova()` è passata da ~320 righe a poche decine: la
route ora si limita a chiamare le funzioni del modulo, gestire flash/
redirect/render. Il file è sceso da 900 a 309 righe.

**Verifica:** copia in `/tmp`, pytest 51/51. Verifica rigorosa via
snapshot-diff dello stato del database: ricostruita la versione
pre-modifica di `routes/assenze.py` con `git show HEAD:...`, eseguita la
stessa richiesta POST (stesso docente reale, stesse date, stesso motivo)
su due copie identiche del database — una con il codice vecchio, una con
quello nuovo — poi confrontato riga per riga lo stato finale di
`Assenza`, `MovimentoBancaOre`, `Supplenza`, `AttivitaIstPresenza`:
nessuna differenza. Ripetuto lo stesso confronto anche per i due
percorsi meno comuni (`permesso_orario` con orario istituzionale HH:MM,
`scambio_orario` con creazione di `ScambioOrario`/`ScambioSlot`):
nessuna differenza anche lì.

---

## Sessione 24 — Consolidamento business logic (parte 3): export_xlsx.py

**Contesto:** proseguimento item #18 su `routes/export_xlsx.py`. Individuata
una duplicazione netta tra `_export_classe()` (un file per una singola
classe) e `_aggiungi_foglio_classe()` (un foglio per classe dentro il
file "tutte le classi"): le due funzioni disegnavano la stessa tabella
(docente/materia/ore/incarichi) con ~80 righe quasi identiche copiate
due volte, con piccole divergenze non intenzionali tra le due copie:

- `_export_classe` usava `a.tipo` come fallback nome-materia quando
  mancava la materia collegata; `_aggiungi_foglio_classe` mostrava
  sempre `'—'` in quel caso, perdendo l'informazione.
- `_aggiungi_foglio_classe` interrogava due volte `IncaricaDocente` per
  la stessa classe (una per la mappa, una per la sezione "Incarichi di
  classe") invece di riusare la lista già recuperata.
- `_export_classe` non troncava/ripuliva il nome del foglio a 31
  caratteri (limite Excel) come faceva invece l'altra funzione — un
  bug latente per etichette di classe molto lunghe.

**Modifica:** estratta `_riempi_foglio_classe(ws, anno, label_classe)`,
che riceve un foglio già creato e lo riempie; `_export_classe()` e
`_aggiungi_foglio_classe()` ora si limitano a creare il workbook/foglio
e delegano il contenuto a questa funzione condivisa. Le tre divergenze
sopra sono state armonizzate (fallback `a.tipo`, incarichi interrogati
una sola volta, troncamento nome foglio applicato in entrambi i casi).

**Verifica:** copia in `/tmp`, pytest 51/51. Generati via test client
tutti gli export (`p1`…`p10`, export singola classe, export "tutte le
classi") sui dati reali — tutti 200 OK. Confronto cella-per-cella,
tramite openpyxl, dell'output di `_export_classe()` vs
`_aggiungi_foglio_classe()` per tutte le 38 classi attive dell'anno
2026-2027: risultato identico su tutte, confermando che la
consolidazione non ha introdotto differenze nei dati reali (le
divergenze erano solo su casi limite mai presentatisi finora).

---

## Sessione 23 — Orario docenti di sostegno

**Contesto:** richiesta esplicita — l'app non gestiva i docenti di sostegno
assegnati alle classi con studenti PEI, che nella pratica sono in
compresenza con il titolare e possono coprirne l'assenza esattamente come
un ITP. Obiettivo: struttura dati per il loro orario, tenuta separata da
quello principale (perché `modules/parser_orario.py` cancella e ricrea
per intero `OrarioDocente` a ogni import), e integrazione nella logica
di suggerimento supplenze e in tutto ciò che già usa `modules/compresenze.py`.

Decisioni prese con l'utente (3 domande):
- Anagrafica: nuovo valore `ruolo='sostegno'` su `Docente` — record
  anagrafico completo come titolari/ITP (scheda, ore contratto, banca ore).
- Inserimento orario: **manuale da interfaccia**, non da file (niente
  parser: un form con docente/giorno/ora/classe/note).
- Segnalazione in supplenze: suggerito **come una compresenza normale**
  (stessa logica di un ITP), niente trattamento speciale nel calcolo —
  solo un badge "SOS" per riconoscerlo visivamente in elenco.

**Modifiche:**
- `models/orario_sostegno.py` (nuovo): modello `OrarioSostegno` — tabella
  separata `orario_sostegno` (id_docente, giorno, ora, classe, note),
  vincolo di unicità (docente, giorno, ora). Funzione di supporto
  `slots_come_orario_docente()` che "traveste" le sue righe da
  `OrarioDocente` (tipo_ora='compresenza') per riusare senza duplicarla
  la logica già scritta altrove.
- `modules/compresenze.py::get_compresenze()`: ora unisce anche le righe
  di `OrarioSostegno` — un solo punto di modifica che propaga il
  beneficio a `routes/supplenze.py`, `routes/assenze.py` e
  `routes/attivita.py::genera_effetti()`, tutti già basati su questo modulo.
- `routes/supplenze.py::api_suggerimenti()`: unisce gli slot di sostegno
  nel calcolo giornaliero e nel calcolo "sua classe" su tutti i giorni;
  aggiunto badge "SOS" (teal) accanto a quello ITP (viola).
- `templates/docenti.html` / `templates/docente_form.html`: terzo
  ruolo "🧩 Sostegno" selezionabile nel form docente, badge "SOSTEGNO"
  nell'elenco; corretto un bug latente nel JS del form (il blocco di
  abbinamento "titolare di riferimento", specifico degli ITP, sarebbe
  comparso erroneamente anche per il ruolo sostegno).
- `routes/orario_sostegno.py` (nuovo blueprint) + `templates/orario_sostegno/index.html`
  (nuovo): sezione dedicata `/orario-sostegno` per inserire/modificare/
  eliminare gli slot orario dei docenti di sostegno, con rilevamento
  conflitti (stesso docente, stesso giorno/ora) e log di audit
  (`crea_orario_sostegno` / `modifica_orario_sostegno` / `elimina_orario_sostegno`).
- `app.py`: registrato il nuovo blueprint (tabella creata automaticamente
  da `db.create_all()`, già presente in `create_app()` — nessuna modifica
  necessaria al meccanismo di migrazione).
- `templates/base.html`: "📅 Orario" trasformato in un piccolo menu a
  tendina con "Orario globale" e "Orario sostegno" (Display resta un
  link diretto, come richiesto in precedenza).

**Verifica:** copia in `/tmp`, pytest 51/51 passati. Test manuali via
Flask test client: CRUD completo su `/orario-sostegno` (aggiunta,
rilevamento conflitto, modifica, eliminazione, tutti verificati sul
DB), e test end-to-end di integrazione: creato un docente di sostegno
con uno slot orario coincidente con quello di un titolare reso assente
quel giorno/ora — la chiamata a `/api/suggerimenti` restituisce
correttamente il docente di sostegno con `compresenza: true` (stesso
meccanismo di un ITP) e badge "SOS".

**Non toccato in questo giro (possibili estensioni future, da valutare
solo su richiesta):** `routes/report.py::pianifica_permessi()` e la
vista orario globale (`routes/sincronizzazione.py`) non mostrano ancora
gli slot di sostegno — non ne avevano bisogno per questa richiesta, ma
potrebbero beneficiarne in futuro.

---

## Sessione 22 — Consolidamento business logic (parte 2): genera_effetti()

**Contesto:** proseguimento item #18 su richiesta esplicita ("perché non
continuiamo con altre parti del codice?"). Target scelto insieme:
`routes/attivita.py::genera_effetti()` (221 righe) — calcola gli effetti
di gite/progetti/FSL/simulazioni su indisponibilità, assenze automatiche
e supplenze scoperte.

### Perché solo due estrazioni mirate, non una riscrittura

A differenza di `api_suggerimenti()` (sola lettura, ritorna JSON),
`genera_effetti()` scrive direttamente su 4 tabelle diverse con
controlli di idempotenza (`if not ... .first(): db.session.add(...)`)
a ogni singolo passo. Separare del tutto "logica pura" da "scrittura DB"
qui richiederebbe una riscrittura strutturale rischiosa senza una
ragione concreta. Estratte in `modules/attivita_effetti.py` solo le due
regole che erano **duplicate identiche** in due punti della funzione
(percorso con calendario dettagliato FSL/BIM vs percorso generico):

- `classe_e_gia_fuori_aula(classe, classi_attivita_corrente, data, id_attivita_corrente, ora)`
  — decide se una classe è già "fuori aula" per un altro motivo (quindi
  niente supplenza scoperta per l'assenza dell'accompagnatore).
- `marker_sorveglianza(tipo_label, descrizione, ore_str, id_attivita, data)`
  — pura, costruisce la stringa usata sia per creare sia per
  riconoscere (idempotenza) il movimento banca ore di sorveglianza.

### Verifica (più rigorosa del solito, vista la scrittura su DB)

Essendo una funzione con effetti collaterali (non un semplice JSON di
risposta), il confronto prima/dopo non poteva limitarsi a un diff di
output HTTP. Usato il repository git per ricostruire la versione
originale di `routes/attivita.py` (`git show HEAD:...`, confermato via
`git diff --stat` che nessun'altra modifica in sospeso tocca quel file),
poi: due copie identiche del database reale in `/tmp`, una con la
funzione originale e una con la versione rifattorizzata, eseguito
`genera_effetti()` su **tutte le 40 attività fuori-aula reali presenti
nel database** (gite, FSL con calendario dettagliato, simulazioni con
sorveglianza, progetti) in entrambe le copie, poi confrontati i dump di
tutte le righe generate (Indisponibilità, Assenze, Supplenze, Movimenti
banca ore) — **identici in ogni campo tranne i timestamp di
inserimento** (ovviamente diversi, essendo due esecuzioni reali in
momenti diversi). Più pytest 51/51.

### Cosa resta

Le altre funzioni lunghe elencate nella Sessione 21 (calendario recupero
giugno, agosto_gruppi, export xlsx, assenze.nuova...) restano da valutare
una alla volta quando si vorrà proseguire — stesso approccio
snapshot/dump-diff, che si è dimostrato affidabile anche per funzioni
con effetti collaterali sul DB, non solo per funzioni di sola lettura.

---

## Sessione 21 — Consolidamento business logic: api_suggerimenti()

**Contesto:** item #18 della roadmap. Il codice ha diverse route molto
lunghe (`recupero_giugno.py::calendario()` 465 righe, `agosto_gruppi()`
422, export xlsx 420, `api_suggerimenti()` 402, `assenze.nuova()` 318,
ecc. — ~15.500 righe totali in `routes/`). Rifattorizzare tutto in una
sessione sarebbe rischioso e impossibile da verificare con cura.
Concordato con l'utente di partire da un caso concreto invece di
tentare tutto insieme, lasciando intatte le funzioni più critiche
(assenze, export, calendari di recupero) già toccate di recente.

### Cosa è cambiato

`routes/supplenze.py::api_suggerimenti()` (calcolo dei docenti
suggeriti come sostituti in dashboard) era una singola funzione di 402
righe che mescolava parsing della request, query DB e regole di
business. Estratte in un nuovo modulo `modules/suggerimenti_supplenza.py`
le parti isolabili senza toccare la logica di classificazione centrale
(troppo intrecciata con `modules.compresenze` per estrarla senza
rischio in questa sessione):

- `formatta_saldo_label(minuti)` e `formatta_saldo_label_proiettato(eff, prev)`
  — pure, senza query. Prima la stessa formula per l'etichetta saldo
  proiettato era duplicata identica in due punti della funzione.
- `calcola_saldi_docenti(anno_scol, oggi=None)` — calcolo saldo
  effettivo/previsto per tutti i docenti.
- `docenti_esclusi(data_sel, ora, giorno)` — chi è assente (tutto il
  giorno o solo quell'ora) o indisponibile puntualmente.
- `docenti_occupati_stessa_ora(data_sel, ora)` — chi è già assegnato
  come sostituto altrove nella stessa ora.
- `ha_ora_adiacente(ore_occupate, ora)` — pura, dice se l'ora prima o
  dopo è già occupata (prima duplicata due volte identica).

`api_suggerimenti()` passa da 402 a 346 righe; la riduzione principale
non è la lunghezza in sé ma il fatto che le regole "chi è escluso",
"come si calcola il saldo" e "come si etichetta" ora hanno un nome,
sono in un file separato e sono richiamabili/testabili senza dover
simulare un'intera richiesta HTTP.

### Verifica

Approccio: snapshot prima/dopo. Su una copia in `/tmp`, prima della
modifica, chiamata `/api/suggerimenti` con 10 combinazioni realistiche
di data/ora/classe/assente (tratte da supplenze reali nel DB + casi
manuali) e salvato l'intero JSON di risposta. Applicata la
refactor, rigenerato lo stesso identico set di chiamate su una copia
fresca: `diff` tra i due file JSON — **nessuna differenza, byte per
byte**, su tutti e 10 i casi. Più pytest 51/51.

### Cosa resta (non affrontato in questa sessione)

Elenco delle funzioni-route più lunghe rimaste, per riferimento futuro
se si vorrà proseguire il consolidamento:
`recupero_giugno.py::calendario()` (465), `recupero_agosto.py::agosto_gruppi()`
(422), `recupero_export.py::export_xlsx()` (420), `assenze.py::nuova()`
(318), `recupero_agosto.py::_genera_bozza_agosto()` (296),
`recupero_giugno.py::gruppi()` (272). Sono tutte più rischiose di
`api_suggerimenti()` da toccare a cuor leggero: alcune sono export
Excel (side-effect su file, più difficili da testare con uno snapshot
puro), altre (assenze.nuova) sono già state modificate più volte in
questa serie di sessioni e centrali all'uso quotidiano — meglio
affrontarle una alla volta, con lo stesso approccio snapshot-diff, in
sessioni dedicate.

---

## Sessione 20 — Lock ottimistico su Supplenze e Docenti

**Contesto:** item #15 della roadmap. Rischio concreto identificato:
segreteria/collaboratore/DSGA possono avere aperta la stessa dashboard
o la stessa scheda docente contemporaneamente; senza alcun controllo,
chi salva per ultimo sovrascrive in silenzio l'altro (es. due persone
assegnano la stessa supplenza scoperta quasi in contemporanea — vince
l'ultimo salvataggio, il primo sparisce senza che nessuno se ne accorga).
Confermato con l'utente l'ambito: Supplenze + Docenti (non Assenze/altro,
dove il rischio è più basso e un lock aggiungerebbe complessità per poco
beneficio).

### Come funziona

Nessun vero "lock" (nessuno blocca il record): si usa il timestamp
`modificato_il` già presente su `Supplenza` (e aggiunto ora su
`Docente`, con migrazione automatica) come "versione". Il valore letto
al caricamento del form viene passato come campo nascosto; al
salvataggio si ricontrolla che coincida ancora con quello nel DB —
se qualcun altro ha salvato nel frattempo, la modifica viene rifiutata
con un avviso esplicito invece di essere applicata alla cieca.
Centralizzato in un nuovo modulo `concorrenza.py` (`versione_str`,
`versione_cambiata`), riusabile per altri modelli in futuro.

Coperti tutti i punti di scrittura su Supplenza chiamabili dalla
dashboard: `assegna`, `annulla`, `cambia-tipo` (inline via fetch/JSON,
409 invece di redirect+flash), `modifica` (form completo). E su
Docente: `modifica` (la creazione `nuovo()` non necessita del controllo,
non c'è nulla da sovrascrivere).

### Verifica

Su copia in `/tmp`: pytest 51/51. Simulato lo scenario reale via Flask
test client — due "utenti" che leggono la stessa supplenza scoperta,
il primo assegna con successo, il secondo (versione ormai superata)
viene bloccato con l'avviso e il DB conserva l'assegnazione del primo,
non sovrascritta. Stesso test per modifica anagrafica docente
(email del secondo utente non applicata) e per cambia-tipo/annulla
(risposta 409 / redirect con avviso, stato invariato). Verificato anche
il caso normale (nessun conflitto): salvataggio a versione corretta
sempre applicato senza falsi positivi.

---

## Sessione 19 — Cronologia modifiche dati (audit trail)

**Contesto:** item #16 della roadmap. Esisteva già un `LogAccesso`
(tabella `log_accessi`, pagina `/log-accessi` sotto Utenti) usato però
solo per login/logout e gestione utenti — nessuna traccia di chi avesse
creato/modificato/eliminato un docente, una supplenza, un'assenza, una
sospensione o i dati istituto. Invece di introdurre una nuova tabella e
un nuovo modello, esteso quello esistente: stessa infrastruttura,
stesso viewer, solo più azioni registrate e filtri migliori per
renderlo effettivamente consultabile.

### Azioni ora tracciate (oltre a login/utenti, già presenti)

- **Docenti**: `crea_docente`, `modifica_docente`, `elimina_docente`
  (con conteggio dei dati collegati se l'eliminazione è stata forzata).
  `anonimizzazione` (art.17 GDPR) era già tracciata.
- **Supplenze**: `assegna_supplenza`, `annulla_supplenza`,
  `modifica_supplenza`, `cambia_tipo_supplenza`.
- **Assenze**: `crea_assenza`, `modifica_assenza`, `elimina_assenza`.
- **Sospensioni didattiche**: `crea_sospensione`, `modifica_sospensione`,
  `elimina_sospensione`.
- **Dati istituto**: `modifica_dati_istituto` — logga solo i campi
  effettivamente cambiati con vecchio→nuovo valore (es.
  `costo_ora_supplenza: 29.08 → 31.5`), non l'intero form.

Non toccati i movimenti banca ore diretti (non hanno una route di
modifica manuale separata: derivano sempre da supplenze/assenze, già
tracciate a monte) né azioni a bassissimo valore/altissima frequenza
non ancora presenti nel codice.

### Viewer migliorato

La pagina (rinominata da "Log Accessi" a **"Cronologia attività"**,
stesso URL `/log-accessi`, stesso permesso `gestione_utenti`) aveva un
elenco fisso degli ultimi 500 record senza alcun filtro — con le nuove
azioni instrumentate sarebbe stata rapidamente inutilizzabile. Aggiunta
una barra filtri: testo libero (cerca in azione+dettaglio), azione
(tendina con i valori realmente presenti in tabella), utente, intervallo
di date. Risultati limitati a 300 per query, ordinati più recenti prima.

### Verifica

Su copia in `/tmp`: pytest 51/51. Smoke test end-to-end via Flask test
client: creazione docente, sospensione, modifica dati istituto,
creazione/eliminazione assenza, creazione/assegnazione/annullamento
supplenza — cronologia interrogata direttamente sul DB e via la pagina
filtrata, confermando che ogni azione compare con il dettaglio corretto
e che i filtri per azione isolano correttamente i risultati.

---

## Sessione 18b — Ritocchi navbar post-feedback

Dopo il primo riordino (Sessione 18), tre correzioni su segnalazione
diretta:

1. **Dropdown "morti" al click**: il menu a tendina era pensato per
   l'hover, ma la nav ha `overflow-x:auto` (necessario per lo scroll
   orizzontale di sicurezza), che per specifica CSS forza anche il
   clipping verticale — il menu veniva tagliato via prima di comparire,
   sia in hover che al click. Risolto passando a un dropdown click-based
   con `position:fixed` calcolato via JS (si veda lo `<script>` in fondo
   a `base.html`), che esce dal contesto di scroll della nav.
2. **Brand**: da "📋 Supplenze — Da Vinci" a due righe — "CaronteApp —
   Da Vinci Chiavenna" sopra, giorno/data/ora corrente sotto (aggiornata
   ogni 30s via JS, nessuna chiamata al server).
3. **Display fuori dal menu "Orario"**: essendo di uso quotidiano,
   riportato come link diretto in barra invece che dentro il dropdown.
   Orologio spostato leggermente più in basso (margin-top) per
   staccarlo meglio dal nome dell'app.

Verificato su copia in `/tmp` ad ogni passaggio: pytest 51/51, smoke
test HTML per la presenza dei nuovi elementi.

---

## Sessione 18 — Riordino navbar: una riga, raggruppata, nomi coerenti

**Contesto:** la navbar aveva 10+ link a piatto (wrap su più righe a
schermi normali) e alcune etichette non coincidenti col contenuto reale
della pagina collegata.

### Incoerenze di naming trovate

- "📁 Fuori sede" → puntava a `attivita.lista`, il cui titolo pagina è
  "Attività fuori aula" e il cui contenuto include anche cose non
  fuori sede in senso stretto (simulazioni d'esame, migrazione gruppo
  = classe parzialmente fuori aula ma comunque a scuola). Rinominato in
  **"Attività fuori aula"**, coerente col titolo pagina.
- "📅 Vista orario" → puntava a `sync.orario_globale`, titolo pagina
  "Orario globale". Rinominato in **"Orario globale"**.
- "📋 Assenze" in grassetto rosso in realtà porta sempre e solo al form
  di *nuova* registrazione (non esiste una pagina lista assenze
  separata): rinominato in **"Registra assenza"** per essere esplicito
  sull'azione, non solo sulla sezione.

### Riorganizzazione

Navbar ora su una riga sola (nowrap + scroll orizzontale come rete di
sicurezza se la finestra è molto stretta, invece di andare a capo).
Raggruppati con menu a tendina (hover, nessun JS necessario) i link
meno usati quotidianamente:
- **Attività ▾**: Attività fuori aula, Attività istituzionali, Attività differite
- **Orario ▾**: Orario globale, Display

Restano diretti in barra i link ad alta frequenza: Dashboard, Registra
assenza (CTA), Banca Ore, Report, Impostazioni. La casella di ricerca
(sessione precedente) è stata spostata a destra, stile più integrato
nella navbar invece che come form isolato. Utente/PIN/Logout ora
raggruppati in un menu "👤 Nome ▾" a destra invece di 3 elementi sparsi,
per liberare spazio.

### Verifica

Su copia in `/tmp`: pytest 51/51 passati; smoke test via Flask test
client sulla dashboard che verifica la presenza di tutte le nuove
etichette e della casella di ricerca nell'HTML renderizzato.

---

## Sessione 17 — Ricerca globale cross-sezione

**Contesto:** item #17 della roadmap. Prima serviva sapere in quale
sezione dell'app cercare (Docenti? Supplenze? Banca ore?) per trovare
un'informazione — utile soprattutto quando si ricorda un nome o una
classe ma non dove sia registrato l'evento collegato.

### Cosa è stato aggiunto

- Nuovo blueprint `routes/ricerca.py` (`/ricerca?q=...`), dietro
  `login_required()` (nessun permesso specifico: chiunque sia loggato
  può cercare, ma solo tra gli stessi dati a cui avrebbe comunque
  accesso navigando le sezioni).
- Ricerca per sottostringa (case-insensitive, `ILIKE %q%`, minimo 2
  caratteri) in parallelo su 5 tabelle: Docenti (cognome, nome,
  nome_display, materia, email, note), Supplenze (classe, note,
  note_display, cognome/nome di assente e sostituto), Assenze (motivo,
  note_interne, cognome/nome docente), Movimenti banca ore
  (descrizione, cognome/nome docente), Sospensioni didattiche
  (descrizione). Risultati raggruppati per categoria, max 25 per
  categoria, ciascuno con link diretto alla pagina di dettaglio/modifica
  esistente (nessuna nuova pagina di dettaglio creata).
- Nessuna indicizzazione full-text: il volume dati della scuola non la
  giustifica, una LIKE è sufficiente e non introduce dipendenze nuove.
- Casella di ricerca aggiunta in `templates/base.html` nella barra di
  navigazione (visibile solo se loggato), sempre raggiungibile da
  qualunque pagina.

### Verifica

Su copia in `/tmp`: pytest 51/51 passati. Smoke test via Flask test
client: `/ricerca` senza query (200, messaggio "digita almeno 2
caratteri"), con 1 carattere (stesso messaggio), ricerca di un cognome
docente reale (trovato, sezione Docenti popolata), ricerca di una
classe con supplenze reali (trovata in sezione Supplenze), ricerca di
una descrizione di movimento banca ore reale (trovata), verifica che
la casella di ricerca compaia nella nav della dashboard senza errori
di rendering.

---

## Sessione 16 — Audit "Calendario scolastico" (Impostazioni): bug, unificazione, promemoria

**Contesto:** su richiesta, verifica della sezione Impostazioni →
Sospensioni didattiche / Periodi ("Calendario scolastico") prima di
proseguire con il resto della roadmap: bug presenti, funzionalità
migliorabili, impostazioni sparse altrove da accorpare lì.

### 1. Bug reale trovato e corretto: titolo pagina rotto

In `templates/impostazioni/sospensioni.html` uno `<script>` con la
funzione `toggleEdit()` era finito per errore dentro
`{% block title %}...{% endblock %}` invece che nel `content`/`extra_script`.
Risultato: il tag `<title>` della pagina conteneva letteralmente il
codice JS (titolo della scheda del browser rotto). Non c'era impatto
funzionale perché la stessa funzione era definita correttamente (in
duplicato) anche in fondo al file. Rimosso lo script dal blocco titolo;
verificato che il duplicato corretto resta e funziona (`toggleEdit`
presente esattamente 1 volta ora, titolo pulito
`<title>Sospensioni didattiche — IIS Da Vinci</title>`).

### 2. Unificati due elenchi paralleli di "giorni non didattici"

Prima esistevano **due** liste separate e mantenute a mano
indipendentemente:
- `Impostazioni → Sospensioni didattiche` (modello `SospensioneDidattica`,
  usato per bloccare/avvisare in fase di registrazione assenze),
- `giorni_festivi_extra` (config_calendario.py, ConfigApp-backed),
  usato **solo** da `pianifica_permessi()` per escludere ponti/sospensioni
  dal calcolo delle date proposte per i permessi.

Rischio concreto: dimenticare di aggiornarne una delle due portava a
calcoli sbagliati (proposte di permesso in giorni di sospensione, o
viceversa) senza alcun avviso.

Ora `pianifica_permessi()` legge le sospensioni **direttamente** da
`SospensioneDidattica` (query sul range `[oggi, fine_anno]`, espandendo
ogni `data_inizio`-`data_fine` in giorni singoli). Rimossi da
`config_calendario.py` la funzione helper `_chiave_festivi_extra` e le
funzioni `get_giorni_festivi_extra`/`set_giorni_festivi_extra` (dead code,
nessun altro chiamante). Rimosso dal form di `pianifica_permessi.html`
il campo testuale "giorni festivi extra"; aggiunta una nota che rimanda
a Impostazioni → Sospensioni didattiche con il conteggio dei giorni
esclusi (`n_festivi_extra`), a beneficio di chi si aspettava ancora quel
campo.

### 3. Aggiunto avviso per mancata rigenerazione annuale

`_seed_sospensioni()` in `app.py` popola le sospensioni solo la prima
volta in assoluto (guardia `if SospensioneDidattica.query.count() > 0:
return`): un nuovo anno scolastico non genera automaticamente le nuove
festività/vacanze, e finora non c'era alcun avviso in caso di elenco
non aggiornato. Aggiunto in `routes/impostazioni.py::sospensioni()` un
controllo che conta le sospensioni sovrapposte all'intervallo
dell'anno scolastico corrente (`config_anno.intervallo_anno_scolastico`)
e, se zero, mostra un banner di avviso nella pagina invitando ad
aggiornare l'elenco. Non blocca nulla, è solo un promemoria visivo.

### Verifica

Su copia in `/tmp` (mai sul database reale): pytest 51/51 passati dopo
ogni modifica; grep di conferma che nessun riferimento a
`giorni_festivi_extra`/funzioni rimosse resti nel codice; smoke test
via Flask test client su `/impostazioni/sospensioni` (titolo corretto,
`toggleEdit` non duplicato, avviso assente quando l'anno corrente è
coperto, presente e corretto quando si simula un anno scolastico privo
di sospensioni) e su `/report/pianifica-permessi` (form senza il vecchio
campo, nota con conteggio corretto e link funzionante, calcolo
`festivi_extra` verificato con una sospensione di test aggiunta ad hoc).

---

## Sessione 15 — Pagina Dati istituto: config centralizzata, bug costo ora corretto

**Contesto:** sviluppo della pagina "Dati istituto" (stub vuoto, ma
attivamente linkato 2 volte da Impostazioni). Prima di costruirla,
scansione del codice per capire cosa oggi è sparso/hardcoded.

### Bug reale trovato: costo orario supplenza incoerente tra due report
Il costo orario supplenza usato per le stime economiche era **29,08€**
in due file (`routes/report.py`, `routes/banca_ore.py`) ma **~30€**
("MAD") hardcoded separatamente in `templates/report/dirigente.html` —
due report diversi (quello per i docenti/segreteria e quello per il
Dirigente) stimavano lo stesso costo con due numeri diversi. Confermato
con Roberto: 29,08€ è il valore corretto, ma deve restare modificabile
in qualsiasi momento (non un altro hardcode).

### Nuova pagina Dati istituto (Impostazioni → Dati istituto)
Creato `config_istituto.py` (stesso pattern chiave/valore di
`config_anno.py`/`config_calendario.py`, tabella `config_app`) con
default sicuri identici ai vecchi valori hardcoded, per non cambiare
nulla finché nessuno modifica esplicitamente i dati dal form. Contiene:
- **Dati anagrafici**: nome e indirizzo istituto.
- **Costo orario supplenza**: ora un'unica fonte per Report, Banca Ore e
  Report Dirigente (corretto il bug sopra).
- **Soglie CCNL art.44**: limite ore bucket A/B (40h) e soglia di alert
  nel cruscotto (32h), prima hardcoded in `get_ore_ist_docente()`.
- **Scadenza accordo sindacale**: i mesi (3) usati da `_lotti_aperti_docente`
  per calcolare la scadenza di ogni ora a debito/credito (Sessione 12).

Il calendario scolastico (fine lezioni, festivi extra — introdotto in
Sessione 10 per la Pianificazione permessi) resta volutamente **fuori**
da questa pagina, su indicazione di Roberto: è concettualmente parte
della sezione "Calendario scolastico" già esistente in Impostazioni
(Sospensioni didattiche, Periodi) — eventuale spostamento lì, non fatto
in questa sessione.

### Propagazione nome istituto
Aggiunto un `context_processor` in `app.py` che inietta `nome_istituto`/
`indirizzo_istituto` in tutti i template. Sostituita la stringa
`IIS "Leonardo da Vinci" — Chiavenna`, prima ripetuta a mano in 11 punti
diversi (login, display pubblico, privacy, bozze email, report Dirigente,
stampa singolo docente, 7 fogli Excel in `recupero_export.py` +
`rientro.py`, indice XLSX globale in `report.py`), con la variabile
centralizzata. Lasciate invariate le stringhe brevi di brand nell'header
("IIS Da Vinci" in `base.html`, titolo pagina e nav) — sono un'etichetta
UI corta, non il nome anagrafico ufficiale usato nei documenti.

### Verifica
Suite di test completa: 51/51 passati. Testato end-to-end su copia del
database reale: form mostra i default corretti (29,08€), salvataggio
funziona, e la modifica si propaga correttamente a login (nome), Report
Dirigente e Banca Ore (costo ora) — verificato con valori di prova
diversi dal default per essere certi che non fossero coincidenze.

---

## Sessione 14 — Badge "da fare" in recupero/copertura.html reso esplicito

Verificato il codice: `stato_agosto` (`routes/recupero.py`) assume oggi
solo due valori possibili (`ok` / `no_gruppo`), quindi il badge "✗ da
fare" non era funzionalmente sbagliato. Il problema era che il template
usava un `{% else %}` generico invece di un controllo esplicito su
`no_gruppo`: se in futuro venisse introdotto un terzo stato, sarebbe
stato etichettato silenziosamente come "da fare" senza che nessuno se ne
accorgesse. Reso esplicito con `{% elif %}` e aggiunto un badge di
fallback visibile ("⚠ stato non riconosciuto") per qualsiasi valore
imprevisto, invece di nasconderlo dietro un'etichetta fissa.

Verificato: suite di test 51/51 passati, template compilato senza errori.

---

## Sessione 13 — Rimosso stub morto "Cambio anno scolastico"

Rimossa la route `impostazioni.cambio_anno` (`/impostazioni/cambio-anno`)
in `routes/impostazioni.py`: era uno stub placeholder ("prossimamente"),
non linkato da nessun template né altrove nel codice — verificato con
grep su templates/routes/tests prima di toccarlo. Il vero wizard di
cambio anno è `routes/cambio_anno.py`, attivo e regolarmente linkato,
non toccato da questa pulizia.

Verificato su copia: suite di test 51/51 passati, app si avvia senza
errori, `url_for('impostazioni.cambio_anno')` ora solleva correttamente
`BuildError` (route effettivamente rimossa).

---

## Sessione 12 — Correzione scadenza 3 mesi: FIFO per singola ora, non saldo aggregato

**Contesto:** Roberto ha segnalato che il calcolo della scadenza 3 mesi
introdotto in Sessione 11 era concettualmente sbagliato: la scadenza va
verificata sulla singola ora a debito/credito, non sul saldo aggregato
del docente. Esempio dato: un'ora presa il 31/01 scade il 30/04, un'altra
presa il 4/02 scade il 4/05 — indipendentemente l'una dall'altra. Inoltre
confermato che la stessa logica deve valere anche per le ore che la
scuola deve far recuperare/pagare al docente (credito), non solo per il
debito del docente verso la scuola.

### Cosa c'era di sbagliato
`_scadenza_saldi()` calcolava "da quanti giorni il saldo cumulato del
docente non torna a zero" — un indicatore aggregato che confondeva ore di
epoche diverse in un unico numero, invece di dare a ciascuna ora presa in
un giorno diverso la propria scadenza individuale.

### Fix: abbinamento FIFO per lotti
Riscritta come due funzioni in `routes/report.py`:
- `_lotti_aperti_docente(id_docente, anno_scol)`: percorre lo storico dei
  movimenti in ordine cronologico mantenendo una coda di "lotti" di ore
  con segno (debito/credito) e data di origine. Un movimento di segno
  opposto compensa, in ordine FIFO, i lotti più vecchi ancora aperti
  (prima quello più vecchio, poi il successivo, ecc.) — due movimenti
  dello stesso segno (es. due permessi) NON si compensano fra loro e
  restano lotti distinti, ciascuno con la propria scadenza. La scadenza
  di ciascun lotto è la data di origine + 3 mesi di calendario (via
  `dateutil.relativedelta`, non giorni fissi — riproduce esattamente
  l'esempio 31/01→30/04, 4/02→4/05).
- `_scadenza_saldi(docenti, anno_scol)`: applica la funzione sopra a
  tutti i docenti e restituisce, per ciascuno con almeno un lotto
  scaduto, l'elenco dei lotti scaduti.

Il tasso di puntualità nel Report Dirigente ora è calcolato sul totale
delle singole ore (lotti) ancora aperte, non sul numero di docenti — una
misura più fedele e granulare di aderenza all'accordo sindacale. Il
cruscotto elenca, per ogni docente con ore scadute, quante e da quando la
più vecchia.

### Verifica
Riprodotto esattamente l'esempio di Roberto (31/01 e 4/02, due lotti
distinti con scadenze 30/04 e 4/05); verificata la compensazione FIFO
(una supplenza svolta compensa prima il debito più vecchio, lasciando
aperto solo quello successivo); verificato il caso simmetrico di credito
(ore di supplenza svolte dal docente non ancora pagate/recuperate dalla
scuola, stessa logica di scadenza). Suite di test completa: 51/51
passati. Cruscotto e Report Dirigente testati end-to-end su copia del
database reale.

---

## Sessione 11 — Bug suggerimento supplenze + monitoraggio scadenza 3 mesi

**Contesto:** Roberto ha chiesto di verificare se la modalità "suggerimento"
per assegnare una supplenza (dashboard) considera solo l'anno scolastico
corrente, e di aggiungere al cruscotto Report il monitoraggio della
scadenza dei 3 mesi per il saldo della banca ore, prevista da accordo
sindacale (ore da recuperare/richiedere da saldare entro 90 giorni) —
come indicatore informativo di qualità per il DS, non bloccante.

### Bug reale trovato e corretto: suggerimento supplenze non scoped per anno
Verificato `api_suggerimenti()` (`routes/supplenze.py`, usata dalla
dashboard per la modalità "suggerimento"): calcolava i saldi banca ore
usati per ordinare i candidati **senza alcun filtro `anno_scol`** — lo
stesso bug corretto in `routes/report.py` nella Sessione 7, ma in un file
diverso che non era stato toccato allora. Il suggerimento quindi ordinava
i docenti in base al debito/credito cumulato su tutti gli anni scolastici
mai registrati, non solo quello in corso. Corretto aggiungendo il filtro
`anno_scol == anno_corrente` alle due query di saldo (effettivo e
previsto), stesso pattern già usato altrove.

Durante la verifica, trovato anche un blocco di codice duplicato e morto
in `ottimizzazione_simulazioni()` (`routes/report.py`): un secondo calcolo
di "saldi" senza filtro anno, mai più referenziato nel resto della
funzione (il codice usa `saldi_proj`, non quel "saldi"). Rimosso.

### Nuovo: monitoraggio scadenza 3 mesi (accordo sindacale)
Aggiunta `_scadenza_saldi()` in `routes/report.py`: per ogni docente con
saldo banca ore ancora aperto (diverso da zero), calcola da quanti giorni
è aperto risalendo lo storico dei movimenti dell'anno e trovando l'ultima
volta in cui il saldo cumulato è tornato a zero (se mai). Soglia di
scadenza: 90 giorni, come da accordo sindacale.

- **Cruscotto Report**: nuovo alert informativo con l'elenco dei docenti
  con saldo aperto da oltre 90 giorni (saldo, giorni, data apertura).
- **Report Dirigente**: nuovo indicatore "Puntualità saldo entro 3 mesi"
  (percentuale di saldi aperti entro il termine) come indicatore di
  qualità, accanto agli altri KPI — nessun nome individuale mostrato,
  coerente con lo stile già esistente di questo report.

**Nota di trasparenza (discussa con Roberto):** con dati reali,
l'indicatore segnala una quota alta di docenti (36 su 41 con saldo
aperto) perché molti saldi piccoli (1-6h) semplicemente non capitano mai
a coincidere esattamente con zero durante l'anno. Proposta una soglia
minima di ore per ridurre il rumore, ma su richiesta di Roberto è stata
mantenuta solo la soglia temporale dei 90 giorni, aderente alla lettera
dell'accordo sindacale. Da tenere presente leggendo l'indicatore: un
numero alto non significa necessariamente una gestione scorretta, ma
riflette anche la normale fisiologia di piccoli saldi che restano aperti.
È comunque solo informativo, non blocca alcuna operazione.

### Verifica
Suite di test completa: 51/51 passati. Endpoint `/api/suggerimenti`,
cruscotto e Report Dirigente testati su copia del database reale;
`_scadenza_saldi()` verificata con dati reali (41 docenti con saldo
aperto, valori e date coerenti con lo storico).

---

## Sessione 10 — Chiusura follow-up tecnici aperti (anno scolastico)

**Contesto:** su richiesta di Roberto, gestione dei 4 follow-up tecnici
rimasti aperti dalle sessioni precedenti, in ordine di priorità concordato.

### 1. Data fine anno hardcoded in "Pianificazione permessi" — risolto
`pianifica_permessi()` (`routes/report.py`) aveva tre valori di calendario
scritti direttamente nel codice: `date(2026, 6, 6)` come ultimo giorno di
lezione, `{date(2026,6,1), date(2026,6,2)}` come festivi, e la riduzione a
3 ore proprio il 6 giugno. Funzionavano solo per l'anno scolastico
2025-2026 — l'anno prossimo, senza intervenire nel codice, il calcolo
avrebbe usato silenziosamente queste date sbagliate.

Creato `config_calendario.py`, che salva questi parametri in `config_app`
(stessa tabella chiave/valore già usata per l'anno scolastico corrente),
con una chiave per ogni anno scolastico. La pagina "Pianificazione
permessi" ora include un form per impostarli (ultimo giorno di lezione,
eventuali giorni di sospensione extra, ore ridotte nell'ultimo giorno) e,
se non ancora configurati per l'anno in corso, mostra un avviso esplicito
invece di procedere con un calcolo silenziosamente sbagliato.

### 2. Export PDF/XLSX docente non archivio-aware — risolto
`report.singolo_pdf` e `report.singolo_xlsx` ora accettano `?anno=` e
calcolano saldo/storico per quell'anno (prima ignoravano sempre l'anno
visualizzato e mostravano quello corrente). Il nome del file scaricato
include l'anno solo quando diverso da quello corrente (es.
`DOC_ROSSI_2024-2025_31-07-2026.xlsx`). I link da `banca_ore/index.html`
e `banca_ore/singolo.html` ora passano l'anno visualizzato.

### 3. Elenco supplenze non filtrato per anno nel dettaglio Banca Ore — risolto
`Supplenza` non ha una colonna `anno_scol` propria. Aggiunta
`intervallo_anno_scolastico(anno_scol)` in `config_anno.py` (restituisce
inizio/fine calendario dell'anno scolastico, stessa convenzione
settembre-agosto usata ovunque) e usata per filtrare le supplenze per
data in `routes/banca_ore.py::singolo()` e nei due export di
`report.py`, così l'elenco supplenze resta coerente con l'anno del saldo
mostrato sopra.

### 4. Cruscotto Report non scoped per anno scolastico — chiuso senza modifiche
Confermato con Roberto: i numeri mensili del cruscotto (assenze/supplenze
del mese vs mese precedente) sono un confronto di calendario per natura,
non di anno scolastico — applicare uno scoping per anno_scol
snaturerebbe il confronto mese-su-mese senza portare benefici reali.
Nessuna modifica necessaria.

### Verifica
Ogni fix verificato singolarmente su copia del database reale prima di
essere applicato: form di configurazione calendario testato end-to-end
(stato non configurato → salvataggio → calcolo corretto), export
PDF/XLSX testati con e senza `?anno=` esplicito, elenco supplenze
verificato con un docente reale con supplenze assegnate. Suite di test
completa: 51/51 passati dopo tutte le modifiche.

---

## Sessione 7 — Fix bug reale: banca ore non si azzerava mai al cambio anno

**Contesto:** su richiesta di Roberto ("verifichiamo che quando faccio il
passaggio al nuovo anno la banca ore venga azzerata e che i dati presenti
siano archiviati"), verifica del comportamento del cambio anno sulla banca
ore. Trovato un bug reale e serio, non introdotto in questa sessione ma
preesistente da sempre nell'app.

### Il bug
La tabella `banca_ore` non aveva **nessuna** colonna che identificasse
l'anno scolastico del movimento. Di conseguenza tutti i calcoli del saldo
(`get_saldi_docente`, `get_storico_settimanale` in `routes/report.py`, più
due simulazioni in `ottimizzazione_simulazioni()` e `pianifica_permessi()`)
sommavano **tutti** i movimenti mai registrati, di ogni anno scolastico,
senza mai azzerarsi. Un commento nel codice di `routes/cambio_anno.py`
affermava (falsamente) che "le viste filtrano già per anno scolastico" —
non era vero, non filtravano affatto.

In pratica: al cambio anno scolastico, il saldo di banca ore di un docente
restava quello accumulato in tutti gli anni precedenti, invece di ripartire
da zero per il nuovo anno.

### La correzione
- Aggiunta colonna `anno_scol` a `MovimentoBancaOre`, calcolata
  automaticamente dalla data del movimento (stessa regola di
  `config_anno.py`: settembre-agosto) tramite un evento SQLAlchemy
  `before_insert` — nessuna delle 6 righe di codice che creano un
  movimento ha dovuto essere toccata.
- Migrazione automatica e idempotente all'avvio (`_backfill_anno_scol_banca_ore`
  in `app.py`) che assegna l'anno scolastico corretto a tutti i movimenti
  storici già esistenti, inferendolo dalla loro data.
- `get_saldi_docente` e `get_storico_settimanale` ora accettano un
  parametro opzionale `anno_scol` (default: l'anno corrente) e filtrano
  di conseguenza. Stesso fix applicato alle due simulazioni in
  `routes/report.py`.
- Corretto il commento/messaggio fuorviante in `routes/cambio_anno.py`.
- Pagina **Banca Ore** (`/banca-ore` e `/banca-ore/docente/<id>`):
  aggiunto un selettore di anno scolastico e un banner "📦 Archivio" quando
  si consulta un anno diverso da quello corrente — così gli anni passati
  restano consultabili ma chiaramente distinti dal saldo attivo.
- Aggiunti test di regressione dedicati (`tests/test_banca_ore_anno_scol.py`,
  12 test) che coprono: calcolo automatico dell'anno scolastico,
  correttezza/idempotenza del backfill, corretto scoping dei saldi per
  anno (verificato che un anno senza movimenti dia saldo zero e che
  l'anno precedente resti intatto e consultabile esplicitamente).
- Verifica end-to-end eseguita su una copia del database reale (mai sul
  file reale): tutti i 535 movimenti storici reali correttamente
  classificati come anno '2025-2026'; simulato un cambio anno a
  '2026-2027' e confermato che il saldo del nuovo anno riparte da zero
  mentre l'archivio '2025-2026' mantiene i valori storici reali.
- Suite di test completa: **51/51 passati** (42 preesistenti + 9 nuovi
  della Sessione 7... di cui 3 con più assert, per un totale di 51 casi).

### Follow-up noti, non ancora risolti (da tenere presente)
- Nel dettaglio Banca Ore di un docente, l'elenco "Supplenze svolte" non è
  ancora filtrato per anno scolastico (la tabella `Supplenza` non ha una
  colonna anno_scol) — può mostrare supplenze di anni diversi da quello
  visualizzato nel saldo sopra.
- Gli export PDF/XLSX per singolo docente (`report.singolo_pdf`,
  `report.singolo_xlsx`) non sono ancora "archivio-aware": mostrano sempre
  l'anno corrente, anche se si esporta dalla vista di un anno archiviato.
- In `pianifica_permessi()` (`routes/report.py`) resta una data di fine
  anno hardcoded (`date(2026, 6, 6)`) non collegata alla configurazione
  dell'anno scolastico — da valutare se e come renderla dinamica.

### Prossimo passo
Redesign della pagina `/report` come hub per generazione report (Dirigente,
docenti, vicepresidi/segreteria) + cruscotto di monitoraggio semplificato
banca ore/assenze — richiesta ancora aperta di Roberto, da affrontare ora
che il fix sui saldi è completo.

---

## Sessione 8 — Pagina Report trasformata in hub con 4 tab

**Contesto:** seconda parte della richiesta di Roberto sulla pagina Report:
farla diventare l'hub per generare i report necessari (Dirigente, docenti,
vicepresidi/segreteria) oltre a un cruscotto di monitoraggio semplificato.
Confermato con Roberto: tab separate (non tutto in un'unica pagina lunga);
cruscotto con numeri di sintesi, docenti in credito/debito estremo,
andamento assenze del mese e alert su soglie.

### Cosa è cambiato
- `/report` è ora un hub con 4 tab (`?tab=cruscotto|dirigente|docenti|segreteria`,
  default `cruscotto`): nessuna nuova route creata, tutto dentro la route
  `report.index()` esistente, per non rompere nessuno dei link già presenti
  verso `report.index` in altri template (`base.html`, `mail_bozze.html`,
  `banca_ore/index.html`, ecc. — verificato che restano tutti funzionanti).
- **Tab Cruscotto** (nuova): ore credito/debito istituto, stima costo
  supplenze a credito, supplenze assegnate e assenze registrate nel mese
  corrente con confronto al mese precedente, elenco docenti in debito
  rilevante (≥5h) e credito rilevante (≥8h) con link diretto al dettaglio
  Banca Ore, alert per supplenze scoperte nei prossimi 7 giorni e docenti
  vicini al limite ore istituzionali CCNL art.44.
- **Tab Report Dirigente**: rimanda al report dettagliato già esistente
  (`report.dirigente()`, invariato) — nessuna duplicazione di logica.
- **Tab Report Docenti**: il contenuto che prima era l'intera pagina
  `/report` (tabella saldi per singolo docente con export PDF/XLSX).
- **Tab Report Segreteria**: tutti gli export e strumenti massivi che
  prima erano in "Report globali" (XLSX completo, bozze email, PDF tutti
  i docenti, pianificazione permessi, ottimizzazione simulazioni, export/
  import Excel, storico prospetti).
- Nuova funzione `_dati_cruscotto()` in `routes/report.py`, che riusa i
  saldi già calcolati da `index()` invece di ricalcolarli — nessuna query
  aggiuntiva pesante rispetto a prima.

### Verifica
- Suite di test completa: 51/51 passati (nessuna modifica ai test, il
  cambiamento è solo di route/template).
- Smoke test end-to-end su copia del database reale: tutte e 4 le tab
  rispondono 200, un valore di `tab` non valido ricade correttamente sul
  cruscotto di default, `report.dirigente` e `/banca-ore` continuano a
  funzionare invariati.

### Follow-up noti
- I numeri del cruscotto (assenze/supplenze del mese) non sono ancora
  filtrati per anno scolastico tramite `anno_scol` — usano direttamente
  la data, quindi a cavallo del cambio anno (agosto/settembre) il
  confronto "mese corrente vs mese precedente" può attraversare due anni
  scolastici diversi. Non un problema nella pratica (il confronto resta
  comunque coerente sul calendario), ma da tenere presente.

---

## Sessione 9 — Verifica utilità comandi Report Segreteria

**Contesto:** su richiesta di Roberto, verifica pratica (eseguendo ogni
comando su una copia del database reale) dell'effettiva utilità/correttezza
di tutti i comandi presenti nella nuova tab Report Segreteria.

### Bug reale trovato e corretto: PDF persi nell'export ZIP per omonimi
"Esporta tutti i report PDF" nominava ogni file `DOC_COGNOME.pdf`. Nell'
istituto ci sono 3 coppie di docenti con lo stesso cognome (Ghezzi,
Tramontana, Valena): il file generava due voci con nome identico nello
ZIP, e la maggior parte dei programmi di estrazione mostra/estrae solo
una delle due, perdendo silenziosamente il PDF dell'altro docente.
Confermato via test diretto sullo ZIP generato (88 docenti attivi, prima
del fix 3 nomi duplicati).

**Fix:** quando il cognome è condiviso da più docenti, il nome del file
include ora l'iniziale del nome (`DOC_GHEZZI_A.pdf`); se anche l'iniziale
coincide, si aggiunge l'ID del docente come ultimo livello di sicurezza
(verificato con i dati reali: succede proprio per Ghezzi e Tramontana,
che condividono anche l'iniziale). Verificato dopo il fix: 88 file nello
ZIP, tutti con nome univoco.

L'export XLSX globale (`report.globale_xlsx`) non aveva lo stesso
problema: openpyxl rinomina automaticamente i fogli di lavoro duplicati
(`DOC_GHEZZI` → `DOC_GHEZZI1`), verificato ricaricando il file generato.

### Rimosse dall'interfaccia: Export/Import banca ore ↔ Excel legacy
Su conferma di Roberto ("non le uso più"), le due card "Export banca ore
→ Excel" e "Import banca ore da Excel" (basate sul vecchio file
`Banca_Ore_Docenti_v3.xlsm`, mantenuto a mano da prima che la banca ore
fosse gestita nel database dell'app) sono state rimosse dalla tab Report
Segreteria. Le route (`report.export_excel`, `import_banca.index`) e i
relativi moduli **non sono stati cancellati** — solo scollegati
dall'interfaccia — per prudenza, nel caso servisse recuperarle. Da
valutare in futuro se rimuoverle definitivamente dal codice.

### Altri comandi verificati, nessun problema trovato
Banca Ore completa XLSX, Prepara bozze email, Pianificazione permessi
orari, Ottimizzazione simulazioni, Storico prospetti supplenze — tutti
testati con esito positivo su copia del database reale.

### Follow-up noto, non ancora risolto
In "Pianificazione permessi" resta una data di fine anno scolastico
hardcoded nel codice (`date(2026, 6, 6)` in `pianifica_permessi()`,
`routes/report.py`). L'anno prossimo, se nessuno se ne ricorda di
aggiornarla, il calcolo si baserà silenziosamente su una data sbagliata.
Da valutare come renderla dinamica (es. derivata dal calendario
scolastico configurato).

### Verifica
Suite di test completa: 51/51 passati dopo entrambe le modifiche. Fix
del bug ZIP e rimozione dei link Excel testati end-to-end su copia del
database reale prima di applicarli ai file reali.

---

## Sessione 6 — Analisi roadmap + archiviazione script storici

**Contesto:** su richiesta di Roberto, analisi indipendente del codice
(non basata sul devlog) per individuare cosa manca da sviluppare. Creata
una todo list con 10 voci, ordinate per priorità percepita. Prima azione
concreta: archiviazione degli script one-off, con conferma di Roberto.

### Roadmap identificata (todo list, non ancora tutta implementata)
1. Vista propria per Banca Ore (oggi `/banca-ore` fa solo redirect a
   Report, nonostante `MovimentoBancaOre` sia centrale in 6 route).
2. Rimuovere lo stub morto `/impostazioni/cambio-anno` (verificato: non
   linkato da nessun template — il vero wizard attivo è
   `routes/cambio_anno.py`, linkato regolarmente).
3. Sviluppare `/impostazioni/dati-istituto` (stub attivamente linkato 2
   volte in `impostazioni/index.html` — da capire con Roberto cosa deve
   contenere davvero).
4. ~~Script one-off in root~~ → **fatto, vedi sotto**.
5. Badge "✗ da fare" hardcoded in `templates/recupero/copertura.html`.
6. Valutare lock ottimistico per modifiche concorrenti (app multiutente
   senza alcun meccanismo di concorrenza trovato: due persone possono
   sovrascriversi su supplenze/banca ore senza avviso).
7. Cronologia modifiche dati: oggi `log_accesso` traccia solo i login,
   non le modifiche ai dati.
8. Ricerca globale cross-sezione (oggi assente).
9. Consolidare business logic fuori dalle route più lunghe
   (`recupero_giugno.py` 1616 righe, `impostazione_anno.py` 1605,
   `report.py` 1177 — molta logica scritta inline nelle route invece
   che in `modules/`).
10. Decidere destino del modulo `att_differite` (hub vuoto con nota
    "in futuro, esami integrativi" mai implementata).

### Fatto: archiviazione script storici una tantum
Spostati in `scripts/legacy/` (nuova cartella, con `README.md` di
spiegazione): `import_banca_ore.py`, `import_orario.py`,
`fix_date_storico.py`, `scripts_seed_classi_concorso.py`,
`scripts_seed_piano_studi.py`, `scripts_collega_piano_materie.py`.

Verificato prima di spostare che **non sono doppioni** di
`modules/import_banca_ore.py` (usato dalla route web ricorrente):
sono bootstrap storici, eseguiti una sola volta all'avvio del progetto,
con date scritte a mano (es. `date(2026, 5, 23)` in
`import_banca_ore.py`) e senza controlli di idempotenza.

**Scoperto un rischio reale durante la verifica**: `scripts_seed_piano_studi.py`
e `scripts_collega_piano_materie.py` eseguono le scritture sul database
appena il modulo viene importato (nessun blocco `if __name__ ==
'__main__':` a protezione, a differenza degli altri 4 script). Non
modificata la struttura interna del file (troppo rischioso riscrivere
l'indentazione di uno script di 300 righe per un guadagno marginale):
segnalato chiaramente nel README invece, con l'istruzione di non
importare mai questi due file da altro codice.

**Fix tecnico necessario per lo spostamento**: i 6 script usano
`sys.path.insert(...)` (o si appoggiavano al comportamento di default di
Python) per trovare `app.py` nella cartella radice. Spostandoli due
livelli più in profondità (`scripts/legacy/`), il calcolo del path
andava aggiornato di conseguenza in tutti e 6 (3 lo avevano già e sono
stati corretti, 3 non lo avevano — perché finora venivano lanciati solo
dalla root — e gli è stato aggiunto). Verificato con aritmetica dei path
+ suite di test completa (42/42) su una copia prima di applicare le
modifiche definitive.

### Verifica
Nessun altro file del progetto importa questi 6 script (`grep` su
`app.py`, `routes/`, `modules/`). Suite di test (42/42) e smoke test
dell'app eseguiti su copia dopo lo spostamento: tutto invariato.

### Fatto: vista propria per Banca Ore
`/banca-ore` prima era solo un redirect verso `/report`. La logica di
calcolo saldi (`get_saldi_docente`, `get_storico_settimanale`,
`get_ore_ist_docente` in `routes/report.py`) era già solida e corretta —
il problema reale non era la logica mancante ma la mancanza di
un'accesso diretto e riconoscibile ("Banca Ore" non compariva da
nessuna parte nel menu, bisognava sapere che stava sotto "Report").

Creato `routes/banca_ore.py` con due nuove route (`index` e
`singolo/<id>`), che **riusano** le funzioni di calcolo già esistenti in
`routes/report.py` (nessuna duplicazione di logica) e due nuovi
template (`templates/banca_ore/index.html`, `.../singolo.html`, adattati
da `report/index.html` e `report/singolo.html`, tenendo solo la parte
saldi/docente e togliendo gli altri strumenti report non pertinenti tipo
prospetti/dirigente/ottimizzazione). Aggiunta voce "💰 Banca Ore" nel
menu principale (`templates/base.html`), prima di "📊 Report".

Gli export PDF/XLSX per singolo docente e l'export XLSX globale
continuano a usare le route storiche di `report.py`
(`report.singolo_pdf`, `report.singolo_xlsx`, `report.globale_xlsx`):
nessun duplicato da mantenere per la stessa funzione.

**Scelta deliberata**: `/report` non è stato toccato — resta il hub per
gli altri strumenti (report Dirigente, prospetti, export Excel
settimanale, ottimizzazione simulazioni, pianificazione permessi), che
non sono specifici di banca ore. Non è stata rimossa la tabella saldi
duplicata in `report/index.html`: resta lì finché Roberto non conferma
di preferire la nuova pagina, per zero rischio di rottura nel frattempo.

Verificato su copia: suite di test (42/42), avvio app, rendering delle
due nuove pagine con dati reali, e conferma che `/report` continua a
funzionare esattamente come prima.

---

## Sessione 5 — Hardening sicurezza, pulizia, bug vincolo aule, copertura test

**Contesto:** dopo una scansione generale del codice (su richiesta di
Roberto) sono emersi diversi problemi di sicurezza e debito tecnico.
Lavoro svolto in più passaggi, sempre verificando su copie isolate del
database reale prima di toccare i file definitivi.

### Sicurezza
- **SECRET_KEY** (`app.py`): ora letta da variabile d'ambiente
  `CARONTE_SECRET_KEY`, con fallback al valore storico (nessuna sessione
  esistente invalidata).
- **Rate-limiting login** (`routes/auth.py`): blocco di 15 minuti dopo 5
  tentativi falliti sulla stessa coppia IP+username (in memoria, nessuna
  dipendenza esterna). Il login corretto azzera il contatore.
- **CSRF** (Flask-WTF): `CSRFProtect(app)` attivato globalmente in
  `app.py`. Invece di modificare a mano i 145 form POST sparsi in 61
  template (rischio altissimo), il token viene iniettato automaticamente
  da uno script centralizzato in `templates/base.html`: inserisce il
  campo `csrf_token` in ogni form POST al load (copre anche i
  `form.submit()` diretti) e aggiunge l'header `X-CSRFToken` a tutte le
  `fetch` di scrittura. Gestiti a parte i due casi che non ereditano da
  `base.html`: `templates/login.html` (campo statico) e il form generato
  via JS in `impostazione_anno/piano_studi.html`. Verificato con jsdom
  (simulazione DOM reale) + test Flask (`tests/test_csrf.py`).
- **Rimosso invio email automatico via SMTP**: eliminati
  `routes/email_report.py`, `modules/email_sender.py`,
  `templates/email_config.html` e i relativi pulsanti/link in
  `templates/report/index.html` (config email, invio singolo, invio
  cumulativo). Mantenuto solo il sistema di bozze (`mail_bozze.py`), che
  non invia nulla in automatico — genera bozze da rivedere e inviare a
  mano (Mail.app su Mac, `.eml`/PowerShell su Windows).

### Pulizia repo
- Rimossi `app.py.bak` (versione di codice obsoleta, non referenziata) e
  `database.db.bak` (backup non cifrato superato, ridondante rispetto ai
  backup cifrati giornalieri in `data/backup/`).
- Rimossi tutti i file `.DS_Store` sparsi nel repo.

### Bug corretto: vincolo UNIQUE tabella `aule`
Il modello Python dichiarava da tempo `UniqueConstraint('anno_scol',
'classe')`, ma il vincolo **reale** nel database era rimasto
`UNIQUE(classe)` da solo — SQLite non permette di alterare un vincolo
UNIQUE su tabella esistente con `ALTER TABLE`, quindi la colonna
`anno_scol` (aggiunta in un secondo momento) non aveva mai reso effettivo
il vincolo combinato dichiarato nel modello. Le route `aule.py` erano
state scritte (Sessione 4) per aggirare il vincolo reale filtrando solo
per `classe`, perdendo così la possibilità per una classe di avere aule
diverse in anni diversi.

Roberto ha confermato che il comportamento desiderato è quello per anno.
Corretto con:
- `app.py::_migra_vincolo_aule()` — migrazione automatica e idempotente
  (pattern standard SQLite: crea tabella nuova con vincolo corretto,
  copia i dati, elimina la vecchia, rinomina) eseguita ad ogni avvio,
  si attiva da sola alla prossima esecuzione di `avvia_caronte.sh`/`.bat`.
  Verificata su una copia esatta del database reale (39 righe): dati
  preservati identici, vincolo corretto, idempotente.
- `routes/aule.py` — ripristinate tutte le query/scritture (`salva`,
  `copia_anno`, `mappa_assegna`, `mappa_libera`, rimozione rapida in
  `lista`) per usare `anno_scol`+`classe` invece di `classe` da sola.
- `templates/aule/lista.html` — il link "rimuovi" non passava l'anno
  nell'URL, corretto insieme al resto.

### Copertura test (21 → 42 test)
Nuovi file in `tests/`:
- `test_aula_vincolo.py`, `test_migrazione_aule.py` — regressione sul bug
  del vincolo sopra descritto (incluso test della migrazione su schema
  storico simulato).
- `test_auth.py` — login, rate-limiting, isolamento tra utenti diversi,
  reset contatore su login corretto, logica permessi per ruolo
  (`Utente.ha_permesso`, incluso il caso "scrittura implica lettura").
- `test_backup_cifrato.py` — roundtrip cifra/decifra, chiave riutilizzata
  tra backup successivi, pulizia vecchi backup (mantiene solo gli ultimi
  N senza toccare file non correlati).
- `test_csrf.py` — conferma che CSRFProtect rifiuta richieste senza
  token e accetta quelle corrette.
Tutti isolati (DB in-memory o file temporanei), nessuno tocca mai
`database.db` reale.

### Verifica cross-platform
Tutte le modifiche di questa sessione sono state sviluppate e testate in
ambiente Linux (sandbox), non solo macOS: suite di test e smoke test
dell'app eseguiti con successo su Linux puro. Confermato che l'unico
riferimento macOS-specifico nel codice (bypass librerie WeasyPrint via
`DYLD_LIBRARY_PATH` in `app.py`) è preesistente, correttamente isolato
da un `if` di piattaforma, e non è stato toccato.

### Azione richiesta a Roberto
Installare la nuova dipendenza nel venv locale prima del prossimo avvio:
`python3 -m pip install -r requirements.txt` (dentro il venv attivato).
Da lì in poi tutto (inclusa la migrazione del vincolo aule) parte da
solo al prossimo avvio.

### Cose ancora aperte
- Nessuna nuova nota aperta da questa sessione; restano valide quelle
  della Sessione 3 (mappa "Sede Staccata - Cappuccini" da aggiungere).

---

## Sessione 4 — Correzione bug salvataggio + ricalibrazione completa mappa

### Bug critico risolto: errore 500 al salvataggio (IntegrityError)
Il modello `Aula` ha un vincolo `UNIQUE` sulla **sola colonna `classe`**
(non su `anno_scol + classe`). Diverse route cercavano/inserivano righe
filtrando per `anno_scol + classe`, causando `IntegrityError` ogni volta
che una classe aveva già una riga per un anno diverso da quello richiesto
(succedeva assegnando un'aula via mappa, via pagina classica "Elenco
aule", o con "copia assegnazioni da un anno all'altro").
**Fix applicato in 4 punti di `routes/aule.py`**: `salva()`,
`copia_anno()`, `rimuovi` (in `lista()`), `mappa_assegna()`,
`mappa_libera()` — tutti ora cercano/aggiornano per `classe` da sola,
indipendentemente dall'anno.

### Salvataggio mappa senza reload di pagina
Prima: dopo assegna/libera, `location.reload()` faceva ripartire dalla
prima sezione e perdeva lo scroll. Ora: `ricaricaDatiSenzaScroll()`
rilegge l'HTML in background via `fetch` e aggiorna solo gli elementi
dinamici (stato zone cliccabili, tabella riepilogativa, dropdown classi
libere), restando sulla scheda e posizione di scroll correnti.

### Ricalibrazione completa coordinate mappa (tutte le 38 aule)
Il metodo di calcolo "a occhio da screenshot" usato in precedenza si è
rivelato **sistematicamente impreciso** (spostamento verso
alto-sinistra). **Metodo definitivo adottato — marcatore mobile:**
1. Inietta un pallino verde temporaneo via JS a una % (x,y) candidata
2. Zoom del browser sulla zona, verifica visiva
3. Sposta il pallino finché non cade esattamente sul numero
4. Scrivi quel valore nel file coordinate

Questo metodo è **molto più affidabile** di qualsiasi calcolo a
ritroso da screenshot o griglia sovrapposta (provata anche una
sovrapposizione grid con percentuali — anch'essa meno precisa del
marcatore per via di piccoli errori di lettura pixel). **Da usare
sempre per future correzioni di coordinate.**

Risultato: tutte e 38 le aule ricontrollate e corrette dove necessario
(quasi tutte tranne Sede Staccata 27-32, già precise). File aggiornato:
`models/aula_mappa_coords.py`.

### Nota per il futuro
Se in uso reale emergono ancora zone cliccabili imprecise: usare SEMPRE
il metodo del marcatore mobile (vedi sopra), mai calcoli a mano da
screenshot — hanno già causato più giri di correzioni sbagliate.

---

## Sessione 3 — Piantina interattiva aule + rifiniture Assegnazioni

**Contesto:** dopo aver chiuso i 4 task iniziali (vedi Sessione 1), lavoro
proseguito su rifiniture della pagina Assegnazioni e su una nuova feature:
mappa interattiva delle aule.

### Rifiniture pagina Assegnazioni (`templates/assegnazioni/index.html`)
- Colonne classi ridotte al minimo per 2-3 cifre (26px → poi 34px per
  evitare a-capo del simbolo ▾)
- Corretto bug: `min-width:100%` sulla tabella causava stiramento delle
  colonne fisse (Docente/Tipo) quando una CC aveva poche classi — rimosso,
  sostituito con larghezza calcolata lato server e scritta come
  `style="width:...px"` diretto sulla tabella (causa: per specifica CSS,
  `width:auto`/`max-content` con `table-layout:fixed` si espande sempre
  al contenitore, non è un bug di cascata)
- Altezza righe docente ridotta da 44px a 26px (causa: padding globale
  ereditato `10px 14px` da uno stile generico dell'app, non nostro —
  aggiunto override compatto `padding:2px 3px`)
- Corretto colonna TIPO allineata a sinistra invece che centrata (mancava
  `text-align:center` sulla classe CSS `.td-tipo`)
- Corretto stesso problema sulla riga Copertura (frazioni "X/Y" non centrate)
- Allargata colonna Azioni (34px→40px) perché il pulsante "+" andava in
  overflow
- **Redesign dettaglio piano studi multi-materia**: da "una riga per
  classe aperta singolarmente" (con bug di disallineamento colonna POT
  mancante) a **un'unica riga condivisa per CC** che mostra tutte le
  classi multi-materia insieme, con espansione dinamica delle sole
  colonne coinvolte (34px→170px) via JS quando si apre il dettaglio

### Piantina interattiva aule (`/aule/mappa`)
Nuova pagina con piantina cliccabile del Corpo Centrale + Sede Staccata.

**Modello dati:**
- `models/aula_mappa_coords.py` — coordinate (percentuale x/y/w/h) di
  ogni aula, organizzate per **sezione** (una immagine per piano/edificio,
  fornita da Roberto già ritagliata dal DXF/CAD)
- 5 sezioni: Piano Terra, 1° Piano, Torretta (piano secondo), Sede
  Staccata, Sede Staccata - Sportivo — **38 aule totali calibrate**
- Immagini in `static/img/cc_piano_terra.jpg`, `cc_primo_piano.jpg`,
  `cc_secondo_piano.jpg`, `ss_sportivo.jpg`, `ss.jpg`

**Route:** `routes/aule.py`
- `GET /aule/mappa` — pagina con tab per sezione
- `POST /aule/mappa/assegna` — assegna/riassegna aula a una classe
- `POST /aule/mappa/libera` — rimuove assegnazione

**UI/UX:**
- Navigazione a schede (tab) tra le 5 sezioni
- Due modalità: **Visualizza** (sola lettura, hover automatico mostra
  classe assegnata senza click) e **Assegna** (click apre popup con
  dropdown per assegnare/cambiare/liberare la classe)
- Zone cliccabili **invisibili** (nessun riquadro/bordo colorato), solo
  cambio cursore — il numero è già stampato sull'immagine originale
- Tabella riepilogativa a destra (solo in modalità Visualizza): N° Aula
  / Classe / Sede, tutte le 38 aule ordinate numericamente

**Note tecniche importanti:**
- Le coordinate sono calibrate **a occhio con verifica visiva** (zoom
  pixel-per-pixel via browser + marcatore di prova spostato
  iterativamente), non un tracciamento vettoriale esatto delle pareti
  — il metodo del "marcatore mobile" si è dimostrato molto più
  affidabile del calcolo a ritroso da screenshot
- **Trasferimento immagini dal mio ambiente al Mac**: il metodo con
  base64 spezzato in più chiamate `write_file` in modalità `append` ha
  **corrotto ripetutamente** i file immagine (checksum MD5 diversi).
  Soluzione: trasferire in **un'unica chiamata** (senza append) e
  verificare sempre il checksum MD5 dopo la decodifica. Poi risolto
  definitivamente facendo generare i JPEG direttamente a Roberto sul
  Mac, evitando il trasferimento
- Se in futuro serve aggiungere/correggere una coordinata: usare il
  metodo del marcatore (vedi sopra), non calcolare a mano da screenshot

### Cose ancora aperte / possibili sviluppi futuri
- Piantina "Sede Staccata - Cappuccini": non ancora disponibile,
  aggiungere quando Roberto fornirà la mappa
- Eventuali aggiustamenti fini di coordinate se qualche aula risultasse
  ancora imprecisa in uso reale

---

## Sessione 2 — Task 4 export XLSX + colonne assegnazioni

(Vedi transcript completo per dettagli. Riassunto:)
- Aggiunta seconda griglia "Assegnazione per docente" sotto la griglia
  "Richiesta" nell'export P9, con calcolo automatico ore residue e
  segnalazione "SUPPLENTE"
- Corretto bordi/colori celle export XLSX
- Numerose correzioni di larghezza/allineamento colonne nella pagina
  Assegnazioni (vedi Sessione 3 per il seguito di questo lavoro)

---

## Sessione 1 — Setup iniziale e 4 task organico

**Contesto:** app Flask/SQLAlchemy per gestione organico IIS "Leonardo
da Vinci" di Chiavenna. Repo: `github.com/robertodaltoe/caronteApp`,
locale in `/Users/Roberto/CaronteApp`. Avvio: `python3 app.py` su
`localhost:5002`, bypass login dev: `CARONTE_SKIP_LOGIN=1`.

### Task 1 — Cattedre di potenziamento (hub Impostazione Anno, passo 6b)
Route CRUD + template `impostazione_anno/cattedre_potenziamento.html`,
basati sul modello già esistente `CattedraPotenziamento`.

### Task 2 — Colonna POT real-time in Assegnazioni
Aggiunta colonna POT alla tabella pivot assegnazioni, con aggiornamento
AJAX istantaneo. Risolti 5 bug di disallineamento tra riga Copertura,
Scheda classe, sub-righe multi-materia e docenti precaricati.

### Task 3 — Piano studi multi-materia (una riga per CC)
Risolto bug critico di eliminazione (form.submit() in loop → solo il
primo eseguito) con nuova route batch `piano_studi_elimina_multi`.
Ridisegnati i cestini (🗑 per materia singola + 🗑 fine riga per intera
CC) e risolto disallineamento visivo tra colonna Materia e colonne anno.

### Task 4 — Export XLSX Passo 9 (assegnazioni classi)
Riscritto da zero seguendo lo stile del file ufficiale
"ASSEGNAZIONI CLASSI 2026-27.xlsx": gruppi indirizzo colorati, blocchi
per classe di concorso, colonna POT, formula RICHIESTA, colonna titolari.
(Poi esteso in Sessione 2/3 con la griglia assegnazione per docente.)

### Convenzioni di lavoro consolidate
- Tutto il codice/UI di CaronteApp in italiano
- Modifiche chirurgiche, non riscritture generali; pixel-perfect nelle UI
- Niente monitoraggio nominale docenti nei report; dati studenti esclusi
  dai dashboard (privacy)
- Desktop Commander per file Mac; Claude-in-Chrome per verifiche visive
- Riferimenti normativi aggiornati (FSL non più PCTO, D.L. 127/2025)
