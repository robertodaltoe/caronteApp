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
            ('Indica il motivo',
             'Malattia, permesso personale, legge 104, permesso orario, ecc. — scegli quello più '
             'preciso possibile: aiuta chi consulta lo storico più avanti.'),
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
             'Solo collaboratore e DSGA — la segreteria non ha accesso a questa sezione, a differenza '
             'di assenze e supplenze.'),
        ],
        'attenzione': None,
    },
]


def get_sezione(slug):
    """Ritorna la sezione con lo slug indicato, o None se non esiste."""
    for s in SEZIONI:
        if s['slug'] == slug:
            return s
    return None
