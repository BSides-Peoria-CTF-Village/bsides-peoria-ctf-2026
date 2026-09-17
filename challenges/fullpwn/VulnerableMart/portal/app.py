import os
import sqlite3
import hashlib
import hmac
import uuid
import subprocess

from flask import (Flask, request, render_template, redirect, url_for,
                   make_response, jsonify, Response)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from reg import compute_registration_key  # noqa: F401  (recipe lives here)
from jwt_utils import JWT

app = Flask(__name__)

EXPECTED_REGISTRATION_KEY = os.environ.get("REGISTRATION_KEY", "")
SELLER_FLAG = os.environ.get("SELLER_FLAG", "<SELLER_FLAG not set>")
PORTAL_ADMIN_FLAG = os.environ.get("PORTAL_ADMIN_FLAG", "<PORTAL_ADMIN_FLAG not set>")

DB_PATH = "portal.db"
COOKIE = "session_token"
KID = "portal-rsa-1"

# RSA keypair for JWT signing, generated at startup. The public half is
# published (jwks + pem) and is reused by the verifier as the HS256 secret.
_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_priv_pem = _key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)
_pub_pem = _key.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo,
)
jwt = JWT(_priv_pem, _pub_pem, KID)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "username TEXT UNIQUE NOT NULL, "
        "pw_hash TEXT NOT NULL, "
        "role TEXT NOT NULL DEFAULT 'seller')"
    )
    conn.commit()
    conn.close()


def hpw(password):
    return hashlib.sha256(password.encode()).hexdigest()


def current_user():
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    try:
        return jwt.verify(token)
    except Exception:
        return None


# --- Invoice PDF generation ---
# The invoice fields are rendered into HTML unsanitized and converted to PDF by
# wkhtmltopdf with local-file-access enabled. wkhtmltopdf runs as www-data with a
# scrubbed environment, so an injected <iframe src="file://..."> can read
# world-readable files (the intended LFI) but NOT flask's secrets or the root flag.
RENDER_USER = "www-data"


def build_invoice_html(client, email, items, notes):
    rows = ""
    for desc, qty, price in items:
        rows += f"<tr><td>{desc}</td><td>{qty}</td><td>{price}</td></tr>"
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body {{ font-family: sans-serif; }}
table {{ width:100%; border-collapse:collapse; }} td,th {{ border:1px solid #ccc; padding:6px; }}
</style></head><body>
<h1>VulnMart Invoice</h1>
<p><strong>Bill to:</strong> {client}<br><strong>Email:</strong> {email}</p>
<table><tr><th>Item</th><th>Qty</th><th>Price</th></tr>{rows}</table>
<h3>Notes</h3>
<div>{notes}</div>
</body></html>"""


def render_invoice_pdf(html: str) -> bytes:
    rid = uuid.uuid4().hex
    html_path = f"/tmp/inv_{rid}.html"
    pdf_path = f"/tmp/inv_{rid}.pdf"
    with open(html_path, "w") as f:
        f.write(html)
    os.chmod(html_path, 0o644)  # readable by the dropped www-data renderer
    try:
        # xvfb-run gives Debian's wkhtmltopdf the X display it needs (headless).
        proc = subprocess.run(
            ["xvfb-run", "-a",
             "wkhtmltopdf", "--enable-local-file-access", "--quiet",
             html_path, pdf_path],
            timeout=40,
            user=RENDER_USER, group=RENDER_USER,
            env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if proc.returncode != 0 or not os.path.exists(pdf_path):
            raise RuntimeError(
                f"wkhtmltopdf rc={proc.returncode}: "
                f"{proc.stderr.decode(errors='replace')[:2000]}"
            )
        with open(pdf_path, "rb") as f:
            return f.read()
    finally:
        for p in (html_path, pdf_path):
            try:
                os.remove(p)
            except OSError:
                pass


@app.route('/')
def index():
    return render_template('portal_index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        reg_key = request.form.get('registration_key', '').strip()

        if not EXPECTED_REGISTRATION_KEY:
            error = "Registration is temporarily disabled."
        elif not (username and password and reg_key):
            error = "All fields are required."
        elif not hmac.compare_digest(reg_key.lower(), EXPECTED_REGISTRATION_KEY.lower()):
            error = "Invalid registration key."
        else:
            conn = sqlite3.connect(DB_PATH)
            try:
                conn.execute(
                    "INSERT INTO users (username, pw_hash, role) VALUES (?, ?, 'seller')",
                    (username, hpw(password)),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                error = "That username is already registered."
            finally:
                conn.close()
            if not error:
                return redirect(url_for('login', registered=1))

    return render_template('register.html', error=error)


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    registered = request.args.get('registered')
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT username, pw_hash, role FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        conn.close()
        if row and hmac.compare_digest(row[1], hpw(password)):
            token = jwt.sign({"username": row[0], "role": row[2]})
            resp = make_response(redirect(url_for('dashboard')))
            resp.set_cookie(COOKIE, token, httponly=True, samesite='Lax')
            return resp
        error = "Invalid username or password."
    return render_template('login.html', error=error, registered=registered)


@app.route('/dashboard')
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    return render_template('dashboard.html', user=user, flag=SELLER_FLAG)


@app.route('/admin')
def admin():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    if user.get('role') != 'admin':
        return render_template('admin_denied.html', user=user), 403
    return render_template('admin.html', user=user, flag=PORTAL_ADMIN_FLAG)


@app.route('/admin/invoices', methods=['GET'])
def invoices():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    if user.get('role') != 'admin':
        return render_template('admin_denied.html', user=user), 403
    return render_template('invoices.html', user=user)


@app.route('/admin/invoices/pdf', methods=['POST'])
def invoices_pdf():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    if user.get('role') != 'admin':
        return render_template('admin_denied.html', user=user), 403

    client = request.form.get('client_name', '')
    email = request.form.get('client_email', '')
    notes = request.form.get('notes', '')
    items = list(zip(
        request.form.getlist('item_desc'),
        request.form.getlist('item_qty'),
        request.form.getlist('item_price'),
    ))
    html = build_invoice_html(client, email, items, notes)
    try:
        pdf = render_invoice_pdf(html)
    except Exception as e:
        # DEBUG: surface the real error while bringing the box up. Tighten before the event.
        import traceback
        traceback.print_exc()
        return f"Invoice rendering failed: {e}", 500

    resp = make_response(pdf)
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = 'inline; filename="invoice.pdf"'
    return resp


@app.route('/.well-known/jwks.json')
def jwks():
    return jsonify(jwt.jwks())


@app.route('/jwt/public.pem')
def public_pem():
    return Response(_pub_pem, mimetype='application/x-pem-file')


@app.route('/logout')
def logout():
    resp = make_response(redirect(url_for('index')))
    resp.delete_cookie(COOKIE)
    return resp


init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
