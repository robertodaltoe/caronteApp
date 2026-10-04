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
        'endpoint': 'dashboard.index',
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
             'In alto le frecce ‹ › portano al giorno prima o dopo, "Oggi" torna a oggi e il '
             'calendario permette di scegliere una data qualsiasi. I tre pulsanti "Mostra nel '
             'display" (Oggi, Domani, Dopodomani) non cambiano il giorno della pagina: aprono '
             'il Display su quella data.'),
            ('Guarda le supplenze scoperte',
             'Le supplenze senza un sostituto assegnato sono evidenziate. Per ognuna trovi un '
             'menu a tendina con i docenti disponibili per quell\'ora: selezionane uno e conferma.'),
            ('Controlla i suggerimenti',
             'Il menu propone per primi i docenti più adatti a coprire quell\'ora (disponibili, '
             'senza altri impegni, con ore di completamento da recuperare). Accanto al menu, il '
             'pulsante con la stella ("Suggerisci chi è libero in quest\'ora") apre l\'elenco di '
             'chi è libero. Puoi comunque scegliere chiunque altro dalla lista.'),
            ('Usa i pulsanti in alto per registrare qualcosa',
             'Per il giorno selezionato trovi "+ Assenza" (vedi la guida "Assenze"), '
             '"Indisponibilità", "+ Supplenza", "Potenziamento/compresenza" (vedi la guida '
             '"Potenziamento e compresenza"), "Prospetto" (la stampa delle supplenze del giorno), '
             '"Display", "Agenda" e "Cambi" (vedi la guida "Cambi quadro"). "Registra assenza" è '
             'anche sempre nella barra di navigazione.'),
            ('Le tue sezioni',
             'In cima alla pagina una riga di scorciatoie cambia secondo il ruolo (DS, DSGA, '
             'collaboratore, segreteria) e porta alle pagine che quel ruolo usa di più. Vedi la '
             'guida "Come muoversi nell\'app".'),
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
        'endpoint': 'assenze.nuova',
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
        'endpoint': 'supplenze.nuova',
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
        'endpoint': 'indisponibilita.nuova',
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
             'Dal pulsante "Indisponibilità" della Dashboard del giorno interessato, dall\'Agenda '
             'o cercandola con Ctrl+K. Non è nel menu Attività.'),
            ('Scegli il docente e il motivo',
             'Colloqui, consiglio di classe, uscita didattica, progetto, gara sportiva, formazione, '
             'riunione o "altro".'),
            ('Decidi se generare anche la supplenza',
             'Accanto al motivo c\'è la spunta "Genera supplenza": va attivata quando il docente '
             'non è fisicamente in classe (es. gara, uscita, formazione — per questi motivi è '
             'già preselezionata) e quindi serve qualcuno che copra le sue ore. Se la lasci '
             'vuota l\'indisponibilità resta solo una nota che toglie il docente dai sostituti.'),
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
            'un\'indisponibilità. L\'unica eccezione è la spunta "Genera supplenza" per un impegno '
            'che porta il docente fuori dalla classe (gara, uscita, formazione).'
        ),
    },
    {
        'slug': 'agenda',
        'endpoint': 'agenda.index',
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
        'endpoint': 'cambi.lista',
        'titolo': 'Cambi quadro',
        'icona': '↻',
        'riassunto': 'Scambi di ore tra docenti, ferie concordate, sorveglianze — al di fuori delle normali assenze.',
        'a_cosa_serve': (
            'Nei menu, nella pagina dei permessi e nella ricerca (Ctrl+K) questa funzione si '
            'chiama "Cambi turno"; la pagina stessa si intitola "Cambi quadro orario": è la '
            'stessa cosa. Si raggiunge dal pulsante "Cambi" della Dashboard, dalle scorciatoie '
            'per ruolo o da Ctrl+K. Serve per registrare accordi che non sono una normale assenza: uno '
            'scambio di ore tra due docenti (uno cede un\'ora, l\'altro la copre e la restituirà più '
            'avanti), ferie o permessi concordati, sorveglianze durante le prove, simulazioni '
            'd\'esame o altre attività alternative.'
        ),
        'passi': [
            ('Apri "Cambi turno" e premi "Nuovo"',
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
        'endpoint': 'attivita.lista',
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
        'endpoint': 'attivita_ist.lista',
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
             'orario, tipo (scrutinio, collegio...) e i docenti partecipanti. Il Piano Annuale delle '
             'Attività (vedi la guida "Piano Annuale attività") può generare automaticamente in blocco '
             'consigli di classe, scrutini, GLO e riunioni di dipartimento, invece di inserirli uno a '
             'uno da qui.'),
            ('Registra le presenze',
             'Il giorno stesso (o dopo), dalla pagina "Presenze" dell\'evento segni chi era presente '
             'e chi assente — se un docente ha un\'assenza registrata per quell\'ora, compare già '
             'segnalato. Per gli scrutini, una card in alto mostra a colpo d\'occhio quanti assenti '
             'hanno già un sostituto individuato (es. "3/5") e due link per scorrere rapidamente al '
             'prossimo/precedente evento dell\'agenda, anche su un giorno diverso.'),
            ('Nomina un sostituto per un assente',
             'Dalla pagina "Sostituzioni" dell\'evento, per ogni docente assente il sistema propone '
             'candidati ordinati per comodità: prima chi ha un\'altra riunione lo stesso giorno subito '
             'prima o dopo (è già a scuola), poi a parità di comodità chi condivide la materia o il '
             'dipartimento con l\'assente. Ogni candidato mostra dei pallini colorati numerati (①②③④) '
             'per i motivi che lo rendono adatto — la legenda sotto la lista spiega cosa significa '
             'ciascuno. Scegli, conferma ed eventualmente indica il numero di protocollo.'),
            ('Protocolla in blocco le sostituzioni di un periodo',
             'Dalla pagina "Sostituzioni" (o da "Attività → Attività istituzionali", pulsante '
             '"Protocollazione scrutini") apri il riepilogo di tutte le sostituzioni assegnate: senza '
             'filtri mostra solo quelle ancora senza protocollo, oppure scegli un intervallo di date '
             'per rivederle tutte, incluse quelle già fatte. Il numero di protocollo si può inserire '
             'riga per riga direttamente lì (è lo stesso campo della pagina Sostituzioni del singolo '
             'evento — aggiornarlo da una parte lo aggiorna anche nell\'altra) e l\'intero elenco è '
             'esportabile in Excel.'),
            ('Importa il Piano delle Attività',
             'Se il Piano annuale è già pronto in un file Excel, puoi importarlo da Impostazioni → '
             'Istituto e calendario → Importa piano delle attività, invece di inserire ogni '
             'riunione a mano.'),
        ],
        'faq': [
            ('Lo stesso docente può essere nominato sostituto per due assenti diversi nella stessa riunione?',
             'No: appena nominato per un assente, il suo nome sparisce dalla lista dei candidati per '
             'gli altri assenti della stessa riunione — non può essere in due posti contemporaneamente.'),
            ('Cosa significano i pallini numerati colorati accanto a un candidato sostituto?',
             'Ogni pallino è un motivo per cui quel candidato è adatto, e possono comparire insieme se '
             'valgono più motivi contemporaneamente: ① stessa materia dell\'assente, ② stesso '
             'dipartimento, ③ ha un\'altra riunione lo stesso giorno (subito prima o dopo, quindi è '
             'comodo perché già a scuola), ④ disponibile ma senza nessuno di questi motivi specifici. '
             'L\'ordine della lista segue soprattutto la comodità oraria (③): la materia/il dipartimento '
             'contano come criterio in più a parità di comodità, non scavalcano un candidato molto più '
             'comodo in orario.'),
            ('Dove trovo tutte le sostituzioni di un intero blocco di scrutini, per protocollarle insieme?',
             'Nella pagina "Protocollazione scrutini" (raggiungibile dalla Lista attività o da '
             'qualunque pagina Sostituzioni di uno scrutinio): un elenco con una riga per ogni '
             'sostituzione — docente assente, classe, sostituto e numero di protocollo modificabile '
             'sul posto — esportabile in Excel.'),
        ],
        'attenzione': None,
    },
    {
        'slug': 'piano-annuale-attivita',
        'endpoint': 'attivita_ist.piano_annuale',
        'titolo': 'Piano Annuale attività',
        'icona': '📅',
        'riassunto': 'Formazione obbligatoria, vista mensile, riepilogo ore, generatore Consigli di classe.',
        'a_cosa_serve': (
            'Vedi anche le guide "Piano della formazione" e "Generatore del piano delle attività". '
            'Il "Piano Annuale delle Attività" sostituisce il foglio Excel che prima riassumeva, '
            'mese per mese, tutti gli impegni fuori dall\'orario di lezione (collegi, consigli di '
            'classe, scrutini, formazione) e le ore che ciascun docente vi dedica. In CaronteApp è '
            'calcolato automaticamente dagli eventi di "Attività istituzionali" e dal Piano della '
            'Formazione, invece di essere compilato a mano — e include un generatore che propone da '
            'solo un calendario di Consigli di classe, da correggere invece di costruire da zero.'
        ),
        'passi': [
            ('Consulta la vista mensile',
             'Da "Attività → Piano delle attività" vedi tutti gli eventi istituzionali dell\'anno '
             'raggruppati mese per mese, nell\'ordine in cui si svolgono — lo stesso colpo d\'occhio '
             'del foglio Excel originale, sempre aggiornato con quanto inserito nell\'app.'),
            ('Controlla il riepilogo ore',
             'Dal pulsante "Riepilogo ore" in quella stessa pagina trovi due tabelle: le ore totali '
             'per classe (consigli + scrutini) e, per ogni docente, il confronto tra le ore già '
             'impegnate in collegio/consigli/formazione e la quota che gli spetta secondo il CCNL — '
             'un\'eventuale eccedenza è solo segnalata con un badge rosso, non blocca nulla.'),
            ('Gestisci il Piano della Formazione',
             'Dalla "Panoramica impostazioni" (o con Ctrl+K, cercando "formazione") apri "Piano '
             'della formazione" e crei i corsi dell\'anno: un corso '
             '"obbligatorio per tutti" iscrive in automatico tutti i docenti in servizio; un corso '
             '"volontario" parte senza iscritti e ciascuno si iscrive/disiscrive dalla sua scheda. '
             'Le ore di formazione confluiscono da sole nel Riepilogo ore e nel Piano Attività '
             'Personale di ciascun docente, senza bisogno di inserirle altrove.'),
            ('Genera una bozza di Consigli di classe',
             'Dalla "Panoramica impostazioni" (o con Ctrl+K, cercando "generatore") apri '
             '"Genera piano delle attività" e scegli le classi (prese dalle '
             'Assegnazioni dell\'anno, non dall\'orario — è pronto anche prima che l\'orario '
             'definitivo sia stabilizzato), il periodo, la fascia oraria giornaliera e quali classi '
             'richiedono la presenza del Dirigente. Il sistema propone una bozza che raggruppa più '
             'classi compatibili nello stesso slot (nessun docente in comune, DS non doppiamente '
             'impegnato) rispettando i vincoli orario fissi dell\'istituto (es. rientro pomeridiano '
             'di certi indirizzi) e le scadenze/slot fissi impostati a mano prima di generare.'),
            ('Correggi e conferma la bozza',
             'Ogni riga della bozza (data, ora, presenza DS) resta modificabile a mano, comprese le '
             'classi che il generatore non è riuscito a piazzare (restano segnalate "in conflitto", '
             'mai un errore bloccante) — solo alla conferma vengono creati gli eventi veri in '
             'Attività istituzionali, con i partecipanti già precompilati dalle Assegnazioni.'),
        ],
        'faq': [
            ('Il generatore di Consigli di classe scrive subito gli eventi definitivi?',
             'No: propone solo una bozza modificabile. Gli eventi reali (visibili in "Attività '
             'istituzionali", con presenze e sostituzioni gestibili come per qualunque altra '
             'riunione) vengono creati solo quando confermi la bozza.'),
            ('Perché una classe risulta "in conflitto" nella bozza del generatore?',
             'Significa che, con i vincoli indicati (orario, docenti condivisi, DS), non è stato '
             'trovato nessuno slot libero compatibile nel periodo scelto — va assegnata a mano '
             'direttamente nella bozza, prima di confermare.'),
            ('Da dove prende il generatore l\'elenco dei docenti di una classe?',
             'Dalle Assegnazioni (classi ↔ docenti) dell\'anno scolastico scelto, non dall\'orario '
             'delle lezioni — l\'orario definitivo si stabilizza troppo tardi rispetto a quando serve '
             'preparare il piano annuale.'),
            ('Un\'eccedenza di ore nel Riepilogo ore blocca qualcosa?',
             'No, è solo un avviso visivo (badge rosso "eccede") per farla notare — non impedisce di '
             'programmare altri eventi né di confermare piani/bozze.'),
        ],
        'attenzione': (
            'Il generatore Consigli di classe non tiene conto dell\'orario delle lezioni (per scelta: '
            'si basa sulle Assegnazioni, disponibili prima che l\'orario sia pronto) — verifica comunque '
            'a mano, prima di confermare la bozza, che gli slot proposti non creino conflitti reali con '
            'lezioni già fissate quando l\'orario sarà pubblicato.'
        ),
    },
    {
        'slug': 'attivita-differite',
        'endpoint': 'att_differite.index',
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
             'È la pagina da cui si entra nelle attività estive e di recupero: tre schede, '
             '"Recupero" (corsi di giugno e agosto), "Rientro dall\'estero" ed "Esami '
             'integrativi" (vedi le rispettive guide). Da qui trovi anche l\'elenco delle attività '
             'già registrate per il periodo corrente.'),
            ('Aggiungi una nuova attività differita',
             'Indica classe, docente, data e ora originaria e quella in cui viene effettivamente '
             'svolta.'),
        ],
        'faq': [],
        'attenzione': None,
    },
    {
        'slug': 'dipartimenti',
        'endpoint': 'attivita_ist.dipartimenti',
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
        'endpoint': 'piano_personale.lista',
        'titolo': 'Piano attività personale',
        'icona': '📋',
        'riassunto': 'I docenti a cattedra non completa (e gli IRC) scelgono i propri impegni collegiali dal Piano ufficiale.',
        'a_cosa_serve': (
            'Un docente con cattedra non completa in istituto (orario ridotto, o cattedra completata '
            'in un\'altra scuola) partecipa agli impegni collegiali (collegio, consigli di classe, '
            'dipartimenti...) solo in proporzione alle ore di contratto qui — non per intero come un '
            'docente a cattedra piena. Rientrano in questo modulo anche gli IRC, anche quando hanno '
            'cattedra piena (18 ore): essendo presenti in moltissime classi, seguire tutti gli '
            'impegni di ognuna supererebbe facilmente le 40 ore annue per bucket previste dal CCNL, '
            'quindi scelgono anche loro quali seguire. Questa pagina genera per ciascuno di questi '
            'docenti un link personale con cui sceglie, tra gli eventi già calendarizzati nel Piano '
            'delle Attività, quelli a cui parteciperà. Gli scrutini restano sempre obbligatori per '
            'tutti e non passano da qui.'
        ),
        'passi': [
            ('Apri "Attività → Piano attività personale"',
             'L\'elenco mostra solo i docenti coinvolti (cattedra non completa, o IRC) per l\'anno '
             'selezionato, con la percentuale di cattedra e le ore dovute per ciascuno dei due '
             'bucket CCNL.'),
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
        'endpoint': 'banca_ore.index',
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
        'endpoint': 'report.index',
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
             'Dal pulsante "Bozze email" in Report puoi generare, per ogni docente, una bozza di '
             'email con il proprio report in allegato — vedi la guida "Bozze email banca ore".'),
            ('Altri prospetti',
             'Oltre al report per docente trovi "Report per il dirigente" (con un selettore per '
             'consultare anche gli anni precedenti), "Pianifica permessi" (per ogni docente con '
             'saldo positivo, le date future in cui potrebbe chiedere un permesso orario sfruttando '
             'le ore libere già note; la data di fine lezioni si imposta nella pagina stessa), '
             '"Incarichi docenti" (in sola lettura, esportabile in PDF o Excel) e il '
             '"Prospetto supplenze" del giorno, stampabile.'),
        ],
        'faq': [],
        'attenzione': None,
    },
    {
        'slug': 'orario',
        'endpoint': 'sync.index',
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
            ('Alternativa IRC',
             'Nello stesso menu Orario c\'è anche "Alternativa IRC": la pianificazione dei gruppi '
             'per chi non segue religione. Ha una guida a parte ("Attività alternativa all\'IRC").'),
            ('Consulta "Orario globale"',
             'Se il tuo ruolo è abilitato, mostra la griglia completa di tutti i docenti — utile '
             'come riferimento, non modificabile da questa vista.'),
        ],
        'faq': [],
        'attenzione': None,
    },
    {
        'slug': 'recupero',
        'endpoint': 'recupero.index',
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
            ('Parti da "Attività → Attività differite → Recupero"',
             'La prima pagina elenca gli alunni con giudizio sospeso; da lì passi alla verifica '
             'della copertura e poi ai corsi di Giugno–luglio e di Agosto.'),
            ('Lavora su Giugno oppure su Agosto',
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
        'endpoint': 'rientro.index',
        'titolo': 'Rientro dall\'estero',
        'icona': '✈',
        'riassunto': 'Organizzazione dei colloqui di verifica per gli studenti di rientro da un periodo all\'estero.',
        'a_cosa_serve': (
            'Per organizzare i colloqui di verifica delle competenze per gli studenti che rientrano '
            'da un periodo di studio all\'estero: materie da verificare per classe, candidati, '
            'calendario dei colloqui con i docenti coinvolti.'
        ),
        'passi': [
            ('Apri "Rientro dall\'estero"',
             'Dal menu Attività → Attività differite, poi la scheda "Rientro dall\'estero".'),
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
        'endpoint': 'esami_integrativi.index',
        'titolo': 'Esami integrativi',
        'icona': '📝',
        'riassunto': 'Organizzazione degli esami integrativi/idoneità: candidati e calendario.',
        'a_cosa_serve': (
            'Per gestire i candidati agli esami integrativi (o di idoneità) e organizzare il '
            'relativo calendario con le commissioni coinvolte.'
        ),
        'passi': [
            ('Apri "Esami integrativi"',
             'Dal menu Attività → Attività differite, poi la scheda "Esami integrativi".'),
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
        'endpoint': 'docenti.lista',
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
             '(o in uscita) in un anno diverso da quello corrente. Ore settimanali, tipo di contratto '
             'e colloqui mostrati in tabella si riferiscono all\'anno selezionato, non sempre a quello '
             'corrente — un valore mostrato più chiaro/attenuato, con una nota al passaggio del mouse, '
             'segnala che è ereditato da un anno precedente e non impostato apposta per quello '
             'selezionato.'),
            ('Aggiungi un nuovo docente',
             'Indica almeno cognome, nome e tipo di contratto; puoi aggiungere subito anche la '
             'classe di concorso e le altre informazioni.'),
            ('Modifica un docente esistente',
             'Apri la sua scheda dall\'elenco — se un altro utente sta modificando la stessa scheda '
             'nello stesso momento, il sistema avvisa invece di sovrascrivere in silenzio. Il box '
             '"Materie insegnate" e quello dei colloqui hanno ciascuno un selettore anno: puoi '
             'consultare o correggere anche le materie/i colloqui di un anno diverso da quello '
             'corrente, non solo quello in corso (per gli altri anni le materie restano in sola '
             'lettura, i colloqui restano modificabili).'),
            ('Ore diverse tra un anno e l\'altro (es. cambio da cattedra spezzata a intera)',
             'Se un docente passa da un numero di ore a un altro da un certo anno in poi (es. entra in '
             'ruolo e prende una cattedra intera al posto di una spezzata su due scuole), il campo '
             '"Ore max (override)" con l\'anno di riferimento accanto permette di far vedere il valore '
             'giusto per l\'anno passato/in corso, aggiornando comunque il contratto base per gli anni '
             'successivi.'),
            ('Supplente temporaneo per pochi mesi',
             'Tra i tipi di contratto c\'è "Contratto Suppl. Breve" (sigla "Suppl. br."), per chi '
             'sostituisce un collega in malattia per 1, 2 o 3 mesi. Si imposta sia nella scheda '
             'del docente sia nel passo "Docenti per anno". Un supplente breve non risulta in '
             'servizio a luglio e agosto e non conta come docente a tempo indeterminato nei '
             'riepiloghi.'),
            ('Un docente con più di un incarico nello stesso anno (es. ITP + Sostegno)',
             'Sotto ai tre ruoli principali (Titolare/ITP/Sostegno) c\'è un checkbox "Ha ANCHE un '
             'incarico di sostegno" con le relative ore, per i casi in cui un docente svolge entrambi '
             'i ruoli nello stesso anno scolastico — il ruolo principale resta quello scelto sopra, '
             'l\'orario del sostegno si assegna comunque a parte dalla pagina "Orario sostegno".'),
        ],
        'faq': [
            ('Un docente che risulta trasferito o pensionato va eliminato?',
             'No, va segnato come "non in servizio" con il motivo (trasferimento/pensionamento/fine '
             'incarico) e l\'anno — resta nello storico ma non compare più tra i docenti attivi.'),
            ('Perché in tabella vedo un numero di ore o un giorno di colloqui diverso da quello che mi aspettavo?',
             'Controlla l\'anno scolastico selezionato in cima alla pagina: ore, contratto e colloqui '
             'possono legittimamente differire da un anno all\'altro (part-time, cambio cattedra, '
             'cambio giorno colloqui). Se il valore mostrato è più chiaro del solito, con una nota al '
             'passaggio del mouse, significa che nessuno ha impostato un valore apposta per quell\'anno '
             'e il sistema sta mostrando l\'ultimo valore noto.'),
        ],
        'attenzione': (
            'L\'eliminazione definitiva di un docente rimuove anche tutta la sua storia (assenze, '
            'supplenze, banca ore): da usare solo per anagrafiche inserite per errore, mai per un '
            'docente che ha davvero prestato servizio.'
        ),
    },
    {
        'slug': 'organico',
        'endpoint': 'impostazione_anno.index',
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
        'endpoint': 'cambio_anno.index',
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
        'endpoint': 'impostazioni.sospensioni',
        'titolo': 'Calendario scolastico',
        'icona': '📆',
        'riassunto': 'Sospensioni delle lezioni, festività, e i periodi usati da recupero/rientro/esami.',
        'a_cosa_serve': (
            'Per registrare le sospensioni didattiche (festività, ponti, chiusure) — durante quei '
            'giorni le assenze non generano supplenze in classe — e i periodi di riferimento '
            'usati da recupero estivo, rientro dall\'estero ed esami integrativi.'
        ),
        'passi': [
            ('Apri "Impostazioni → Istituto e calendario"',
             'Le voci sono "Sospensioni didattiche" e "Periodi (recupero, rientro…)".'),
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
        'endpoint': 'impostazioni.dati_istituto',
        'titolo': 'Istituto',
        'icona': '🏛',
        'riassunto': 'Dati anagrafici dell\'istituto, parametri economici, backup del database.',
        'a_cosa_serve': (
            'I dati anagrafici dell\'istituto (nome, indirizzo — usati in intestazioni di report e '
            'PDF), i parametri economici (es. costo orario di una supplenza) e lo scarico di una '
            'copia di backup del database.'
        ),
        'passi': [
            ('Apri "Impostazioni → Istituto → Dati istituto"',
             'Modifica nome, indirizzo e gli altri dati anagrafici.'),
            ('Imposta il costo ora supplenza',
             'Nella stessa pagina, sezione "Parametri economici" — usato nei report per stimare il '
             'costo delle supplenze a pagamento.'),
            ('Scarica un backup',
             'Da "Impostazioni → Sistema → Backup database" scarichi sul tuo computer una copia '
             'del database (file "caronteapp_backup_<data>.db"), da fare prima di un\'operazione '
             'delicata. Il file contiene tutti i dati personali: conservalo con la stessa cura '
             'del database.'),
        ],
        'faq': [],
        'attenzione': None,
    },
    {
        'slug': 'incarichi',
        'endpoint': 'incarichi.index',
        'titolo': 'Incarichi',
        'icona': '⭐',
        'riassunto': 'Assegnare incarichi ai docenti (funzioni strumentali, referenti...) e i loro tipi.',
        'a_cosa_serve': (
            'Per assegnare ai docenti incarichi interni (funzioni strumentali, referenti di '
            'progetto, coordinatori...) e — separatamente — per gestire l\'elenco dei tipi e delle '
            'categorie di incarico disponibili nella scuola.'
        ),
        'passi': [
            ('Apri "Impostazioni → Anno scolastico → Incarichi docenti"',
             'Assegna a un docente uno o più incarichi tra quelli disponibili.'),
            ('Gestisci i tipi di incarico',
             'Da "Impostazioni → Istituto e calendario → Tipi di incarico" puoi aggiungere nuovi tipi '
             'o categorie, prima di poterli assegnare ai docenti.'),
        ],
        'faq': [],
        'attenzione': None,
    },
    {
        'slug': 'assegnazioni',
        'endpoint': 'assegnazioni.index',
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
        'faq': [
            ('Cosa significano i badge "Cede a" e "Completa" su una cattedra?',
             'Compaiono quando la cattedra riguarda il completamento orario esterno (COE) con '
             'un\'altra scuola. "Cede a" indica che il docente è titolare altrove e questa scuola '
             'gli cede ore in eccesso per completargli la cattedra qui; "Completa" indica il caso '
             'opposto — il docente è titolare qui e la sua cattedra si completa con ore in '
             'un\'altra scuola. Passando sopra il badge compare la spiegazione estesa.'),
        ],
        'attenzione': None,
    },
    {
        'slug': 'sync',
        'endpoint': 'sync_conflitti.index',
        'titolo': 'Sincronizzazione tra postazioni',
        'icona': '🔄',
        'riassunto': 'Come si tengono allineati i dati quando si lavora da più computer.',
        'a_cosa_serve': (
            'Chi lavora da più postazioni (es. computer personale e computer di segreteria), con '
            '"database.db" condiviso via Google Drive, ha due meccanismi distinti che lavorano '
            'insieme: un allineamento automatico in background, silenzioso nella maggior parte dei '
            'casi, e — solo quando serve — una pagina per decidere a mano un vero conflitto.'
        ),
        'passi': [
            ('Allineamento automatico (non richiede nulla)',
             'Mentre l\'app è aperta, ogni 30 secondi un processo in background scarica il database '
             'pubblicato dall\'altra postazione e importa in automatico le righe nuove di Assenze, '
             'Supplenze, Indisponibilità e Sostituzioni scrutinio — solo aggiunte, non modifica mai '
             'righe già esistenti in locale. Se ci sono novità (qui o là), ripubblica da solo il '
             'database aggiornato, così l\'altra postazione le riceve al giro successivo.'),
            ('Un banner ti avvisa se serve il tuo intervento',
             'Se la STESSA modifica (stessa assenza, stessa supplenza...) risulta diversa sulle due '
             'postazioni — un vero conflitto — compare un banner giallo in cima a ogni pagina: '
             '"N modifiche fatte da un\'altra postazione devono essere confermate prima di essere '
             'unite ai dati".'),
            ('Risolvi il conflitto da "Rivedi ora"',
             'Il pulsante del banner porta a "/sync/conflitti", dove per ogni riga vedi affiancati i '
             'valori locali e quelli remoti, campo per campo, e scegli quale versione tenere: '
             '"Tieni la versione locale" oppure "Tieni la versione dall\'altra postazione".'),
        ],
        'faq': [
            ('Se elimino un\'assenza qui, sparisce anche dall\'altra postazione?',
             'Sì, al giro successivo: l\'eliminazione lascia una traccia interna ("lapide") che '
             'impedisce alla riga di ricomparire quando l\'altra postazione la scarica ancora '
             'presente sulla propria copia — senza, l\'eliminazione locale verrebbe silenziosamente '
             'annullata.'),
            ('Assegnazioni docenti/classi e Attività fuori aula si sincronizzano allo stesso modo?',
             'No, restano fuori da questo meccanismo automatico: sono strutture con dati collegati '
             'tra loro (cattedre, ore, classi) troppo delicate per un\'unione automatica. Per quelle '
             'un disallineamento tra postazioni va risolto a mano, confrontando le due copie.'),
            ('Se scelgo "Tieni la versione locale" su un conflitto, poi si ripresenta?',
             'No, la scelta viene ricordata: se la proposta remota resta la stessa, non ricompare. '
             'Ricompare come conflitto NUOVO solo se nel frattempo qualcuno modifica di nuovo quella '
             'stessa riga sull\'altra postazione.'),
        ],
        'attenzione': (
            'Questo meccanismo automatico è diverso dal check-out/check-in manuale di sync_db.py '
            '(lo script da riga di comando usato per scaricare/pubblicare l\'intero database prima '
            'e dopo una sessione di lavoro): quello serve a scaricare la versione più recente prima '
            'di iniziare a lavorare, questo qui è un allineamento continuo mentre l\'app è già aperta.'
        ),
    },
    {
        'slug': 'permessi',
        'endpoint': 'impostazioni.permessi',
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
             'Le sezioni sono oltre trenta, raggruppate per area (Assenze e supplenze, Attività, Banca '
             'ore e report, Orario, Recupero, Anno scolastico e organico, Docenti e incarichi, '
             'Istituto e calendario, Assegnazioni, Progetti FSE/FESR, Contrattazione '
             'integrativa). Di default la Contrattazione integrativa è visibile solo a '
             'segreteria e DSGA.'),
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
    {
        'slug': 'navigazione',
        'endpoint': 'impostazioni.index',
        'titolo': 'Come muoversi nell\'app',
        'icona': '🧭',
        'riassunto': 'Barra di navigazione, menu Impostazioni a gruppi, ricerca con Ctrl+K, percorso e scorciatoie.',
        'a_cosa_serve': (
            'L\'app ha molte funzioni, e non tutte stanno nella barra in alto. Questa guida spiega '
            'dove trovarle: la barra principale per quello che si usa ogni giorno, il menu '
            'Impostazioni a gruppi per tutto il resto, la casella Cerca (Ctrl+K) per arrivare '
            'a qualunque pagina scrivendone il nome. Vedi ogni voce solo se il tuo ruolo può '
            'aprirla: se una funzione non compare, di solito è per i permessi (vedi la guida '
            '"Permessi per ruolo").'
        ),
        'passi': [
            ('La barra in alto',
             'Dashboard, "Registra assenza", i menu Attività e Orario, Banca Ore, Report, Display, '
             'Impostazioni, Guida. La voce della sezione in cui ti trovi è evidenziata, e sopra il '
             'titolo di ogni pagina compare il percorso (es. "Contabilità e progetti › Progetti '
             'FSE/FESR") per capire dove sei.'),
            ('Il menu Impostazioni a gruppi',
             'Impostazioni si apre a tendina con i gruppi: Anno scolastico, Docenti, Contabilità e '
             'progetti, Istituto e calendario, Sistema. Dentro ci sono per esempio Assegnazioni, '
             'Incarichi, Anagrafica docenti, Contrattazione, Progetti FSE/FESR, Dati istituto, '
             'Permessi per ruolo. "Panoramica impostazioni" in cima porta alla pagina di prima, '
             'con i conteggi.'),
            ('Cerca una funzione con Ctrl+K',
             'Da qualunque pagina Ctrl+K (su Mac Cmd+K) porta il cursore nella casella Cerca. '
             'Scrivi una parola — es. "ricorrenti", "formazione", "scrutini", "lettere" — e il '
             'menu propone le pagine dell\'app che corrispondono; con le frecce e Invio ci vai. '
             'La stessa casella cerca anche docenti e altri dati (vedi la guida "Ricerca").'),
            ('Le scorciatoie per ruolo',
             'In cima alla Dashboard, la riga "Le tue sezioni" mostra le pagine che il tuo ruolo '
             'usa più spesso (per esempio il DS trova Report per il dirigente, Dashboard anno e '
             'Piano delle attività; la segreteria Banca ore, Report, Bozze email, Lettere di '
             'incarico).'),
            ('Usare l\'app da tastiera',
             'I menu a tendina si aprono anche con la tastiera (Invio o Spazio, poi le frecce) e '
             'c\'è il link "Vai al contenuto" per saltare la barra.'),
        ],
        'faq': [
            ('Non trovo una funzione nella barra: dove l\'hanno messa?',
             'Quasi sicuramente nel menu Impostazioni (per esempio Contrattazione e Progetti '
             'FSE/FESR sono nel gruppo "Contabilità e progetti") oppure è raggiungibile solo da '
             'un pulsante di un\'altra pagina (per esempio "Indisponibilità" e "Cambi" dalla '
             'Dashboard). Prova Ctrl+K e scrivi il nome.'),
            ('Perché un collega vede voci che io non vedo?',
             'Ogni ruolo vede solo ciò che il Dirigente ha abilitato nella pagina "Permessi per '
             'ruolo"; alcune voci (Importa orario, Conflitti di sincronizzazione, Permessi per '
             'ruolo) sono riservate a DS e DSGA.'),
        ],
        'attenzione': None,
    },
    {
        'slug': 'ricerca',
        'endpoint': 'ricerca.index',
        'titolo': 'Ricerca',
        'icona': '🔍',
        'riassunto': 'La casella Cerca in alto: pagine dell\'app e dati (docenti, supplenze, assenze...).',
        'a_cosa_serve': (
            'La casella "Cerca… (Ctrl+K)" in alto serve a due cose insieme: proporre le pagine '
            'dell\'app che corrispondono a quello che scrivi, e cercare nei dati — docenti, '
            'supplenze, assenze, movimenti di banca ore e sospensioni didattiche — senza dover '
            'sapere in quale sezione si trova un dato.'
        ),
        'passi': [
            ('Scrivi nella casella',
             'Mentre scrivi compaiono i suggerimenti: prima le funzioni ("Vai a…"), poi eventuali '
             'dati. Scegli con le frecce e Invio, oppure con il mouse.'),
            ('Premi Invio per tutti i risultati',
             'La pagina dei risultati ha una sezione "Funzioni" con le pagine dell\'app e le '
             'sezioni dei dati trovati (al massimo 25 per ciascuna).'),
        ],
        'faq': [
            ('Trova anche le parole con o senza accenti?',
             'Sì: "attività" e "attivita" si trovano a vicenda, e per le funzioni conta anche una '
             'serie di sinonimi (es. "scrutini", "religione", "malattia").'),
            ('Vedo nei risultati anche il motivo di un\'assenza?',
             'Solo se il tuo ruolo può vederlo: per gli altri è mascherato, come nel resto '
             'dell\'app.'),
        ],
        'attenzione': None,
    },
    {
        'slug': 'potenziamento',
        'endpoint': 'supplenze.nuovo_potenziamento',
        'titolo': 'Potenziamento e compresenza',
        'icona': '➕',
        'riassunto': 'Assegnare un docente libero o di potenziamento a una classe, su più ore insieme.',
        'a_cosa_serve': (
            'Per assegnare un docente di potenziamento — o semplicemente un docente libero in '
            'quell\'ora — a una classe per potenziamento o compresenza, su una o più ore dello '
            'stesso giorno con un solo invio. Non c\'è un docente assente da sostituire: è la '
            'differenza rispetto a una supplenza normale.'
        ),
        'passi': [
            ('Apri "Potenziamento/compresenza" dalla Dashboard',
             'Il pulsante è tra quelli in alto, e usa il giorno selezionato.'),
            ('Scegli classe, docente e ore',
             'Seleziona tutte le ore che servono: viene creata una voce per ciascuna.'),
            ('Conferma',
             'Le ore compaiono nella Dashboard del giorno come supplenze di tipo "potenziamento".'),
        ],
        'faq': [],
        'attenzione': None,
    },
    {
        'slug': 'sostituzioni-docenti',
        'endpoint': 'sostituzioni.index',
        'titolo': 'Sostituzione di un docente titolare',
        'icona': '🔁',
        'riassunto': 'Quando un docente esce (malattia lunga, trasferimento) e ne arriva un altro: un solo passaggio.',
        'a_cosa_serve': (
            'Per sostituire un docente titolare con un altro, temporaneamente (es. malattia lunga, '
            'con rientro previsto) oppure per il resto dell\'anno (es. trasferimento, cambio '
            'classe). In un solo passaggio vengono aggiornati orario, assenze/supplenze e cattedra. '
            'Non va confusa con le "sostituzioni" di una riunione o di uno scrutinio descritte in '
            'Attività istituzionali: lì si trova un sostituto per un singolo evento.'
        ),
        'passi': [
            ('Apri "Impostazioni → Docenti → Sostituzioni docenti"',
             'In cima scegli il docente titolare (chi esce) e premi "Continua"; sotto vedi le '
             'sostituzioni attive.'),
            ('Scegli il sostituto e il tipo',
             'Il sostituto deve già avere un\'anagrafica (se non ce l\'ha, creala prima: un link '
             'nella pagina la apre in una scheda nuova). "Temporanea" significa che il titolare '
             'tornerà (serve una data di fine); "Definitiva" vale per il resto dell\'anno.'),
            ('Cosa succede se è temporanea',
             'L\'orario del titolare passa al sostituto solo per quel periodo, viene registrata '
             'l\'assenza del titolare e le supplenze che ne derivano nascono già assegnate al '
             'sostituto; le riunioni future nel periodo vengono scambiate.'),
            ('Cosa succede se è definitiva',
             'L\'orario e l\'intera cattedra passano al sostituto per sempre, e il sostituto si '
             'iscrive alle riunioni future delle classi coinvolte. Non viene registrata nessuna '
             'assenza: è un cambio di incarico, non un\'assenza.'),
            ('Concludi una sostituzione temporanea',
             'Dall\'elenco delle sostituzioni attive il pulsante "Termina" rimette l\'orario e le '
             'riunioni esattamente come erano.'),
        ],
        'faq': [
            ('Se avevo già registrato l\'assenza del titolare, rischio di averla doppia?',
             'No: i giorni già coperti da un\'assenza non vengono duplicati, e le supplenze '
             'ancora scoperte di quei giorni vengono assegnate al sostituto indicato.'),
            ('Posso spezzare la cattedra fra titolare e sostituto?',
             'Non con la sostituzione definitiva, che sposta sempre l\'intera cattedra: se serve, '
             'si fa a mano dalla pagina Assegnazioni.'),
            ('Non so ancora quando rientra il titolare: che data metto?',
             'Una data di fine provvisoria: non esiste ancora l\'azione "estendi", quindi quando '
             'si sa di più si conclude e si riavvia la sostituzione.'),
        ],
        'attenzione': (
            'La sostituzione definitiva sposta tutta la cattedra e non si può annullare con un '
            'pulsante: controlla titolare e sostituto prima di confermare.'
        ),
    },
    {
        'slug': 'alternativa-irc',
        'endpoint': 'alternativa_irc.index',
        'titolo': 'Attività alternativa all\'IRC',
        'icona': '🎓',
        'riassunto': 'Gruppi e docenti per gli studenti che non seguono religione, secondo la nota MIM 11814/2026.',
        'a_cosa_serve': (
            'Per organizzare l\'attività alternativa all\'insegnamento della religione cattolica '
            '(nota MIM prot. 11814 del 06/05/2026, punto 3.7): le ore da coprire sono quelle di '
            'religione già presenti nell\'orario, e il docente di ogni gruppo è lo stesso per '
            'tutto l\'anno. La pagina iniziale riassume a che punto sei: studenti che chiedono un '
            'docente, gruppi, gruppi con docente assegnato, gruppi ancora da assegnare.'
        ),
        'passi': [
            ('1 · Adesioni per classe',
             'Per ogni classe inserisci quanti studenti chiedono un docente per l\'attività '
             'alternativa. Serve solo il numero: nessun nominativo.'),
            ('2 · Disponibilità dei docenti',
             'Registra chi ha dato la disponibilità volontaria: solo questi docenti vengono '
             'proposti in seconda priorità.'),
            ('3 · Gruppi e assegnazione docenti',
             '"Aggiorna gruppi dalle adesioni" crea un gruppo per ogni slot settimanale di '
             'religione in cui le classi hanno studenti da seguire. Per ogni gruppo scegli il '
             'docente: i candidati sono in ordine di priorità della circolare (1. a disposizione '
             'o a completamento d\'orario, 2. disponibilità volontaria, 3. nuovo contratto, con '
             '"supplente da nominare"). Chi insegna in una classe del gruppo, ha un impegno in '
             'quell\'ora, è presso un\'altra scuola o ha un\'indisponibilità fissa non compare.'),
            ('Dividi un gruppo numeroso',
             'Con almeno due classi, "Dividi in due gruppi" crea un secondo gruppo nello stesso '
             'giorno e ora, bilanciando per classi intere. Ogni parte (A, B…) ha il proprio '
             'docente; puoi spostare una classe da una parte all\'altra e "Riunisci" per tornare '
             'a un solo gruppo. Non c\'è un limite fisso al numero di gruppi o di studenti.'),
            ('4 · Orario settimanale',
             'La griglia settimanale dei gruppi, esportabile in Excel.'),
        ],
        'faq': [
            ('Cosa succede se il docente di un gruppo è assente?',
             'Registrando la sua assenza, viene creata automaticamente una supplenza per il '
             'gruppo (classe "ALT. IRC", con l\'elenco delle classi nelle note), come per qualunque '
             'altra ora.'),
            ('Cambiando le adesioni o l\'orario si perde il lavoro già fatto?',
             '"Aggiorna gruppi dalle adesioni" non disfa le divisioni già fatte: le classi tolte '
             'spariscono dalla parte in cui erano, quelle nuove vanno nella parte meno numerosa '
             'con un avviso. Un docente non più compatibile viene segnalato, non cancellato.'),
            ('Perché non vedo un docente tra i candidati?',
             'È escluso se insegna in una delle classi del gruppo, se ha già un impegno in quell\'ora '
             'o è già assegnato a un altro gruppo nello stesso slot.'),
        ],
        'attenzione': (
            'Il numero indicato come "gruppo numeroso" (oltre 20 studenti) è solo un segnale per '
            'far notare che forse conviene dividerlo, non un limite di legge.'
        ),
    },
    {
        'slug': 'formazione',
        'endpoint': 'formazione.lista',
        'titolo': 'Piano della formazione',
        'icona': '🎯',
        'riassunto': 'I corsi di formazione dell\'anno, obbligatori o volontari, con le iscrizioni dei docenti.',
        'a_cosa_serve': (
            'Per inserire i corsi di formazione dell\'anno scolastico e gestire chi vi partecipa. '
            'Ogni corso crea un evento nel Piano delle attività: le ore confluiscono da sole nel '
            'Riepilogo ore e nel Piano attività personale dei docenti, senza doverle inserire '
            'altrove.'
        ),
        'passi': [
            ('Apri "Piano della formazione"',
             'Dalla "Panoramica impostazioni" oppure con Ctrl+K cercando "formazione". In alto '
             'scegli l\'anno scolastico.'),
            ('Crea un corso',
             'Un corso "obbligatorio per tutti" iscrive in automatico tutti i docenti in servizio; '
             'un corso "volontario" parte senza iscritti. Puoi indicare date, anche su più '
             'giorni, e la modalità.'),
            ('Gestisci le iscrizioni',
             'Per i corsi volontari iscrivi o disiscrivi i docenti dalla scheda del corso.'),
        ],
        'faq': [
            ('Chi non è in servizio nelle date del corso viene iscritto lo stesso?',
             'No: vengono esclusi i docenti non in servizio a quella data (arrivati dopo, usciti '
             'prima, in aspettativa).'),
        ],
        'attenzione': None,
    },
    {
        'slug': 'generatore-cdc',
        'endpoint': 'generatore_cdc.index',
        'titolo': 'Generatore del piano delle attività',
        'icona': '⚙️',
        'riassunto': 'Una bozza modificabile di Consigli di classe, scrutini, GLO e riunioni di dipartimento.',
        'a_cosa_serve': (
            'Per non costruire da zero il calendario delle riunioni: il generatore propone una '
            'bozza di Consigli di classe, scrutini e GLO che raggruppa più classi compatibili nello '
            'stesso slot (nessun docente in comune, DS non doppiamente impegnato). La bozza è '
            'sempre modificabile a mano e crea eventi veri solo quando la confermi. Le classi e i '
            'loro docenti sono presi dalle Assegnazioni dell\'anno, non dall\'orario delle lezioni.'
        ),
        'passi': [
            ('Apri "Genera piano delle attività"',
             'Dalla "Panoramica impostazioni" oppure con Ctrl+K cercando "generatore".'),
            ('Imposta i vincoli',
             'Due pagine dedicate: i vincoli di orario fisso per classe (es. rientro pomeridiano '
             'di certi indirizzi) e i vincoli manuali, cioè slot e scadenze fissati a mano prima '
             'di generare.'),
            ('Genera e correggi la bozza',
             'Scegli tipo di riunione (consiglio di classe, scrutinio, GLO), classi, periodo e '
             'fascia oraria. Le classi che non trovano slot restano "in conflitto" e vanno '
             'piazzate a mano nella bozza.'),
            ('Riunioni di dipartimento ed eventi unici',
             'Le riunioni di dipartimento/materia si piazzano in data senza motore di scheduling '
             '(dipartimenti diversi non condividono docenti). "Eventi unici" serve per le '
             'riunioni uniche per tutti, come il Collegio docenti e l\'incontro scuola-famiglia.'),
            ('Verifica l\'orario',
             'La pagina "Verifica orario" segnala le riunioni che si sovrappongono a lezioni '
             'quando l\'orario è stato caricato.'),
        ],
        'faq': [
            ('Il generatore scrive subito gli eventi?',
             'No, solo alla conferma della bozza; i partecipanti vengono precompilati dalle '
             'Assegnazioni.'),
        ],
        'attenzione': (
            'Il generatore dei Consigli di classe non guarda l\'orario delle lezioni: controlla '
            'a mano gli slot proposti quando l\'orario è definitivo (la pagina "Verifica orario" '
            'aiuta).'
        ),
    },
    {
        'slug': 'contrattazione',
        'endpoint': 'contrattazione.index',
        'titolo': 'Contrattazione integrativa',
        'icona': '💶',
        'riassunto': 'Fondi, capitoli di spesa, assegnazioni ai docenti, lettere di incarico, personale ATA.',
        'a_cosa_serve': (
            'L\'area per la segreteria e l\'ufficio contabilità: si inseriscono i fondi (FIS, FMOF, '
            'altri), da cui si sottrae l\'eventuale quota del DSGA; l\'importo contrattabile si '
            'divide in capitoli di spesa; dentro ogni capitolo si assegna un importo a ciascun '
            'docente. Gli importi si inseriscono a mano, perché possono cambiare fino alla chiusura '
            'della contrattazione. Di default la vede solo la segreteria (e il DSGA).'
        ),
        'passi': [
            ('Apri "Impostazioni → Contabilità e progetti → Fondi e capitoli"',
             'Con "Nuovo fondo" inserisci un fondo dell\'anno; poi i capitoli di spesa (es. '
             'Valorizzazione, PCTO, Supporto organizzativo).'),
            ('Assegna gli importi ai docenti',
             'In ogni capitolo aggiungi le assegnazioni: ognuna passa da "Previsto" a "Comunicato '
             '(lettera inviata)" a "Liquidato". Puoi spostare un\'assegnazione da un capitolo '
             'all\'altro anche dopo la lettera: lo storico degli spostamenti resta sempre '
             'visibile e i saldi restano coerenti. Con "importa incarichi" porti in un '
             'capitolo le nomine già fatte nel Piano attività per i tipi di incarico collegati '
             'al catalogo, invece di ridigitarle.'),
            ('Cura il catalogo incarichi',
             'Il "Catalogo incarichi" raccoglie, per ogni tipo di incarico, il numero di '
             'riferimento e il testo descrittivo che finisce nelle lettere. Il testo lo compila e '
             'aggiorna la segreteria (anche con l\'importazione di massa); non è generato '
             'dall\'app.'),
            ('Produci le lettere di incarico',
             '"Lettere di incarico" mostra una riga per destinatario, con numero di incarichi, '
             'totale, liquidati e protocollo della lettera. La lettera è una per destinatario ed '
             'è cumulativa di tutti gli incarichi dell\'anno (tabella riassuntiva più testo '
             'esteso dei soli incarichi assegnati), in PDF o Word. Le "Impostazioni lettera" '
             'contengono i riferimenti che cambiano ogni anno (visti, delibere).'),
            ('Personale ATA e retribuzione fondi MOF',
             '"Personale ATA" è un\'anagrafica minima del personale ATA, assegnabile agli '
             'incarichi come i docenti. Per ogni persona c\'è anche il documento "Retribuzione '
             'fondi MOF".'),
        ],
        'faq': [
            ('Se sposto un\'assegnazione tra capitoli devo rifare la lettera?',
             'No: non serve una lettera di rettifica, ma lo spostamento resta tracciato.'),
        ],
        'attenzione': (
            'Per i PDF serve WeasyPrint; dove non è disponibile l\'app lo segnala invece di '
            'mostrare in silenzio una versione HTML.'
        ),
    },
    {
        'slug': 'progetti-fse',
        'endpoint': 'progetti_fse.index',
        'titolo': 'Progetti FSE/FESR',
        'icona': '🇪🇺',
        'riassunto': 'Progetti finanziati da fondi europei: moduli, incarichi, calendario, presenze, documenti.',
        'a_cosa_serve': (
            'Un\'area amministrativa separata dal Piano delle attività didattico, per i progetti '
            'finanziati da fondi strutturali europei (FSE+/FESR, PN "Scuola e competenze" '
            '2021-2027, per esempio il Piano Estate). Ogni progetto ha moduli, ogni modulo ha '
            'incarichi (esperto, tutor, figura aggiuntiva, project manager), sessioni di '
            'calendario e presenze dei partecipanti. Le sole date dei moduli compaiono in sola '
            'lettura nell\'Agenda, per controllare che non si sovrappongano agli impegni '
            'didattici dei docenti incaricati.'
        ),
        'passi': [
            ('Apri "Impostazioni → Contabilità e progetti → Progetti FSE/FESR"',
             'L\'elenco mostra i progetti (bozza, autorizzato, in corso, chiuso); c\'è anche un '
             'cruscotto d\'insieme.'),
            ('Crea progetto e moduli',
             'Per ogni progetto indichi il tipo di costo: costi standard (UCS, con tariffa '
             'oraria per esperto e tutor e costo di gestione per ora di presenza di ogni '
             'partecipante) oppure costi reali. L\'app calcola i costi, non vanno ricalcolati a '
             'mano.'),
            ('Incarichi, calendario e presenze',
             'In ogni modulo aggiungi gli incarichi (anche in stato "Candidato", per la raccolta '
             'delle candidature), il calendario delle sessioni e le presenze: servono per stimare '
             'il rimborso.'),
            ('Segui la procedura e genera i documenti',
             'Nella pagina Documenti del progetto trovi i passi dell\'iter in ordine: '
             'disseminazione, decreto di assunzione al bilancio, decreto di avvio selezione e '
             'avviso, raccolta candidature, nomina commissione, dichiarazioni dei commissari, '
             'verbale, graduatorie provvisoria e definitiva, decreto di conferimento incarichi, '
             'lettere di incarico o contratti. Per molti passi l\'app genera il documento.'),
        ],
        'faq': [
            ('Dove la trovo ora nel menu?',
             'Non è più nella barra: sta nel gruppo "Contabilità e progetti" del menu '
             'Impostazioni, accanto alla Contrattazione, e si trova anche con Ctrl+K.'),
            ('Chi la vede?',
             'Di default DS, collaboratore e segreteria in modifica: si cambia da "Permessi per '
             'ruolo".'),
        ],
        'attenzione': None,
    },
    {
        'slug': 'display',
        'endpoint': 'display.display',
        'titolo': 'Display',
        'icona': '🖥',
        'riassunto': 'La pagina da mostrare su un monitor a scuola: supplenze del giorno, sempre aggiornate.',
        'a_cosa_serve': (
            'Il Display mostra le supplenze di un giorno in un formato adatto a un monitor in '
            'sala docenti o all\'ingresso: classe, aula, docente che sostituisce. Si aggiorna '
            'da solo ogni 30 secondi e, se i dati non entrano nello schermo, scorre su e giù. '
            'Si apre in una scheda a parte.'
        ),
        'passi': [
            ('Apri "Display" dalla barra',
             'Mostra le supplenze di oggi.'),
            ('Scegli un altro giorno dalla Dashboard',
             'Nella Dashboard i pulsanti "Mostra nel display" (Oggi, Domani, Dopodomani) aprono '
             'il Display su quella data; anche i pulsanti "Display" in alto fanno lo stesso per '
             'il giorno selezionato.'),
            ('Usa un utente "Display" per il monitor',
             'Per un monitor fisso si crea un utente con ruolo "Display (sola lettura)": vede solo '
             'questa pagina, qualunque indirizzo apra. Vedi la guida "Utenti e PIN".'),
        ],
        'faq': [
            ('Cosa compare nelle note sul Display?',
             'Il campo "Note display" della supplenza (vedi la guida "Supplenze"): tienile '
             'brevi, chi le legge non ha altro contesto.'),
            ('Mostra anche l\'aula della classe?',
             'Sì, l\'aula assegnata alla classe (o l\'eventuale aula impostata solo per quella '
             'supplenza).'),
        ],
        'attenzione': None,
    },
    {
        'slug': 'dashboard-anno',
        'endpoint': 'dashboard_anno.index',
        'titolo': 'Dashboard anno',
        'icona': '📈',
        'riassunto': 'Il riepilogo di un anno scolastico: classi, docenti, organico, assegnazioni, incarichi.',
        'a_cosa_serve': (
            'Un riepilogo trasversale, per l\'anno scolastico scelto in alto: classi attive e '
            'indirizzi, docenti in organico (a tempo indeterminato e determinato), movimenti '
            '(entranti, uscenti, aspettative) e lo stato di avanzamento di organico e '
            'assegnazioni. Utile per capire cosa manca prima di attivare l\'anno nuovo. Ogni '
            'scheda porta alla pagina di dettaglio, e da qui si apre anche la scheda di ogni '
            'classe.'
        ),
        'passi': [
            ('Apri "Impostazioni → Anno scolastico → Dashboard anno"',
             'Scegli l\'anno con i pulsanti in alto: puoi guardare sia l\'anno in corso sia '
             'quello in preparazione.'),
            ('Segui le schede',
             'Cliccando una scheda (Classi attive, Docenti in organico…) vai alla pagina del '
             'passo corrispondente di "Impostazione anno".'),
            ('Apri la scheda di una classe',
             'Dalla dashboard si arriva alla scheda di dettaglio di ogni classe.'),
        ],
        'faq': [],
        'attenzione': None,
    },
    {
        'slug': 'mappa-aule',
        'endpoint': 'aule.mappa',
        'titolo': 'Mappa aule',
        'icona': '🗺',
        'riassunto': 'La piantina interattiva delle aule, con le classi assegnate.',
        'a_cosa_serve': (
            'Una piantina interattiva, divisa in sezioni (una per piano o edificio): le zone '
            'cliccabili mostrano le classi assegnate a ogni aula. Ha due modalità: "visualizza", '
            'in sola lettura, e "assegna", che permette di scegliere la classe di un\'aula '
            'direttamente dalla mappa (o liberarla).'
        ),
        'passi': [
            ('Apri "Mappa aule"',
             'Dal pulsante "Piantina interattiva" nella pagina "Aule per classe" (vedi la guida '
             '"Assegnazioni e aule") oppure con Ctrl+K. '
             'L\'aula di una classe vale per un anno scolastico: scegli l\'anno prima di assegnare.'),
            ('Assegna o libera un\'aula',
             'In modalità "assegna" clicca l\'aula, scegli la classe e conferma; per liberarla '
             'usa il comando apposito. Le assegnazioni di altri anni non cambiano.'),
        ],
        'faq': [],
        'attenzione': None,
    },
    {
        'slug': 'bozze-email',
        'endpoint': 'mail_bozze.index',
        'titolo': 'Bozze email banca ore',
        'icona': '✉️',
        'riassunto': 'Preparare per ogni docente la mail con il proprio report della banca ore in allegato.',
        'a_cosa_serve': (
            'Per inviare a molti docenti, in un colpo solo, la comunicazione sul proprio saldo di '
            'banca ore con il report PDF allegato. Scegli i docenti (chi non ha un indirizzo '
            'email non è selezionabile), scrivi oggetto e testo e l\'app prepara le bozze: non invia nulla '
            'da sola.'
        ),
        'passi': [
            ('Apri "Bozze email"',
             'Dal pulsante in Report, o con Ctrl+K cercando "mail".'),
            ('Seleziona i docenti',
             '"Seleziona tutti", "Deseleziona tutti" e "Solo con email" aiutano; un contatore '
             'mostra quanti ne hai scelti.'),
            ('Scrivi oggetto e testo',
             'Nel testo puoi usare i segnaposto {COGNOME}, {NOME} ed {EMAIL}, sostituiti per '
             'ogni docente. Il testo proposto è modificabile.'),
            ('Crea le bozze',
             'Su Mac compare "Apri bozze in Mail.app", su Windows "Script Outlook (.ps1)"; su tutti '
             '"Scarica .eml + PDF (ZIP)" da aprire con il proprio programma di posta. Le '
             'bozze vanno controllate e inviate da te.'),
        ],
        'faq': [],
        'attenzione': (
            'I pulsanti disponibili dipendono dal computer: l\'apertura diretta in Mail.app '
            'funziona solo su Mac.'
        ),
    },
    {
        'slug': 'utenti',
        'endpoint': 'auth.lista_utenti',
        'titolo': 'Utenti e PIN',
        'icona': '👥',
        'riassunto': 'Chi può accedere all\'app, con quale ruolo e PIN; cronologia degli accessi.',
        'a_cosa_serve': (
            'Ogni persona accede con username e PIN. DS e DSGA creano gli utenti, scelgono il ruolo '
            '(Dirigente Scolastico, DSGA, Collaboratore DS, Segreteria Personale, Display), '
            'cambiano un PIN o disattivano un account. Ogni utente può cambiare da sé il proprio '
            'PIN dal menu in alto a destra. La cronologia attività mostra accessi e modifiche '
            'ai dati.'
        ),
        'passi': [
            ('Apri "Impostazioni → Sistema → Gestione utenti e PIN"',
             'Elenco degli utenti con ruolo e stato.'),
            ('Crea o modifica un utente',
             'Username (non modificabile dopo la creazione), cognome, nome, ruolo e PIN. Per '
             'cambiare il PIN a qualcuno basta scriverne uno nuovo nella sua scheda; per '
             'disattivare un account togli la spunta "attivo". Non puoi eliminare il tuo stesso '
             'account.'),
            ('Cambia il tuo PIN',
             'Dal menu utente in alto a destra, "Cambia PIN": serve il PIN attuale e il nuovo '
             'deve avere almeno 4 cifre.'),
            ('Consulta la cronologia',
             'Da "Log accessi": accessi e modifiche (docenti, supplenze, assenze, sospensioni, '
             'dati istituto, utenti), filtrabili per testo, azione, utente e date; vengono '
             'mostrati gli ultimi 300 risultati. I log più vecchi vengono cancellati '
             'automaticamente (conservazione limitata, per la privacy).'),
        ],
        'faq': [
            ('Dopo vari PIN sbagliati non riesco più ad entrare.',
             'Dopo 5 tentativi falliti con lo stesso utente dallo stesso computer l\'accesso è '
             'bloccato per 15 minuti.'),
            ('Cosa può fare un utente "Display"?',
             'Vede solo la pagina Display, sempre; non può aprire altro. È pensato per un monitor '
             'in sala docenti.'),
        ],
        'attenzione': (
            'Gli utenti si gestiscono da DS e DSGA. I PIN non vengono mostrati: se qualcuno lo '
            'dimentica se ne imposta uno nuovo.'
        ),
    },
]


def get_sezione(slug):
    """Ritorna la sezione con lo slug indicato, o None se non esiste."""
    for s in SEZIONI:
        if s['slug'] == slug:
            return s
    return None


def _campi_pesati(sez):
    """Tutti i campi testuali di una sezione, ciascuno col peso da dare
    a un suo eventuale match nella ricerca — un titolo o una domanda
    FAQ che contiene la parola cercata è un indizio molto più forte di
    una frase persa nel corpo di un passo, quindi pesa di più."""
    campi = [
        (sez['titolo'], 10),
        (sez['riassunto'], 5),
        (sez['a_cosa_serve'], 3),
    ]
    for titolo_passo, testo_passo in sez.get('passi', []):
        campi.append((titolo_passo, 4))
        campi.append((testo_passo, 2))
    for domanda, risposta in sez.get('faq', []):
        campi.append((domanda, 6))
        campi.append((risposta, 2))
    if sez.get('attenzione'):
        campi.append((sez['attenzione'], 2))
    return campi


def _estrai_snippet(testo, parola, larghezza=110):
    """Un frammento di `testo` centrato sulla prima occorrenza di
    `parola` (case-insensitive), con puntini di sospensione se tagliato."""
    testo_lower = testo.lower()
    i = testo_lower.find(parola)
    if i == -1:
        return testo[:larghezza] + ('…' if len(testo) > larghezza else '')
    inizio = max(0, i - larghezza // 2)
    fine = min(len(testo), i + len(parola) + larghezza // 2)
    frammento = testo[inizio:fine]
    if inizio > 0:
        frammento = '…' + frammento
    if fine < len(testo):
        frammento = frammento + '…'
    return frammento


def cerca(query):
    """
    Ricerca per parole chiave nel contenuto della guida (tutte le
    sezioni, tutti i campi — non solo titolo/riassunto), con un
    punteggio di rilevanza per ordinare i risultati: più parole
    trovate, e in campi più "importanti" (titolo/FAQ prima del corpo
    di un passo), più il risultato sale in classifica.

    Ritorna una lista di dict {'sezione', 'punteggio', 'snippet'},
    ordinata dal più rilevante, oppure lista vuota se la query è vuota
    o non trova nulla.
    """
    parole = [p.strip().lower() for p in (query or '').split() if p.strip()]
    if not parole:
        return []

    risultati = []
    for sez in SEZIONI:
        punteggio = 0
        snippet = None
        migliore_peso_snippet = -1
        for testo, peso in _campi_pesati(sez):
            testo_lower = testo.lower()
            for parola in parole:
                occorrenze = testo_lower.count(parola)
                if not occorrenze:
                    continue
                punteggio += occorrenze * peso
                if peso > migliore_peso_snippet:
                    migliore_peso_snippet = peso
                    snippet = _estrai_snippet(testo, parola)
        if punteggio > 0:
            risultati.append({'sezione': sez, 'punteggio': punteggio, 'snippet': snippet})

    risultati.sort(key=lambda r: -r['punteggio'])
    return risultati
