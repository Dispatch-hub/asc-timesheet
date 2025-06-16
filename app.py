from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3, os
from datetime import datetime

BASE = os.path.dirname(__file__)
DB = os.path.join(BASE, 'timesheets.db')
TPL = os.path.join(BASE, 'templates')

app = Flask(__name__, template_folder=TPL)
app.secret_key = 'asc-secret'

DB_PATH = 'timesheets.db'

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # users table
    c.execute("""CREATE TABLE IF NOT EXISTS users (
         username TEXT PRIMARY KEY,
         password TEXT NOT NULL,
         role TEXT NOT NULL
    )""")
    # timesheets table
    c.execute("""CREATE TABLE IF NOT EXISTS timesheets (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         username TEXT,
         date TEXT, time TEXT,
         hours REAL,
         description TEXT
    )""")
    # default admin
    c.execute("SELECT 1 FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users VALUES (?,?,?)",
                  ('admin','admin123','admin'))
    conn.commit()
    conn.close()

@app.route('/', methods=['GET','POST'])
def login():
    error = None
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        conn = sqlite3.connect(DB)
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
        return redirect(url_for('login'))

    if session['role'] == 'admin':
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT username, role FROM users")
        users = c.fetchall()  # returns list of (username, role)
        conn.close()
        return render_template('admin_dashboard.html', users=users)

    else:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, date, time, hours, description FROM timesheets WHERE username=?", (session['user'],))
        entries = c.fetchall()
        conn.close()
        return render_template('user_dashboard.html',
                               username=session['user'],
                               entries=entries,
                               current_date=datetime.now().strftime('%Y-%m-%d'),
                               current_time=datetime.now().strftime('%H:%M'))


@app.route('/submit', methods=['POST'])
def submit():
    if 'user' not in session:
        return redirect(url_for('login'))

    date = request.form['date']         # 🗓️ selected date from input
    time = request.form['time']         # 🕒 selected time from input
    hours = float(request.form['hours'])  # ⏱️ hours worked
    desc = request.form['description']    # 📝 what they did

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO timesheets (username, date, time, hours, description)
        VALUES (?, ?, ?, ?, ?)
    """, (session['user'], date, time, hours, desc))
    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
from flask import Response
import csv
from io import StringIO

@app.route('/filter_user/<user>')
def filter_user(user):
    start = request.args.get('start_date', '')
    end = request.args.get('end_date', '')
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT date,time,hours,description FROM timesheets WHERE username=?"
    params = [user]
    if start and end:
        query += " AND date BETWEEN ? AND ?"
        params += [start, end]
    rows = conn.execute(query, tuple(params)).fetchall()
    conn.close()
    return render_template("view_timesheets.html", user=user, rows=rows)

@app.route('/filter_mine')
def filter_mine():
    if 'user' not in session:
        return redirect(url_for('home'))
    start = request.args.get('start_date', '')
    end = request.args.get('end_date', '')
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT date,time,hours,description FROM timesheets WHERE username=?"
    params = [session['user']]
    if start and end:
        query += " AND date BETWEEN ? AND ?"
        params += [start, end]
    rows = conn.execute(query, tuple(params)).fetchall()
    conn.close()
    return render_template("user_dashboard.html", username=session['user'], entries=rows,
                           current_date=datetime.now().strftime('%Y-%m-%d'),
                           current_time=datetime.now().strftime('%H:%M'))

@app.route('/filter_timesheets')
def filter_timesheets():
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    start = request.args.get('start_date', '')
    end = request.args.get('end_date', '')
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT username, date, time, hours, description FROM timesheets"
    params = []
    if start and end:
        query += " WHERE date BETWEEN ? AND ?"
        params += [start, end]
    rows = conn.execute(query, tuple(params)).fetchall()
    conn.close()
    # Render simple list or return CSV
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["User", "Date", "Time", "Hours", "Description"])
    for row in rows:
        writer.writerow(row)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=filtered_timesheets.csv"})

@app.route('/export_user/<user>')
def export_user(user):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT date,time,hours,description FROM timesheets WHERE username=?", (user,)).fetchall()
    conn.close()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Time", "Hours", "Description"])
    for row in rows:
        writer.writerow(row)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={"Content-Disposition": f"attachment;filename={user}_timesheets.csv"})

@app.route('/export_all')
def export_all():
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT username, date, time, hours, description FROM timesheets").fetchall()
    conn.close()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["User", "Date", "Time", "Hours", "Description"])
    for row in rows:
        writer.writerow(row)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=all_timesheets.csv"})

@app.route('/delete_user/<user>')
def delete_user(user):
    if session.get('role') != 'admin' or user == 'admin':
        return redirect(url_for('dashboard'))
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM users WHERE username=?", (user,))
    conn.execute("DELETE FROM timesheets WHERE username=?", (user,))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))
@app.route('/add_user', methods=['POST'])
def add_user():
    if session.get('role') != 'admin':
        return redirect(url_for('home'))

    new_u = request.form['new_username']
    new_p = request.form['new_password']
    new_r = request.form['new_role']

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (new_u, new_p, new_r))
        conn.commit()
        flash(f"User '{new_u}' added.", 'success')
    except sqlite3.IntegrityError:
        flash(f"Username '{new_u}' already exists.", 'error')
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/edit/<int:entry_id>', methods=['GET', 'POST'])
def edit_timesheet(entry_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if request.method == 'POST':
        new_date = request.form['date']
        new_time = request.form['time']
        new_hours = request.form['hours']
        new_desc = request.form['description']
        c.execute("""
            UPDATE timesheets
            SET date=?, time=?, hours=?, description=?
            WHERE id=?
        """, (new_date, new_time, new_hours, new_desc, entry_id))
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))

    # GET method
    c.execute("SELECT date, time, hours, description FROM timesheets WHERE id=?", (entry_id,))
    row = c.fetchone()
    conn.close()

    return render_template("edit_timesheet.html", entry_id=entry_id, entry=row)
@app.route('/view/<user>')
def view(user):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, date, time, hours, description FROM timesheets WHERE username=?", (user,))
    rows = c.fetchall()
    conn.close()
    return render_template('view_timesheets.html', user=user, rows=rows)
@app.route('/edit/<int:entry_id>', methods=['GET', 'POST'])
def edit_timesheet(entry_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if request.method == 'POST':
        new_date = request.form['date']
        new_time = request.form['time']
        new_hours = request.form['hours']
        new_desc = request.form['description']
        c.execute("UPDATE timesheets SET date=?, time=?, hours_worked=?, description=? WHERE id=?",
                  (new_date, new_time, new_hours, new_desc, entry_id))
        conn.commit()
        conn.close()
        flash("Timesheet updated!", "success")
        return redirect(url_for('dashboard'))
    else:
        c.execute("SELECT date, time, hours_worked, description FROM timesheets WHERE id=?", (entry_id,))
        entry = c.fetchone()
        conn.close()
        return render_template('edit_timesheet.html', entry=entry, entry_id=entry_id)

@app.route('/delete/<int:entry_id>')
def delete_timesheet(entry_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM timesheets WHERE id=?", (entry_id,))
    conn.commit()
    conn.close()
    flash("Timesheet entry deleted.", "success")
    return redirect(url_for('dashboard'))


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0")

