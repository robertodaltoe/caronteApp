# CaronteApp — guida rapida per Claude Code

Gestione supplenze, banca ore, recuperi, organico e organizzazione
docenti — IIS "Leonardo da Vinci", Chiavenna. Flask + SQLAlchemy +
SQLite, porta 5002. Sviluppatore/utente unico: Roberto (Robi),
vicepreside. Repo: `github.com/robertodaltoe/caronteApp`, locale in
`/Users/Roberto/CaronteApp`.

**Prima di lavorare qui, leggi `DEVLOG.md`** (ordine cronologico
inverso, voce più recente in cima — oggi ~3700 righe). Questo file
orienta rapidamente, non sostituisce il devlog: per capire il perché
di una scelta specifica, cerca lì la sessione/task pertinente.

## Regole non negoziabili (rispettate sistematicamente in ~70 task)

1. **Mai scrivere su `database.db` reale durante sviluppo/debug.** Ogni
   verifica va fatta su una copia isolata (`/tmp/...`) — anche i test
   funzionali "innocui". È già successo per errore (Sessione 31, modulo
   Esami Integrativi: un test end-to-end ha scritto un candidato di
   prova sul DB reale perché `create_app()` punta lì di default se non
   diversamente specificato) — rimediato subito, ma è la ragione per
   cui va sempre passato esplicitamente un DB di test.
2. **Backup cifrato prima di ogni modifica strutturale al database
   reale**, con nome file che descrive il motivo e timestamp (es.
   `database_20260807_2010_pre_fix_lsp_atipica.db.enc`). Usa
   `modules/backup_cifrato.py::crea_backup_cifrato`.
3. **`PRAGMA integrity_check` dopo ogni scrittura sul DB reale.**
4. **Verifica end-to-end prima di dire "fatto"**: mai solo `py_compile`
   o sintassi. Il pattern consolidato per modifiche che toccano la
   logica di scrittura (non solo di visualizzazione) è **snapshot-diff**:
   due copie identiche del DB, stesso identico input/richiesta HTTP su
   entrambe (una col codice vecchio, una col nuovo), confronto riga per
   riga dello stato finale delle tabelle coinvolte. Usato ripetutamente
   nelle sessioni di "consolidamento business logic" (21, 22, 24, 25,
   26, 27, 28, 29) per garantire che un refactor non cambi comportamento.
5. **`git show HEAD:<file>` spesso NON è una base affidabile** per
   ricostruire "la versione precedente" — molte sessioni di sviluppo
   sono passate senza commit intermedi (lavoro via Cowork/sandbox che a
   volte non riesce a fare commit/push per problemi di lock sul mount).
   Quando serve un confronto prima/dopo, meglio catturare il corpo della
   funzione originale a mano prima di modificare, invece di fidarsi
   ciecamente di un diff con HEAD.
6. **Segnalare, mai decidere al posto di Roberto** su dati ambigui:
   anagrafiche potenzialmente duplicate, valori sospetti, cattedre su
   classi di concorso implausibili. Il pattern ricorrente è: si trova
   l'anomalia, si segnala con i dettagli, si aspetta conferma esplicita
   prima di unire/eliminare/correggere. Non sempre l'ipotesi è corretta
   — "Ghezzi Andrea"/"Ghezzi Angelo" sembravano un duplicato ma erano
   due persone reali diverse (falso allarme, verificato prima di agire);
   "Tramontana" era invece un duplicato vero.
7. Se una sessione gira in sandbox Linux (Cowork) invece che sul Mac
   diretto, annotarlo nel devlog. Limiti noti della sandbox: WeasyPrint
   assente (fallback HTML, non è un bug), e scritture dirette sul
   mount di rete verso il Mac che falliscono con "disk I/O error" per
   problemi di locking SQLite — quando serve scrivere sul DB reale da
   sandbox, lavorare su una copia locale e poi trasferire il risultato
   con `open()+os.fsync()`, non un semplice `cp`.

## Architettura in breve

- **`app.py`** — entry point. Crea l'app, gestisce le migrazioni
  automatiche additive in `_auto_migrate()` (colonne nuove su tabelle
  esistenti — pattern usato costantemente, mai richiede intervento
  manuale sul Mac di Roberto), avvia il thread di `modules/auto_sync.py`
  in background (guardia su `WERKZEUG_RUN_MAIN`, non su `app.debug` —
  quest'ultimo è sempre `False` a quel punto di `create_app()`, un bug
  già preso e corretto una volta, non ripeterlo). Contiene anche
  `_migra_vincolo_aule()` e altre migrazioni "pesanti" (che richiedono
  ricreare una tabella, tipico limite SQLite su `ALTER TABLE`).
- **`models/`** — un file per entità (SQLAlchemy). Tabelle chiave:
  `docente`, `assenza`, `supplenza`, `indisponibilita`, `piano_studi`,
  `assegnazione_docente`/`assegnazione_classe`, `movimento_banca_ore`,
  `cattedra_organico`, `sync_conflitto`, `sync_tombstone`,
  `esami_integrativi_*`. Occhio ai campi "congelati alla creazione"
  (es. `id_cc_default` su `piano_studi`, `ANNO_SCOL_CORRENTE` calcolata
  una sola volta al boot in vecchi punti di `attivita_ist.py`) — non si
  aggiornano da soli quando la situazione reale cambia, causa nota di
  bug silenziosi (badge sbagliati, anno sbagliato finché non si
  riavvia il server).
- **`routes/`** — un blueprint per area funzionale, quasi 1:1 con la
  navbar. Permessi in `BLUEPRINT_PERMESSI` dove richiesti (non tutte le
  route lo richiedono — es. `/guida`, `/ricerca` sono aperte a
  chiunque sia loggato).
- **`modules/`** — logica di dominio riusata da più route. Diversi
  moduli sono nati da un refactor esplicito ("consolidamento business
  logic", roadmap item #18) per estrarre logica da route diventate
  troppo lunghe: `assenze_registrazione.py`, `pianificazione_permessi.py`,
  `suggerimenti_supplenza.py`, `attivita_effetti.py`,
  `recupero_giugno_calendario.py`, `recupero_agosto_calendario.py`.
  Il pattern è sempre lo stesso: la funzione di modulo fa l'orchestrazione
  pura (parsing, calcolo, creazione oggetti) e ritorna un risultato o
  un dict `{'msg':..., 'cat':...}`; la route fa solo commit/audit
  log/flash/redirect.
- **`templates/`** — Jinja2. Pattern ricorrente: macro condivise per
  non duplicare markup di tabella (es. `tabella_eventi` in
  `attivita_ist/lista.html`), e per pagine sequenziali un context
  processor a livello di **app** (non di blueprint — registrarlo su
  un solo blueprint lo rende invisibile alle pagine di altri blueprint,
  bug già preso una volta con la barra passi di Impostazione Anno che
  non compariva su Aule/Assegnazioni).
- **Wizard "Impostazione Anno"** — 13 passi in sequenza per preparare
  un nuovo anno scolastico, con barra di navigazione condivisa
  (`_step_nav.html`, iniettata da un context processor su `app.py`).
  Concetti-anno da NON confondere fra loro, causa ricorrente di bug:
  - `get_anno_corrente()` — anno operativo reale (cambia il 1°
    settembre secondo calendario, o è configurabile a mano).
  - `_anno_default_piano()` — l'anno più recente con dati reali nel
    piano studi/calcolo organico (quello "in preparazione").
    Confonderli ha causato più bug distinti: box riepilogo che
    guardavano l'anno sbagliato (Task 23), docenti del 2026-2027
    visibili anche nel 2025-2026 (Task 35), pagine ferme sull'anno
    vecchio senza modo di cambiarlo (Task 31).
  - Alcune viste distinguono anche "fatto" vs "diritto" per l'organico
    (`CattedraOrganico.tipo`): la convenzione corretta, applicata dopo
    più correzioni, è **preferire sempre il fatto, ricadere sul
    diritto solo se il fatto manca** — non il contrario (Task 24, 25).

## Sync multi-postazione (assenze/supplenze/indisponibilità)

Roberto lavora da più macchine (MacBook Pro personale + "ministudio",
talvolta un Mac mini), con `database.db` pubblicato/scaricato da Google
Drive. Due livelli distinti:

- **`sync_db.py`** — check-out/check-in manuale, NON fa merge. Il file
  condiviso è cifrato (`database.db.enc`, Fernet — stessa chiave
  locale usata per i backup, generata alla prima esecuzione su ogni
  macchina e MAI distribuita automaticamente: se due macchine hanno
  chiavi diverse, la seconda non può decifrare il file dell'altra —
  errore da riconoscere: `cryptography.fernet.InvalidToken`. In quel
  caso `sync_db.py` non deve mai proseguire silenziosamente con un DB
  locale superato: intercetta l'eccezione, non tocca il DB locale, e
  richiede di copiare a mano `.backup_key` dalla macchina buona).
- **`modules/auto_sync.py`** — sopra a questo, un thread in background
  che ogni 30s fa un merge **additivo** automatico, solo su `assenze`,
  `supplenze`, `indisponibilita` (non su Assegnazioni/AttivitaFuoriAula:
  hanno tabelle collegate/id auto-referenziali, valutato e
  deliberatamente escluso — troppo delicate per merge automatico).

Concetti chiave se tocchi questo modulo (5 bug distinti corretti in
sequenza durante il collaudo reale, tutti nel devlog sotto Task 46):
- **Chiave logica** per riga (es. docente+data+fascia oraria per le
  assenze — **mai** includere il `motivo`/campo di contenuto nella
  chiave, o due varianti dello stesso evento vengono sommate invece
  che segnalate come conflitto), mai l'id autoincrementale.
- **Tombstone** (`sync_tombstone.py`) per propagare le eliminazioni —
  senza, un'eliminazione locale viene "resuscitata" al giro successivo
  perché vista come riga nuova da importare (era il bug più
  importante trovato in collaudo).
- **Pubblicazione anche quando le novità sono solo locali**, non solo
  quando arrivano righe dal remoto — altrimenti nessuna delle due
  macchine vede mai i dati dell'altra finché qualcuno non riavvia.
- **Risoluzione "tieni locale" deve essere memorizzata**, non solo
  applicata una volta — altrimenti lo stesso conflitto ricompare ogni
  giro (ciclo infinito riprodotto e corretto in collaudo).
- **Conflitti veri** (stessa chiave, contenuto diverso) finiscono in
  `sync_conflitti`, mai risolti in automatico — revisione umana da
  `/sync/conflitti`.
- **Limite noto, non risolto**: modificare docente/data di una riga
  già sincronizzata (cambio di chiave logica) non genera tombstone —
  rischio di duplicazione silenziosa. Non affrontato finché non
  emerge come problema reale.

## Pattern di bug ricorrenti (utile per debug futuro)

- **Filtri "corretti" che nascondono un caso limite reale.** Un filtro
  pensato per evitare doppi conteggi (es. `compresenza=False` per non
  contare due volte le ore quando una CC ha sia ore proprie sia ore di
  compresenza) fa sparire del tutto le righe che esistono SOLO in
  quella condizione (Task 44, 6 classi di concorso "solo compresenza"
  invisibili ovunque). Quando qualcosa "non compare da nessuna parte"
  nonostante i dati esistano nel DB, sospettare prima un filtro
  troppo aggressivo, non il modello.
- **Backend pronto ma non raggiungibile dall'interfaccia.** Route già
  scritte e funzionanti ma senza link/pulsante che le richiami: pagina
  Agenda (irraggiungibile per mesi), pulsante "Nomina" per placeholder
  supplenti (Task 42), pagina "Confronto TI↔Organico USR" standalone
  (Task 26), gestione tipi di incarico (Task 30). Quando Roberto chiede
  "dov'è la funzione X", verificare prima se esiste già nel backend
  prima di riscriverla da zero.
- **Due meccanismi paralleli per lo stesso scopo.** Quando emergono
  (es. la sezione "Altri docenti" aggiunta sopra a una griglia già
  esistente con lo stesso scopo), Roberto preferisce sistematicamente
  unificarli a uno solo piuttosto che tenerli sincronizzati a mano.
- **Campi "congelati" alla creazione, mai più aggiornati.**
  `id_cc_default` su `piano_studi`, `ANNO_SCOL_CORRENTE` calcolata una
  volta a livello di modulo — causano falsi positivi/negativi in badge
  e alert quando la situazione reale cambia ma il campo resta fermo.
- **`id` di riga confuso con `id_materia`/FK vera.** Il bug più serio
  mai trovato nel progetto (Task 19undecies/19duodecies): il form
  multi-materia in Assegnazioni salvava l'id della riga di PianoStudi
  al posto dell'id reale della Materia — sistemico, presente da tempo,
  in 18 casi reali su dati di produzione. Quando una FK sembra
  "puntare a caso" a un'altra riga plausibile, verificare sempre se si
  sta confondendo la PK della tabella sorgente con la FK verso la
  tabella di destinazione.
- **Un fix applicato al posto sbagliato perché la stessa verifica è
  duplicata altrove.** Più volte la stessa logica di business esiste
  in 2-3 punti indipendenti dell'app (es. "TI↔Organico USR" esisteva
  standalone, inline nel Passo 8, e in dashboard-anno — Task 24/25:
  corretto solo il primo, Roberto continuava a vedere il bug perché
  guardava il secondo). Quando si corregge un comportamento, cercare
  con grep se la stessa logica è duplicata altrove prima di dichiarare
  "fatto".
- **Un conteggio di righe invariato non esclude modifiche ai valori.**
  Un ripristino da backup verificato solo contando le righe per tabella
  ha silenziosamente cancellato modifiche a 15 righe esistenti (Sessione
  32) — il conteggio era identico prima/dopo, ma i *valori* erano
  cambiati nel frattempo. Confrontare sempre riga per riga, non solo il
  totale, quando si valuta un ripristino.

## Ambiente

- Dipendenze: `requirements.txt`, venv locale in `venv/` (attenzione:
  è già capitato che il venv puntasse a un path di un'altra macchina/
  progetto — se `pip`/import falliscono in modo strano, verificare lo
  shebang di `venv/bin/pip` prima di perdere tempo altrove;
  rigenerarlo da zero è spesso più veloce che debuggarlo).
- Test: `pytest`, suite in `tests/` — 51 test all'ultimo aggiornamento
  del devlog, farli passare tutti prima di ogni consegna.
- WeasyPrint richiede librerie di sistema (`brew install pango cairo
  gdk-pixbuf libffi` su macOS, vedi README.md) — già installate sul Mac
  di Roberto; assenti in sandbox Linux, dove esiste un fallback HTML
  automatico (non è un bug se succede fuori dal Mac).
- Porta 5002, avvio con `./avvia_caronte.sh` (macOS/Linux) o
  `avvia_caronte.bat` (Windows). `avvia_caronte.sh` ora blocca l'avvio
  se `sync_db.py scarica` fallisce (es. chiave di cifratura non
  sincronizzata tra macchine), invece di partire silenziosamente con
  un DB locale superato.
- `database.db` **non è nel repo** — va copiato a mano su ogni nuova
  macchina.
- Funzionalità macOS-only: invio bozze email via Mail.app (AppleScript)
  — su Windows/Linux le bozze `.eml` restano scaricabili.
- `CARONTE_SKIP_LOGIN=1` per bypassare il login in sviluppo locale.

## Cosa NON fare senza chiedere

- Non estendere il sync automatico a strutture con tabelle collegate
  (Assegnazioni, AttivitaFuoriAula) — motivo già valutato e respinto
  esplicitamente (Task 46, ultimo aggiornamento).
- Non unire anagrafiche duplicate di docenti senza conferma esplicita
  di Roberto, anche quando il pattern sembra identico a casi già
  risolti (Agrò id 2/102, Tramontana id 81/96) — verificare sempre
  prima che non siano invece due persone reali diverse (falso allarme
  già capitato con "Ghezzi").
- Non rimuovere/allentare un controllo duplicati su salvataggi
  multi-riga senza capire prima la vera chiave logica — più casi di
  chiavi insufficienti hanno causato scarti errati di righe legittime
  (slot multipli di Consigli di Classe nello stesso giorno, Task 47).
- Non toccare `ANNO_SCOL_CORRENTE` calcolata a livello di modulo in
  `attivita_ist.py` (righe 13/40/457/605/607) senza affrontare
  l'intero pattern insieme — è un problema noto e rimandato
  esplicitamente (Task 31), non una svista da correggere di sfuggita.
- Non aggiornare il report GDPR (`CaronteApp_GDPR_Report.docx`, fermo
  a v2.2) finché non arriva riscontro dal DPO (Avv. Emanuela Caricati)
  sui punti aperti: base giuridica, residenza dati del tenant Google
  Workspace, copertura DPA per l'uso amministrativo di Drive.
