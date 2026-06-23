"""
Hub "Attività Differite": punto di ingresso unico per le attività
scolastiche che si svolgono fuori dal calendario ordinario — corsi/esami
di recupero, colloqui di rientro dall'estero e, in futuro, esami
integrativi per passaggi e trasferimenti di settembre.
"""
from flask import Blueprint, render_template

att_differite_bp = Blueprint('att_differite', __name__)


@att_differite_bp.route('/att-differite')
def index():
    return render_template('att_differite/index.html')
