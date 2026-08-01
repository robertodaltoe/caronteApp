"""
Seed una tantum: classi di concorso (IIS Leonardo da Vinci, da organico
di diritto fornito dall'USR Sondrio per il 2026/27) + collegamento alle
materie già esistenti nel database. Da lanciare una sola volta a mano.
"""
import sys, os
# Percorso della cartella radice del progetto (questo script vive in
# scripts/legacy/, due livelli sotto la radice dove sta app.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app
from models import db
from models.classe_concorso import ClasseConcorso, CattedraOrganico
from models.materia import Materia

app = create_app()

ANNO_DIRITTO = '2026-2027'

# (codice, nome, tipo_posto)
CLASSI_CONCORSO = [
    ('A-01', 'Disegno e Storia Arte sec. II grado', 'cattedra'),
    ('A-11', 'Discipline Letterarie e Latino', 'cattedra'),
    ('A-12', 'Discipline Letterarie sec. II grado', 'cattedra'),
    ('A-18', 'Filosofia e Scienze Umane', 'cattedra'),
    ('A-19', 'Filosofia e Storia', 'cattedra'),
    ('A-20', 'Fisica', 'cattedra'),
    ('A-21', 'Geografia', 'cattedra'),
    ('A-22-ING', 'Lingua e Culture Straniere (Inglese)', 'cattedra'),
    ('A-22-SPA', 'Lingua e Culture Straniere (Spagnolo)', 'cattedra'),
    ('A-22-TED', 'Lingua e Culture Straniere (Tedesco)', 'cattedra'),
    ('A-26', 'Matematica', 'cattedra'),
    ('A-27', 'Matematica e Fisica', 'cattedra'),
    ('A-34', 'Scienze e Tecnologie Chimiche', 'cattedra'),
    ('A-37', 'Costruzioni Tecnologie e Tecniche Rappr. Grafica', 'cattedra'),
    ('A-45', 'Scienze Economico-Aziendali', 'cattedra'),
    ('A-46', 'Scienze Giuridico-Economiche', 'cattedra'),
    ('A-47', 'Scienze Matematiche Applicate', 'cattedra'),
    ('A-48', 'Scienze Motorie e Sportive sec. II grado', 'cattedra'),
    ('A-50', 'Scienze Naturali, Chimica e Biologia', 'cattedra'),
    ('A-51', 'Scienze, Tecnologie e Tecniche Agrarie', 'cattedra'),
    ('B-02-ING', 'Conversazione Lingua Straniera (Inglese)', 'itp'),
    ('B-14', 'Laboratorio Scienze e Tecnologie Costruzioni', 'itp'),
    ('ADSS', 'Area Unica Sostegno', 'sostegno'),
]

# (codice_cc, n_docenti, n_coi, n_coe, direzione, scuola, coe_ore, ore_residue, n_potenziamento)
ORGANICO_DIRITTO = [
    ('A-01',     2, 1, 1, 'completa_con', 'IIS Balilla Pinchetti', 8,  None, 0),
    ('A-11',     8, 8, 1, 'completa_con', 'Liceo P. Nervi - G. Ferrari', 6, 12, 0),
    ('A-12',     4, 5, 0, 'cede_a',       'ITI Enea Mattei',       None, 6,  0),
    ('A-18',     2, 1, 1, 'completa_con', 'IS Saraceno - Romegialli', 9, None, 0),
    ('A-19',     3, 3, 1, 'completa_con', 'Liceo P. Nervi - G. Ferrari', 9, None, 0),
    ('A-20',     1, 1, 0, None,           None,                    None, None, 0),
    ('A-21',     0, 0, 0, 'cede_a',       'IIS Balilla Pinchetti', None, 8,  0),
    ('A-22-ING', 3, 6, 0, None,           None,                    None, None, 0),
    ('A-22-SPA', 0, 2, 0, None,           None,                    None, None, 0),
    ('A-22-TED', 3, 3, 0, 'cede_a',       'Liceo P. Nervi - G. Ferrari', None, 10, 0),
    ('A-26',     4, 4, 0, None,           None,                    None, None, 0),
    ('A-27',     3, 4, 0, None,           None,                    None, None, 0),
    ('A-34',     1, 1, 0, None,           None,                    None, None, 1),  # potenziamento
    ('A-37',     0, 2, 1, 'completa_con', 'IS Saraceno - Romegialli', 3, 16, 0),
    ('A-45',     1, 1, 1, 'completa_con', 'Ist. Prof. Crotto Caurga', 9, None, 0),
    ('A-46',     2, 3, 0, 'cede_a',       'Ist. Prof. Crotto Caurga', None, 8, 1),  # potenziamento
    ('A-47',     1, 1, 0, None,           None,                    None, None, 0),
    ('A-48',     4, 5, 0, None,           None,                    None, None, 0),
    ('A-50',     3, 3, 1, 'completa_con', 'Liceo P. Nervi - G. Ferrari', 6, 12, 0),
    ('A-51',     1, 0, 1, 'completa_con', 'IS Saraceno - Romegialli', 7, 11, 0),
    ('B-02-ING', 0, 0, 0, 'cede_a',       'Liceo P. Nervi - G. Ferrari', None, 8, 0),
    ('B-14',     1, 1, 1, 'completa_con', 'IS Saraceno - Romegialli', 9, None, 0),
    ('A-22-TED', 0, 0, 0, None,           None,                    None, None, 1),  # potenziamento aggiuntivo Tedesco
]

# Collegamento materie esistenti -> classe di concorso (per sigla materia)
MATERIA_TO_CLASSE = {
    'ITA':       'A-11',
    'LAT':       'A-11',
    'STO-GEO':   'A-12',   # Storia e Geografia, biennio - storia/lettere
    'STO':       'A-19',   # Storia (triennio licei) - Filosofia e Storia
    'DIS-ARTE':  'A-01',
    'ST-ARTE':   'A-01',
    'ING':       'A-22-ING',
    'ING-CONV':  'B-02-ING',
    'TED':       'A-22-TED',
    'TED-CONV':  'A-22-TED',
    'SPA':       'A-22-SPA',
    'SPA-CONV':  'A-22-SPA',
    'MAT':       'A-26',
    'MAT-FIS':   'A-27',
    'FIS':       'A-20',
    'SCI':       'A-50',
    'CHI':       'A-34',
    'INFO':      'A-47',
    'TEC-INFO':  'A-41',   # nota: A-41 non in elenco organico, da verificare con Roberto
    'SC-UM':     'A-18',
    'FILO':      'A-18',   # Filosofia (LSU) - Filosofia e Scienze Umane
    'DIR-ECO':   'A-46',
    'DIR':       'A-46',
    'REL-INT':   'A-46',
    'EC-AZ':     'A-45',
    'EC-AZ-GEO': 'A-45',
    'DIR-SPORT': 'A-46',
    'TOPO':      'A-51',
    'GEO-EST':   'A-51',
    'PCI':       'A-37',
    'CANT-SIC':  'A-37',
    'TTRG':      'A-37',
    'TTRG-SAL':  'A-37',
    'TOPO-CANT': 'A-51',
    'SC-MOT':    'A-48',
    'DISC-SP':   'A-48',
    'SC-DISC-SP': 'A-48',
    'SOS':       'ADSS',
}


def main():
    with app.app_context():
        cc_map = {}
        for codice, nome, tipo_posto in CLASSI_CONCORSO:
            cc = ClasseConcorso.query.filter_by(codice=codice).first()
            if not cc:
                cc = ClasseConcorso(codice=codice, nome=nome, tipo_posto=tipo_posto)
                db.session.add(cc)
                db.session.commit()
                print(f'Creata classe di concorso: {codice} - {nome}')
            cc_map[codice] = cc

        n_org = 0
        for (codice, n_doc, n_coi, n_coe, direzione, scuola, coe_ore,
             ore_res, n_pot) in ORGANICO_DIRITTO:
            cc = cc_map.get(codice)
            if not cc:
                print(f'ATTENZIONE: classe di concorso {codice} non trovata, salto riga organico')
                continue
            esiste = CattedraOrganico.query.filter_by(
                anno_scol=ANNO_DIRITTO, tipo='diritto', id_classe_concorso=cc.id).first()
            if esiste:
                # Riga di potenziamento aggiuntivo sulla stessa classe: somma il potenziamento
                if n_pot:
                    esiste.n_potenziamento = (esiste.n_potenziamento or 0) + n_pot
                    db.session.commit()
                continue
            db.session.add(CattedraOrganico(
                anno_scol=ANNO_DIRITTO, tipo='diritto', id_classe_concorso=cc.id,
                n_docenti=n_doc, n_coi=n_coi, n_coe=n_coe,
                coe_direzione=direzione, coe_scuola=scuola, coe_ore=coe_ore,
                ore_residue=ore_res, n_potenziamento=n_pot,
            ))
            n_org += 1
        db.session.commit()
        print(f'Righe organico di diritto inserite: {n_org}')

        n_link = 0
        for sigla_materia, codice_cc in MATERIA_TO_CLASSE.items():
            cc = cc_map.get(codice_cc)
            if not cc:
                print(f'ATTENZIONE: classe {codice_cc} non trovata per materia {sigla_materia}')
                continue
            m = Materia.query.filter_by(sigla=sigla_materia).first()
            if not m:
                print(f'ATTENZIONE: materia {sigla_materia} non trovata nel database')
                continue
            if m.id_classe_concorso != cc.id:
                m.id_classe_concorso = cc.id
                n_link += 1
        db.session.commit()
        print(f'Materie collegate a classe di concorso: {n_link}')


if __name__ == '__main__':
    main()
