"""
backfill_docente_materie.py — una tantum

Roberto: "perche in docenti-materia per la classe di concorso a-11 non
ho la compilazione automatica dalla pagina assegnazioni?"

Causa: le Assegnazioni con id_materia già corretto ("caso OK" di
scripts/backfill_id_materia.py) non sono mai state sincronizzate verso
"Docenti ↔ Materie" (DocenteMateria) — quel backfill sincronizzava
SOLO i docenti che doveva correggere (Caso A/B), non tutti quelli con
dati già validi. La sincronizzazione "live" (routes/assegnazioni.py::
_sync_docente_materie, chiamata da salva/aggiorna-ore/nomina) esiste dal
10/07/2026, ma si applica solo ai salvataggi fatti DA QUEL MOMENTO IN
POI attraverso quelle tre route — molte Assegnazioni reali risultano
comunque mai sincronizzate (verificato: query diretta, 0 righe
DocenteMateria con origine='auto' su tutto il 2026-2027 nonostante
centinaia di AssegnazioneClasse con id_materia valorizzato).

Questo script applica _sync_docente_materie() (la STESSA funzione già
usata dai salvataggi normali — nessuna logica nuova, nessun rischio di
comportamento diverso) a OGNI AssegnazioneDocente con un docente reale
(non placeholder) e almeno una classe con id_materia valorizzato, per
tutti gli anni scolastici presenti. Idempotente: non tocca mai righe
DocenteMateria già esistenti, mai quelle 'manuale', crea solo quelle
mancanti con origine='auto'.

Uso:
    python scripts/backfill_docente_materie.py            # dry-run
    python scripts/backfill_docente_materie.py --applica   # applica davvero

Fare un backup cifrato del database prima di eseguirlo con --applica
(vedi modules/backup_cifrato.py).
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db
from models.assegnazione import AssegnazioneDocente
from models.materia import DocenteMateria


def main():
    applica = '--applica' in sys.argv
    app = create_app()
    with app.app_context():
        from routes.assegnazioni import _sync_docente_materie

        assegnazioni = (AssegnazioneDocente.query
                         .filter(AssegnazioneDocente.id_docente.isnot(None))
                         .order_by(AssegnazioneDocente.anno_scol, AssegnazioneDocente.id)
                         .all())

        n_creati_tot = 0
        n_asgn_toccate = 0
        for asgn in assegnazioni:
            materie_ids = {ac.id_materia for ac in asgn.classi if ac.id_materia}
            if not materie_ids:
                continue
            mancanti = [
                mid for mid in materie_ids
                if not DocenteMateria.query.filter_by(
                    id_docente=asgn.id_docente, id_materia=mid,
                    anno_scol=asgn.anno_scol).first()
            ]
            if not mancanti:
                continue
            n_asgn_toccate += 1
            n_creati_tot += len(mancanti)
            print(f'  {asgn.anno_scol} {asgn.display_name:30s} '
                  f'CC={asgn.classe_concorso.codice if asgn.classe_concorso else "?":6s} '
                  f'materie mancanti: {sorted(mancanti)}'
                  f'{"" if applica else "  (dry-run)"}')
            if applica:
                _sync_docente_materie(asgn.id_docente, asgn, asgn.anno_scol)

        print()
        print(f'Assegnazioni con materie mancanti in DocenteMateria: {n_asgn_toccate}')
        print(f'Righe DocenteMateria da creare (origine=auto): {n_creati_tot}')
        if not applica:
            print('\nDRY-RUN — nessuna modifica applicata. Rilancia con --applica per eseguire.')
        else:
            print('\nApplicato.')


if __name__ == '__main__':
    main()
