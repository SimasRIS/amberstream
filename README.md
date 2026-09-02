# AmberStream Energy — Security Training Lab

A small Flask website for a fictional Baltic hydro-energy company, used as a
**deliberately vulnerable training target**.

> ⚠️ **Isolated / localhost use only.** This build ships armed with a stored-XSS
> vulnerability (see [SECURITY_LAB.md](SECURITY_LAB.md)). Run it only on
> localhost inside an isolated VM. Never expose it to a network, never point it
> at real data, never deploy it.

## Run (Ubuntu VM)

```bash
sudo apt update
sudo apt install -y python3 python3-venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

The app starts on **http://localhost:5000**. The database (`instance/plans.db`)
and a default `admin` / `admin` staff account are created automatically on first
run.

## The vulnerability

The customer reviews feature has a **stored cross-site-scripting (XSS)** hole
that is always active — a review body is rendered as raw HTML after a weak,
intentionally bypassable blocklist. There is no on-page warning and no way to
disable it; the app is a fixed vulnerable target.

Full details, the bypass payload and the fix are in
**[SECURITY_LAB.md](SECURITY_LAB.md)**. The `AmberStream_Vulnerabilities.docx`
write-up is distributed separately and is not part of this repository.

## Host it on the VM (Ubuntu 24.04 desktop)

To have the site come up automatically at boot instead of running `app.py` by
hand, install it as a systemd service. From the project directory:

```bash
bash deploy/install.sh
```

That creates `.venv`, installs the dependencies, generates a `SECRET_KEY`,
initialises the database, and installs + starts a unit that serves the site
under gunicorn. Re-run it any time to apply changes; it updates in place.

```bash
systemctl status amberstream      # is it up
journalctl -u amberstream -f      # follow the logs
sudo systemctl restart amberstream
bash deploy/uninstall.sh          # remove the service
```

### Where it listens

`deploy/amberstream.env` ships with:

```ini
BIND_ADDR=auto
PORT=80
BIND_WAIT=30
```

`auto` binds the VM's own primary address — the one on its default-route
interface — worked out when the service starts. Nothing is hardcoded, so a
golden image can be cloned any number of times and each clone serves on its own
address with no edit to any file. Virtual bridges (`docker0` and similar) are
skipped. To override, put a literal address in `BIND_ADDR`.

No address, subnet or hostname belonging to any real environment is committed to
this repository. `deploy/amberstream.env` is the only place those appear, and it
is gitignored.

The service logs the address it chose:

```bash
journalctl -u amberstream | grep 'listening on'
```

Port 80 is the default so the site answers at `http://<host>/` with no port in
the URL; the unit grants `CAP_NET_BIND_SERVICE`, so it does not run as root.

**If the network is not up yet**, the service waits `BIND_WAIT` seconds, then
falls back to `127.0.0.1` and says so in the log. It never falls back to
`0.0.0.0`: if we cannot work out which network the VM is on, the safe answer for
a knowingly vulnerable app is to be reachable from nowhere but the VM itself.

### Reaching it by name

The app serves any `Host` header, so a hostname needs no nginx and no change to
the app — just point the name at the VM's address in whatever resolves names on
your lab network (a local DNS server, or `/etc/hosts` on the machines that need
it).

> ⚠️ Resolve the name **internally only**. Never point public DNS at this build:
> it ships a live stored-XSS hole and a default `admin` / `admin` login.

## Structure

```
app.py                # Flask app: site, admin console, review lab
wsgi.py               # gunicorn entry point
requirements.txt      # Python dependencies
deploy/               # install.sh, uninstall.sh, systemd unit, config
static/               # CSS and images
templates/            # Public pages, admin console, lab control
instance/             # SQLite database (auto-created, gitignored)
SECURITY_LAB.md       # Lab guide
```

## Staff console

`/admin` — default login `admin` / `admin`. From there: edit electricity rates,
moderate customer reviews, change the password.
