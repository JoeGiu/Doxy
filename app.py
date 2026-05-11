# app.py - Applicazione Flask per la gestione dati Doxy
import os
import uuid
from functools import wraps
from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import pymysql

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Secret key — legge da env, fallback al valore di sviluppo locale
app.secret_key = os.environ.get('SECRET_KEY', 'doxy-secret-key-2024')

# Configurazione connessione al database MySQL (env vars con fallback locali)
DB_CONFIG = {
    'host':     os.environ.get('MYSQL_HOST',     'localhost'),
    'port':     int(os.environ.get('MYSQL_PORT', 3306)),
    'database': os.environ.get('MYSQL_DATABASE', 'doxy_db'),
    'user':     os.environ.get('MYSQL_USER',     'root'),
    'password': os.environ.get('MYSQL_PASSWORD', 'Giuseppe'),
    'cursorclass': pymysql.cursors.DictCursor,
    'charset': 'utf8mb4'
}


def get_db_connection():
    """Crea e restituisce una connessione al database MySQL."""
    return pymysql.connect(**DB_CONFIG)


def fetch_table(query, params=None):
    """
    Esegue una query e restituisce (righe, errore).
    In caso di errore DB restituisce una lista vuota e il messaggio.
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            righe = cursor.fetchall()
        conn.close()
        return righe, None
    except pymysql.MySQLError as e:
        return [], f"Errore di connessione al database: {e}"


def _upsert(conn, table, id_field, fields, id_val=None):
    """
    INSERT (id_val=None, usa MAX+1) o UPDATE (id_val=int) su una tabella.
    fields: dict ordinato {colonna: valore}.
    Restituisce l'id usato.
    """
    if id_val is None:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COALESCE(MAX({id_field}), 0) + 1 AS nid FROM {table}")
            next_id = cur.fetchone()['nid']
        cols = ', '.join([id_field] + list(fields.keys()))
        ph   = ', '.join(['%s'] * (len(fields) + 1))
        vals = [next_id] + list(fields.values())
        with conn.cursor() as cur:
            cur.execute(f"INSERT INTO {table} ({cols}) VALUES ({ph})", vals)
        return next_id
    else:
        set_clause = ', '.join(f"{k}=%s" for k in fields.keys())
        vals = list(fields.values()) + [id_val]
        with conn.cursor() as cur:
            cur.execute(f"UPDATE {table} SET {set_clause} WHERE {id_field}=%s", vals)
        return id_val


def _get_by_id(table, id_field, id_val):
    """Restituisce il record come dict, o None se non trovato."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {table} WHERE {id_field} = %s", (id_val,))
            row = cur.fetchone()
        conn.close()
        return row, None
    except pymysql.MySQLError as e:
        return None, str(e)


def login_required(f):
    """Decorator: protegge le route richiedendo una sessione attiva."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# --------------------------------------------------------------------------- #
# Login
# --------------------------------------------------------------------------- #
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Se l'utente è già loggato, manda direttamente alle pagine
    if 'user_email' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT nome, cognome FROM utente WHERE email = %s AND password = %s",
                    (email, password)
                )
                utente = cursor.fetchone()
            conn.close()
        except pymysql.MySQLError as e:
            flash(f"Errore di connessione al database: {e}", 'danger')
            return render_template('login.html')

        if utente:
            session['user_email'] = email
            session['user_nome'] = f"{utente['nome']} {utente['cognome']}"
            return redirect(url_for('index'))
        else:
            flash('Email o password non corretti.', 'danger')

    return render_template('login.html')


# --------------------------------------------------------------------------- #
# Logout
# --------------------------------------------------------------------------- #
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# --------------------------------------------------------------------------- #
# Homepage → redirect a /utenti
# --------------------------------------------------------------------------- #
@app.route('/')
@login_required
def index():
    return redirect(url_for('utenti'))


# --------------------------------------------------------------------------- #
# Utenti
# --------------------------------------------------------------------------- #
@app.route('/utenti')
@login_required
def utenti():
    q = request.args.get('q', '').strip()
    if q:
        like = f'%{q}%'
        righe, errore = fetch_table(
            "SELECT id_utente, matricola, nome, cognome, email, telefono, localita_residenza "
            "FROM utente "
            "WHERE matricola LIKE %s OR nome LIKE %s OR cognome LIKE %s OR codice_fiscale LIKE %s "
            "ORDER BY cognome, nome",
            (like, like, like, like)
        )
    else:
        righe, errore = fetch_table(
            "SELECT id_utente, matricola, nome, cognome, email, telefono, localita_residenza "
            "FROM utente ORDER BY cognome, nome"
        )
    return render_template(
        'table.html',
        page_title='Utenti',
        active_page='utenti',
        colonne=['matricola', 'nome', 'cognome', 'email', 'telefono', 'localita_residenza'],
        righe=righe,
        errore=errore,
        action_url='/utenti/nuovo',
        action_label='Nuovo Utente',
        row_edit_url='/utenti/modifica',
        row_id_key='id_utente',
        row_delete_url='/utenti/elimina',
        row_delete_label_keys=['nome', 'cognome'],
        search_url='/utenti',
        search_query=q
    )


# --------------------------------------------------------------------------- #
# Nuovo Utente
# --------------------------------------------------------------------------- #
@app.route('/utenti/nuovo', methods=['GET', 'POST'])
@login_required
def utenti_nuovo():
    if request.method == 'POST':
        nome      = request.form.get('nome', '').strip()
        cognome   = request.form.get('cognome', '').strip()
        email     = request.form.get('email', '').strip()
        password  = request.form.get('password', '').strip()
        matricola = request.form.get('matricola', '').strip()

        if not all([nome, cognome, email, password, matricola]):
            flash('I campi Nome, Cognome, Email, Password e Matricola sono obbligatori.', 'danger')
            return render_template('utenti_form.html', active_page='utenti',
                                   page_title='Nuovo Utente', form_action='/utenti/nuovo',
                                   submit_label='Salva Utente', form=request.form)

        codice_fiscale      = request.form.get('codice_fiscale', '').strip() or None
        data_nascita        = request.form.get('data_nascita', '').strip() or None
        telefono            = request.form.get('telefono', '').strip() or None
        indirizzo_residenza = request.form.get('indirizzo_residenza', '').strip() or None
        localita_residenza  = request.form.get('localita_residenza', '').strip() or None
        indirizzo_domicilio = request.form.get('indirizzo_domicilio', '').strip() or None
        localita_domicilio  = request.form.get('localita_domicilio', '').strip() or None
        localita_nascita    = request.form.get('localita_nascita', '').strip() or None

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT COALESCE(MAX(id_utente), 0) + 1 AS next_id FROM utente")
                next_id = cursor.fetchone()['next_id']
                cursor.execute(
                    """INSERT INTO utente (
                        id_utente, nome, cognome, email, password, matricola,
                        codice_fiscale, data_nascita, telefono,
                        indirizzo_residenza, localita_residenza,
                        indirizzo_domicilio, localita_domicilio, localita_nascita
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (next_id, nome, cognome, email, password, matricola,
                     codice_fiscale, data_nascita, telefono,
                     indirizzo_residenza, localita_residenza,
                     indirizzo_domicilio, localita_domicilio, localita_nascita)
                )
            conn.commit()
            conn.close()
        except pymysql.err.IntegrityError:
            flash('Errore: esiste già un utente con questa email o matricola.', 'danger')
            return render_template('utenti_form.html', active_page='utenti',
                                   page_title='Nuovo Utente', form_action='/utenti/nuovo',
                                   submit_label='Salva Utente', form=request.form)
        except pymysql.MySQLError as e:
            flash(f'Errore database: {e}', 'danger')
            return render_template('utenti_form.html', active_page='utenti',
                                   page_title='Nuovo Utente', form_action='/utenti/nuovo',
                                   submit_label='Salva Utente', form=request.form)

        flash(f'Utente {nome} {cognome} inserito con successo.', 'success')
        return redirect(url_for('utenti'))

    return render_template('utenti_form.html', active_page='utenti',
                           page_title='Nuovo Utente', form_action='/utenti/nuovo',
                           submit_label='Salva Utente', form={})


# --------------------------------------------------------------------------- #
# Modifica Utente
# --------------------------------------------------------------------------- #
@app.route('/utenti/modifica/<int:id>', methods=['GET', 'POST'])
@login_required
def utenti_modifica(id):
    form_action = f'/utenti/modifica/{id}'

    if request.method == 'POST':
        nome      = request.form.get('nome', '').strip()
        cognome   = request.form.get('cognome', '').strip()
        email     = request.form.get('email', '').strip()
        password  = request.form.get('password', '').strip()
        matricola = request.form.get('matricola', '').strip()

        if not all([nome, cognome, email, password, matricola]):
            flash('I campi Nome, Cognome, Email, Password e Matricola sono obbligatori.', 'danger')
            return render_template('utenti_form.html', active_page='utenti',
                                   page_title='Modifica Utente', form_action=form_action,
                                   submit_label='Aggiorna Utente', form=request.form)

        codice_fiscale      = request.form.get('codice_fiscale', '').strip() or None
        data_nascita        = request.form.get('data_nascita', '').strip() or None
        telefono            = request.form.get('telefono', '').strip() or None
        indirizzo_residenza = request.form.get('indirizzo_residenza', '').strip() or None
        localita_residenza  = request.form.get('localita_residenza', '').strip() or None
        indirizzo_domicilio = request.form.get('indirizzo_domicilio', '').strip() or None
        localita_domicilio  = request.form.get('localita_domicilio', '').strip() or None
        localita_nascita    = request.form.get('localita_nascita', '').strip() or None

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE utente SET
                        nome=%s, cognome=%s, email=%s, password=%s, matricola=%s,
                        codice_fiscale=%s, data_nascita=%s, telefono=%s,
                        indirizzo_residenza=%s, localita_residenza=%s,
                        indirizzo_domicilio=%s, localita_domicilio=%s, localita_nascita=%s
                    WHERE id_utente=%s""",
                    (nome, cognome, email, password, matricola,
                     codice_fiscale, data_nascita, telefono,
                     indirizzo_residenza, localita_residenza,
                     indirizzo_domicilio, localita_domicilio, localita_nascita,
                     id)
                )
            conn.commit()
            conn.close()
        except pymysql.err.IntegrityError:
            flash('Errore: i dati inseriti violano un vincolo di unicità.', 'danger')
            return render_template('utenti_form.html', active_page='utenti',
                                   page_title='Modifica Utente', form_action=form_action,
                                   submit_label='Aggiorna Utente', form=request.form)
        except pymysql.MySQLError as e:
            flash(f'Errore database: {e}', 'danger')
            return render_template('utenti_form.html', active_page='utenti',
                                   page_title='Modifica Utente', form_action=form_action,
                                   submit_label='Aggiorna Utente', form=request.form)

        flash(f'Utente {nome} {cognome} aggiornato con successo.', 'success')
        return redirect(url_for('utenti'))

    # GET: carica dati utente dal DB
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM utente WHERE id_utente = %s", (id,))
            utente = cursor.fetchone()
        conn.close()
    except pymysql.MySQLError as e:
        flash(f'Errore database: {e}', 'danger')
        return redirect(url_for('utenti'))

    if utente is None:
        flash(f'Utente con ID {id} non trovato.', 'danger')
        return redirect(url_for('utenti'))

    return render_template('utenti_form.html', active_page='utenti',
                           page_title='Modifica Utente', form_action=form_action,
                           submit_label='Aggiorna Utente', form=utente)


# --------------------------------------------------------------------------- #
# Elimina Utente
# --------------------------------------------------------------------------- #
@app.route('/utenti/elimina/<int:id>', methods=['POST'])
@login_required
def utenti_elimina(id):
    # Impedisce di eliminare se stessi
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT nome, cognome, email FROM utente WHERE id_utente = %s", (id,))
            utente = cursor.fetchone()

        if utente is None:
            flash(f'Utente con ID {id} non trovato.', 'danger')
            conn.close()
            return redirect(url_for('utenti'))

        if utente['email'] == session.get('user_email'):
            flash('Non puoi eliminare il tuo stesso account.', 'danger')
            conn.close()
            return redirect(url_for('utenti'))

        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM utente WHERE id_utente = %s", (id,))
        conn.commit()
        conn.close()

    except pymysql.MySQLError as e:
        flash(f'Errore database: {e}', 'danger')
        return redirect(url_for('utenti'))

    flash(f'Utente {utente["nome"]} {utente["cognome"]} eliminato con successo.', 'success')
    return redirect(url_for('utenti'))


# --------------------------------------------------------------------------- #
# Articoli — CRUD completo
# --------------------------------------------------------------------------- #
@app.route('/articoli')
@login_required
def articoli():
    q = request.args.get('q', '').strip()
    if q:
        like = f'%{q}%'
        righe, errore = fetch_table(
            "SELECT id_articolo, codice, descrizione, unita_misura, quantita, giacenza, valore "
            "FROM articolo WHERE codice LIKE %s OR descrizione LIKE %s ORDER BY codice",
            (like, like)
        )
    else:
        righe, errore = fetch_table(
            "SELECT id_articolo, codice, descrizione, unita_misura, quantita, giacenza, valore "
            "FROM articolo ORDER BY codice"
        )
    return render_template(
        'table.html',
        page_title='Articoli', active_page='articoli',
        colonne=['codice', 'descrizione', 'unita_misura', 'quantita', 'giacenza', 'valore'],
        righe=righe, errore=errore,
        action_url='/articoli/nuovo', action_label='Nuovo Articolo',
        row_edit_url='/articoli/modifica', row_id_key='id_articolo',
        row_delete_url='/articoli/elimina', row_delete_label_keys=['codice', 'descrizione'],
        search_url='/articoli', search_query=q
    )


def _articolo_fields(form):
    return {
        'codice':       form.get('codice', '').strip() or None,
        'descrizione':  form.get('descrizione', '').strip() or None,
        'unita_misura': form.get('unita_misura', '').strip() or None,
        'quantita':     form.get('quantita') or None,
        'giacenza':     form.get('giacenza') or None,
        'valore':       form.get('valore') or None,
    }


@app.route('/articoli/nuovo', methods=['GET', 'POST'])
@login_required
def articoli_nuovo():
    tpl_vars = dict(active_page='articoli', page_title='Nuovo Articolo',
                    form_action='/articoli/nuovo', submit_label='Salva Articolo')
    if request.method == 'POST':
        if not request.form.get('codice', '').strip() or not request.form.get('descrizione', '').strip():
            flash('I campi Codice e Descrizione sono obbligatori.', 'danger')
            return render_template('articoli_form.html', **tpl_vars, form=request.form)
        try:
            conn = get_db_connection()
            _upsert(conn, 'articolo', 'id_articolo', _articolo_fields(request.form))
            conn.commit(); conn.close()
        except pymysql.MySQLError as e:
            flash(f'Errore database: {e}', 'danger')
            return render_template('articoli_form.html', **tpl_vars, form=request.form)
        flash(f'Articolo "{request.form["codice"]}" inserito con successo.', 'success')
        return redirect(url_for('articoli'))
    return render_template('articoli_form.html', **tpl_vars, form={})


@app.route('/articoli/modifica/<int:id>', methods=['GET', 'POST'])
@login_required
def articoli_modifica(id):
    tpl_vars = dict(active_page='articoli', page_title='Modifica Articolo',
                    form_action=f'/articoli/modifica/{id}', submit_label='Aggiorna Articolo')
    if request.method == 'POST':
        if not request.form.get('codice', '').strip() or not request.form.get('descrizione', '').strip():
            flash('I campi Codice e Descrizione sono obbligatori.', 'danger')
            return render_template('articoli_form.html', **tpl_vars, form=request.form)
        try:
            conn = get_db_connection()
            _upsert(conn, 'articolo', 'id_articolo', _articolo_fields(request.form), id_val=id)
            conn.commit(); conn.close()
        except pymysql.MySQLError as e:
            flash(f'Errore database: {e}', 'danger')
            return render_template('articoli_form.html', **tpl_vars, form=request.form)
        flash(f'Articolo "{request.form["codice"]}" aggiornato con successo.', 'success')
        return redirect(url_for('articoli'))
    row, err = _get_by_id('articolo', 'id_articolo', id)
    if err or row is None:
        flash(err or f'Articolo ID {id} non trovato.', 'danger')
        return redirect(url_for('articoli'))
    return render_template('articoli_form.html', **tpl_vars, form=row)


@app.route('/articoli/elimina/<int:id>', methods=['POST'])
@login_required
def articoli_elimina(id):
    row, err = _get_by_id('articolo', 'id_articolo', id)
    if err or row is None:
        flash(err or f'Articolo ID {id} non trovato.', 'danger')
        return redirect(url_for('articoli'))
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM articolo WHERE id_articolo=%s", (id,))
        conn.commit(); conn.close()
    except pymysql.MySQLError as e:
        flash(f'Errore database: {e}', 'danger')
        return redirect(url_for('articoli'))
    flash(f'Articolo "{row["codice"]}" eliminato con successo.', 'success')
    return redirect(url_for('articoli'))


# --------------------------------------------------------------------------- #
# Fornitori — CRUD completo
# --------------------------------------------------------------------------- #
@app.route('/fornitori')
@login_required
def fornitori():
    q = request.args.get('q', '').strip()
    if q:
        like = f'%{q}%'
        righe, errore = fetch_table(
            "SELECT id_fornitore, matricola, ragione_sociale, p_iva, email, telefono, citta "
            "FROM fornitore "
            "WHERE ragione_sociale LIKE %s OR matricola LIKE %s OR p_iva LIKE %s "
            "ORDER BY ragione_sociale",
            (like, like, like)
        )
    else:
        righe, errore = fetch_table(
            "SELECT id_fornitore, matricola, ragione_sociale, p_iva, email, telefono, citta "
            "FROM fornitore ORDER BY ragione_sociale"
        )
    return render_template(
        'table.html',
        page_title='Fornitori', active_page='fornitori',
        colonne=['matricola', 'ragione_sociale', 'p_iva', 'email', 'telefono', 'citta'],
        righe=righe, errore=errore,
        action_url='/fornitori/nuovo', action_label='Nuovo Fornitore',
        row_edit_url='/fornitori/modifica', row_id_key='id_fornitore',
        row_delete_url='/fornitori/elimina', row_delete_label_keys=['ragione_sociale', 'matricola'],
        search_url='/fornitori', search_query=q
    )


def _fornitore_fields(form):
    return {
        'ragione_sociale': form.get('ragione_sociale', '').strip() or None,
        'matricola':       form.get('matricola', '').strip() or None,
        'p_iva':           form.get('p_iva', '').strip() or None,
        'codice_fiscale':  form.get('codice_fiscale', '').strip() or None,
        'email':           form.get('email', '').strip() or None,
        'telefono':        form.get('telefono', '').strip() or None,
        'citta':           form.get('citta', '').strip() or None,
        'indirizzo':       form.get('indirizzo', '').strip() or None,
    }


@app.route('/fornitori/nuovo', methods=['GET', 'POST'])
@login_required
def fornitori_nuovo():
    tpl_vars = dict(active_page='fornitori', page_title='Nuovo Fornitore',
                    form_action='/fornitori/nuovo', submit_label='Salva Fornitore')
    if request.method == 'POST':
        if not request.form.get('ragione_sociale', '').strip() or not request.form.get('matricola', '').strip():
            flash('I campi Ragione Sociale e Matricola sono obbligatori.', 'danger')
            return render_template('fornitori_form.html', **tpl_vars, form=request.form)
        try:
            conn = get_db_connection()
            _upsert(conn, 'fornitore', 'id_fornitore', _fornitore_fields(request.form))
            conn.commit(); conn.close()
        except pymysql.MySQLError as e:
            flash(f'Errore database: {e}', 'danger')
            return render_template('fornitori_form.html', **tpl_vars, form=request.form)
        flash(f'Fornitore "{request.form["ragione_sociale"]}" inserito con successo.', 'success')
        return redirect(url_for('fornitori'))
    return render_template('fornitori_form.html', **tpl_vars, form={})


@app.route('/fornitori/modifica/<int:id>', methods=['GET', 'POST'])
@login_required
def fornitori_modifica(id):
    tpl_vars = dict(active_page='fornitori', page_title='Modifica Fornitore',
                    form_action=f'/fornitori/modifica/{id}', submit_label='Aggiorna Fornitore')
    if request.method == 'POST':
        if not request.form.get('ragione_sociale', '').strip() or not request.form.get('matricola', '').strip():
            flash('I campi Ragione Sociale e Matricola sono obbligatori.', 'danger')
            return render_template('fornitori_form.html', **tpl_vars, form=request.form)
        try:
            conn = get_db_connection()
            _upsert(conn, 'fornitore', 'id_fornitore', _fornitore_fields(request.form), id_val=id)
            conn.commit(); conn.close()
        except pymysql.MySQLError as e:
            flash(f'Errore database: {e}', 'danger')
            return render_template('fornitori_form.html', **tpl_vars, form=request.form)
        flash(f'Fornitore "{request.form["ragione_sociale"]}" aggiornato con successo.', 'success')
        return redirect(url_for('fornitori'))
    row, err = _get_by_id('fornitore', 'id_fornitore', id)
    if err or row is None:
        flash(err or f'Fornitore ID {id} non trovato.', 'danger')
        return redirect(url_for('fornitori'))
    return render_template('fornitori_form.html', **tpl_vars, form=row)


@app.route('/fornitori/elimina/<int:id>', methods=['POST'])
@login_required
def fornitori_elimina(id):
    row, err = _get_by_id('fornitore', 'id_fornitore', id)
    if err or row is None:
        flash(err or f'Fornitore ID {id} non trovato.', 'danger')
        return redirect(url_for('fornitori'))
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM fornitore WHERE id_fornitore=%s", (id,))
        conn.commit(); conn.close()
    except pymysql.MySQLError as e:
        flash(f'Errore database: {e}', 'danger')
        return redirect(url_for('fornitori'))
    flash(f'Fornitore "{row["ragione_sociale"]}" eliminato con successo.', 'success')
    return redirect(url_for('fornitori'))


# --------------------------------------------------------------------------- #
# Veicoli — CRUD completo
# --------------------------------------------------------------------------- #
@app.route('/veicoli')
@login_required
def veicoli():
    q = request.args.get('q', '').strip()
    if q:
        like = f'%{q}%'
        righe, errore = fetch_table(
            "SELECT id_veicolo, matricola, modello, targa, numero_telaio, data_immatricolazione "
            "FROM veicolo "
            "WHERE matricola LIKE %s OR modello LIKE %s OR targa LIKE %s OR numero_telaio LIKE %s "
            "ORDER BY targa",
            (like, like, like, like)
        )
    else:
        righe, errore = fetch_table(
            "SELECT id_veicolo, matricola, modello, targa, numero_telaio, data_immatricolazione "
            "FROM veicolo ORDER BY targa"
        )
    return render_template(
        'table.html',
        page_title='Veicoli', active_page='veicoli',
        colonne=['matricola', 'modello', 'targa', 'numero_telaio', 'data_immatricolazione'],
        righe=righe, errore=errore,
        action_url='/veicoli/nuovo', action_label='Nuovo Veicolo',
        row_edit_url='/veicoli/modifica', row_id_key='id_veicolo',
        row_delete_url='/veicoli/elimina', row_delete_label_keys=['targa', 'modello'],
        search_url='/veicoli', search_query=q
    )


def _veicolo_fields(form):
    return {
        'matricola':            form.get('matricola', '').strip() or None,
        'modello':              form.get('modello', '').strip() or None,
        'targa':                form.get('targa', '').strip() or None,
        'numero_telaio':        form.get('numero_telaio', '').strip() or None,
        'data_immatricolazione': form.get('data_immatricolazione', '').strip() or None,
    }


@app.route('/veicoli/nuovo', methods=['GET', 'POST'])
@login_required
def veicoli_nuovo():
    tpl_vars = dict(active_page='veicoli', page_title='Nuovo Veicolo',
                    form_action='/veicoli/nuovo', submit_label='Salva Veicolo')
    if request.method == 'POST':
        req = [request.form.get(f, '').strip() for f in ('matricola', 'modello', 'targa')]
        if not all(req):
            flash('I campi Matricola, Modello e Targa sono obbligatori.', 'danger')
            return render_template('veicoli_form.html', **tpl_vars, form=request.form)
        try:
            conn = get_db_connection()
            _upsert(conn, 'veicolo', 'id_veicolo', _veicolo_fields(request.form))
            conn.commit(); conn.close()
        except pymysql.MySQLError as e:
            flash(f'Errore database: {e}', 'danger')
            return render_template('veicoli_form.html', **tpl_vars, form=request.form)
        flash(f'Veicolo "{request.form["targa"]}" inserito con successo.', 'success')
        return redirect(url_for('veicoli'))
    return render_template('veicoli_form.html', **tpl_vars, form={})


@app.route('/veicoli/modifica/<int:id>', methods=['GET', 'POST'])
@login_required
def veicoli_modifica(id):
    tpl_vars = dict(active_page='veicoli', page_title='Modifica Veicolo',
                    form_action=f'/veicoli/modifica/{id}', submit_label='Aggiorna Veicolo')
    if request.method == 'POST':
        req = [request.form.get(f, '').strip() for f in ('matricola', 'modello', 'targa')]
        if not all(req):
            flash('I campi Matricola, Modello e Targa sono obbligatori.', 'danger')
            return render_template('veicoli_form.html', **tpl_vars, form=request.form)
        try:
            conn = get_db_connection()
            _upsert(conn, 'veicolo', 'id_veicolo', _veicolo_fields(request.form), id_val=id)
            conn.commit(); conn.close()
        except pymysql.MySQLError as e:
            flash(f'Errore database: {e}', 'danger')
            return render_template('veicoli_form.html', **tpl_vars, form=request.form)
        flash(f'Veicolo "{request.form["targa"]}" aggiornato con successo.', 'success')
        return redirect(url_for('veicoli'))
    row, err = _get_by_id('veicolo', 'id_veicolo', id)
    if err or row is None:
        flash(err or f'Veicolo ID {id} non trovato.', 'danger')
        return redirect(url_for('veicoli'))
    return render_template('veicoli_form.html', **tpl_vars, form=row)


@app.route('/veicoli/elimina/<int:id>', methods=['POST'])
@login_required
def veicoli_elimina(id):
    row, err = _get_by_id('veicolo', 'id_veicolo', id)
    if err or row is None:
        flash(err or f'Veicolo ID {id} non trovato.', 'danger')
        return redirect(url_for('veicoli'))
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM veicolo WHERE id_veicolo=%s", (id,))
        conn.commit(); conn.close()
    except pymysql.MySQLError as e:
        flash(f'Errore database: {e}', 'danger')
        return redirect(url_for('veicoli'))
    flash(f'Veicolo "{row["targa"]}" eliminato con successo.', 'success')
    return redirect(url_for('veicoli'))


# --------------------------------------------------------------------------- #
# DDT — lista + ricerca
# --------------------------------------------------------------------------- #
@app.route('/ddt')
@login_required
def ddt():
    q = request.args.get('q', '').strip()
    base_sql = """
        SELECT d.id_ddt, d.numero_ddt, d.data_ddt,
               COALESCE(f.ragione_sociale, '—') AS ragione_sociale,
               COUNT(cd.id_corpo_documento) AS righe
        FROM ddt d
        LEFT JOIN fornitore f ON d.id_fornitore = f.id_fornitore
        LEFT JOIN corpo_documento cd ON d.id_ddt = cd.id_ddt
        {where}
        GROUP BY d.id_ddt, d.numero_ddt, d.data_ddt, f.ragione_sociale
        ORDER BY d.id_ddt DESC
    """
    if q:
        like = f'%{q}%'
        righe, errore = fetch_table(
            base_sql.format(where="WHERE d.numero_ddt LIKE %s OR f.ragione_sociale LIKE %s"),
            (like, like)
        )
    else:
        righe, errore = fetch_table(base_sql.format(where=""))

    return render_template(
        'table.html',
        page_title='DDT - Documenti di Trasporto', active_page='ddt',
        colonne=['numero_ddt', 'data_ddt', 'ragione_sociale', 'righe'],
        righe=righe, errore=errore,
        action_url='/ddt/nuovo', action_label='Nuovo DDT',
        row_edit_url='/ddt/modifica', row_id_key='id_ddt',
        row_delete_url='/ddt/elimina', row_delete_label_keys=['numero_ddt', 'data_ddt'],
        search_url='/ddt', search_query=q
    )


def _ddt_get_fornitori(cur):
    cur.execute("SELECT id_fornitore, ragione_sociale FROM fornitore ORDER BY ragione_sociale")
    return cur.fetchall()


def _ddt_get_articoli(cur):
    cur.execute("SELECT id_articolo, codice, descrizione FROM articolo ORDER BY codice")
    return cur.fetchall()


def _ddt_parse_righe(form):
    """Restituisce lista di (id_articolo, quantita) dal form."""
    ids  = form.getlist('righe_articolo[]')
    qtys = form.getlist('righe_quantita[]')
    rows = []
    for art_id, qty in zip(ids, qtys):
        try:
            art_id = int(art_id)
            qty    = max(1, int(qty or 1))
            rows.append((art_id, qty))
        except (ValueError, TypeError):
            continue
    return rows


def _ddt_insert_righe(cur, id_ddt, rows):
    """INSERT righe in corpo_documento e aggiorna giacenze +."""
    if not rows:
        return
    cur.execute("SELECT COALESCE(MAX(id_corpo_documento), 0) + 1 AS nid FROM corpo_documento")
    next_id = cur.fetchone()['nid']
    for i, (art_id, qty) in enumerate(rows):
        cur.execute(
            "INSERT INTO corpo_documento (id_corpo_documento, id_articolo, id_ddt, quantita) "
            "VALUES (%s, %s, %s, %s)",
            (next_id + i, art_id, id_ddt, qty)
        )
        cur.execute(
            "UPDATE articolo SET giacenza = giacenza + %s WHERE id_articolo = %s",
            (qty, art_id)
        )


def _ddt_delete_righe(cur, id_ddt):
    """Annulla le giacenze delle righe esistenti e le elimina."""
    cur.execute(
        "SELECT id_articolo, quantita FROM corpo_documento WHERE id_ddt = %s",
        (id_ddt,)
    )
    for r in cur.fetchall():
        cur.execute(
            "UPDATE articolo SET giacenza = giacenza - %s WHERE id_articolo = %s",
            (r['quantita'] or 0, r['id_articolo'])
        )
    cur.execute("DELETE FROM corpo_documento WHERE id_ddt = %s", (id_ddt,))


# --------------------------------------------------------------------------- #
# DDT — nuovo
# --------------------------------------------------------------------------- #
@app.route('/ddt/nuovo', methods=['GET', 'POST'])
@login_required
def ddt_nuovo():
    conn = get_db_connection()
    with conn.cursor() as cur:
        fornitori = _ddt_get_fornitori(cur)
        articoli  = _ddt_get_articoli(cur)
    conn.close()

    if request.method == 'POST':
        numero_ddt   = request.form.get('numero_ddt', '').strip()
        data_ddt     = request.form.get('data_ddt', '').strip()
        id_fornitore = request.form.get('id_fornitore') or None
        rows         = _ddt_parse_righe(request.form)

        if not numero_ddt or not data_ddt:
            flash('Numero DDT e Data sono obbligatori.', 'danger')
            return render_template('ddt_form.html', active_page='ddt',
                                   page_title='Nuovo DDT', form_action='/ddt/nuovo',
                                   submit_label='Salva DDT',
                                   fornitori=fornitori, articoli=articoli,
                                   form=request.form, righe_form=rows)
        try:
            conn = get_db_connection()
            conn.begin()
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(MAX(id_ddt), 0) + 1 AS nid FROM ddt")
                id_ddt = cur.fetchone()['nid']
                cur.execute(
                    "INSERT INTO ddt (id_ddt, numero_ddt, data_ddt, id_fornitore) VALUES (%s,%s,%s,%s)",
                    (id_ddt, numero_ddt, data_ddt, id_fornitore)
                )
                _ddt_insert_righe(cur, id_ddt, rows)
            conn.commit()
            conn.close()
        except pymysql.MySQLError as e:
            conn.rollback(); conn.close()
            flash(f'Errore database: {e}', 'danger')
            return render_template('ddt_form.html', active_page='ddt',
                                   page_title='Nuovo DDT', form_action='/ddt/nuovo',
                                   submit_label='Salva DDT',
                                   fornitori=fornitori, articoli=articoli,
                                   form=request.form, righe_form=rows)

        flash(f'DDT n. {numero_ddt} creato con successo ({len(rows)} righe).', 'success')
        return redirect(url_for('ddt'))

    return render_template('ddt_form.html', active_page='ddt',
                           page_title='Nuovo DDT', form_action='/ddt/nuovo',
                           submit_label='Salva DDT',
                           fornitori=fornitori, articoli=articoli,
                           form={}, righe_form=[])


# --------------------------------------------------------------------------- #
# DDT — modifica
# --------------------------------------------------------------------------- #
@app.route('/ddt/modifica/<int:id>', methods=['GET', 'POST'])
@login_required
def ddt_modifica(id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        fornitori = _ddt_get_fornitori(cur)
        articoli  = _ddt_get_articoli(cur)
        cur.execute("SELECT * FROM ddt WHERE id_ddt = %s", (id,))
        testata = cur.fetchone()
        cur.execute(
            "SELECT id_articolo, quantita FROM corpo_documento WHERE id_ddt = %s", (id,)
        )
        righe_esistenti = cur.fetchall()
    conn.close()

    if testata is None:
        flash(f'DDT ID {id} non trovato.', 'danger')
        return redirect(url_for('ddt'))

    form_action = f'/ddt/modifica/{id}'

    if request.method == 'POST':
        numero_ddt   = request.form.get('numero_ddt', '').strip()
        data_ddt     = request.form.get('data_ddt', '').strip()
        id_fornitore = request.form.get('id_fornitore') or None
        rows         = _ddt_parse_righe(request.form)

        if not numero_ddt or not data_ddt:
            flash('Numero DDT e Data sono obbligatori.', 'danger')
            return render_template('ddt_form.html', active_page='ddt',
                                   page_title='Modifica DDT', form_action=form_action,
                                   submit_label='Aggiorna DDT',
                                   fornitori=fornitori, articoli=articoli,
                                   form=request.form, righe_form=rows)
        try:
            conn = get_db_connection()
            conn.begin()
            with conn.cursor() as cur:
                # 1. Annulla giacenze vecchie righe, cancella righe
                _ddt_delete_righe(cur, id)
                # 2. Aggiorna testata
                cur.execute(
                    "UPDATE ddt SET numero_ddt=%s, data_ddt=%s, id_fornitore=%s WHERE id_ddt=%s",
                    (numero_ddt, data_ddt, id_fornitore, id)
                )
                # 3. Inserisci nuove righe e aggiorna giacenze
                _ddt_insert_righe(cur, id, rows)
            conn.commit()
            conn.close()
        except pymysql.MySQLError as e:
            conn.rollback(); conn.close()
            flash(f'Errore database: {e}', 'danger')
            return render_template('ddt_form.html', active_page='ddt',
                                   page_title='Modifica DDT', form_action=form_action,
                                   submit_label='Aggiorna DDT',
                                   fornitori=fornitori, articoli=articoli,
                                   form=request.form, righe_form=rows)

        flash(f'DDT n. {numero_ddt} aggiornato con successo.', 'success')
        return redirect(url_for('ddt'))

    # GET: precompila con dati esistenti
    righe_form = [(r['id_articolo'], r['quantita'] or 1) for r in righe_esistenti]
    return render_template('ddt_form.html', active_page='ddt',
                           page_title='Modifica DDT', form_action=form_action,
                           submit_label='Aggiorna DDT',
                           fornitori=fornitori, articoli=articoli,
                           form=testata, righe_form=righe_form)


# --------------------------------------------------------------------------- #
# DDT — elimina
# --------------------------------------------------------------------------- #
@app.route('/ddt/elimina/<int:id>', methods=['POST'])
@login_required
def ddt_elimina(id):
    row, err = _get_by_id('ddt', 'id_ddt', id)
    if err or row is None:
        flash(err or f'DDT ID {id} non trovato.', 'danger')
        return redirect(url_for('ddt'))
    try:
        conn = get_db_connection()
        conn.begin()
        with conn.cursor() as cur:
            _ddt_delete_righe(cur, id)
            cur.execute("DELETE FROM ddt WHERE id_ddt=%s", (id,))
        conn.commit()
        conn.close()
    except pymysql.MySQLError as e:
        conn.rollback(); conn.close()
        flash(f'Errore database: {e}', 'danger')
        return redirect(url_for('ddt'))

    flash(f'DDT n. {row["numero_ddt"]} eliminato con successo.', 'success')
    return redirect(url_for('ddt'))


# =========================================================================== #
# COMMESSE
# =========================================================================== #

# --------------------------------------------------------------------------- #
# Commesse — lista + ricerca
# --------------------------------------------------------------------------- #
@app.route('/commesse')
@login_required
def commesse():
    q = request.args.get('q', '').strip()
    base_sql = """
        SELECT c.id_commessa, c.numero_commessa, c.data_entrata, c.data_uscita,
               COALESCE(CONCAT(v.targa, ' — ', v.modello), '—') AS veicolo,
               COUNT(ca.id_commessa_articolo) AS pezzi
        FROM commessa c
        LEFT JOIN veicolo v ON c.id_veicolo = v.id_veicolo
        LEFT JOIN commessa_articolo ca ON c.id_commessa = ca.id_commessa
        {where}
        GROUP BY c.id_commessa, c.numero_commessa, c.data_entrata, c.data_uscita, v.targa, v.modello
        ORDER BY c.id_commessa DESC
    """
    if q:
        like = f'%{q}%'
        righe, errore = fetch_table(
            base_sql.format(where="WHERE c.numero_commessa LIKE %s OR v.targa LIKE %s"),
            (like, like)
        )
    else:
        righe, errore = fetch_table(base_sql.format(where=""))

    return render_template(
        'table.html',
        page_title='Commesse', active_page='commesse',
        colonne=['numero_commessa', 'data_entrata', 'data_uscita', 'veicolo', 'pezzi'],
        righe=righe, errore=errore,
        action_url='/commesse/nuovo', action_label='Nuova Commessa',
        row_edit_url='/commesse/modifica', row_id_key='id_commessa',
        row_delete_url='/commesse/elimina', row_delete_label_keys=['numero_commessa', 'data_entrata'],
        search_url='/commesse', search_query=q
    )


# --------------------------------------------------------------------------- #
# Helpers Commesse
# --------------------------------------------------------------------------- #
def _comm_get_veicoli(cur):
    cur.execute("SELECT id_veicolo, targa, modello FROM veicolo ORDER BY targa")
    return cur.fetchall()


def _comm_get_articoli(cur):
    cur.execute("SELECT id_articolo, codice, descrizione FROM articolo ORDER BY codice")
    return cur.fetchall()


def _comm_parse_righe(form):
    """Restituisce lista di (id_articolo, quantita) dal form."""
    ids  = form.getlist('righe_articolo[]')
    qtys = form.getlist('righe_quantita[]')
    rows = []
    for art_id, qty in zip(ids, qtys):
        try:
            rows.append((int(art_id), max(1, int(qty or 1))))
        except (ValueError, TypeError):
            continue
    return rows


def _comm_insert_righe(cur, id_commessa, rows):
    """INSERT righe in commessa_articolo e DECREMENTA giacenze."""
    if not rows:
        return
    cur.execute("SELECT COALESCE(MAX(id_commessa_articolo), 0) + 1 AS nid FROM commessa_articolo")
    next_id = cur.fetchone()['nid']
    for i, (art_id, qty) in enumerate(rows):
        cur.execute(
            "INSERT INTO commessa_articolo (id_commessa_articolo, id_commessa, id_articolo, quantita) "
            "VALUES (%s, %s, %s, %s)",
            (next_id + i, id_commessa, art_id, qty)
        )
        cur.execute(
            "UPDATE articolo SET giacenza = giacenza - %s WHERE id_articolo = %s",
            (qty, art_id)
        )


def _comm_delete_righe(cur, id_commessa):
    """RIPRISTINA giacenze delle righe esistenti e le elimina."""
    cur.execute(
        "SELECT id_articolo, quantita FROM commessa_articolo WHERE id_commessa = %s",
        (id_commessa,)
    )
    for r in cur.fetchall():
        cur.execute(
            "UPDATE articolo SET giacenza = giacenza + %s WHERE id_articolo = %s",
            (r['quantita'] or 0, r['id_articolo'])
        )
    cur.execute("DELETE FROM commessa_articolo WHERE id_commessa = %s", (id_commessa,))


# --------------------------------------------------------------------------- #
# Commesse — nuovo
# --------------------------------------------------------------------------- #
@app.route('/commesse/nuovo', methods=['GET', 'POST'])
@login_required
def commesse_nuovo():
    conn = get_db_connection()
    with conn.cursor() as cur:
        veicoli  = _comm_get_veicoli(cur)
        articoli = _comm_get_articoli(cur)
    conn.close()

    tpl = dict(active_page='commesse', page_title='Nuova Commessa',
               form_action='/commesse/nuovo', submit_label='Salva Commessa',
               veicoli=veicoli, articoli=articoli)

    if request.method == 'POST':
        numero   = request.form.get('numero_commessa', '').strip()
        entrata  = request.form.get('data_entrata', '').strip()
        uscita   = request.form.get('data_uscita', '').strip() or None
        id_veic  = request.form.get('id_veicolo') or None
        descr    = request.form.get('descrizione_lavori', '').strip() or None
        rows     = _comm_parse_righe(request.form)

        if not numero or not entrata:
            flash('Numero commessa e Data entrata sono obbligatori.', 'danger')
            return render_template('commesse_form.html', **tpl, form=request.form, righe_form=rows)

        try:
            conn = get_db_connection()
            conn.begin()
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(MAX(id_commessa), 0) + 1 AS nid FROM commessa")
                id_c = cur.fetchone()['nid']
                cur.execute(
                    "INSERT INTO commessa "
                    "(id_commessa, numero_commessa, data_entrata, data_uscita, id_veicolo, descrizione_lavori) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (id_c, numero, entrata, uscita, id_veic, descr)
                )
                _comm_insert_righe(cur, id_c, rows)
            conn.commit(); conn.close()
        except pymysql.MySQLError as e:
            conn.rollback(); conn.close()
            flash(f'Errore database: {e}', 'danger')
            return render_template('commesse_form.html', **tpl, form=request.form, righe_form=rows)

        flash(f'Commessa "{numero}" creata con successo ({len(rows)} pezzi).', 'success')
        return redirect(url_for('commesse'))

    return render_template('commesse_form.html', **tpl, form={}, righe_form=[])


# --------------------------------------------------------------------------- #
# Commesse — modifica
# --------------------------------------------------------------------------- #
@app.route('/commesse/modifica/<int:id>', methods=['GET', 'POST'])
@login_required
def commesse_modifica(id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        veicoli  = _comm_get_veicoli(cur)
        articoli = _comm_get_articoli(cur)
        cur.execute("SELECT * FROM commessa WHERE id_commessa = %s", (id,))
        testata = cur.fetchone()
        cur.execute(
            "SELECT id_articolo, quantita FROM commessa_articolo WHERE id_commessa = %s", (id,)
        )
        righe_esistenti = cur.fetchall()
    conn.close()

    if testata is None:
        flash(f'Commessa ID {id} non trovata.', 'danger')
        return redirect(url_for('commesse'))

    form_action = f'/commesse/modifica/{id}'
    tpl = dict(active_page='commesse', page_title='Modifica Commessa',
               form_action=form_action, submit_label='Aggiorna Commessa',
               veicoli=veicoli, articoli=articoli)

    if request.method == 'POST':
        numero   = request.form.get('numero_commessa', '').strip()
        entrata  = request.form.get('data_entrata', '').strip()
        uscita   = request.form.get('data_uscita', '').strip() or None
        id_veic  = request.form.get('id_veicolo') or None
        descr    = request.form.get('descrizione_lavori', '').strip() or None
        rows     = _comm_parse_righe(request.form)

        if not numero or not entrata:
            flash('Numero commessa e Data entrata sono obbligatori.', 'danger')
            return render_template('commesse_form.html', **tpl, form=request.form, righe_form=rows)

        try:
            conn = get_db_connection()
            conn.begin()
            with conn.cursor() as cur:
                _comm_delete_righe(cur, id)   # ripristina giacenze vecchie
                cur.execute(
                    "UPDATE commessa SET numero_commessa=%s, data_entrata=%s, data_uscita=%s, "
                    "id_veicolo=%s, descrizione_lavori=%s WHERE id_commessa=%s",
                    (numero, entrata, uscita, id_veic, descr, id)
                )
                _comm_insert_righe(cur, id, rows)   # applica nuove giacenze
            conn.commit(); conn.close()
        except pymysql.MySQLError as e:
            conn.rollback(); conn.close()
            flash(f'Errore database: {e}', 'danger')
            return render_template('commesse_form.html', **tpl, form=request.form, righe_form=rows)

        flash(f'Commessa "{numero}" aggiornata con successo.', 'success')
        return redirect(url_for('commesse'))

    righe_form = [(r['id_articolo'], r['quantita'] or 1) for r in righe_esistenti]
    return render_template('commesse_form.html', **tpl, form=testata, righe_form=righe_form)


# --------------------------------------------------------------------------- #
# Commesse — elimina
# --------------------------------------------------------------------------- #
@app.route('/commesse/elimina/<int:id>', methods=['POST'])
@login_required
def commesse_elimina(id):
    row, err = _get_by_id('commessa', 'id_commessa', id)
    if err or row is None:
        flash(err or f'Commessa ID {id} non trovata.', 'danger')
        return redirect(url_for('commesse'))
    try:
        conn = get_db_connection()
        conn.begin()
        with conn.cursor() as cur:
            _comm_delete_righe(cur, id)
            cur.execute("DELETE FROM commessa WHERE id_commessa=%s", (id,))
        conn.commit(); conn.close()
    except pymysql.MySQLError as e:
        conn.rollback(); conn.close()
        flash(f'Errore database: {e}', 'danger')
        return redirect(url_for('commesse'))

    flash(f'Commessa "{row["numero_commessa"]}" eliminata con successo.', 'success')
    return redirect(url_for('commesse'))


# =========================================================================== #
# AUTISTI
# =========================================================================== #

@app.route('/autisti')
@login_required
def autisti():
    q = request.args.get('q', '').strip()
    if q:
        like = f'%{q}%'
        rows, err = fetch_table(
            "SELECT id_autista, nome, cognome, email, telefono FROM autista "
            "WHERE nome LIKE %s OR cognome LIKE %s OR email LIKE %s "
            "ORDER BY cognome, nome",
            (like, like, like)
        )
    else:
        rows, err = fetch_table(
            "SELECT id_autista, nome, cognome, email, telefono FROM autista "
            "ORDER BY cognome, nome"
        )
    if err:
        flash(f'Errore database: {err}', 'danger')
        rows = []
    return render_template('table.html',
        active_page='autisti',
        page_title='Gestione Autisti',
        columns=['Nome', 'Cognome', 'Email', 'Telefono'],
        column_keys=['nome', 'cognome', 'email', 'telefono'],
        rows=rows,
        new_url='/autisti/nuovo',
        new_label='Nuovo Autista',
        row_edit_url='/autisti/modifica',
        row_id_key='id_autista',
        row_delete_url='/autisti/elimina',
        row_delete_label_keys=['nome', 'cognome'],
        search_url='/autisti',
        search_query=q,
    )


@app.route('/autisti/nuovo', methods=['GET', 'POST'])
@login_required
def autisti_nuovo():
    if request.method == 'POST':
        nome     = request.form.get('nome', '').strip()
        cognome  = request.form.get('cognome', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        telefono = request.form.get('telefono', '').strip() or None
        if not all([nome, cognome, email, password]):
            flash('Nome, cognome, email e password sono obbligatori.', 'danger')
            return render_template('autisti_form.html',
                active_page='autisti',
                page_title='Nuovo Autista',
                form_action='/autisti/nuovo',
                submit_label='Crea Autista',
                form=request.form)
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(MAX(id_autista), 0) + 1 AS nid FROM autista")
                next_id = cur.fetchone()['nid']
                cur.execute(
                    "INSERT INTO autista (id_autista, nome, cognome, email, password, telefono) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (next_id, nome, cognome, email, password, telefono)
                )
            conn.commit(); conn.close()
        except pymysql.MySQLError as e:
            flash(f'Errore database: {e}', 'danger')
            return render_template('autisti_form.html',
                active_page='autisti',
                page_title='Nuovo Autista',
                form_action='/autisti/nuovo',
                submit_label='Crea Autista',
                form=request.form)
        flash(f'Autista {nome} {cognome} creato con successo.', 'success')
        return redirect(url_for('autisti'))
    return render_template('autisti_form.html',
        active_page='autisti',
        page_title='Nuovo Autista',
        form_action='/autisti/nuovo',
        submit_label='Crea Autista',
        form={})


@app.route('/autisti/modifica/<int:id>', methods=['GET', 'POST'])
@login_required
def autisti_modifica(id):
    if request.method == 'POST':
        nome     = request.form.get('nome', '').strip()
        cognome  = request.form.get('cognome', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        telefono = request.form.get('telefono', '').strip() or None
        if not all([nome, cognome, email, password]):
            flash('Nome, cognome, email e password sono obbligatori.', 'danger')
            return render_template('autisti_form.html',
                active_page='autisti',
                page_title='Modifica Autista',
                form_action=f'/autisti/modifica/{id}',
                submit_label='Salva Modifiche',
                form=request.form)
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE autista SET nome=%s, cognome=%s, email=%s, password=%s, telefono=%s "
                    "WHERE id_autista=%s",
                    (nome, cognome, email, password, telefono, id)
                )
            conn.commit(); conn.close()
        except pymysql.MySQLError as e:
            flash(f'Errore database: {e}', 'danger')
            return render_template('autisti_form.html',
                active_page='autisti',
                page_title='Modifica Autista',
                form_action=f'/autisti/modifica/{id}',
                submit_label='Salva Modifiche',
                form=request.form)
        flash(f'Autista {nome} {cognome} aggiornato con successo.', 'success')
        return redirect(url_for('autisti'))
    # GET — precompila dal DB
    rows, err = fetch_table(
        "SELECT * FROM autista WHERE id_autista=%s", (id,)
    )
    if err or not rows:
        flash('Autista non trovato.', 'danger')
        return redirect(url_for('autisti'))
    return render_template('autisti_form.html',
        active_page='autisti',
        page_title='Modifica Autista',
        form_action=f'/autisti/modifica/{id}',
        submit_label='Salva Modifiche',
        form=rows[0])


@app.route('/autisti/elimina/<int:id>', methods=['POST'])
@login_required
def autisti_elimina(id):
    rows, err = fetch_table(
        "SELECT nome, cognome FROM autista WHERE id_autista=%s", (id,)
    )
    if err or not rows:
        flash('Autista non trovato.', 'danger')
        return redirect(url_for('autisti'))
    row = rows[0]
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM autista WHERE id_autista=%s", (id,))
        conn.commit(); conn.close()
    except pymysql.MySQLError as e:
        flash(f'Errore database: {e}', 'danger')
        return redirect(url_for('autisti'))
    flash(f'Autista {row["nome"]} {row["cognome"]} eliminato con successo.', 'success')
    return redirect(url_for('autisti'))


# =========================================================================== #
# API REST
# =========================================================================== #

_BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(_BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

_ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}


def _api_require_autista():
    if 'autista_id' not in session:
        return jsonify({'error': 'Non autenticato'}), 401
    return None


def _api_require_doxy():
    if 'user_email' not in session:
        return jsonify({'error': 'Non autenticato'}), 401
    return None


def _json_input():
    """Legge JSON body oppure form data."""
    return request.get_json(silent=True) or request.form


# --------------------------------------------------------------------------- #
# API — Autista login / register
# --------------------------------------------------------------------------- #
@app.route('/api/autista/login', methods=['POST'])
def api_autista_login():
    d        = _json_input()
    email    = (d.get('email') or '').strip()
    password = (d.get('password') or '').strip()
    if not email or not password:
        return jsonify({'error': 'Email e password obbligatori'}), 400
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id_autista, nome, cognome FROM autista WHERE email=%s AND password=%s",
                (email, password)
            )
            row = cur.fetchone()
        conn.close()
    except pymysql.MySQLError as e:
        return jsonify({'error': str(e)}), 500
    if not row:
        return jsonify({'error': 'Credenziali non valide'}), 401
    session['autista_id']   = row['id_autista']
    session['autista_nome'] = f"{row['nome']} {row['cognome']}"
    return jsonify({'id_autista': row['id_autista'], 'nome': row['nome'], 'cognome': row['cognome']})


@app.route('/api/autista/logout', methods=['POST'])
def api_autista_logout():
    session.pop('autista_id', None)
    session.pop('autista_nome', None)
    return jsonify({'message': 'Disconnesso'})


@app.route('/api/autista/register', methods=['POST'])
def api_autista_register():
    d        = _json_input()
    nome     = (d.get('nome') or '').strip()
    cognome  = (d.get('cognome') or '').strip()
    email    = (d.get('email') or '').strip()
    password = (d.get('password') or '').strip()
    telefono = (d.get('telefono') or '').strip() or None
    if not all([nome, cognome, email, password]):
        return jsonify({'error': 'Nome, cognome, email e password sono obbligatori'}), 400
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(id_autista), 0) + 1 AS nid FROM autista")
            next_id = cur.fetchone()['nid']
            cur.execute(
                "INSERT INTO autista (id_autista, nome, cognome, email, password, telefono) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (next_id, nome, cognome, email, password, telefono)
            )
        conn.commit(); conn.close()
    except pymysql.err.IntegrityError:
        return jsonify({'error': 'Email già registrata'}), 409
    except pymysql.MySQLError as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'message': 'Registrazione completata', 'id_autista': next_id}), 201


# --------------------------------------------------------------------------- #
# API — Doxy login via API
# --------------------------------------------------------------------------- #
@app.route('/api/doxy/login', methods=['POST'])
def api_doxy_login():
    d        = _json_input()
    email    = (d.get('email') or '').strip()
    password = (d.get('password') or '').strip()
    if not email or not password:
        return jsonify({'error': 'Email e password obbligatori'}), 400
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT nome, cognome FROM utente WHERE email=%s AND password=%s",
                (email, password)
            )
            row = cur.fetchone()
        conn.close()
    except pymysql.MySQLError as e:
        return jsonify({'error': str(e)}), 500
    if not row:
        return jsonify({'error': 'Credenziali non valide'}), 401
    session['user_email'] = email
    session['user_nome']  = f"{row['nome']} {row['cognome']}"
    return jsonify({'email': email, 'nome': row['nome'], 'cognome': row['cognome']})


@app.route('/api/doxy/logout', methods=['POST'])
def api_doxy_logout():
    session.pop('user_email', None)
    session.pop('user_nome', None)
    return jsonify({'message': 'Disconnesso'})


# --------------------------------------------------------------------------- #
# API — Veicoli (richiede auth autista)
# --------------------------------------------------------------------------- #
@app.route('/api/veicoli', methods=['GET'])
def api_veicoli():
    err = _api_require_autista()
    if err:
        return err
    righe, db_err = fetch_table(
        "SELECT id_veicolo, targa, modello, matricola FROM veicolo ORDER BY targa"
    )
    if db_err:
        return jsonify({'error': db_err}), 500
    return jsonify(list(righe))


# --------------------------------------------------------------------------- #
# API — Segnalazioni
# --------------------------------------------------------------------------- #
@app.route('/api/segnalazioni', methods=['POST'])
def api_segnalazioni_crea():
    err = _api_require_autista()
    if err:
        return err
    id_veicolo  = request.form.get('id_veicolo', '').strip()
    descrizione = request.form.get('descrizione', '').strip()
    foto        = request.files.get('foto')
    if not id_veicolo or not descrizione:
        return jsonify({'error': 'id_veicolo e descrizione sono obbligatori'}), 400

    foto_path = None
    if foto and foto.filename:
        ext = os.path.splitext(secure_filename(foto.filename))[1].lower()
        if ext not in _ALLOWED_EXT:
            ext = '.jpg'
        filename  = str(uuid.uuid4()) + ext
        foto.save(os.path.join(UPLOAD_FOLDER, filename))
        foto_path = f'uploads/{filename}'

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(id_segnalazione), 0) + 1 AS nid FROM segnalazione")
            next_id = cur.fetchone()['nid']
            cur.execute(
                "INSERT INTO segnalazione "
                "(id_segnalazione, id_autista, id_veicolo, descrizione, foto_path) "
                "VALUES (%s,%s,%s,%s,%s)",
                (next_id, session['autista_id'], int(id_veicolo), descrizione, foto_path)
            )
        conn.commit(); conn.close()
    except pymysql.MySQLError as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'message': 'Segnalazione inviata', 'id_segnalazione': next_id}), 201


@app.route('/api/segnalazioni', methods=['GET'])
def api_segnalazioni_lista():
    err = _api_require_doxy()
    if err:
        return err
    righe, db_err = fetch_table(
        """SELECT s.id_segnalazione, s.descrizione, s.foto_path,
                  s.data_segnalazione, s.stato, s.letta,
                  a.nome AS autista_nome, a.cognome AS autista_cognome,
                  a.telefono AS autista_tel,
                  v.targa, v.modello
           FROM segnalazione s
           JOIN autista a ON s.id_autista = a.id_autista
           JOIN veicolo  v ON s.id_veicolo  = v.id_veicolo
           ORDER BY s.data_segnalazione DESC"""
    )
    if db_err:
        return jsonify({'error': db_err}), 500
    result = []
    for r in righe:
        row = dict(r)
        if row.get('data_segnalazione'):
            row['data_segnalazione'] = str(row['data_segnalazione'])
        row['letta'] = bool(row.get('letta'))
        result.append(row)
    return jsonify(result)


@app.route('/api/segnalazioni/nuove/count', methods=['GET'])
def api_segnalazioni_count():
    err = _api_require_doxy()
    if err:
        return err
    righe, db_err = fetch_table(
        "SELECT COUNT(*) AS count FROM segnalazione WHERE letta = FALSE"
    )
    if db_err:
        return jsonify({'error': db_err}), 500
    return jsonify({'count': righe[0]['count'] if righe else 0})


@app.route('/api/segnalazioni/<int:seg_id>', methods=['GET'])
def api_segnalazione_dettaglio(seg_id):
    err = _api_require_doxy()
    if err:
        return err
    righe, db_err = fetch_table(
        """SELECT s.id_segnalazione, s.descrizione, s.foto_path,
                  s.data_segnalazione, s.stato, s.letta,
                  a.nome AS autista_nome, a.cognome AS autista_cognome,
                  a.telefono AS autista_tel,
                  v.targa, v.modello
           FROM segnalazione s
           JOIN autista a ON s.id_autista = a.id_autista
           JOIN veicolo  v ON s.id_veicolo  = v.id_veicolo
           WHERE s.id_segnalazione = %s""",
        (seg_id,)
    )
    if db_err:
        return jsonify({'error': db_err}), 500
    if not righe:
        return jsonify({'error': 'Segnalazione non trovata'}), 404
    row = dict(righe[0])
    if row.get('data_segnalazione'):
        row['data_segnalazione'] = str(row['data_segnalazione'])
    row['letta'] = bool(row.get('letta'))
    return jsonify(row)


@app.route('/api/segnalazioni/<int:seg_id>/letta', methods=['PUT'])
def api_segnalazione_letta(seg_id):
    err = _api_require_doxy()
    if err:
        return err
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE segnalazione SET letta = TRUE WHERE id_segnalazione = %s", (seg_id,)
            )
        conn.commit(); conn.close()
    except pymysql.MySQLError as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'message': 'Segnalazione marcata come letta'})


# --------------------------------------------------------------------------- #
# PWA serve routes
# --------------------------------------------------------------------------- #
@app.route('/pwa/autista')
@app.route('/pwa/autista/')
def pwa_autista_index():
    return send_from_directory(os.path.join(_BASE_DIR, 'pwa-autista'), 'index.html')


@app.route('/pwa/autista/<path:filename>')
def pwa_autista_files(filename):
    return send_from_directory(os.path.join(_BASE_DIR, 'pwa-autista'), filename)


@app.route('/pwa/doxy')
@app.route('/pwa/doxy/')
def pwa_doxy_index():
    return send_from_directory(os.path.join(_BASE_DIR, 'pwa-doxy'), 'index.html')


@app.route('/pwa/doxy/<path:filename>')
def pwa_doxy_files(filename):
    return send_from_directory(os.path.join(_BASE_DIR, 'pwa-doxy'), filename)


if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    port  = int(os.environ.get('PORT', 8080))
    app.run(debug=debug, host='0.0.0.0', port=port)
