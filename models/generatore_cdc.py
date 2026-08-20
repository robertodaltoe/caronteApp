"""
Generatore Consigli di Classe — Piano Annuale delle Attività, Fase 3.

Due tabelle di vincoli, entrambe lette dal generatore prima di produrre
una bozza (mai un piano imposto — stesso principio di ogni altro
generatore già in app, es. genera_bozza_agosto):

- VincoloOrarioClasse: finestre settimanali fisse in cui un gruppo di
  indirizzi/classi NON è libero da lezione (es. martedì 13:30-15:30
  rientro pomeridiano CAT/AFM/ROM) — dato di calendario, non legato
  a un anno scolastico specifico, tipicamente stabile.
- VincoloGeneratoreCdc: vincoli manuali per una singola generazione
  (es. "il CdC della 5A entro il 20"), impostabili PRIMA di generare —
  confermato necessario con Roberto, non solo correzione a posteriori.
"""
from models import db


GIORNI_SETTIMANA = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato']

TIPI_VINCOLO_CDC = {
    'entro_data': 'Da fare entro una data',
    'fissa':      'Slot fisso (data e ora esatte)',
}


class VincoloOrarioClasse(db.Model):
    __tablename__ = 'vincoli_orario_classe'

    id              = db.Column(db.Integer, primary_key=True)
    giorno_settimana= db.Column(db.Integer, nullable=False)  # 0=lunedì .. 5=sabato
    ora_inizio      = db.Column(db.String(5), nullable=False)  # 'HH:MM'
    ora_fine        = db.Column(db.String(5), nullable=False)
    indirizzi       = db.Column(db.String(120), nullable=False)  # 'CAT,AFM,ROM'
    anno_corso_min  = db.Column(db.Integer, nullable=True)  # None = tutti gli anni
    anno_corso_max  = db.Column(db.Integer, nullable=True)
    descrizione     = db.Column(db.String(200), nullable=True)

    @property
    def indirizzi_list(self):
        return [i.strip() for i in self.indirizzi.split(',') if i.strip()]

    @property
    def giorno_label(self):
        return GIORNI_SETTIMANA[self.giorno_settimana] if 0 <= self.giorno_settimana <= 5 else '?'

    def si_applica_a(self, indirizzo, anno_corso):
        if indirizzo not in self.indirizzi_list:
            return False
        if self.anno_corso_min is not None and anno_corso < self.anno_corso_min:
            return False
        if self.anno_corso_max is not None and anno_corso > self.anno_corso_max:
            return False
        return True

    def __repr__(self):
        return (f'<VincoloOrarioClasse {self.giorno_label} {self.ora_inizio}-{self.ora_fine} '
                f'{self.indirizzi}>')


class VincoloGeneratoreCdc(db.Model):
    __tablename__ = 'vincoli_generatore_cdc'

    id          = db.Column(db.Integer, primary_key=True)
    anno_scol   = db.Column(db.String(9), nullable=False, index=True)
    classe      = db.Column(db.String(20), nullable=False)  # es. '3A LLI'
    tipo        = db.Column(db.String(20), nullable=False, default='entro_data')
    scadenza    = db.Column(db.Date, nullable=True)   # per tipo='entro_data'
    data_fissa  = db.Column(db.Date, nullable=True)   # per tipo='fissa'
    ora_fissa   = db.Column(db.String(5), nullable=True)
    note        = db.Column(db.String(200), nullable=True)

    @property
    def tipo_label(self):
        return TIPI_VINCOLO_CDC.get(self.tipo, self.tipo)

    def __repr__(self):
        return f'<VincoloGeneratoreCdc {self.classe} {self.tipo}>'
