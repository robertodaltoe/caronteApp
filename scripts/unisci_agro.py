"""
Unione dei due profili duplicati del docente Agrò Andrea:
  - id=2   AGRO'  (senza accento) — profilo storico, con tutto lo storico
           operativo (orario, banca ore, presenze, supplenze, cambio ore)
  - id=102 AGRÒ   (con accento) — profilo creato quest'anno con
           l'abilitazione corretta A-11 e la cattedra 2026-2027 corretta

Decisione (confermata da Roberto in chat):
  - Sopravvive id=2 (per non perdere lo storico).
  - Riceve: cognome accentato "AGRÒ", abilitazione A-11 (da id=102),
    id_classe_concorso=2 (A-11), tipo_contratto='TI',
    anno_scol_inizio='2026-2027' (da id=102 — evidentemente creato
    quando Agrò è diventato titolare quest'anno).
  - La cattedra 2026-2027 sbagliata su B-17 (id_assegnazione=3, dati
    inseriti per errore su id=2) viene eliminata; resta solo quella
    corretta su A-11 (id_assegnazione=17, spostata da id=102 a id=2).
  - id=102 viene eliminato dopo aver spostato tutte le sue righe.

Uso:
    python scripts/unisci_agro.py            # dry-run (nessuna scrittura)
    python scripts/unisci_agro.py --applica   # applica per davvero
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app
from models import db
from models.docente import Docente
from models.classe_concorso import DocenteClasseConcorso
from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse

ID_KEEP = 2
ID_DROP = 102


def main():
    applica = '--applica' in sys.argv
    app = create_app()
    with app.app_context():
        keep = Docente.query.get(ID_KEEP)
        drop = Docente.query.get(ID_DROP)
        if not keep or not drop:
            print('Uno dei due docenti non esiste più: keep=', keep, 'drop=', drop)
            return

        print(f'Prima: keep(id={ID_KEEP})={keep.cognome} {keep.nome} | '
              f'drop(id={ID_DROP})={drop.cognome} {drop.nome}')

        # 1) Elimina la cattedra 2026-2027 sbagliata su B-17 per id=2
        asgn_sbagliata = AssegnazioneDocente.query.filter_by(
            id_docente=ID_KEEP, anno_scol='2026-2027', id_classe_concorso=30).first()
        if asgn_sbagliata:
            n_classi = AssegnazioneClasse.query.filter_by(
                id_assegnazione=asgn_sbagliata.id).count()
            print(f'  - Elimino assegnazione id={asgn_sbagliata.id} (CC B-17, sbagliata), '
                  f'{n_classi} righe classe collegate')
            if applica:
                db.session.delete(asgn_sbagliata)  # cascade su AssegnazioneClasse
        else:
            print('  - Nessuna assegnazione B-17 trovata su id=2 (già pulita?)')

        # 2) Sposta l'abilitazione A-11 da id=102 a id=2
        abil = DocenteClasseConcorso.query.filter_by(id_docente=ID_DROP).all()
        for a in abil:
            print(f'  - Sposto abilitazione CC={a.id_classe_concorso} da 102 a 2')
            if applica:
                a.id_docente = ID_KEEP

        # 3) Sposta tutte le altre righe che referenziano id=102 su id=2
        # (attivita_ist_partecipanti/presenze e banca_ore/orario/supplenze/
        # scambi_ore hanno righe SOLO su id=2, verificato nell'audit
        # preliminare: nulla da spostare lì per id=102)
        from models.recupero import RecuperoDocente
        tabelle_da_spostare = [('recupero_docenti', RecuperoDocente, 'id_docente')]

        # Assegnazioni (la cattedra corretta A-11) — sposta id_docente 102 -> 2
        asgn_corretta = AssegnazioneDocente.query.filter_by(
            id_docente=ID_DROP, anno_scol='2026-2027', id_classe_concorso=2).first()
        if asgn_corretta:
            print(f'  - Sposto assegnazione corretta id={asgn_corretta.id} '
                  f'(CC A-11) da 102 a 2')
            if applica:
                asgn_corretta.id_docente = ID_KEEP

        for nome_tbl, Model, campo in tabelle_da_spostare:
            righe = Model.query.filter_by(**{campo: ID_DROP}).all()
            for r in righe:
                print(f'  - Sposto {nome_tbl} id={r.id} da 102 a 2')
                if applica:
                    setattr(r, campo, ID_KEEP)

        # 4) Aggiorna i campi anagrafica di id=2 con i valori corretti
        print('  - Aggiorno anagrafica id=2: cognome=AGRÒ, id_classe_concorso=2, '
              "tipo_contratto=TI, anno_scol_inizio=2026-2027")
        if applica:
            keep.cognome = 'AGRÒ'
            keep.nome_display = 'AGRÒ A.'
            keep.id_classe_concorso = 2
            keep.tipo_contratto = 'TI'
            keep.anno_scol_inizio = '2026-2027'

        # 5) Elimina id=102
        print(f'  - Elimino docente id={ID_DROP}')
        if applica:
            db.session.delete(drop)

        if applica:
            db.session.commit()
            print('APPLICATO.')
        else:
            db.session.rollback()
            print('DRY-RUN: nessuna modifica scritta. Rilancia con --applica per applicare.')


if __name__ == '__main__':
    main()
