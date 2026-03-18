import datetime
import shutil

from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, hashlib
from functools import wraps

app = Flask(__name__)
app.secret_key = 'a4f8b23c9d67e92b7f1e3a3d8e2c1b9a'

# ---------------------------
# Hash seguro
# ---------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ---------------------------
# Inicializar base de datos
# ---------------------------
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS personas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            edad INTEGER NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS privilegios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rol_privilegio (
            rol_id INTEGER,
            privilegio_id INTEGER,
            PRIMARY KEY (rol_id, privilegio_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuario_rol (
            usuario_id INTEGER,
            rol_id INTEGER,
            PRIMARY KEY (usuario_id, rol_id)
        )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS registros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    accion TEXT,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')


    # Roles
    cursor.execute("INSERT OR IGNORE INTO roles (nombre) VALUES ('admin')")
    cursor.execute("INSERT OR IGNORE INTO roles (nombre) VALUES ('user')")

    # Privilegios
    privilegios = ['crear', 'leer', 'actualizar', 'eliminar']
    for p in privilegios:
        cursor.execute("INSERT OR IGNORE INTO privilegios (nombre) VALUES (?)", (p,))

    # Obtener IDs
    cursor.execute("SELECT id FROM roles WHERE nombre='admin'")
    admin_id = cursor.fetchone()[0]

    cursor.execute("SELECT id FROM roles WHERE nombre='user'")
    user_id = cursor.fetchone()[0]

    cursor.execute("SELECT id FROM privilegios")
    privilegios_ids = cursor.fetchall()

    # Admin → todos
    for pid in privilegios_ids:
        cursor.execute("INSERT OR IGNORE INTO rol_privilegio VALUES (?, ?)", (admin_id, pid[0]))

    # User → leer y actualizar
    cursor.execute("SELECT id FROM privilegios WHERE nombre='leer'")
    leer_id = cursor.fetchone()[0]

    cursor.execute("SELECT id FROM privilegios WHERE nombre='actualizar'")
    actualizar_id = cursor.fetchone()[0]

    cursor.execute("INSERT OR IGNORE INTO rol_privilegio VALUES (?, ?)", (user_id, leer_id))
    cursor.execute("INSERT OR IGNORE INTO rol_privilegio VALUES (?, ?)", (user_id, actualizar_id))

    # Crear usuario admin
    cursor.execute("SELECT id FROM usuarios WHERE username='admin'")
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO usuarios (username, password) VALUES (?, ?)",
            ('admin', hash_password('Admin#2026'))
        )

    cursor.execute("SELECT id FROM usuarios WHERE username='admin'")
    admin_user_id = cursor.fetchone()[0]

    cursor.execute("INSERT OR IGNORE INTO usuario_rol VALUES (?, ?)", (admin_user_id, admin_id))

    conn.commit()
    conn.close()

init_db()

# ---------------------------
# Decoradores
# ---------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Inicia sesión primero.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def privilege_required(nombre_privilegio):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):

            if 'username' not in session:
                return redirect(url_for('login'))

            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()

            cursor.execute("""
                SELECT p.nombre
                FROM usuarios u
                JOIN usuario_rol ur ON u.id = ur.usuario_id
                JOIN roles r ON ur.rol_id = r.id
                JOIN rol_privilegio rp ON r.id = rp.rol_id
                JOIN privilegios p ON rp.privilegio_id = p.id
                WHERE u.username = ?
            """, (session['username'],))

            privilegios = [row[0] for row in cursor.fetchall()]
            conn.close()

            if nombre_privilegio not in privilegios:
                flash('No tienes permiso para esta acción.', 'danger')
                return redirect(url_for('index'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ---------------------------
# Autenticación
# ---------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_password(request.form['password'])

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO usuarios (username, password) VALUES (?, ?)",
                (username, password)
            )

            user_id = cursor.lastrowid

            cursor.execute("SELECT id FROM roles WHERE nombre='user'")
            role_id = cursor.fetchone()[0]

            cursor.execute(
                "INSERT INTO usuario_rol (usuario_id, rol_id) VALUES (?, ?)",
                (user_id, role_id)
            )

            conn.commit()
            flash('Cuenta creada correctamente ✅', 'success')
            return redirect(url_for('login'))

        except sqlite3.IntegrityError:
            flash('El usuario ya existe ⚠️', 'danger')

        finally:
            conn.close()

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_password(request.form['password'])

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        cursor.execute("""
            SELECT u.username
            FROM usuarios u
            WHERE u.username=? AND u.password=?
        """, (username, password))

        user = cursor.fetchone()
        conn.close()

        if user:
            session['username'] = user[0]
            flash('Bienvenido 👋', 'success')
            return redirect(url_for('index'))
        else:
            flash('Credenciales incorrectas ❌', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
@app.route('/admin/logs')
@app.route('/control_panel')
@login_required
@privilege_required('leer')
def control_panel():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM registros ORDER BY fecha DESC")
    logs = cursor.fetchall()

    conn.close()

    return render_template('control_panel.html', logs=logs)

@app.route('/admin/backup')
@login_required
def backup_bd():

    if session['username'] != 'admin':
        flash("Solo el administrador puede hacer backup", "danger")
        return redirect(url_for('index'))

    fecha = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    backup_file = f"backup_empresa_{fecha}.db"

    try:
        shutil.copy("database.db", backup_file)

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO registros (accion) VALUES (?)",
            (f"backup creado: {backup_file}",)
        )

        conn.commit()
        conn.close()

        flash("Backup creado correctamente ✅", "success")

    except Exception as e:
        flash(f"Error en backup: {e}", "danger")

    return redirect(url_for('index'))

# ---------------------------
# CRUD
# ---------------------------

@app.route('/')
@login_required
@privilege_required('leer')
def index():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Personas
    cursor.execute("SELECT * FROM personas")
    personas = cursor.fetchall()

    # Privilegios
    cursor.execute("""
        SELECT p.nombre
        FROM usuarios u
        JOIN usuario_rol ur ON u.id = ur.usuario_id
        JOIN roles r ON ur.rol_id = r.id
        JOIN rol_privilegio rp ON r.id = rp.rol_id
        JOIN privilegios p ON rp.privilegio_id = p.id
        WHERE u.username = ?
    """, (session['username'],))

    privilegios = [row[0] for row in cursor.fetchall()]


    logs = []
    if session['username'] == 'admin':
        cursor.execute("SELECT * FROM registros ORDER BY fecha DESC")
        logs = cursor.fetchall()

    conn.close()

    return render_template(
        'index.html',
        personas=personas,
        privilegios=privilegios,
        logs=logs  
    )


@app.route('/add', methods=['POST'])
@privilege_required('crear')
def add():
    nombre = request.form['nombre']
    edad = request.form['edad']

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    cursor.execute(
    "INSERT INTO personas (nombre, edad) VALUES (?, ?)",
    (nombre, edad)
)
    cursor.execute(
    "INSERT INTO registros (accion) VALUES (?)",
    ('crear',)
)


    conn.commit()

    conn.close()

    return redirect(url_for('index'))


@app.route('/edit/<int:id>')
@privilege_required('actualizar')
def edit(id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM personas WHERE id=?", (id,))
    persona = cursor.fetchone()

    cursor.execute(
        "INSERT INTO registros (accion) VALUES (?)",
        ('leer',)
    )

    conn.commit()
    conn.close()

    return render_template('edit.html', persona=persona)


@app.route('/update/<int:id>', methods=['POST'])
@privilege_required('actualizar')
def update(id):
    nombre = request.form['nombre']
    edad = request.form['edad']

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE personas SET nombre=?, edad=? WHERE id=?",
        (nombre, edad, id)
    )

    cursor.execute(
        "INSERT INTO registros (accion) VALUES (?)",
        ('actualizar',)
    )

    conn.commit()
    conn.close()

    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
@privilege_required('eliminar')
def delete(id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM personas WHERE id=?", (id,))
    cursor.execute(
    "INSERT INTO registros (accion) VALUES (?)",
    ('eliminar',)
)

    conn.commit()
    conn.close()

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
