# CaronteApp — Diario di sviluppo

> File di log persistente delle sessioni di sviluppo con Claude.
> Va aggiornato alla fine di ogni sessione, aggiungendo una nuova voce
> in cima (ordine cronologico inverso). Non cancellare le voci precedenti.

## Sessione 66 addendum 22 — Riorganizzazione navbar/Impostazioni per il Piano Annuale (Cowork)

Roberto: il Generatore CdC e il Piano della Formazione non sono
funzioni da usare tutti i giorni (sono attività di *preparazione*
dell'anno), quindi via dal menu "Attività" — dove invece resta comodo
un link diretto alla vista di sola lettura del piano. Richiesta
precisa: "non lo terrei nel piano delle attività ma lo sposterei
nelle impostazioni nella sezione della preparazione del nuovo anno
scolastico e una pagina di collegamento per la visualizzazione in
calendario scolastico che si chiama Piano delle attività. Idem per
piano della formazione, via da navbar e inserimento della doppia voce
in impostazioni."

- `templates/base.html`: dal menu "Attività" tolti "Piano della
  Formazione" e "Generatore Consigli di classe"; aggiunto "Piano delle
  attività" che punta alla vista a schermo già esistente
  (`attivita_ist.piano_annuale`, gli export PDF/Excel restano
  raggiungibili da lì).
- `templates/impostazioni/index.html`: nella sezione "Anno
  scolastico" (quella con Hub impostazione anno, Docenti per anno,
  Classi attive, ecc. — esattamente la "sezione della preparazione
  del nuovo anno" richiesta), aggiunte le due voci "Genera piano delle
  attività" (→ `generatore_cdc.index`) e "Piano della formazione" (→
  `formazione.lista`).
- Rinominato il generatore da "Generatore Consigli di classe" a
  "Genera piano delle attività" ovunque compaia (titolo pagina, h1,
  4 link di ritorno nelle sotto-pagine vincoli/dipartimenti/eventi
  unici) — coerente col nuovo nome scelto da Roberto.

Nella stessa richiesta, due correzioni estetiche alla pagina
Impostazioni: tolto "— 9 passi" dall'etichetta "Hub impostazione
anno" (il numero cambia se si aggiungono passi, meglio non
promettere un conteggio); le caselle KPI in alto (Sezioni attive/CC
confermate/Docenti TI/Docenti attivi) erano centrate ma il centraggio
non veniva preciso a video — cambiate da `text-align:center` a
`text-align:left` in `.kpi` (CSS della pagina).

Verificato a video sul server con `database.db` reale (sola lettura):
menu Attività senza le due voci rimosse e con "Piano delle attività"
al loro posto, sezione Anno scolastico di Impostazioni con le due
nuove voci, titolo scheda browser del generatore aggiornato a "Genera
piano delle attività — IIS Da Vinci", KPI allineate a sinistra, "Hub
impostazione anno" senza il conteggio passi. Nessuna logica toccata,
solo template — 175/175 test passano invariati.

## Sessione 66 addendum 21 — Export Piano Annuale in Excel, stile identico al modello originale (Cowork)

Dopo l'export PDF, Roberto ha chiarito che il formato condivisibile
deve essere xlsx, non PDF, e ha fornito il file originale
(`BOZZA_PIANO_ATTIVITA_2026_27_CORRETTO.xlsx`, 13 fogli) con
l'istruzione di non cambiarne layout e stile. Analizzato il file con
openpyxl prima di scrivere codice: titolo/intestazione colorati
(fill `1F3864`/`2E5395`), colonna mese a sinistra ruotata 90° e unita
per tutta l'altezza del foglio, banner colorati per giorno (blu
`4472C4`), gruppi di attività multi-riga con intestazione propria
(grigio-blu `6C7A96`), riga singola per eventi unici come il Collegio
(rosa `EAD1DC`), festività a giorno singolo in rosso (`C00000`),
sospensioni multi-giorno/termine lezioni in verde (`375623`), font
"Open Sans" (stesso font già incorporato nei PDF di questa sessione),
colonna Ore con formula `=(F-E)*24`, foglio "Riepilogo ore" a parte
con Indirizzo/Classe/Ore Consigli/Ore Scrutini/Totale.

Prima di scrivere codice, due punti erano ambigui e sono stati
chiesti a Roberto invece di essere decisi da soli (regola
"segnalare, mai decidere" su cose non ovvie dai dati):
1. quali dei 13 fogli generare dai dati di CaronteApp — risposta:
   solo i fogli mese + Riepilogo ore (Introduzione/Piano della
   formazione/Dati_flat restano manuali o fuori scope);
2. come trattare il testo libero del foglio originale (agenda del
   Collegio, "ORDINE DEL GIORNO" dei Consigli) — non è un dato
   strutturato in CaronteApp — risposta: lasciare vuote quelle celle,
   da compilare a mano dopo l'export.

**Semplificazione dichiarata, non silenziosa**: il foglio originale
ha un'impaginazione in parte editoriale — es. la scritta "CONSIGLI DI
CLASSE — Classi prime" copre più giorni consecutivi come un titolo di
sezione scritto a mano, non derivabile meccanicamente dai singoli
eventi in `AttivitaIst`. L'export generato invece raggruppa in modo
puramente meccanico: un banner per ogni giorno con eventi, e sotto,
per ogni giorno, un sotto-titolo per ciascun gruppo di eventi con lo
stesso `tipo` (es. tutti i Consigli di classe di quel giorno) — stessi
colori e stessa gerarchia visiva del modello, ma senza il
raggruppamento pluri-giorno fatto a mano nell'originale. Roberto ne è
stato informato esplicitamente, non è un dettaglio nascosto.

**Implementazione**: nuovo `modules/export_piano_xlsx.py` (funzione
pura `genera_xlsx_piano_annuale(mesi, classi_ore, anno)`, nessun
accesso al DB — riceve gli stessi `mesi` già prodotti da
`_righe_piano_annuale()`, la stessa fonte unica usata da schermo e
PDF, coerente col principio "un solo posto per la stessa logica").
Nuova route `piano_annuale_xlsx()` in `routes/attivita_ist.py`:
oltre a passare `mesi`, calcola l'elenco ufficiale delle classi
dell'anno da `AssegnazioneClasse`/`AssegnazioneDocente` (non solo
dagli eventi già calendarizzati, così una classe senza ancora nessun
CdC/scrutinio compare comunque con 0 ore, non sparisce dal
riepilogo) e le ore per classe separate Consigli/Scrutini. Pulsante
"Esporta Excel" aggiunto accanto a "Esporta PDF" in
`templates/attivita_ist/piano_annuale.html`.

Verificato: 6 test nuovi in `tests/test_export_piano_xlsx.py` (unitari
sul modulo puro, oggetti-evento finti — un foglio per mese più
Riepilogo, riga singola con fill rosa per Collegio, sottogruppo
grigio-blu per eventi multipli stesso tipo/giorno, sospensione
multi-giorno verde vs singolo giorno rosso, banner termine lezioni,
righe del Riepilogo con le classi passate) + verifica end-to-end sul
`database.db` reale (sola lettura, server avviato come per il PDF):
export scaricato e riaperto con openpyxl, confermati fogli
`['settembre 2026', 'dicembre 2026', ..., 'Riepilogo ore']`, banner
"MARTEDÌ 1"/blu, "Collegio docenti"/rosa, sottogruppo "Formazione" e
"Consiglio di classe" (18/09 reale)/grigio-blu, colonna mese unita
verticalmente A3:A31, Riepilogo ore con 3 classi AFM/CAT reali e
relative ore. 175/175 test passano (169 + 6 nuovi).

## Sessione 66 addendum 20 — Vista Piano Annuale condivisibile + export PDF (Cowork)

Ultimo pezzo dell'estensione: "procedi, usa esattamente il modello che
ti ho fornito" — la vista `piano_annuale` doveva riprodurre fedelmente
il modello originale in foglio elettronico di Roberto: colonne
Attività/Indirizzo/Classe/Inizio/Fine/Ore/Categoria raggruppate per
giorno, con sospensioni delle lezioni e termine lezioni segnati nel
mezzo del calendario come nell'originale, non solo gli eventi.

**Modello dati** — `mesi` passa da `[(etichetta, {data: [eventi]})]` a
`[(etichetta, [(data, tipo_riga, contenuto)])]`, dove `tipo_riga` è
`'evento'`/`'sospensione'`/`'termine_lezioni'`: permette di intercalare
banner di calendario (sospensione in blu, termine lezioni in verde)
tra i giorni con eventi, nell'ordine cronologico esatto del foglio
originale. Estratto in un helper condiviso `_righe_piano_annuale(anno)`
in `routes/attivita_ist.py`, usato sia dalla vista a schermo sia dal
nuovo export PDF — stessa logica, una sola fonte (pattern "due
meccanismi paralleli" da evitare, vedi CLAUDE.md).

**Export PDF** (`/attivita-ist/piano-annuale/pdf`) — nuovo
`templates/attivita_ist/piano_annuale_print.html`, stesso schema font
embedded di `report/singolo_print.html` (WeasyPrint via
`HTML(string=...)`, niente `base_url` quindi font must essere
base64), A4 landscape. Fallback se WeasyPrint non è disponibile: nel
codice esistente di `routes/report.py` il fallback cattura solo
`ImportError`, ma in sandbox Linux WeasyPrint è installato mentre
mancano le librerie di sistema (pango/cairo) — l'errore reale è
`OSError: cannot load library 'libgobject-2.0-0'`, non
`ImportError`. Corretto nella mia nuova route con
`except (ImportError, OSError)`; segnalato (non toccato, fuori
scope) che `routes/report.py` ha la stessa lacuna nelle sue due route
PDF.

Verificato su dati reali con server avviato sul `database.db` vero
(sola lettura): colonne corrette per Settembre 2026 (Collegio +
Formazione), banner "Vacanze natalizie" in Dicembre 2026, banner
"Termine lezioni" 08/06/2027 in Giugno 2027, export PDF via fetch
diretto → 200, `application/pdf`, 22KB (WeasyPrint disponibile su
questo Mac). 4 test nuovi + 1 sistemato in
`tests/test_piano_annuale_riepilogo.py` per il nuovo formato a tuple.
169/169 test passano.

Con questo la vista condivisibile del Piano Annuale è completa e
l'intera epica "Piano Annuale delle Attività" (Fasi 0-4 più
l'estensione del generatore concordata con Roberto) è conclusa.

## Sessione 66 addendum 19 — Referenti dipartimento + Eventi unici (Cowork)

Roberto ha precisato due punti sui dipartimenti prima di passare alla
vista condivisibile: "i dipartimenti hanno tre momenti diversi da
impostare: riunione referenti di dipartimento (riservata solo ai
docenti incaricati di essere capidipartimento); riunione dipartimento;
riunioni per materie. Questa differenza pesa nel conteggio ore per i
capidipartimento." Più "mancherebbe la programmazione degli incontri
scuola-famiglia che sono o per tutti i docenti o solo per i
coordinatori (solo una riunione)."

**Riunione referenti (capidipartimento)** — terzo tipo in
`TIPI_DIPARTIMENTO`, ma con una fonte partecipanti diversa dalle altre
due: nuova `referenti_per_dipartimento()` (da `IncaricaDocente`, tipo
"Referente di dipartimento" — incarico già esistente in anagrafica,
riusato non reinventato) invece di `docenti_per_dipartimento()` (tutti
i docenti del dipartimento via `DocenteMateria`). La bozza segnala già
prima di confermare i dipartimenti senza nessun referente nominato per
l'anno (non blocca, ma è meglio saperlo subito) — verificato sul
reale: 8 degli 9 dipartimenti non hanno ancora un referente nominato
per il 2026-2027.

**Eventi unici** (nuova pagina, `/generatore-cdc/eventi-unici`) —
Collegio e Incontro scuola-famiglia coinvolgono tutto l'istituto
insieme, non tante unità da mettere in parallelo: creazione diretta,
niente bozza intermedia. Per l'Incontro scuola-famiglia, scelta
esplicita tra "tutti i docenti" e "solo i coordinatori di classe"
(nuova `coordinatori_di_classe()`, stesso principio — da
`IncaricaDocente` tipo "Coordinatore di classe", incarico già
esistente) — sempre una sola riunione, cambia solo chi vi partecipa.

Verificato: 5 test nuovi (`tests/test_generatore_cdc.py` — referenti
esclude i membri non capidipartimento, bozza segnala dipartimento
senza referente, Collegio include tutti, Incontro famiglie sia con
tutti sia solo coordinatori) + verifica a video sul reale (tutti e tre
i tipi dipartimento nel selettore, blocco partecipanti che compare/
sparisce scegliendo Incontro scuola-famiglia, avviso "nessun
referente" su 8/9 dipartimenti reali). Aggiunto anche l'import di
`CategoriaIncarico`/`TipoIncarico`/`IncaricaDocente` mancante in
`tests/conftest.py`. 166/166 test passano (161 + 5 nuovi).

Con questo, l'estensione del generatore concordata con Roberto è
completa: Consigli/Scrutini/GLO con motore, dipartimenti/materia/
referenti senza motore, eventi unici (Collegio/Incontro famiglie)
senza bozza. Resta l'ultimo pezzo: vista condivisibile con le
sospensioni.

## Sessione 66 addendum 18 — Riunioni dipartimento/materia: niente motore (Cowork)

Correzione di impostazione da Roberto prima ancora di iniziare a
scrivere codice: "i dipartimenti/materie non hanno bisogno di un
motore, devono solo essere piazzati in data, non serve verificare
sovrapposizioni perché i dipartimenti non hanno docenti in comune".
Giusto — la premessa sbagliata era mia (avevo previsto un "motore
gemello" con la stessa logica di parallelismo dei Consigli, quando
invece qui il problema non esiste affatto: dipartimenti diversi non
condividono mai docenti per costruzione, quindi non c'è nulla da
mettere in conflitto).

Nuova route `/generatore-cdc/dipartimenti`, deliberatamente SENZA
`modules/generatore_cdc.py::genera_bozza_cdc()`: si scelgono i
dipartimenti, una singola data/ora/durata, e vengono piazzati tutti lì
— anche in contemporanea, se serve, perché non c'è nulla da evitare.
Bozza comunque modificabile riga per riga prima di confermare (stesso
principio "mai un piano imposto" di tutto il resto del generatore).
Aggiunta `docenti_per_dipartimento()` (da `DocenteMateria`) solo per
popolare i partecipanti dell'evento creato, non per calcolare
conflitti — usata esattamente come `docenti_reali_per_classe()` viene
usata alla conferma dei Consigli, ma senza l'algoritmo a monte.

Verificato: 2 test nuovi (`tests/test_generatore_cdc.py` — bozza
piazza tutti i dipartimenti nello stesso slot senza alcuna verifica,
conferma crea eventi con partecipanti corretti da DocenteMateria) +
verifica a video sui 9 dipartimenti reali (incluso "— Non assegnato"),
tutti piazzati correttamente nello stesso slot. 161/161 test passano
(159 + 2 nuovi).

Prossimo passo: vista condivisibile con le sospensioni (ultimo pezzo
concordato).

## Sessione 66 addendum 17 — Generatore: turni multipli in un solo invio (Cowork)

Terzo pezzo dell'estensione concordata con Roberto: poter scegliere
quanti turni di riunioni predisporre (es. Consigli di ottobre e di
marzo) in un solo invio, invece di rigenerare a mano ogni volta.

Il form ora ha un blocco "Turni da generare" con un elenco di periodi
(Dal/Al) aggiungibili/rimovibili via JS (`+ Aggiungi turno`, parte già
con un turno pronto), le classi/orario/durata/DS restano condivisi tra
tutti i turni. Lato route: `genera_bozza_cdc()` gira una volta per
ogni turno con date valide, indipendentemente l'uno dall'altro (un
turno non "sa" dello slot occupato da un altro — sono periodi diversi
dell'anno, non in competizione per lo stesso spazio) — nessuna
modifica al motore stesso. La bozza risultante è una lista unica con
le righe di tutti i turni concatenate, taggate con l'indice/periodo
del turno; la colonna "Turno" in tabella compare solo se sono più di
uno, per non appesantire il caso comune.

Verificato: 2 test nuovi (`tests/test_generatore_cdc.py` — due turni
producono bozze indipendenti e correttamente taggate; un turno
aggiunto e poi rimosso lato client, quindi con indice mancante nel
form, non fa inciampare la route) + verifica a video end-to-end (2
turni × 39 classi reali = 78 righe, taggate correttamente "Turno 1
05/10–09/10/2026" / "Turno 2 08/03–12/03/2027"), scartata subito dopo,
mai sul reale. Aggiornati anche i 2 test esistenti che postavano i
vecchi nomi di campo `data_inizio`/`data_fine` (ora `data_inizio_0`/
`data_fine_0` + `n_turni`). 159/159 test passano (157 + 2 nuovi).

Prossimo passo scelto da Roberto: dipartimenti/materia (motore
gemello, raggruppamento per dipartimento), poi vista condivisibile
con le sospensioni.

## Sessione 66 addendum 16 — Generatore: aggiunto GLO (Cowork)

Roberto: "mettiamo anche GLO come selezione. Se imposto GLO però devo
selezionare le classi che fanno parte del turno". Aggiunto come terzo
tipo in `TIPI_GENERABILI` (45 min di default) — stesso form, stesso
selettore classi già usato per Consigli/Scrutini, nessuna differenza
di interfaccia.

Punto segnalato esplicitamente nel codice (non deciso in silenzio):
altrove nell'app `_preset_partecipanti()` tratta il GLO come "solo
manuale" — nessun preset automatico, perché la composizione reale
dipende dall'alunno seguito (sostegno + pochi curricolari), non
dall'intera classe. Qui invece, non avendo un dato più preciso da cui
partire, il generatore usa comunque l'insieme docenti dell'INTERA
classe come segnale di conflitto — una stima per eccesso: nessun
rischio di doppio impegno, ma potrebbe evitare sovrapposizioni non
realmente necessarie e proporre meno slot del possibile. I
partecipanti proposti restano comunque modificabili come sempre dalla
pagina presenze.

Verificato: 2 test nuovi (`tests/test_generatore_cdc.py` — GLO
richiede comunque le classi, conferma crea eventi tipo GLO) + verifica
a video che l'opzione compaia nel selettore. 157/157 test passano
(155 + 2 nuovi).

## Sessione 66 addendum 15 — Generatore: anche gli scrutini (Cowork)

Roberto ha proposto di estendere il generatore: turni multipli,
scrutini con la stessa regola dei Consigli, Collegio/dipartimenti/
materia nello stesso strumento, vista condivisibile con le
sospensioni. Discusso insieme prima di implementare (domanda
esplicita "sei d'accordo?"): confermato che scrutini si estendono
bene con lo stesso motore (stessa logica di preset/bucket di
`_preset_partecipanti` per `consiglio_classe`/`scrutinio`), i
dipartimenti/materia richiedono un raggruppamento per dipartimento
invece che per classe (motore gemello, non un'opzione in più), e il
Collegio docenti non si adatta allo schema (coinvolge tutti insieme,
niente da mettere in parallelo) — va tenuto fuori dall'algoritmo.
Roberto ha scelto di partire dagli scrutini, il resto in seguito.

Aggiunto un selettore "Tipo di riunione" (Consiglio di classe /
Scrutinio) in cima al form del generatore, con durata di default
diversa (60 min / 45 min, aggiornata via JS alla scelta) — la logica
di raggruppamento (`genera_bozza_cdc`) resta identica, non sapeva né
sa nulla del tipo: il tipo entra in gioco solo nella conferma finale,
per il campo `AttivitaIst.tipo` e il titolo dell'evento.

Verificato: 3 test nuovi (`tests/test_generatore_cdc.py` — genera con
tipo scrutinio produce bozza corretta, conferma crea eventi con
tipo/titolo giusti) + verifica a video che la durata si aggiorni da
sola cambiando il tipo. 155/155 test passano (153 + 3, uno in più del
previsto perché il test dell'addendum 14 era già conteggiato).

Prossimo passo scelto da Roberto: turni multipli nello stesso invio,
poi dipartimenti/materia, poi vista condivisibile con le sospensioni.

## Sessione 66 addendum 14 — Generatore CdC: anno di default sbagliato (Cowork)

Roberto: "se seleziono la pagina non ho modo di selezionare l'anno
2026-2027. considera che la generazione del piano delle attività è
un'attività preparatoria per il nuovo anno scolastico come
assegnazioni e richiesta organico". Bug reale: `routes/generatore_cdc.py`
usava `_anno_scolastico()` (calcolato dalla data odierna — oggi
2025-2026, il cambio scatta a settembre) invece di
`_anno_default_piano()` (l'anno con dati reali nel piano studi/calcolo
organico, la stessa fonte già usata da Formazione e Piano Annuale in
questa sessione) — e non c'era nemmeno un selettore anno a pillole per
correggerlo a mano, a differenza di ogni altra pagina anno-scoped
dell'app.

Corretto in `index()` e `vincoli_manuali()`: default a
`_anno_default_piano()`, aggiunto il selettore a pillole standard
(nascosto se c'è un solo anno con Assegnazioni, come nelle altre
pagine — oggi il caso reale, esiste solo il 2026-2027). Aggiunta
`_anni_disponibili_assegnazioni()` per calcolare l'elenco dagli anni
con Assegnazioni già inserite.

Verificato: 1 test nuovo che blocca il comportamento (pagina aperta
senza `?anno=` esplicito deve mostrare l'anno con dati nel piano
studi, non quello odierno) + verifica a video sul reale — la pagina
ora si apre di default su "a.s. 2026-2027" su entrambe le pagine.
153/153 test passano (152 + 1 nuovo).

## Sessione 66 addendum 13 — Fase 3: Generatore Consigli di Classe (Cowork)

Fase 3 del project plan approvato — la parte più impegnativa: bozza
automatica di calendarizzazione Consigli di classe, con tutti i
vincoli decisi durante l'analisi iniziale.

**Modelli nuovi** (`models/generatore_cdc.py`):
- `VincoloOrarioClasse` — finestre settimanali fisse non libere da
  lezione (es. martedì 13:30-15:30 rientro pomeridiano CAT/AFM/ROM),
  per indirizzo + range anni di corso opzionale. Non legate a un anno
  scolastico, restano valide finché non cambia l'orario reale.
- `VincoloGeneratoreCdc` — vincoli manuali per classe, impostabili
  PRIMA di generare: `entro_data` (scadenza) o `fissa` (slot esatto).
- `AttivitaIst.richiede_ds` (nuova colonna, migrazione additiva in
  `_auto_migrate`) — presenza del Dirigente Scolastico come vincolo
  forte di sovrapposizione.

**Motore** (`modules/generatore_cdc.py::genera_bozza_cdc`) — algoritmo
greedy, non scrive nulla sul DB, ritorna solo la proposta:
1. Docenti per classe dalle Assegnazioni (`docenti_reali_per_classe`),
   non dall'orario — placeholder esclusi (nessun insieme docenti noto
   finché non nominati).
2. Griglia di slot dal periodo scelto, esclusi i giorni coperti da
   `SospensioneDidattica` e le domeniche.
3. Classi ordinate per vincolo fisso prima, poi per numero di slot
   validi crescente (euristica CSP: le più vincolate vanno piazzate
   per prime), poi per scadenza più vicina.
4. Per ogni classe: preferisce impacchettare nello stesso slot già
   usato da altre classi compatibili — l'obiettivo primario è la
   massima classi-in-parallelo, non semplicemente "libero" — con
   preferenza secondaria per lo stesso indirizzo tra le opzioni
   ugualmente valide (bug trovato e corretto in fase di test: la prima
   versione preferiva slot vuoti a slot occupati da indirizzo diverso,
   il contrario di quello che serviva).
5. DS: due classi che lo richiedono non vanno mai nello stesso slot,
   anche senza docenti condivisi.
6. Classi senza slot valido restano "in conflitto" (data/ora vuote),
   da piazzare a mano nella bozza — mai un errore bloccante.

**Route** (`routes/generatore_cdc.py`, blueprint proprio): pagina di
generazione (selezione classi da Assegnazioni, periodo, orario
giornaliero, durata, classi che richiedono DS) → bozza modificabile
riga per riga (data/ora/DS editabili anche per le righe in conflitto)
→ conferma crea gli `AttivitaIst` reali con partecipanti già popolati
dalle Assegnazioni. Più due pagine CRUD per i vincoli. Nuova voce
"Generatore Consigli di classe" in Attività, permessi riusati dalla
sezione `attivita_istituzionali`.

Verificato: 13 test sul motore puro (`tests/test_generatore_cdc.py` —
parallelo senza docenti comuni, separazione con docenti comuni,
vincoli orario per indirizzo/anno, scadenze, slot fissi in conflitto,
DS, preferenza stesso indirizzo, giorni lavorativi, query reale dalle
Assegnazioni). End-to-end su copia del DB: generate 39 classi reali
(dalle Assegnazioni 2026-2027) su una settimana, **zero conflitti**,
impacchettate in 19 slot, confermate e verificate le
`AttivitaIstPartecipante` create correttamente per ognuna — poi
scartata, mai sul reale. Aggiunti sul database reale i due vincoli
orario veri segnalati da Roberto durante l'analisi (martedì
13:30-15:30 CAT/AFM/ROM, martedì 12:30-13:30 3ª-4ª LLI) tramite
l'interfaccia stessa, con backup cifrato successivo
(`database_20260820_2054_post_generatore_cdc_vincoli.db.enc`),
`PRAGMA integrity_check` ok. 152/152 test passano (139 + 13 nuovi).

Con questo, tutte e 5 le fasi del Piano Annuale delle Attività
concordate nell'analisi iniziale sono implementate (0. Calendario,
1. Formazione, 2. Vista+Riepilogo, 3. Generatore CdC). Resta la Fase 4
(Pubblicazione PDF) — non ancora affrontata.

## Sessione 66 addendum 12 — Import Consigli settembre + formazione obbligatoria sui placeholder (Cowork)

Per dare al riepilogo dati veri da mostrare (finora 0 Consigli di
classe per il 2026-2027), importati i 10 Consigli di classe prime già
presenti nel foglio "settembre I" (venerdì 18/09/2026, 1h ciascuno).
Rilette due righe ambigue del foglio via nuovo tab del browser (il
tab precedente aveva smesso di comporre gli screenshot — problema
del pannello, non del foglio): "CAT 1A" e "LLI 1B" comparivano due
volte con solo l'orario diverso. Segnalato a Roberto invece di
assumere, confermato che sono in realtà l'altra sezione (1B CAT e 1A
LLI) scritta per errore nella bozza, non una doppia sessione.

Backfill dei partecipanti per questi 10 eventi usando le Assegnazioni
reali già esistenti per l'anno (47 partecipanti aggiunti) — necessario
perché creati via script diretto, non tramite la route che lo avrebbe
fatto da sola.

Seconda richiesta di Roberto: ai placeholder nel riepilogo andrebbero
assegnate anche le ore di Formazione obbligatoria (bucket A), non solo
i Consigli di classe (bucket B) — la formazione obbligatoria vale per
chiunque sia in servizio, a prescindere da chi occuperà poi il posto.
Aggiunto in `riepilogo_ore()`: somma delle ore dei corsi Formazione
con `obbligatorio_tutti=True` per l'anno, calcolata una sola volta
(stesso valore per ogni placeholder, non dipende dalle sue classi) e
sommata a `ore_a`. La riga placeholder ora compare anche con sole ore
di bucket A, senza bisogno di classi assegnate.

Verificato: entrambe le importazioni su copia prima, backup cifrato
(`database_20260820_2029_pre_import_cdc_settembre.db.enc`) e poi sul
reale, `PRAGMA integrity_check` ok. 2 test nuovi
(`tests/test_piano_annuale_riepilogo.py`). Confermato a video: 22
placeholder reali in elenco, tutti con 0.5h di Formazione obbligatoria,
alcuni anche con ore di bucket B dai Consigli appena importati (es.
"SUPPLENTE 1 — AS48": 0.5h / 3.0h). 139/139 test passano (138 + 1
netto, un test di conferma live-update dell'addendum 11 già contava).

## Sessione 66 addendum 11 — Conferma aggiornamento live placeholder (Cowork)

Roberto: "e se inserisco un nuovo placeholder si aggiorna l'elenco?"
Sì per costruzione — `riepilogo_ore()` non ha nessuna cache, rilegge
`AssegnazioneDocente` a ogni richiesta. Aggiunto un test dedicato che
lo blocca esplicitamente (carica la pagina, crea un placeholder DOPO,
ricarica, verifica che compaia) invece di lasciarlo solo implicito nel
comportamento della route — utile soprattutto se in futuro qualcuno
aggiungesse una cache qui senza pensare a invalidarla. 138/138 test
passano (137 + 1 nuovo).

## Sessione 66 addendum 10 — Placeholder supplenti nel Riepilogo ore (Cowork)

Richiesta di Roberto: nel Riepilogo ore per docente, vedere anche i
placeholder di Assegnazioni ancora da nominare ("Supplente 1", "da
assegnare internamente"...), etichettati come "NomePlaceholder — codice
CC" (es. "SUPPLENTE 1 — AS48"), che spariscono da soli quando il
supplente viene nominato.

Implementato in `riepilogo_ore()`: per ogni `AssegnazioneDocente` con
`id_docente IS NULL` e `nome_placeholder` valorizzato per l'anno
mostrato, somma le ore di bucket B (solo Consigli di classe — gli
scrutini sono BUCKET_NO, fuori conteggio, esclusi di proposito) per le
classi già assegnate (`AssegnazioneClasse.label_classe`, stesso
formato di `AttivitaIst.classe`, riusato senza conversioni). Righe
mostrate solo se ci sono ore reali da mostrare (niente righe vuote per
placeholder senza eventi ancora programmati sulle loro classi). Bucket
A e quota non hanno senso per un placeholder (non è un docente con
ore di contratto note): colonna A mostrata come "—", niente confronto
eccedenza.

La sparizione automatica dopo la nomina non ha richiesto nuovo codice:
`routes/assegnazioni.py::nomina()` già azzera `nome_placeholder` (la
query dei placeholder smette di trovarlo) e già chiama
`iscrivi_docente_a_eventi_classe()` (addendum 4) che crea gli
`AttivitaIstPartecipante` reali — le stesse ore ricompaiono
automaticamente sotto il nome del docente vero, stesso principio già
descritto da Roberto ("si aggiornano in automatico").

Verificato: 3 test nuovi (`tests/test_piano_annuale_riepilogo.py`) —
placeholder con ore da Consigli di classe, esclusione degli scrutini,
sparizione dopo nomina. Verificato anche su copia del database.db
reale con un evento di prova (rimosso subito dopo, mai nel DB reale):
"SUPPLENTE 1 — AS48" compare con "da nominare" e le ore corrette.
137/137 test passano (134 + 3 nuovi).

## Sessione 66 addendum 9 — Stesso bug anche nel Riepilogo ore (Cowork)

Seguito diretto dell'addendum 8: Roberto ha rifatto la verifica e
trovato lo stesso problema in `riepilogo_ore()`, non nelle tendine
stavolta ma nel report — 83 docenti mostrati per il 2026-2027 contro
i ~57 realmente in servizio quell'anno (93 attivi totali, 34 con
`anno_scol_uscita<=2026-2027`).

Causa diversa dall'addendum precedente: qui il problema non è una
tendina che propone nuove selezioni, ma il fatto che le righe
`AttivitaIstPartecipante` di un evento già esistente (es. "Collegio
dei docenti — settembre 2026") non si aggiornano da sole quando
l'uscita di un docente viene segnalata DOPO che è già stato convocato
— pattern "campi congelati alla creazione" già documentato in
CLAUDE.md. Il report leggeva quelle righe così com'erano, senza
rivalidare lo stato di servizio dei docenti al momento della lettura.

Fix scelto deliberatamente **read-only**: `riepilogo_ore()` ora
esclude dal report chi non è in servizio per l'anno mostrato
(`_non_in_servizio_per_data`), senza toccare/cancellare le righe
`AttivitaIstPartecipante` esistenti — un conto è correggere cosa si
*mostra* nel riepilogo, un altro è decidere se quell'evento già
svolto/pianificato debba davvero perdere quel partecipante (dato
storico, potenzialmente voluto). Nessuna scrittura sul DB per questo
fix.

Verificato: 1 test nuovo in `tests/test_piano_annuale_riepilogo.py`
(docente con partecipazione registrata PRIMA dell'uscita, verificato
che sparisca dal riepilogo dell'anno in cui non è più in servizio).
Confermato sul database.db reale: righe da 83 a 57, ALAIMO Giuseppe
non più presente. 134/134 test passano (133 + 1 nuovo).

## Sessione 66 addendum 8 — Docenti fuori servizio comparivano nelle tendine (Cowork)

Roberto: "verifica la correttezza del richiamo dei docenti in funzione
dell'a.s. selezionato. in 2026-2027 compaiono anche i docenti che sono
già stati indicati fuori servizio". Confermato sul DB reale: molti
docenti hanno `anno_scol_uscita='2026-2027'` (fine_td, pensionamento,
trasferimento — segnalati dal passo 7) ma restano `attivo=True` fino a
fine dell'anno corrente (2025-2026), come corretto — il bug era che
tre tendine di selezione manuale filtravano solo per `attivo=True`,
ignorando `anno_scol_uscita`, mentre il preset automatico
(`_preset_partecipanti`, via `_non_in_servizio_per_data` /
`_docenti_non_in_servizio` di routes/docenti.py) lo gestiva già
correttamente da tempo — stesso pattern di bug ricorrente già
documentato in CLAUDE.md (fix analogo già fatto 3 volte per altri
punti: recupero agosto/giugno, attivita_ist, incarichi.py), qui
ripresentatosi in punti non ancora coperti.

Tre punti corretti, tutti con lo stesso principio — escludere chi non
è in servizio alla data di riferimento MA senza mai far sparire un
docente già selezionato/convocato in precedenza (solo evitare di
proporne di nuovi):
- `routes/formazione.py::form()` — tendina "iscrivi un docente":
  nuova lista `docenti_selezionabili` (filtrata) accanto a `docenti`
  (completa, invariata, usata per l'elenco "già iscritto" così un
  docente iscritto prima di uscire resta visibile).
- `routes/attivita_ist.py::form()` — checkbox partecipanti: filtrata
  la stessa `docenti` ma con eccezione esplicita per chi è già
  preset/selezionato (`gia_coinvolti`).
- `routes/attivita_ist.py::presenze()` — tendina "+ Aggiungi docente":
  `docenti_extra` ora filtrata con `non_in_servizio_ids`, già calcolata
  lì per un altro scopo (segnalare i convocati usciti) — bug proprio
  accanto al codice che already gestiva correttamente l'avviso.

Verificato: 5 test nuovi (`tests/test_esclusione_non_in_servizio_form.py`)
con lo stesso approccio "monkeypatch di render_template" già usato per
Fase 2 (il fixture app leggero non ha il template_folder reale).
Aggiunto anche l'import di `PianoAttivitaPersonale`/`PianoAttivitaPersonaleVoce`
mancante in `tests/conftest.py` (serviva a `_preset_partecipanti()`).
Verificato anche sul database.db reale: ALAIMO Giuseppe (uscita
2026-2027) non compare più né nella tendina Formazione né nei checkbox
di un nuovo evento del 2026-2027. 133/133 test passano (128 + 5 nuovi).

Non toccati in questo giro (stesso bug, ma non ancora segnalato/
verificato): righe 907/945/1025 di routes/attivita_ist.py (roster
docenti-materie, sostituzione scrutinio) — usano lo stesso
`Docente.query.filter_by(attivo=True)` senza filtro anno. Da
sistemare se/quando emerge un caso concreto, invece di un'estensione
preventiva non richiesta.

## Sessione 66 addendum 7 — Stesso bug di overflow tabella su /attivita-ist (Cowork)

Roberto ha segnalato che anche `templates/attivita_ist/lista.html`
(la pagina principale di Attività istituzionali, non toccata
nell'addendum 5) aveva lo stesso problema: tabella 1663px dentro un
contenitore da 1240px, `overflow-x` non gestito → colonne
Bucket/N.doc/Azioni irraggiungibili, confermato via JS prima del fix
esattamente come nell'addendum 5. Preesistente, non introdotto in
questa sessione.

Stesso fix: `overflow-x:auto` + `table-layout:fixed` nel macro
condiviso `tabella_eventi()` (usato sia per gli eventi futuri sia per
quelli già svolti), con `white-space:normal` sulla colonna Titolo per
i titoli lunghi. Le colonne Data/Tipo/Bucket/Doc. avevano bisogno di
qualche px in più (con `table-layout:fixed` un contenuto più largo
della colonna viene tagliato silenziosamente, non si allarga più da
solo come con `auto`) e l'etichetta "N. doc." è stata accorciata a
"Doc." per stare nella larghezza assegnata. Verificato via JS che la
tabella combacia esattamente col contenitore. Nessuna modifica alla
logica, solo al template — 128/128 test invariati.

Dato che questo pattern (tabella larga + `.card` senza scroll interno)
si è ripetuto due volte in pagine diverse, vale la pena, se emergono
altre segnalazioni simili, controllare anche le altre pagine con
tabelle non ancora passate in rassegna in questa sessione (es.
`dipartimenti.html`, `presenze.html`) invece di aspettare che si
ripresentino una per una.

## Sessione 66 addendum 6 — Fase 2: Vista Piano Annuale + Riepilogo ore (Cowork)

Fase 2 del project plan approvato: due nuove pagine di sola lettura in
`routes/attivita_ist.py`, stesso ruolo dei fogli "mensili" e "Riepilogo
ore" del piano cartaceo, ma calcolate dai dati già in app.

- **`/attivita-ist/piano-annuale`**: vista mensile di `AttivitaIst`
  raggruppata per giorno, con intestazioni di sezione. L'ordinamento
  cronologico degli eventi (già settembre→agosto per costruzione, un
  anno scolastico è già in ordine di data) basta a raggruppare i mesi
  nell'ordine giusto senza bisogno di riordinarli a mano — nessuna
  lista `MESI_IT` da re-ordinare, solo raggruppamento consecutivo.
  Riusa `modules/prospetto_supplenze.py::MESI_IT` per le etichette
  invece di affidarsi a `strftime('%B')` (dipendente dal locale di
  sistema, con fallback a catena già visto fallire in `app.py`).
- **`/attivita-ist/riepilogo-ore`**: due report — ore per classe
  (Consigli + Scrutini, da `AttivitaIst.durata_ore`) e ore per docente
  su Collegio/Consigli/Formazione confrontate col bucket A/B, che riusa
  **`quota_ore_bucket()`** già scritta per il Piano Attività Personale
  (Sessione 57) invece di un calcolo di quota parallelo — funziona
  automaticamente sia per cattedra piena (40h) sia proporzionale
  (cattedra incompleta), nessuna logica duplicata. Un'eccedenza è solo
  segnalata (badge rosso "eccede"), non blocca nulla.

Tenuto a mente il bug di stile appena corretto (addendum 5): entrambe
le tabelle usano da subito `overflow-x:auto` + `table-layout:fixed`
dentro `.card`, verificato via JS (`getBoundingClientRect`) che
nessuna delle due eccede il contenitore anche coi titoli di corso più
lunghi già in produzione.

Verificato: 6 test nuovi (`tests/test_piano_annuale_riepilogo.py`) —
raggruppamento mese/giorno, somma ore per classe, confronto bucket con
e senza eccedenza, docente senza eventi che non compare. Il fixture
`app` leggero dei test non ha il template_folder reale né i context
processor dell'app (stesso limite già noto, vedi
`test_piano_attivita_personale.py`): monkeypatch di `render_template`
per catturare i dati calcolati dalla route invece di renderizzare
l'HTML, così i test verificano la logica anche senza i template reali.
Aggiunto anche l'import di `ConfigApp` mancante in `tests/conftest.py`
(serviva a `quota_ore_bucket()`). Verificato a video sul server con
CARONTE_SKIP_LOGIN, solo lettura, contro il database.db reale (già
popolato dal Collegio e dai 12 corsi Formazione importati). 128/128
test passano (122 + 6 nuovi).

Prossimo passo: Fase 3 (Generatore Consigli di Classe).

## Sessione 66 addendum 5 — Fix stile tabella Piano della Formazione (Cowork)

Roberto: "la tabella non segue per niente lo standard dell'app". Due
problemi distinti, trovati confrontando con `templates/utenti/lista.html`
e `templates/attivita_ist/piano_personale_lista.html`:

1. La tabella non era dentro un `<div class="card">` — mancavano
   sfondo/bordi arrotondati/ombra standard, e il badge "obbligatorio"
   era un pill fatto a mano invece della classe `.badge` già in uso
   ovunque nell'app.
2. Più serio: la tabella (7 colonne, titoli di corso reali fino a ~150
   caratteri, es. "Indicazioni operative didattiche d'Istituto
   (prassi); Relazioni e funzionamento della segreteria; Buone prassi
   procedurali e scadenze didattiche") si allargava a 1836px dentro un
   contenitore di 772-1240px. Il CSS globale (`.card{overflow:hidden}`)
   NON mostra una scrollbar in questo caso — taglia via in silenzio le
   colonne Modalità/Periodo/Iscritti/Azioni, rendendo i pulsanti
   modifica/elimina letteralmente irraggiungibili. Confermato via
   JS (`getBoundingClientRect`) prima e dopo il fix, non solo a
   schermata.

Fix: adottato lo stesso pattern già usato per tabelle con contenuto
lungo altrove (`piano_personale_lista.html`) —
`<div class="card"><div style="overflow-x:auto;"><table
style="table-layout:fixed; min-width:920px;">`, con `white-space:normal;
word-wrap:break-word` sulle colonne di testo libero (Titolo, Tipologia)
così il contenuto va a capo nella colonna invece di forzarne
l'allargamento. Verificato: tabella ora esattamente larga quanto il
contenitore (1240px = 1240px), nessun taglio, tutte le azioni
raggiungibili. 6/6 test di `test_formazione.py` invariati (nessuna
logica toccata, solo template).

## Sessione 66 addendum 4 — Iscrizione automatica anche per classe/dipartimento (Cowork)

Seguito diretto dell'addendum 3: Roberto ha chiesto se, assegnando una
classe a un docente, questo verrebbe iscritto anche a Consigli di
classe/dipartimenti/riunioni materia/GLO già creati. Risposta iniziale:
no, e lì il motivo non era "manca l'aggancio" ma che
`_preset_partecipanti()` per questi tipi guarda l'**orario**
(`OrarioDocente.classe`/`DocenteMateria`), non le Assegnazioni — un
aggancio alle Assegnazioni non avrebbe comunque coinciso con la fonte
dati usata dal preset. Roberto ha fatto notare, correttamente, che le
Assegnazioni SONO già il segnale giusto ("quando assegno, non cambio
l'assegnazione classe") — non serve che l'aggancio replichi la stessa
fonte dati di `_preset_partecipanti()` (che ha un compito diverso: dare
la lista più aggiornata vicino alla data dell'evento), può benissimo
usare le Assegnazioni come proprio segnale indipendente.

Aggiunte due funzioni in `routes/attivita_ist.py`, con un nucleo comune
`_iscrivi_docente_a_eventi()` condiviso anche da
`iscrivi_docente_a_obbligatori()` (rifattorizzata sullo stesso helper):
- `iscrivi_docente_a_eventi_classe(id_docente, classi_label)` — Consigli
  di classe/scrutini futuri per le classi indicate. Note:
  `AssegnazioneClasse.label_classe` produce già lo stesso formato di
  `AttivitaIst.classe`/`OrarioDocente.classe` (es. "3A LLI"), nessuna
  conversione necessaria.
- `iscrivi_docente_a_eventi_dipartimento(id_docente, id_dipartimento)` —
  dipartimenti/riunioni materia/riunioni referenti futuri per quel
  dipartimento.

Agganciate in `routes/assegnazioni.py` in tutti e 3 i punti dove un
docente reale si lega a una classe: `salva()` (form assegnazione),
`aggiorna_ore()` (endpoint AJAX della griglia interattiva — il percorso
usato davvero dall'interfaccia), `nomina()` (placeholder → docente
reale). Il lato dipartimenti è agganciato dentro `_sync_docente_materie()`
stessa (già chiamata da tutti e 3 i punti), non serve ripeterlo.

GLO resta l'unico caso davvero irriducibile: il suo preset è sempre
vuoto e manuale (dipende dall'alunno seguito, non dalla classe/
dipartimento) — non esiste alcun dato di assegnazione da cui derivarlo,
spiegato a Roberto invece di forzare una soluzione.

Verificato: 8 test nuovi (`tests/test_iscrizione_automatica_assegnazione.py`,
sia sulle funzioni isolate sia sulle route reali `/assegnazioni/salva`
e `/assegnazioni/<id>/nomina` con blueprint registrato su un'app di
test), più import dei modelli mancanti (`AssegnazioneDocente`,
`AssegnazioneClasse`, `PianoStudi`) in `tests/conftest.py`. Smoke test
di `/assegnazioni`, `/attivita-ist`, `/docenti` su copia del
database.db reale (nessun evento futuro di questi tipi esiste ancora
in produzione, quindi nessun comportamento visibile da verificare lì
oltre all'assenza di errori). 122/122 test passano (114 + 8 nuovi).

## Sessione 66 addendum 3 — Iscrizione automatica docente a eventi obbligatori (Cowork)

Roberto: "quando aggiungerò un nuovo docente, quello verrà inserito in
automatico [negli eventi obbligatori]? sarà lo stesso in ogni altra
attività del piano annuale?" Risposta verificata nel codice: no, non
era automatico da nessuna parte — il preset partecipanti
(`_preset_partecipanti`) viene calcolato solo alla creazione/modifica
di un evento, mai ricalcolato quando cambia l'anagrafica docenti.
Confermato con Roberto di chiudere il buco.

Nuova funzione `routes/attivita_ist.py::iscrivi_docente_a_obbligatori()`,
chiamata dopo il commit sia in `routes/docenti.py::nuovo()` sia in
`riattiva()`. Copre solo i tipi il cui preset è "tutti i docenti attivi"
senza scelta — Collegio, incontri scuola-famiglia, 'altro' — più i
corsi di Formazione con `obbligatorio_tutti=True` (i corsi volontari
restano esclusi, l'iscrizione lì è sempre una scelta). Esclude
esplicitamente Consigli di classe/dipartimenti/riunioni materia/GLO:
dipendono da orario/assegnazioni che un docente appena creato non ha
ancora, non c'è nulla di corretto da preimpostare lì — limite noto,
non affrontato (serve un lavoro diverso, non generalizzabile a "tutti
i docenti").

Verificato: 7 test di unità (`tests/test_iscrizione_automatica_docente.py`,
copertura di tutti i confini — evento futuro/passato, tipo scoped
escluso, corso obbligatorio/volontario, nessuna doppia iscrizione) +
verifica end-to-end su copia del DB con Flask test client attraverso
la route reale `/docenti/nuovo` (non solo la funzione isolata),
`PRAGMA integrity_check` ok. 114/114 test passano (107 + 7 nuovi).

## Sessione 66 addendum 2 — Selettore anno + import Piano formazione reale (Cowork)

Due richieste di Roberto dopo aver visto la Fase 1: 1) il filtro anno a
testo libero in `/formazione` era scomodo, sostituito con le pillole
anno standard già usate altrove (`anni_disponibili`, stesso pattern di
`piano_personale`/`attivita_ist.dipartimenti`) — nascoste se c'è un
solo anno con dati, come nelle altre pagine. 2) importare i corsi veri
dal foglio "Piano della formazione" di BOZZA_PIANO_ATTIVITA_2026_27.xlsx
che Roberto aveva già confermato corretti in fase di analisi.

Rileggendo il foglio: 12 corsi, ma con due problemi che il modello
Fase 1 non copriva silenziosamente — segnalati e decisi insieme prima
di importare (non assunti in autonomia):
- Le date "Dal–Al" sono placeholder letterali (`[dal]-[al]`), mai
  compilate — confermato anche dal foglio mensile "settembre I", che
  si dichiara esso stesso "PROPOSTA... Date/orari da confermare in
  Collegio Docenti". Deciso con Roberto: data provvisoria unica
  (15/09/2026) per tutti e 12, segnata esplicitamente in nota, da
  correggere quando il Collegio le fissa.
- I destinatari nel foglio sono quasi sempre gruppi mirati ("Neo
  immessi in ruolo", "primo biennio", "max N posti su iscrizione QO"),
  non "tutti" o "chi si iscrive liberamente" come gestisce oggi il
  flag `obbligatorio_tutti`. Deciso con Roberto: solo "Indicazioni
  sicurezza Istituto" (l'unico segnato "obbligatorio"/"Tutti" nel
  foglio) importato come corso obbligatorio con iscrizione automatica
  di tutti i docenti in servizio (57 su 93 attivi, esclusi per
  `_non_in_servizio_per_data`); gli altri 11 importati come volontari,
  col criterio di destinazione originale del foglio riportato in nota
  (nessuna targeting automatica per sottogruppo — limite noto, non
  affrontato in questa fase).

Script di import verificato su copia del DB, poi backup cifrato
(`database_20260820_1717_pre_import_piano_formazione.db.enc`) e
applicato al reale, `PRAGMA integrity_check` ok, 107/107 test passano,
verificato visivamente nel browser (badge "obbligatorio" solo sul
corso giusto, note con destinatari/data provvisoria leggibili).

## Sessione 66 addendum — Fase 1: Piano della Formazione (Cowork)

Nuovo modello `models/formazione.py::CorsoFormazione` + blueprint
`routes/formazione.py` (`/formazione`), come da Fase 1 del piano
approvato. Scelta di design: niente tabella "iscrizioni" separata —
ogni corso ha un `id_attivita` collegato a un `AttivitaIst`
(`tipo='formazione'`, bucket A) creato/aggiornato insieme al corso, e
le iscrizioni sono le stesse righe `AttivitaIstPartecipante` di
quell'evento (`preset=True` per i corsi obbligatori per tutti,
`preset=False` per le iscrizioni volontarie) — riusa integralmente il
meccanismo bucket/presenze/Piano Attività Personale già esistente per
gli altri eventi istituzionali, invece di un conteggio ore parallelo
da mantenere allineato a mano (pattern "due meccanismi paralleli"
esplicitamente da evitare, vedi CLAUDE.md).

Corso obbligatorio → alla creazione aggiunge automaticamente tutti i
docenti in servizio (riusa `_non_in_servizio_per_data()` di
`routes/attivita_ist.py`, stessa esclusione già in uso per gli altri
eventi). Corso volontario → nessun partecipante iniziale, iscrizione/
disiscrizione singola da pagina di modifica corso. Pagina di gestione
raggiungibile da Attività → Piano della Formazione (permesso riusato:
stessa sezione `attivita_istituzionali`, nessuna nuova voce nella
matrice permessi).

Verificato: su copia del DB con Flask test client (creazione corso
obbligatorio/volontario, iscrizione/disiscrizione, modifica, eliminazione
con cascade dell'evento collegato), poi visivamente nel browser (lista
vuota, form nuovo corso, voce in navbar) col server puntato sul
database.db reale ma solo in lettura (nessun submit, verificato dopo
che `corsi_formazione` restava a 0 righe). Aggiunti 6 test di
regressione (`tests/test_formazione.py`) + import dei nuovi modelli in
`tests/conftest.py`. 107/107 test passano (101 + 6 nuovi).

Prossimo passo: Fase 2 (Vista Piano Annuale + Riepilogo ore).

## Sessione 66 — Piano Annuale delle Attività: analisi/piano + Fase 0 calendario (Cowork)

**Contesto:** Roberto ha condiviso il foglio Google
`BOZZA_PIANO_ATTIVITA_2026_27.xlsx` (12 fogli: Introduzione, Piano
della formazione, Riepilogo ore + 9 fogli mensili) e ha chiesto
un'analisi di fattibilità completa per integrarlo in CaronteApp,
collegandolo a calendario scolastico e assegnazione classi, con un
generatore di Consigli di classe in parallelo — esplicitamente "un
project plan prima di scriverlo e implementarlo".

Prodotto un artifact ("Piano Annuale delle Attività") con: mappa di
cosa esiste già (bucket CCNL art.44 in `models/attivita_ist.py`,
`SospensioneDidattica`, Assegnazioni, `_preset_partecipanti()`), gap
analysis, principio del generatore CdC (insiemi docenti per classe
dalle **Assegnazioni**, non dall'orario — l'orario si stabilizza
troppo tardi rispetto all'approvazione del piano annuale), e un piano
a 5 fasi (0. Calendario, 1. Piano Formazione, 2. Vista+Riepilogo ore,
3. Generatore CdC, 4. Pubblicazione PDF). Raffinato attraverso ~15
round di commenti diretti sull'artifact: niente vincolo di stesso
anno/indirizzo tra classi (solo docenti non condivisi, con
raggruppamento per indirizzo come preferenza secondaria non
vincolante), vincoli fissi di orario (martedì CAT/AFM/ROM 13:30-15:30,
3ª/4ª LLI 12:30-13:30), presenza obbligatoria alle riunioni anche nei
giorni personalmente liberi da lezione, presenza del DS impostabile
per riunione/blocco come vincolo forte di sovrapposizione, vincoli
manuali pre-generazione, pubblicazione solo PDF (niente pagina
pubblica).

Punto delicato: il bucket CCNL per la Formazione. Roberto ha chiesto
inizialmente di metterla nello stesso bucket dei Consigli di classe;
verificata la normativa su sua richiesta esplicita (CCNL art.29 comma
3, Cassazione n.7320/2019), la formazione obbligatoria rientra invece
nelle 40 ore del **Collegio docenti** (bucket A), non in quelle dei
Consigli di classe (bucket B) — corrisponde già a come
`TIPI_ATTIVITA` classifica oggi i due tipi, quindi nessuna modifica al
codice esistente su questo punto. Roberto ha confermato la lettura
normativa.

**Fase 0 completata** (calendario scolastico 2026-2027): letto
`Calendario_2026_27.pdf` (delibera CdI n.199 del 29/06/2026) fornito
da Roberto, confermate con lui le date esatte (le chiusure uffici del
7/24/31 dicembre + 24/31 marzo NON sono sospensione didattica, sono
chiusura uffici — escluse). Popolato `sospensioni_didattiche` con 6
righe per il 2026-2027 (Immacolata 7-8 dic, vacanze natalizie 23 dic
-6 gen, Carnevale 8-9 feb, vacanze pasquali 24-31 mar, 1 maggio, 2
giugno) e `data_fine_lezioni_2026-2027` = 8 giugno 2027 via
`config_calendario.py`. Verificato prima su copia del DB, poi backup
cifrato (`database_20260820_1636_pre_seed_calendario_2026_27.db.enc`)
e applicato al DB reale, `PRAGMA integrity_check` ok, 101/101 test
passano. Nota: "inizio lezioni" (14 settembre 2026) non ha un campo
dedicato in nessun punto dell'app — non inventato un nuovo
`config_app`/modello per questo finché non emerge un uso reale.

Prossimo passo: Fase 1 (Piano della Formazione — nuovo modello +
iscrizioni per singola voce).

## Sessione 65 — Assegnazioni: classe con sola compresenza spariva (Cowork)

**Contesto:** Roberto: B-02-ING (ITP Conversazione Inglese) ha ore
proprie in 1ª-4ª LLI ma è marcata compresenza in 5ª LLI — quella
singola classe non compariva affatto nella pagina Assegnazioni,
nessun modo di assegnarci ore alla docente. Temeva un problema anche
nel Calcolo organico USR.

Causa: `routes/assegnazioni.py::_classi_per_cc()` derivava l'elenco
classi da `_righe_piano()` chiamata senza anno_corso/indirizzo — quella
funzione, così, sceglie le righe di compresenza solo se l'INTERA
classe di concorso non ha alcuna riga propria in NESSUNA classe
(fallback pensato per le CC che esistono solo come compresenza: B-02,
B-03, B-12, B-14, B-16, B-17 — Task 44). Con B-02-ING che ha ore
proprie altrove, il fallback non scattava mai e la riga di sola
compresenza per 5ª LLI spariva dall'elenco classi per l'intera CC, non
solo dal conteggio ore.

Fix: `_classi_per_cc()` ora prende l'unione di tutte le righe di piano
studi per quella CC (proprie e di compresenza), non solo quelle scelte
dal fallback. Il calcolo ore per singola classe (`_righe_piano` con
anno_corso/indirizzo, usata altrove) resta invariato e già corretto.

Verificato che il timore sul Calcolo organico USR era infondato:
`_ricalcola_organico()` già somma tutte le righe di piano studi,
comprese quelle di compresenza, verso l'organico della CC dell'ITP —
nessuna modifica necessaria lì.

Verificato sul DB reale (5ª LLI assente prima, presente con le ore
corrette dopo) e sul server reale ("5A LLI" ora tra le colonne).
Aggiunti 3 test di regressione, incluso uno che verifica che il caso
originale (Task 44) non regredisca. 101/101 test passano (98 + 3
nuovi). Commit: `e931b54`.

**Addendum:** Roberto ha chiesto di chiarire la differenza tra i badge
"COE ←︎"/"COE →︎" in Assegnazioni (coe_entrata/coe_uscita). Chiarito
insieme (con una correzione sua alla mia prima spiegazione): coe_uscita
= "completa con" (titolare qui, cattedra completata con ore altrove);
coe_entrata = "cede a" (titolare altrove, il nostro istituto cede ore
in eccesso per completargli la cattedra qui) — stesso linguaggio già
in uso in Organico USR (`CattedraOrganico.coe_direzione`). Su richiesta
di Roberto, sostituite le sole frecce con queste stesse parole nei
badge di Assegnazioni ("Completa"/"Cede a", spazio in tabella troppo
stretto per la forma estesa), con tooltip per la spiegazione completa.
101/101 test passano. Commit: `4cf67ef`.

## Sessione 64 — Incarichi docenti: tendina non filtrava per anno di servizio (Cowork)

**Contesto:** Roberto: selezionando l'anno corrente in Incarichi
docenti, la tendina mostra anche docenti non in servizio per
quell'anno — stesso bug già trovato e corretto in altri 5 punti
dell'app in questa sessione (prove di recupero agosto/giugno, attività
istituzionali): `routes/incarichi.py` filtrava solo
`Docente.attivo==True`, senza controllare `anno_scol_inizio`/
`anno_scol_uscita` né tener conto dell'anno effettivamente selezionato
nella pagina — la tendina mostrava sempre lo stesso elenco di docenti
correntemente attivi, qualunque anno si scegliesse.

Sostituito con `routes/impostazione_anno.py::_docenti_per_anno(anno)`,
lo stesso helper già usato con successo in `docenti.py`,
`assegnazioni.py`, `banca_ore.py`, `dashboard_anno.py` ed
`export_xlsx.py` — stesso pattern di import locale già consolidato.

Verificato sul DB reale: per l'anno corrente (2025-2026), 13 docenti
con `anno_scol_inizio` 2026-2027 (non ancora in servizio) sono ora
correttamente esclusi (93 → 80 in tendina); verificato anche sul
server reale. 98/98 test passano. Commit: `b0963c4`.

## Sessione 63 — Icone SVG mostrate come testo grezzo (textContent→innerHTML) (Cowork)

**Contesto:** Roberto segnala che nel popup di inserimento ore in
Assegnazioni compare il markup SVG grezzo (`<svg width="16"...>`)
invece dell'icona di conferma.

Causa: `templates/assegnazioni/index.html` impostava `msg.textContent
= '{{ icon('check') }}'` — `icon()` (macro in `templates/_icons.html`)
restituisce markup SVG grezzo, che va inserito con `innerHTML` per
essere interpretato come HTML; con `textContent` il browser lo tratta
come testo puro e lo mostra letteralmente.

Cercato lo stesso pattern in tutto il progetto — trovate altre 11
occorrenze reali in 8 file: `import_banca_ore.html` (2), `dashboard.html`
(toggle box + tendina "Cambia tipo" supplenza, dove "Recupero" era
l'unico tipo con icona SVG anziché un carattere semplice, mai
notato), `assenza_form.html` (avviso "supera 2h CCNL"),
`calendario_fsl.html` (3, incluso il valore salvato per il ripristino
del bottone), `roster.html` (2, toggle apri/chiudi card),
`piano_studi.html` (label seleziona tutti/nessuno),
`recupero/agosto_gruppi.html` (badge "già coperta" — qui passava per
`document.createTextNode()`, che non interpreta MAI l'HTML).

Un caso diverso dal sintomo visibile: `docenti_classi_concorso.html`
aveva una funzionalità rotta in silenzio — un controllo "il badge ha
già la stella?" confrontava `.textContent.includes('{{ icon(...) }}')`,
che non trova mai l'SVG (textContent non contiene mai markup HTML),
quindi la stella di "classe di concorso principale" non veniva mai
riassegnata dopo aver rimosso la precedente. Il controllo era comunque
ridondante (un solo badge principale alla volta) — rimosso invece di
ripararlo.

Verificato: grep finale su tutto templates/ per gli stessi pattern —
zero occorrenze rimanenti. Sul server reale, confermato che il codice
servito contiene `msg.innerHTML = '<svg...'` e che il browser lo
renderizza come icona (nessun testo residuo). 98/98 test passano
(solo script lato client, nessuna logica server toccata). Commit:
`06b27d8`.

**Addendum:** Roberto, sempre in Assegnazioni: non riesce a cliccare
il box ore potenziamento per Casarico, e nota che quella cella non è
centrata in nessuna tabella. Causa comune: la colonna Potenziamento
(`.td-pot`, 34px, subito dopo le due colonne fisse Docente/Tipo) non
aveva `text-align:center`, e soprattutto non era "sticky" come le due
colonne che la precedono (`.td-doc` sticky a `left:0`, `.td-tipo`
sticky a `left:170px`). Con la tabella scorsa anche di pochi pixel —
inevitabile su schermi non larghissimi, una colonna per ogni classe —
la colonna Potenziamento, ferma nel flusso normale, finiva
fisicamente SOTTO la colonna Tipo (che restando ancorata la copre con
z-index più alto): i click in quella zona colpivano la cella Tipo
sottostante. Riprodotto con precisione via `elementFromPoint()`: a
scroll orizzontale >0, il punto centrale della cella risultava
occupato da `td.td-tipo`, non da `td.td-pot`.

Aggiunta `text-align:center` e `position:sticky` (`left:226px` =
170+56) alla regola CSS condivisa `.td-pot`/`.th-pot`, e la classe
`td-pot` (mancante) alle 7 celle della colonna che non l'avevano —
solo quella interattiva delle assegnazioni ce l'aveva già. Verificato:
dopo il fix, allo stesso scroll il punto appartiene alla cella
potenziamento stessa (confermato via `getComputedStyle`), e un click
reale in quel punto apre correttamente il popover. 98/98 test
passano.

## Sessione 62 — Prove agosto: docenti fuori servizio in tendina, assenze senza alert (Cowork)

**Contesto:** Roberto, su `/recupero/agosto/calendario`: la tendina
"Docente assistente" mostrava anche docenti che entreranno in servizio
dopo il 31 agosto (dopo le prove) e docenti con contratto già scaduto;
inoltre un'assenza registrata dopo aver assegnato un docente come
assistente non dava alcun riscontro.

Causa (1): `costruisci_dati_agosto()` filtrava i docenti solo su
`attivo==True` e `tipo_contratto` — nessun controllo sull'anno
scolastico di servizio, mentre `_docenti_per_anno()` in
`routes/impostazione_anno.py` ha già il filtro giusto su
`anno_scol_inizio`/`anno_scol_uscita` (corretto in passato per lo
stesso tipo di bug, Task 35). Replicato lo stesso filtro qui (non
importato da routes/, per non introdurre una dipendenza da un modulo
route dentro modules/). Verificato sul DB reale: 13 docenti con
`anno_scol_inizio` 2026-2027 ora correttamente esclusi (71 → 58
docenti in tendina).

Causa (2): nessun controllo incrociava titolare/assistente assegnati
con la tabella Assenza. Aggiunto un nuovo tipo di conflitto 'assenza'
nello stesso meccanismo già esistente per i conflitti docente/alunno
(banner rosso in cima alla pagina) — a livello di data, non di ora
precisa (le ore di RecuperoLezione sono HH:MM, quelle di Assenza sono
numeri di ora scolastica 1-9, rappresentazioni diverse senza
conversione diretta; un'assenza quel giorno resta comunque un segnale
utile anche solo a livello di data). Verificato sul DB reale: il caso
concreto segnalato (Santagata, assistente assente il 26/08) ora genera
correttamente l'alert.

Aggiunti 4 test di regressione. 95/95 test passano (91 + 4 nuovi).
Commit: `5cf4128`.

**Addendum:** Roberto ha chiesto di verificare che lo stesso bug non
si ripetesse altrove. Grep sistematica di ogni query "docenti attivi"
usata per liste candidati legate a un anno/periodo fisso — trovate 4
ricorrenze reali, verificate sul DB reale (13 docenti 2026-2027 le
rendevano visibili dove non dovevano):
1. `routes/recupero_agosto.py::agosto_docenti_disponibili()` — pagina
   dedicata "Docenti disponibili", stesso bug della tendina.
2. `routes/recupero_agosto.py` (route gruppi, GET) — creava una riga
   RecuperoDocente anche per chi non è ancora in servizio.
3. `modules/recupero_agosto_calendario.py::genera_bozza_agosto()` — la
   più seria: il generatore automatico poteva ASSEGNARE (non solo
   proporre) un docente non ancora arrivato come assistente, senza
   verifica umana nel mezzo.
4. `routes/recupero_giugno.py::docenti()` — lista "non ancora
   iscritto" per giugno (senza filtro sul tipo contratto, regola
   diversa da agosto).
5. `routes/attivita_ist.py::_non_in_servizio_per_data()` — preset
   partecipanti eventi istituzionali: il controllo esisteva già per chi
   è USCITO ma non per chi non è ancora ARRIVATO.

Centralizzato in due funzioni condivise in `routes/recupero_costanti.py`
(foglia dell'albero di import): `docenti_in_servizio_query(anno_scol)`
e `docenti_idonei_periodo(anno_scol)` (la precedente + CONTRATTI_OK).
Verificato sul DB reale e dal vivo che nessuno dei 13 docenti
2026-2027 compaia più in nessuno dei punti corretti. Aggiunti 3 test
di regressione. 98/98 test passano (95 + 3 nuovi). Commit: `7fcee78`.

## Sessione 61 — Assenze: eliminazione multipla per periodi di più giorni (Cowork)

**Contesto:** Roberto, dopo il fix della Sessione 60: caricando
un'assenza di più giorni, non c'era modo di eliminare l'intero blocco
— bisognava farlo riga per riga, perché ogni giorno di un range/
periodico viene creato come `Assenza` indipendente (nessun id_gruppo
le collega, per scelta di design invariata qui). Proposta un'euristica
automatica (stesso docente+motivo+giorni contigui) o selezione
manuale — scelta la selezione manuale, per poter correggere anche un
periodo non del tutto contiguo.

- `routes/assenze.py::_elimina_assenza_righe()`: estratta dalla
  vecchia `elimina()` tutta la logica di cancellazione di UNA riga
  (movimenti banca ore, supplenze automatiche, presenze
  istituzionali, lapide di sync) senza commit/log — condivisa ora fra
  l'eliminazione singola esistente e quella multipla nuova.
- Nuova route POST `/assenze/elimina-multiple`: riceve una lista di id
  (checkbox) + id_docente, elimina solo le righe selezionate.
- Nuova route GET `/assenze/docente/<id>` +
  `templates/assenze/docente_lista.html`: elenco di tutte le assenze
  di un docente (filtrabile per periodo), con checkbox per riga,
  "seleziona tutte" e un pulsante "Elimina selezionate" che si attiva
  solo con almeno una riga scelta.
- `templates/dashboard.html`: icona "elenco" accanto a modifica/
  elimina in ogni riga di "Docenti assenti", verso la nuova pagina —
  richiedeva l'id_docente, prima non tracciato nel namespace di
  raggruppamento (aggiunto `ns.prev_id_docente`).

Verificato: test end-to-end diretto su copia del DB reale (creata/
eliminata un'assenza di prova su 3 giorni selezionandone 2 su 3 —
solo quelle sparite, la terza intatta; database.db reale mai
toccato). Sul server reale: pagina, checkbox, contatore e "seleziona
tutte" funzionano; i 17 link dalla dashboard puntano all'URL corretto
per il rispettivo docente. Aggiunti 3 test di regressione. 91/91 test
passano (88 + 3 nuovi). Commit: `895fad6`.

**Addendum:** stesso collegamento aggiunto anche in Agenda (sezione
"Assenze future"), su richiesta di Roberto. Verificando dal vivo è
emerso un problema preesistente: nessuna delle 4 tabelle di
`agenda.html` aveva un contenitore `overflow-x:auto` — con "Assenze
future" già a 22 righe, la tabella era più larga della card ANCHE
PRIMA di aggiungere la nuova icona (869px vs 724px senza, 824px
rimuovendo la nuova icona via JS — già oltre). Corretto avvolgendo
tutte e 4 le tabelle della pagina nello stesso pattern
`overflow-x:auto` già usato altrove nell'app. 91/91 test passano.
Commit: `d187733`.

## Sessione 60 — Assenze: data futura ignorata nei tab "Più giorni"/"Periodico" (Cowork)

**Contesto:** Roberto segnala che registrando un'assenza con inizio
nel futuro, l'app salva la data di apertura del form invece di quella
inserita.

Causa: `templates/assenza_form.html` ha tre coppie di campi data (uno
per ciascun tab "Un giorno"/"Più giorni"/"Periodico"), tutte presenti
nel DOM contemporaneamente e precompilate con la stessa data di
apertura del form — `setDurata()` cambiava solo `style.display` per
mostrare/nascondere il tab, non disabilitava i campi degli altri due.
Il browser inviava quindi sempre anche il campo "data" del tab "Un
giorno" (mai toccato se si usava un altro tab), e `modules/assenze_
registrazione.py::registra_assenze_form()` controlla i campi in
quest'ordine: `form.get('data') or form.get('data_range_ini') or
form.get('data_per_ini')` — "data" vinceva sempre perché non è mai
vuoto, ignorando in silenzio la data scelta nel tab realmente in uso.

Fix: i campi dei tab non attivi vengono disabilitati (non solo
nascosti) in `setDurata()`, così il browser non li invia più — stesso
approccio anche di default nell'HTML per i tab inattivi al
caricamento. Verificato sul server reale via `FormData()`: prima del
fix tutti e tre i campi arrivavano popolati, dopo solo quello del tab
attivo. Aggiunti 2 test di regressione che chiamano
`registra_assenze_form()` con solo `data_range_ini`/`data_per_ini`
valorizzati (come farebbe ora il browser) e verificano che l'Assenza
creata abbia la data futura corretta. 88/88 test passano (86 + 2
nuovi). Commit: `bfe034a`.

**Nota a margine:** nella stessa sessione, verificata anche su
richiesta la tabella della piantina interattiva aule (`/aule/mappa`):
la colonna "Sede" era tagliata a bordo pagina per un riquadro laterale
troppo stretto (260px) — corretto allargandolo a 300px e aggiungendo
`class="wrap"` alla cella Sede. Vedi addendum Sessione 59.

## Sessione 59 — Classi di concorso: codici obsoleti/errati corretti (Cowork)

**Contesto:** Roberto nota che l'app mostra ancora "A048" mentre ora
si chiama "AS48", chiede una verifica completa dei codici contro la
normativa più recente.

Verifica sull'app + ricerca online (Allegato 8 ministeriale — elenco
ufficiale codici DPR 19/2016 — e tabelle del D.I. 22/12/2023 n. 255):
il problema era più ampio del solo A-48. Due errori indipendenti da
qualunque riforma, verosimilmente refusi di inserimento originari
(nessuna nota li giustificava come scelta deliberata):
- `A-01` era etichettato "Disegno e storia dell'arte II grado", ma
  A-01 ufficialmente è "Arte e immagine nella scuola secondaria di I
  grado" — tutt'altra materia/grado; quello giusto per noi era A-17.
- `A-22-ING/SPA/TED` era etichettato "Lingua e Culture Straniere", ma
  A-22 ufficialmente era "Italiano, storia, geografia I grado" —
  quello giusto era A-24.

Prima di modificare il database (11 docenti reali collegati a questi
codici), chiesto conferma esplicita a Roberto — segnalato, non deciso
da soli, come da regola del progetto sui dati ambigui: (1) se il
prospetto SIDI ricevuto per il 2026-2027 mostra già i nuovi codici
AM/AS o ancora i vecchi (le fonti di settore segnalavano che a metà
2025 alcune procedure, es. Esami di Stato, usavano ancora i vecchi
codici DPR 19/2016 — non un fatto scontato); (2) conferma per la
correzione di A-01/A-22. Risposta: SIDI mostra già i nuovi codici,
procedi con entrambe le correzioni.

Codici corretti direttamente al valore finale post-riforma (non
attraverso l'intermedio A-17/A-24, dato che comunque va aggiornato):
A-01→AS01, A-22-ING→AS2B, A-22-SPA→AS2C, A-22-TED→AS2D, A-48→AS48.

- `app.py::_migra_codici_classi_concorso()`: nuova migrazione
  idempotente (stesso pattern delle altre già presenti — guardia su
  sqlite_master, UPDATE solo se il vecchio codice esiste ancora), si
  applica da sola su ogni macchina di Roberto al prossimo avvio.
- `routes/assegnazioni.py::AREE`: aggiornato l'elenco usato per
  raggruppare le classi di concorso nella pagina Assegnazioni — senza
  questo, i gruppi "Storia dell'Arte", "Lingue" e "Motorie e Sportive"
  sarebbero spariti in silenzio (`ClasseConcorso.query.filter_by(
  codice=...)` non trova nulla col codice vecchio e salta il gruppo).
- Backup cifrato del DB reale prima di procedere (regola non
  negoziabile #2), migrazione testata su copie isolate tramite
  `create_app()` completo (non solo SQL a mano) verificando
  idempotenza (secondo giro: nessun UPDATE) e nessuna perdita dati
  (conteggio docenti/materie collegati identico prima/dopo — le
  relazioni sono per `id`, non per `codice`, quindi il rename non le
  tocca). Applicata poi sul database.db reale, `PRAGMA integrity_check`:
  ok. 86/86 test passano. Commit: `25a504a`.

**Addendum:** Roberto chiede di verificare la tabella nella sezione
Aule. Trovato: nella tabella laterale della piantina interattiva
(`/aule/mappa`) la colonna "Sede" veniva tagliata a bordo pagina — il
riquadro aveva larghezza fissa (260px, comprensiva del padding di
default di `.card`, 24px per lato) insufficiente per il testo più
lungo ("Sede Centrale - Piano Terra"), senza scroll orizzontale né
andare a capo. Allargato il riquadro (260px→300px, padding ridotto a
14px) e aggiunta `class="wrap"` alla cella Sede (colonna più stretta,
testo su due righe invece di forzare una colonna larga). Verificato:
0 celle in overflow dopo il fix (prima: tableWidth 291px >
containerWidth 260px). 86/86 test passano. Commit: `f9eecd2`.

## Sessione 58 — Display: autoscroll quando le ore non entrano a video (Cowork)

**Contesto:** Roberto, sul monitor display in corridoio (nessuno lo
tocca): nei giorni con molte supplenze le ore oltre la prima/seconda
restano fuori dallo schermo, chiede se ha senso un autoscroll.

Trovata una `autoScroll()` già presente in `templates/display.html` ma
completamente morta: cercava elementi `.sup-card`, classe che non
esiste nel markup attuale (i box supplenza sono `.box`, le sezioni
`.sezione-ora`) — probabilmente un resto di una versione precedente
del template, mai raggiunto perché la querySelectorAll tornava sempre
vuota.

Sostituita con `avviaAutoScroll()`: se il contenuto della pagina non
supera l'altezza della finestra non fa nulla (niente scroll superfluo
nei giorni con poche variazioni); altrimenti scorre una `.sezione-ora`
(un'ora scolastica) alla volta con `scrollIntoView`, con intervallo
calcolato per stare entro i 30s del refresh automatico di pagina già
esistente (che comunque riporta tutto in cima ad ogni ciclo).

Verificato sul server reale: data con 39 supplenze/5 ore (contenuto
2124px contro 800px di viewport) → autoscroll attivo, sequenza delle
5 sezioni verificata via JS con offset crescenti coerenti; data senza
supplenze (contenuto = esattamente 1 schermata) → nessuno scroll,
come atteso. 86/86 test passano (solo JS lato client). Commit:
`5434582`.

**Addendum:** Roberto: meno a scatti e più fluido, e box più compatti
per ridurre quanto c'è da scorrere. Sostituito lo scroll a salti tra
`.sezione-ora` (scrollIntoView) con un movimento continuo pixel per
pixel via `requestAnimationFrame`, con pausa di lettura all'inizio e
alla fine prima del refresh a 30s — verificato campionando `scrollY`
frame per frame (performance.now()): incrementi di ~1px ogni ~16ms
(60fps), non più un balzo discreto. Box supplenza/classe libera/
migrazione ridotti al minimo leggibile (min-height quasi dimezzata,
font-size ridotti in proporzione). Sulla stessa giornata di prova
(2026-06-03, 5 ore/39 supplenze) l'altezza del contenuto è scesa da
2124px a 1558px a parità di viewport — meno da scorrere, più visibile
subito. 86/86 test passano. Commit: `b2e2eb3`.

**Secondo addendum:** Roberto: sul suo browser sembrava lento. Causa:
la durata totale dello scroll era fissa (~22s) indipendentemente da
quanto c'era da scorrere — su una pagina con poco overflow, coprire
poca distanza in 22s dà una velocità (px/s) molto bassa. Sostituita
con una velocità costante (110px/s, verificata via campionamento
frame per frame: ~2px ogni 16ms, contro i ~33px/s di prima); se il
contenuto è così lungo da non starci nel tempo residuo prima del
refresh a 30s, la durata viene comunque compressa per restare nel
limite, come prima. 86/86 test passano. Commit: `4d044e4`.

**Terzo addendum:** Roberto segnala che l'ultima parte del contenuto
restava nascosta e che la footer blu fissa copriva del testo; propone
anche un "va e vieni" visto che lo scroll ora è più veloce del refresh
a 30s. Causa del contenuto nascosto: la footer è `position:fixed`,
quindi non fa parte del flusso del documento — non sposta da sola il
punto di scroll massimo, per cui anche a fondo scroll l'ultima fetta
di contenuto pari all'altezza della footer restava sempre sotto di
essa, perché il body non riservava lo spazio corrispondente. Aggiunto
`padding-bottom` al body pari all'altezza della footer (50px, quella
reale misura 32px) — verificato sul server reale che a scrollTop
massimo il fondo dell'ultima sezione-ora sta ora sopra la footer
(750.5px contro footerTop 767px). Aggiunto anche il va-e-vieni
richiesto: raggiunta la fine, dopo una pausa di lettura risale fino in
cima e ridiscende in loop finché il refresh a 30s non ricomincia da
capo, più una soglia minima (20px) sotto la quale l'autoscroll non
parte per non far vibrare la pagina per un arrotondamento di pochi
pixel quando il contenuto sta già tutto a video. 86/86 test passano.
Commit: `d6b9dbd`.

**Quarto addendum:** velocità autoscroll ridotta da 110 a 90px/s su
richiesta di Roberto. Commit: `cb3a09e`.

**Quinto addendum:** rimosso il campo data in alto a destra nella
banner — Roberto segnala che non è modificabile (probabile limite del
browser/monitor kiosk su cui è mostrato lo schermo, nessuno lo tocca
comunque) e chiede di toglierlo. Restano le frecce ‹ › e "Oggi" (link
semplici, non un date-picker). Commit: `a4d3545`.

## Sessione 57 — Piano Attività Personale per docenti a cattedra incompleta (Cowork)

**Contesto:** Roberto: i docenti con cattedra non completa in istituto
(orario ridotto o completamento altrove) partecipano agli impegni
collegiali solo in proporzione alle ore di contratto qui — prima
gestito fuori dall'app (piano personale su carta/email), ora scelto
direttamente dal Piano delle Attività ufficiale. Confermato: link
personale con token (nessun account per i docenti), quota
proporzionale, selezione che sostituisce il preset automatico,
modificabile finché lo staff non la blocca. Commit: `33bfe15`.

- `models/piano_attivita_personale.py`: `PianoAttivitaPersonale`
  (token, stato bozza/inviato/bloccato) + `PianoAttivitaPersonaleVoce`
  (eventi scelti). Riusa i bucket CCNL art.44 già modellati in
  `models/attivita_ist.py` (BUCKET_A/B, 40h/anno per cattedra piena) —
  gli scrutini restano sempre obbligatori per tutti, fuori da qui.
- **Trovata un'ambiguità nei dati durante il collaudo**: `Docente.
  ore_contratto` non si può usare come riferimento "cattedra piena" —
  per i part-time contiene già il valore ridotto (verificato: ABRAMINI
  ha ore_contratto=15 e ore_contratto_pt=15, la frazione sarebbe
  sempre stata 1.0, nascondendo proprio i docenti da intercettare).
  Aggiunto `config_istituto.py::ore_cattedra_piena` (default 18,
  configurabile in Impostazioni → Dati istituto) come riferimento
  esterno — segnalato a Roberto di verificare se 18 vale per tutte le
  categorie di docenti nel suo istituto. Riusa anche `ore_ist_limite`
  (già esistente, usato dal cruscotto ore istituzionali in
  routes/report.py, lì fisso a 40h per chiunque — qui proporzionato).
- `routes/attivita_ist.py::_preset_partecipanti()`: per gli eventi
  non-scrutinio, un docente con un piano attivo per l'anno non segue
  più il preset "per tutti/per classe/per dipartimento" — la sua
  selezione personale lo sostituisce interamente.
- `routes/piano_personale.py`: route staff (genera/rigenera link,
  blocca/sblocca — nuova sezione `piano_personale` nella matrice
  permessi) + route pubbliche a token (nessun controllo oltre al
  token — vedi `app.py::ROUTE_PUBBLICHE`). La pagina pubblica non
  estende `base.html` (niente nav/permessi staff per un visitatore
  anonimo).

Verificato con una copia del database reale: 30 docenti su 93 attivi
risultano a cattedra incompleta, frazioni/quote coerenti. Flusso
end-to-end completo (genera link → docente sceglie un evento → compare
come partecipante SOLO per quello, non per altri eventi bucket A/B
dello stesso anno, scrutinio invariato → blocco → tentativo di
modifica forzata rifiutato → sblocco). Aggiunto
`tests/test_piano_attivita_personale.py` (12 test, inclusa la
regressione su "Salva e invia" che deve salvare anche le spunte, non
solo lo stato). Suite completa: 82/82 test passano.

**Addendum stessa sessione:** Roberto segnala che la pagina non
mostrava da nessuna parte l'anno scolastico, e usava come default
`_anno_default_piano()` (l'anno "in preparazione") invece dell'anno
operativo — proprio la confusione tra i due concetti-anno già causa di
bug ricorrenti in passato (vedi guida rapida del progetto). Cambiato
il default a `get_anno_corrente()`, aggiunto un selettore anni (stesso
pattern di `templates/docenti.html`) e un avviso quando si guarda un
anno diverso da quello corrente. I dati erano già correttamente
separati per anno (chiave unica docente+anno_scol) — mancava solo la
visibilità/il modo di cambiarlo in UI. Commit: `d9cb73d`.

**Secondo addendum:** Roberto chiede conferma che il link personale
funzioni solo sulla stessa rete del Mac che esegue l'app — confermato
(`app.py` fa `app.run(host='0.0.0.0', ...)`: raggiungibile in LAN, non
esposto su internet; un docente da casa non può aprirlo, a meno di una
VPN/tunnel a parte, fuori dal codice). Chiesto che questo sia chiaro,
non solo detto a voce: aggiunto un avviso esplicito nella pagina
staff, nella pagina pubblica del docente e nella voce Guida. Commit:
`90c2c60`.

**Terzo addendum:** Roberto propone (confermato) un richiamo al piano
direttamente in Anagrafica docenti, e chiede se colloqui
scuola-famiglia/formazione rientrino nei bucket CCNL — sì, erano già
in bucket A, mai reso esplicito. Aggiunto `models/attivita_ist.py::
label_bucket()` (elenco tipi per bucket, derivato da TIPI_ATTIVITA) e
la legenda esplicita nella pagina staff, pagina pubblica e una nuova
FAQ in Guida. In `templates/docenti.html`: badge colorato per stato
piano (da generare/in attesa/inviato/OK) accanto al tipo contratto,
solo per chi ha permesso su 'piano_personale'. In
`templates/docente_form.html`: nuova card "Piano attività personale"
(stesso stile della card Incarichi) con ore bucket A/B, stato ed
elenco impegni scelti, solo per docenti a cattedra non completa
nell'anno corrente. Commit: `90217de`.

**Quarto addendum:** Roberto segnala un caso reale non coperto: gli
IRC hanno spesso 18 ore (cattedra piena) ma su moltissime classi (1h/
settimana ciascuna) — seguendo tutti i consigli di classe di ognuna
sforerebbero facilmente le 40 ore del bucket B, quindi devono
scegliere anche loro pur essendo a tempo pieno. Il criterio precedente
(`cattedra_incompleta`, frazione < 1) li escludeva del tutto. Aggiunta
`deve_compilare_piano()` = cattedra incompleta OPPURE
`tipo_contratto == 'IRC'` — la quota per un IRC a 18 ore resta piena
(40/40h, non ridotta): il punto non è fare meno ore ma scegliere
quali. Verificato sui 2 IRC reali del database (entrambi 18 ore, prima
esclusi, ora correttamente inclusi con quota piena). Commit:
`e82402a`.

**Quinto addendum:** Roberto chiede una verifica visuale di
`/docenti?anno=2025-2026` — il badge "Piano attività personale" (terzo
addendum) risultava troncato a bordo pagina. Causa più ampia del
singolo badge: il contenitore della tabella aveva `overflow:hidden`
senza nessun meccanismo di scroll orizzontale, mentre la tabella
(1270px) è più larga del contenitore visibile (772px) — le colonne
Colloqui, Stato e soprattutto Azioni (modifica/esporta/elimina) erano
già silenziosamente irraggiungibili anche prima di questa sessione, il
nuovo badge ha solo reso il problema più visibile. Aggiunto un
contenitore `overflow-x:auto`, stesso pattern già usato in questa
sessione per `piano_personale_lista.html` e `agosto_calendario.html`.
Verificato sul server reale (prima: `scrollLeft` senza alcun effetto;
dopo: colonne raggiungibili scorrendo). Commit: `6dba99c`.

**Sesto addendum:** Roberto preferisce non dover scorrere affatto —
chiede etichette più corte (es. colloqui "Lun 1^-2^", tipo contratto
"TI", stato come icona invece di "Attivo"/"Non attivo"). Aggiunte
`Docente.colloqui_label_breve` ("Lun 1ª–2ª" invece di "Lunedì 1ª–2ª
ora") e `Docente.tipo_contratto_label_breve` (TI, IRC, TD ann., TD
30/6, TD-GS, Pot.) — l'etichetta estesa resta nel tooltip. Badge
"Piano" accorciato (via "da fare" invece di "Piano: da generare").
Colonna Stato → icona verde/rossa (check/x) con tooltip. La tabella è
passata da `table-layout:auto` (una colonna senza vincoli "rubava"
spazio alle altre finché non serviva scroll) a `table-layout:fixed`
con larghezze esplicite per ogni colonna tranne "Classe di concorso",
che assorbe lo spazio restante. Verificato sul server reale misurando
`scrollWidth`/`clientWidth` di ogni cella a più larghezze finestra
(1440px e 1090px): nessuno scroll orizzontale necessario, restano
troncati solo 6 cognomi eccezionalmente lunghi (es. "ORDINANA
TORTOSA") — comportamento preesistente, non introdotto da questa
modifica. 86/86 test passano (solo presentazione, nessuna logica
toccata). Commit: `f3b4ade`.

**Settimo addendum:** Roberto: le etichette corte vanno bene, ma non
il `table-layout:fixed` e la `class="wrap"` introdotti nell'addendum
precedente — la colonna Classe di concorso restava con spazio
inutilizzato perché il fixed le assegnava sempre tutto il residuo
anche quando non le serviva. Tornato a `table-layout:auto`: con le
etichette già accorciate il contenuto naturale della tabella ora entra
da solo, senza bisogno di forzare le larghezze; rimossa anche la
`class="wrap"` sulla cella Contratto (badge TI/PT/Piano di nuovo su
una riga sola). Verificato sul server reale: 0 celle troncate a
1440px/1090px, tabella larga esattamente quanto il contenitore, niente
spazio residuo forzato. A finestre molto strette (~860px) l'
`overflow-x:auto` del quinto addendum resta come rete di sicurezza
(scrollbar invece di clip silenzioso). 86/86 test passano. Commit:
`6270396`.

**Ottavo addendum:** con l'auto layout c'era di nuovo margine.
Ripristinate le intestazioni estese (H/sett, Contratto, Colloqui,
Attivo) dove entrano senza forzare scroll, lasciando abbreviati solo i
*valori* nelle celle (TI, "Lun 1ª–2ª", icona check/x) — erano quelli
il vero bersaglio della compattazione, non le intestazioni. Verificato
sul server reale a 1440px/1090px: nessuna intestazione o cella
troncata. 86/86 test passano. Commit: `0340cd7`.

## Sessione 56 — Calendario prove agosto: colonne tabella corrette (Cowork)

**Contesto:** Roberto ha chiesto una verifica visuale di
`/recupero/agosto/calendario` sul suo server reale (localhost:5002),
con login fatto direttamente nel pannello browser. Commit: `c8578c7`.

Trovati due problemi visivi: la colonna "Docente assistente" (un
`<select>`) troncava il testo senza ellissi ("SCHEPIS M. — 1 impe...");
la colonna "Classi" spezzava la lista separata da virgole a metà
token su righe diverse. Causa radice comune: la tabella usa il
`table-layout:auto` di default del sito, quindi una "Materia" molto
lunga su una riga rubava spazio alle colonne con larghezza dichiarata,
comprimendole in modo incoerente riga per riga.

- `table-layout:fixed` sulla tabella, con larghezze esplicite anche
  per Materia e Classi (prima senza width, causa dello squeeze).
- Contenitore `overflow-x:auto` + `min-width` sulla tabella: senza,
  il fixed layout avrebbe schiacciato proporzionalmente TUTTE le
  colonne sui viewport stretti — ora scorre in orizzontale.
- "Docente assistente" allargata a 230px (prima 190px).
- "Classi": spazio dopo ogni virgola solo in visualizzazione (il dato
  salvato resta invariato) così il testo va a capo ai punti naturali.
- "Materia" passa alla classe `.wrap` invece di troncare in silenzio.

Verificato visivamente sul server reale, prima e dopo, su più righe
con materie/cognomi lunghi. 110/110 template passano il parser Jinja
(a parte il falso positivo preesistente su roster.html). Suite
completa: 70/70 test passano (nessuna logica toccata, solo CSS/markup).

## Sessione 55 — Guida: sezioni mancanti aggiunte, contenuto obsoleto corretto (Cowork)

**Contesto:** chiesto se la Guida avesse bisogno di aggiornamenti e se
farli con un Cowork dedicato o in questa stessa sessione — risposto
che conveniva restare qui (già tutto il contesto delle ultime
sessioni caricato, nessun ciclo di test/verifica come per il codice).
Confermato con "rendi la guida quanto più completa e corretta
possibile ora". Commit: `6494fad`.

La Guida copriva solo 6 sezioni su una ventina di aree funzionali
esistenti, e due punti erano ormai sbagliati: "Assenze" diceva ancora
al collaboratore di scegliere "il motivo più preciso possibile
(malattia, permesso, legge 104...)" — l'opposto di quanto introdotto
nella Sessione 54 (privacy del motivo); "Cambi quadro" diceva "la
segreteria non ha accesso a questa sezione", falso da quando esiste
la matrice permessi configurabile (Sessione 49/53).

Aggiunte 18 sezioni nuove in `modules/guida_content.py`: Attività
fuori aula, Attività istituzionali (con la logica delle sostituzioni
scrutinio), Attività differite, Dipartimenti e materie, Banca ore,
Report, Orario, Recupero, Rientro dall'estero, Esami integrativi,
Docenti, Impostazione anno/Organico (con l'elenco reale dei 13 passi
del wizard), Cambio anno scolastico, Calendario scolastico, Istituto,
Incarichi, Assegnazioni e aule, Permessi per ruolo.

Verificato con una copia del database reale: tutte le 24 sezioni
(indice + pagina + PDF) rispondono 200. Corretto anche un test della
sessione precedente che usava `date.today()` come data di prova e
falliva se eseguito di domenica (l'app esclude di proposito le
domeniche dal periodo di un'assenza) — sostituita con una data fissa.
Suite completa: 70/70 test passano.

## Sessione 54 — Assenze: motivo specifico nascosto al collaboratore del DS (Cowork)

**Contesto:** Roberto: un collaboratore del DS coordina le sostituzioni
ma non deve sapere il motivo di salute/personale di un'assenza — solo
se l'ora è recuperabile (permesso orario) o no. Ferie/cambi turno non
hanno bisogno di un motivo, restano invariati. Chiesto "come potremmo
organizzare la sezione assenze per rispettare questo discorso di
privacy?" — confermato con lui che DS/DSGA/segreteria (gestisce già le
pratiche per prassi HR) vedono lo specifico, il collaboratore no.
Commit: `63ec41d`.

Il modello aveva già un abbozzo (`cat_label` vs `cat_label_interna`,
un commento "visibile solo DS/DSGA") mai completato: il form di
inserimento faceva scegliere a chiunque, collaboratore incluso, il
motivo esatto (lo sapeva comunque, lo digitava lui), e diverse pagine
(dashboard, agenda, presenze scrutini, ricerca...) mostravano il
codice motivo grezzo senza filtro.

- `models/assenza.py`: nuovo motivo `non_recuperabile` (usato al posto
  dello specifico da chi non ha titolo). `MOTIVI_RISERVATI` calcolato
  da `CATEGORIE` (tutti i motivi con etichetta pubblica 'Assenza'), non
  duplicato a mano. `cat_label_visibile()`/`motivo_visibile()`:
  mascherano sia l'etichetta sia il CODICE per ruolo — il codice anche,
  perché altrimenti resterebbe leggibile nel sorgente HTML (campo
  nascosto del form).
- `contesto_form_assenza(ruolo=...)`: i pulsanti specifici (malattia/
  lutto/matrimonio/permesso_personale/permesso_sindacale) compaiono
  solo a ds/dsga/segreteria, altrimenti un solo pulsante generico "Non
  recuperabile"; i contatori CCNL incorporati come JSON nella pagina
  escludono i motivi riservati per chi non ha titolo (altrimenti
  leggibili dal sorgente anche senza il pulsante).
- Difesa in profondità lato server: un tentativo di registrare/
  assegnare un motivo specifico via POST diretto da un ruolo non
  autorizzato viene forzato a `non_recuperabile`; modificare
  un'assenza già classificata nello specifico da chi ha titolo non può
  declassarla (il valore reale resta), anche cambiando altri campi
  come orario o note.
- Chiuse le fughe di visualizzazione dello stesso dato in dashboard,
  agenda, presenze scrutini/collegi, ricerca globale (che ora esclude
  anche il motivo dai criteri di ricerca per chi non ha titolo),
  disponibilità docenti corsi di agosto, endpoint JSON di disponibilità
  docente/classe/ora.

**Segnalato a Roberto, non deciso:** l'export dati personali GDPR
art.15 (`/docenti/<id>/esporta-dati`) mostra correttamente il dettaglio
completo (corretto per finalità legali), ma oggi vi accede chiunque
abbia 'visualizza' su Docenti — quindi anche il collaboratore può
generarlo per qualunque docente, bypassando di fatto questa
protezione. Indisponibilità ha un campo motivo separato (testo
libero), non toccato in questa sessione.

Verificato con una copia del database reale: collaboratore non vede né
i pulsanti né il valore nascosto nell'HTML; POST diretto con
motivo='lutto' forzato a 'non_recuperabile'; segreteria riclassifica
correttamente; DS vede lo specifico in sola lettura (coerente con la
matrice permessi, che gli dà solo 'visualizza' su assenze) ma non può
modificare; collaboratore che riapre un'assenza già classificata può
cambiarne l'orario ma non declassarla. Aggiunto
`tests/test_privacy_motivo_assenza.py` (12 test). Suite completa:
70/70 test passano.

**Addendum stessa sessione:** chiesto se anche Indisponibilità espone
dati sensibili — i motivi strutturati sono già tutti non sensibili
(colloqui, consiglio, uscita, progetto, gara, formazione, riunione,
altro), ma il campo note è testo libero visibile a chiunque abbia
accesso alla sezione. Aggiunto lo stesso avviso già presente nel form
Assenze ("non riportare qui motivi personali/clinici") sia nel form di
creazione (`templates/indisponibilita_form.html`) sia in quello di
modifica (`templates/modifica_indisponibilita.html`). Solo testo UI,
nessuna logica toccata. Commit: `d99db7a`.

## Sessione 53 — Permessi: sezioni granulari, Orario globale configurabile, blocco pulsanti in Visualizza (Cowork)

**Contesto:** Roberto trova la matrice permessi (Sessione 49) incompleta
su tre punti: "Orario globale" non è impostabile (era hardcoded ds/dsga,
mai passato dalla matrice); diverse sezioni sono accorpate e le vorrebbe
singole, "anche le sottosezioni"; il livello "Visualizza" dovrebbe anche
impedire di cliccare i pulsanti di modifica (es. "+ Assenza"), non solo
rifiutare il salvataggio lato server. Commit: `5c5401d`.

- `models/permesso_ruolo.py`: `SEZIONI` passa da 14 a 28 voci singole al
  posto dei raggruppamenti precedenti (es. 'attivita' → 'attivita' +
  'attivita_istituzionali' + 'attivita_differite' + 'dipartimenti';
  'supplenze' → 'supplenze' + 'cambi' + 'agenda'; stesso schema per
  banca_ore/import, report/mail_bozze, recupero/rientro/esami_integrativi,
  organico/dashboard_anno, istituto/tipi_incarico, assegnazioni/aule),
  più la nuova 'orario_globale'. `SEZIONI_GRUPPI` raggruppa solo
  visivamente le righe nella pagina Permessi (9 gruppi), il controllo di
  accesso resta per singola sezione.
- `_migra_split_sezioni_permessi()`: su un'installazione già in uso, ogni
  sezione nata da uno scorporo eredita il livello REALE già salvato per
  la sezione genitore (non il default statico) — altrimenti un accesso
  già funzionante sarebbe sparito di colpo al deploy (le sezioni nuove,
  senza righe proprie, sarebbero state trattate come 'esclusa' per
  tutti). Idempotente, gira ad ogni avvio insieme al seed esistente.
  'orario_globale' non eredita da nessuna sezione (prima era hardcoded,
  non un raggruppamento): seed diretto con lo stesso comportamento di
  prima (solo ds/dsga in modifica).
- `app.py::check_auth`: `BLUEPRINT_DSGA_ONLY_ECCEZIONI` porta fuori
  `sync.orario_globale` dal blocco hardcoded del blueprint `sync` (che
  resta DSGA-only per `sync.index`/`importa` — sovrascrivono l'orario,
  troppo rischiosi per essere configurabili, invariato per scelta
  esplicita) e lo fa passare dal controllo normale per sezione.
- Nuovi template global `sezione_corrente()`/`sola_lettura()`: quando la
  sezione della pagina corrente è 'visualizza' per l'utente, il `<body>`
  prende la classe `sola-lettura` — CSS generico disabilita i pulsanti
  submit dei form POST in tutta l'app senza dover toccare ogni singolo
  template, più un banner esplicito e il pulsante "+ Registra assenza"
  in nav disattivato quando 'assenze' è in sola visualizzazione. Il
  blocco server-side in check_auth resta la vera difesa, invariato.

Verificato con una copia del database reale: la migrazione crea 84 righe
(28 sezioni × 3 ruoli) ereditando correttamente i valori già salvati;
`orario_globale` configurabile per collaboratore/segreteria mantenendo
`sync.index` bloccato; il body riceve la classe `sola-lettura` e il POST
resta comunque rifiutato lato server anche forzandolo via richiesta
diretta. Aggiunto `tests/test_permessi_sezioni_granulari.py` (6 test).
Suite completa: 58/58 test passano.

## Sessione 52 — Banca Ore: docenti neoassunti anno futuro visibili anche negli anni precedenti (Cowork)

**Contesto:** Roberto segnala che in Banca Ore, con l'anno 2025-2026
selezionato, comparivano docenti inseriti come neoassunti per il
2026-2027 (`anno_scol_inizio='2026-2027'`, già `attivo=True`). Commit:
`1c49203`.

`routes/banca_ore.py::index()` interrogava
`Docente.query.filter_by(attivo=True)` senza applicare alcun filtro
sull'anno scolastico selezionato. Stesso bug già preso una volta per la
pagina Docenti (Task 35, `_docenti_per_anno()` in
`routes/impostazione_anno.py`) — qui il fix non era mai stato applicato
perché la stessa logica di "docenti attivi in un dato anno" era
duplicata invece di essere condivisa (pattern ricorrente, vedi guida
rapida). Sistemato riusando direttamente `_docenti_per_anno(anno)`.

Verificato: con una copia del database reale, i 13 docenti attualmente
segnati come neoassunti 2026-2027 (tra cui Agrò, Ghezzi, Tramontana,
già oggetto di unione anagrafiche in sessioni precedenti) sparivano
dall'elenco Banca Ore 2025-2026 col fix, comparivano prima. Aggiunto
test di regressione (`tests/test_banca_ore_docenti_anno.py`). Suite
completa: 52/52 test passano.

## Sessione 51 — Sostituzioni scrutinio: niente doppie nomine + riunione prec./succ. (Cowork)

**Contesto:** in Attività istituzionali, nulla impediva di nominare lo
stesso docente come sostituto di due assenti diversi nello stesso
scrutinio/collegio (fisicamente impossibile). Chiesto anche di vedere,
per i candidati liberi in quella riunione, se hanno la riunione
immediatamente precedente o successiva lo stesso giorno — utile per
scegliere chi è comunque già a scuola in quella fascia. Un commit:
`fa201bf`.

- `routes/attivita_ist.py::sostituzione_scrutinio()`: candidati
  suggeriti e menu a tendina ora calcolati per riga (per assente),
  escludendo i docenti già nominati sostituto di un ALTRO assente nella
  stessa attività — restano selezionabili per la propria riga già
  assegnata. Controllo anche lato server al salvataggio (non solo nel
  menu, per non essere scavalcato da due form aperti insieme): un
  tentativo di doppia nomina viene rifiutato con messaggio esplicito.
- Per ogni candidato, se ha un'altra riunione istituzionale lo stesso
  giorno immediatamente prima o dopo lo scrutinio in corso, viene
  mostrata con orario e classe (es. "08:45 2A AFM →"). Non cambia
  l'ordine dei candidati (il punteggio esistente resta invariato), è
  solo un'informazione in più.

Verificato: 110/110 template passano il parser Jinja; test end-to-end
con dati reali (copia locale del database) — nominato un sostituto per
un assente, confermato che sparisce dal menu del secondo restando
selezionato nel proprio; forzato un tentativo di doppia nomina via POST
diretto, rifiutato correttamente; confermata la visualizzazione
"riunione successiva" per un candidato con un altro scrutinio a seguire.

## Sessione 50 — Avviso per sezioni future non collegate ai permessi (Cowork)

**Contesto:** l'utente ha chiesto se le sezioni aggiunte in futuro
entrano da sole nella matrice permessi. Risposta onesta: no — resta un
passo manuale (registrare la sezione + mappare blueprint/endpoint), e
se me lo dimentico la parte nuova resta aperta a chiunque sia loggato
senza che sia visibile a nessuno. Un commit: `0d77a7a`.

Spostate le mappe blueprint/endpoint → sezione da `app.py` a
`models/permesso_ruolo.py` (unica fonte, non più duplicata) e aggiunta
`blueprint_non_mappati(app)`: confronta i blueprint registrati nell'app
con quelli conosciuti dalle mappe (sezione configurabile, dsga_only, o
intenzionalmente aperti) e restituisce quelli rimasti fuori. La pagina
Permessi mostra un avviso con l'elenco, se non vuoto — non risolve da
solo il collegamento mancante, ma lo rende visibile al DS invece che
silenzioso.

Verificato: 110/110 template passano il parser Jinja; con l'app reale
la lista risulta vuota; simulato un blueprint fittizio non collegato e
confermato che compare nell'avviso, sia via codice sia con controllo
visivo della pagina.

## Sessione 49 — Matrice permessi configurabile dal DS (Cowork)

**Contesto:** dopo l'audit ruoli/permessi (chiesto di "fare il punto"
sui profili previsti e sulla possibilità di visualizzare/modificare i
dati), emerso che il controllo esistente era per-blueprint intero (un
solo permesso per l'intera sezione, niente distinzione lettura/
scrittura) e che 13 sezioni non avevano alcun controllo di ruolo.
Presentata una matrice di correzione (ds/dsga/collaboratore/segreteria
× sezione → visualizza/modifica/esclusa); l'utente ha proposto di non
fissarla nel codice ma di renderla una pagina di configurazione in
Impostazioni, riservata al DS. Un commit: `5985f85` (rebasato sopra il
lavoro in parallelo di un'altra sessione, Task 47/etichette
tipo_contratto — nessun conflitto).

- Nuova tabella `permessi_ruolo` (`models/permesso_ruolo.py`): 14
  sezioni × 3 ruoli configurabili (ds, collaboratore, segreteria) × 3
  livelli. DSGA resta bypass hardcoded (accesso pieno sempre, come
  già era con `'tutto'` in `PERMESSI`); ruolo `display` non passa da
  questa matrice — redirect fisso a `/display` sia dopo il login sia
  da `check_auth` per qualunque altro endpoint, "vede solo quella
  pagina e nient'altro" come richiesto esplicitamente. Nessuno dei due
  è modificabile dalla pagina, apposta: evita che una configurazione
  sbagliata blocchi l'intera app o l'unico ruolo che potrebbe
  correggerla.
- `app.py` `check_auth`: la vecchia mappa blueprint→permesso (un solo
  permesso, nessuna distinzione GET/POST) sostituita da
  blueprint→sezione + una manciata di override per endpoint dove un
  blueprint contiene più sezioni concettuali (es. `attivita_ist` ha
  sia "Attività istituzionali" che "Dipartimenti"; `incarichi` ha sia
  "Assegna incarichi" che, per due route, "Dati istituto"). A parità
  di sezione, il livello "visualizza" ora blocca davvero le richieste
  non-GET — prima poteva comunque scrivere, il controllo non
  distingueva. `sync`/`sync_conflitti` restano hardcoded dsga_only
  (cancellano/ricreano dati).
- Pagina `/impostazioni/permessi`: riservata **letteralmente** al
  ruolo `ds` (non tramite il sistema di permessi normale — nemmeno il
  DSGA può aprirla, scelta esplicita dell'utente). Matrice mostrata
  come tabella con un `<select>` colorato per cella.
- Voci di nav e card di Impostazioni nascoste per sezione (nuovo
  helper Jinja `puo_vedere(sezione)`) — non è il controllo di sicurezza
  (quello resta `check_auth`, vale anche per URL digitati a mano), ma
  evita che un ruolo veda in menu qualcosa che non può aprire. Bug
  trovato e corretto in verifica: l'hub `/impostazioni` stesso
  ereditava di default la sezione "istituto" (esclusa) dal suo
  blueprint, bloccando l'accesso alla pagina anche solo per vederne le
  card permesse — serviva un override esplicito a "nessun cancello".

Verificato: 110/110 template passano il parser Jinja; test end-to-end
via `test_client` per ognuno dei 4 ruoli configurabili + dsga +
display (login, redirect display, blocco GET/POST secondo livello,
hub Impostazioni raggiungibile da tutti, pagina Permessi riservata al
solo ds anche per il dsga); salvataggio della matrice con effetto
immediato verificato nella stessa sessione (un cambio da "visualizza"
a "modifica" sblocca subito la POST corrispondente); controllo visivo
della pagina Permessi e della nav filtrata con un utente di prova
ruolo ds.

**Aggiornamento Task 47 — punteggio candidati sostituzione scrutini
ricalibrato su prima/dopo e vicinanza oraria**: Roberto ha segnalato
che in `/attivita-ist/<id>/sostituzioni` i docenti suggeriti come
possibili sostituti comparivano sostanzialmente in ordine alfabetico
e capitava di vedere in buona posizione un docente con un'altra
riunione lontana (es. nel pomeriggio) mentre lo scrutinio da coprire
era di mattina.

Causa: `_score_candidato()` in `routes/attivita_ist.py` assegnava lo
stesso punteggio fisso (30) a **qualunque** docente con un'altra
riunione quel giorno, senza distinguere se la riunione fosse prima o
dopo lo scrutinio né quanto fosse vicina in orario — per questo, a
parità di punteggio, l'ordine finale ricadeva sul cognome (ordine di
`candidati_base`).

Ricalibrato lo score, usando i dati (`riun_prec`/`riun_succ`) già
calcolati da `_riunione_prec_succ()` — già mostrati in pagina, solo
non usati per l'ordinamento:
- Stessa materia → 10, stesso dipartimento → 20 (invariato).
- **Riunione prima** dello scrutinio (già a scuola, la scelta più
  comoda) → punteggio 21–25, più vicina nel tempo = più in alto.
- **Riunione dopo** → punteggio 26–30, stessa logica di vicinanza,
  ma sempre dopo "riunione prima" a parità di condizioni.
- Nessun'altra riunione quel giorno → 50 (invariato).
La soglia usata dal template per l'etichetta "③ riunione"
(`score <= 30`) restava valida senza toccare `sostituzioni_scrutinio.html`.

Verificato su copia isolata del database reale con due scrutini
reali del 6/6/2026: per uno scrutinio delle 10:30–11:15, i candidati
con riunione alle 11:15 (subito dopo) sono comparsi prima di quelli
con riunione alle 12:45 (più lontana); per uno scrutinio delle
14:45–15:30, i candidati con riunione conclusa proprio alle 14:45
(subito prima, quindi già a scuola) sono comparsi in cima, davanti a
quelli con riunione solo dopo — comportamento corretto secondo la
richiesta di Roberto.

**Aggiornamento Task 47 — IRC incluso in CONTRATTI_OK, rinomina
etichette tipo_contratto, controllo indisponibilità in Presenze**:
Roberto ha corretto tre punti dopo la voce precedente.

1. **IRC ha contratto fino al 31 agosto.** L'aggiunta di IRC a
   `CONTRATTI_OK` nella voce precedente non era un effetto collaterale
   da valutare: è corretta. Confermato, nessuna ulteriore modifica
   necessaria (il valore era già stato aggiunto). Beneficio indiretto:
   la stessa costante è condivisa con `routes/recupero_agosto.py`
   (disponibilità docenti per le prove di recupero di agosto), quindi
   corregge lo stesso problema anche lì.

2. **Le etichette "Supplente breve" e "TD fino a GS" erano scambiate.**
   Il valore interno `supplente` è in realtà il contratto prorogato
   d'ufficio (CCNL) fino al giorno degli scrutini → va etichettato
   "TD fino a GS". Il valore interno `TD_GS` è invece il contratto a
   termine che si ferma esattamente al 30 giugno, senza proroga → va
   etichettato "TD 30 giugno". **Scelta deliberata: solo le etichette
   mostrate in interfaccia sono cambiate, i valori salvati nel database
   (`supplente`, `TD_GS`) restano identici** — non serve nessuna
   migrazione dati, perché nessun docente reale cambia categoria: è
   sempre stato solo un problema di come veniva scritto in schermo il
   nome del contratto, non di quali docenti vi appartenessero. Creato
   `models/docente.py::TIPO_CONTRATTO_LABELS` come unica fonte di
   verità (dict valore→etichetta) e proprietà `Docente.tipo_contratto_label`;
   iniettato globalmente via context processor in `app.py`. Aggiornati
   tutti i punti che mostravano l'etichetta grezza: `templates/docenti.html`,
   `templates/docente_form.html` (dropdown ora generato dal dict),
   `templates/impostazione_anno/docenti_anno.html` (dropdown con opzione
   aggiuntiva `ap_entrante` non nel dict condiviso, corretto a mano),
   `templates/docenti/esporta_dati.html`, `templates/report/singolo.html`,
   `templates/report/singolo_print.html`, `templates/banca_ore/singolo.html`,
   `routes/export_xlsx.py` (due export xlsx). Verificato su copia
   isolata: `/docenti` e `/docenti/nuovo` mostrano "TD 30 giugno" e
   "TD fino a GS" correttamente.

3. **Controllo indisponibilità in Attività Istituzionali — mancava
   davvero.** Verificato che assenze e permessi sono già coperti (in
   Caronte i permessi sono righe di `Assenza` con `motivo` specifico:
   permesso_orario/personale/sindacale/retribuito — la query esistente
   su `Assenza.query.filter_by(data=evento.data)` li intercetta già,
   sia in `_auto_presenze()` che in `presenze()`). Il modello
   `Indisponibilita` (colloqui/consiglio/uscita/progetto/gara/
   formazione/altro), invece, pur usato in molti altri moduli
   dell'app, non era mai stato collegato ad Attività Istituzionali.
   Aggiunta in `routes/attivita_ist.py::presenze()` una query
   `Indisponibilita.query.filter_by(data=evento.data)` (dict
   `indisponibilita_giorno`, per gestire eventuali indisponibilità
   multiple nello stesso giorno), passata al template. In
   `presenze.html` aggiunto un badge dedicato (`.badge-indisponibile`,
   colore distinto dal rosso delle assenze e dal giallo del "non più in
   servizio") che mostra il/i motivo/i accanto al nome del docente — è
   solo un avviso informativo, non esclude dalla convocazione (a
   differenza delle assenze/non-in-servizio), perché un'indisponibilità
   dichiarata non impedisce di forma la partecipazione, va solo
   verificata come possibile conflitto.

   Verificato su copia isolata del database reale: trovato un caso
   reale di sovrapposizione (evento id 46, "Scrutinio finale CAT V A"
   del 6/6/2026, docente PALERMO Giuseppe con indisponibilità
   "progetto" nello stesso giorno) — il badge compare correttamente
   nella pagina Presenze.

**Aggiornamento Task 47 — fine contratto (TD_GS/supplenti brevi) per gli
eventi di luglio/agosto**: Roberto ha fatto notare che la correzione
precedente (esclusione docenti non in servizio dai partecipanti
preventivati) non bastava per gli scrutini del 31 agosto: TI e
TD_annuale restano in servizio fino al 31 agosto compreso, ma i
supplenti brevi ("scadenza contratto fine delle lezioni") e i TD fino
a GS (**GS = Giorno degli Scrutini**, CCNL — il contratto viene
prorogato dal termine delle lezioni fino al giorno conclusivo degli
scrutini, cioè fine giugno) non lo sono più. Verificato che questa
distinzione NON era considerata.

Trovato che questa esatta regola esiste già altrove nell'app, per uno
scopo diverso: `routes/recupero_costanti.py::CONTRATTI_OK = ('TI',
'TD_annuale')`, usata da `routes/recupero_agosto.py` per decidere chi
è disponibile per le prove di recupero di agosto. Invece di
duplicarla, creata `routes/attivita_ist.py::_non_in_servizio_per_data()`
che combina: (1) la stessa esclusione per anno scolastico di prima
(uscita/AP uscente/aspettativa), sempre attiva; (2) **solo per eventi
datati luglio o agosto**, esclude anche chi ha `tipo_contratto` non in
`CONTRATTI_OK` (quindi TD_GS, supplente, e — conseguenza diretta del
riuso della stessa costante — anche IRC, che nell'app non rientra in
CONTRATTI_OK: segnalato a Roberto come effetto collaterale da valutare,
non deciso qui). Sia `_preset_partecipanti()` che il badge "non più in
servizio" in `presenze.html` usano ora questa funzione unica al posto
della sola `_docenti_non_in_servizio`.

Verificato su copia isolata del database reale: per un evento
fittizio del 31/8/2026 gli esclusi salgono da 10 (solo uscita/
aspettativa per l'anno 2025-2026, a cui appartiene il 31 agosto per
convenzione dell'app — vedi `_anno_scolastico()`, l'anno scolastico
cambia a settembre) a 34 (+24: 16 TD_GS + 6 supplenti + 2 IRC),
nessuna sovrapposizione tra i due gruppi. Trovato un caso reale in
`OrarioDocente`: il docente BADASA (contratto "supplente", classe 1A
CAT) risulta correttamente escluso dal preset di uno scrutinio
ipotetico del 31/8/2026 e correttamente incluso per lo stesso
scrutinio ipotetico all'8/6/2026 (quando il suo contratto era ancora
valido). Database reale non toccato.

**Aggiornamento Task 47 — numeri romani nell'import xlsx + esclusione
docenti non più in servizio dai partecipanti preventivati**:

1. `modules/import_piano_xlsx.py::_normalizza_classe_romana()` — la
   colonna Classe del file xlsx può contenere l'anno-corso in numero
   romano (es. "II A", "III"), come nel vecchio formato originale:
   viene ora convertito in numero arabo nel formato usato da Caronte
   (es. "2A", "3"), lasciando invariati i valori già in numeri arabi.
   Provato riconvertendo "AGOSTO_PIANO DELLE ATTIVITA_2025_26.xlsx"
   (vedi voce precedente): "II A" → "2A", "III" → "3", ecc.

2. Roberto ha chiesto se l'assegnazione automatica dei partecipanti
   (`_preset_partecipanti` in `routes/attivita_ist.py`) tenesse già
   conto dei docenti non più in servizio. Verificato che **no**: il
   filtro esistente controllava solo `Docente.attivo == True`, che
   però — come già documentato in `routes/docenti.py::
   _docenti_non_in_servizio` — non si aggiorna in tempo reale quando
   un docente viene segnalato in uscita (`segna_uscita` in
   `impostazione_anno.py` imposta solo `anno_scol_uscita`/
   `motivo_uscita`, il flag `attivo` passa a `False` solo al
   passaggio formale di cambio anno) né tiene conto di AP
   uscente/aspettativa (`status_presenza`). Confermato con un caso
   reale nel database (sola lettura, copia isolata): 34 docenti con
   `anno_scol_uscita='2026-2027'` risultavano comunque tra i
   partecipanti preventivati del Collegio dei docenti del 1°
   settembre 2026 (evento id 41, anno scolastico 2026-2027).

   Corretto `_preset_partecipanti()`: ora esclude, per tutti i tipi di
   evento, i docenti restituiti da `_docenti_non_in_servizio(anno)`
   calcolato sull'anno scolastico della **data dell'evento** (non
   "oggi" — un Consiglio di marzo 2027 guarda chi è in servizio nel
   2026/27). Verificato: sullo stesso evento fittizio (Collegio
   7/9/2026, 93 docenti attivi) i partecipanti preventivati scendono
   correttamente da 93 a 57 (esclusi i 34 usciti + 2 ap_uscente/
   aspettativa).

   Aggiunta anche una segnalazione visiva in
   `templates/attivita_ist/presenze.html` (nuovo badge giallo "non più
   in servizio") per i partecipanti **già presenti** in un evento
   (es. eventi importati prima di questa correzione, o aggiunti a
   mano) che risultano non più in servizio alla data dell'evento —
   con link diretto a "nomina sostituto" quando l'evento è uno
   scrutinio (route `sostituzione_scrutinio` già esistente). Verificato
   sull'evento reale id 41: 34 badge mostrati, uno per ciascuno dei 34
   docenti non in servizio tra i suoi partecipanti.

   Tutto verificato su copie isolate del database reale (mai scritto),
   con bypass login `CARONTE_SKIP_LOGIN=1` + `CARONTE_DEBUG=1` (nota:
   il bypass ora richiede **entrambe** le variabili, non più solo la
   prima — cambiato rispetto a quanto documentato nella voce
   precedente di questo stesso Task, verificato leggendo `app.py`
   aggiornato prima di ripetere i test).

## Sessione 48 — Audit larghezze colonne su tutte le tabelle dell'app (Cowork)

**Contesto:** segnalato che in `/utenti` la colonna "Nome" occupava
troppo spazio senza motivo; richiesta poi allargata a una verifica
sistematica di tutte le tabelle dell'app: colonne larghe adeguate al
contenuto, evitare il testo a capo dove non serve, distribuzione
equa dello spazio in eccesso. Un commit: `75d080a`.

Causa del problema originale: in `utenti/lista.html` la colonna
"Nome" era l'unica senza `width` esplicita tra colonne tutte
fissate — assorbiva tutto lo spazio residuo della riga. Sistemata
dando larghezze esplicite a tutte le colonne.

Per l'audit completo: lanciata un'esplorazione dedicata su tutte le
53 tabelle dell'app (grep `<table`), per classificare ogni colonna —
larghezza già impostata o no, contenuto breve o testo libero
(note/descrizioni/elenchi) che deve poter andare su più righe.

Cambio di base ([base.html](templates/base.html)): le celle di
tabella ora hanno `white-space:nowrap` di default (prima l'ellipsis
era dichiarata ma senza `nowrap` non aveva alcun effetto — il testo
andava comunque a capo). Aggiunta la classe di escape `.wrap` per le
colonne che devono restare multi-riga.

Applicato in ~25 file: `.wrap` sulle colonne di testo libero (note,
descrizioni, elenchi di classi/materie/accompagnatori), larghezza
esplicita sulle colonne corte che assorbivano lo spazio al posto
della colonna giusta (stesso bug della segnalazione iniziale:
Nome/Cognome docenti, Docente, Nome classe di concorso).

Lasciate invariate le celle già con troncamento manuale
(`dashboard.html`, `agenda.html`, `recupero/agosto_calendario.html`)
e i 3 template standalone che non estendono base.html (`privacy.html`,
`docenti/esporta_dati.html`, `report/singolo_print.html`), su cui la
nuova regola CSS non ha effetto comunque.

**Caso critico trovato durante l'audit**: `ricerca/risultati.html` ha
5 tabelle con una sola cella per riga contenente l'intera riga di
risultato composta — senza `.wrap` la nuova regola di default
avrebbe troncato quasi tutto il contenuto a una riga. Corretto.

Verificato: 109/109 template passano il parser Jinja; rendering via
test_client su tutte le pagine toccate; controllo visivo su
`/utenti`, `/docenti`, `/attivita`, `/ricerca` (caso critico),
`/impostazione-anno/organico`, `/recupero/gruppi`.

## Sessione 47 — Checkbox rotta e link di ritorno mancante in utenti/modifica (Cowork)

**Contesto:** segnalati due problemi su `/utenti/<id>/modifica`: la
checkbox "Utente attivo" non rispettava i bordi, e la pagina non aveva
un modo per tornare all'elenco utenti. Un commit: `4ec672e`.

- La checkbox: causa era la regola globale `.form-group input`
  ([base.html](templates/base.html)) — pensata per campi di testo
  (width:100%, padding, bordo, border-radius) ma applicata a QUALUNQUE
  `input` dentro `.form-group`, checkbox incluse, gonfiandola in un
  riquadro enorme che sbordava dalla label "Utente attivo". Verificato
  che nessun'altra pagina con checkbox in `.form-group` era colpita
  (solo utenti/form.html ha quella struttura). Aggiunta un'eccezione
  CSS per `input[type=checkbox/radio]` che ripristina l'aspetto
  nativo — vale per tutta l'app, non solo per questa pagina.
- Link di ritorno: la pagina aveva solo un "Annulla" in fondo al form
  (facile da perdere, specie con la checkbox rotta che faceva sembrare
  la pagina troncata). Aggiunto il link "← Utenti" in cima, stesso
  pattern usato nel resto dell'app.

Verificato: 109/109 template passano il parser Jinja; controllo
visivo su utenti/1/modifica — checkbox nativa, link di ritorno visibile.

## Sessione 46 — Nav bar: omologato il riempimento di "Registra assenza" (Cowork)

**Contesto:** il pulsante "Registra assenza" aveva un pill rosso pieno
(`background: rgba(220,38,38,.35)`) che lo faceva risaltare troppo
rispetto al resto della barra, ora sfaccettata. Un commit: `4544b80`.

Rimosso lo sfondo dedicato, resta solo il grassetto per l'enfasi (è
l'azione più frequente) — stesso comportamento hover delle altre voci.

## Sessione 45 — Nav bar: testo bianco pieno, non più "impastato" (Cowork)

**Contesto:** l'utente ha precisato meglio il problema della Sessione
44: le icone SVG erano bianche e nitide, ma il testo risultava grigio.
Un commit: `26b65ca`.

Causa: l'alone a più livelli (text-shadow con raggio fino a 5px)
risolveva il contrasto ma, a dimensione piccola (.93rem), lo
sfocamento si fondeva con i bordi anti-aliasati delle lettere — le
icone non ne risentivano perché `filter:drop-shadow` non tocca la
forma (sfoca una copia della sagoma dietro, non i bordi del disegno
stesso, a differenza di `text-shadow` che sfoca "dentro" al glifo).

Semplificato: colore portato a bianco pieno (era rgba(255,255,255,.96)
— la trasparenza residua contribuiva anch'essa all'effetto lavato),
text-shadow ridotta a un solo livello stretto (`0 1px 2px`, niente più
bagliore a raggio largo). Stesso trattamento per brand-nome,
brand-datetime, nav-user. Icone (.nav-ic) invariate.

Verificato: 109/109 template passano il parser Jinja; controllo
visivo a 1600px — testo nitido e bianco come le icone.

## Sessione 44 — Nav bar: alone scuro invece di ombra singola (Cowork)

**Contesto:** le Sessioni 42-43 non bastavano — l'utente vedeva ancora
alcune voci (Display, Impostazioni, Guida) più sbiadite delle altre.
Un commit: `0b74525`.

Verificato che il CSS calcolato era identico per tutte le voci (stesso
colore, stessa ombra) — non era uno stile diverso. Causa reale: la
mesh sotto è casuale faccetta per faccetta, e `preserveAspectRatio=
"xMidYMid slice"` la ritaglia diversamente a seconda della risoluzione
dello schermo — a seconda della larghezza, una voce diversa può
capitare proprio sopra una faccetta più chiara. Confermato provando a
1440px/1920px: il pattern di quali voci sembravano sbiadite cambiava
ogni volta, non erano mai le stesse.

Una singola ombra morbida non poteva bastare contro un caso peggiore
imprevedibile. Sostituita con un vero alone (più livelli di
text-shadow/drop-shadow sovrapposti, alta opacità, raggio piccolo) su
`nav a`, `.brand-nome`, `.brand-datetime`, `.nav-user` e `.nav-ic` —
garantisce contrasto qualunque cosa capiti dietro, invece di sperare
che la faccetta in quel punto sia abbastanza scura.

Verificato: 109/109 template passano il parser Jinja; controllo
visivo a tre larghezze (1440/1600/1920px) — voci uniformemente
leggibili in tutte.

## Sessione 43 — Testo e icone nav bar ancora più solidi (Cowork)

**Contesto:** l'ombra della Sessione 42 non bastava — l'utente notava
che le voci con menù a tendina (Attività, Orario, utente) sembravano
più "piene" delle altre. Causa reale: le icone SVG (tratti, non testo)
non ricevono `text-shadow`, quindi restavano senza protezione di
contrasto, a un'opacità effettiva di ~74% (90% propria × 82% ereditata
dal colore del link). La differenza percepita tra voci era probabile
solo un effetto della mesh che varia punto per punto, non uno stile
diverso. Un commit: `e830b5e`.

- `nav a`: colore da 82% a 96% di opacità, text-shadow rinforzata.
- `.nav-ic`: rimossa l'opacity:.9 propria, aggiunto un
  `filter:drop-shadow` equivalente alla text-shadow (le icone SVG non
  la ricevono altrimenti).

Verificato: 109/109 template passano il parser Jinja; controllo
visivo — tutte le voci nav, con o senza dropdown, ora uniformemente
leggibili.

## Sessione 42 — Testo nav bar sopra la mesh sfaccettata (Cowork)

**Contesto:** dopo la Sessione 41, il testo della nav in alcuni punti
risultava "opacizzato" — il bianco semi-trasparente scelto per la
gerarchia visiva (brand-datetime, nav a, nav-user) perdeva contrasto
dove la mesh sottostante era più chiara. Un commit: `1fc847f`.

Aggiunta un'ombra leggera (`text-shadow: 0 1px 3px rgba(0,0,0,.55)`) a
brand-nome, brand-datetime, nav a e nav-user: il testo resta nitido
qualunque faccetta capiti dietro, senza toccare i colori/opacità già
scelti per la gerarchia (bianco pieno per il brand, più trasparente per
sottotitoli e link secondari).

## Sessione 41 — Nav bar sfaccettata + regolazioni Display (Cowork)

**Contesto:** a seguire della Sessione 40, tre richieste: box del
Display meno trasparenti, sfondo Display ancora più discreto (.28→.18),
e uno sfondo sfaccettato anche sulla nav bar (come login) per dare
tridimensionalità. Un commit: `c47ad71`.

- Box Display: opacità del fondo colorato portata da 10-12% a 22-24%
  — leggono come pannelli pieni invece che velature (è uno schermo
  da corridoio, va letto a distanza). Sfondo low-poly abbassato a
  `.18` per dare risalto ai box ora più solidi.
- Nav bar: nuova mesh low-poly (`_nav_bg.html`), stessa tecnica di
  login/display ma range cromatico più stretto e opacità `.5` — un
  rilievo discreto, non un pattern che compete con testo/icone.
  Applicato subito il fix imparato nella Sessione 40: niente z-index
  negativo, la mesh è il primo figlio di `<nav>` e l'ordine del DOM
  basta a tenerla dietro a brand/link. Aggiunto `overflow:hidden` su
  nav; verificato che i menu a tendina (position:fixed, non absolute)
  non vengono ritagliati da quell'overflow.

Verificato: 109/109 template passano il parser Jinja; controllo
visivo su dashboard-anno (mesh nav visibile, dropdown "Attività"
aperto e non tagliato) e su display?data=2026-05-28.

## Sessione 40 — Bug dietro lo sfondo sfaccettato "blando" del Display (Cowork)

**Contesto:** l'utente ha segnalato che lo sfondo low-poly del Display
restava troppo blando anche con i box informativi sopra (verificato sul
28/05/2026 con dati reali). Un commit: `05a6aae`.

Non era un problema di taratura colori: `.bg-lowpoly` usava
`position:fixed; z-index:-1`, e in questo motore browser un elemento a
z-index negativo viene dipinto SOTTO lo sfondo solido di `html, body`
(`background:var(--bg)`), che lo copriva quasi interamente — si vedeva
solo una sottile striscia residua. Confermato rendendo temporaneamente
trasparente `html/body`: il pattern è apparso interamente, in modo
vivido. Cambiare colori/opacità del pattern (provate più iterazioni:
v2, v3, v4 con distribuzioni di colore diverse) non poteva risolverlo
da solo, perché il layer restava comunque sotto un canvas opaco.

Fix strutturale: rimosso lo z-index negativo. Essendo `.bg-lowpoly` il
primo figlio di `<body>` e restando `position:fixed`, l'ordine del DOM
da solo lo mette dietro a header/banner/contenuto/footer (dichiarati
dopo) — non serve z-index negativo, che in questo motore finisce sotto
il canvas invece che sopra.

Rigenerata anche la mesh (era concentrata per il 90% nei toni più
scuri, con il gradiente vivace schiacciato in una striscia) con una
distribuzione di colore uniforme su tutta la superficie. Opacità
tarata a `.28` bilanciando con i box informativi (sfondi rgba al
10-12%, quindi semi-trasparenti): a opacità più alta (testate .9, .5,
.4, .2) il testo nei box perdeva leggibilità.

Verificato: 108/108 template passano il parser Jinja; controllo
visivo sul 28/05/2026 con dati reali (copia locale del database),
sia nella parte alta della pagina dove finiscono i box sia scorrendo
più in basso.

## Sessione 39 — Risolta la sovrapposizione "Incarichi docenti" / "Incarichi per docente" (Cowork)

**Contesto:** l'utente ha notato due voci quasi identiche in
Impostazioni che aprivano pagine diverse. Un commit: `79094cd`.

Analisi: non erano duplicati, ma due viste sugli stessi dati
(`IncaricaDocente`) — `incarichi.index` è la gestione (assegna/elimina,
raggruppata per categoria), `dashboard_anno.incarichi_docenti` era una
vista di sola lettura raggruppata per docente. Il problema era la UI:
stessa icona, nomi quasi identici, stesso livello in Impostazioni.

Scelta (tra 3 opzioni proposte, l'utente ha scelto una combinazione):
spostata la vista di sola lettura da Impostazioni a Report (dove
concettualmente appartiene, essendo un report e non un'impostazione),
mantenendola raggiungibile come voce secondaria sia dalla pagina di
gestione sia viceversa:
- Route: `/incarichi-docenti` (dashboard_anno) → `/report/incarichi-docenti`
  (report). Verificato prima di spostare che tutti i ruoli con accesso
  a dashboard_anno (nessuna restrizione) hanno anche `report_r` —
  nessuna perdita di accesso per nessun ruolo.
- Rimossa la voce duplicata da Impostazioni (resta solo "Incarichi
  docenti" → gestione).
- Aggiunti link incrociati: "Vista per docente" nella pagina di
  gestione, "Gestisci incarichi" nella vista di sola lettura.
- Aggiunta una card nella tab "Report Segreteria".

**Bug scoperto per caso**: verificando la card "Esporta tutti i report
PDF" in report/index.html, un `onclick="this.textContent='{{ icon(...)
}} ...'"` inseriva l'SVG (con i suoi doppi apici) dentro un attributo
HTML già delimitato da doppi apici, troncandolo a metà — il resto del
markup "sbordava" come testo visibile nel pulsante. Bug preesistente,
non introdotto da questa modifica. Corretto rimuovendo l'icona da
quel punto (un attributo onclick non può contenere HTML/SVG).

Verificato: 108/108 template passano il parser Jinja; rendering via
test_client su tutte le pagine toccate; controllo visivo dei link
incrociati in entrambe le direzioni.

## Sessione 38 — Allineamento nav bar + ultimi glifi/emoji (Cowork)

**Contesto:** su ulteriore segnalazione ("anche in nav bar non sembrano
ben allineati") e richiesta di proseguire con le sostituzioni rimaste.
Due commit: `a74ea98`, `2f1f391`.

### Allineamento nav bar (`a74ea98`)
`.nav-ic` centra l'icona nello span con `align-items:center`, ma lo
span stesso (inline-flex) viene posizionato dal browser secondo il suo
`vertical-align` di default (baseline) rispetto al testo del link — non
rispetto all'altezza maiuscola (cap-height) del testo. Misurato: il
centro dell'icona cadeva ~2.6px più in alto del centro reale delle
lettere maiuscole della nav (14.88px). Corretto con
`transform: translateY(2px)` su `.nav-ic`, portando lo scarto sotto 1px
(verificato via marker DOM). Interessa sia le voci di primo livello sia
le sottovoci dei menu a tendina (stessa classe).

### Ultimi glifi/emoji (`2f1f391`)
Aggiunte 2 icone (`triangle`, `pause`); sostituiti a mano gli ultimi 34
glifi in 18 file (✦→star, ⊘→forbidden, △→triangle, ⏸→pause), verificando
per ciascuno il contesto prima di applicare la modifica invece di una
regex globale (per non ripetere l'errore della Sessione 36). Lasciati
intenzionalmente: i glifi dentro `<option>` (non possono contenere SVG)
e il toggle ▶/▼ di `recupero/vincoli.html` (dinamico via JS, come già
per `dashboard.html`). Il `❌` di `attivita/form.html`, incorporato in
una stringa JS lato client, sostituito con `{{ icon('close', 10) }}`
inline nel template (processato comunque da Jinja lato server).

Verificato: 108/108 template passano il parser Jinja; rendering via
`test_client()` su tutte le pagine toccate.

## Sessione 37 — Allineamento verticale icone SVG (Cowork)

**Contesto:** su segnalazione dell'utente ("alcuni simboli non sono
allineati correttamente con il testo"), verifica sistematica
dell'allineamento di tutte le 47 icone di `_icons.html`. Un commit:
`697deba`.

Misurato per ciascuna icona lo scarto tra il fondo visivo
dell'inchiostro SVG e il fondo del bounding box (rendering su canvas +
scansione pixel non trasparenti). La maggioranza (cerchi, rettangoli,
triangoli) ha l'inchiostro quasi a contatto col bordo del viewBox
16x16, quindi il `vertical-align:-2px` condiviso le allinea bene alla
base del testo. 5 icone — forme simmetriche centrate nel box (frecce
orizzontali `arrow`/`arrow-left`, `check`, `chevron-down`,
`chevron-up`) — hanno invece l'inchiostro che si ferma 4-5px sopra il
bordo, e con lo stesso vertical-align sembravano "fluttuare" sopra la
riga di testo.

Corretto aumentando il vertical-align negativo solo per queste 5
(da -2px a valori tra -3.3px e -5.3px, calcolati per compensare lo
spazio vuoto interno di ciascuna). Le altre 42 non sono state toccate.

Verificato: 108/108 template passano il parser Jinja; pagina di test
con tutte le icone accanto a una riga di base (marker DOM span 0x0
con `vertical-align:baseline`) per confronto visivo prima/dopo;
controllo dal vivo su `docenti.html` e `cambi-quadro/nuovo`.

## Sessione 36 — Icone SVG: sostituzione globale glifi/emoji (Cowork)

**Contesto:** completamento della sostituzione icone iniziata in
precedenza (nav, H1 dei restyling, `docenti.html`/`docente_form.html`)
con un giro finale su tutti i glifi/emoji ancora presenti nell'app.
Un commit: `92ef3bf`.

Aggiunte 10 icone a `_icons.html` (chevron-down, package, plus,
hourglass, print, mail, school, forbidden, undo, swap) e sostituiti
687 glifi/emoji in 94 file con uno script di regex globale.

**Bug scoperto e corretto:** la sostituzione automatica aveva inserito
`{{ icon('x') }}` dentro stringhe che erano già argomenti di
un'espressione Jinja attiva (tuple di `<option>`, ternari, argomenti
di macro come `kpi()`/`step()`, dizionari letterali, fallback di
`.get()`) — Jinja non ammette `{{ }}` annidato dentro un altro
`{{ }}`/`{% %}`. 12 file coinvolti, corretti singolarmente:
- `cambio_modifica.html`, `modifica_supplenza.html`,
  `recupero/alunni.html` (opzione `<option>`): ripristinato il testo
  semplice, perché `<option>` non può contenere HTML/SVG.
- `attivita_ist/form.html`, `utenti/form.html`: ternario riscritto con
  l'operatore `~` per la concatenazione.
- `attivita_ist/import_piano_xlsx_preview.html`: `icon()` passata
  direttamente come valore di default a `.get('emoji', ...)` invece
  che dentro una stringa.
- `dashboard_anno/index.html`, `recupero/agosto_index.html`,
  `recupero/giugno_index.html`: `icon('x')` passata come argomento
  reale alle macro `kpi()`/`step()` invece che incorporata in una
  stringa tra virgolette.
- `rientro/calendario.html`, `recupero/agosto_calendario.html`,
  `recupero/calendario.html`: ternari di etichetta riscritti con `~`.
- `recupero/alunni.html` (dizionario `STATO_LABEL`): valori `icon()`
  diretti invece che stringhe con `{{ }}` annidato.

Verificato: tutti i 108 template passano `app.jinja_env.parse()`
(zero errori), rendering completo via `test_client()` con bypass di
login locale su tutte le pagine corrette (icone SVG presenti nel body,
19–29 per pagina a seconda del contenuto).

## Sessione 35 — Restyling colori: resto dell'app + export XLSX (Cowork)

**Contesto:** completamento diretto della Sessione 34, stessa
metodologia (mappatura indaco/viola/rosso/verde/ambra generici -> token
di `base.html`), estesa a tutte le sezioni rimanenti. Tre commit:
`e5d71d6`, `e350cf6`, `355fee2`.

### Web — sezioni rimanenti (`e5d71d6`, `e350cf6`)
Applicata la stessa mappatura già validata nella Sessione 34 a 37 file
in blocco (stessi pattern di colore ripetuti identici ovunque, quindi
sostituzione con uno script unico invece che file per file):
- Attività, Attività Istituzionali, Recupero (agosto/giugno), Rientro,
  Esami Integrativi, Incarichi, Cambio Anno — 33 file.
- Form di dettaglio: `assenza_form.html`, `docente_form.html`,
  `supplenza_form.html`, `modifica_assenza.html` — 4 file
  (`indisponibilita_form.html`, `cambio_form.html`,
  `cambio_modifica.html`, `utenti/form.html` non avevano colori da
  sostituire in questa mappatura).

**Caso particolare** in `docente_form.html`: un `loop.cycle` di 6 colori
distingue le materie insegnate da un docente — categoriale, come gli
indirizzi in Assegnazioni. Escluso da questa un colore (`#b45309`) che
sarebbe altrimenti coinciso con un altro già mappato sullo stesso
token (`--giallo`), per non ridurre la rotazione a 5 tonalità invece
di 6.

Verificato: sintassi Jinja corretta su tutti i file (35 nel primo giro,
via `app.jinja_env.parse()`), app avviata dal vivo più volte (Attività,
Recupero, Docenti/nuovo, Assenze/nuova, Incarichi) — nessun errore.

### Export XLSX (`355fee2`)
Gli export Excel (`openpyxl`, non CSS) avevano lo stesso problema dei
vecchi template: `routes/export_xlsx.py` definiva `BLU = '1e3a5f'`
(vecchio navy) come colore di default per intestazioni e titoli in
**tutti e 10** gli export dell'hub Impostazione Anno. Allineato a
`7a1c17` (lo stesso `--blu` di `base.html`); allineate anche
`BLU_L`/`VERD`/`VERD_L`/`ROSS`/`GIAL` ai valori esatti della palette
web.

Lo stesso `1e3a5f` è stato trovato *indipendentemente* (costanti locali
separate, non condivise) in altri 5 punti: `esami_integrativi.py`,
`recupero.py`, `recupero_export.py` (×2), `rientro.py`. Corretti tutti.

**Verifica reale, non solo a occhio**: script Python con `urllib` che fa
login (gestendo il token CSRF), scarica `/export/p1` per davvero, poi
riapre il file con `openpyxl` e legge il colore effettivo delle celle
— confermato `7a1c17` sulle intestazioni.

**Lasciata intatta**, in entrambi i giri: la palette categoriale per
indirizzo/passo (sia nei template web sia nell'export XLSX,
`export_xlsx.py` righe 327-332) — stessa scelta della Sessione 34, è
funzionale/di orientamento non di brand.

### Stato del restyling a fine sessione
Copertura pressoché completa: shell (`base.html`), login, tutte le
sezioni principali, form di dettaglio, export XLSX. Aperto solo se
Roberto vuole procedere: ridisegnare le due palette categoriali
(indirizzi, passi Impostazione Anno) mantenendole distinguibili ma
coerenti col resto — non ancora affrontato, richiede curare N tonalità
nuove invece di un semplice swap di token.

---

## Sessione 34 — Restyling completo: font, icona, login, colori sezione per sezione (Cowork)

**Contesto:** seguito diretto della Sessione 33. Dopo il debug critico,
Roberto ha chiesto di simulare un restyling estetico (skill
`ui-ux-pro-max` + `stop-slop`) partendo da mockup statici (Artifact) di
Dashboard, Impostazioni e Assegnazioni, poi di applicarlo davvero al
codice, sezione per sezione. Due commit: `a461326` (font/icona/sfondo,
già in Sessione 33) e `1b85523` (colori).

### Mockup e scelte di design (prima del codice)
- Esplorati due indirizzi tipografici via Artifact: **Fraunces + Karla**
  (caldo, editoriale) vs **Oswald + IBM Plex Sans** (tecnico, "quaderno
  Da Vinci" — titoli condensati stile cartiglio tecnico, Plex Sans
  condivide il disegno con Plex Mono già usato per i numeri). Scelto
  **Oswald + IBM Plex Sans**.
- Icona brand (`static/img/brand/caronte-icon.png`): aveva uno sfondo
  nero pieno dietro al disegno (verificato pixel per pixel, non un
  problema di visualizzazione). Ripulita: ora solo il tratto rosso,
  sfondo trasparente.
- Sfondo pagina: dal crema originale (`#f7f4ef`) a un grigio-azzurro
  tenue ("carta bollata", `#EDF0EE`) — il bordeaux del brand era già
  coerente con la nuova direzione, non toccato.

### Font locali, non più Google Fonts (`app.py:14` era gia' su questo, qui `base.html`/`login.html`)
- Oswald (titoli, tutti gli `h1`/`h2` via regola globale in
  `base.html`) e IBM Plex Sans (resto dell'interfaccia) scaricati e
  ospitati in `static/fonts/` — l'app funziona anche offline, niente
  più dipendenza da una CDN esterna.
- **Icona invisibile sulla barra**: scoperto e misurato (rapporto di
  contrasto WCAG) che un rosso scuro su una barra bordeaux e'
  otticamente illeggibile (~1.2:1) qualunque sfumatura di bordeaux si
  scelga — non era "il bordeaux sbagliato" ma rosso-su-rosso per
  definizione. Risolto con un cerchio di sfondo chiaro (`var(--blu-light)`)
  dietro l'icona in `nav .brand img`, indipendente dalla tonalità.

### Login (`templates/login.html`) — documento a sé, non estende `base.html`
- Era rimasta sul vecchio blu navy (`#0a1f35`/`#1a4a7a`): riportata al
  bordeaux del brand (variabili ripetute in chiaro, non essendoci
  `base.html` da ereditare).
- **Sfondo low-poly originale**: su richiesta di Roberto di uno stile
  "sfaccettato" simile a un'immagine stock che pero' non poteva essere
  usata (asset Adobe Stock a pagamento, watermark visibile) — generata
  invece una mesh triangolare proceduralmente in Python (126 poligoni,
  jitter casuale su una griglia, gradiente dal bordeaux scuro in alto
  al piu' acceso in basso), incorporata come SVG inline. Fallback: il
  gradiente piatto precedente resta come sfondo del `<body>` sotto
  l'SVG.
  Icona reale accanto al nome nel box di login; box reso semi-trasparente
  (`rgba(255,255,255,.88)` + `backdrop-filter: blur`) per lasciare
  intravedere la mesh restando leggibile.

### Colori: sezione per sezione (`1b85523`)
Sostituiti i colori "da SaaS generico" (soprattutto l'indaco `#6366f1`
e i residui del vecchio brand blu navy, es. `#1e3a5c`/`#1e3a8a`) con i
token già definiti in `base.html` (`--bronzo`, `--viola`, `--rosso`,
`--verde`, `--giallo`, `--blu`, `--blu-light`), pagina per pagina:
Impostazioni, Impostazione Anno, Assegnazioni, Dashboard, Docenti,
Report, Banca Ore, Aule (lista + mappa + override).

**Lasciati intatti, per scelta**:
- la palette per indirizzo in Assegnazioni (AFM blu, RIM blu chiaro,
  CAT ocra, LLI verde, LSC teal, LSP viola, LSU rosa, SOS grigio) e il
  sistema di colori per passo in Impostazione Anno (1-10, condiviso con
  `_step_nav.html`) — sono palette categoriali/di orientamento, non
  colori di brand: ridisegnarle e' una scelta a sé (curare N tonalità
  ancora distinguibili), non un semplice swap di token. Segnalato a
  Roberto come possibile prossimo passo, non fatto qui.
- blu informativi (`#0369a1` e affini), teal (badge SOSTEGNO, export
  dati GDPR) e bruno scuro (anonimizzazione GDPR): colori funzionali
  distinti che già si intonano al bordeaux, non residui del vecchio
  brand.

### Metodo di verifica
Ogni pagina toccata è stata controllata avviando davvero l'app in
locale (login incluso) e navigandola nel browser, non solo letta staticamente:
sintassi Jinja verificata via `app.jinja_env.parse()` prima ancora del
render completo (dati di test insufficienti in alcuni casi per popolare
tabelle pivot complesse — es. Assegnazioni con dati reali andrebbe
ricontrollata da Roberto).

### Cose ancora aperte
- Pagine minori non ancora toccate: form di dettaglio, export XLSX,
  moduli di Attività/Recupero/Rientro.
- Le due palette categoriali (indirizzo, passo) restano da ridisegnare
  se Roberto vuole completare la coerenza visiva.
- Verificare a occhio un export PDF vero (Sessione 33: WeasyPrint non
  testabile in sandbox Cowork, mancano le librerie di sistema).

---

## Sessione 33 — Debug architetturale critico, sicurezza, pulizia file morti, nav responsive (Cowork)

**Contesto:** su richiesta di Roberto, debug completo e critico
dell'architettura di CaronteApp da un ambiente Cowork (worktree
`debug-vicepresident-app-architecture-dbc44f`): file superflui,
sicurezza, efficacia grafica/logica/produttiva. Lavoro svolto a step,
con verifica visiva reale avviando l'app nel browser (login,
dashboard, piantina aule, desktop e mobile) ad ogni modifica, non solo
analisi statica del codice.

### Sicurezza (`app.py`)
- **`debug=True` hardcoded → spento di default.** Il debugger
  interattivo Werkzeug, con `host='0.0.0.0'` (necessario: più
  postazioni — segreteria/DSGA/DS — accedono alla stessa istanza in
  LAN), avrebbe permesso esecuzione di codice arbitrario a chiunque
  sulla rete. Ora attivabile solo con `CARONTE_DEBUG=1`.
  `use_reloader` resta sempre attivo (indipendente, nessun rischio
  analogo).
- **`SECRET_KEY` non più hardcoded nel sorgente.** Nuova
  `_ottieni_secret_key()`: usa `CARONTE_SECRET_KEY` se impostata,
  altrimenti legge/genera un `secret_key.txt` locale (permessi `600`,
  già in `.gitignore`, mai committato) al primo avvio su ogni
  macchina. Sostituisce la vecchia chiave fissa
  `'suplenzeapp-chiave-locale-2025'` nota a chiunque avesse accesso al
  repository. Effetto collaterale unico e voluto: le sessioni aperte
  con la vecchia chiave sono invalidate una tantum al primo avvio con
  questa modifica (richiede un nuovo login).
- **`CARONTE_SKIP_LOGIN=1` ora richiede anche `CARONTE_DEBUG=1`** per
  bypassare il login (prima bastava da sola): un `SKIP_LOGIN=1`
  dimenticato in una shell non disattiva più da solo l'autenticazione.
- **`TEMPLATES_AUTO_RELOAD = True` esplicito** — effetto collaterale
  scoperto durante il testing: spegnere `debug` di default spegne
  anche l'auto-reload dei template Jinja (che in Flask segue
  `app.debug`), quindi una modifica a un `.html` smetteva di vedersi
  senza riavviare il processo. Va impostato a parte.
- **Thread di sync automatico ([modules/auto_sync.py](modules/auto_sync.py))
  reso indipendente da Werkzeug.** La vecchia guardia contro il doppio
  avvio (`WERKZEUG_RUN_MAIN == 'true'`) funziona solo perché l'app usa
  sempre il reloader Werkzeug: con un server diverso (es. un ipotetico
  futuro gunicorn) il thread non sarebbe MAI partito, in silenzio,
  senza errori — non "duplicato" come inizialmente ipotizzato in
  fase di analisi, ma proprio assente. `create_app()` ha ora un
  parametro esplicito `avvio_con_reloader` (default `True`,
  comportamento identico ad oggi); un ipotetico entrypoint futuro
  diverso da `python3 app.py` dovrebbe chiamare
  `create_app(avvio_con_reloader=False)`.

### File superflui rimossi
- 5 immagini duplicate in `static/img/` (`CC - piano terra.jpg`, `CC -
  primo piano.jpg`, `CC - secondo piano.jpg`, `SS - sportivo.jpg`,
  `SS.jpg`) — copie byte-identiche delle versioni effettivamente usate
  (`cc_piano_terra.jpg` ecc.), non referenziate da nulla.
- `templates/impostazioni/stub.html` — placeholder orfano, nessuna
  route lo richiamava.
- `scripts/legacy/` — script "una tantum" già documentati come non più
  necessari (vedi README interno alla cartella), rimossi dal working
  tree (restano nella cronologia git).
- `storico_db/*.db.enc` — backup cifrati tolti dal tracking git
  (restano su disco), coerentemente con la policy già dichiarata nel
  `.gitignore` ("dati e backup locali" non versionati); aggiunta
  `storico_db/` al `.gitignore`.
- `CaronteApp_GDPR_Report.docx` spostato in `docs/` (prima nella root
  del repo insieme al codice sorgente).
- **Verificato, NON rimosso**: `concorrenza.py` — sembrava a rischio
  ma è effettivamente usato in `routes/docenti.py` e
  `routes/supplenze.py` (controllo di concorrenza ottimistica sui
  salvataggi). Da controllare in futuro solo se si notano
  sovrascritture silenziose su form non coperti da questo controllo.

### Grafica/UX (`templates/base.html`, `templates/login.html`)
- **Naming incoerente CaronteApp/SupplenzeApp** corretto: la pagina di
  login e il titolo di default della scheda browser dicevano ancora
  "SupplenzeApp"/"Supplenze" mentre l'header interno dice "CaronteApp".
- **Nav bar troncata a metà parola** ("Impo...") su risoluzioni
  desktop standard (1280px): corretto. Quando il contenuto della nav è
  comunque più largo dello spazio disponibile, compare ora una
  sfumatura sul bordo destro (classe `.nav-overflow`, calcolata via
  JS) a segnalare che c'è altro da scorrere — prima non c'era alcun
  indizio visivo.
- **Nav praticamente inutilizzabile su mobile**: aggiunto un vero menu
  hamburger (`.nav-toggle` + `.nav-links`, soglia 880px) — sotto la
  soglia mobile compare un pannello verticale con tutte le voci
  (Dashboard, Attività, Banca Ore, Report, Orario, Display,
  Impostazioni, Guida, ricerca, menu utente), prima raggiungibili solo
  scorrendo alla cieca dentro una striscia orizzontale di 68px senza
  alcun indizio che si potesse scorrere.
- **Bug scoperto e corretto durante il test**: il nome istituto lungo
  nell'header ("CaronteApp — Da Vinci Chiavenna") spingeva l'hamburger
  fuori dallo schermo su viewport strette (`flex-shrink:0` sul brand);
  ora si tronca con ellissi sotto gli 880px.
- Verificato via browser reale: login, dashboard, piantina aule
  interattiva (`/aule/mappa`, invariata e funzionante), apertura/
  chiusura menu hamburger e sottomenu (Attività, Orario) sia in
  viewport desktop (1400px) che mobile (375px).

### Verifiche fatte durante l'analisi (nessuna modifica)
- Test automatici: **51 funzioni di test in 10 file** sotto `tests/`
  (non "10 test" come una lettura superficiale del solo conteggio file
  suggeriva) — concentrati su autenticazione (10), banca ore/anno
  scolastico (9), bozze recupero agosto/giugno/rientro (6 ciascuno).
  Restano scoperte Assegnazioni, Export XLSX/PDF, Impostazione Anno.

### Debiti tecnici architetturali identificati, rimandati su richiesta di Roberto
Discussi ma non affrontati in questa sessione ("possiamo lasciarle lì
per un momento migliore"), da riprendere quando ci sarà un dolore
specifico su uno di questi, non per pulizia fine a se stessa:
1. Route "grasse" — business logic dentro `routes/` invece che in un
   livello di servizio separato (`impostazione_anno.py` a 1799 righe).
2. Migrazioni schema manuali — 40+ `ALTER TABLE` in una lista che
   cresce ad ogni avvio (`app.py::_auto_migrate`), niente Alembic né
   cronologia versionata.
3. Copertura di test parziale (vedi sopra).
4. 423 import fatti dentro le funzioni invece che in testa ai file.

**Nota per sessioni future in Cowork**: aggiornare questo file a fine
sessione (o quando si chiude un blocco di lavoro coerente), con lo
stesso stile — contesto, cosa è cambiato e perché, cosa resta aperto.

---

**Aggiornamento Task 47 — spostato il link import da Cambio Anno a Impostazioni**:
su richiesta di Roberto, il link a "Importa Piano delle Attività"
(`attivita_ist.import_piano_xlsx`) è stato tolto dalla pagina Cambio
Anno Scolastico e spostato in Impostazioni, nello stesso box
"◷︎ Orario" dove si trova "Importa / modifica orario"
(`templates/impostazioni/index.html`). Rimossa anche la dicitura
"Facoltativo" e il testo esplicativo che l'accompagnava in Cambio
Anno — resta solo la voce "Importa Piano delle Attività". Verificato
con richieste GET dirette (su copia isolata, non sul DB reale) che
`/impostazioni`, `/cambio-anno` e `/attivita-ist/import-xlsx`
rispondano ancora 200 dopo la modifica.

**Aggiornamento Task 47 — tabella "Attività già svolte" separata**:
su richiesta di Roberto, in `/attivita-ist` le attività con data
passata (rispetto a oggi) non compaiono più mescolate a quelle future
nella tabella principale: `routes/attivita_ist.py::lista()` ora divide
la query già ordinata in `eventi_futuri` (data ≥ oggi) ed
`eventi_passati` (data < oggi, mostrati dal più recente), passati
entrambi al template. `templates/attivita_ist/lista.html` estrae il
markup della tabella in una macro Jinja `tabella_eventi(eventi,
svolte=false)` per non duplicare colonne/azioni, e la richiama due
volte: la tabella principale (invariata) e una seconda sezione in
fondo alla pagina, "▤︎ Attività già svolte", con card a sfondo grigio
chiaro e righe a opacità ridotta (classe `.ev-row-svolta`, torna
opaca al passaggio del mouse). Restano invariate tutte le azioni
(Presenze/Modifica/Elimina) anche sulle righe svolte. La sezione non
compare affatto se non ci sono eventi passati. Verificato su copia
isolata del database reale (sola lettura) che la pagina risponda 200
e che la sezione "Attività già svolte" compaia correttamente per gli
eventi di giugno 2026 già trascorsi rispetto alla data odierna.

### Task 47 — Import automatico Piano Annuale delle Attività da .xlsx

Contesto: da Cowork, lavorando prima sul file
"PIANO DELLE ATTIVITA_2025_26.xlsx" (fuori da questo repo), è stato
definito un nuovo "standard" grafico/strutturale per il Piano Annuale
delle Attività (banner-giorno a piena larghezza colorato, blocchi
Consigli di Classe/GLO con righe-slot, righe-evento per Collegio/
Formazione/Incontri scuola-famiglia, righe-scadenza), poi generato un
modello vuoto di partenza e una proposta compilata per il 2026/27.
Terzo passo concordato con Roberto: verificare che questo standard sia
leggibile da CaronteApp e collegare l'import alla pagina Cambio Anno,
sostituendo la necessità di trascrivere a mano ogni anno gli eventi
nel codice (come fatto finora in `_import_piano_2025_26()`).

- **`modules/import_piano_xlsx.py`** (nuovo) — parser puro (nessun
  accesso al DB): `parse_piano_xlsx(file_bytes_o_path)` legge ogni
  foglio mensile riconoscendo i ruoli delle righe dal colore di
  riempimento della cella colonna "Attività" (banner blu = giorno,
  banner grigio-blu = titolo sezione Consigli/GLO **solo se** seguito
  da un banner-giorno, altrimenti banner puramente informativo e
  ignorato; riga grigia "ORDINE DEL GIORNO" = nota, riattaccata a
  posteriori a tutti gli slot già raccolti della sezione; riga verde
  "⚑" = scadenza, ignorata perché senza orario). La data si ricostruisce
  contando i giorni banner in ordine progressivo, facendo avanzare il
  mese nei fogli combinati (es. "NOVEMBRE-DICEMBRE") quando il numero
  del giorno torna indietro. Restituisce `{fogli, eventi, avvisi}`.
- **`routes/attivita_ist.py`** — nuova route
  `/attivita-ist/import-xlsx` (GET/POST) in due passi: upload → analisi
  e anteprima (conteggio eventi per tipo + tabella completa, eventi
  serializzati in un campo nascosto) → conferma esplicita prima di
  scrivere qualunque cosa nel DB. Stesso meccanismo di preset
  partecipanti già usato da `_import_piano_2025_26`. Controllo
  duplicati su tipo+data+titolo+classe+**ora_inizio** (l'ora_inizio è
  fondamentale: gli slot dei Consigli sono generici/non assegnati,
  quindi hanno tutti lo stesso titolo e classe=None nello stesso
  giorno — senza l'orario nella chiave, il 2°/3°/4° slot dello stesso
  giorno veniva scambiato per un doppione del 1° e scartato: bug
  trovato e corretto durante la verifica, prima di consegnare).
- **`templates/attivita_ist/import_piano_xlsx.html`** (nuovo, form di
  upload) e **`import_piano_xlsx_preview.html`** (nuovo, anteprima +
  conferma). Pulsante "Import piano da xlsx" in `lista.html` aggiornato
  per puntare qui (il vecchio import con dati fissi nel codice resta
  raggiungibile come "legacy" per il 2025/26, non più linkato dalla
  navigazione principale).
- **`templates/cambio_anno/index.html`** — aggiunta una card
  "Facoltativo — Importa Piano delle Attività" tra le operazioni A e B,
  con link alla nuova pagina.

**Verifica end-to-end**: eseguita su una copia completa e isolata
dell'app in `/tmp` (venv del Mac non utilizzabile in sandbox Linux,
reinstallate le dipendenze con pip nel sandbox), **mai sul
`database.db` reale**. Caricata la proposta 2026/27 (274 eventi
attesi): tutti riconosciuti correttamente (158 Consigli, 76 scrutini,
14 GLO, 6 formazione, 6 incontri famiglia, 5 Collegio, 5 altro/elezioni,
2 dipartimento/materia, 1 riunione referenti), partecipanti
pre-compilati, nota ODG allegata agli slot corretti. Verificata anche
l'idempotenza: ricaricando lo stesso file una seconda volta, tutti i
274 eventi vengono riconosciuti come già presenti e nessuno viene
duplicato. `database.db` reale confermato invariato (solo controlli
di sola lettura + `py_compile` sui file toccati).

**Nota**: questa sessione è stata condotta interamente da Cowork
(non da Claude Code), agendo sui file del repository via accesso
diretto alla cartella collegata (`/Users/Roberto/CaronteApp`); Roberto
non ha ancora verificato la funzionalità di persona sull'app reale.

**Aggiornamento — unificate le due griglie (eliminata la sovrapposizione)**:
Roberto ha chiarito che l'esclusione dei TD dalla griglia originale
era una scelta intenzionale in fase di progettazione, non una svista —
e che la sezione "Altri docenti" aggiunta sopra creava due meccanismi
paralleli per lo stesso scopo (segnalare un'uscita), col rischio di
comportamenti incoerenti tra i due. Su sua richiesta, scelta UNA sola
strada: la griglia "Docenti TI — gestione presenza" è stata allargata
a `docenti_gestione` (tutti i contratti, non solo TI) ed è stata
rimossa la sezione parallela "Altri docenti" e la query `altri_docenti`
introdotte in questo stesso Task. Dentro l'unica griglia risultante,
i pulsanti "→ AP" e "⏸ Asp." (mobilità sull'organico USR) restano
visibili solo per i TI, dato che non hanno senso per un TD; per i
non-TI il motivo di uscita proposto è "fine incarico" (`fine_td`)
invece di "pensionamento". La sezione "TD/Supplenti inseriti per
{{anno}}" resta invariata (informativa, per le nuove nomine) e la
griglia unificata esclude chi vi compare già, evitando di mostrare lo
stesso docente due volte. Corretta anche l'etichetta della sezione
"Uscite TI per {{anno}}" in "Uscite per {{anno}}": la query non era
mai stata limitata ai soli TI, solo il testo era fuorviante.

Verificato di nuovo end-to-end sulla copia di prova: Cantarella (TD)
compare nell'unica griglia con "fine incarico" tra le opzioni;
segnata come uscita, sparisce da `_docenti_per_anno`/`/docenti`;
compare in `/docenti?mostra=inattivi` CON il pulsante "Riattiva"
(perché il motivo non è pensionamento); un docente TI pensionato
(Buiarelli) resta invece senza possibilità di riattivazione, come
previsto. Riattivata Cantarella end-to-end (`POST
/docenti/<id>/riattiva`): `attivo` torna `True`, `anno_scol_uscita`
si azzera, `anno_scol_inizio` si aggiorna al nuovo anno di rientro.
`PRAGMA integrity_check` ok. Nessun riferimento residuo a
`ti_attivi`/`altri_docenti` nel codice.

**Nota — pagina Agenda irraggiungibile, ora collegata dalla Dashboard**:
Roberto ha notato (verificato insieme via Claude in Chrome sull'app
reale) che la pagina `/agenda`, pur completa e funzionante, non era
collegata da nessun link o pulsante — né in navbar né altrove — quindi
di fatto irraggiungibile per chiunque usasse l'app normalmente
(esisteva solo un form nascosto per l'azione di eliminazione gruppo,
richiamato dalla Dashboard, ma nessun link all'indice). Su richiesta
di Roberto, aggiunto un pulsante "📅 Agenda" nella riga di azioni della
Dashboard (`templates/dashboard.html`, accanto a "Prospetto"), non in
navbar. Aggiornato anche il testo del primo passo nella guida Agenda
(`modules/guida_content.py`) per riflettere la posizione reale del
pulsante. Verificato visivamente sull'app reale (Claude in Chrome,
non in sandbox): il pulsante compare in Dashboard, il click porta
correttamente a `/agenda` con i dati reali, e la pagina di Guida
mostra il testo aggiornato.

**Nota — correzione dati reali LSP Matematica 1ª/2ª**: dopo aver
spostato manualmente (Roberto, dal menu CC del passo 2) Matematica
1ª e 2ª di LSP da A-27 ad A-26, il badge "atipica" compariva comunque
— comportamento corretto ma non voluto in questo caso: il flag
confronta la CC scelta con `id_cc_default`, che restava congelato al
valore con cui la riga era stata creata (A-27), quindi il sistema la
vedeva come un'eccezione anche se per Roberto è ormai la norma.
Backup cifrato (`database_20260807_2010_pre_fix_lsp_atipica.db.enc`)
e aggiornate a mano le righe `piano_studi` id 117 e 118: `id_cc_default`
portato a 11 (A-26, come `id_classe_concorso`) e `atipica` a 0. Le
righe id 119-121 (Matematica 3ª/4ª/5ª LSP, l'eccezione vera e propria)
non sono state toccate — restano `id_cc_default=12 (A-27)`,
`atipica=1`, badge visibile. Verificato `PRAGMA integrity_check` ok e,
con un client di test contro l'app reale, che il badge non compaia più
per le righe 117/118 e resti presente per 119/120/121.

### Task 37 — Sezione Guida (FAQ + manuali scaricabili)

Richiesta di Roberto: una sezione della navbar dedicata a FAQ e
manuali d'uso, consultabile come pagine interattive e scaricabile
come guida PDF vera e propria. Ambito concordato: prima le funzioni
d'uso quotidiano (Dashboard, Assenze, Supplenze, Indisponibilità,
Agenda, Cambi quadro), pubblico segreteria/collaboratori (linguaggio
semplice, passo-passo), un PDF per singola sezione.

- **`modules/guida_content.py`** — unica fonte del contenuto (lista
  `SEZIONI`, una voce per sezione: slug, titolo, icona, riassunto,
  "a cosa serve", passi numerati, FAQ, nota "attenzione" opzionale).
  Sia la pagina HTML che il PDF leggono da qui, per non dover
  scrivere lo stesso testo due volte in due posti che prima o poi
  divergerebbero. Aggiungere una nuova sezione in futuro richiede solo
  di aggiungere una voce a questa lista, non tocca le route.
- **`routes/guida.py`** — blueprint `guida_bp`: `/guida` (indice a
  schede), `/guida/<slug>` (pagina interattiva con FAQ ad
  accordion), `/guida/<slug>/pdf` (genera il PDF con WeasyPrint,
  stesso pattern già in uso per l'export GDPR di
  `routes/docenti.py::esporta_dati`, incluso il fallback a HTML grezzo
  se WeasyPrint non è installato nell'ambiente). Non richiede permessi
  specifici (non è in `BLUEPRINT_PERMESSI`) — accessibile a chiunque
  sia loggato, di qualunque ruolo.
- **`templates/guida/index.html`** — indice a schede (icona +
  titolo + riassunto), stesso stile a card già in uso in
  Impostazioni.
- **`templates/guida/sezione.html`** — pagina di una sezione: menu
  laterale per passare alle altre, box "a cosa serve", passi numerati,
  nota di attenzione se presente, FAQ ad accordion (apri/chiudi al
  clic, senza libreria esterna), pulsante "Scarica PDF".
- **`templates/guida/pdf_sezione.html`** — versione stampabile
  (solo HTML/CSS inline, senza navbar) per WeasyPrint.
- **`templates/base.html`** — voce "Guida" in navbar, subito dopo
  Impostazioni.

Contenuto scritto verificando riga per riga il comportamento reale
del codice di ciascuna sezione (routes/assenze.py,
modules/assenze_registrazione.py, routes/supplenze.py,
routes/indisponibilita.py, routes/agenda.py, routes/cambi_quadro.py,
routes/dashboard.py) — non testo generico, ma passi che corrispondono
esattamente ai pulsanti e ai campi che l'utente vede.

Verificato: tutte le 6 pagine (`/guida`, le 6 sotto-pagine, i 6 PDF)
restituiscono 200 OK; uno slug inesistente dà 404; il link "Guida"
compare in navbar; ogni pagina PDF contiene effettivamente il testo
della sezione corrispondente. L'ambiente sandbox di Cowork non ha
WeasyPrint installato (stesso limite già noto per l'export GDPR) —
il fallback restituisce l'HTML stampabile invece di rompersi: nessun
problema atteso sul Mac di Roberto, dove WeasyPrint è già installato
e in uso per l'export GDPR.

### Task 36 — Bug reale: badge atipicità assente per CC con più materie insieme

Roberto ha segnalato che in LSP la materia A-12 (Lingua e letteratura
italiana + Storia insegnate insieme, anni 1-3, invece della A-11
normativa) non mostrava il badge "⚠︎️ Atipicità" nel passo 2 (Piano di
Studi), mentre A-26 (Matematica al posto di A-27, anni 3-5) lo
mostrava correttamente.

Causa: `templates/impostazione_anno/piano_studi.html` ha due layout
diversi per blocco CC — uno per CC con una sola materia (es. A-26 con
solo Matematica) che include il menu di cambio CC e il badge atipica,
e uno più compatto per CC con più materie insieme nella stessa colonna
(es. A-12 con Lingua + Storia) che NON conteneva affatto quel codice
— non un controllo sbagliato, proprio l'intero blocco mancava nel
ramo "multi-materia". Il flag `atipica` era comunque salvato
correttamente nel database (verificato: `True` su tutte le righe A-12
di Roberto) — il problema era solo di visualizzazione.

Aggiunto lo stesso menu CC + badge atipica + checkbox compresenza
anche al ramo multi-materia, identico a quello già presente nel ramo
a materia singola. Verificato: le 5 righe A-12 di LSP (id 46,47,48,59,60)
ora mostrano correttamente il select `cc_<id>` e il badge; verificato
anche che le pagine di altri indirizzi (LSC, CAT) continuino a
rendere correttamente (200 OK), nessuna regressione sul layout a
materia singola.

### Task 34 — Bug reale: TD/supplenti storici invisibili al passo 7 (uscite)

Roberto ha segnalato che in `/docenti` con anno 2026-2027 selezionato
comparivano ancora docenti che non dovrebbero più essere in servizio.
Primo controllo: la logica di filtro per anno (`_docenti_per_anno`)
funzionava correttamente — i docenti già segnati come usciti (con
`anno_scol_uscita`) venivano esclusi come previsto.

Roberto ha però messo il dito sul punto vero: **Cantarella (TD
annuale) non compariva da nessuna parte nella pagina Impostazione
Anno → passo 7** (`/impostazione-anno/docenti-anno`), quindi non era
nemmeno possibile segnarla come uscita da lì. Verificato: la pagina
costruisce 4 gruppi — TI presenti (`tipo_contratto == 'TI'`), uscite,
AP uscenti/entranti, e "TD/supplenti inseriti per questo anno"
(`anno_scol_inizio == anno`). Un docente non-TI assunto in un anno
precedente (spesso con `anno_scol_inizio` mai valorizzato, come
Cantarella) non rientra in NESSUno dei 4 gruppi: non è TI, e non è
stato "inserito per questo anno" — quindi resta strutturalmente
invisibile in quella pagina, per qualunque anno si selezioni. Risultato:
impossibile segnalarne l'uscita, e quindi rimane "in servizio" per
sempre secondo `/docenti` anche quando in realtà se n'è andato.
Interessa 29 docenti attivi su 93 (TD_annuale, TD_GS, supplente, IRC
con `anno_scol_inizio` non impostato).

Aggiunta una quinta lista in `routes/impostazione_anno.py::docenti_anno()`
— `altri_docenti`: non-TI, con `anno_scol_inizio` diverso dall'anno
selezionato (o NULL) e non già segnati come usciti per quell'anno.
Nuova sezione in `templates/impostazione_anno/docenti_anno.html`
("Altri docenti — TD/supplenti/IRC") con lo stesso meccanismo "✕︎
Esce" già usato per i TI, motivo di default `fine_td` (valore già
previsto dal modello ma mai esposto nel form).

Verificato in isolamento (harness sull'app reale con database.db
puntato a una copia in `/tmp`, mai sul file in uso): Cantarella ora
compare nella nuova sezione del passo 7; segnandola come uscita
2026-2027/fine_td, sparisce correttamente da `_docenti_per_anno` e da
`/docenti?anno=2026-2027`, e ricompare in `/docenti?mostra=inattivi`;
`PRAGMA integrity_check` ok; smoke test `/`, `/docenti`,
`/impostazione-anno/docenti-anno` tutti 200 OK. Il database reale non
è stato toccato — nessuna delle 29 anagrafiche coinvolte è stata
modificata: la decisione su chi segnare come uscito e con quale
motivo spetta a Roberto, pagina per pagina, dalla nuova sezione.

### Task 33 — Inserimento rapido incarichi: docente unico + multi-classe

Roberto ha segnalato due problemi nella pagina `/incarichi`: il form
permetteva un solo incarico alla volta anche quando serve assegnarne
più di uno allo stesso docente, e il menu a tendina dell'indirizzo
(nel contesto "classe") ripeteva ogni indirizzo una volta per ogni
sezione attiva (es. "AFM" comparso 3 volte se ci sono tre sezioni AFM).

Ridisegnato il form di `templates/incarichi/index.html` seguendo lo
stesso pattern multi-riga già usato in "Nuova indisponibilità": il
docente si seleziona una volta sola in alto, poi si possono aggiungere
più righe incarico con "+ Aggiungi incarico", ciascuna con il proprio
tipo, contesto e compenso. Per gli incarichi legati a una classe
(es. Coordinatore di classe), il contesto non è più una tripla di
tendine indirizzo/anno/sezione ma un elenco di checkbox delle classi
attive raggruppate per indirizzo (l'indirizzo compare una sola volta
come intestazione di gruppo, non ripetuto) — selezionandone più di una
si genera una nomina per ciascuna in un solo salvataggio.

`routes/incarichi.py::salva()` riscritta per accettare il nuovo formato
(`id_tipo[i]`, `classi[i][]`, `note[i]`, ecc.) e loopare su tutte le
righe e tutte le classi selezionate, creando una `IncaricaDocente` per
ogni combinazione; il controllo duplicati esistente (stesso
docente+tipo+contesto+anno) resta invariato, ora applicato per ogni
singola nomina generata.

Verificato in isolamento (harness Flask+SQLAlchemy puntato su una copia
del database in `/tmp`, mai sul file reale): pagina `/incarichi` non
contiene più il vecchio `<select name="indirizzo">` (conferma dedup);
un salvataggio con 1 riga "Coordinatore di classe" e 2 classi selezionate
genera correttamente 2 nomine distinte; un secondo invio identico non
crea doppioni (controllo duplicati ancora attivo); `PRAGMA
integrity_check` ok.

### Task 27 — Gestione elegante del mismatch CSRF (errorhandler)
Su ministudio l'errore "Bad Request: The CSRF tokens do not match" si
è ripresentato una seconda volta, questa volta senza altre schede/Mac
collegati. Confrontando (come la volta precedente) il token nel campo
nascosto del form con quello nel cookie di sessione inviato dal
browser: di nuovo diversi, ma con timestamp itsdangerous quasi
identici — segno di due richieste GET /login quasi simultanee (tipico
di un prefetch/precaricamento del browser al primissimo accesso su un
browser "pulito"), ciascuna con la propria sessione/token, non di un
problema di dati o di codice.

Invece di continuare a diagnosticare caso per caso un fenomeno che può
ripresentarsi per varie cause innocue (prefetch, sessione scaduta,
scheda vecchia), aggiunto un `@app.errorhandler(CSRFError)` in
`app.py`: invece della pagina bianca "Bad Request", ora si viene
rediretti al login (o alla pagina di provenienza) con un messaggio
chiaro ("La sessione era scaduta... riprova"). Non elimina la causa
di fondo (che resta innocua e specifica del browser/momento), ma la
rende un semplice "riprova" invece di un errore che sembra un guasto.

Verificato: pytest 51/51, simulazione diretta di un token CSRF non
valido su `/login` → redirect 302 pulito a `/login` invece
dell'eccezione grezza.

### Task 31 — Estensione sync automatico a indisponibilità

Seguito diretto del Task 46 (e delle sue 4 "aggiornamento" successive,
in particolare `creato_da` e l'intervallo portato a 30s): Roberto ha
chiesto se lo stesso sistema di sync valga anche per le indisponibilità
docenti, confermando che anche lì capita l'editing concorrente tra
postazioni.

Estesa `TABELLE` in `modules/auto_sync.py` con una voce `indisponibilita`
(chiave logica: docente+data+ora; campi di confronto: motivo, note),
seguendo esattamente lo stesso schema già in uso per assenze/supplenze.
Aggiunta colonna `creato_da` al modello `Indisponibilita` (migrazione
additiva automatica in `_auto_migrate()`), popolata in tutti i punti di
creazione trovati con una ricerca mirata nel codice:
`routes/indisponibilita.py::nuova()`, `routes/cambi_quadro.py::nuovo()`
(indisponibilità automatica per ferie/permesso concordato),
`routes/attivita.py::genera_effetti()` (le due creazioni legate alle
attività fuori aula).

Aggiunta anche la lapide (`registra_eliminazione`) nei punti di
eliminazione trovati: `routes/agenda.py::elimina_gruppo_indisp()` — e
qui, controllando questa route, si è scoperta una lacuna precedente non
ancora chiusa: le eliminazioni a cascata di Assenza/Supplenza collegate
(quando l'indisponibilità era "Auto") non venivano tombstonate neppure
nel lavoro precedente sulle assenze — chiusa in questo stesso giro.

Verificato in isolamento su copie di prova (`/tmp/test_indisp`, non sul
database reale): inserimento additivo di una indisponibilità presente
solo sul "remoto" confermato; conflitto genuino (stesso docente/data/ora,
motivo diverso) rilevato correttamente con `campi_diversi=["motivo"]`;
eliminazione locale con lapide verificata — un secondo giro di merge
non resuscita la riga eliminata (comportamento identico ai test già
fatti per le assenze). App avviata con `create_app()` e route `/`,
`/sync/conflitti`, `/indisponibilita/nuova` verificate con test client
(200 OK su tutte). Come già notato per `creato_da` su assenze/supplenze,
resta da verificare al primo uso reale in browser che il campo si popoli
correttamente (i test automatici lo confermano solo a livello di query
diretta).

### Task 46 — Sync automatico additivo (assenze/supplenze) ogni 60s

Seguito diretto del Task 45: Roberto ha chiesto un modo per evitare che
la divergenza tra macchine (segreteria che segna le assenze mentre lui
assegna le supplenze, entrambi con l'app aperta in parallelo) si
ripresenti, senza aspettare il passaggio a un server condiviso
(rimandato — vedi nota in fondo).

Costruito un meccanismo a due parti:

1. **`modules/auto_sync.py`** — un thread in background (avviato da
   `app.py`, con guardia contro il doppio avvio dovuto al reloader di
   Flask in debug) che ogni 60 secondi: scarica il database pubblicato
   su Google Drive, lo confronta con quello locale SOLO sulle tabelle
   `assenze` e `supplenze` (le due toccate dal caso d'uso descritto —
   le cattedre annuali restano fuori, troppo delicate per un merge
   anche parziale automatico, vedi Task 45), usando una chiave logica
   stabile per riga (es. docente+data+fascia oraria per le assenze;
   data+ora+classe+assente per le supplenze) invece dell'id
   autoincrementale, che può coincidere per righe diverse su database
   indipendenti. Le righe nuove (presenti solo sul remoto) vengono
   inserite in automatico; le righe con la stessa chiave logica ma
   contenuto diverso (vero conflitto, es. la stessa supplenza assegnata
   in modo diverso sulle due postazioni) NON vengono toccate: finiscono
   in una nuova tabella `sync_conflitti` (`models/sync_conflitto.py`)
   in attesa di revisione umana. Se sono state inserite righe nuove, il
   database locale aggiornato viene ripubblicato su Drive. Un lock file
   dedicato su Drive (`caronte_autosync.lock`, separato dal lock
   manuale di `sync_db.py`) evita che due giri partano nello stesso
   istante da macchine diverse.

2. **`routes/sync_conflitti.py` + `templates/sync_conflitti.html`** —
   pagina `/sync/conflitti` con il confronto campo per campo (locale vs
   "dall'altra postazione") di ogni conflitto in sospeso, e due
   pulsanti per scegliere quale versione tenere. Alla conferma, si
   aggiornano solo i campi realmente diversi (non l'intera riga) e si
   ripubblica subito su Drive, cosi la scelta si propaga e il conflitto
   non ricompare al giro successivo. Banner in `templates/base.html`
   (subito sotto la barra di navigazione, su tutte le pagine) con il
   conteggio dei conflitti in sospeso e link diretto alla revisione.

Verificato: motore di merge testato in isolamento su copie di prova del
database (non sul file reale) — inserimento additivo di una riga nuova
confermato, conflitto rilevato correttamente senza toccare la riga
locale, risoluzione con aggiornamento mirato dei soli campi diversi
confermata, `PRAGMA integrity_check` ok in ogni fase. App avviata con
`create_app()` e route `/sync/conflitti` verificata con test client
(200 OK). Nota tecnica: l'ambiente sandbox di Cowork usato per questa
sessione ha mostrato instabilità nella scrittura diretta sul file nel
mount condiviso (stesso "disk I/O error" già visto nel Task 45); non è
un problema del codice né riguarderà l'uso reale sul Mac di Roberto —
gestito comunque ripristinando il database da un backup pulito ad ogni
occorrenza, senza mai lasciare il file reale in uno stato inconsistente
(verificato con integrity_check dopo ogni recupero).

Resta sospeso, come da richiesta di Roberto: il passaggio a un server
condiviso raggiungibile sia da scuola sia da casa (discusso ma non
ancora scelto tra rete locale della scuola / piccolo hosting cloud) —
il meccanismo di questo Task è pensato come soluzione-ponte fino a quel
momento, non come sostituto definitivo.

**Aggiornamento — due bug trovati nel primo collaudo reale** (Roberto ha
provato con un'assenza a "Alaimo Giuseppe" — docente/motivo diversi
sulle due macchine per lo stesso giorno):

1. Il thread di background non partiva in modo affidabile: la guardia
   contro il doppio avvio (per via del reloader di Flask) controllava
   `app.debug`, che a quel punto della funzione `create_app()` è
   sempre `False` (diventa `True` solo dentro `app.run()`, chiamato
   dopo). Corretto affidandosi solo a `WERKZEUG_RUN_MAIN`. Aggiunto
   anche un log a ogni giro (non solo quando succede qualcosa) tramite
   `print()` invece di `app.logger`, perché il livello di log di
   default di Flask filtra via gli `INFO` anche in debug — serve a
   vedere da terminale che il thread è vivo.
2. La chiave logica delle assenze includeva `motivo`: due assenze per
   lo stesso docente/giorno/fascia oraria ma con motivo diverso (es.
   "lutto" su una macchina, un altro motivo sull'altra) venivano viste
   come due righe distinte e sommate invece che segnalate come
   conflitto. Rimosso `motivo` dalla chiave, spostato tra i
   `campi_confronto`. **Effetto collaterale già scritto nel database**
   di produzione durante il collaudo (prima della correzione): Alaimo
   Giuseppe risulta con due assenze per il 6/8/2026 invece di una
   ("formazione" e "lutto") — segnalato a Roberto, che ha scelto di
   sistemarlo a mano più avanti, non toccato da qui.
3. Un terzo problema, di comportamento non di bug: il sync pubblicava
   su Drive solo quando riceveva righe nuove dall'altra postazione, mai
   quando era la macchina locale ad avere novità proprie — quindi in
   pratica nessuna delle due macchine vedeva mai i dati dell'altra
   finché qualcuno non chiudeva l'app. Corretto: `_merge_additivo` ora
   calcola anche `solo_locali` (righe presenti in locale ma non ancora
   su Drive) e il ciclo pubblica se `inserite>0` OPPURE `solo_locali>0`.

Nota di processo: non sono riuscito a fare `git commit`/`push` da questo
ambiente (stesso tipo di blocco di scrittura sul mount già visto per
`database.db` — file di lock che non si riescono a rimuovere). Le
modifiche sono comunque scritte correttamente sui file reali; commit e
push restano da fare da Roberto direttamente dal proprio terminale.

**Secondo aggiornamento — quarto bug, dal collaudo con risoluzione
"tieni versione locale"**: scegliendo "tieni versione locale" il
contenuto della riga non viene toccato (per design — è la scelta di
NON applicare la proposta remota). Ma il controllo che evita i
duplicati cercava solo conflitti "non risolti" con quella chiave: al
giro successivo il contenuto locale/remoto era ancora diverso (perché
nessuno dei due lati era effettivamente cambiato), quindi ne veniva
creato uno NUOVO invece di riconoscere che era la stessa proposta già
rifiutata — un ciclo infinito, riprodotto e confermato sul database
reale (Alaimo: 4 righe in `sync_conflitti`, due già "risolte come
locale" a un minuto di distanza l'una dall'altra). Corretto: prima di
creare un nuovo conflitto, si controlla se l'ultima risoluzione
"locale" per quella stessa chiave riguardava ESATTAMENTE lo stesso
valore remoto — se sì, non richiede di nuovo; se il valore remoto è
nel frattempo cambiato davvero, il conflitto (genuino) torna a comparire.
Verificato con un test a 4 giri su copie isolate: 1) conflitto rilevato,
2) risolto come locale, 3) giro successivo — non ricompare, 4) valore
remoto cambiato di proposito — ricompare correttamente.

Nota collaterale (non un bug di questo meccanismo, ma un suo effetto
collaterale): la doppia assenza di Alaimo del 6/8 (Task precedente,
lasciata volutamente intoccata da Roberto) ha due righe con la stessa
chiave logica nello STESSO database — questo genera un conflitto
"fantasma" ricorrente finché quella duplicazione non viene sistemata a
mano; con la correzione sopra, però, resta un'unica voce che non si
moltiplica più ad ogni giro. (Le tre assenze di prova su Alaimo sono
poi state eliminate a mano su richiesta di Roberto, con backup cifrato
prima dell'operazione.)

**Terzo aggiornamento — quinto bug, il più importante: le eliminazioni
non si propagavano**. Segnalato da Roberto: se elimini un'assenza solo
su una postazione, l'altra la ha ancora — e al giro successivo il
merge additivo la vede come "riga nuova" e la rimette, anche dove era
stata cancellata apposta. Vero limite strutturale del solo "importa ciò
che è nuovo": senza un modo per distinguere "non ancora arrivata" da
"cancellata di proposito", le due situazioni sono indistinguibili.

Aggiunto un meccanismo di "lapidi" (tombstone —
`models/sync_tombstone.py`, tabella `sync_tombstones`): quando una
route elimina fisicamente una riga di `assenze` o `supplenze`, prima
registra la sua chiave logica con `modules.auto_sync.registra_eliminazione()`
(agganciato in `routes/assenze.py::elimina` e nella cascata di
`modules/assenze_registrazione.py::modifica_assenza`, gli unici due
punti dell'app che cancellano fisicamente righe di queste tabelle).
Il merge automatico ora: unisce le lapidi tra le macchine per prime
(sono "solo aggiunta", non possono mai essere in conflitto); non
reintroduce mai una riga la cui chiave ha una lapide, arrivata da
qualunque lato; elimina anche in locale una riga ancora presente la
cui chiave risulta lapidata dall'altra macchina. Le lapidi contano
anche ai fini di `solo_locali` (una lapide nuova, come una riga nuova,
attiva la ripubblicazione su Drive).

Verificato con due test mirati su copie isolate del database (stessa
riga presente su "locale" e "remoto", come se fosse già sincronizzata):
1) elimino su "locale" (lapide + delete, come fa la route) → giro di
merge con "remoto" che ha ancora la riga → resta eliminata, non
resuscita; 2) dal lato opposto, "remoto" scarica la lapide arrivata da
"locale" → la riga, ancora presente lì, viene eliminata anche lì.
`PRAGMA integrity_check` ok in entrambi i casi. App avviata con
`create_app()`: la nuova tabella si crea da sola via `db.create_all()`,
nessuna regressione sulle route esistenti.

**Quarto aggiornamento — nota "inserita da"**: su proposta di Roberto,
aggiunta una colonna `creato_da` (username) a `assenze` e `supplenze`,
valorizzata in tutti i punti che creano queste righe (form manuale di
assenze/supplenze, generazione automatica supplenze scoperte,
`routes/attivita.py::genera_effetti`, `routes/cambi_quadro.py`) con lo
stesso pattern già in uso nel codebase (`g.utente.username`). Propagata
nel sync automatico (`colonne_insert` in `modules/auto_sync.py`, non tra
i `campi_confronto`: l'autore da solo non genera mai un conflitto).
Mostrata nella pagina `/sync/conflitti` (sotto le intestazioni "Qui" e
"Dall'altra postazione") e nella dashboard, tabella "Docenti assenti"
("inserita da ..." sotto il tipo). Verificato: app avviata con
`create_app()`, migrazione applicata al database reale
(`PRAGMA integrity_check` ok, dati esistenti intatti), route
`/`, `/sync/conflitti`, `/assenze/nuova`, `/supplenze/nuova` tutte
200 OK. Non ancora verificato con un inserimento reale da interfaccia
(solo sintassi + smoke test) — da controllare al prossimo utilizzo
normale che il nome utente compaia correttamente.

**Limite noto, non risolto in questo Task**: se invece di eliminare
un'assenza la si MODIFICA cambiando docente o data (stessa riga, chiave
logica diversa — `modules/assenze_registrazione.py::modifica_assenza`,
punto 3), la vecchia chiave "sparisce" in locale esattamente come per
un'eliminazione, ma non viene lapidata: se era già stata sincronizzata,
il giro successivo potrebbe reintrodurla come riga a sé stante invece
di riconoscere che è stata sostituita dalla modifica. Non affrontato
ora (Roberto ha segnalato il caso della cancellazione, non questo);
da valutare in un prossimo giro se emerge come problema reale. Lo
stesso limite vale anche per `routes/indisponibilita.py::modifica()`
(Task 31, sotto).

**Quinto aggiornamento — intervallo portato a 30s**: su richiesta di
Roberto ("forse un minuto è troppo"), `INTERVALLO_SECONDI` in
`modules/auto_sync.py` portato da 60 a 30.

**Sesto aggiornamento — valutata e scartata l'estensione ad Attività
fuori aula**: Roberto ha chiesto se includere anche
`AttivitaFuoriAula` nel sync automatico. Analizzato il modello: a
differenza di assenze/supplenze/indisponibilità (una riga = un fatto
indipendente), qui c'è un record padre con due tabelle collegate
tramite il suo id autoincrementale (`AttivitaClasse`, associazione
many-to-many con i docenti accompagnatori) più un riferimento
auto-referenziale (`id_attivita_gruppo`) — struttura paragonabile ad
Assegnazioni, già esclusa in Task 45 come "troppo delicata per un
merge anche parziale automatico". Concordato con Roberto di NON
estendere il sync al record dell'attività in sé: gli effetti concreti
che generano davvero conflitti nell'uso quotidiano (le assenze,
supplenze e indisponibilità generate da `genera_effetti()` per i
docenti accompagnatori) sono già coperti dal sync automatico da
oggi (Task 46 + Task 31). Il record dell'attività (nome, date, elenco
classi/accompagnatori) resta gestito solo manualmente, come
Assegnazioni.

---

### Task 45 — Merge manuale macmini → macbookpro (Assegnazioni 2026-2027)

Roberto aveva modificato le Assegnazioni sul macmini e l'organico di
fatto sul macbook pro, in parallelo, senza sincronizzare tra una
modifica e l'altra: `sync_db.py` (Google Drive) non fa merge
automatico, solo check-out/check-in manuale, quindi le due basi dati
erano divergenti. Deciso con Roberto di unire (non scegliere una
macchina vincente): tenere l'organico di fatto del macbook pro e le
Assegnazioni del macmini.

Copiato `database_macmini.db` nella cartella condivisa e confrontato
riga per riga `assegnazioni_docenti`/`assegnazioni_classi` per
l'a.s. 2026-2027 tra i due file (tabelle di riferimento
`classi_concorso`/`materie` verificate identiche, quindi id
direttamente comparabili). Risultato:
- 14 assegnazioni presenti solo sul macmini → aggiunte al macbook pro
  (con le relative ore per classe), tra cui Ghezzi Angelo su IRC
  (id_docente remappato da 95 a 43, l'id già unificato in precedenza).
- 1 riga sospetta esclusa: B-17/Abramini 5h — verificato che Abramini
  è di ruolo su A-26 Matematica, non su un laboratorio meccanico:
  stesso tipo di errore di inserimento già corretto in passato per
  Agrò. Segnalata a Roberto e confermata come errore da non importare.
- 3 conflitti (stessa CC+docente, ore diverse tra le due macchine:
  Paolini, Bosisio, Agrò su A-11) risolti tenendo la versione del
  macmini su indicazione esplicita di Roberto.

Eseguita prima una copia di sicurezza cifrata di `database.db`
(`modules.backup_cifrato.crea_backup_cifrato`). Nota tecnica: il primo
tentativo di scrittura diretta sul file nella cartella montata ha dato
"disk I/O error" a causa di un file di journal SQLite residuo che il
mount non permetteva di rimuovere (Operation not permitted); risolto
lavorando su una copia locale, poi scritto il risultato finale sul
file di destinazione con `open()+os.fsync()` invece di un semplice
`cp`. Verificato dopo il merge: `PRAGMA integrity_check` ok, nessuna
riga orfana in `assegnazioni_classi`, nessuna FK non valida, la vecchia
riga errata B-17/Agrò (già rimossa in una sessione precedente) resta
assente, totale assegnazioni 2026-2027 passato da 14 a 28.

Rimane da fare (esplicitamente rimandato da Roberto a dopo il merge):
decidere un meccanismo di salvaguardia per evitare che le due macchine
divergano di nuovo (es. banner di stato sync, blocco se il lock è
tenuto da un'altra macchina).

---

### Task 44 — CC "solo compresenza" (B-02, B-03, B-12, B-14, B-16,
B-17) mai visibili in Assegnazioni nonostante fossero nel piano studi

Causa comune trovata per due segnalazioni insieme: "B-02 (ing/ted/spa)
dovrebbe comparire nella sezione Lingue" (già elencata in `AREE` ma di
fatto invisibile) e "B-03/B-12/B-14/B-16/B-17 non compaiono nemmeno in
tutte, nonostante siano nei piani di studio" (mancavano anche
dall'elenco `AREE` sotto "Tecnici Geo/Cost", che aveva solo A-37,
A-51, B-14, B-17).

Verificato sul database: per tutte queste CC, OGNI riga di PianoStudi
per il 2026-2027 ha `compresenza=True` — non hanno mai un titolare
"principale" con ore proprie, esistono solo come ore di compresenza
affiancate a un altro insegnamento (conversazione lingue, laboratori
tecnici). Ma `_classi_per_cc`, `_ore_piano_per_classe`, il calcolo di
`piano_materie` in `_build_area`, `_resolve_id_materia` e il controllo
avvisi in `api_verifica` filtravano TUTTI esplicitamente
`compresenza=False` — corretto per evitare doppi conteggi quando una
CC ha ore proprie E ore di compresenza sulla stessa classe, ma quando
una CC esiste SOLO come compresenza il filtro escludeva tutto,
facendola sparire ovunque nella pagina.

Aggiunto un helper unico `_righe_piano(anno_scol, cc_id, anno_corso,
indirizzo)`: usa le righe non-compresenza se esistono, altrimenti
quelle di compresenza come fallback — non cambia nulla per le CC che
hanno già ore proprie, corregge solo il caso "solo compresenza".
Sostituiti tutti e 5 i punti che duplicavano il filtro diretto.
Completato anche l'elenco `AREE`: "Tecnici Geo/Cost" ora include
B-03, B-12, B-16 oltre ad A-37, A-51, B-14, B-17 già presenti.

Verificato pytest (51/51) e lettura reale di `/assegnazioni?anno=
2026-2027`: tutte e otto le CC (B-02-ING/TED/SPA, B-03, B-12, B-14,
B-16, B-17) ora compaiono nella pagina.

### Task 43 — Corretto il layout del form "Nomina" (era tagliato dalla
tabella) + simbolo del pulsante più chiaro

Il form inline aggiunto nel Task 42 (una riga `<tr colspan="20">`
dentro la tabella pivot) veniva tagliato dai contenitori con overflow/
colonne sticky della tabella, restando visibile solo nei margini della
prima colonna. Sostituito con un modal centrato a comparsa (stesso
linguaggio visivo del popover ore già esistente in questa pagina:
`position:fixed`, backdrop semi-trasparente cliccabile per chiudere),
condiviso da tutte le righe placeholder invece di una copia per riga —
un'unica select "docente" popolata una volta sola, il form cambia solo
l'action (`/assegnazioni/<id>/nomina`) e il nome del placeholder
mostrato via JS (`apriNomina`/`chiudiNomina`). Simbolo del pulsante
cambiato da "☺︎" (poco chiaro) a "⇄︎" (scambio/sostituzione), con
tooltip esplicito.

Verificato pytest (51/51) e lettura reale della pagina: pulsante e
modal presenti, nessuna riga con colspan residua nel markup.

### Task 42 — Pulsante "Nomina" per i placeholder in Assegnazioni +
placeholder salvabili senza ore

Due segnalazioni collegate su Assegnazioni classi→docenti:

1. **"Come rinomino un placeholder col docente reale quando arriva?
   Avevamo previsto un sistema ma non lo trovo più."** Verificato: il
   backend esiste già ed è completo — route
   `POST /assegnazioni/<id>/nomina` (routes/assegnazioni.py), assegna
   il docente reale al posto del placeholder e sincronizza
   automaticamente le sue materie — ma NON era collegata a nessun
   controllo nell'interfaccia (nessun form/pulsante nel template la
   richiamava). Aggiunto un pulsante "☺︎" nella colonna azioni di ogni
   riga placeholder che apre un mini-form inline (select docente reale
   + conferma), riusando la stessa lista `docenti_anno` già caricata
   per il form di aggiunta assegnazione.

2. **"Ho provato ad aggiungere un placeholder per A-22-SPA e B-02-ING
   ma non compare in tabella."** Riprodotto un salvataggio via backend
   con dati equivalenti: la logica di salvataggio ha funzionato
   correttamente quando erano presenti delle ore — il sospetto era che
   il valore ore non fosse stato effettivamente registrato nella
   cella della griglia prima di premere "Salva", nel qual caso l'app
   silenziosamente rifiuta il salvataggio con un flash message
   ("Inserisci almeno un'ora su una classe") che Roberto ha confermato
   di non aver notato. Contestualmente Roberto ha chiesto una modifica
   più ampia: poter inserire un placeholder anche SENZA nessuna ora
   assegnata (riga "riservata" da completare più avanti). Tolto quel
   blocco per i soli placeholder in routes/assegnazioni.py::salva()
   (i docenti reali restano soggetti al controllo, invariato) — un
   placeholder senza ore su nessuna classe viene ora salvato
   normalmente (0h totali) e resta modificabile/nominabile da lì.

Verificato pytest (51/51) e un ciclo completo via test client: salvato
un placeholder senza ore su A-22-SPA (comparso in tabella con 0
classi), poi nominato con successo un docente reale al suo posto
tramite la nuova route/pulsante, confermando `id_docente` valorizzato
e `nome_placeholder` azzerato.

### Task 41 — Etichette complete nelle pillole della barra passi

Su richiesta di Roberto: le pillole della barra di navigazione a passi
(Impostazione Anno) mostravano solo il numero, con l'etichetta
visibile solo al passaggio del mouse (tooltip). Cambiato in
"{{ numero }}. {{ etichetta }}" per tutte e 13, più leggibile a colpo
d'occhio (il breadcrumb sopra già mostrava l'etichetta del passo
corrente, invariato). Verificato pytest (51/51) e lettura reale di una
pagina del wizard.

### Task 40 — Box "Incarichi" nella scheda docente

Su suggerimento di Roberto: aggiunto un box nella scheda docente
(subito sotto "Materie insegnate", come da conferma) con gli incarichi
dell'a.s. corrente in evidenza e lo storico degli anni precedenti in
un dettaglio a scomparsa (`<details>`), sola lettura — si assegnano e
modificano dalla pagina Incarichi esistente, linkata in alto nel box.
Dati presi da `Docente.incarichi` (backref già presente su
IncaricaDocente, nessun modello nuovo). Non mostrato nel form di
creazione nuovo docente (non ha ancora incarichi per definizione).
Verificato pytest (51/51) e lettura reale di /docenti/23/modifica
(mostra correttamente "Nessun incarico per l'a.s. corrente" + storico
con 1 incarico pregresso).

### Task 39 — Aggiustamenti al Task 38: codice ministeriale nella
classe di concorso, rimosso il blocco assegnazione superfluo,
confermata l'origine delle sigle in /display

Tre correzioni su segnalazione di Roberto:

1. `Docente.materia_effettiva` mostrava solo il nome della classe di
   concorso (es. "Scienze Motorie e Sportive sec. II grado"),
   facilmente confuso con un nome di materia. Aggiunto il codice
   ministeriale davanti: ora "A-48 — Scienze Motorie e Sportive sec. II
   grado", inequivocabile.

2. Rimosso il blocco "Materie insegnate secondo le assegnazioni"
   aggiunto nel Task 38 nella scheda del singolo docente: secondo
   Roberto il box già esistente "Materie insegnate (a.s. corrente)"
   era già collegato correttamente e la nuova sezione era superflua.
   Tolti sia il codice in routes/docenti.py::modifica() sia il blocco
   in templates/docente_form.html; nessun impatto sul resto (era
   un'aggiunta isolata del turno precedente).

3. Verificata e confermata l'ipotesi di Roberto su /display: i titoli
   dei singoli box materia in quella pagina vengono da
   `OrarioDocente.materia` (l'orario scolastico importato da Excel),
   NON dai campi `sigla`/`nome_breve`/`alias` che lui stesso imposta
   su ogni Materia nella pagina "Materie ↔︎ Classi di concorso"
   (passo 3) o in "Dipartimenti e Materie". Segnalato inoltre che
   esiste già un campo pensato esattamente per questo collegamento —
   `Materia.codice_orario` ("per matching automatico con
   OrarioDocente.materia", editabile oggi solo dalla pagina
   Dipartimenti e Materie) — ma non è attualmente usato da nessuna
   logica di confronto/matching nell'app: è una base già pronta ma
   incompiuta per il futuro compito di abbinare l'orario importato
   alle sigle definite da Roberto, discusso ma non implementato in
   questo giro.

Verificato pytest (51/51) e lettura reale di /docenti (ora "A-48 —
Scienze Motorie e Sportive sec. II grado") e di /docenti/23/modifica
(blocco assegnazione confermato assente).

### Task 38 — Correzione del Task 37: colonna "Materia" rinominata in
"Classe di concorso" + materie realmente insegnate spostate nella
scheda docente (da assegnazione, non da anagrafica)

Osservazione corretta di Roberto: la colonna dell'elenco /docenti si
chiamava "Materia" ma dal Task 37 mostrava la classe di concorso — le
due cose sono concettualmente diverse (abilitazione vs materie
davvero insegnate). Intestazione rinominata in "Classe di concorso"
(contenuto invariato, era già corretto). Aggiunta invece nella scheda
del singolo docente (routes/docenti.py::modifica) una sezione di sola
lettura "Materie insegnate secondo le assegnazioni" per gli anni
successivi a quello corrente per cui esistono già dati reali di
assegnazione (oggi solo il 2026-2027) — calcolata da
AssegnazioneDocente/AssegnazioneClasse (la scheda assegnazione, passo
9), non dal roster DocenteMateria mantenuto a mano. Il blocco esistente
"Materie insegnate (a.s. corrente)" resta identico, non toccato: per
l'anno in corso restano le diciture già presenti, come richiesto.

Chiarito anche il secondo dubbio: le sigle/materie mostrate in
`/display` (cruscotto sale) per l'ora di lezione vengono da
`OrarioDocente.materia`, un campo testo separato e legittimo,
popolato dall'orario scolastico importato da Excel
(routes/sincronizzazione.py + modules/parser_orario.py, foglio
"ORARIO DEFINITIVO") — riflette la materia realmente schedulata quel
giorno/ora, non ha nulla a che fare col vecchio campo libero
Docente.materia. Trovata per l'occasione anche l'origine storica di
quel vecchio campo: lo stesso importatore lo scrive UNA VOLTA (solo se
vuoto) dal foglio "Docenti" dell'Excel importato — spiega perché è
rimasto fermo alla prima importazione e mai più allineato.

Verificato pytest (51/51) e lettura reale di /docenti (intestazione
aggiornata) e /docenti/23/modifica (mostra correttamente "Discipline
sportive" e "Scienze motorie e sportive" per l'a.s. 2026-2027, sola
lettura, link alla pagina Assegnazioni per quell'anno).

### Task 37 — Materia mostrata in anagrafica presa dalla classe di
concorso (dato univoco), non più dal vecchio campo libero

Segnalazione: nell'elenco /docenti, di fianco al proprio nome
comparivano ancora "SCIENZE E DISCIPLINE SPORTIVE, SCIENZE MOTORIE" —
dicitura mai più aggiornata da quando (probabilmente da un import
iniziale) era stata scritta nel vecchio campo libero `Docente.materia`.
Le materie reali collegate (DocenteMateria → Materia) erano corrette,
il problema era solo che l'interfaccia leggeva il campo sbagliato.

Su richiesta esplicita di "univocare il riferimento come per il resto
dell'app": aggiunta la property `Docente.materia_effettiva` (in
models/docente.py) che restituisce `classe_concorso.nome` — il dato
relazionale già pensato come sostituto stabile del vecchio campo libero
(lo dice esplicitamente il docstring di models/classe_concorso.py, mai
attuato finora) — con fallback al vecchio campo solo per i docenti non
ancora classificati con una CC, per non lasciare celle vuote.

Sostituiti tutti i punti di sola VISUALIZZAZIONE che leggevano
`Docente.materia`: elenco e ricerca docenti, scheda docente (elenco
titolari per abbinamento ITP), export dati personali (GDPR art.15),
form attività istituzionali e "fuori aula" (dati JS autocomplete),
sostituzioni scrutinio (assente/candidati/select nomina), display
sale (rimosso anche un vecchio hack `.split(',')[0]` che tagliava a
mano la vecchia stringa concatenata — non più necessario), report e
banca ore (intestazione scheda singolo docente), elenco docenti
disponibili per il recupero. Il popup di scelta "materia" in
routes/supplenze.py (usato dal cruscotto sostituzioni) ora costruisce
il campo dalla stessa property.

Deliberatamente NON toccata la logica di *matching* in
routes/recupero_giugno.py (confronto testo libero con l'orario
scolastico, `rd.docente.materia` usato come chiave di ricerca, non
solo come etichetta) — cambiarla rischierebbe di rompere
l'abbinamento automatico dei gruppi di recupero, ed esula dalla
richiesta (che riguardava la visualizzazione in anagrafica). Lasciato
invariato anche `routes/ricerca.py` (il filtro di ricerca testuale
sul vecchio campo `materia`).

Verificato pytest (51/51), lettura reale di /docenti (ora mostra
"Scienze Motorie e Sportive sec. II grado" per Dal Toè, invece del
vecchio testo) e di /docenti/23/esporta-dati (200, file generato senza
errori).

### Task 36 — Unificate le anagrafiche duplicate Ghezzi e Tramontana

Confermato da Roberto: "Ghezzi Andrea" e "Ghezzi Angelo" sono la stessa
persona (nome doppio), non due docenti come ipotizzato — da fondere
come "Ghezzi Angelo". "Tramontana" confermato come duplicato reale.
Stesso pattern già visto per Agrò (id 2/102): un record storico
TD_annuale senza classe di concorso collegata (con tutto lo storico
operativo — banca ore, presenze, supplenze, orario) e un record nuovo
inserito per il 2026-2027 con la classificazione IRC corretta ma senza
storico. Backup cifrato di sicurezza prima di procedere
(`database_..._prima-unione-ghezzi-tramontana.db.enc`). Script dedicato
`scripts/unisci_ghezzi_tramontana.py` (dry-run di default, `--applica`
per confermare): per ciascuna coppia tiene l'id storico (43 per Ghezzi,
81 per Tramontana), adotta da lì la classificazione corretta
(tipo_contratto=IRC, id_classe_concorso=IRC, anno_scol_inizio=
2026-2027), sposta le righe collegate (abilitazione classe di concorso,
materia_ist, l'assegnazione classe→docente di Tramontana), rinomina
Ghezzi da "Andrea" a "Angelo" come indicato, poi elimina il duplicato.
Verificato `PRAGMA integrity_check`, audit di tutte le foreign key verso
`docenti` (nessun riferimento residuo agli id 95/96 eliminati) e pytest
(51/51).

### Task 35 — Tre bug segnalati dopo il primo giro di test su /docenti

Roberto ha riprovato la pagina e segnalato tre problemi concreti:

1. **Anno di default sbagliato**: la pagina apriva già su "2026-2027"
   nonostante oggi (4 agosto) siamo ancora operativamente nel
   2025-2026 fino al 31 agosto. Causa: usava `_anno_default_piano()`
   (pensato per il wizard "Impostazione Anno", che punta subito
   all'anno che si sta preparando) invece dell'anno operativo reale.
   Cambiato in `get_anno_corrente()` (stessa fonte usata da
   assegnazioni, banca ore, ecc.).

2. **Docenti del 2026-2027 visibili anche nel 2025-2026** (Bollasina,
   De Agostini, Di Liberto, Fazio, Loffi, Misticoni, Remondina,
   Tarabini, Toracca, Veda + le nuove schede di Ghezzi/Tramontana).
   Causa: `_docenti_per_anno()` per gli anni correnti/passati
   restituiva TUTTI i docenti attivi senza applicare i limiti
   `anno_scol_inizio`/`anno_scol_uscita` (li applicava solo per gli
   anni futuri). Ora i limiti si applicano sempre; il filtro
   aggiuntivo sui TD senza data d'inizio resta solo per gli anni
   futuri, per non escludere TD storici mai aggiornati con quel campo.
   Verificato che dashboard_anno/assegnazioni/export_xlsx (altri 3
   punti che usano la stessa funzione) continuano a funzionare: si
   appoggiano tutti su AP uscenti/aspettativa restando nell'elenco,
   comportamento non toccato da questa modifica.

   Controllo collaterale sui presunti duplicati segnalati: "Ghezzi"
   sono in realtà due persone diverse (Andrea id 43, Angelo id 95) —
   falso allarme. "Tramontana Miriana" è invece un vero duplicato (id
   81 storica TD_annuale senza CC, id 96 nuova IRC per il 2026-2027) —
   segnalato a Roberto, in attesa di conferma per l'unione (stesso
   percorso già seguito per Agrò), nessuna modifica ai dati fatta.

3. **AP uscenti/aspettativa/trasferiti assenti dall'elenco "non in
   servizio"**: la sezione "ex docenti" filtrava solo `attivo=False`,
   ma questi stati (gestiti dal passo 7, `docenti_anno()`) non toccano
   mai quel campo — restano `attivo=True`. Aggiunta
   `_docenti_non_in_servizio(anno_scol)`, che unisce disattivati,
   usciti (`anno_scol_uscita <= anno_scol`) e chi ha
   `status_presenza` AP uscente/aspettativa. Tasto "Riattiva" nascosto
   per chi ha `motivo_uscita == 'pensionamento'` (mostrato solo per
   consultazione storica, con link diretto alla scheda) — bloccato
   anche lato server nella route `riattiva()`, non solo nel template.
   La riattivazione ora ripulisce anche `status_presenza`/`scuola_ap`,
   non solo `anno_scol_uscita`/`motivo_uscita`.

   Verificato pytest (51/51) e sul database reale: default ora
   2025-2026 corretto, i docenti "puri 2026-2027" non compaiono più
   nella vista 2025-2026, i 5 usciti/AP/aspettativa reali (Buiarelli,
   Caprigli, Del Re, Libera, Meneghello, Toracca, Tarabini) compaiono
   tutti nell'elenco "non in servizio" per il 2026-2027 con Riattiva
   presente per tutti tranne i due pensionati (Buiarelli, Del Re).

### Task 34 — Selettore anno sempre visibile (bug) + vista "ex docenti"
con riattivazione senza duplicare l'anagrafica

Due follow-up al Task 33, entrambi segnalati da Roberto dopo aver
riprovato la pagina:

1. **Bug: selettore anno invisibile.** Gli anni mostrati venivano presi
   solo dai dati già inseriti in Piano di Studi/Classi — con un solo
   anno in archivio ("2026-2027") il template nascondeva la fila di
   pillole (condizione `length > 1`). Sostituito con una finestra fissa
   di 4 anni intorno all'anno corrente (`_shift_anno()`, nuovo helper)
   unita a qualunque anno con dati reali, sempre visibile.

2. **"Un docente uscito quest'anno che torna il prossimo, posso
   recuperare la sua anagrafica invece di ricrearla?"** — verificato che
   oggi la risposta era no: `Docente.attivo=False` lo rende invisibile
   ovunque (58 punti dell'app filtrano su quel campo), non esiste una
   vista "non attivi", e i campi già pronti per l'uscita/rientro
   (`anno_scol_inizio`, `anno_scol_uscita`, `motivo_uscita`) non sono
   mai scritti da nessuna route. L'unica alternativa sarebbe stata
   ricreare da zero l'anagrafica — lo stesso problema già visto con
   Agrò (id 2/102). Su conferma esplicita, aggiunto: link "Mostra anche
   i non attivi" in `/docenti` (elenco separato, non tocca le 58
   query esistenti che filtrano `attivo=True`), e una nuova route
   `POST /docenti/<id>/riattiva` che rimette `attivo=True` sulla STESSA
   riga, imposta `anno_scol_inizio` all'anno di rientro scelto e
   ripulisce `anno_scol_uscita`/`motivo_uscita` — nessuna nuova
   anagrafica creata, storico/banca ore/supplenze restano collegati.
   Non toccata la cessazione (deliberatamente fuori scope per questo
   giro): il checkbox "attivo" in scheda docente resta l'unico modo per
   disattivare, senza chiedere motivo/anno di uscita.
   Verificato pytest (51/51) e un ciclo completo disattiva→mostra
   inattivi→riattiva→verifica campi sul database reale (poi ripulito il
   record di prova).

### Task 33 — Selettore anno in Anagrafica docenti + versionamento
part-time per anno futuro

Su domanda ("l'elenco docenti in anagrafica docenti, non dovrebbe avere
un selettore d'anno... un docente che oggi non ha part-time il
prossimo anno potrebbe averlo... così posso predisporre oggi i dati
per l'anno prossimo"), due interventi distinti (scelti insieme via
AskUserQuestion):

1. **Selettore anno in `/docenti`**: la lista ora riusa
   `_docenti_per_anno()` (già scritta per il passo 7, "Docenti per
   anno scolastico") così le due pagine si comportano in modo
   coerente — anno corrente/passato mostra tutti gli attivi, anno
   futuro filtra a soli TI senza uscita segnalata + TD/AP già
   inseriti per quell'anno. Pillole anno in alto, avviso quando si
   guarda un anno diverso da quello corrente.

2. **Versionamento part-time/ore contratto PT**: prima del Task, questi
   due campi erano un'unica "istantanea attuale" su `Docente`, letta
   così com'è ovunque (nessun modo di dichiarare oggi un cambio di
   regime già noto per l'anno prossimo senza toccare l'anno in corso).
   Aggiunto lo stesso pattern già esistente per `ore_max_anno`/
   `anno_scol_ore_max`: tre nuovi campi (`part_time_prog`,
   `ore_contratto_pt_prog`, `anno_scol_part_time_prog`) + due metodi
   `part_time_effettivo_per_anno(anno_scol)` /
   `ore_contratto_pt_effettive_per_anno(anno_scol)` che restituiscono
   il valore programmato solo se l'anno richiesto coincide con
   `anno_scol_part_time_prog`, altrimenti il valore corrente — quindi
   nessun rischio di alterare i calcoli dell'anno in corso. Verificato
   il perimetro reale d'uso di `part_time`/`ore_contratto_pt` (solo
   `routes/docenti.py` in scrittura e `models/docente.py` in lettura,
   più poche righe di template) prima di procedere: intervento
   circoscritto, non un refactor esteso. Form scheda docente: nuovo
   riquadro "Cambio di regime già noto per un anno futuro" con
   selezione dell'a.s. e del nuovo regime. Elenco docenti: badge PT
   calcolato per l'anno visualizzato (segnala se deriva da un cambio
   programmato). Migrazione automatica aggiunta a
   `app.py::_auto_migrate()` per le tre nuove colonne. Verificato
   pytest (51/51), smoke test su `/docenti`, `/docenti?anno=2027-2028`
   e `/docenti/<id>/modifica`, `PRAGMA integrity_check` sul database
   reale dopo la migrazione.

### Task 32 — Rimossa la ANNO_SCOL_CORRENTE congelata in
routes/attivita_ist.py (i 4 punti segnalati nel Task 31)

Seguito della nota lasciata nel Task 31. Rimossa
`ANNO_SCOL_CORRENTE = get_anno_corrente()` (calcolata una sola volta al
caricamento del modulo, mai più aggiornata finché il server non viene
riavviato) e sistemati i 4 punti che la usavano, ciascuno con la fonte
più corretta per il proprio contesto invece di un semplice "richiama
get_anno_corrente() ad ogni request":

- `_preset_partecipanti()` (elenco automatico docenti per riunioni di
  dipartimento): ora usa `_anno_scolastico(attivita.data)` — l'anno
  scolastico della DATA dell'evento, non "oggi". Più corretto anche
  della semplice sostituzione con l'anno corrente: una riunione
  programmata per un anno diverso da quello in corso userà comunque le
  materie dell'anno giusto.
- `assegnazioni()` (`/attivita-ist/roster`, pagina roster
  Docenti↔Materie): default ora `_anno_default_piano()`, coerente con
  tutte le altre pagine anno-scoped sistemate in questa sessione.
- `_score_candidato()` (suggerimento automatico supplenti per
  scrutini, confronto materie assente/candidato): ora usa
  `_anno_scolastico(evento.data)`, stessa logica di
  `_preset_partecipanti()`.

Rimosso anche l'import ormai inutilizzato di `get_anno_corrente` in
testa al file.

Verificato: py_compile, pytest 51/51, `/attivita-ist/roster` aperta
senza parametro anno mostra correttamente 2026-2027 di default (prima
sarebbe stata legata al valore congelato all'avvio del server).

### Task 31 — Chiarito lo status anno di "Dipartimenti e Materie";
selettore anno mancante per i referenti

Roberto si chiedeva come impostare "Dipartimenti e Materie" per il
2026-2027, non vedendo modo di cambiare anno su quella pagina.
Chiarito: `Materia`/`Dipartimento` non hanno `anno_scol` — sono un
catalogo stabile come "Classi di concorso" (passo 1), non legato
all'anno. Quello che c'è oggi vale già anche per il 2026-2027, non va
importato né reimpostato.

Trovato però un problema reale nella stessa pagina: i **referenti di
dipartimento** mostrati (badge verde/grigio sopra ogni dipartimento)
sono per anno (`IncaricaDocente.anno_scol`), ma la query in
`routes/attivita_ist.py::dipartimenti()` usava sempre
`get_anno_corrente()` — l'anno "di sistema" configurabile a mano, che
risulta fermo a 2025-2026 (stesso problema di fondo del Task 23) —
senza alcun selettore per guardare un anno diverso. In pratica, per
vedere/assegnare i referenti del 2026-2027 su questa pagina non c'era
modo.

Corretto: aggiunto un parametro `anno` (default `_anno_default_piano()`,
come nelle altre pagine anno-scoped) e un selettore ad anni-pillola in
`templates/attivita_ist/dipartimenti.html`, identico nello stile a
quello già usato altrove. Aggiunta anche una nota nella pagina che
spiega la distinzione (catalogo stabile vs referenti per anno), per
evitare che la stessa domanda si riproponga.

Verificato: default ora mostra 2026-2027 (non più fermo su 2025-2026),
`?anno=2026-2027` esplicito funziona, pytest 51/51.

**Nota per una sessione futura (non affrontata ora, fuori scope):**
`routes/attivita_ist.py` ha anche una `ANNO_SCOL_CORRENTE` calcolata
UNA VOLTA SOLA al caricamento del modulo (riga 13,
`ANNO_SCOL_CORRENTE = _get_anno()`) e riusata in altri 4 punti del
file (righe 40, 457, 605, 607) — resta congelata al valore di quando
il server è partito, anche se il calendario cambia o la config
anno_scol_corrente viene aggiornata mentre il server resta attivo. Non
è lo stesso bug appena corretto (quello era "anno sbagliato ma
selezionabile male"; questo è "anno giusto al boot, poi mai
aggiornato"), ma vale la pena rivederlo in una sessione dedicata.

### Task 30 — "Costo ora supplenza" reso un deep-link utile; collegata
la gestione tipi di incarico (esisteva già, non era raggiungibile)

Roberto ha segnalato che "Costo ora supplenza" (sezione Istituto)
apriva semplicemente "Dati istituto" senza portare da nessuna parte di
specifico, e che gli mancava un posto per definire gli incarichi
assegnabili ai docenti.

Verificato nel codice: `costo_ora_supplenza` è davvero un campo dentro
"Dati istituto" (sezione "Parametri economici",
`config_istituto.py`) — il link non è rotto, è solo un duplicato senza
destinazione precisa. Aggiunto `id="parametri-economici"` alla sezione
in `templates/impostazioni/dati_istituto.html` e cambiato il link in
`templates/impostazioni/index.html` in
`{{ url_for('impostazioni.dati_istituto') }}#parametri-economici`, così
ora salta davvero al campo giusto invece di aprire la pagina da capo.

Sugli incarichi: la gestione CRUD dei tipi di incarico esiste già
(`models/incarico.py::TipoIncarico`, route `/incarichi/tipi` in
`routes/incarichi.py`, template `incarichi/tipi.html`) — permette di
creare/modificare/disattivare i tipi, con categoria e compenso
default, ed è già quello che alimenta il selettore nella pagina
"Assegna incarichi". Il problema era di scoperta, non di funzionalità
mancante: era raggiungibile solo da un piccolo pulsante "⚙︎ Gestisci
tipi" dentro la pagina Incarichi docenti, non da Istituto né dall'hub
Impostazioni. Aggiunta una nuova card "✦︎ Tipi di incarico assegnabili"
nella sezione Istituto di `impostazioni/index.html`, che punta
direttamente a `incarichi.tipi`.

Verificato via Flask test client: link con ancora presente, id
dell'ancora presente nella pagina di destinazione, `/incarichi/tipi`
raggiungibile (200). Pytest 51/51.

### Task 29 — Barra mancante su "4b. Aule" e "9. Assegnazioni" (context
processor registrato solo sul blueprint sbagliato)

Roberto ha segnalato che le tessere 4b e 9 non mostravano il
breadcrumb/barra introdotta nel Task 27. Causa: `nav_steps` era
iniettato con `@impostazione_anno_bp.context_processor`, che in Flask
si applica SOLO alle richieste gestite da quel blueprint — "Aule"
(`routes/aule.py`, blueprint `aule`) e "Assegnazioni"
(`routes/assegnazioni.py`, blueprint `assegnazioni`) vivono altrove,
quindi non ricevevano mai la funzione e l'`{% include %}` in quelle due
pagine non era stato nemmeno aggiunto.

Corretto: il context processor è ora registrato a livello di app in
`app.py` (`app.context_processor(lambda: dict(nav_steps=_nav_steps))`,
subito dopo la registrazione del blueprint impostazione_anno) invece
che sul solo blueprint — così raggiunge tutte le pagine dell'app.
Aggiunto l'`{% include 'impostazione_anno/_step_nav.html' %}` anche in
`templates/aule/lista.html` e `templates/assegnazioni/index.html`.

Verificato via Flask test client (con `CARONTE_SKIP_LOGIN=1` per Aule,
che richiede il permesso `aule_r` non posseduto dall'utente id=1 usato
nei test precedenti — comportamento corretto del sistema permessi, non
un bug): entrambe le pagine ora mostrano correttamente il breadcrumb
("4b. Aule per classe" e "9. Assegnazioni classi →︎ docenti"). Pytest
51/51.

### Task 28 — Link correlati per Calendario, Sistema e Docenti (resto
della sezione Impostazioni)

Completata l'analisi promessa nel Task 27 sul resto di Impostazioni
(oltre a Impostazione Anno). Premessa emersa dall'analisi: esiste già
una barra di navigazione fissa in cima a ogni pagina (`base.html`) con
un link sempre visibile a "Impostazioni" — tornare all'hub costa già
un click da qualunque punto dell'app. Il vero problema, dove esiste,
non è "tornare all'hub" ma muoversi lateralmente tra pagine sorelle
dello stesso gruppo, che prima non si linkavano mai tra loro.

A differenza di Impostazione Anno (10+ passi in sequenza, serviva una
barra con prev/next), qui i gruppi sono piccoli (1-3 pagine) e non
sequenziali: non serve un'analoga barra a passi, basta una riga
compatta di "link correlati" in cima a ogni pagina. Aggiunta a:

- **Calendario** (`impostazioni/sospensioni.html`,
  `impostazioni/periodi.html`): si linkano a vicenda.
- **Sistema** (`utenti/lista.html`, `cambia_pin.html`): si linkano a
  vicenda più un link diretto a Backup database; aggiunto anche un
  link di ritorno a Impostazioni che prima mancava del tutto su
  entrambe le pagine (si affidavano solo alla nav fissa).
- **Docenti** (`docenti.html`, `impostazione_anno/docenti_classi_concorso.html`,
  `impostazione_anno/docenti_materie.html`, `attivita_ist/dipartimenti.html`):
  gruppo più critico, quattro pagine su tre blueprint diversi
  (`docenti`, `impostazione_anno`, `attivita_ist`) che riguardano lo
  stesso docente da angolazioni diverse (anagrafica, abilitazioni,
  materie insegnate, dipartimento) e prima non si linkavano affatto tra
  loro. Sulle due pagine già dotate della barra a passi del Task 27
  (docenti_classi_concorso, docenti_materie) la riga è ridotta a "Vedi
  anche" per non affollare la pagina con due blocchi di navigazione
  simili.

Verificato via Flask test client su tutte le 9 pagine coinvolte: status
200 ovunque. Pytest 51/51.

### Task 27 — Barra di navigazione a passi per tutta la sezione
Impostazione Anno

Su richiesta di Roberto ("ti sembra intuitivo il modo di spostarsi da
una pagina all'altra?"), implementata la proposta di navbar interna
mostrata in anteprima nella chat.

Aggiunto in `routes/impostazione_anno.py`: `_nav_steps(anno_corrente)`,
elenco unico dei 13 passi (num, etichetta, endpoint, kwargs url, colore,
flag `own` per distinguere le pagine di questo blueprint da quelle
esterne come Aule e Assegnazioni), iniettato in tutti i template del
blueprint tramite `@impostazione_anno_bp.context_processor`. Un solo
punto da aggiornare se in futuro cambia l'ordine o si aggiunge un
passo.

Creato `templates/impostazione_anno/_step_nav.html`: breadcrumb
("Impostazioni › Impostazione Anno › passo corrente"), prev/next per
muoversi in sequenza con un click (limitato alle pagine di questo
blueprint — Aule e Assegnazioni restano cliccabili nella fila di
tessere ma non nel conteggio prev/next, avendo una loro navigazione
propria), e una fila di tessere numerate sempre visibili (1, 2, 3, 4,
4b, 5, 6, 6b, 7, 8, 8b, 9, 10) con quella corrente evidenziata, per
saltare direttamente a un passo qualsiasi anche non adiacente. La barra
usa la variabile `anno` della pagina corrente (se definita) invece di
ricalcolare sempre l'anno di default, così spostandosi tra passi resta
coerente con l'anno che si sta guardando.

Incluso in tutte le 11 pagine "passo" del blueprint (classi_concorso,
piano_studi, materie_classi_concorso, classi_attive, calcolo_organico,
organico, cattedre_potenziamento, docenti_anno,
docenti_classi_concorso, confronto_organico, docenti_materie), subito
sotto l'intestazione esistente (lasciata invariata). Aggiunto anche un
breadcrumb leggero (senza tessere, già ridondanti con la lista della
pagina) nell'hub `impostazione_anno/index.html`.

Verificato via Flask test client su tutte le 12 pagine (hub incluso):
status 200 ovunque, breadcrumb corretto, prev/next assenti/presenti
correttamente ai due estremi della sequenza (1 non ha "indietro", 10
non ha "avanti", risulta collegato solo a 8b). Pytest 51/51.

Prossimo passo (in corso): estendere l'analisi di navigazione anche
alle altre sezioni di Impostazioni (Calendario, Docenti, Orario,
Istituto, Sistema, Cambio Anno), non ancora toccate.

## Sessione 32 — Ricostruzione modifiche organico di fatto perse dal ripristino

Roberto ha chiesto di risalire alle modifiche fatte il 3/8 tra le 10 e
le 14 ai dati di "Organico di fatto 2026-2027" (tabella
`cattedre_organico`), non avendole più ritrovate.

**Causa: effetto collaterale del ripristino da backup di ieri sera
(Sessione 31, Task 19quinquies).** Quel ripristino era stato verificato
confrontando solo il *numero* di righe per tabella tra lo stato
pre-ripristino e il backup delle 10:58 — controllo che non rileva
modifiche ai *valori* di righe già esistenti (solo aggiunte/rimozioni).
Decifrando e confrontando riga per riga lo snapshot delle 10:59 di
ieri con quello delle 21:51 (l'ultimo salvato prima del ripristino) è
emerso che 15 righe di `cattedre_organico` (anno 2026-2027, tipo
'fatto') erano state modificate in quella finestra — e il ripristino
le aveva silenziosamente riportate allo stato delle 10:59, cancellando
il lavoro della giornata su n_docenti, ore_residue e dati COE per le
classi di concorso A-11, A-12, A-19, A-20, A-22-ING, A-22-SPA,
A-22-TED, A-26, A-27, A-34, A-37, A-45, A-46, A-48, A-50.

Riportati i valori corretti (quelli delle 21:51) a Roberto in una
tabella riepilogativa; li ha reinseriti manualmente lui stesso — nessun
intervento diretto sul DB da parte mia questa volta.

**Lezione per i prossimi ripristini da backup:** confrontare sempre il
contenuto riga per riga delle tabelle toccate di recente, non solo il
conteggio delle righe — un conteggio invariato non esclude che righe
esistenti siano state modificate nel frattempo. Da valutare in futuro:
estendere la Cronologia attività (Task 16, Sessione 19) anche alle
route di Impostazione Anno (organico, cattedre di potenziamento,
piano studi override, ecc.), attualmente non tracciate — avrebbe reso
questa ricostruzione immediata invece di richiedere il confronto
manuale tra backup cifrati.

---

### Task 26 — Collegata la pagina standalone "Confronto TI ↔ Organico
USR" (era raggiungibile solo digitando l'URL)

Roberto ha chiesto dove si trovasse la pagina standalone corretta nel
Task 24 (`/impostazione-anno/confronto-organico`) — non era collegata
da nessuna parte dell'interfaccia, solo url diretto. Chiesto dove fosse
logico collegarla: scelta la home di Impostazione Anno, come voce a sé
(non legata a un solo passo, essendo una vista di controllo
trasversale).

Aggiunta in `templates/impostazione_anno/index.html` una card "8b.
Verifica TI ↔︎ Organico USR" subito dopo il passo 8 (Docenti ↔︎ Classe
di concorso) e prima del passo 9 (Assegnazioni) — posizione naturale:
è il checkpoint per verificare le abilitazioni appena inserite al
passo 8 prima di procedere alle assegnazioni ore. Verificato via test
client: link presente in `/impostazione-anno`, pytest 51/51.

### Task 25 — Il fix fatto/diritto del Task 24 era sulla pagina
sbagliata; corrette anche Passo 8 e dashboard-anno

Roberto non vedeva l'aggiornamento promesso nel Task 24. Causa: c'è
sempre stata un'implementazione DUPLICATA della stessa verifica "TI
collegati ↔ DOC Organico USR" — una standalone
(`/impostazione-anno/confronto-organico`, quella corretta nel Task 24)
e una identica ma inline nella pagina Passo 8
(`/impostazione-anno/docenti-classi-concorso`,
`routes/impostazione_anno.py::docenti_classi_concorso()`), con lo
stesso identico titolo "⌕︎ Verifica: TI collegati ↔︎ DOC Organico
USR". Quest'ultima è quella che Roberto guardava, e usava ancora
`tipo='diritto'` fisso — non toccata dal Task 24.

Corretta anche questa con la stessa precedenza fatto→diritto (stesso
pattern di `_budget()`), stessa etichetta "(fatto)"/"(diritto)" in
tabella, e sistemata la raccolta CC per evitare duplicati quando
esistono sia la riga 'diritto' sia la riga 'fatto' (stesso fix del
Task 24, applicato qui perché mancava).

Approfittando della segnalazione, sistemato anche
`routes/dashboard_anno.py` (`/dashboard-anno`, terza occorrenza dello
stesso confronto, richiesta esplicitamente da Roberto): usava
`CattedraOrganico.tipo.in_(['fatto','diritto']).first()` senza
ordinamento esplicito — quale dei due risultasse primo dipendeva
dall'ordine di inserimento nel DB, senza garantire la preferenza per il
fatto. Ora usa la stessa logica esplicita fatto→diritto, con
l'etichetta della fonte visibile accanto a ogni scarto segnalato.

In totale, la stessa verifica "TI ↔ DOC Organico USR" esiste ora in tre
punti dell'app (Passo 8 inline, pagina standalone, dashboard-anno) —
tutti e tre coerenti sulla stessa logica. Verificato con Flask test
client sulle tre pagine reali per l'anno 2026-2027: tutte mostrano
"(fatto)", zero "(diritto)", nessuna CC duplicata. Pytest 51/51.

### Task 24 — Confronto TI ↔︎ Organico USR: usava sempre l'organico di
diritto invece di preferire quello di fatto

Roberto ha fatto notare che la pagina "Confronto TI ↔︎ Organico USR"
(`/impostazione-anno/confronto-organico`) confrontava i TI collegati in
app sempre con l'organico **di diritto** (il bollettino USR iniziale,
teorico, spesso rivisto), mentre altrove nell'app — in
`routes/assegnazioni.py::_budget()`, usata per i controlli di budget
cattedre in Assegnazioni — si preferisce già l'organico **di fatto**
(la dotazione reale, calcolata dopo le iscrizioni effettive) e si
ricade sul diritto solo se il fatto non è ancora stato inserito.
Aveva ragione: era un'incoerenza, non una sua svista.

Corretto `routes/impostazione_anno.py::confronto_organico()` con la
stessa precedenza fatto→diritto. Aggiunta anche l'etichetta "(fatto)"
o "(diritto)" accanto al numero DOC USR in tabella, per capire a colpo
d'occhio quale fonte è stata usata riga per riga (utile finché il
bollettino di fatto non è ancora stato inserito per tutte le CC).
Sistemato anche un side-effect della query di raccolta CC: il vecchio
join fisso su `tipo='diritto'` è stato tolto e sostituito con due
sottoquery di id (una per CalcoloOrganico, una per CattedraOrganico di
qualsiasi tipo), per evitare di duplicare una CC nell'elenco quando
esistono sia la riga 'diritto' sia la riga 'fatto'.

Verificato via Flask test client sulla pagina reale (2026-2027): 19 CC
in elenco, nessuna duplicata, tutte le 19 mostrano "(fatto)" — nei dati
attuali diritto e fatto coincidono ovunque quindi i numeri non
cambiano oggi, ma la fonte usata ora è quella corretta. Pytest 51/51.

### Task 23 — I box riassuntivi di impostazione-anno guardavano l'anno
sbagliato (calendario vs anno di lavoro)

Roberto stava impostando il 2026-2027 (agosto 2026) ma i 5 box in cima
a `/impostazione-anno` mostravano dati vecchi. Causa: 3 dei 5 box
("Sezioni attive", "Righe piano studi", "Calcoli organico confermati")
usavano `anno_corrente`, calcolato SOLO dal calendario
(`_anno_scolastico_corrente()`: cambia il 1° settembre) — ad agosto
risulta ancora "2025-2026". Tutti i link della pagina sotto, invece,
usavano già `anno_piano` (`_anno_default_piano()`: l'anno più recente
con dati reali nel piano studi/calcolo organico), che risultava
correttamente "2026-2027". I box e i link puntavano quindi a due anni
diversi.

Corretto in `routes/impostazione_anno.py::index()`: le tre query dei
box ora filtrano su `anno_piano` invece di `anno_corrente`; anche il
link "6. Organico USR" (che usava `anno_corrente`) ora usa
`anno_piano`, per coerenza con tutti gli altri link della pagina.
`anno_corrente` resta calcolato (serve altrove) ma non è più usato in
questa pagina. Verificato coi dati reali: sul 2026-2027 risultano 38
sezioni attive, 358 righe piano studi, 30/30 calcoli confermati — molto
diversi dai numeri del 2025-2026 mostrati prima della correzione.
Pytest 51/51.

### Task 22 — Corretto badge "materie collegate": leggeva un campo
legacy disallineato, non la tabella reale

Roberto ha segnalato che "Geografia Economica" risultava non collegata
nel badge nonostante avesse un collegamento a A-21 in passo 3 (stesso
per "Tecnologia dell'informazione e della comunicazione" → A-41).
Verificato: entrambe avevano regolarmente una riga in
`MateriaClasseConcorso` (fonte='normativa'), ma il campo legacy
`Materia.id_classe_concorso` — su cui si basava il badge introdotto nel
Task 21 — era rimasto `NULL` per entrambe (probabilmente inserite in
passo 3 con un percorso che non ha sincronizzato il campo legacy,
oppure risalenti a un import diretto). Il campo legacy non è usato da
nessun'altra funzionalità reale dell'app (Assegnazioni, Docenti↔Materie
ecc. leggono già `MateriaClasseConcorso` direttamente) — l'unico
impatto era il badge stesso.

Corretto in due parti:
1. Risincronizzato il campo legacy per le due materie (`id_classe_concorso
   = 7` per Geografia Economica, `= 24` per TIC), verificato contro la
   riga 'normativa' esistente prima di scrivere.
2. Reso il badge "Materie con CC associata" in
   `routes/impostazione_anno.py::index()` più robusto: ora conta le
   materie con almeno una riga in `MateriaClasseConcorso` (fonte
   qualsiasi, quindi anche 'eccezione_istituto' come Religione/IRC),
   non più il campo legacy — così un futuro disallineamento dello
   stesso tipo non si ripresenta. Risultato dopo la correzione: 49/49
   materie collegate (Religione ora conta correttamente grazie al
   collegamento IRC come eccezione istituto).

Verificato: py_compile, pytest 51/51, conteggio confermato via query
diretta (0 materie fuori da `MateriaClasseConcorso`).

### Task 21 — Controllo coerenza passo 3, box riepilogo più chiari,
unione anagrafiche duplicate Agrò

**1) Controllo di coerenza in "Materie ↔ Classi di concorso" (passo
3).** Confermato a Roberto che scollegare una materia da una CC non
tocca a cascata le ore già assegnate (Assegnazioni classi → docenti).
Per evitare che questo resti un'incoerenza silenziosa, in
`routes/impostazione_anno.py::materie_classi_concorso()` ora, dopo il
salvataggio, per ogni collegamento materia↔CC rimosso si controlla se
esistono ancora righe `AssegnazioneClasse` con ore > 0 per quella
coppia materia/CC; se sì, un flash di avviso (arancione) elenca
docenti e classi coinvolti, senza toccare i dati. Il salvataggio non
viene mai bloccato — solo segnalato.

**2) Chiarimento box riepilogo in `/impostazione-anno`.** Il badge
"46/49" era "Materie collegate" senza contesto. Rinominato in "Materie
con CC associata", con tooltip che elenca le materie non collegate
(nel caso reale: Religione cattolica — corretto, non ha una CC — più
Geografia Economica e Tecnologia dell'informazione e della
comunicazione, da rivedere). Aggiunto anche l'anno di riferimento alle
etichette dei box che sono scope-anno (Sezioni attive, Righe piano
studi, Calcoli organico confermati) e chiarito che l'ultimo box conta
calcoli organico confermati, non classi di concorso.

**3) Unione delle due anagrafiche duplicate di Agrò Andrea.** Docente
id=2 ("AGRO'", senza accento, con tutto lo storico operativo: orario,
banca ore, presenze, supplenze, cambio ore) e id=102 ("AGRÒ", con
accento, creato quest'anno con l'abilitazione A-11 corretta e la
cattedra 2026-2027 corretta) erano lo stesso docente. Durante l'analisi
è emerso che id=2 aveva anche una cattedra 2026-2077 sbagliata sulla CC
B-17 (Laboratorio Scienze e Tecnologie Meccaniche) — stesso pattern di
errore di inserimento già visto per Abramini — mentre id=102 aveva
quella corretta su A-11. Segnalato a Roberto, che ha confermato di
eliminare la cattedra B-17.

Eseguito `scripts/unisci_agro.py` (dry-run poi `--applica`, dopo backup
cifrato): sopravvive id=2, con cognome "AGRÒ", abilitazione A-11,
`tipo_contratto='TI'` e `anno_scol_inizio='2026-2027'` presi da id=102;
spostate su id=2 anche l'abilitazione CC e la riga `recupero_docenti`
di id=102; eliminata la cattedra B-17 sbagliata; eliminato id=102.
Verificato con audit su tutte le tabelle con FK verso `docenti.id`:
zero riferimenti residui a id=102. Pytest 51/51.

### Task 20 — Chiarimento cascata passo 3, messa in sicurezza sync
Docenti↔Materie, link docente→anagrafica in Assegnazioni

Tre richieste di Roberto in un'unica sessione di follow-up dopo il
Task 19undecies/19duodecies (bug id_materia):

**1) Chiarimento (nessuna modifica di codice).** Chiesto se modificare
le materie in "Materie ↔ Classi di concorso" (passo 3) aggiorni anche
il resto dell'app. Risposta: no, non c'è propagazione automatica.
Quella pagina scrive solo su `MateriaClasseConcorso` e su
`Materia.id_classe_concorso`; non tocca `AssegnazioneClasse`,
`DocenteMateria` né altro. Se una materia viene rimossa da una classe
di concorso dopo che erano già state assegnate ore su quella materia
per quella cattedra, le assegnazioni esistenti restano invariate (non
vengono invalidate né segnalate). Nessuna azione richiesta da Roberto
su questo punto per ora; resta un possibile miglioramento futuro (un
controllo di coerenza) se in futuro servirà.

**2) Messa in sicurezza del sync Docenti↔Materie (rischio perdita
dati).** In risposta a "userei il sistema che riduce al minimo il
rischio di perdere dati": due punti di scrittura cancellavano *tutte*
le righe `DocenteMateria` di un docente/anno (o dell'intero anno, nel
caso della pagina roster) prima di ricrearle, comprese quelle con
`origine='auto'` sincronizzate automaticamente da Assegnazioni classi
→ docenti (Task 19decies). Corretto in due punti, applicando lo stesso
pattern — cancella e ricrea solo le righe `origine='manuale'`, mai
quelle `'auto'`:
- `routes/attivita_ist.py::assegnazioni()` (pagina roster
  Dipartimenti/Attività istituzionali): da
  `DocenteMateria.query.filter_by(anno_scol=anno).delete()` a
  `.filter_by(anno_scol=anno, origine='manuale').delete()`, con
  controllo di esistenza prima di inserire nuove righe.
- `routes/docenti.py::_sync_materia_roster()` (scheda anagrafica
  docente, campo materie): stesso pattern, scoping su
  `origine='manuale'`.

Prima di questa correzione, salvare il roster Dipartimenti per
qualunque anno, o anche solo modificare l'anagrafica di un docente
(pure per un dato non correlato come email/telefono), avrebbe
silenziosamente cancellato le materie derivate dalle ore assegnate in
Assegnazioni — richiedendo poi che il backfill/sync venisse rieseguito
per ripristinarle.

**3) Link docente → anagrafica in Assegnazioni.** In
`templates/assegnazioni/index.html`, il nome del docente (sia nelle
righe già assegnate sia nelle righe "docenti precaricati" non ancora
assegnati) è ora un link a `docenti.modifica` (scheda anagrafica). I
placeholder (supplenti non ancora nominati) restano testo semplice,
non essendoci un'anagrafica da aprire.

Verificato: `create_app()` senza eccezioni, py_compile su
attivita_ist.py/docenti.py/assegnazioni.py, pytest 51/51.

### Task 19quinquies — Ripristino database da backup cifrato manuale
Roberto ha caricato un backup cifrato del proprio Mac
(`database_20260803_105809_MacBook-Pro-di-Roberto-DT.local.db.enc`,
storico delle 10:58 di stamattina) chiedendo di ripristinarlo come DB
valido, presumibilmente per superare lo stato incerto lasciato dagli
incidenti di ministudio (Task 19quater).

Prima di sovrascrivere: decifrato con la chiave locale, verificato
`PRAGMA integrity_check` (ok), confrontato riga per riga con il DB
reale allora attivo. Unica differenza reale: il backup mancava di 2
righe in `assegnazioni_docenti` (cattedre 2026-2027 per i docenti id
102 e id 1, tipo TI, inserite oggi alle 10:34-10:35) e della relativa
riga di log — nonostante il backup sia datato 10:58, non le conteneva
(causa non determinata da qui, forse una scrittura su disco non ancora
fluita al momento dello snapshot). Segnalato esplicitamente a Roberto,
che ha confermato di voler procedere comunque.

Eseguito: backup di sicurezza dello stato precedente
(`data/backup/database_20260803_2151_prima-ripristino-20260803.db.enc`),
poi sostituito `database.db` con la versione ripristinata. Verificato:
integrity check ok, `create_app()` senza eccezioni, pytest 51/51.

**Nota per la prossima sessione:** le 2 assegnazioni cattedra
2026-2027 (docente id 102/classe concorso 2, docente id 1/classe
concorso 11, tipo TI) andranno reinserite a mano se erano corrette —
non sono più presenti dopo questo ripristino. Il ripristino è stato
fatto solo in locale su questa macchina: non è stato ripubblicato su
Google Drive (va fatto con `sync_db.py carica` quando si è sicuri
dello stato, specialmente dopo aver sistemato la chiave di cifratura
condivisa con ministudio, Task 46).

### Task 19duodecies — Applicate le correzioni sul database reale
(eliminazione Abramini + backfill materie), risolto anche il venv rotto

**Premessa tecnica**: i primi tentativi di scrivere sul database reale
dalla sandbox di Cowork fallivano con "disk I/O error" — il mount di
rete tra la sandbox e il Mac non regge bene il locking di SQLite in
scrittura (letture e modifiche di file normali invece funzionano). Sul
Mac di Roberto, inoltre, il `venv` del progetto risultava con `pip`
puntato a un percorso di un'altra macchina
(`/Users/ministudio/SupplenzeApp/venv/...` — probabilmente il venv era
stato creato/sincronizzato lì e mai rigenerato su questo MacBook Pro),
quindi `pip install` falliva con "bad interpreter" e Flask/Flask-WTF
risultavano non importabili anche dopo aver individuato il venv giusto.
Risolto passando a operare direttamente sul Mac di Roberto tramite il
tool Desktop Commander (controllo del suo terminale reale, non più la
sandbox) e rigenerando il venv da zero (`rm -rf venv && python3 -m venv
venv && pip install -r requirements.txt`) — tutte le dipendenze
necessarie (Flask, Flask-SQLAlchemy, Flask-WTF, SQLAlchemy, openpyxl)
si installano e importano correttamente; solo WeasyPrint segnala le
librerie di sistema mancanti (pango/cairo, note e non necessarie per
queste operazioni — vedi README per l'installazione via brew se serve
in futuro per l'export PDF).

**Operazioni eseguite sul database reale, in ordine, con verifica dopo
ciascuna:**
1. Eliminata `AssegnazioneDocente` id 2 (ABRAMINI Iulia, CC B-17, 5A
   LSP, 3h+2h) su richiesta esplicita di Roberto — la riassegnerà lui
   con la classe di concorso corretta. Verificato che la riga sia
   sparita e `PRAGMA integrity_check` → ok.
2. Lanciato `scripts/backfill_id_materia.py` in dry-run: confermati gli
   stessi numeri già visti sulle copie di prova (65 Caso A, 18 Caso B,
   0 già corrette) — con qualche riga di Caso B in più (Boffi Silvia,
   Bosisio Federica, Dal Toè Roberto) rispetto all'ultima verifica,
   segno che Roberto ha continuato a usare il modulo Assegnazioni nel
   frattempo con lo stesso bug non ancora corretto lato codice.
3. Applicato con `--applica`: `AssegnazioneClasse` aggiornate, 3 righe
   `DocenteMateria` con il vecchio valore sbagliato rimosse (le 3 di
   Agrò, origine 'manuale' da migrazione), 4 nuove righe corrette
   create (`origine='auto'`).
4. Verificato sul database reale: `PRAGMA integrity_check` → ok;
   `DocenteMateria` di Agrò (docente id 102) ora mostra correttamente
   Lingua e letteratura italiana / Lingua e cultura latina / Storia e
   geografia (invece di Spagnolo/Diritto ed economia dello
   sport/materia inesistente); pytest 51/51.

Nessun'altra modifica al database in questa voce. Da controllare da
Roberto: pagina 10 (Docenti↔Materie) e scheda classe 1B LLI, per
conferma visiva finale.

### Task 19undecies — Bug MOLTO più serio trovato: id_materia sbagliato
(non NULL) per TUTTE le classi "multi-materia" storiche — inclusa la mia
propria correzione del Task 19decies

**Come è emerso.** Verificando perché il caso reale di Agrò (docente id
102, "AGRÒ Andrea", CC A-11, 1B LLI, 3 materie da 3h) non comparisse in
Docenti↔Materie nonostante il fix del Task 19decies, ho trovato che
`AssegnazioneClasse.id_materia` per le classi **multi-materia** (quelle
col popover con un campo ore per materia — Lettere/Latino/Storia,
Scienze motorie/Discipline sportive, ecc.) non è mai stato l'id della
materia vera e propria. `_build_area()` in `routes/assegnazioni.py`
costruiva il campo `piano_materie[classe]` usando `r.id` — la chiave
primaria della RIGA di PianoStudi — invece di `r.id_materia`, la vera FK
verso la tabella Materia (due entità con contatori indipendenti). Il
form multi-materia nomina i suoi campi `ore_<classe>_<quel numero>`, e
quel numero finiva salvato pari pari in `AssegnazioneClasse.id_materia`,
dichiarata FK verso Materia — puntando quindi a una riga completamente
sbagliata (o inesistente) ogni volta.

Verificato sui dati reali di Agrò: id salvati 11/28/34 (id di righe
PianoStudi) invece di 1/2/3 (id reali delle materie Lingua e letteratura
italiana/Lingua e cultura latina/Storia e geografia) — risultato,
`DocenteMateria` per Agrò conteneva "Spagnolo" e "Diritto ed economia
dello sport" (materie reali ma completamente a caso, stesso id numerico
per coincidenza) più una terza riga con id 34 che nella tabella Materia
non esiste affatto (quindi invisibile ovunque, silenziosamente).
Rilanciando il backfill in dry-run sull'intero database reale: **0**
righe multi-materia/materia-singola risultavano già corrette, 65 casi
"NULL" (Task 19decies) e **18 casi di id sbagliato** (non solo Agrò —
anche BOFFI Silvia, Scienze motorie/Discipline sportive su più classi).
Il bug era quindi sistemico, presente probabilmente da quando è stato
introdotto il form multi-materia, e mai emerso prima perché nessuno
sincronizzava ancora automaticamente Docenti↔Materie da qui.

**Errore mio da segnalare esplicitamente:** la funzione
`_resolve_id_materia()` che avevo scritto nel Task 19decies per il caso
"materia singola" (id NULL) conteneva **lo stesso identico errore**
(`return righe[0].id` invece di `righe[0].id_materia`) — non è mai stata
eseguita con `--applica` su un database reale (solo dry-run e su copie
di prova), quindi non ha corrotto nulla, ma andava comunque corretta
insieme al resto.

**Fix (tutti nello stesso commit logico):**
- `routes/assegnazioni.py::_build_area()` — `piano_materie[classe]`
  ora usa `r.id_materia` (e scarta le righe senza materia collegata,
  nessuna in pratica: verificato 0/358 righe piano studi senza
  `id_materia` sul database reale).
- `routes/assegnazioni.py::_resolve_id_materia()` — stesso fix.
- `routes/export_xlsx.py::_riempi_foglio_classe()` — stesso fix nel
  fallback per righe storiche.
- `scripts/backfill_id_materia.py` — riscritto per correggere **entrambi**
  i casi (A: NULL: come nel Task 19decies; B: id sbagliato — nuovo):
  per ogni riga con `id_materia` valorizzato, verifica se il valore
  combacia con un id di Materia valido per il contesto (già corretto,
  non tocca) oppure con l'id di una riga di PianoStudi dello stesso
  contesto (Caso B, corregge). Alla sincronizzazione finale, oltre a
  ripulire le righe `DocenteMateria` `origine='auto'` orfane, ripulisce
  anche le righe con il vecchio valore sbagliato **di qualunque
  origine** (incluse quelle marcate `'manuale'` solo per default della
  migrazione, come le 3 di Agrò, create da una sincronizzazione
  automatica precedente a questa sessione).
- Verificato **sul database reale, solo in dry-run e su copie**: 65
  Caso A + 18 Caso B, 0 già corrette. Applicato **su una copia**
  (`--applica`): Agrò risulta correttamente con Lingua e letteratura
  italiana/Lingua e cultura latina/Storia e geografia (`origine='auto'`),
  le 3 righe sbagliate precedenti rimosse, pytest 51/51 dopo
  l'applicazione. **Non ancora applicato al database reale** — da fare
  Roberto sul suo Mac dopo backup, vedi istruzioni nello script.

**Perché "Docenti ↔ Materie" non mostrava comunque Agrò anche a dati
corretti:** trovato un secondo problema, indipendente. La pagina 10
mostra solo le materie ammesse dalle classi di concorso **abilitate**
del docente (passo 8, tabella `DocenteClasseConcorso`) — se una materia
è in `DocenteMateria` ma la relativa classe di concorso non è tra le sue
abilitazioni, il checkbox semplicemente non veniva mai renderizzato (il
template scorre solo `materie_ammesse`). Nel caso reale, Agrò/AGRÒ
(docente 102) **ha** A-11 tra le abilitazioni, quindi questo problema
specifico non lo riguarda più una volta corretto l'id_materia — ma
esiste comunque un **secondo docente omonimo**, id 2 "AGRO'" (senza
accento, con apostrofo), abilitazioni vuote, con una vecchia
assegnazione su B-17/1A AFM tuttora NULL e irrisolvibile dal backfill
(0 materie nel piano studi per quella combinazione) — probabile
duplicato anagrafico della stessa persona, da unificare o eliminare
manualmente: **segnalato a Roberto, nessuna azione automatica presa**,
serve una decisione umana su quale dei due record tenere.

Corretto comunque il problema generale di visibilità in
`routes/impostazione_anno.py::docenti_materie()` +
`templates/impostazione_anno/docenti_materie.html`: le materie già in
`DocenteMateria` ma non coperte da nessuna abilitazione ora vengono
mostrate comunque, in una sezione "extra" con avviso arancione che
rimanda al passo 8, invece di restare invisibili. Corretta anche la
validazione POST della pagina 10 (`ids_ammessi`) perché non cancellasse
in silenzio queste righe extra a ogni salvataggio del form.

**Verifica:** `py_compile` su tutti i file Python toccati; pytest 51/51
su copie fresche, prima e dopo l'applicazione reale del backfill
corretto; riprodotto l'intero scenario di Agrò via Flask test client
(crea-e-assegna + aggiorna-ore con gli id materia corretti) confermando
sync corretto di DocenteMateria e comparsa in pagina 10.
**Non eseguibile da qui**: applicazione del backfill sul database
reale — da fare Roberto, con backup preventivo.

### Task 19decies — Bug reale trovato: id_materia NULL per classi "materia
singola" in Assegnazioni, e sincronizzazione automatica Docenti↔Materie

**Causa del caso di Agrò segnalato da Roberto** (le ore inserite in
Assegnazioni non comparivano al passo 10 "Docenti ↔ Materie"): nel form
di Assegnazioni, quando una classe ha una sola materia nel piano studi
per quella classe di concorso (caso comune — es. Matematica in una
classe che non ha "multi-materia"), il campo del form è `ore_<classe>`
senza indicare l'id materia, perché non c'è ambiguità da chiedere
all'utente. `AssegnazioneClasse.id_materia` restava quindi **NULL** per
queste righe. `_sync_docente_materie()` (introdotta nella sessione
precedente per questo scopo) filtra esplicitamente `if ac.id_materia`,
quindi le righe NULL venivano ignorate — Docenti ↔ Materie non si
aggiornava mai per queste assegnazioni (solo per quelle su classi
multi-materia, dove il form passa sempre l'id). Stessa causa dietro il
secondo problema segnalato: l'export "scheda classe" (Impostazione Anno
→ Classi attive → Esporta scheda classe) mostrava il tipo di contratto
(es. "TI") al posto del nome materia, perché il suo fallback su
`ac.id_materia` mancante era proprio quello.

**Fix alla radice** (`routes/assegnazioni.py`): nuova
`_resolve_id_materia(anno_scol, cc_id, label)` — se il piano studi ha
esattamente una materia per quella classe di concorso/indirizzo/anno
corso, la risolve e la usa come `id_materia`, invece di lasciarlo NULL.
Applicata sia in `salva()` (creazione nuova assegnazione) sia in
`aggiorna_ore()` (modifica AJAX delle ore). Da ora in poi le nuove
assegnazioni/modifiche su classi a materia singola hanno sempre
`id_materia` valorizzato, e la sincronizzazione verso Docenti↔Materie
funziona anche lì. Aggiornato anche l'export scheda classe
(`_riempi_foglio_classe` in `export_xlsx.py`) per risolvere al volo la
materia mancante sulle righe storiche non ancora corrette, così i file
generati sono corretti da subito anche prima del backfill.

**Backfill dati storici**: `scripts/backfill_id_materia.py` (una
tantum, non eseguito automaticamente) — corregge le `AssegnazioneClasse`
già esistenti con `id_materia` NULL risolvibili in modo univoco dal
piano studi, e sincronizza di conseguenza Docenti↔Materie per i docenti
toccati. Dry-run di default, richiede `--applica` per scrivere
davvero. Da lanciare da Roberto sul suo Mac (`python scripts/
backfill_id_materia.py` poi, se l'elenco sembra corretto, `--applica`)
— non eseguibile da questo ambiente sandbox (mancano le dipendenze
Python del progetto qui).

**Le tre opzioni di centralizzazione discusse, tutte implementate:**

1. **Pulizia automatica dei simmetrici mancanti.** Nuovo campo
   `DocenteMateria.origine` (`'auto'` | `'manuale'`, migrazione
   additiva in `app.py::_auto_migrate()`, default `'manuale'` per le
   righe esistenti — nessuna già presente viene reinterpretata come
   automatica). `_sync_docente_materie()` marca `origine='auto'` le
   righe che crea. Nuova `_pulisci_docente_materie_orfane(id_docente,
   anno_scol)`: rimuove le righe `origine='auto'` non più coperte da
   nessuna `AssegnazioneClasse` del docente per quell'anno — mai quelle
   `'manuale'`. Richiamata quando si azzerano le ore di una
   classe/materia (`aggiorna_ore`, ramo ore=0) e quando si elimina
   un'intera assegnazione (`elimina`).
2. **Tracciabilità della provenienza.** Il campo `origine` sopra è
   proprio questo: ogni riga sa se è "dichiarata a mano" o "dedotta
   dalle ore assegnate".
3. **Visibilità in pagina 10.** `templates/impostazione_anno/
   docenti_materie.html`: le materie con `origine='auto'` mostrano un
   piccolo badge viola "auto" con tooltip esplicativo. Scelta
   deliberata: il badge è solo informativo, la spunta resta comunque
   rimovibile manualmente da lì (bloccarla del tutto avrebbe impedito
   di correggere un caso sbagliato senza prima andare a togliere le ore
   in Assegnazioni) — un salvataggio manuale da questa pagina resetta
   comunque tutto a `'manuale'` per quel docente (dichiarazione
   esplicita che sovrascrive la deduzione automatica).

**Verifica:** sintassi Python controllata (`py_compile`) su tutti i
file toccati (`app.py`, `routes/assegnazioni.py`,
`routes/impostazione_anno.py`, `routes/export_xlsx.py`,
`models/materia.py`, `scripts/backfill_id_materia.py`) — nessun errore.
**Non eseguibile da qui**: pytest (51/51 attesi), test funzionale reale
del caso Agrò, e il backfill stesso — mancano le dipendenze del
progetto in questo ambiente sandbox. Da fare alla prossima sessione sul
Mac: pytest, riprovare il caso di Agrò (inserire ore → verificare
comparsa in passo 10), lanciare il backfill in dry-run e controllarne
l'elenco prima di `--applica`, rigenerare una scheda classe e
verificare che mostri i nomi materia invece del tipo contratto.

### Task 19novies — Riordino passi 9/10 in Impostazione Anno Scolastico
Su richiesta, invertito l'ordine dei due ultimi passi nell'indice
`/impostazione-anno` (`templates/impostazione_anno/index.html`): ora è
**9. Assegnazioni classi → docenti** e **10. Docenti ↔ Materie** (prima
erano invertiti). Solo etichette numeriche e ordine dei due blocchi
scambiati, nessun link/route toccato.

### Task 19octies — Docenti di sostegno nella vista Orario globale
Riaperto uno dei tre punti chiusi "così com'è" nella voce precedente:
su richiesta, la vista `/orario/globale` ora mostra anche gli slot dei
docenti di sostegno, che non compaiono nel file Excel importato (vivono
in `OrarioSostegno`, tabella separata — vedi Sessione 23).

**Implementazione:**
- `routes/sincronizzazione.py::orario_globale()`: oltre agli slot di
  `OrarioDocente`, ora interroga anche `OrarioSostegno` per lo stesso
  giorno e costruisce una seconda griglia `griglia_sostegno[classe][ora]`
  (tenuta separata da `griglia`, non unita/travestita da OrarioDocente —
  qui serve un rendering distinto, non il matching supplenze già
  gestito da `slots_come_orario_docente()` altrove). `docenti_map` ora
  include anche i docenti di sostegno.
- `templates/orario_globale.html`: nella cella della griglia, sotto il
  titolare (blu) e l'eventuale ITP in compresenza (viola, invariato),
  aggiunta una riga "+ cognome" in bordeaux (`var(--blu-med)`, la
  stessa palette di brand) per ogni docente di sostegno nello stesso
  classe/ora. Stessa logica riportata nella modale di dettaglio classe
  (click su una classe) e nei dati JS `ORARIO_DATI`. Aggiunta una
  legenda colori sopra la tabella (Titolare/ITP/Sostegno).

Nessuna modifica a `OrarioSostegno`, a `compresenze.py` o alla logica
supplenze — solo visualizzazione. `pianifica_permessi()` resta non
toccata (fuori dall'ambito di questa richiesta).

**Verifica:** da fare alla prossima sessione con pytest (51/51 attesi,
nessun test tocca `/orario/globale` con dati di sostegno) e controllo
visivo con un docente di sostegno reale inserito in griglia — non
eseguibile in questo ambiente (sandbox senza le dipendenze Python del
progetto).

### Task 19septies — Chiusura task aperti (nessuna azione)
Su richiesta esplicita di Roberto, i task/note in sospeso elencati sotto
sono stati chiusi così come sono, senza ulteriori interventi:

- **Task 19quinquies**: le 2 assegnazioni cattedra 2026-2027 mancanti
  dopo il ripristino (docente id 102/classe concorso 2, docente id
  1/classe concorso 11, entrambe tipo TI) **non** sono state
  reinserite — se servono, andranno aggiunte a mano in futuro. Il DB
  ripristinato resta pubblicato solo localmente su questa macchina, non
  ricaricato su Google Drive.
- **Sessione 30, Task 10**: il report GDPR resta fermo alla v2.2, in
  attesa di riscontro dal DPO sui quattro punti aperti (base giuridica,
  residenza dati tenant Google Workspace, copertura DPA per Drive uso
  amministrativo, verifica registro trattamenti su Spaggiari).
- **Sessione 23**: `pianifica_permessi()` e la vista orario globale
  restano senza gli slot dei docenti di sostegno — non implementato.

Nessuna modifica al codice o al database in questa voce.

### Task 19sexies — Login CSRF su ministudio dopo il ripristino chiave
Dopo aver sincronizzato la chiave di cifratura e ripubblicato il DB su
Drive (Task 19quater/quinquies), il login su ministudio falliva con
"Bad Request: The CSRF tokens do not match", indipendente da browser,
cache e orologio di sistema (tutti esclusi in diagnosi).

Diagnosi: confrontando il token nel campo nascosto del form inviato
con il token dentro il cookie di sessione effettivamente mandato dal
browser (decodificati entrambi manualmente, formato itsdangerous), i
due NON coincidevano — prova diretta che la pagina inviata era
disallineata dalla sessione attiva. Causa reale: sul MacBook Pro di
Roberto era rimasta aperta una scheda su `localhost:5002` mentre si
lavorava sul Mac mini via condivisione Finder/schermo — le due
macchine hanno istanze CaronteApp separate (stesso indirizzo locale,
server diversi), ed è facile confondersi su quale finestra si sta
usando durante lo screen sharing, inviando il form dalla scheda
sbagliata. Nessun bug applicativo: chiudendo la scheda sull'altro Mac
e ripetendo il login su una sola finestra pulita, ha funzionato.

Nessuna modifica al codice per questo punto — solo diagnosi e
procedura operativa da tenere a mente quando si usano le due macchine
in contemporanea con screen sharing attivo.

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

### Task 19quater — Due problemi emersi dopo il `git pull` su ministudio
Dopo l'aggiornamento del codice, il primo avvio su ministudio ha
mostrato due problemi distinti, entrambi diagnosticati e corretti:

**1) Chiave di cifratura non condivisa tra le macchine (bloccante).**
Lo scarico del DB da Drive è fallito con `cryptography.fernet.InvalidToken`.
Causa: la chiave Fernet (`data/backup/.backup_key`) è generata localmente
alla prima esecuzione su ogni macchina (`_get_or_create_key()` in
`modules/backup_cifrato.py`) e non viene mai distribuita — per design,
dato che è un segreto e non va messa su git. Il Mac "ministudio" ha
quindi una chiave diversa da quella con cui il file su Drive è stato
cifrato, e non può decifrarlo. Il vero problema è che lo script
proseguiva comunque silenziosamente: `sync_db.py scarica` non
intercettava l'eccezione, `avvia_caronte.sh` non controllava l'esito e
avviava l'app con il DB locale superato, poi allo spegnimento lo
ricaricava su Drive sovrascrivendo la cronologia buona con dati
vecchi/sbagliati — rischio concreto di perdita progressiva dei backup
buoni nella rotazione a 10 versioni.

Corretto:
- `sync_db.py::scarica()` ora intercetta `InvalidToken`, stampa
  un messaggio esplicito (serve copiare `.backup_key`/`.backup_salt`
  dalla macchina che ha il DB buono), e NON tocca il DB locale.
- Il blocco `__main__` esce con `sys.exit(1)` in questo caso specifico
  (prima usciva sempre con successo).
- `avvia_caronte.sh` controlla l'esito di `sync_db.py scarica`: se fallisce,
  interrompe l'avvio prima di lanciare Flask e non esegue mai il `carica`
  finale.
- Aggiunta anche una seconda protezione: se Flask termina da solo con
  errore (crash, come il caso aule_new sotto) invece che per CTRL+C,
  lo script salta il ricaricamento automatico su Drive e avvisa
  l'utente, invece di pubblicare uno stato di migrazione a metà.
- **Azione richiesta all'utente** (non automatizzabile da qui): copiare
  il file `data/backup/.backup_key` (l'unico che conta per la cifratura;
  `.backup_salt` è solo un marcatore, non è realmente usato) dal Mac
  con il DB buono a ministudio, via canale diretto (AirDrop/USB), prima
  di rilanciare `avvia_caronte.sh` lì.

**2) `aule_new` residua da un crash precedente.**
Il crash della sera prima (Task 19ter) aveva lasciato una tabella
`aule_new` vuota nel DB locale — la CREATE TABLE era andata a buon fine
prima che l'INSERT fallisse, e non essendo mai stata droppata è rimasta
lì. Il tentativo successivo di `_migra_vincolo_aule()` falliva quindi
con "table aule_new already exists". Aggiunta una `DROP TABLE IF EXISTS
aule_new` difensiva subito prima della CREATE TABLE, così un run
interrotto a metà non blocca più i tentativi successivi.

Verificato: pytest 51/51, simulazione dello scenario chiave-sbagliata
(exit code 1, nessuna scrittura sul DB locale), DB reale invariato
(`PRAGMA integrity_check` → ok, 39 righe in aule).

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
