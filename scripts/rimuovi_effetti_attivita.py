"""
Rimuove le assenze (e indisponibilità / supplenze automatiche collegate)
generate da una attività fuori aula ormai cancellata, per un docente.

Le righe generate da genera_effetti() (routes/attivita.py) portano nelle
note il marcatore "[<id attività>]". Se l'attività è stata eliminata senza
passare da _pulisci_effetti, restano orfane.

Uso:
    python scripts/rimuovi_effetti_attivita.py --id 57 --docente Parolo            # dry-run
    python scripts/rimuovi_effetti_attivita.py --id 57 --docente Parolo --applica  # applica

Con --applica: backup cifrato prima, eliminazione con lapide di sync
(stesso percorso dell'eliminazione assenza da interfaccia), poi
PRAGMA integrity_check.
"""
import argparse
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app
from models import db
from models.assenza import Assenza
from models.docente import Docente
from models.indisponibilita import Indisponibilita
from models.supplenza import Supplenza
from modules.auto_sync import registra_eliminazione

GIORNI = ['lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', type=int, required=True, help='id attività (il numero tra [ ])')
    ap.add_argument('--docente', required=True, help='cognome (parziale) del docente')
    ap.add_argument('--applica', action='store_true')
    a = ap.parse_args()
    marker = f'[{a.id}]'

    app = create_app()
    with app.app_context():
        # Cognome esatto in priorità ("Parolo" non deve trovare "Comparolo");
        # in alternativa corrispondenza parziale.
        docs = Docente.query.filter(db.func.lower(Docente.cognome) == a.docente.lower()).all()
        if not docs:
            docs = Docente.query.filter(Docente.cognome.ilike(f'%{a.docente}%')).all()
        if len(docs) != 1:
            print('Docenti trovati:', [(d.id, d.cognome, d.nome) for d in docs])
            print('Serve esattamente un docente: affina --docente.')
            return
        d = docs[0]
        print(f'Docente: id={d.id} {d.cognome} {d.nome}  marcatore: {marker}')

        assenze = (Assenza.query.filter_by(id_docente=d.id)
                   .filter(Assenza.note_interne.like(f'%{marker}%'))
                   .order_by(Assenza.data, Assenza.ora_inizio).all())
        indisp = (Indisponibilita.query.filter_by(id_docente=d.id)
                  .filter(Indisponibilita.note.like(f'%{marker}%'))
                  .order_by(Indisponibilita.data, Indisponibilita.ora).all())
        suppl = (Supplenza.query.filter_by(id_assente=d.id, origine='automatica')
                 .filter(Supplenza.note.like(f'%{marker}%'))
                 .order_by(Supplenza.data, Supplenza.ora).all())

        print(f'\nAssenze ({len(assenze)}):')
        for x in assenze:
            print(f'  id={x.id} {x.data} {GIORNI[x.data.weekday()]} ore {x.ora_inizio}-{x.ora_fine} | {x.note_interne}')
        print(f'Indisponibilità ({len(indisp)}):')
        for x in indisp:
            print(f'  id={x.id} {x.data} {GIORNI[x.data.weekday()]} ora {x.ora} | {x.note}')
        print(f'Supplenze automatiche ({len(suppl)}) — stato diverso da scoperta/non_assegnabile NON vengono toccate:')
        for x in suppl:
            print(f'  id={x.id} {x.data} ora {x.ora} {x.classe} stato={x.stato}')

        if not a.applica:
            print('\nDry-run: nessuna scrittura. Aggiungi --applica per eseguire.')
            return
        if not (assenze or indisp or suppl):
            print('Niente da rimuovere.')
            return

        from modules.backup_cifrato import crea_backup_cifrato
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bk = crea_backup_cifrato(os.path.join(base, 'database.db'),
                                 os.path.join(base, 'data', 'backup'),
                                 suffisso=f'_pre_rimuovi_attivita_{a.id}')
        print('Backup:', bk)

        from routes.assenze import _elimina_assenza_righe
        for x in assenze:
            _elimina_assenza_righe(x, 'script')
        db.session.flush()
        for x in indisp:
            registra_eliminazione('indisponibilita', {
                'id_docente': x.id_docente, 'data': x.data.isoformat(), 'ora': x.ora},
                utente='script')
            db.session.delete(x)
        for x in suppl:
            if x in db.session and x.stato in ('scoperta', 'non_assegnabile'):
                registra_eliminazione('supplenze', {
                    'data': x.data.isoformat(), 'ora': x.ora,
                    'classe': x.classe, 'id_assente': x.id_assente}, utente='script')
                db.session.delete(x)
        db.session.commit()
        print('Integrity check:', db.session.execute(db.text('PRAGMA integrity_check')).scalar())


if __name__ == '__main__':
    main()
