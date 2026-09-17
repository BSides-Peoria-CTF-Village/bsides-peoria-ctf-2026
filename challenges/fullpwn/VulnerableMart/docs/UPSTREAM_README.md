# BSides-Peoria-WebVillage-2026
Repo for the web app village CTF at BSides Peoria 2026.

A multi-step web challenge ("Vulnerable Mart"), a separate command-injection box,
and a second "Seller Portal" app locked behind the first that ends in a
PDF-LFI → SSH → Chef-root capstone. **8 flags**, all randomized per deploy and
stored only in environment variables.

## Layout
```
web/           # Flask shop app  (8888->80)  — LFI, SQLi, base64, auth, param-tampering
maintenance/   # Isolated box    (50050)     — command injection / shell + mysterioususer
portal/        # Seller portal   (8889->80, ssh 50022) — reg lock, JWT confusion, PDF-LFI→SSH→Chef
gen_flags.py   # Generates flags.env: randomized flags + secrets + the portal lock
flags.env      # (gitignored) generated env, consumed by docker-compose at runtime
SOLUTION.md    # Full solve writeup + red herrings + QA checklist (organizers only)
```

The three services are deliberately **separate containers**. The maintenance box
holds no web-app database, no web source, and no web flags — so RCE there cannot
shortcut the chain (its only secrets are `SHELL_FLAG` and the `mysterioususer`
shadow hash, both *meant* to be taken via RCE). The portal only ever holds the
final registration key and its own two flags — never the raw inputs that derive them.

## Setup
Requirements: Docker + Docker Compose, and a Python 3 with either the stdlib
`crypt` module or `openssl` on `PATH` (gen_flags.py needs one to build
`mysterioususer`'s shadow hash).

```bash
# 1. Generate randomized flags + secrets. Writes flags.env (gitignored) and prints
#    the flags for your scoreboard. Run once per deploy.
python gen_flags.py              # use --force to overwrite an existing flags.env

# 2. Build & run all three services.
docker compose up --build -d

# 3. Endpoints:
#    web  (shop)       http://localhost:8888     (host 8888 -> container 80)
#    portal (sellers)  http://localhost:8889
#    maintenance       localhost:50050           (raw TCP — nc / port-scan target)
```

Re-roll flags for a new event (rebuild so containers re-read flags and re-seed):
```bash
python gen_flags.py --force && docker compose up -d --build
```

**Validate the whole path** with the automated solver (captures all 8 flags;
exits non-zero if any step breaks — handy after changes):
```bash
python solve.py                 # localhost + compose ports; --host for a remote/VPN target
python solve.py --verbose       # also prints recovered creds/secrets
```
Needs `requests pypdf paramiko` (`pip install`); uses the real exploit for each step.
Port mappings live in `docker-compose.yml`. View the current flags anytime with
`grep _FLAG flags.env`. Local (no-Docker) dev for the shop app only:
```bash
cd web && set -a && . ../flags.env && set +a && python init_db.py && python app.py
```

## Intended Path
1. **Template hint in page source** — HTML comment on `/` hints at `?template=`.
2. **LFI via `?template=`** — `?template=../app.py` reveals source: the SQLi in
   `/search`, the base64 login logic, and the **staff credential** (a credential,
   not a flag).
3. **UNION-based SQLi** on `/search?q=` — dump the `users` table to get the admin
   username and stored password value.
4. **Base64 decode** the dumped admin password value once to get the plaintext.
5. **Log in** — as `staff` (creds from step 2 → `STAFF_FLAG`) and as `admin`
   (creds from steps 3–4 → `ADMIN_FLAG`, shown in the panel header).
6. **Checkout parameter tampering** — intercept `/checkout` and flip the hidden
   `promo_valid` field to `true` (`CHECKOUT_FLAG`).
7. **(Separate box) port 50050** — port-scan finds the maintenance interface;
   command injection in the `ping` handler gives a shell → read `/root/flag.txt`
   (`SHELL_FLAG`).
8. **Unlock the Seller Portal (`:8889`)** — combine the admin password (steps 3–4)
   with `mysterioususer`'s `/etc/shadow` hash (step 7 RCE) to derive the
   registration key: `SHAKE256(shadow_hash + admin_password)` (512-bit hex). The
   app-1 admin page `/admin/seller-keys` documents the recipe. Register at
   `:8889/register`.
9. **Seller login → `SELLER_FLAG`** — log in; the seller dashboard shows the flag
   and nudges toward an admin console.
10. **JWT RS256→HS256 confusion → `PORTAL_ADMIN_FLAG`** — the portal verifies the
    session JWT using the alg from its header and reuses the RSA public key (from
    `/.well-known/jwks.json` / `/jwt/public.pem`) as the HMAC secret. Forge an
    `alg:HS256`, `role:admin` token signed with the public key → `/admin`.
11. **Invoice PDF → LFI** — the admin Invoice Generator renders user fields to PDF
    via `wkhtmltopdf` (local-file-access on). Inject `<iframe src="file://...">`
    (runs as www-data) to read `/var/mail/jdoe`.
12. **SSH foothold → `USER_FLAG`** — the mail leaks `jdoe`'s SSH password;
    `ssh -p 50022 jdoe@host` → `~/user.txt`.
13. **Chef privesc → `ROOT_FLAG`** — `jdoe` may `sudo chef-apply` a recipe that runs
    as root (GTFOBins-style) → root shell → `/root/root.txt`. **End of CTF.**

See [`SOLUTION.md`](SOLUTION.md) for the full step-by-step exploitation writeup,
the red-herring inventory, and a QA checklist.

## Flags: randomization, secrecy & forced ordering

**Randomized per deploy.** `gen_flags.py` mints fresh random flags and secrets
every run (e.g. `CTF{...}` with a random suffix, a high-entropy admin password,
the `mysterioususer` password, and the derived registration key). Nothing is
hardcoded, so flags differ between events and can't be shared between teams or
copied from a past run. The script prints the flags for your scoreboard.

**Kept from players.** Flags live **only** in environment variables, injected at
runtime via docker-compose `env_file: flags.env`. `flags.env` is gitignored and
never baked into an image. Concretely, players can't reach them because:
- **Source never contains a flag.** App code reads `os.environ[...]`; the in-source
  defaults are literally `<NAME not set>`. So the LFI (which *can* read source) and
  the `dev.py` decoy leak no flags.
- **The LFI can't pivot to flags.** `init_db.py` is deleted at container start (so
  the admin hash can't be read from source), the sqlite DB fails text-decode via
  LFI, and SSTI was removed — the only LFI loot is the staff *credential*.
- **The RCE box is isolated.** Command injection on `:50050` yields only
  `SHELL_FLAG` and the `mysterioususer` hash; the web DB/source/flags aren't there.
- **The portal never holds the raw inputs.** It only gets the precomputed
  `REGISTRATION_KEY` and its own two flags; the admin password and shadow hash that
  derive the key are not present on that host.

**Forced (mostly) in order.** Each flag is gated behind the artifacts of earlier
steps, so the intended path is largely enforced rather than suggested:

```
recon ─LFI→ staff creds ───────────────────────────────────→ STAFF_FLAG
        └─LFI→ (discover SQLi) ─SQLi→ admin b64 ─decode→ admin login → ADMIN_FLAG
                                                              │ (admin password)
cart ─param-tamper→ CHECKOUT_FLAG        (independent side-quest)
                                                              │
port-scan :50050 ─cmd-injection→ root RCE → SHELL_FLAG        │
                       └→ read /etc/shadow (mysterioususer hash)
                                          │                   │
                                          ▼                   ▼
                 REGISTRATION_KEY = SHAKE256(shadow_hash + admin_password)
                                          │
                          portal /register → /login → SELLER_FLAG
                                          │
                       JWT RS256→HS256 confusion → /admin → PORTAL_ADMIN_FLAG
                                          │
                  admin Invoice Generator → PDF render (wkhtmltopdf, www-data)
                                          │  inject <script> XHR file:///var/mail/jdoe
                          read /var/mail/jdoe → jdoe SSH password
                                          │
                       ssh :50022 jdoe → USER_FLAG
                                          │
              sudo chef-apply <recipe> (runs as root) → ROOT_FLAG  ← END
```

The two early branches (web exploitation → **admin password**, and port-scan →
**root RCE / shadow hash**) must **both** be completed before the portal will
register a seller — that convergence is the lock that forces players through the
earlier content. From there the portal sub-chain is linear (register → login →
seller flag → privesc → admin flag). Deliberate non-linearities, for organizer
awareness: **checkout tampering** (`CHECKOUT_FLAG`) is an independent side-quest
doable anytime, and the **shell box** is reachable independently — it only becomes
*required* when deriving the registration key.

## Project status & handoff

**Done & validated end-to-end (8 flags).** The full intended path works against a
real `docker compose` deployment, confirmed by the automated solver `solve.py`
(captures 8/8): shop chain (LFI → SQLi → base64 → staff/admin login → checkout
tampering), isolated command-injection box, the seller portal (registration lock →
seller flag → JWT RS256/HS256 confusion → portal admin flag), and the capstone
(invoice PDF LFI → SSH foothold → Chef privesc to root).

Capstone infra notes (resolved): the portal image pins **Debian bullseye**
(trixie/bookworm dropped `wkhtmltopdf`) and renders headless via `xvfb`; Chef Infra
Client is installed (cinc fallback) under `/usr/local/bin/chef-apply` with its
**license pre-accepted** at build so the privesc is a clean `sudo chef-apply`.

**Open (not started) — see the proposal below:**
- **Connectivity** — per-team/per-user VPN configs + VPN-specific flags.
- **Scoreboard** — a public standings view and a private ops view (logs/details).

**Before the event (cleanup):** the portal invoice route currently returns the raw
`wkhtmltopdf` error on failure (marked `DEBUG` in `portal/app.py`) — revert it to a
generic message so it doesn't aid players.

**Regression testing.** After any change/rebuild, run `python solve.py` — it walks
every step with the real exploit and exits non-zero if any flag breaks.

**For contributors:** each service is a self-contained folder with its own
Dockerfile. To add a flag: generate it in `gen_flags.py` (and document it in
`flags.env.example`), inject it via `docker-compose.yml` `env_file`, and read it
with `os.environ` in the app — **never hardcode a flag in source**. Whenever you
add or change a step, update `SOLUTION.md` (path + QA checklist) and `solve.py`.

## Action Items
- [x] Document Setup Instructions
- [x] Create Setup Script (randomize flags, etc) — `gen_flags.py`
- [x] Document Expected Exploitation Steps for each vuln — see `SOLUTION.md`
- [x] (Optional) Add content to confuse LLMs — `web/dev.py` decoy module (LFI-readable, wordlist-friendly name; all leads inert, see `SOLUTION.md` "Red herrings")
- [x] Validate admin password isn't common enough to brute-force — now a high-entropy `token_urlsafe(18)` (not in any wordlist)
- [x] Make the admin password longer/more complex. (Brute-force throttling intentionally NOT added — relying on password entropy; revisit if needed)
- [x] Make checkout clearer that ordering the T-shirt yields a flag (product description updated)
- [x] Validate the shell is not on the web server — moved to its own isolated container with no DB/source/flags
- [x] Validate reading source in step 2 can't read any flag — all flags moved to env; `init_db.py` is removed at container start so the admin hash can't be LFI'd
- [ ] Solve how users connect — VPN files? (per-team VPN configs to log attempts).
      Two designs drafted in "Proposal: VPN per-user flags & scoreboard" above — pending decision.

## Future Ideas
- [x] Second web app (`portal/`, `:8889`) requiring a registration key from the first app
  - [x] Registration locked behind admin password + `mysterioususer` shadow hash (root RCE on 50050).
        Key = `SHAKE256(shadow_hash + admin_password)`; validation implemented + tested.
  - [x] JWT RS256→HS256 algorithm confusion (jwks + pem endpoints, seller→admin) — `SELLER_FLAG` + `PORTAL_ADMIN_FLAG`
  - [x] Invoice-to-PDF on the admin page; `wkhtmltopdf` LFI via `file://` iframe (runs as www-data)
  - [x] LFI reads `/var/mail/jdoe` → SSH password → `ssh :50022` → `USER_FLAG`
  - [x] Chef `sudo chef-apply` GTFOBins privesc → root → `ROOT_FLAG` (end of CTF)

## Proposal: VPN per-user flags & scoreboard (FOR REVIEW — not built)

Two candidate designs for getting players connected, attributing/scoring their
work, and (optionally) making flags **specific to each VPN identity** so a leaked
flag is useless to anyone else. Pick one (or a blend) before implementing. Both
assume **WireGuard** for the VPN (simple per-peer configs, easy source-IP
attribution); OpenVPN is a drop-in alternative if preferred.

Shared vocabulary: a *competitor* = one VPN identity = one WireGuard peer (a team
or an individual). The scoreboard's **public** view shows standings/first-blood; the
**private/ops** view shows per-competitor logs and submission history.

### Option 1 — Per-competitor isolated stacks (isolation; strongest anti-cheat)
- **Infra:** each competitor gets their own full `docker compose` stack
  (`docker compose -p comp<N> …`) on its own internal network, seeded with its own
  `gen_flags.py` run → **unique flags per competitor**. Their WireGuard peer is
  firewalled to only reach their stack.
- **Flags:** already env-injected and per-deploy random, so this needs **no app
  changes** — just run `gen_flags.py` per stack and record the flag set.
- **Scoreboard:** central service stores `{competitor → flag set}`; a submission is
  valid only if it's in *that* competitor's set, so a shared flag scores nothing for
  anyone else. (CTFd can host the UI; per-competitor flags need a small plugin or a
  custom validation endpoint.)
- **Pros:** true isolation; sharing is pointless; clean attribution; zero changes to
  the challenge apps. **Cons:** N× compute/disk (the portal image is heavy:
  Chef + wkhtmltopdf); needs an orchestrator to spin up/tear down stacks and a
  per-competitor-flag scoreboard. Best when competitor count is small/known.

### Option 2 — Single shared instance + identity-derived flags (light infra; more app work)
- **Infra:** one shared stack. A reverse proxy / VPN gateway maps each peer's
  **source IP → competitor_id** and passes that identity to the apps.
- **Flags:** instead of a static env flag, each flag is **derived per competitor**,
  e.g. `CTF{<step>_<HMAC(server_secret, competitor_id|step_id)>}`. The web apps emit
  the requester's own flag; the scoreboard validates a submission by recomputing the
  expected value for the submitting competitor — so a flag from competitor B is
  invalid for A.
- **Scoreboard:** stateless validation (recompute `HMAC(secret, id|step)`); public +
  ops views as above. No per-competitor flag table needed.
- **Pros:** one lightweight deployment; flags are still per-identity (anti-share);
  attribution is built in. **Cons:** real app changes (every flag-emitting endpoint
  must personalize by identity), and the **non-HTTP steps are awkward** — the `nc`
  maintenance box (`SHELL_FLAG`) and the SSH/Chef flags (`USER_FLAG`/`ROOT_FLAG`)
  would each need source-IP→competitor logic, or be left as shared (attribution-only).

### Pragmatic baseline (if neither is worth the effort)
Single shared instance + **per-competitor WireGuard configs for logging only** +
CTFd with the current per-deploy (shared) flags. Flags aren't identity-specific, so
sharing is *detected* via VPN logs + submission timing rather than *prevented*.
Lowest effort; loses the "user-specific flag" property.

### Decision criteria
- Expected competitor count + available host resources → favors **1** if small, **2**
  if many.
- Tolerance for app changes vs ops/orchestration → **2** trades infra for dev work;
  **1** trades dev work for infra.
- How strictly flag-sharing must be *prevented* vs merely *detected* → **1**/**2**
  prevent; the baseline only detects.

---

## Notes / Design Decisions
- Flags: **env-only, never in source.** Unset flags render as `<NAME not set>`.
- **Staff creds are hardcoded literals in `web/app.py`** (`staff` / `Wint3r_St0ck_R00m_2026!`).
  They are LFI *loot*, not a flag, so they must appear in the source the LFI reads.
  Do not move them to env, or the LFI-found password won't match the running one.
- Source contains **no comments that name the vulns or the solution** (the LFI
  exposes these files, so they must read like a normal app, not an answer key).
- Login base64 is **single** encode/decode (README previously said "double").
- `/search` SSTI was removed; only the intended UNION SQLi remains.
- **Capstone PDF LFI** (`portal/app.py`): invoice fields are rendered to PDF by
  `wkhtmltopdf --enable-local-file-access`, run as **www-data** via
  `subprocess(..., user="www-data", env={scrubbed})`. The privilege drop + scrubbed
  env are load-bearing: they keep the LFI from reading flask's env (JWT key, flags)
  or `/root/root.txt`, so players must do the SSH + Chef steps. `USER_FLAG` is
  `jdoe`-only (mode 640); `ROOT_FLAG` is root-only (600). `jdoe`'s SSH password is
  leaked through `/var/mail/jdoe` (world-readable for the LFI) and `jdoe` has
  `sudo NOPASSWD` on `/usr/local/bin/chef-apply` (real Chef or cinc fallback). The
  working PDF payload is a `<script>` that XHRs `file:///var/mail/jdoe` and
  `document.write`s it (wkhtmltopdf runs JS); an `<iframe>` works too.
- **Chef license:** real Chef Infra Client won't run until its license is accepted,
  so the image pre-accepts it at build (`chef-apply <recipe> --chef-license accept`;
  the flag must come *after* the recipe file or it's read as a filename). The
  privesc is then a bare `sudo chef-apply recipe.rb`.
- **Portal JWT** uses a custom verifier (`portal/jwt_utils.py`) on purpose: modern
  PyJWT blocks RS256→HS256 confusion, so a faithful hand-rolled verifier is the
  realistic vuln. It trusts the token's `alg` header and reuses the RSA public key
  PEM as the HMAC secret. The RSA keypair is generated at portal startup; the
  public key is published at `/.well-known/jwks.json` and `/jwt/public.pem`.
- **Portal lock recipe** (`portal/reg.py` is the source of truth; `gen_flags.py`
  duplicates it to precompute `REGISTRATION_KEY`):
  `SHAKE256(mysterioususer_shadow_hash + admin_password)` → 512-bit lowercase hex.
  The portal only ever sees the final `REGISTRATION_KEY`, never the raw inputs.
  The shadow hash is stored base64 in `flags.env` (`MYSTERIOUS_USER_HASH_B64`) to
  keep `$` out of env files; the maintenance container decodes it into
  `mysterioususer`'s `/etc/shadow`.
