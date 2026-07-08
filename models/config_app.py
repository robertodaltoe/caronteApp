"""
Tabella di configurazione generale dell'app — chiave/valore.
Usata per anno_scol_corrente e altri parametri globali.
"""
from models import db


class ConfigApp(db.Model):
    __tablename__ = 'config_app'

    id     = db.Column(db.Integer, primary_key=True)
    chiave = db.Column(db.String(60), nullable=False, unique=True)
    valore = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f'<ConfigApp {self.chiave}={self.valore}>'
