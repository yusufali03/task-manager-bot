import sqlite3

DB_FILE = "tasks.db"

def init_database():

    # Connect to SQLite database
    db = sqlite3.connect(DB_FILE)
    cursor = db.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT UNIQUE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            description TEXT NOT NULL,
            sender TEXT NOT NULL,
            recipient INTEGER NOT NULL,
            due_date TEXT NOT NULL,
            importance TEXT CHECK (importance IN ('Low', 'Average', 'High')),
            status TEXT CHECK (status IN ('New', 'Accepted', 'Completed')) DEFAULT 'New'
        )
    ''')

    db.commit()
    db.close()

def add_user(user_id, username):
    db = sqlite3.connect(DB_FILE)
    cursor = db.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    db.commit()
    db.close()

def get_user_id(username):
    db = sqlite3.connect(DB_FILE)
    cursor = db.cursor()
    cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    db.close()

    return user[0] if user else None

