from flask import Blueprint, render_template, request
from models.supplenza import Supplenza
from models.aula import Aula
from models.aula_override import AulaOverride
from models.orario_docente import OrarioDocente
from models.migrazione_slot import MigrazioneSlot
from models.attivita_fuori_aula import AttivitaFuoriAula
from models.assenza import Assenza
from models.docente import Docente
from datetime import date, timedelta

display_bp = Blueprint('display', __name__)

@display_bp.route('/display')
def display():
    oggi = date.today()
    data_str = request.args.get('data', oggi.isoformat())
    try:
        data_sel = date.fromisoformat(data_str)
    except ValueError:
        data_sel = oggi

    supplenze = Supplenza.query\
        .filter_by(data=data_sel)\
        .order_by(Supplenza.ora)\
        .all()

    # Mappa classe -> aula standard
    aule_map = {a.classe: a for a in Aula.query.all()}

    # Mappa id_supplenza -> override aula
    override_map = {ov.id_supplenza: ov for ov in AulaOverride.query.all()}

    # Mappa (id_docente, giorno, ora) -> materia per trovare la materia dell'assente
    giorno = data_sel.weekday()
    slot_map = {}
    for s in OrarioDocente.query.filter_by(giorno=giorno).all():
        slot_map[(s.id_docente, s.ora)] = s.materia or ''

    # Migrazione gruppi: raggruppa per ora
    # { ora: [ {classe_dest, attivita} ] }
    from collections import defaultdict
    migrazione_per_ora = defaultdict(list)
    att_oggi = AttivitaFuoriAula.query.filter(
        AttivitaFuoriAula.data_inizio <= data_sel,
        AttivitaFuoriAula.data_fine   >= data_sel,
        AttivitaFuoriAula.stato == 'attiva',
        AttivitaFuoriAula.gruppo_rimanente == True,
    ).all()
    for att in att_oggi:
        if att.ricorrenza == 'settimanale' and giorno not in att.giorni_sett_list:
            continue
        slots = MigrazioneSlot.query.filter_by(id_attivita=att.id).all()
        for slot in slots:
            if slot.classe_dest:
                migrazione_per_ora[slot.ora].append({
                    'classe_orig': ', '.join(att.classi_list),
                    'classe_dest': slot.classe_dest,
                    'attivita': att.descrizione or att.tipo_label,
                })

    # Classi libere: assenze con classe_libera=True
    # Per ogni assenza determina se "ENTRA DOPO" o "ESCE PRIMA"
    # in base alle ore libere rispetto all'orario del docente quel giorno
    classi_libere = []
    assenze_cl = Assenza.query.filter_by(data=data_sel, classe_libera=True).all()
    for a in assenze_cl:
        slots_doc = OrarioDocente.query.filter_by(
            id_docente=a.id_docente, giorno=giorno
        ).order_by(OrarioDocente.ora).all()
        classi_reali = [s for s in slots_doc
                        if s.classe and s.classe not in ('---','-x-','','POTENZIAMENTO')]
        if not classi_reali:
            continue
        ore_docente = [s.ora for s in classi_reali]
        ore_assenza = list(range(a.ora_inizio, a.ora_fine + 1))
        ore_libere  = [o for o in ore_assenza if o in ore_docente]
        if not ore_libere:
            continue
        prima_ore_doc = min(ore_docente)
        ultima_ore_doc = max(ore_docente)
        # Se le ore libere sono le prime dell'orario → ENTRA DOPO
        # Se sono le ultime → ESCE PRIMA
        if min(ore_libere) == prima_ore_doc:
            tipo_cl = 'entra_dopo'
            testo   = 'ENTRA DOPO'
            ultima_libera = max(ore_libere)
        else:
            tipo_cl = 'esce_prima'
            testo   = 'ESCE PRIMA'
            ultima_libera = min(ore_libere)
        # Raggruppa classi distinte coinvolte
        classi_coinvolte = list({s.classe for s in classi_reali if s.ora in ore_libere})
        for classe in classi_coinvolte:
            classi_libere.append({
                'ora_inizio': min(ore_libere),
                'ora_fine':   max(ore_libere),
                'ore':        ore_libere,
                'classe':     classe,
                'tipo':       tipo_cl,
                'testo':      testo,
                'docente':    Docente.query.get(a.id_docente),
            })

    return render_template('display.html',
        timedelta=timedelta,
        supplenze=supplenze,
        data_sel=data_sel,
        aule_map=aule_map,
        override_map=override_map,
        slot_map=slot_map,
        migrazione_per_ora=dict(migrazione_per_ora),
        classi_libere=classi_libere,
    )
