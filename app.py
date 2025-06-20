# ✅ Alberta Safety Timesheet App with Invoice Features

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, make_response
import sqlite3
import os
import pandas as pd
from datetime import datetime
from io import BytesIO
import json
import pdfkit
import platform

# ✅ Define DB path first
DB_PATH = 'timesheets.db'

# ✅ Ensure 'status' column exists in invoices table
with sqlite3.connect(DB_PATH) as conn:
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE invoices ADD COLUMN status TEXT DEFAULT 'Pending'")
        conn.commit()
    except sqlite3.OperationalError:
        pass

app = Flask(__name__)
app.secret_key = 'alberta-safety-secret-key'

# --- PDFKit Configuration ---
if platform.system() == "Windows":
    config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')
else:
    config = pdfkit.configuration(wkhtmltopdf='/usr/bin/wkhtmltopdf')

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
    c.execute('''CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        invoice_number TEXT,
        date TEXT,
        customer TEXT,
        location TEXT,
        po TEXT,
        afe TEXT,
        customer_rep TEXT,
        safety_rep TEXT,
        subtotal REAL,
        gst REAL,
        total REAL,
        line_items TEXT,
        notes TEXT,
        signature TEXT,
        status TEXT DEFAULT 'Pending'
    )''')
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)",
              ('admin', 'admin123', 'admin'))
    conn.commit()
    conn.close()

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
        search_user = request.args.get('search_user', '').strip()
        c.execute("SELECT username, role FROM users")
        users = c.fetchall()

        if search_user:
            c.execute("SELECT id, username, date, time, hours_worked, description FROM timesheets WHERE username=? ORDER BY date DESC", (search_user,))
            timesheet_rows = c.fetchall()
            c.execute("SELECT * FROM invoices WHERE username=? ORDER BY id DESC", (search_user,))
            invoice_rows = c.fetchall()
        else:
            c.execute("SELECT id, username, date, time, hours_worked, description FROM timesheets ORDER BY username, date DESC")
            timesheet_rows = c.fetchall()
            c.execute("SELECT * FROM invoices ORDER BY id DESC")
            invoice_rows = c.fetchall()

        timesheets = {}
        for row in timesheet_rows:
            timesheets.setdefault(row[1], []).append(row)

        invoices = invoice_rows
        conn.close()
        return render_template('admin_dashboard.html', users=users, timesheets=timesheets, invoices=invoices)

    else:
        c.execute("SELECT id, date, time, hours_worked, description FROM timesheets WHERE username=? ORDER BY date DESC", (session['user'],))
        entries = c.fetchall()
        c.execute("SELECT * FROM invoices WHERE username=? ORDER BY id DESC", (session['user'],))
        invoices = c.fetchall()
        conn.close()
        return render_template('user_dashboard.html', username=session['user'], entries=entries, invoices=invoices)

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
    flash("Timesheet submitted successfully.", "success")
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
        flash("Timesheet updated.", "success")
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
    flash("Timesheet deleted.", "success")
    return redirect(url_for('dashboard'))

@app.route('/delete_user/<username>')
def delete_user(username):
    if 'user' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM timesheets WHERE username=?", (username,))
    c.execute("DELETE FROM invoices WHERE username=?", (username,))
    c.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()
    flash(f"User '{username}' and their records were deleted.", "success")
    return redirect(url_for('dashboard'))

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
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, role))
        conn.commit()
        flash("User added successfully.", "success")
    except sqlite3.IntegrityError:
        flash("User already exists!", "error")
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/create_invoice', methods=['GET', 'POST'])
def create_invoice():
    if 'user' not in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        data = request.form
        try:
            line_items = json.loads(data['line_items'])
            subtotal = float(data.get('subtotal', 0))
            gst = float(data.get('gst', 0))
            total = float(data.get('total', 0))
        except (ValueError, json.JSONDecodeError):
            flash("Invalid invoice data submitted.", "error")
            return redirect(url_for('create_invoice'))

        invoice_number = data['invoice_number']

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO invoices (
                username, invoice_number, date, customer, location, po, afe,
                customer_rep, safety_rep, subtotal, gst, total,
                line_items, notes, signature
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session['user'], invoice_number, data['date'], data['customer'], data['location'],
            data['po'], data['afe'], data['customer_rep'], data['safety_rep'],
            subtotal, gst, total, json.dumps(line_items), data['notes'], data['signature']
        ))
        conn.commit()
        conn.close()

        flash("Invoice created successfully!", "success")
        return redirect(url_for('dashboard'))

    else:
        invoice_number = f"ASC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        today = datetime.now().strftime('%Y-%m-%d')
        return render_template('create_invoice.html', invoice_number=invoice_number, today=today)

@app.route('/download_invoice/<int:invoice_id>')
def download_invoice(invoice_id):
    if 'user' not in session:
        return redirect(url_for('index'))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,))
    invoice = c.fetchone()
    conn.close()

    if not invoice:
        flash("Invoice not found.", "error")
        return redirect(url_for('dashboard'))

    invoice_dict = {
        'id': invoice[0], 'username': invoice[1], 'invoice_number': invoice[2], 'date': invoice[3],
        'customer': invoice[4], 'location': invoice[5], 'po': invoice[6], 'afe': invoice[7],
        'customer_rep': invoice[8], 'safety_rep': invoice[9], 'subtotal': float(invoice[10]),
        'gst': float(invoice[11]), 'total': float(invoice[12]), 'line_items': [],
        'notes': invoice[14], 'signature': invoice[15]
    }

    try:
        raw_items = json.loads(invoice[13])
        for item in raw_items:
            invoice_dict['line_items'].append({
                'description': item.get('description', ''),
                'qty': float(item.get('qty', 0)),
                'rate': float(item.get('rate', 0))
            })
    except Exception as e:
        flash(f"Error parsing line items: {e}", "error")
        return redirect(url_for('dashboard'))

    rendered = render_template('invoice_pdf.html', invoice=invoice_dict)
    pdf = pdfkit.from_string(rendered, False, configuration=config)
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=Invoice_{invoice_dict["invoice_number"]}.pdf'
    return response
@app.route('/export')
def export_all():
    if 'user' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM timesheets", conn)
    conn.close()
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Timesheets')
    output.seek(0)
    return send_file(output, download_name="all_timesheets.xlsx", as_attachment=True)

@app.route('/export/<username>')
def export_user(username):
    if 'user' not in session or (session['role'] != 'admin' and session['user'] != username):
        return redirect(url_for('index'))
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM timesheets WHERE username=?", conn, params=(username,))
    conn.close()
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=username)
    output.seek(0)
    return send_file(output, download_name=f"{username}_timesheets.xlsx", as_attachment=True)

@app.route('/update_invoice_status/<int:invoice_id>', methods=['POST'])
def update_invoice_status(invoice_id):
    if 'user' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))
    new_status = request.form['status']
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE invoices SET status=? WHERE id=?", (new_status, invoice_id))
    conn.commit()
    conn.close()
    flash("Invoice status updated successfully!", "success")
    return redirect(url_for('dashboard'))

@app.route('/reset_password/<username>', methods=['GET', 'POST'])
def reset_password(username):
    if 'user' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))
    if request.method == 'POST':
        new_password = request.form['new_password']
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE users SET password=? WHERE username=?", (new_password, username))
        conn.commit()
        conn.close()
        flash(f"Password for {username} updated successfully!", "success")
        return redirect(url_for('dashboard'))
    return render_template('reset_password.html', username=username)
@app.route('/delete_invoice/<int:invoice_id>', methods=['POST'])
def delete_invoice(invoice_id):
    if 'user' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM invoices WHERE id=?", (invoice_id,))
    conn.commit()
    conn.close()

    flash("Invoice deleted successfully.", "success")
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
 