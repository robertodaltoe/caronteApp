"""
Unisce le anagrafiche duplicate di Ghezzi e Tramontana, riscontrate
durante l'audit di /docenti (stesso pattern già visto per Agrò id 2/102):
un docente "storico" TD_annuale senza classe di concorso collegata, e uno
"nuovo" inserito per il 2026-2027 con la classificazione IRC corretta.

Per ciascuna coppia si tiene l'id storico (più dati operativi collegati:
banca ore, supplenze, presenze, ecc.), si adotta la classificazione IRC
corretta dal record nuovo, si spostano le righe collegate (abilitazione,
materia_ist, eventuali assegnazioni) e si elimina il duplicato.

Uso:
    python3 scripts/unisci_ghezzi_tramontana.py           # dry-run
    python3 scripts/unisci_ghezzi_tramontana.py --applica # applica
"""
import sys
sys.path.insert(0, '.')

from app import create_app
from models import db
from models.docente import Docente
from models.classe_concorso import DocenteClasseConcorso
from models.materia import DocenteMateria
from models.assegnazione import AssegnazioneDocente

APPLICA = '--applica' in sys.argv

# (id_da_tenere, id_da_eliminare, nome_finale)
COPPIE = [
    (43, 95, 'Angelo'),   # Ghezzi: tenuto id storico, nome unificato come da indicazione
    (81, 96, 'Miriana'),  # Tramontana: nome già coincidente
]

app = create_app()
with app.app_context():
    for id_tieni, id_elimina, nome_finale in COPPIE:
        tieni = Docente.query.get(id_tieni)
        elimina = Docente.query.get(id_elimina)
        if not tieni or not elimina:
            print(f"Salto {id_tieni}/{id_elimina}: uno dei due non esiste più.")
            continue

        print(f"\n=== {tieni.cognome}: tengo id={id_tieni} ({tieni.nome}), "
              f"elimino id={id_elimina} ({elimina.nome}) ===")

        print(f"  nome: '{tieni.nome}' -> '{nome_finale}'")
        print(f"  tipo_contratto: '{tieni.tipo_contratto}' -> '{elimina.tipo_contratto}'")
        print(f"  id_classe_concorso: {tieni.id_classe_concorso} -> {elimina.id_classe_concorso}")
        print(f"  anno_scol_inizio: {tieni.anno_scol_inizio} -> {elimina.anno_scol_inizio}")

        if APPLICA:
            tieni.nome = nome_finale
            tieni.nome_display = f"{tieni.cognome} {nome_finale[0]}."
            tieni.tipo_contratto = elimina.tipo_contratto
            tieni.id_classe_concorso = elimina.id_classe_concorso
            tieni.anno_scol_inizio = elimina.anno_scol_inizio

        # Abilitazioni (classi di concorso collegate)
        for a in DocenteClasseConcorso.query.filter_by(id_docente=id_elimina).all():
            print(f"  sposto abilitazione cc={a.id_classe_concorso}")
            if APPLICA:
                esiste = DocenteClasseConcorso.query.filter_by(
                    id_docente=id_tieni, id_classe_concorso=a.id_classe_concorso).first()
                if esiste:
                    db.session.delete(a)
                else:
                    a.id_docente = id_tieni

        # Materie collegate (per anno — non c'è conflitto se l'anno è diverso)
        for m in DocenteMateria.query.filter_by(id_docente=id_elimina).all():
            print(f"  sposto materia_ist id_materia={m.id_materia} anno={m.anno_scol}")
            if APPLICA:
                esiste = DocenteMateria.query.filter_by(
                    id_docente=id_tieni, id_materia=m.id_materia, anno_scol=m.anno_scol).first()
                if esiste:
                    db.session.delete(m)
                else:
                    m.id_docente = id_tieni

        # Assegnazioni (classi -> docenti)
        for asg in AssegnazioneDocente.query.filter_by(id_docente=id_elimina).all():
            print(f"  sposto assegnazione id={asg.id}")
            if APPLICA:
                asg.id_docente = id_tieni

        if APPLICA:
            db.session.delete(elimina)
            db.session.commit()
            print(f"  -> unito.")

    if not APPLICA:
        print("\n[DRY RUN] Nessuna modifica scritta. Rilancia con --applica per confermare.")
