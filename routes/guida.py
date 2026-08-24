"""
Sezione "Guida" — FAQ e manuali d'uso, consultabili come pagine HTML
interattive e scaricabili come PDF per sezione. Il contenuto vive in
modules/guida_content.py: qui ci sono solo le route che lo mostrano.

Accessibile a chiunque sia loggato, senza permesso specifico (non è
in BLUEPRINT_PERMESSI in app.py) — è pensata per aiutare TUTTI gli
utenti dell'app, non solo un ruolo.
"""
import io
from flask import Blueprint, render_template, abort, send_file, request
from modules.guida_content import SEZIONI, get_sezione, cerca

guida_bp = Blueprint('guida', __name__)


@guida_bp.route('/guida')
def index():
    return render_template('guida/index.html', sezioni=SEZIONI, query=None, risultati=None)


@guida_bp.route('/guida/cerca')
def cerca_guida():
    query = request.args.get('q', '').strip()
    risultati = cerca(query) if query else None
    return render_template('guida/index.html', sezioni=SEZIONI,
                            query=query, risultati=risultati)


@guida_bp.route('/guida/<slug>')
def sezione(slug):
    sez = get_sezione(slug)
    if not sez:
        abort(404)
    return render_template('guida/sezione.html', sez=sez, sezioni=SEZIONI)


@guida_bp.route('/guida/<slug>/pdf')
def sezione_pdf(slug):
    sez = get_sezione(slug)
    if not sez:
        abort(404)

    html_content = render_template('guida/pdf_sezione.html', sez=sez)

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html_content).write_pdf()
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'guida_{slug}.pdf'
        )
    except ImportError:
        # Ambiente senza WeasyPrint (es. sviluppo locale non completo):
        # mostra comunque il contenuto stampabile in HTML come fallback,
        # invece di rompere la pagina con un errore 500.
        return html_content
