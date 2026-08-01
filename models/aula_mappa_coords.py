"""
models/aula_mappa_coords.py

Coordinate delle aule sulla piantina, organizzate per SEZIONE (una immagine
per piano/edificio, fornita già ritagliata da Roberto). Ogni sezione ha:
  - immagine: percorso relativo dentro static/
  - aule: dict aula -> {x, y, w, h} in percentuale (0-100) rispetto
    ALLA SUA immagine (non a un'unica piantina globale)

sede — deve corrispondere esattamente a un valore di models.aula.SEDI
"""

SEZIONI = {
    'cc_piano_terra': {
        'immagine': 'img/cc_piano_terra.jpg',
        'titolo': 'Corpo Centrale — Piano Terra',
        'sede': 'Sede Centrale - Piano Terra',
        'aule': {
            '6':  {'x': 9.0,  'y': 42.85, 'w': 2.2, 'h': 2.3},
            '7':  {'x': 17.9, 'y': 41.85, 'w': 2.2, 'h': 2.3},
            '5':  {'x': 7.9,  'y': 52.85, 'w': 2.2, 'h': 2.3},
            '4':  {'x': 7.9,  'y': 61.85, 'w': 2.2, 'h': 2.3},
            '3':  {'x': 13.9, 'y': 61.85, 'w': 2.2, 'h': 2.3},
            '2':  {'x': 18.9, 'y': 61.85, 'w': 2.2, 'h': 2.3},
            '1':  {'x': 24.9, 'y': 60.85, 'w': 2.2, 'h': 2.3},
            '8B': {'x': 79.83, 'y': 47.85, 'w': 2.2, 'h': 2.3},
            '8C': {'x': 84.02, 'y': 46.66, 'w': 2.2, 'h': 2.3},
            '8A': {'x': 73.56, 'y': 58.89, 'w': 2.2, 'h': 2.3},
        },
    },
    'cc_primo_piano': {
        'immagine': 'img/cc_primo_piano.jpg',
        'titolo': 'Corpo Centrale — 1° Piano',
        'sede': 'Sede Centrale - 1° Piano',
        'aule': {
            '15': {'x': 8.9,  'y': 42.85, 'w': 2.2, 'h': 2.3},
            '16': {'x': 18.9, 'y': 41.85, 'w': 2.2, 'h': 2.3},
            '17': {'x': 35.9, 'y': 40.85, 'w': 2.2, 'h': 2.3},
            '18': {'x': 44.9, 'y': 40.85, 'w': 2.2, 'h': 2.3},
            '14': {'x': 7.9,  'y': 50.85, 'w': 2.2, 'h': 2.3},
            '9':  {'x': 27.9, 'y': 52.9, 'w': 2.2, 'h': 2.3},
            '19': {'x': 57.9,  'y': 43.9,  'w': 2.2, 'h': 2.3},
            '20': {'x': 67.9,  'y': 44.9,  'w': 2.2, 'h': 2.3},
            '21': {'x': 78.9,  'y': 45.9,  'w': 2.2, 'h': 2.3},
            '13': {'x': 7.9,  'y': 60.85, 'w': 2.2, 'h': 2.3},
            '12': {'x': 13.9, 'y': 60.85, 'w': 2.2, 'h': 2.3},
            '11': {'x': 19.9, 'y': 62.85, 'w': 2.2, 'h': 2.3},
            '10': {'x': 25.9, 'y': 60.85, 'w': 2.2, 'h': 2.3},
            '22': {'x': 70.9, 'y': 59.9, 'w': 2.2, 'h': 2.3},
            '23': {'x': 70.5, 'y': 57.8, 'w': 2.2, 'h': 2.3},
        },
    },
    'cc_secondo_piano': {
        'immagine': 'img/cc_secondo_piano.jpg',
        'titolo': 'Corpo Centrale — Torretta (piano secondo)',
        'sede': 'Sede Centrale - Torretta',
        'aule': {
            '24': {'x': 72.9, 'y': 41.85, 'w': 2.2, 'h': 2.3},
            '25': {'x': 70.9, 'y': 46.85, 'w': 2.2, 'h': 2.3},
            '26': {'x': 68.9, 'y': 51.85, 'w': 2.2, 'h': 2.3},
        },
    },
    'ss_sportivo': {
        'immagine': 'img/ss_sportivo.jpg',
        'titolo': 'Sede Staccata — Sportivo',
        'sede': 'Sede Staccata - Sportivo',
        'aule': {
            '33': {'x': 27.0, 'y': 23.5, 'w': 5.0, 'h': 3.0},
            '34': {'x': 26.0, 'y': 37.5, 'w': 5.0, 'h': 3.0},
            '35': {'x': 26.0, 'y': 53.5, 'w': 5.0, 'h': 3.0},
            '36': {'x': 26.0, 'y': 70.5, 'w': 5.0, 'h': 3.0},
        },
    },
    'ss': {
        'immagine': 'img/ss.jpg',
        'titolo': 'Sede Staccata',
        'sede': 'Sede Staccata',
        'aule': {
            '27': {'x': 16.36, 'y': 55.43, 'w': 2.5, 'h': 2.5},
            '28': {'x': 29.25, 'y': 51.60, 'w': 2.5, 'h': 2.5},
            '29': {'x': 42.23, 'y': 45.79, 'w': 2.5, 'h': 2.5},
            '30': {'x': 51.66, 'y': 38.35, 'w': 2.5, 'h': 2.5},
            '31': {'x': 64.9,  'y': 39.9,  'w': 2.2, 'h': 2.3},
            '32': {'x': 76.9,  'y': 39.9,  'w': 2.2, 'h': 2.3},
        },
    },
}
