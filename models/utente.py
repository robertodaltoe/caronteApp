"""models/utente.py — Utenti con ruolo per accesso multi-livello."""
from models import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

RUOLI = {
    'ds':              'Dirigente Scolastico',
    'dsga':            'DSGA',
    'collaboratore':   'Collaboratore DS',
    'segreteria':      'Segreteria Personale',
    'display':         'Display (sola lettura)',
}

# Permessi per ruolo
# Suffisso '_r' = sola lettura, senza suffisso = lettura+scrittura
PERMESSI = {
    'ds': {
        'gestione_utenti', 'log',
        'report',
        'supplenze_r',          # legge le supplenze, non le modifica
        'banca_ore_r',          # legge la banca ore
        'docenti_r',            # legge i docenti
        'recupero_r',           # legge corsi/prove di recupero, rientro dall'estero
        'organico_r',           # legge classi di concorso e organico diritto/fatto
        'display',
    },
    'dsga': {
        'tutto',                # accesso completo tranne gestione utenti e log
        'report', 'supplenze', 'banca_ore', 'docenti', 'display',
        'orario', 'aule', 'assenze', 'attivita',
    },
    'collaboratore': {
        'supplenze',            # assegna e gestisce supplenze
        'assenze',              # inserisce assenze (se necessario)
        'attivita',             # vede/gestisce progetti e uscite
        'indisponibilita',      # gestisce indisponibilità
        'recupero',             # corsi/prove di recupero, rientro dall'estero
        'banca_ore_r',          # vede banca ore in sola lettura
        'report_r',             # vede report in sola lettura
        'docenti_r',            # vede anagrafica docenti
        'orario_r',             # vede orario
        'aule_r',               # vede aule
        'organico_r',           # vede classi di concorso e organico diritto/fatto
        'display',
    },
    'segreteria': {
        'supplenze_r',          # vede le supplenze (non assegna)
        'assenze',              # inserisce assenze docenti
        'attivita',             # inserisce progetti, uscite, viaggi
        'recupero',             # corsi/prove di recupero, rientro dall'estero
        'banca_ore',            # gestisce banca ore e pagamenti
        'report',               # accede ai report
        'docenti_r',            # vede anagrafica
        'aule_r',               # vede le aule
        'display',
    },
    'display': {
        'display',
    },
}


class Utente(db.Model):
    __tablename__ = 'utenti'

    id          = db.Column(db.Integer, primary_key=True)
    username    = db.Column(db.String(50), nullable=False, unique=True)
    cognome     = db.Column(db.String(80), nullable=False, default='')
    nome        = db.Column(db.String(80), nullable=False, default='')
    ruolo       = db.Column(db.String(20), nullable=False, default='segreteria')
    pin_hash    = db.Column(db.String(256), nullable=False)
    attivo      = db.Column(db.Boolean, default=True)
    creato_il   = db.Column(db.DateTime, default=datetime.utcnow)
    ultimo_accesso = db.Column(db.DateTime)

    @property
    def nome_completo(self):
        return f'{self.cognome} {self.nome}'.strip() or self.username

    def set_pin(self, pin):
        self.pin_hash = generate_password_hash(str(pin))

    def check_pin(self, pin):
        return check_password_hash(self.pin_hash, str(pin))

    def ha_permesso(self, permesso):
        perms = PERMESSI.get(self.ruolo, set())
        if 'tutto' in perms:
            return True
        if permesso in perms:
            return True
        # Chi ha permesso di scrittura ha implicitamente anche lettura
        # es. 'banca_ore' implica 'banca_ore_r'
        if permesso.endswith('_r'):
            base = permesso[:-2]  # rimuovi '_r'
            return base in perms
        return False

    @property
    def ruolo_label(self):
        return RUOLI.get(self.ruolo, self.ruolo)

    def __repr__(self):
        return f'<Utente {self.username} ({self.ruolo})>'
