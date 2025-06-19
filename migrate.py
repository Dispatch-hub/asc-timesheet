import sqlite3

conn = sqlite3.connect('timesheets.db')
c = conn.cursor()

# Create invoices table if not exists
c.execute('''
    CREATE TABLE IF NOT EXISTS invoices (
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
        signature TEXT
    )
''')

conn.commit()
conn.close()

print("✅ Invoice table created or already exists.")
