"""
Contenuto della sezione "Guida" (FAQ + manuali d'uso), unica fonte per
sia la pagina HTML interattiva che il PDF scaricabile di ogni sezione
— evita di dover scrivere due volte lo stesso testo in due punti che
prima o poi finirebbero per non coincidere più.

Pensato per chi usa l'app ogni giorno (segreteria, collaboratore del
DS) ma non l'ha sviluppata: linguaggio semplice, un passo alla volta,
niente termini tecnici non spiegati.

Per aggiungere una nuova sezione: aggiungere una voce alla lista
SEZIONI qui sotto con lo stesso formato delle altre. Non serve
toccare le route o i template — vengono generati automaticamente.
"""

SEZIONI = [
    {
        'slug': 'dashboard',
        'titolo': 'Dashboard',
        'icona': '⌂',
        'riassunto': 'La situazione di un giorno: chi è assente, chi copre, chi manca ancora.',
        'a_cosa_serve': (
            'La Dashboard è la prima pagina che vedi aprendo CaronteApp. Mostra, per un '
            'giorno scelto, tre cose: i docenti assenti, le supplenze (chi copre quali ore) '
            'e le indisponibilità (docenti non disponibili per un motivo diverso da un\'assenza). '
            'È il punto da cui si parte ogni mattina per organizzare le sostituzioni.'
        ),
        'passi': [
            ('Scegli il giorno',
             'In alto trovi tre scorciatoie — Oggi, Domani, Dopodomani — oppure un calendario '
             'per scegliere una data qualsiasi.'),
            ('Guarda le supplenze scoperte',
             'Le supplenze senza un sostituto assegnato sono evidenziate. Per ognuna trovi un '
             'menu a tendina con i docenti disponibili per quell\'ora: selezionane uno e conferma.'),
            ('Controlla i suggerimenti',
             'Il menu propone per primi i docenti più adatti a coprire quell\'ora (disponibili, '
             'senza altri impegni, con ore di completamento da recuperare). Puoi comunque scegliere '
             'chiunque altro dalla lista.'),
            ('Registra una nuova assenza',
             'Il pulsante "Registra assenza" in alto a destra ti porta al modulo dedicato — vedi '
             'la guida "Assenze".'),
        ],
        'faq': [
            ('Perché una supplenza resta "scoperta" anche dopo che ho assegnato un docente?',
             'Controlla di aver premuto il pulsante di conferma dopo aver scelto il nome dal menu: '
             'la sola selezione dal menu a tendina non basta, va confermata.'),
            ('Non vedo un docente tra i suggeriti per una supplenza: perché?',
             'Il docente potrebbe essere già impegnato in quell\'ora (lezione, altra supplenza) o '
             'segnato come indisponibile per quel giorno/ora. Puoi comunque cercarlo scorrendo tutto '
             'il menu — i suggerimenti sono solo i primi proposti, non un filtro.'),
            ('La dashboard mostra dati aggiornati in tempo reale?',
             'Sì, quello che vedi riflette sempre i dati più recenti salvati sul database in uso '
             'in quel momento su questo computer.'),
        ],
        'attenzione': (
            'La Dashboard mostra solo il giorno selezionato. Per una visione sui prossimi giorni '
            'usa la pagina Agenda.'
        ),
    },
    {
        'slug': 'assenze',
        'titolo': 'Assenze',
        'icona': '✎',
        'riassunto': 'Registrare l\'assenza di un docente e generare automaticamente le coperture.',
        'a_cosa_serve': (
            'Questa pagina serve per segnalare che un docente non sarà a scuola in un certo '
            'giorno (o periodo) per un motivo come malattia, permesso, legge 104, ecc. '
            'Appena registri l\'assenza, il sistema genera da solo le supplenze da coprire per '
            'ogni ora di lezione toccata da quell\'assenza.'
        ),
        'passi': [
            ('Apri "Registra assenza"',
             'Dal pulsante rosso in alto nella barra di navigazione, oppure dalla Dashboard.'),
            ('Scegli il docente e la data',
             'Puoi indicare un solo giorno o un intervallo di più giorni (es. un\'intera settimana '
             'di malattia) in un unico inserimento.'),
            ('Indica il tipo',
             'Se sei collaboratore del DS vedi solo due opzioni per le assenze vere e proprie: '
             '"Permesso orario" (ore che il docente dovrà recuperare) oppure "Non recuperabile" '
             '(qualunque altro motivo — malattia, lutto, permesso personale... non è di tua '
             'competenza saperlo). Ferie e cambio turno restano scelte a parte, senza bisogno di '
             'indicare un motivo. DS, DSGA e segreteria vedono invece anche il motivo specifico, e '
             'possono assegnarlo in un secondo momento quando arriva la giustificazione.'),
            ('Scegli le ore',
             'Puoi segnare "tutta la giornata" oppure solo alcune ore specifiche (es. un permesso '
             'orario di 2 ore).'),
            ('Conferma',
             'Il sistema salva l\'assenza e crea automaticamente le supplenze scoperte per le classi '
             'coinvolte in quelle ore — pronte da assegnare dalla Dashboard.'),
        ],
        'faq': [
            ('Ho sbagliato a registrare un\'assenza: come la correggo?',
             'Aprila dalla Dashboard del giorno in questione e modificala, oppure eliminala con il '
             'pulsante ✕ — verranno rimosse anche le supplenze generate automaticamente insieme ad essa.'),
            ('Qual è la differenza tra un\'assenza e un\'indisponibilità?',
             'L\'assenza è quando il docente non è a scuola e serve un sostituto per le sue classi. '
             'L\'indisponibilità è quando il docente è comunque disponibile per il proprio orario ma '
             'NON può essere usato per coprire supplenze in certe ore (es. è impegnato in un colloquio). '
             'Vedi la guida "Indisponibilità" per i dettagli.'),
            ('Se registro un\'assenza di più giorni, devo ripetere l\'inserimento ogni giorno?',
             'No: scegliendo un intervallo di date in un\'unica registrazione, il sistema crea da solo '
             'un\'assenza per ciascun giorno del periodo (esclusi i giorni di sospensione delle lezioni).'),
            ('Perché non vedo più le voci "Malattia", "Lutto", "Permesso personale"...?',
             'Per tutelare la riservatezza dei docenti, un collaboratore del DS non ha bisogno di '
             'conoscere il motivo specifico di un\'assenza — solo se comporta un\'ora da recuperare '
             'o no. Il motivo esatto lo vedono e lo assegnano DS, DSGA e segreteria, quando serve.'),
        ],
        'attenzione': (
            'Eliminando un\'assenza vengono eliminate anche le supplenze collegate, comprese quelle '
            'già assegnate a un sostituto: controlla prima di confermare.'
        ),
    },
    {
        'slug': 'supplenze',
        'titolo': 'Supplenze',
        'icona': '⇄',
        'riassunto': 'Chi copre quale classe, ora per ora — assegnazione manuale o automatica.',
        'a_cosa_serve': (
            'Le supplenze nascono quasi sempre in automatico quando registri un\'assenza (vedi '
            'la guida "Assenze"), ma da questa pagina puoi anche crearne una a mano — utile per '
            'situazioni che non passano dal modulo assenze, es. una copertura decisa direttamente '
            'per un\'ora specifica.'
        ),
        'passi': [
            ('Per assegnare un sostituto a una supplenza già esistente',
             'Il modo più rapido è dalla Dashboard del giorno: ogni supplenza scoperta ha un menu a '
             'tendina con i docenti disponibili, da confermare con un clic.'),
            ('Per creare una supplenza nuova da zero',
             'Vai su "Supplenze → Nuova": scegli data, ora, classe, il docente assente (se pertinente) '
             'e il sostituto.'),
            ('Se non trovi un sostituto disponibile',
             'Puoi lasciare la supplenza "scoperta" (resterà visibile in Dashboard finché non viene '
             'assegnata) oppure segnarla come "classe non assegnabile" se non è proprio possibile '
             'coprirla.'),
            ('Note visibili sul display',
             'Il campo "Note display" è quello che compare sul monitor esposto a scuola (se attivo): '
             'usalo per messaggi brevi e chiari per gli studenti/docenti (es. "in aula magna").'),
        ],
        'faq': [
            ('Che differenza c\'è tra "note" e "note display"?',
             '"Note" sono appunti interni, visibili solo nell\'app. "Note display" comparirono invece '
             'sul monitor pubblico della scuola, se collegato — vanno tenute brevi e comprensibili '
             'a chi le legge senza altro contesto.'),
            ('Posso assegnare lo stesso docente a due supplenze nella stessa ora?',
             'Il sistema non lo impedisce automaticamente in ogni caso, ma i suggerimenti evitano di '
             'proporre un docente già impegnato in quell\'ora — controlla comunque prima di confermare.'),
            ('Come segno che una supplenza è stata coperta con un\'ora di recupero (banca ore)?',
             'Scegli il tipo "recupero" al momento dell\'assegnazione: il sistema registra da solo il '
             'movimento corrispondente nella Banca Ore del docente sostituto.'),
        ],
        'attenzione': (
            'Una supplenza segnata come "non assegnabile" resta comunque visibile: usala solo quando '
            'è davvero impossibile coprire quell\'ora, non come parcheggio temporaneo.'
        ),
    },
    {
        'slug': 'indisponibilita',
        'titolo': 'Indisponibilità',
        'icona': '🚫',
        'riassunto': 'Segnalare quando un docente non può essere usato per una supplenza (ma è comunque a scuola).',
        'a_cosa_serve': (
            'Serve per i casi in cui un docente è regolarmente in servizio ma, per un\'ora o un '
            'periodo, non può essere chiamato a coprire una supplenza: colloqui con le famiglie, '
            'un consiglio di classe, un\'uscita didattica, una gara sportiva, un impegno di '
            'formazione. Non è un\'assenza: il docente resta a scuola, semplicemente non va '
            'considerato tra i sostituti disponibili in quelle ore.'
        ),
        'passi': [
            ('Apri "Nuova indisponibilità"',
             'La trovi nel menu Attività o dalla Dashboard/Agenda del giorno interessato.'),
            ('Scegli il docente e il motivo',
             'Colloqui, consiglio di classe, uscita didattica, progetto, gara sportiva, formazione, '
             'riunione o "altro".'),
            ('Scegli la modalità',
             'Giorno singolo, un intervallo di più giorni, oppure ricorrente ogni settimana (utile '
             'per un impegno fisso, es. "ogni martedì mattina per un mese").'),
            ('Scegli le ore',
             'Puoi lasciare "tutta la giornata" selezionata oppure scegliere solo alcune ore.'),
            ('Aggiungi più righe se serve',
             'Il pulsante "+ Aggiungi indisponibilità" permette di registrare più indisponibilità '
             'diverse (anche per docenti diversi) in un unico invio, senza dover ripetere tutta '
             'la procedura da capo ogni volta.'),
        ],
        'faq': [
            ('Se segno un\'indisponibilità, il docente sparisce anche dal suo orario normale?',
             'No. L\'indisponibilità riguarda solo la disponibilità per le supplenze, non l\'orario di '
             'lezione ordinario del docente, che resta invariato.'),
            ('Le indisponibilità che si ripetono ogni settimana vanno inserite ogni volta?',
             'No, per quelle esiste una sezione dedicata ("Indisponibilità ricorrenti") pensata proprio '
             'per gli impegni fissi settimanali, da attivare/disattivare una sola volta.'),
            ('Come elimino un\'indisponibilità inserita per errore?',
             'Dall\'Agenda, trovi il gruppo di indisponibilità di quel giorno con un pulsante per '
             'eliminarle — se erano state generate automaticamente insieme ad altre variazioni '
             '(es. un\'attività fuori aula), vengono rimosse insieme.'),
        ],
        'attenzione': (
            'Non usare l\'indisponibilità al posto dell\'assenza: se il docente non è proprio a '
            'scuola, va registrata un\'assenza (che genera anche le supplenze da coprire), non solo '
            'un\'indisponibilità.'
        ),
    },
    {
        'slug': 'agenda',
        'titolo': 'Agenda',
        'icona': '📅',
        'riassunto': 'La vista d\'insieme sui prossimi giorni: cosa è già programmato.',
        'a_cosa_serve': (
            'Mentre la Dashboard mostra un solo giorno alla volta, l\'Agenda raccoglie in una sola '
            'pagina tutto quello che è già stato programmato per i prossimi 60 giorni: '
            'indisponibilità, assenze future già note, supplenze già assegnate e cambi quadro aperti. '
            'Utile per una visione d\'insieme prima di organizzare la settimana.'
        ),
        'passi': [
            ('Apri l\'Agenda',
             'Dal pulsante viola "📅 Agenda" nella Dashboard — mostra automaticamente i prossimi 60 '
             'giorni a partire da oggi.'),
            ('Consulta le indisponibilità',
             'Sono raggruppate per docente, data e motivo, con le ore indicate in modo compatto '
             '(es. "1ª–3ª, 5ª").'),
            ('Elimina un gruppo se non serve più',
             'Selezionando un gruppo di indisponibilità puoi eliminarlo: se era stato generato in '
             'automatico insieme ad assenze o supplenze collegate (es. da un\'attività fuori aula), '
             'queste vengono rimosse insieme, in modo coerente.'),
        ],
        'faq': [
            ('Perché alcune indisponibilità nell\'Agenda hanno la scritta "Auto"?',
             'Significa che sono state generate automaticamente da un\'altra funzione (tipicamente '
             'un\'attività fuori aula con docenti accompagnatori), non inserite a mano.'),
            ('L\'Agenda si aggiorna da sola quando registro una nuova assenza?',
             'Sì, mostra sempre i dati più recenti — non serve fare nulla per "aggiornarla".'),
        ],
        'attenzione': None,
    },
    {
        'slug': 'cambi-quadro',
        'titolo': 'Cambi quadro',
        'icona': '↻',
        'riassunto': 'Scambi di ore tra docenti, ferie concordate, sorveglianze — al di fuori delle normali assenze.',
        'a_cosa_serve': (
            'Questa pagina serve per registrare accordi che non sono una normale assenza: uno '
            'scambio di ore tra due docenti (uno cede un\'ora, l\'altro la copre e la restituirà più '
            'avanti), ferie o permessi concordati, sorveglianze durante le prove, simulazioni '
            'd\'esame o altre attività alternative.'
        ),
        'passi': [
            ('Apri "Cambi quadro → Nuovo"',
             'Scegli la data e il tipo di cambio (scambio ore, ferie concordate, sorveglianza, '
             'simulazione, attività alternativa, o altro).'),
            ('Indica chi cede e chi copre l\'ora',
             'Puoi registrare più righe insieme se lo scambio riguarda più ore o più classi nello '
             'stesso giorno.'),
            ('Se è uno scambio da restituire',
             'Indica (se già nota) la data prevista di restituzione: comparirà tra gli "aperti" finché '
             'non lo segni come restituito.'),
            ('Segna come restituito',
             'Quando l\'ora viene effettivamente restituita, apri il cambio dall\'elenco e conferma '
             'la data e l\'ora reali della restituzione.'),
        ],
        'faq': [
            ('Perché uno scambio di ore non si registra come una supplenza normale?',
             'Perché uno scambio è un accordo reciproco tra due docenti, con l\'aspettativa di una '
             'restituzione futura — informazione che una supplenza normale non tiene traccia.'),
            ('Cosa succede se annullo un cambio quadro di tipo "ferie concordate"?',
             'Viene rimossa automaticamente anche l\'indisponibilità che era stata generata per quel '
             'giorno, così il docente torna disponibile.'),
            ('Chi può registrare un cambio quadro?',
             'Dipende dai permessi impostati dal DS in Impostazioni → Permessi per ruolo: di norma il '
             'collaboratore può registrare e modificare, mentre segreteria e DS possono solo '
             'consultare. Se un pulsante ti risulta disattivato, è perché il tuo ruolo per questa '
             'sezione è impostato in sola visualizzazione.'),
        ],
        'attenzione': None,
    },
    {
        'slug': 'attivita-fuori-aula',
        'titolo': 'Attività fuori aula',
        'icona': '🧭',
        'riassunto': 'Viaggi d\'istruzione, uscite didattiche, gite — con i docenti accompagnatori.',
        'a_cosa_serve': (
            'Per registrare un\'attività che porta una o più classi fuori dalla normale aula '
            '(viaggio d\'istruzione, uscita didattica, visita guidata...), indicando i docenti '
            'accompagnatori. Per ogni accompagnatore impegnato nell\'attività, il sistema genera '
            'automaticamente le variazioni di orario necessarie per le sue altre classi.'
        ),
        'passi': [
            ('Apri "Attività → Attività fuori aula → Nuova"',
             'Indica titolo, date (anche più giorni), classi coinvolte.'),
            ('Aggiungi gli accompagnatori',
             'Per ciascuno puoi indicare gli slot orari in cui è effettivamente impegnato '
             '(es. solo alcune ore, non l\'intera giornata).'),
            ('Verifica la disponibilità',
             'Il sistema segnala se un accompagnatore risulta già assente, indisponibile o già '
             'impegnato come accompagnatore su un\'altra attività nello stesso slot.'),
            ('Salva',
             'Vengono generate automaticamente le supplenze scoperte per le classi che restano '
             'senza il loro docente in quelle ore.'),
        ],
        'faq': [
            ('Posso modificare gli accompagnatori dopo aver creato l\'attività?',
             'Sì, dalla pagina di modifica dell\'attività — le variazioni di orario collegate '
             'vengono ricalcolate di conseguenza.'),
            ('Cosa succede se annullo un\'attività fuori aula?',
             'Le supplenze e le variazioni generate automaticamente per gli accompagnatori vengono '
             'rimosse insieme.'),
        ],
        'attenzione': None,
    },
    {
        'slug': 'attivita-istituzionali',
        'titolo': 'Attività istituzionali',
        'icona': '🏫',
        'riassunto': 'Scrutini, collegi docenti, consigli di classe — presenze e sostituzioni.',
        'a_cosa_serve': (
            'Per programmare riunioni istituzionali (scrutini, collegio docenti, consigli di '
            'classe) e gestire chi vi partecipa. Include anche l\'assegnazione di un sostituto '
            'quando un docente convocato risulta assente il giorno della riunione.'
        ),
        'passi': [
            ('Apri "Attività → Attività istituzionali"',
             'La lista mostra gli eventi programmati; da "Nuova" crei un evento indicando data, '
             'orario, tipo (scrutinio, collegio...) e i docenti partecipanti.'),
            ('Registra le presenze',
             'Il giorno stesso (o dopo), dalla pagina "Presenze" dell\'evento segni chi era presente '
             'e chi assente — se un docente ha un\'assenza registrata per quell\'ora, compare già '
             'segnalato.'),
            ('Nomina un sostituto per un assente',
             'Dalla pagina "Sostituzioni" dell\'evento, per ogni docente assente il sistema propone '
             'candidati (per materia, dipartimento o perché già presente a scuola per un\'altra '
             'riunione vicina) — scegli e conferma, indicando eventualmente il numero di protocollo.'),
            ('Importa il Piano delle Attività',
             'Se il Piano annuale è già pronto in un file Excel, puoi importarlo da Impostazioni → '
             'Orario invece di inserire ogni riunione a mano.'),
        ],
        'faq': [
            ('Lo stesso docente può essere nominato sostituto per due assenti diversi nella stessa riunione?',
             'No: appena nominato per un assente, il suo nome sparisce dalla lista dei candidati per '
             'gli altri assenti della stessa riunione — non può essere in due posti contemporaneamente.'),
            ('Cosa significa la freccia con l\'orario accanto a un candidato sostituto?',
             'Indica che quel docente ha un\'altra riunione istituzionale lo stesso giorno, subito '
             'prima o dopo — utile per scegliere chi è comunque già a scuola in quella fascia.'),
        ],
        'attenzione': None,
    },
    {
        'slug': 'attivita-differite',
        'titolo': 'Attività differite',
        'icona': '⏱',
        'riassunto': 'Ore di lezione da recuperare in un momento diverso da quello previsto in orario.',
        'a_cosa_serve': (
            'Per registrare ore di lezione "differite" — spostate rispetto al loro slot ordinario '
            'in orario, ad esempio per un evento straordinario che ha bisogno di quell\'aula/classe '
            'in un\'altra fascia.'
        ),
        'passi': [
            ('Apri "Attività → Attività differite"',
             'Trovi l\'elenco delle attività già registrate per il periodo corrente.'),
            ('Aggiungi una nuova attività differita',
             'Indica classe, docente, data e ora originaria e quella in cui viene effettivamente '
             'svolta.'),
        ],
        'faq': [],
        'attenzione': None,
    },
    {
        'slug': 'dipartimenti',
        'titolo': 'Dipartimenti e materie',
        'icona': '📚',
        'riassunto': 'L\'organizzazione dei dipartimenti disciplinari e le materie che li compongono.',
        'a_cosa_serve': (
            'Per gestire l\'elenco dei dipartimenti disciplinari della scuola e collegare ogni '
            'materia al dipartimento di appartenenza — informazione usata, tra l\'altro, per '
            'suggerire sostituti dello stesso dipartimento quando manca un collega della stessa '
            'materia esatta (vedi la guida "Attività istituzionali").'
        ),
        'passi': [
            ('Apri "Impostazioni → Docenti → Dipartimenti e materie"',
             'La trovi nel box "Docenti" della pagina Impostazioni.'),
            ('Aggiungi o modifica un dipartimento',
             'Basta un nome — le materie si collegano separatamente.'),
            ('Assegna una materia a un dipartimento',
             'Dall\'elenco delle materie, scegli il dipartimento di appartenenza per ciascuna.'),
        ],
        'faq': [],
        'attenzione': None,
    },
    {
        'slug': 'piano-personale',
        'titolo': 'Piano attività personale',
        'icona': '📋',
        'riassunto': 'I docenti a cattedra non completa scelgono i propri impegni collegiali dal Piano ufficiale.',
        'a_cosa_serve': (
            'Un docente con cattedra non completa in istituto (orario ridotto, o cattedra completata '
            'in un\'altra scuola) partecipa agli impegni collegiali (collegio, consigli di classe, '
            'dipartimenti...) solo in proporzione alle ore di contratto qui — non per intero come un '
            'docente a cattedra piena. Questa pagina genera per ciascuno di questi docenti un link '
            'personale con cui sceglie, tra gli eventi già calendarizzati nel Piano delle Attività, '
            'quelli a cui parteciperà. Gli scrutini restano sempre obbligatori per tutti e non passano '
            'da qui.'
        ),
        'passi': [
            ('Apri "Attività → Piano attività personale"',
             'L\'elenco mostra solo i docenti con cattedra non completa per l\'anno selezionato, con '
             'la percentuale di cattedra e le ore dovute per ciascuno dei due bucket CCNL.'),
            ('Genera il link per un docente',
             'Il pulsante "Genera link" crea un link personale univoco (nessun account richiesto) — '
             'invialo al docente via email o come preferisci.'),
            ('Il docente sceglie i propri impegni',
             'Aprendo il link, il docente vede l\'elenco degli eventi del Piano e spunta quelli a cui '
             'parteciperà, con un contatore delle ore scelte rispetto alla quota dovuta. Può salvare '
             'e tornare più volte, oppure "Salva e invia" per segnalare che ha finito.'),
            ('Blocca il piano quando è definitivo',
             'Il pulsante 🔒 impedisce ulteriori modifiche dal docente — usalo quando le scelte sono '
             'confermate. Lo sblocco (↺) permette correzioni successive.'),
        ],
        'faq': [
            ('Colloqui scuola-famiglia e formazione rientrano in uno dei due bucket?',
             'Sì. Bucket A: collegio docenti, incontri scuola-famiglia, formazione, altro. '
             'Bucket B: consigli di classe, riunioni di dipartimento/materia, GLO, riunioni referenti '
             'di dipartimento. Solo gli scrutini restano fuori da entrambi (sempre obbligatori per '
             'tutti). L\'elenco esatto compare anche nella pagina del link personale.'),
            ('Cosa succede alla partecipazione del docente agli eventi che non ha scelto?',
             'Non compare più come partecipante previsto per quegli eventi — la sua selezione '
             'personale sostituisce interamente il calcolo automatico "per tutti/per classe/per '
             'dipartimento" usato per un docente a cattedra piena.'),
            ('Come viene calcolata la quota di ore dovute?',
             'In proporzione alle ore di contratto del docente rispetto al riferimento di "cattedra '
             'completa" impostato in Impostazioni → Istituto (di norma 18 ore).'),
            ('Il link scaduto o condiviso per errore si può disattivare?',
             'Sì, il pulsante di rigenerazione crea un nuovo link e rende inutilizzabile quello '
             'precedente.'),
        ],
        'attenzione': (
            'Il link personale non richiede alcun login: chiunque lo riceva può vedere e modificare '
            'il piano di quel docente. Condividilo solo per canali diretti e riservati (email al '
            'docente), mai in modo pubblico. Funziona inoltre solo da un dispositivo collegato alla '
            'rete dell\'istituto: il docente deve compilarlo da scuola, non da casa — avvisalo quando '
            'gli invii il link.'
        ),
    },
    {
        'slug': 'banca-ore',
        'titolo': 'Banca ore',
        'icona': '⏲',
        'riassunto': 'Il saldo ore di ogni docente: supplenze svolte, permessi da recuperare, pagamenti.',
        'a_cosa_serve': (
            'Mostra, per ogni docente e per l\'anno scolastico selezionato, il saldo tra le ore di '
            'supplenza svolte (che il docente ha "a credito") e le ore di permesso orario da '
            'recuperare (che ha "a debito") — al netto delle ore eventualmente pagate invece che '
            'recuperate.'
        ),
        'passi': [
            ('Apri "Banca Ore"',
             'La tabella mostra il saldo di ogni docente attivo per l\'anno scolastico selezionato '
             'in alto (di default quello corrente).'),
            ('Cambia anno per consultare lo storico',
             'Il selettore in alto permette di rivedere il saldo di anni scolastici precedenti, '
             'senza che i movimenti di anni diversi si mescolino tra loro.'),
            ('Apri il dettaglio di un docente',
             'Cliccando sul nome vedi lo storico settimanale dei movimenti, le supplenze svolte e i '
             'permessi presi in quell\'anno.'),
        ],
        'faq': [
            ('Perché un docente neoassunto per il prossimo anno non compare nel saldo dell\'anno corrente?',
             'È corretto: un docente inserito con data di arrivo nell\'anno scolastico successivo non '
             'compare negli anni precedenti a quello, anche se è già stato registrato in anagrafica.'),
            ('Come faccio a sapere quante ore ha ancora da recuperare un docente?',
             'Il saldo negativo (in rosso) indica ore di permesso orario prese e non ancora coperte '
             'da supplenze svolte — il dettaglio del docente mostra la scomposizione completa.'),
        ],
        'attenzione': None,
    },
    {
        'slug': 'report',
        'titolo': 'Report',
        'icona': '📊',
        'riassunto': 'Prospetti riepilogativi per il Dirigente e per la segreteria, anche in PDF/Excel.',
        'a_cosa_serve': (
            'Genera prospetti riepilogativi delle ore (supplenze, permessi, saldo banca ore) per '
            'singolo docente o per l\'intero istituto, esportabili in PDF o Excel — utili per il '
            'Dirigente o per la trasmissione ai competenti uffici.'
        ),
        'passi': [
            ('Apri "Report"',
             'La schermata iniziale mostra un cruscotto d\'insieme sui saldi di tutti i docenti.'),
            ('Apri il report di un singolo docente',
             'Da qui puoi scaricarlo in PDF (pronto da firmare/archiviare) o in Excel.'),
            ('Esporta il report globale',
             'Il pulsante "Esporta tutti" genera un unico file con i dati di tutti i docenti.'),
            ('Prepara le bozze email',
             'Da "Report → Bozze email" puoi generare, per ogni docente, una bozza di email con il '
             'proprio report in allegato — su Mac si apre direttamente in Mail.app, su Windows/Linux '
             'si scarica come file .eml da aprire nel proprio programma di posta.'),
        ],
        'faq': [],
        'attenzione': None,
    },
    {
        'slug': 'orario',
        'titolo': 'Orario',
        'icona': '▦',
        'riassunto': 'L\'orario settimanale di ogni docente — di sostegno e generale.',
        'a_cosa_serve': (
            '"Orario sostegno" mostra e permette di modificare l\'orario dei docenti di sostegno. '
            '"Orario globale" (dove abilitato) mostra l\'orario completo di tutti i docenti, usato '
            'come riferimento per capire chi è impegnato in una certa ora — ma la sua importazione/'
            'modifica massiva resta un\'operazione riservata a DS e DSGA, perché sovrascrive dati '
            'usati da tutta l\'app.'
        ),
        'passi': [
            ('Apri "Orario → Orario sostegno"',
             'Seleziona il docente per vedere/modificare il suo orario settimanale.'),
            ('Consulta "Orario globale"',
             'Se il tuo ruolo è abilitato, mostra la griglia completa di tutti i docenti — utile '
             'come riferimento, non modificabile da questa vista.'),
        ],
        'faq': [],
        'attenzione': None,
    },
    {
        'slug': 'recupero',
        'titolo': 'Recupero (corsi di giugno e agosto)',
        'icona': '📖',
        'riassunto': 'Organizzazione dei corsi di recupero estivi: gruppi, calendario, disponibilità docenti.',
        'a_cosa_serve': (
            'Per organizzare i corsi di recupero del debito formativo che si tengono a giugno e '
            'agosto: creare i gruppi di alunni per materia/classe, verificare la disponibilità dei '
            'docenti (tenendo conto delle loro assenze/ferie nel periodo) e generare il calendario '
            'delle lezioni.'
        ),
        'passi': [
            ('Apri "Recupero → Giugno" oppure "Recupero → Agosto"',
             'Le due sezioni funzionano allo stesso modo ma sono indipendenti — periodi ed elenchi '
             'di gruppi non si mescolano.'),
            ('Crea i gruppi',
             'Per ciascun gruppo indica materia, classi coinvolte, alunni ed eventuale docente/i '
             'assegnato.'),
            ('Controlla i docenti disponibili',
             'La pagina "Docenti disponibili" mostra, per ciascun docente, i giorni liberi nel '
             'periodo e le assenze già note — chi non ha titolo a vedere il motivo specifico lo '
             'vede comunque mascherato, come nel resto dell\'app.'),
            ('Genera il calendario',
             'Il generatore automatico distribuisce le lezioni rispettando i vincoli orari indicati '
             'e senza sovrapposizioni per gli alunni che condividono più gruppi.'),
        ],
        'faq': [
            ('Rigenerare il calendario cancella quello già fatto?',
             'Sì, per i corsi del periodo scelto (giugno oppure agosto): richiede una conferma '
             'esplicita proprio per questo, e non tocca mai le lezioni dell\'altro periodo.'),
        ],
        'attenzione': (
            'Il generatore automatico del calendario elimina e ricrea tutte le lezioni del periodo '
            'scelto: usalo solo quando sei sicuro che gruppi e vincoli siano definitivi.'
        ),
    },
    {
        'slug': 'rientro',
        'titolo': 'Rientro dall\'estero',
        'icona': '✈',
        'riassunto': 'Organizzazione dei colloqui di verifica per gli studenti di rientro da un periodo all\'estero.',
        'a_cosa_serve': (
            'Per organizzare i colloqui di verifica delle competenze per gli studenti che rientrano '
            'da un periodo di studio all\'estero: materie da verificare per classe, candidati, '
            'calendario dei colloqui con i docenti coinvolti.'
        ),
        'passi': [
            ('Apri "Recupero → Rientro dall\'estero"',
             'La trovi nel menu Attività, tra le sezioni di recupero.'),
            ('Indica le materie da verificare per classe',
             'Ogni classe può avere materie diverse da verificare, a seconda del percorso seguito '
             'all\'estero.'),
            ('Aggiungi i candidati',
             'Gli studenti di rientro per cui vanno organizzati i colloqui.'),
            ('Genera il calendario dei colloqui',
             'Assegna automaticamente date/orari/docenti, esportabile in Excel.'),
        ],
        'faq': [],
        'attenzione': None,
    },
    {
        'slug': 'esami-integrativi',
        'titolo': 'Esami integrativi',
        'icona': '📝',
        'riassunto': 'Organizzazione degli esami integrativi/idoneità: candidati e calendario.',
        'a_cosa_serve': (
            'Per gestire i candidati agli esami integrativi (o di idoneità) e organizzare il '
            'relativo calendario con le commissioni coinvolte.'
        ),
        'passi': [
            ('Apri "Recupero → Esami integrativi"',
             'La trovi nel menu Attività, tra le sezioni di recupero.'),
            ('Aggiungi i candidati',
             'Indica classe di destinazione e materie d\'esame per ciascuno.'),
            ('Genera il calendario',
             'Assegna date/orari/commissari, esportabile in Excel.'),
        ],
        'faq': [],
        'attenzione': None,
    },
    {
        'slug': 'docenti',
        'titolo': 'Docenti',
        'icona': '👤',
        'riassunto': 'L\'anagrafica di tutti i docenti: contratto, contatti, classe di concorso.',
        'a_cosa_serve': (
            'L\'elenco anagrafico di tutti i docenti dell\'istituto: dati di contratto (tipo, ore, '
            'part-time), classe di concorso, contatti, orario di colloqui — la base su cui si '
            'appoggiano assenze, supplenze, banca ore e tutte le altre sezioni.'
        ),
        'passi': [
            ('Apri "Impostazioni → Docenti → Anagrafica docenti"',
             'L\'elenco si può filtrare per anno scolastico, per seguire anche i docenti in arrivo '
             '(o in uscita) in un anno diverso da quello corrente.'),
            ('Aggiungi un nuovo docente',
             'Indica almeno cognome, nome e tipo di contratto; puoi aggiungere subito anche la '
             'classe di concorso e le altre informazioni.'),
            ('Modifica un docente esistente',
             'Apri la sua scheda dall\'elenco — se un altro utente sta modificando la stessa scheda '
             'nello stesso momento, il sistema avvisa invece di sovrascrivere in silenzio.'),
        ],
        'faq': [
            ('Un docente che risulta trasferito o pensionato va eliminato?',
             'No, va segnato come "non in servizio" con il motivo (trasferimento/pensionamento/fine '
             'incarico) e l\'anno — resta nello storico ma non compare più tra i docenti attivi.'),
        ],
        'attenzione': (
            'L\'eliminazione definitiva di un docente rimuove anche tutta la sua storia (assenze, '
            'supplenze, banca ore): da usare solo per anagrafiche inserite per errore, mai per un '
            'docente che ha davvero prestato servizio.'
        ),
    },
    {
        'slug': 'organico',
        'titolo': 'Impostazione anno / Organico',
        'icona': '🗂',
        'riassunto': 'Il percorso guidato in più passi per preparare un nuovo anno scolastico.',
        'a_cosa_serve': (
            'Un percorso guidato, passo dopo passo, per preparare tutto ciò che serve all\'avvio di '
            'un nuovo anno scolastico: classi di concorso, piano di studi, classi attive, aule, '
            'calcolo dell\'organico richiesto, confronto con l\'organico assegnato dall\'USR, '
            'docenti per l\'anno, assegnazione classi ↔ docenti.'
        ),
        'passi': [
            ('Apri "Impostazioni → Anno scolastico → Hub impostazione anno"',
             'La barra in alto in ogni pagina della sezione mostra tutti i passi, con quello '
             'corrente evidenziato — puoi saltare avanti/indietro liberamente, non è obbligatorio '
             'seguirli in ordine stretto.'),
            ('Segui i passi principali',
             '1. Classi di concorso · 2. Piano di studi · 3. Materie↔Classi di concorso · '
             '4. Classi attive (+ 4b. Aule) · 5. Calcolo organico richiesto · 6. Organico USR '
             '(+ 6b. Cattedre di potenziamento) · 7. Docenti per anno · 8. Docenti↔Classe di '
             'concorso (+ 8b. Verifica TI↔Organico USR) · 9. Assegnazioni classi→docenti · '
             '10. Docenti↔Materie.'),
            ('Consulta la Dashboard anno',
             'Un riepilogo trasversale sullo stato di avanzamento, utile per capire cosa manca '
             'ancora prima di attivare l\'anno nuovo (vedi la guida "Cambio anno scolastico").'),
        ],
        'faq': [
            ('Qual è la differenza tra questa sezione e "Cambio anno scolastico"?',
             '"Impostazione anno" prepara i dati (può iniziare mesi prima); "Cambio anno scolastico" '
             'è l\'operazione finale che rende l\'anno preparato quello effettivamente operativo per '
             'tutta l\'app.'),
            ('Perché un docente che ho appena inserito per il prossimo anno non compare ancora da nessuna parte?',
             'Se non ha una data di arrivo (anno_scol_inizio) impostata su quell\'anno, il sistema lo '
             'considera non ancora "in servizio" per quell\'anno — controlla il passo "Docenti per '
             'anno".'),
        ],
        'attenzione': None,
    },
    {
        'slug': 'cambio-anno',
        'titolo': 'Cambio anno scolastico',
        'icona': '↺',
        'riassunto': 'L\'operazione, riservata, che rende operativo il nuovo anno scolastico preparato.',
        'a_cosa_serve': (
            'L\'operazione finale — riservata, tipicamente a fine agosto — che attiva ufficialmente '
            'il nuovo anno scolastico come quello operativo per tutta l\'app: dopo, dashboard, '
            'assenze, supplenze e banca ore fanno tutti riferimento al nuovo anno.'
        ),
        'passi': [
            ('Apri "Impostazioni → Anno scolastico → Prepara / Attiva nuovo anno scolastico"',
             'Riservata a chi ha i permessi per questa sezione (di default nessuno: va abilitata '
             'esplicitamente dal DS).'),
            ('Prepara',
             'Verifica che tutto il percorso "Impostazione anno" sia completo per il nuovo anno '
             'prima di procedere.'),
            ('Attiva',
             'Conferma esplicita — da questo momento il nuovo anno diventa quello corrente in tutta '
             'l\'app.'),
        ],
        'faq': [],
        'attenzione': (
            'Questa sezione è esclusa di default per tutti i ruoli configurabili (nemmeno DS/'
            'collaboratore/segreteria ce l\'hanno per default): va abilitata esplicitamente da '
            'Impostazioni → Permessi per ruolo a chi deve poterla usare. È un\'operazione delicata, '
            'da eseguire con calma e non "per errore".'
        ),
    },
    {
        'slug': 'calendario',
        'titolo': 'Calendario scolastico',
        'icona': '📆',
        'riassunto': 'Sospensioni delle lezioni, festività, e i periodi usati da recupero/rientro/esami.',
        'a_cosa_serve': (
            'Per registrare le sospensioni didattiche (festività, ponti, chiusure) — durante quei '
            'giorni le assenze non generano supplenze in classe — e i periodi di riferimento '
            'usati da recupero estivo, rientro dall\'estero ed esami integrativi.'
        ),
        'passi': [
            ('Apri "Impostazioni → Calendario"',
             'La trovi nel box "Calendario scolastico" della pagina Impostazioni.'),
            ('Aggiungi una sospensione didattica',
             'Indica data (o intervallo) e descrizione — es. "Ponte 1° novembre".'),
            ('Configura i periodi',
             'Date di inizio/fine per corsi di recupero giugno/agosto, rientro dall\'estero, esami '
             'integrativi — usate dai rispettivi generatori di calendario.'),
        ],
        'faq': [],
        'attenzione': None,
    },
    {
        'slug': 'istituto',
        'titolo': 'Istituto',
        'icona': '🏛',
        'riassunto': 'Dati anagrafici dell\'istituto, parametri economici, backup del database.',
        'a_cosa_serve': (
            'I dati anagrafici dell\'istituto (nome, indirizzo — usati in intestazioni di report e '
            'PDF), i parametri economici (es. costo orario di una supplenza) e la gestione dei '
            'backup cifrati del database.'
        ),
        'passi': [
            ('Apri "Impostazioni → Istituto → Dati istituto"',
             'Modifica nome, indirizzo e gli altri dati anagrafici.'),
            ('Imposta il costo ora supplenza',
             'Nella stessa pagina, sezione "Parametri economici" — usato nei report per stimare il '
             'costo delle supplenze a pagamento.'),
            ('Gestisci i backup',
             'Da "Backup database" puoi vedere lo storico dei backup cifrati automatici e crearne '
             'uno manuale prima di un\'operazione delicata.'),
        ],
        'faq': [],
        'attenzione': None,
    },
    {
        'slug': 'incarichi',
        'titolo': 'Incarichi',
        'icona': '⭐',
        'riassunto': 'Assegnare incarichi ai docenti (funzioni strumentali, referenti...) e i loro tipi.',
        'a_cosa_serve': (
            'Per assegnare ai docenti incarichi interni (funzioni strumentali, referenti di '
            'progetto, coordinatori...) e — separatamente — per gestire l\'elenco dei tipi e delle '
            'categorie di incarico disponibili nella scuola.'
        ),
        'passi': [
            ('Apri "Impostazioni → Docenti → Incarichi docenti"',
             'Assegna a un docente uno o più incarichi tra quelli disponibili.'),
            ('Gestisci i tipi di incarico',
             'Da "Impostazioni → Istituto → Tipi di incarico assegnabili" puoi aggiungere nuovi tipi '
             'o categorie, prima di poterli assegnare ai docenti.'),
        ],
        'faq': [],
        'attenzione': None,
    },
    {
        'slug': 'assegnazioni',
        'titolo': 'Assegnazioni e aule',
        'icona': '🚪',
        'riassunto': 'Quale docente insegna in quale classe (cattedre) e quale aula usa ogni classe.',
        'a_cosa_serve': (
            '"Assegnazioni" collega i docenti alle classi/cattedre dell\'anno scolastico. "Aule" '
            'indica quale aula usa normalmente ogni classe — informazione usata per segnalare '
            'automaticamente dove si trova una classe, utile a chi deve individuarla rapidamente.'
        ),
        'passi': [
            ('Apri "Impostazioni → Anno scolastico → Assegnazioni classi → docenti"',
             'Per ogni classe di concorso vedi le cattedre da assegnare e i docenti disponibili.'),
            ('Assegna un docente a una cattedra',
             'Indica le ore per classe — il sistema segnala se le ore assegnate superano quelle '
             'della cattedra o del contratto del docente.'),
            ('Gestisci le aule',
             'Da "Impostazioni → Anno scolastico → Aule per classe" assegna l\'aula abituale di '
             'ogni classe; la "Mappa aule" mostra una vista d\'insieme e permette override '
             'temporanei per singola supplenza.'),
        ],
        'faq': [],
        'attenzione': None,
    },
    {
        'slug': 'permessi',
        'titolo': 'Permessi per ruolo',
        'icona': '🔑',
        'riassunto': 'La pagina, riservata al DS, che decide cosa può vedere e fare ogni ruolo.',
        'a_cosa_serve': (
            'Permette al Dirigente Scolastico di decidere, sezione per sezione, cosa può fare '
            'ciascun ruolo (Collaboratore DS, Segreteria Personale): "Esclusa" (la sezione non '
            'compare nemmeno nel menu), "Visualizza" (può consultarla ma non modificare nulla — i '
            'pulsanti di modifica risultano disattivati) o "Modifica" (accesso completo). Il DSGA '
            'ha sempre accesso pieno a tutto e non compare in questa tabella; l\'utente Display vede '
            'solo la pagina Display, sempre — nessuna delle due cose è modificabile da qui.'
        ),
        'passi': [
            ('Apri "Impostazioni → Sistema → Permessi per ruolo"',
             'Visibile solo se il tuo ruolo è Dirigente Scolastico.'),
            ('Scegli il livello per ogni sezione e ruolo',
             'Le righe sono raggruppate per area (Assenze e supplenze, Attività, Banca ore e '
             'report...) per restare orientabili nonostante siano molte.'),
            ('Salva',
             'Le modifiche si applicano subito a tutti gli utenti con quel ruolo.'),
        ],
        'faq': [
            ('Se aggiungo una funzione nuova all\'app in futuro, entra automaticamente in questa tabella?',
             'No, va collegata a mano — se questa pagina mostra un avviso con un elenco di parti '
             'dell\'app "non ancora collegate", significa che sono aperte a chiunque sia loggato: '
             'segnalalo per farle rientrare in una sezione esistente o in una nuova.'),
            ('Perché non trovo il ruolo "dsga" o "display" in questa tabella?',
             'Sono gestiti a parte proprio per evitare che una configurazione qui possa bloccare '
             'l\'unico ruolo capace di correggerla (dsga) o alterare il comportamento fisso della '
             'pagina Display.'),
        ],
        'attenzione': (
            'Escludere per errore una sezione a tutti i ruoli configurabili (compreso il DS) la '
            'rende raggiungibile solo dal DSGA finché qualcuno non la riabilita da questa stessa '
            'pagina — attenzione particolare quando si escludono più sezioni insieme.'
        ),
    },
]


def get_sezione(slug):
    """Ritorna la sezione con lo slug indicato, o None se non esiste."""
    for s in SEZIONI:
        if s['slug'] == slug:
            return s
    return None
