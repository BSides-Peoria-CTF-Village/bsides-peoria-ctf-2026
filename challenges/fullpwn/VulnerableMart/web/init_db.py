import os
import sqlite3
import base64


def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    admin_password = os.environ.get("ADMIN_PASSWORD", "supersecretadmin")
    encoded = base64.b64encode(admin_password.encode()).decode()
    cursor.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)",
                   ('admin', encoded))

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            description TEXT NOT NULL
        )
    ''')

    products = [
        ('T-shirt', 20, 'A stylish white T-shirt. Complete a purchase to receive your reward flag!'),
        ('Coffee Mug', 15, 'For late-night hacking.'),
        ('Sticker Pack', 5, 'High-quality stickers.')
    ]
    cursor.executemany("INSERT INTO products (name, price, description) VALUES (?, ?, ?)", products)

    conn.commit()
    conn.close()
    print("Database initialized.")


if __name__ == "__main__":
    init_db()
