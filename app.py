import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
DB_PATH = os.path.join(BASE_DIR, 'timesheets.db')

app = Flask(__name__, template_folder=TEMPLATES_DIR)
app.secret_key = 'asc-secret'

def init_db():
    # Create database and tables if not exist
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
      CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','user'))
      )
    """)
    c.execute("""
      CREATE TABLE IF NOT EXISTS timesheets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        date TEXT,
        time TEXT,
        hours REAL,
        description TEXT
      )
    """)
    # Insert default admin if missing
    c.execute("SELECT 1 FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users VALUES (?,?,?)", ('admin','admin123','admin'))
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=('GET','POST'))
def login():
    error = None
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT role FROM users WHERE username=? AND password=?", (u,p))
        row = c.fetchone()
        conn.close()
        if row:
            session['user'] = u
            session['role'] = row[0]
            return redirect(url_for('dashboard'))
        error = 'Invalid credentials'
    return render_template('login.html', error=error)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('home'))
    if session['role']=='admin':
        conn = sqlite3.connect(DB_PATH)
        users = [r[0] for r in conn.execute("SELECT username FROM users")]
        conn.close()
        return render_template('admin_dashboard.html', users=users)
    return render_template('user_dashboard.html', username=session['user'])

@app.route('/submit', methods=('POST',))
def submit():
    if 'user' not in session:
        return redirect(url_for('home'))
    now = datetime.now()
    data = (
        session['user'],
        now.strftime('%Y-%m-%d'),
        now.strftime('%H:%M:%S'),
        float(request.form['hours']),
        request.form['description']
    )
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO timesheets (username,date,time,hours,description) VALUES (?,?,?,?,?)", data)
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/view/<user>')
def view(user):
    if session.get('role')!='admin':
        return redirect(url_for('home'))
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT date,time,hours,description FROM timesheets WHERE username=?", (user,)).fetchall()
    conn.close()
    return render_template('view_timesheets.html', user=user, rows=rows)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))
@app.route('/add_user', methods=['POST'])
def add_user():
    if 'user' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))

    username = request.form['username']
    password = request.form['password']
    role = request.form['role']

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                  (username, password, role))
        conn.commit()
        flash("✅ User added successfully!", "success")
    except sqlite3.IntegrityError:
        flash("⚠️ User already exists!", "error")
    conn.close()
    return redirect(url_for('dashboard'))

if __name__=='__main__':
    app.run(debug=True)
