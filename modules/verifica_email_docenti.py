"""modules/verifica_email_docenti.py — confronto tra l'elenco utenti della
console Workspace (CSV) e l'anagrafica docenti.

Logica pura: legge il CSV e produce le categorie da mostrare; non scrive
nulla. La scrittura (solo righe scelte da una persona, con anteprima) sta
in routes/docenti.py::verifica_email_applica.

Regola di CLAUDE.md: i casi ambigui (omonimi, due account per un docente,
stessa email su due docenti, email abbinata a un nome diverso) vengono
solo segnalati, mai proposti per la correzione.
"""
import csv
import io
import re
import unicodedata


class ErroreCsv(ValueError):
    """Il file non è un elenco utenti leggibile."""


EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

# Nomi di colonna accettati (dopo normalizzazione: minuscolo, senza "[Required]").
_COLONNE = {
    'nome':    ('first name', 'nome', 'given name'),
    'cognome': ('last name', 'cognome', 'family name'),
    'email':   ('email address', 'email', 'indirizzo email', 'e-mail',
                'primary email', 'indirizzo e-mail'),
    'stato':   ('status', 'stato'),
    'ou':      ('org unit path', 'unita organizzativa', 'unità organizzativa'),
}


def normalizza(testo):
    """Minuscolo, senza accenti né apostrofi; trattini e punti come spazi."""
    if not testo:
        return ''
    t = unicodedata.normalize('NFKD', str(testo))
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[’'`´]", '', t)
    t = re.sub(r'[-_.]+', ' ', t)
    return re.sub(r'\s+', ' ', t).strip().lower()


def _token(testo):
    return tuple(sorted(normalizza(testo).split()))


def email_pulita(valore):
    """Email in minuscolo; vuoto per None / '' / la stringa 'None' (vecchi dati)."""
    v = (valore or '').strip().lower()
    return '' if v == 'none' else v


def _decodifica(raw):
    for codifica in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            return raw.decode(codifica)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'replace')


def _intestazione(nome_colonna):
    n = re.sub(r'\[.*?\]', '', nome_colonna or '').strip().lower()
    for chiave, varianti in _COLONNE.items():
        if n in varianti:
            return chiave
    return None


def leggi_csv(raw):
    """CSV (bytes) -> lista di dict nome/cognome/email/stato/ou.
    Ignora le righe senza una email valida."""
    if not raw or not raw.strip():
        raise ErroreCsv('Il file è vuoto.')
    testo = _decodifica(raw)
    prima = testo.splitlines()[0] if testo.splitlines() else ''
    delimitatore = ';' if prima.count(';') > prima.count(',') else ','
    lettore = csv.reader(io.StringIO(testo), delimiter=delimitatore)
    righe = list(lettore)
    if not righe:
        raise ErroreCsv('Il file è vuoto.')
    colonne = {}
    for i, nome_colonna in enumerate(righe[0]):
        chiave = _intestazione(nome_colonna)
        if chiave and chiave not in colonne:
            colonne[chiave] = i
    if 'email' not in colonne:
        raise ErroreCsv('Manca la colonna con l\'indirizzo email '
                        '(es. "Email Address [Required]").')

    def cella(riga, chiave):
        i = colonne.get(chiave)
        return riga[i].strip() if i is not None and i < len(riga) else ''

    utenti = []
    for riga in righe[1:]:
        email = cella(riga, 'email').lower()
        if not EMAIL_RE.match(email):
            continue
        utenti.append({'nome': cella(riga, 'nome'), 'cognome': cella(riga, 'cognome'),
                       'email': email, 'stato': cella(riga, 'stato'),
                       'ou': cella(riga, 'ou')})
    return utenti


def _sospeso(utente):
    return utente['stato'].strip().lower().startswith(('susp', 'sosp'))


def confronta(utenti, docenti):
    """Abbina gli utenti Workspace ai docenti e ritorna le categorie."""
    esito = {k: [] for k in (
        'ok', 'da_impostare', 'differenti', 'nome_diverso', 'ambigui',
        'sospesi_con_docente_attivo', 'account_attivo_docente_inattivo',
        'docenti_senza_account', 'account_senza_docente')}

    per_email, per_nome = {}, {}
    for d in docenti:
        e = email_pulita(d.email)
        if e:
            per_email.setdefault(e, []).append(d)
        per_nome.setdefault(_token(f'{d.cognome} {d.nome}'), []).append(d)

    def candidati(u):
        """(docenti candidati, criterio di abbinamento)."""
        if u['email'] in per_email:
            return per_email[u['email']], 'email'
        trovati = per_nome.get(_token(f"{u['cognome']} {u['nome']}"), [])
        if trovati:
            return trovati, 'nome'
        parte_locale = u['email'].split('@')[0]
        if re.search(r'\d', parte_locale):
            return [], None
        trovati = per_nome.get(_token(parte_locale), [])
        return trovati, 'email_nome' if trovati else None

    abbinati = []     # (utente, docente, criterio)
    coinvolti = set() # id dei docenti toccati da un caso ambiguo o abbinati
    for u in utenti:
        cand, criterio = candidati(u)
        if not cand:
            esito['account_senza_docente'].append(u)
        elif len(cand) > 1:
            esito['ambigui'].append({'utente': u, 'docenti': list(cand), 'utenti': [u]})
            coinvolti.update(d.id for d in cand)
        else:
            abbinati.append((u, cand[0], criterio))

    # Un docente abbinato a più account: ambiguo, nessuna proposta.
    utenti_per_docente = {}
    for u, d, _ in abbinati:
        utenti_per_docente.setdefault(d.id, []).append(u)
    gia_ambigui = set()
    for u, d, criterio in abbinati:
        coinvolti.add(d.id)
        if len(utenti_per_docente[d.id]) > 1:
            if d.id not in gia_ambigui:
                gia_ambigui.add(d.id)
                esito['ambigui'].append({'utente': u, 'docenti': [d],
                                         'utenti': utenti_per_docente[d.id]})
            continue
        if not d.attivo:
            if not _sospeso(u):
                esito['account_attivo_docente_inattivo'].append({'docente': d, 'utente': u})
            continue
        if _sospeso(u):
            esito['sospesi_con_docente_attivo'].append({'docente': d, 'utente': u})
            continue
        attuale = email_pulita(d.email)
        voce = {'docente': d, 'utente': u, 'email_attuale': attuale,
                'email_nuova': u['email']}
        if criterio == 'email' and _token(f'{d.cognome} {d.nome}') != _token(
                f"{u['cognome']} {u['nome']}"):
            voce['stesso_nome'] = per_nome.get(_token(f"{u['cognome']} {u['nome']}"), [])
            esito['nome_diverso'].append(voce)
        elif attuale == u['email']:
            esito['ok'].append(voce)
        elif not attuale:
            esito['da_impostare'].append(voce)
        else:
            esito['differenti'].append(voce)

    # La stessa email scritta su più docenti, senza account che li aggancia.
    for e, lista in per_email.items():
        if len(lista) > 1 and not any(x['utente']['email'] == e for x in esito['ambigui']):
            coinvolti.update(d.id for d in lista)
            esito['ambigui'].append({'utente': None, 'docenti': list(lista), 'utenti': [],
                                     'email': e})

    esito['docenti_senza_account'] = sorted(
        (d for d in docenti if d.attivo and d.id not in coinvolti),
        key=lambda d: (d.cognome or '', d.nome or ''))
    return esito
