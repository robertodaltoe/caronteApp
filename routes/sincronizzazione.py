from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db
from models.sync_orario import AliasDocente, LogImportazione
from models.posto_vacante import AliasPostoVacante, OrarioPlaceholder  # noqa: F401 (tabelle per create_all)
from models.docente import Docente
from models.orario_docente import OrarioDocente
from werkzeug.utils import secure_filename
import os, json

sync_bp = Blueprint('sync', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
ALLOWED_EXT   = {'xlsx', 'xlsm'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


# ── PAGINA PRINCIPALE ────────────────────────────────────────

@sync_bp.route('/orario/globale')
def orario_globale():
    from models.orario_docente import OrarioDocente
    from models.docente import Docente
    from models.orario_sostegno import OrarioSostegno
    from collections import defaultdict

    GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato']
    giorno_sel = request.args.get('giorno', 0, type=int)

    slots_giorno = OrarioDocente.query.filter_by(giorno=giorno_sel).all()
    sostegno_giorno = OrarioSostegno.query.filter_by(giorno=giorno_sel).all()

    # Posti vacanti (docenti non ancora nominati): righe in piu' nella
    # stessa griglia, con un "docente virtuale" a id negativo, cosi' il
    # template non cambia. Vedi modules/posti_vacanti.py.
    from types import SimpleNamespace
    from modules.posti_vacanti import posti_collegati, classe_reale
    slots_posti = []
    docenti_virtuali = {}
    for n, p in enumerate(posti_collegati().values(), start=1):
        vid = -n
        docenti_virtuali[vid] = SimpleNamespace(
            id=vid, cognome='◌ ' + p['nome'], ruolo='')
        for r in p['slots']:
            if r.giorno == giorno_sel and r.tipo_ora == 'lezione' and classe_reale(r.classe):
                slots_posti.append(SimpleNamespace(
                    id_docente=vid, giorno=r.giorno, ora=r.ora, classe=r.classe,
                    materia=r.materia, tipo_ora='lezione'))
    slots_giorno = list(slots_giorno) + slots_posti

    classi = sorted(set(
        s.classe for s in slots_giorno
        if s.classe and s.classe not in ('---','-x-','','POTENZIAMENTO')
        and s.classe[0].isdigit()
    ))
    ore_list = sorted(set(s.ora for s in slots_giorno if s.classe in classi))

    # griglia[classe][ora] = lista di slot (supporta compresenze/ITP)
    griglia = defaultdict(lambda: defaultdict(list))
    for s in slots_giorno:
        if s.classe in classi:
            griglia[s.classe][s.ora].append(s)

    # griglia_sostegno[classe][ora] = lista di slot OrarioSostegno,
    # tenuta separata (colore diverso in template, tabella diversa) —
    # il docente di sostegno non compare nel file orario importato.
    griglia_sostegno = defaultdict(lambda: defaultdict(list))
    for s in sostegno_giorno:
        if s.classe in classi:
            griglia_sostegno[s.classe][s.ora].append(s)

    doc_ids = {s.id_docente for s in slots_giorno} | {s.id_docente for s in sostegno_giorno}
    docenti_map = {d.id: d for d in Docente.query.filter(
        Docente.id.in_(doc_ids)).all()}
    docenti_map.update(docenti_virtuali)

    # In una compresenza (due docenti sulla stessa classe/ora) il
    # titolare va sempre mostrato per primo in cella (nome principale),
    # l'ITP per secondo (etichetta "+ cognome" nel template) — senza
    # questo ordinamento esplicito l'ordine dipendeva da quale riga
    # capitava prima nella query (di fatto l'ordine di importazione),
    # scambiando titolare e ITP a caso (Roberto: MAY/STRAMBINI su
    # 3ALLI martedì 4ª ora risultavano invertiti).
    for ore_map in griglia.values():
        for slots in ore_map.values():
            if len(slots) > 1:
                slots.sort(key=lambda s: (
                    docenti_map[s.id_docente].ruolo == 'itp'
                    if s.id_docente in docenti_map else False
                ))

    giorni_con_orario = sorted(set(
        r[0] for r in OrarioDocente.query
        .with_entities(OrarioDocente.giorno).distinct().all()
        if r[0] is not None
    ) | {r.giorno for p in posti_collegati().values() for r in p['slots']})

    return render_template('orario_globale.html',
        classi=classi,
        ore_list=ore_list,
        griglia=griglia,
        griglia_sostegno=griglia_sostegno,
        docenti_map=docenti_map,
        giorno_sel=giorno_sel,
        giorni_con_orario=giorni_con_orario,
        giorni_nomi=GIORNI,
    )

@sync_bp.route('/sincronizzazione')
def index():
    logs  = LogImportazione.query.order_by(LogImportazione.data_ora.desc()).limit(10).all()
    alias = AliasDocente.query.order_by(AliasDocente.nome_file).all()
    docenti = Docente.query.filter_by(attivo=True).order_by(Docente.cognome).all()

    # File orario attuale in data/
    file_corrente = None
    for f in os.listdir(UPLOAD_FOLDER):
        if f.endswith(('.xlsx', '.xlsm')) and 'ORARIO' in f.upper():
            file_corrente = f
            break

    # Statistiche orario attuale
    slot_count = OrarioDocente.query.count()
    doc_con_orario = db.session.query(
        OrarioDocente.id_docente
    ).distinct().count()

    from modules.posti_vacanti import posti_collegati, nomi_in_attesa
    from models.assegnazione import AssegnazioneDocente
    from config_anno import get_anno_corrente
    placeholder_disponibili = AssegnazioneDocente.query.filter(
        AssegnazioneDocente.anno_scol == get_anno_corrente(),
        AssegnazioneDocente.id_docente.is_(None)).order_by(
        AssegnazioneDocente.nome_placeholder).all()

    return render_template('sincronizzazione.html',
        posti=list(posti_collegati().values()), in_attesa=nomi_in_attesa(),
        placeholder_disponibili=placeholder_disponibili,
        logs=logs, alias=alias, docenti=docenti,
        file_corrente=file_corrente,
        slot_count=slot_count,
        doc_con_orario=doc_con_orario,
    )


# ── UPLOAD + IMPORTA ─────────────────────────────────────────
@sync_bp.route('/sincronizzazione/importa', methods=['POST'])
def importa():
    from modules.parser_orario import applica_importazione

    # Usa file caricato o quello già presente
    file_path = None

    if 'file_orario' in request.files:
        f = request.files['file_orario']
        if f and f.filename and allowed_file(f.filename):
            filename = secure_filename(f.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            f.save(file_path)

    if not file_path:
        # Cerca file già presente
        for fn in os.listdir(UPLOAD_FOLDER):
            if fn.endswith(('.xlsx', '.xlsm')) and 'ORARIO' in fn.upper():
                file_path = os.path.join(UPLOAD_FOLDER, fn)
                break

    if not file_path or not os.path.exists(file_path):
        flash('Nessun file orario trovato. Carica un file .xlsx/.xlsm.', 'error')
        return redirect(url_for('sync.index'))

    from datetime import date, datetime
    data_inizio_validita = data_fine_validita = None
    v_ini_raw = request.form.get('data_inizio_validita', '').strip()
    v_fine_raw = request.form.get('data_fine_validita', '').strip()
    if v_ini_raw:
        data_inizio_validita = datetime.strptime(v_ini_raw, '%Y-%m-%d').date()
    if v_fine_raw:
        data_fine_validita = datetime.strptime(v_fine_raw, '%Y-%m-%d').date()
    if data_inizio_validita and data_fine_validita and data_inizio_validita > data_fine_validita:
        flash('La data di inizio validità non può essere successiva alla data di fine.', 'error')
        return redirect(url_for('sync.index'))

    try:
        stats = applica_importazione(
            file_path, db.session,
            data_inizio_validita=data_inizio_validita,
            data_fine_validita=data_fine_validita,
        )
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante l\'importazione: {e}', 'error')
        return redirect(url_for('sync.index'))

    msg = (f'Orario aggiornato: {stats["slot_totali"]} slot, '
           f'{stats["docenti_nuovi"]} docenti nuovi.')

    if data_inizio_validita or data_fine_validita:
        from modules.assenze_registrazione import ricalcola_supplenze_periodo
        # Ricalcolo su tutto il periodo indicato (se un solo estremo è
        # dato, ricalcola comunque solo entro quell'estremo sull'altro
        # lato aperto -- qui serve un intervallo concreto: se manca un
        # estremo si usa oggi/fra un anno come bordo pratico).
        d_ini = data_inizio_validita or date.today()
        d_fine = data_fine_validita or (d_ini.replace(year=d_ini.year + 1))
        esito = ricalcola_supplenze_periodo(d_ini, d_fine)
        if esito['create'] or esito['cancellate']:
            msg += (f' Supplenze ricalcolate nel periodo indicato: '
                    f'{esito["create"]} aggiunte, {esito["cancellate"]} rimosse perché non più coerenti col nuovo orario.')
        if esito['da_rivedere']:
            righe = '; '.join(
                f'{r["docente"]} {r["data"]} ora {r["ora"]} cl.{r["classe"]}'
                for r in esito['da_rivedere'][:10]
            )
            altro = f' e altre {len(esito["da_rivedere"]) - 10}' if len(esito['da_rivedere']) > 10 else ''
            flash(f'⚠︎ {len(esito["da_rivedere"])} supplenza/e in un giorno precedente a oggi '
                  f'non è più coerente col nuovo orario ma NON è stata toccata (verifica a mano): '
                  f'{righe}{altro}.', 'warning')
    else:
        from modules.assenze_registrazione import rigenera_supplenze_mancanti
        supplenze_rigenerate = rigenera_supplenze_mancanti(data_da=date.today())
        if supplenze_rigenerate:
            msg += (f' {supplenze_rigenerate} supplenz{"a" if supplenze_rigenerate == 1 else "e"} '
                    f'da assegnare generat{"a" if supplenze_rigenerate == 1 else "e"} per assenze '
                    f'già registrate che risultano ora coperte dal nuovo orario.')

    from modules.posti_vacanti import ricalcola_supplenze_posti, posti_collegati
    esito_posti = ricalcola_supplenze_posti()
    if esito_posti['create'] or esito_posti['cancellate']:
        msg += (f' Posti vacanti: {esito_posti["create"]} supplenze da assegnare '
                f'aggiunte, {esito_posti["cancellate"]} rimosse.')

    if stats['non_riconosciuti']:
        nr = ', '.join(stats['non_riconosciuti'])
        flash(msg, 'warning')
        flash(f'⚠︎ Nomi non riconosciuti: {nr}. Se sono docenti non ancora nominati '
              f'collegali a un posto vacante qui sotto; se sono docenti veri aggiungi un alias.',
              'warning')
    else:
        flash(msg, 'success')

    # Le riunioni pomeridiane (Consigli di classe/scrutini) vengono
    # programmate dalle Assegnazioni, ben prima che l'orario reale sia
    # disponibile — appena l'orario arriva potrebbe smentirne qualcuna
    # (un docente coinvolto ha in realtà lezione in quell'ora). Segnala
    # subito qui, invece di scoprirlo solo per caso — richiesto da
    # Roberto. Solo le riunioni da oggi in poi: quelle passate sono
    # ormai storia, non serve segnalarle.
    from datetime import date
    from modules.verifica_orario_riunioni import trova_conflitti_orario_riunioni
    conflitti = trova_conflitti_orario_riunioni(data_da=date.today())
    if conflitti:
        flash(f'⚠︎ {len(conflitti)} conflitt{"o" if len(conflitti) == 1 else "i"} tra '
              f'l\'orario appena importato e riunioni già programmate — vedi '
              f'"Genera piano delle attività" → "Verifica conflitti orario".',
              'warning')

    return redirect(url_for('sync.index'))


# ── GESTIONE ALIAS ───────────────────────────────────────────
@sync_bp.route('/sincronizzazione/alias/nuovo', methods=['POST'])
def nuovo_alias():
    nome_file  = request.form.get('nome_file', '').strip().upper()
    id_docente = request.form.get('id_docente', type=int)

    if not nome_file or not id_docente:
        flash('Compila entrambi i campi.', 'warning')
        return redirect(url_for('sync.index'))

    esistente = AliasDocente.query.filter_by(nome_file=nome_file).first()
    if esistente:
        esistente.id_docente = id_docente
        flash(f'Alias "{nome_file}" aggiornato.', 'success')
    else:
        a = AliasDocente(nome_file=nome_file, id_docente=id_docente)
        db.session.add(a)
        flash(f'Alias "{nome_file}" creato.', 'success')

    db.session.commit()
    return redirect(url_for('sync.index'))


@sync_bp.route('/sincronizzazione/alias/<int:id>/elimina', methods=['POST'])
def elimina_alias(id):
    a = AliasDocente.query.get_or_404(id)
    db.session.delete(a)
    db.session.commit()
    flash(f'Alias "{a.nome_file}" eliminato.', 'warning')
    return redirect(url_for('sync.index'))


# ── POSTI VACANTI (docenti non ancora nominati) ──────────────

@sync_bp.route('/sincronizzazione/posti/collega', methods=['POST'])
def posto_collega():
    from modules.posti_vacanti import collega_nome, ricalcola_supplenze_posti
    nome = (request.form.get('nome_file') or '').strip()
    scelta = request.form.get('scelta') or ''
    if not nome or not (scelta in ('nuovo', 'ignora') or scelta.startswith('asg:')):
        flash('Scegli cosa fare con questo nome.', 'warning')
        return redirect(url_for('sync.index'))
    collega_nome(nome, scelta)
    esito = ricalcola_supplenze_posti()
    if scelta == 'ignora':
        flash(f'"{nome}" ignorato nei prossimi import.', 'success')
    else:
        flash(f'"{nome}" collegato a un posto vacante: {esito["create"]} supplenze '
              f'da assegnare create da oggi.', 'success')
    return redirect(url_for('sync.index'))


@sync_bp.route('/sincronizzazione/posti/<int:id>/scollega', methods=['POST'])
def posto_scollega(id):
    from models.posto_vacante import AliasPostoVacante
    from modules.posti_vacanti import ricalcola_supplenze_posti
    a = db.session.get(AliasPostoVacante, id)
    if a:
        nome = a.nome_file
        db.session.delete(a)
        db.session.commit()
        esito = ricalcola_supplenze_posti()
        flash(f'"{nome}" scollegato ({esito["cancellate"]} supplenze rimosse).', 'warning')
    return redirect(url_for('sync.index'))


@sync_bp.route('/sincronizzazione/posti/nomina', methods=['POST'])
def posto_nomina():
    from modules.posti_vacanti import nomina_posto
    chiave = request.form.get('chiave') or ''
    id_doc = request.form.get('id_docente', type=int)
    doc = db.session.get(Docente, id_doc) if id_doc else None
    if not chiave or not doc:
        flash('Scegli il docente da nominare.', 'warning')
        return redirect(url_for('sync.index'))
    esito = nomina_posto(chiave, doc.id)
    if chiave.startswith('A'):
        from models.assegnazione import AssegnazioneDocente
        asg = db.session.get(AssegnazioneDocente, int(chiave[1:]))
        if asg and asg.id_docente is None:
            asg.id_docente, asg.nome_placeholder = doc.id, None
            db.session.commit()
    flash(f'{doc.cognome} nominato: {esito["ore"]} ore nel suo orario, '
          f'{esito["supplenze_cancellate"]} supplenze del posto cancellate.', 'success')
    return redirect(url_for('sync.index'))
