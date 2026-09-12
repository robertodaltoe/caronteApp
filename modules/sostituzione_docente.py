"""
Sostituzione di un docente titolare con un altro (temporanea o
definitiva) — Sessione 69 addendum 2, richiesta di Roberto: quando un
docente esce a metà anno (malattia lunga, trasferimento, cambio classe)
e al suo posto arriva un altro docente mai stato in anagrafica, serve
un'unica azione che sposti l'orario, generi/assegni le supplenze e
(per il caso definitivo) aggiorni la cattedra -- invece di intrecciare
a mano 4-5 pagine diverse.

Le due modalita':

- 'temporanea': il titolare (X) torna prima o poi. Il suo orario viene
  SPOSTATO (mai copiato -- modules/compresenze.py cerca chi ha una riga
  di OrarioDocente per un dato giorno/ora/classe, una copia farebbe
  vedere una compresenza fantasma) al sostituto (Y) solo per la durata
  della sostituzione, tracciato riga per riga in SostituzioneOrarioSlot
  cosi' "termina_sostituzione" puo' rimetterlo esattamente a posto.
  Viene registrata l'assenza di X per il periodo e le supplenze
  scoperte che ne derivano nascono gia' assegnate a Y (vedi
  modules/assenze_registrazione.py::_genera_supplenze,
  id_sostituto_preset). Le riunioni istituzionali future nella finestra
  vengono scambiate (X fuori, Y dentro) e riportate a posto al rientro.

- 'definitiva': X non torna su quel posto. L'orario viene spostato per
  sempre (nessun tracciamento di ripristino), la cattedra
  (AssegnazioneDocente) passa a Y con le stesse regole gia' usate per
  nominare un placeholder (routes/assegnazioni.py::nomina), e Y si
  iscrive a tutti gli eventi istituzionali futuri delle classi
  coinvolte. Non viene registrata nessuna assenza: non e' un'assenza,
  e' un cambio di incarico.

Nota tecnica importante: in questo database "classe" ha DUE formati
distinti e indipendenti, che NON vanno mai confusi o confrontati come
stringhe -- OrarioDocente.classe/Supplenza.classe/Assenza (dal file
orario importato, es. '5ARIM', senza spazio) e AssegnazioneClasse.
label_classe/AttivitaIst.classe per i CdC (costruito in app, es.
'5A RIM', con spazio). Per questo lo spostamento dell'orario (che usa
il primo formato, scelto da chi avvia la sostituzione) e il
trasferimento di cattedra + la sostituzione nei Consigli di classe/
scrutini (che usano il secondo, letto direttamente dalle Assegnazioni
del titolare) sono due passaggi separati, ciascuno nel proprio formato
-- MAI un tentativo di convertire l'uno nell'altro per confrontarli.

Limiti noti (scelta deliberata, non svista):
- 'definitiva' sposta SEMPRE l'intera cattedra (tutte le righe
  AssegnazioneDocente del titolare per l'anno corrente): non supporta
  lo spacchettamento di una cattedra fra titolare e sostituto (se
  serve, va fatto a mano dopo, dalla pagina Assegnazioni).
- 'temporanea' richiede una data_fine: per un'assenza a data di
  rientro ancora ignota, usare comunque una data_fine provvisoria e
  poi concludere/riavviare quando si sa di piu' (non c'e' ancora
  un'azione "estendi").
- Se per il titolare esistono gia' delle supplenze 'scoperta' generate
  in precedenza per le stesse date/ore (es. l'assenza era gia' stata
  registrata a mano prima di sapere chi sarebbe stato il sostituto),
  _genera_supplenze() le trova gia' presenti e le salta (e' pensata per
  essere idempotente) -- NON le riassegna al sostituto. In quel caso
  vanno assegnate a mano da Supplenze, come sempre; avviare una
  sostituzione PRIMA di registrare l'assenza evita il problema.
"""
from datetime import date as _date, datetime as _datetime_mod, timedelta

from models import db
from models.docente import Docente
from models.orario_docente import OrarioDocente
from models.assenza import Assenza, cat_genera_supplenza, cat_assegnabile
from modules.assenze_registrazione import _genera_supplenze, is_sospensione, GIORNI_SETTIMANA


def _datetime_now():
    return _datetime_mod.utcnow()


class SostituzioneDocenteErrore(Exception):
    """Errore di validazione applicativa (non un bug) -- il chiamante
    (route) lo mostra come messaggio flash, non come pagina di errore."""
    pass


def _giorni_periodo(data_inizio, data_fine):
    giorni = []
    cur = data_inizio
    while cur <= data_fine:
        if cur.weekday() < 6:  # esclude la domenica, come registra_assenze_form
            giorni.append(cur)
        cur += timedelta(days=1)
    return giorni


def avvia_sostituzione(id_titolare, id_sostituto, tipo, data_inizio,
                        data_fine=None, classi=None, motivo='malattia',
                        note=None, creato_da=None):
    """
    Avvia una sostituzione. classi=None -> tutte le classi in cui il
    titolare ha attualmente orario. Ritorna il record SostituzioneDocente
    creato; solleva SostituzioneDocenteErrore su input non valido.
    """
    from models.sostituzione_docente import (
        SostituzioneDocente, SostituzioneOrarioSlot, SostituzioneEventoSwap,
    )

    if tipo not in ('temporanea', 'definitiva'):
        raise SostituzioneDocenteErrore(f"Tipo non valido: {tipo!r}.")
    if id_titolare == id_sostituto:
        raise SostituzioneDocenteErrore('Titolare e sostituto non possono coincidere.')
    titolare  = Docente.query.get(id_titolare)
    sostituto = Docente.query.get(id_sostituto)
    if not titolare or not sostituto:
        raise SostituzioneDocenteErrore('Docente titolare o sostituto non trovato.')
    if tipo == 'temporanea' and not data_fine:
        raise SostituzioneDocenteErrore(
            "Una sostituzione temporanea richiede una data di fine "
            "(anche provvisoria, se il rientro non è ancora certo)."
        )

    q_orario = OrarioDocente.query.filter_by(id_docente=id_titolare)
    if classi:
        q_orario = q_orario.filter(OrarioDocente.classe.in_(classi))
    slots = q_orario.all()
    if not slots:
        raise SostituzioneDocenteErrore(
            f'{titolare.cognome} non ha ore di orario da spostare '
            f'{"per le classi indicate" if classi else ""}.'.strip()
        )

    sost = SostituzioneDocente(
        id_titolare=id_titolare, id_sostituto=id_sostituto, tipo=tipo,
        data_inizio=data_inizio, data_fine=data_fine,
        stato='attiva', note=note, creato_da=creato_da,
    )
    db.session.add(sost)
    db.session.flush()

    n_assenze = 0
    n_supplenze = 0
    if tipo == 'temporanea':
        # Genera assenza + supplenze PRIMA di spostare l'orario: la
        # generazione legge OrarioDocente del titolare, che a questo
        # punto deve avere ancora le sue righe.
        for giorno in _giorni_periodo(data_inizio, data_fine):
            if is_sospensione(giorno):
                continue
            db.session.add(Assenza(
                id_docente=id_titolare, data=giorno, ora_inizio=1, ora_fine=9,
                motivo=motivo, note_interne=note or '', creato_da=creato_da,
            ))
            n_assenze += 1
            if cat_genera_supplenza(motivo):
                n_supplenze += _genera_supplenze(
                    id_titolare, giorno, 1, 9, cat_assegnabile(motivo), '',
                    id_sostituto_preset=id_sostituto,
                )

    # Sposta l'orario (mai copiato -- vedi docstring del modulo).
    for slot in slots:
        db.session.add(SostituzioneOrarioSlot(
            id_sostituzione=sost.id, id_orario_docente=slot.id,
            giorno=slot.giorno, ora=slot.ora, classe=slot.classe,
        ))
        slot.id_docente = id_sostituto
    from modules.compresenze import invalida_cache
    invalida_cache()

    # Riunioni istituzionali (CdC/scrutini): scambia i partecipanti sulle
    # classi della cattedra UFFICIALE del titolare (AssegnazioneClasse,
    # formato "5A RIM") -- MAI sulle classi dell'orario appena spostato
    # (formato diverso, "5ARIM", vedi nota tecnica nella docstring del
    # modulo): sono le stesse classi che, per il caso definitivo,
    # riceveranno anche il trasferimento di cattedra qui sotto.
    classi_cattedra = _classi_cattedra_titolare(id_titolare)
    n_eventi = _scambia_partecipanti_eventi(
        sost, classi_cattedra,
        data_da=data_inizio,
        data_a=data_fine if tipo == 'temporanea' else None,
    )

    n_cattedre = 0
    if tipo == 'definitiva':
        n_cattedre = _trasferisci_cattedra(id_titolare, id_sostituto)

    db.session.commit()
    return {
        'sostituzione': sost,
        'n_slot_orario': len(slots),
        'n_assenze': n_assenze,
        'n_supplenze': n_supplenze,
        'n_eventi_ist': n_eventi,
        'n_cattedre_trasferite': n_cattedre,
    }


def _classi_cattedra_titolare(id_titolare):
    """Le classi (formato AssegnazioneClasse.label_classe, es. '5A RIM')
    dell'anno corrente in cui il titolare ha una cattedra -- usata per
    sapere quali Consigli di classe/scrutini lo riguardano, indipendente
    da quali classi/ore di orario sono state scelte per la sostituzione.
    """
    from models.assegnazione import AssegnazioneDocente
    anno = _anno_scol_corrente()
    classi = set()
    for asgn in AssegnazioneDocente.query.filter_by(
            anno_scol=anno, id_docente=id_titolare).all():
        classi |= {c.label_classe for c in asgn.classi}
    return classi


def _scambia_partecipanti_eventi(sost, classi_coinvolte, data_da, data_a):
    """Toglie il titolare e aggiunge il sostituto come partecipante
    negli eventi istituzionali (AttivitaIst) futuri sulle classi
    coinvolte, nella finestra indicata (data_a=None = senza limite,
    caso definitivo). Traccia ogni scambio in SostituzioneEventoSwap
    per poterlo invertire a fine sostituzione temporanea.

    Riguarda SOLO Consigli di classe/scrutini (AttivitaIst.classe e'
    valorizzato solo li'): le riunioni di dipartimento/per materia sono
    legate a id_dipartimento, non a una classe, e per il caso
    'definitiva' vengono gia' coperte indirettamente da
    _trasferisci_cattedra -> _sync_docente_materie, che iscrive il
    sostituto ai dipartimenti delle materie appena assegnate (stesso
    meccanismo gia' usato per un placeholder appena nominato). Il
    titolare NON viene tolto dai dipartimenti automaticamente in nessun
    caso: potrebbe insegnare la stessa materia anche altrove."""
    from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
    from models.sostituzione_docente import SostituzioneEventoSwap

    if not classi_coinvolte:
        return 0

    oggi = _date.today()
    q = AttivitaIst.query.filter(
        AttivitaIst.data >= max(data_da, oggi),
        AttivitaIst.classe.in_(classi_coinvolte),
    )
    if data_a:
        q = q.filter(AttivitaIst.data <= data_a)

    n = 0
    for ev in q.all():
        aveva_titolare = AttivitaIstPartecipante.query.filter_by(
            id_attivita=ev.id, id_docente=sost.id_titolare).first()
        if aveva_titolare:
            db.session.delete(aveva_titolare)
        gia_presente = AttivitaIstPartecipante.query.filter_by(
            id_attivita=ev.id, id_docente=sost.id_sostituto).first()
        if not gia_presente:
            db.session.add(AttivitaIstPartecipante(
                id_attivita=ev.id, id_docente=sost.id_sostituto, preset=True))
        db.session.add(SostituzioneEventoSwap(
            id_sostituzione=sost.id, id_attivita=ev.id,
            titolare_era_presente=bool(aveva_titolare),
        ))
        n += 1
    return n


def _trasferisci_cattedra(id_titolare, id_sostituto):
    """Sposta a Y TUTTE le cattedre (AssegnazioneDocente) del titolare
    per l'anno corrente -- nessuno spacchettamento parziale (vedi limiti
    noti nella docstring del modulo). Ritorna quante ne ha trasferite."""
    from models.assegnazione import AssegnazioneDocente
    from routes.assegnazioni import _sync_docente_materie
    from routes.attivita_ist import iscrivi_docente_a_eventi_classe

    anno = _anno_scol_corrente()
    trasferite_classi = set()
    n = 0
    for asgn in AssegnazioneDocente.query.filter_by(
            anno_scol=anno, id_docente=id_titolare).all():
        asgn.id_docente = id_sostituto
        _sync_docente_materie(id_sostituto, asgn, anno)
        trasferite_classi |= {c.label_classe for c in asgn.classi}
        n += 1

    if trasferite_classi:
        iscrivi_docente_a_eventi_classe(id_sostituto, list(trasferite_classi), anno_scol=anno)
    return n


def _anno_scol_corrente():
    from config_anno import get_anno_corrente
    return get_anno_corrente()


def termina_sostituzione(id_sostituzione, creato_da=None):
    """Chiude una sostituzione TEMPORANEA: rimette l'orario spostato sul
    titolare (le righe che nel frattempo sono sparite -- es. un nuovo
    import orario completo -- vengono semplicemente ignorate, non e' un
    errore) e ripristina i partecipanti agli eventi istituzionali futuri
    ancora aperti. Non tocca le assenze/supplenze gia' generate (restano
    come storico)."""
    from models.sostituzione_docente import (
        SostituzioneDocente, SostituzioneOrarioSlot, SostituzioneEventoSwap,
    )
    from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante

    sost = SostituzioneDocente.query.get(id_sostituzione)
    if not sost:
        raise SostituzioneDocenteErrore('Sostituzione non trovata.')
    if sost.tipo != 'temporanea':
        raise SostituzioneDocenteErrore(
            'Solo una sostituzione temporanea può essere conclusa: una '
            'definitiva è un cambio di incarico permanente.')
    if sost.stato != 'attiva':
        raise SostituzioneDocenteErrore('Questa sostituzione è già conclusa.')

    n_ripristinati = 0
    for slot in SostituzioneOrarioSlot.query.filter_by(id_sostituzione=sost.id).all():
        riga = OrarioDocente.query.get(slot.id_orario_docente)
        if riga is not None:
            riga.id_docente = sost.id_titolare
            n_ripristinati += 1

    oggi = _date.today()
    for swap in SostituzioneEventoSwap.query.filter_by(id_sostituzione=sost.id).all():
        ev = AttivitaIst.query.get(swap.id_attivita)
        if not ev or ev.data < oggi:
            continue  # evento passato: non ha più senso invertire i partecipanti
        AttivitaIstPartecipante.query.filter_by(
            id_attivita=ev.id, id_docente=sost.id_sostituto).delete()
        if swap.titolare_era_presente and not AttivitaIstPartecipante.query.filter_by(
                id_attivita=ev.id, id_docente=sost.id_titolare).first():
            db.session.add(AttivitaIstPartecipante(
                id_attivita=ev.id, id_docente=sost.id_titolare, preset=True))

    sost.stato = 'conclusa'
    sost.concluso_il = _datetime_now()
    sost.concluso_da = creato_da
    db.session.commit()

    from modules.compresenze import invalida_cache
    invalida_cache()
    return {'sostituzione': sost, 'n_orario_ripristinato': n_ripristinati}
