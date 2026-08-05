"""
backfill_id_materia.py — una tantum

Corregge due problemi distinti sui dati storici di AssegnazioneClasse.id_materia
(FK verso la tabella Materia), entrambi descritti in DEVLOG.md:

CASO A — Task 19decies: "materia singola" con id_materia NULL.
Per le classi con una sola materia nel piano studi per quella classe di
concorso, il form di Assegnazioni non passava esplicitamente quale
materia (non c'era ambiguità) — AssegnazioneClasse.id_materia restava
NULL. Conseguenze: la sincronizzazione automatica verso "Docenti ↔
Materie" non aveva modo di sapere quale materia sincronizzare, e
l'export "scheda classe" mostrava il tipo di contratto al posto del
nome materia.

CASO B — Task 19undecies, PIÙ SERIO: id_materia con il valore SBAGLIATO
per le classi "multi-materia". Il form multi-materia (quello con un
campo per ogni materia, es. Lettere/Latino/Storia in 1a Liceo) etichetta
ogni campo con l'id della RIGA di PianoStudi (PianoStudi.id), non con
l'id della materia vera e propria (PianoStudi.id_materia, la FK verso
la tabella Materia — sono due entità distinte con contatori indipendenti).
Quel numero veniva salvato così com'è in AssegnazioneClasse.id_materia,
che però è dichiarata come FK verso Materia: il risultato è che ogni
assegnazione multi-materia storica punta quasi sempre a una materia
SBAGLIATA (qualunque riga della tabella Materia abbia per caso lo stesso
id numerico della riga di PianoStudi). Bug presente probabilmente da
quando è stato introdotto il form multi-materia — non è nuovo, solo mai
notato prima perché "Docenti ↔ Materie" non veniva ancora sincronizzato
automaticamente da qui.

Questo script:
  1. Per ogni AssegnazioneClasse con id_materia NULL (caso A, esclusa
     POT): se il piano studi ha un'unica materia per quella combinazione
     classe di concorso/indirizzo/anno corso, la imposta.
  2. Per ogni AssegnazioneClasse con id_materia valorizzato (caso B):
     verifica se il valore combacia con l'id di una riga di PianoStudi
     nel CONTESTO GIUSTO (stessa classe di concorso/indirizzo/anno corso/
     anno scolastico dell'assegnazione) invece che con un vero id di
     Materia per quello stesso contesto — se sì, è quasi certamente il
     bug: corregge a PianoStudi.id_materia. Se il valore combacia già
     con un id di Materia valido per il contesto, non tocca nulla
     (segno che quella riga era già corretta).
  3. Per ogni docente reale toccato, sincronizza "Docenti ↔ Materie"
     (stessa funzione usata dal salvataggio normale, quindi origine='auto').

Le righe che restano ambigue (0 o più materie nel piano studi per quella
combinazione, per il caso A) non vengono toccate — restano NULL come
prima, nessuna modifica.

Uso (una sola volta, con venv attivo, DOPO aver aggiornato il codice):
    python scripts/backfill_id_materia.py            # dry-run: stampa cosa farebbe
    python scripts/backfill_id_materia.py --applica   # applica davvero

Fare un backup del database prima di eseguirlo con --applica (la
cifratura automatica di app.py già ne crea uno a ogni avvio, ma un
backup dedicato pre-intervento è più tranquillo — vedi
modules/backup_cifrato.py o semplicemente una copia manuale di
database.db).

IMPORTANTE: questo script sostituisce integralmente una prima versione
scritta per il solo Caso A, che purtroppo conteneva essa stessa lo
stesso errore del Caso B (restituiva PianoStudi.id invece di
PianoStudi.id_materia) — non è mai stata eseguita con --applica su un
database reale, solo in dry-run e su copie di prova, quindi nessun dato
reale è stato corrotto da quella versione. Vedi DEVLOG Task 19undecies.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db
from models.assegnazione import AssegnazioneClasse
from models.piano_studi import PianoStudi
from models.materia import DocenteMateria, Materia


def _piano_contesto(anno_scol, cc_id, anno_corso, indirizzo):
    return PianoStudi.query.filter_by(
        anno_scol=anno_scol, id_classe_concorso=cc_id,
        anno_corso=anno_corso, indirizzo=indirizzo, compresenza=False).all()


def main():
    applica = '--applica' in sys.argv
    app = create_app()
    with app.app_context():
        tutte = (AssegnazioneClasse.query
                 .filter(AssegnazioneClasse.indirizzo != 'POT')
                 .all())

        n_caso_a = 0
        n_caso_b = 0
        n_ambigue = 0
        n_ok = 0
        docenti_da_sync = set()  # {(id_docente, anno_scol)}
        # Per ogni docente/anno toccato dal Caso B, i vecchi id sbagliati
        # corretti — servono per ripulire eventuali righe DocenteMateria
        # già create con quel valore sbagliato PRIMA che esistesse il
        # campo 'origine' (quindi marcate 'manuale' per default della
        # migrazione, non perché scelte davvero a mano — la pulizia
        # automatica delle 'auto' orfane da sola non le tocca).
        vecchi_valori_da_ripulire = {}  # {(id_docente, anno_scol): {vecchio_id, ...}}

        for ac in tutte:
            asgn = ac.assegnazione
            contesto = _piano_contesto(asgn.anno_scol, asgn.id_classe_concorso,
                                        ac.anno_corso, ac.indirizzo)
            if not contesto:
                continue  # nessun piano studi per questa combinazione, non decidibile

            id_materie_valide = {p.id_materia for p in contesto if p.id_materia}
            id_piano_studi_righe = {p.id: p.id_materia for p in contesto}

            if ac.id_materia is None:
                # Caso A
                if len(contesto) == 1 and contesto[0].id_materia:
                    nuovo = contesto[0].id_materia
                    n_caso_a += 1
                    print(f'  [A] {asgn.anno_scol} {asgn.display_name:30s} '
                          f'{ac.label_classe:16s} NULL -> materia id {nuovo}'
                          f'{"" if applica else "  (dry-run)"}')
                    if applica:
                        ac.id_materia = nuovo
                        if asgn.id_docente:
                            docenti_da_sync.add((asgn.id_docente, asgn.anno_scol))
                else:
                    n_ambigue += 1
                continue

            if ac.id_materia in id_materie_valide:
                # Già corretto: punta a un vero id di Materia coerente col contesto.
                n_ok += 1
                continue

            if ac.id_materia in id_piano_studi_righe:
                # Caso B: il valore salvato è in realtà l'id di una riga di
                # PianoStudi di questo stesso contesto, non un id di Materia.
                corretto = id_piano_studi_righe[ac.id_materia]
                if corretto:
                    n_caso_b += 1
                    mat_sbagliata = Materia.query.get(ac.id_materia)
                    mat_giusta = Materia.query.get(corretto)
                    print(f'  [B] {asgn.anno_scol} {asgn.display_name:30s} '
                          f'{ac.label_classe:16s} '
                          f'"{mat_sbagliata.nome if mat_sbagliata else ac.id_materia}" (sbagliata) -> '
                          f'"{mat_giusta.nome if mat_giusta else corretto}" (corretta)'
                          f'{"" if applica else "  (dry-run)"}')
                    if applica:
                        vecchio = ac.id_materia
                        ac.id_materia = corretto
                        if asgn.id_docente:
                            chiave = (asgn.id_docente, asgn.anno_scol)
                            docenti_da_sync.add(chiave)
                            vecchi_valori_da_ripulire.setdefault(chiave, set()).add(vecchio)
                else:
                    n_ambigue += 1
            else:
                # Non combacia né con un id Materia né con un id PianoStudi
                # di questo contesto: non decidibile automaticamente, non tocco.
                n_ambigue += 1

        print(f'\nCaso A (NULL risolti): {n_caso_a}')
        print(f'Caso B (id sbagliato corretto): {n_caso_b}')
        print(f'Già corrette: {n_ok}')
        print(f'Non decidibili automaticamente (nessuna modifica): {n_ambigue}')

        if not applica:
            print('\nDRY-RUN: nessuna modifica scritta. Rilanciare con --applica per applicare davvero.')
            return

        db.session.commit()
        print('AssegnazioneClasse aggiornate e salvate.')

        # Per ogni docente toccato: ricalcola da zero le materie derivate
        # dalle sue assegnazioni correnti (ora corrette) e rimuove dalle
        # "auto" quelle che risultavano dal valore sbagliato di prima,
        # aggiungendo quelle corrette.
        n_sync = 0
        n_rimosse = 0
        n_rimosse_manuali_sbagliate = 0
        for chiave in docenti_da_sync:
            id_doc, anno_scol = chiave
            assegnazioni_doc = (AssegnazioneClasse.query
                .join(AssegnazioneClasse.assegnazione)
                .filter_by(anno_scol=anno_scol, id_docente=id_doc).all())
            materie_corrette = {a.id_materia for a in assegnazioni_doc if a.id_materia}

            # Rimuove le 'auto' che non sono (più) tra le materie corrette
            # coperte dalle sue assegnazioni attuali.
            for dm in DocenteMateria.query.filter_by(
                    id_docente=id_doc, anno_scol=anno_scol, origine='auto').all():
                if dm.id_materia not in materie_corrette:
                    db.session.delete(dm)
                    n_rimosse += 1

            # Rimuove anche le righe (di QUALSIASI origine, incluse
            # 'manuale' per default di migrazione) che puntano esattamente
            # a uno dei vecchi valori sbagliati appena corretti per questo
            # stesso docente/anno — a meno che quel valore non sia
            # comunque ancora valido per un'altra materia realmente
            # coperta (edge case molto raro, per sicurezza non le tocca).
            for vecchio in vecchi_valori_da_ripulire.get(chiave, set()):
                if vecchio in materie_corrette:
                    continue
                dm_sbagliata = DocenteMateria.query.filter_by(
                    id_docente=id_doc, anno_scol=anno_scol, id_materia=vecchio).first()
                if dm_sbagliata:
                    db.session.delete(dm_sbagliata)
                    n_rimosse_manuali_sbagliate += 1

            for id_mat in materie_corrette:
                esiste = DocenteMateria.query.filter_by(
                    id_docente=id_doc, id_materia=id_mat, anno_scol=anno_scol).first()
                if not esiste:
                    db.session.add(DocenteMateria(
                        id_docente=id_doc, id_materia=id_mat,
                        anno_scol=anno_scol, origine='auto'))
                    n_sync += 1
        db.session.commit()
        print(f'Righe DocenteMateria con vecchio id sbagliato rimosse '
              f'(qualsiasi origine): {n_rimosse_manuali_sbagliate}')
        print(f'Docenti ↔ Materie: {n_sync} nuove righe create, '
              f'{n_rimosse} righe automatiche sbagliate rimosse.')


if __name__ == '__main__':
    main()
