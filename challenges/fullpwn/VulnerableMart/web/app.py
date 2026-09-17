import sqlite3
import os
import base64
from flask import Flask, request, render_template, session, redirect, url_for

from protected_routes import bp as protected_bp
from dev import dev as dev_bp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_key_12345")

app.register_blueprint(protected_bp)
app.register_blueprint(dev_bp)

STAFF_USERNAME = "staff"
STAFF_PASSWORD = "Wint3r_St0ck_R00m_2026!"


def get_db():
    conn = sqlite3.connect('database.db')
    return conn


@app.route('/')
def index():
    page = request.args.get('template')
    if page:
        try:
            return open(os.path.join('templates', page)).read()
        except Exception:
            return "Error loading page", 404
    return render_template('index.html')


@app.route('/search')
def search():
    q = request.args.get('q', '')
    conn = get_db()
    items = []
    try:
        if q:
            query = f"SELECT name, price, description, id FROM products WHERE name LIKE '%{q}%'"
            items = conn.execute(query).fetchall()
        else:
            items = conn.execute("SELECT name, price, description, id FROM products").fetchall()
    except Exception:
        pass
    finally:
        conn.close()

    return render_template('search.html', items=items)


@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    item_id = request.form.get('item_id')
    if 'cart' not in session:
        session['cart'] = []

    session['cart'].append(item_id)
    session.modified = True
    return redirect(url_for('cart'))


@app.route('/cart')
def cart():
    cart_ids = session.get('cart', [])
    items = []
    total_price = 0

    if cart_ids:
        conn = get_db()
        try:
            placeholders = ','.join('?' for _ in cart_ids)
            query = f"SELECT name, price, description, id FROM products WHERE id IN ({placeholders})"
            items = conn.execute(query, cart_ids).fetchall()
        except Exception:
            pass
        finally:
            conn.close()

    for item in items:
        total_price += item[1]

    return render_template('cart.html', items=items, total=total_price)


@app.route('/checkout', methods=['POST'])
def checkout():
    is_promo_valid = request.form.get('promo_valid', 'false')

    if 'cart' not in session or not session['cart']:
        return "Error: Cart is empty.", 400

    if is_promo_valid == 'true':
        session.pop('cart', None)
        checkout_flag = os.environ.get("CHECKOUT_FLAG", "<CHECKOUT_FLAG not set>")
        return render_template('success.html', flag=checkout_flag)

    return "Error: Payment failed. Invalid Promo Code or Insufficient Funds.", 400


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == STAFF_USERNAME and password == STAFF_PASSWORD:
            session['user'] = 'staff'
            return redirect(url_for('protected.staff_dashboard'))

        try:
            encoded_password = base64.b64encode(password.encode()).decode()
        except Exception:
            encoded_password = password

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?",
                            (username, encoded_password)).fetchone()
        conn.close()

        if user:
            session['user'] = user[1]
            return redirect(url_for('protected.admin_dashboard'))

        return "Invalid Credentials", 401
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))


if __name__ == '__main__':
    if not os.path.exists('database.db'):
        try:
            import init_db
            init_db.init_db()
        except Exception:
            pass

    app.run(host='0.0.0.0', port=80)
