# Vulnerable Mart — Fullpwn

Eight independently scored challenges share one three-container deployment.
The manifests in `challenges/` each contain exactly one flag and use the same
500 → 100 logarithmic scoring settings as the existing repository challenges.

## Source

Imported from https://github.com/GabeRoy01/BSides-Peoria-WebVillage-2026.git at
`31b926ec7cdb2ffd58e7cf2e992e04837c6c85a5` (`Create PLATFORM_DESIGN.md`). This is
the parent of `742a076c7a4c3a755c122af3488efc5128cb0a78`, the consolidation commit.
The application sources, Dockerfiles, Compose file, solver, flag generator and
deployment flag values come from that parent. No CTFd plugin, Docker backend,
platform plans, or duplicate FlightLog/DispatchPanel code is imported.

The historical upstream README is in `docs/UPSTREAM_README.md`; the instructions
below describe this repository's integration. `SOLUTION.md` contains the intended
solve path and organizer QA checklist.

## Deployment

From this directory, on the challenge host:

```sh
python3 sync_flags.py --check
docker compose up -d --build
```

| Service | Host port | Purpose |
| --- | --- | --- |
| web | 8888 | Shop HTTP |
| maintenance | 50050 | Maintenance TCP service |
| portal | 8889 | Seller portal HTTP |
| portal | 50022 | SSH foothold |

Run this stack once on a dedicated CTF host and announce that host to players.
All eight entries refer to this same environment; starting a separate stack for
each flag would break the intended chain. The GitHub workflow synchronizes the
eight scoring entries using CTFd's built-in `dynamic` challenge type. It does
not deploy this Compose stack or add per-player start buttons. The existing web
challenges retain their current Docker build and synchronization behavior.

## Flags and scoring

| Entry | Environment variable |
| --- | --- |
| Staff Login | STAFF_FLAG |
| Admin Panel | ADMIN_FLAG |
| Checkout | CHECKOUT_FLAG |
| Maintenance Shell | SHELL_FLAG |
| Seller Portal | SELLER_FLAG |
| Portal Admin | PORTAL_ADMIN_FLAG |
| User | USER_FLAG |
| Root | ROOT_FLAG |

`flags.env` is intentionally included as the reproducible deployment fixture
from the selected revision. Each manifest matches its corresponding value.
Do not regenerate deployment flags without regenerating the scoring manifests.
For a new set, run from this directory on Linux (Python crypt or OpenSSL required):

```sh
python3 gen_flags.py --force
python3 sync_flags.py
python3 sync_flags.py --check
docker compose up -d --force-recreate
```

Commit the matching env file and manifests together. On push, the workflow
creates/updates eight separate entries and replaces their flags from these
manifests, including for existing shared-environment entries. A manual workflow
run resynchronizes all challenges. Rotate before play; changing flags during
play invalidates flags already recovered by players.

## Verification

```sh
python3 sync_flags.py --check
docker compose config --quiet
python3 -m pip install requests pypdf paramiko
python3 solve.py --host <challenge-host> --no-color
```

The imported solver exercises all eight stages against the running stack. Its
default target is localhost. Keep solutions, manifests and env files on the
organizer side; players need the deployed services.
