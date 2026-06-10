from models import db
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# CATEGORIE ASSENZE
# Tuple: (label_pubblica, impatta_banca, colonna_banca,
#         genera_supplenza, assegnabile,
#         limite_tipo, limite_valore, limite_unita)
#
# limite_tipo: None | 'giorni_anno' | 'ore_giorno' | 'giorni_consecutivi'
# limite_valore: numero limite (None = nessuno)
# limite_unita: 'giorni' | 'ore' | None
# ─────────────────────────────────────────────────────────────
CATEGORIE = {

    # ── Impatta banca ore ────────────────────────────────────
    'permesso_orario': (
        'Permesso orario',
        True, 'permesso_orario', True, True,
        'ore_giorno', 2, 'ore'          # CCNL: max 2h/giorno (TD)
    ),
    'ed_civica': (
        'Ed. Civica',
        True, 'civica', True, True,
        None, None, None
    ),

    # ── Assenze — nessun impatto banca ore ──────────────────
    'malattia': (
        'Assenza',
        False, None, True, True,
        None, None, None
    ),
    'permesso_personale': (
        'Assenza',
        False, None, True, True,
        'giorni_anno', 3, 'giorni'      # CCNL: 3 gg TD / 3+6 TI
    ),
    'lutto': (
        'Assenza',
        False, None, True, True,
        'giorni_anno', 3, 'giorni'      # CCNL: 3 gg, collegati all'evento
    ),
    'matrimonio': (
        'Assenza',
        False, None, True, True,
        'giorni_consecutivi', 15, 'giorni'  # CCNL: 15 gg consecutivi
    ),
    'permesso_sindacale': (
        'Assenza',
        False, None, True, True,
        None, None, None
    ),
    'formazione': (
        'Formazione',
        False, None, True, True,
        'giorni_anno', 5, 'giorni'      # CCNL: 5 gg/anno (docenti)
    ),
    'attivita_istituzionale': (
        'Attività istituzionale',
        False, None, True, True,
        None, None, None
    ),

    # ── Classe libera — NON assegnabile ─────────────────────
    # (usato anche con flag classe_libera su altri tipi)
    'classe_libera': (
        'Classe libera',
        False, None, True, False,
        None, None, None
    ),

    # ── Ferie ───────────────────────────────────────────────
    'ferie': (
        'Ferie',
        False, None, False, False,      # sostituto nominato, no supplenza automatica
        'giorni_anno', 6, 'giorni'      # CCNL: max 6 gg fuori sospensione didattica
    ),

    # ── Compatibilità con categorie vecchie ─────────────────
    'permesso_retribuito': (
        'Assenza',
        False, None, True, True,
        None, None, None
    ),
    'assemblea': (
        'Assenza',
        False, None, True, True,
        None, None, None
    ),
    'sciopero': (
        'Assenza',
        False, None, True, False,
        None, None, None
    ),
    'viaggio': (
        'Attività istituzionale',
        False, None, True, True,
        None, None, None
    ),
    'progetto': (
        'Attività istituzionale',
        False, None, True, True,
        None, None, None
    ),
    'riunione': (
        'Attività istituzionale',
        False, None, True, True,
        None, None, None
    ),
    'sorveglianza_prove': (
        'Attività istituzionale',
        False, None, True, True,
        None, None, None
    ),
    'simulazione_esame': (
        'Attività istituzionale',
        False, None, True, True,
        None, None, None
    ),
    'attivita_alternativa': (
        'Attività istituzionale',
        False, None, True, True,
        None, None, None
    ),
}

# Categorie visibili nel form (ordine di visualizzazione)
CATEGORIE_FORM = [
    ('assenze', 'Assenze', [
        'malattia', 'permesso_personale', 'lutto', 'matrimonio',
        'permesso_sindacale',
    ]),
    ('orario', 'Variazioni orario', [
        'permesso_orario', 'ferie', 'classe_libera',
    ]),
    ('attivita', 'Attività', [
        'ed_civica', 'formazione', 'attivita_istituzionale',
    ]),
]

# Etichette per il form (motivo interno — visibile solo DS/DSGA)
LABEL_INTERNE = {
    'malattia':              '🤒 Malattia',
    'permesso_personale':    '📄 Permesso personale / familiare',
    'lutto':                 '🕯 Lutto',
    'matrimonio':            '💍 Matrimonio',
    'permesso_sindacale':    '🗣 Permesso sindacale',
    'permesso_orario':       '📋 Permesso orario',
    'ferie':                 '🏖 Ferie',
    'classe_libera':         '🚫 Classe libera (sciopero / altro)',
    'ed_civica':             '📚 Ed. Civica',
    'formazione':            '🎓 Formazione',
    'attivita_istituzionale':'🏫 Attività istituzionale',
    # vecchie (compatibilità)
    'permesso_retribuito':   '📄 Permesso retribuito (L.104)',
    'assemblea':             '🗣 Assemblea',
    'sciopero':              '✊ Sciopero',
    'viaggio':               '✈ Viaggio istruzione',
    'progetto':              '📐 Progetto',
    'riunione':              '🏫 Riunione',
}

# Limiti CCNL per alert — { motivo: (descrizione, valore, unita) }
LIMITI_CCNL = {
    'permesso_personale': {
        'TD':  (3,  'giorni', 'Art.35 c.12 CCNL 2019/21 — 3 gg/anno (TD)'),
        'TI':  (9,  'giorni', 'Art.15 c.2 CCNL — 3+6 gg/anno (TI)'),
    },
    'lutto':      {'*': (3,  'giorni', 'Art.35 c.8 CCNL — 3 gg collegati all\'evento')},
    'matrimonio': {'*': (15, 'giorni', 'Art.35 c.8 CCNL — 15 gg consecutivi')},
    'formazione': {'*': (5,  'giorni', 'Art.36 CCNL — 5 gg/anno per formazione')},
    'permesso_orario': {'*': (2, 'ore', 'CCNL — max 2h/giorno, recupero entro 2 mesi')},
    # permesso_ist: ore prese su attività istituzionali — stesso limite,
    # sommato al permesso_orario per il controllo 2h/giorno
    'permesso_ist':    {'*': (2, 'ore', 'CCNL — max 2h/giorno (include permesso orario lezioni)')},
    'ferie':      {'*': (6,  'giorni', 'Art.13 CCNL — max 6 gg fuori sospensione didattica')},
}


def cat_label(motivo):
    return CATEGORIE.get(motivo, (motivo,))[0]

def cat_label_interna(motivo):
    return LABEL_INTERNE.get(motivo, motivo)

def cat_impatta_banca(motivo):
    return CATEGORIE.get(motivo, ('', False, None, True, True, None, None, None))[1]

def cat_colonna_banca(motivo):
    return CATEGORIE.get(motivo, ('', False, None, True, True, None, None, None))[2]

def cat_genera_supplenza(motivo):
    return CATEGORIE.get(motivo, ('', False, None, True, True, None, None, None))[3]

def cat_assegnabile(motivo):
    return CATEGORIE.get(motivo, ('', False, None, True, True, None, None, None))[4]

def cat_limite(motivo):
    """Restituisce (tipo, valore, unita) o (None,None,None)."""
    c = CATEGORIE.get(motivo)
    if c and len(c) >= 8:
        return c[5], c[6], c[7]
    return None, None, None


class Assenza(db.Model):
    __tablename__ = 'assenze'

    id             = db.Column(db.Integer, primary_key=True)
    id_docente     = db.Column(db.Integer, db.ForeignKey('docenti.id'),
                               nullable=False, index=True)
    data           = db.Column(db.Date,    nullable=False, index=True)
    ora_inizio     = db.Column(db.Integer, default=1)
    ora_fine       = db.Column(db.Integer, default=9)
    motivo         = db.Column(db.String(50), default='malattia')
    # Motivo interno — visibile solo a DS/DSGA (stesso valore di motivo
    # per le categorie già private; campo separato per futura granularità)
    motivo_interno = db.Column(db.String(200), nullable=True)
    # Flag: la classe non riceve sostituto, entra dopo / esce prima
    classe_libera  = db.Column(db.Boolean, default=False)
    note_interne   = db.Column(db.Text)
    creato_il      = db.Column(db.DateTime, default=datetime.utcnow)
    # Permesso orario per attività istituzionali — orario assoluto HH:MM
    ora_ist_inizio = db.Column(db.String(5), nullable=True)   # es. '14:00'
    ora_ist_fine   = db.Column(db.String(5), nullable=True)   # es. '16:00'

    @property
    def impatta_banca_ore(self):
        return cat_impatta_banca(self.motivo)

    @property
    def colonna_banca_ore(self):
        return cat_colonna_banca(self.motivo)

    @property
    def genera_supplenza(self):
        return cat_genera_supplenza(self.motivo)

    @property
    def assegnabile(self):
        if self.classe_libera:
            return False
        return cat_assegnabile(self.motivo)

    @property
    def label_motivo(self):
        return cat_label(self.motivo)

    @property
    def n_ore(self):
        return max(1, self.ora_fine - self.ora_inizio + 1)

    def __repr__(self):
        return f"<Assenza doc:{self.id_docente} {self.data} {self.motivo}>"
