# ASC Timesheet - Cleaned Version of app.py

from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'asc-secret-key'

DB_PATH = 'timesheets.db'

# --- Ensure DB Exists ---
if not os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'user'))
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS timesheets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        date TEXT,
        time TEXT,
        hours_worked REAL,
        description TEXT
    )''')
    c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
              ('admin', 'admin123', 'admin'))
    conn.commit()
    conn.close()

# --- Routes ---
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username=? AND password=?", (username, password))
    row = c.fetchone()
    conn.close()
    if row:
        session['user'] = username
        session['role'] = row[0]
        return redirect(url_for('dashboard'))
    return render_template('login.html', error="Invalid login")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('index'))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if session['role'] == 'admin':
        c.execute("SELECT username, role FROM users")
        users = c.fetchall()
        conn.close()
        return render_template('admin_dashboard.html', users=users)
    else:
        c.execute("SELECT id, date, time, hours_worked, description FROM timesheets WHERE username=? ORDER BY date DESC", (session['user'],))
        entries = c.fetchall()
        conn.close()
        return render_template('user_dashboard.html', username=session['user'], entries=entries)

@app.route('/submit', methods=['POST'])
def submit():
    if 'user' not in session:
        return redirect(url_for('index'))

    date = request.form.get('date') or datetime.now().strftime('%Y-%m-%d')
    time = request.form.get('time') or datetime.now().strftime('%H:%M:%S')
    hours = request.form['hours']
    desc = request.form['description']

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO timesheets (username, date, time, hours_worked, description) VALUES (?, ?, ?, ?, ?)",
              (session['user'], date, time, hours, desc))
    conn.commit()
    conn.close()

    flash("Entry added successfully.", "success")
    return redirect(url_for('dashboard'))

@app.route('/edit/<int:entry_id>', methods=['GET', 'POST'])
def edit_timesheet(entry_id):
    if 'user' not in session:
        return redirect(url_for('index'))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if request.method == 'POST':
        date = request.form['date']
        time = request.form['time']
        hours = request.form['hours']
        desc = request.form['description']
        c.execute("UPDATE timesheets SET date=?, time=?, hours_worked=?, description=? WHERE id=?",
                  (date, time, hours, desc, entry_id))
        conn.commit()
        conn.close()
        flash("Entry updated.", "success")
        return redirect(url_for('dashboard'))
    else:
        c.execute("SELECT date, time, hours_worked, description FROM timesheets WHERE id=?", (entry_id,))
        entry = c.fetchone()
        conn.close()
        return render_template('edit_timesheet.html', entry=entry, entry_id=entry_id)

@app.route('/delete/<int:entry_id>')
def delete_timesheet(entry_id):
    if 'user' not in session:
        return redirect(url_for('index'))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM timesheets WHERE id=?", (entry_id,))
    conn.commit()
    conn.close()
    flash("Entry deleted.", "success")
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
