# Flight-Link Secure

Flask web application for **ICAO flight plan intake**, **ATC estimate validation**, **secure handoff to defense**, and **server-driven radar simulation** (Pakistan FIR–oriented routes, SVG map, real-time updates).

---

## Overview

Flight-Link Secure connects three operational roles:

- **ATC** enters or imports flight plans, validates estimates (ETO, CFL, SSR), builds tracks, and transfers selected data to defense.
- **Defense** receives encrypted payloads, views a **radar-style** track display with **HTTP** and **WebSocket** updates, and inspects message history.
- **Admin** manages users, views logs and operational data, and performs maintenance actions.

The system parses structured ICAO-style flight plan text, persists plans and tracks in **SQLite** (configurable to another DB via `DATABASE_URL`), encrypts defense-bound data with **Fernet** (`cryptography`), and advances aircraft positions along **resolved route polylines** using shared airway data in `config/radar_airways.json`.

---

## Key Features

| Area | What the code provides |
|------|-------------------------|
| **Authentication** | Flask-Login; roles `admin`, `atc`, `defense` with route guards (`admin_required`, `atc_required`, `defense_required`). |
| **Flight plans** | Store raw ICAO messages; parse with a **two-layer** parser (`modules/flight_plan_parser.py`); optional form round-trip (`modules/flight_plan_form_io.py`). |
| **ATC workflow** | Dashboard, flight plan retrieval, estimate entry, SSR validation, transfer to defense, add/edit/delete flight plans, track deactivation. |
| **Defense workflow** | Dashboard, radar page, encrypted message detail, REST APIs for tracks and alerts. |
| **Radar simulation** | Server-side progression along `route_builder` paths; kinematics in `simulation_service` / `kinematics`; optional **separation** flags via `separation_engine`. |
| **Real-time** | Flask-SocketIO: `aircraft_update` broadcasts; optional `radar_test_stats` when radar test monitor is enabled. |
| **Audit** | `SystemLog` and `audit_service` for logged actions. |
| **CSRF** | Flask-WTF CSRF on web forms (disabled only in `TestingConfig`). |

---

## Requirements

- **Python 3** (dependencies are pinned in `requirements.txt`).
- **pip** for installing packages.

---

## Installation

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd flight_link_secure
```

Use the directory that contains `app.py`, `config.py`, and `requirements.txt` as the application root for all commands below.

### 2. Create a virtual environment

**Windows (PowerShell)**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux / macOS**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

Pinned stack includes Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF, Flask-SocketIO, python-socketio, python-engineio, Werkzeug, and cryptography.

---

## Running Locally

From the **`flight_link_secure`** directory (with the virtual environment activated):

```bash
python app.py
```

This will:

1. Create the Flask/SocketIO app (`create_app()`).
2. Call `init_db(app)` (create tables, default users, any schema helpers).
3. Run `populate_sample_data()` (inserts sample flight plans if missing).
4. Start the server with **`socketio.run`** on **`0.0.0.0:5000`**, **debug** enabled.

Open **http://127.0.0.1:5000** in a browser.

**Default users** (created on first DB init if absent):

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `admin123` |
| ATC | `atc` | `atc123` |
| Defense | `defense` | `defense123` |

Change these immediately in any shared or production environment.

**Optional (Linux/macOS):** `./start.sh` installs dependencies with `pip3` and runs `python3 app.py`.

**WSGI:** `wsgi.py` exposes `app = create_app()` for production servers (e.g. gunicorn with a compatible SocketIO worker if you use WebSockets in production).

---

## Project Structure

```
flight_link_secure/
├── app.py                 # Dev entrypoint: init_db, sample data, socketio.run
├── wsgi.py                # Production-style app object for WSGI servers
├── config.py              # Config classes and environment-driven settings
├── requirements.txt
├── models.py              # Re-exports / compatibility shim for models
├── start.sh               # Optional shell helper to install deps and run app
├── app/
│   ├── __init__.py        # Application factory, blueprints, SocketIO registration
│   ├── extensions.py      # db, login_manager, csrf, socketio
│   ├── models/            # SQLAlchemy models (User, FlightPlan, TrackData, …)
│   ├── routes/            # auth, admin, atc, defense blueprints
│   ├── services/          # Business logic (ATC, defense, sim, radar, audit, …)
│   ├── socketio_handlers.py
│   └── utils/decorators.py
├── modules/               # Parser, validators, encryption, sample_data, form I/O
├── config/
│   └── radar_airways.json # FIR fixes, airway polylines, route rules for simulation
├── templates/             # Jinja2 HTML (base, login, admin, atc, defense)
├── static/                # CSS, JS (including defense radar client)
└── instance/              # Typical location for local SQLite file (if used)
```

---

## Main Components

### Application factory (`app/__init__.py`)

- Builds the Flask app with correct `template_folder` / `static_folder`.
- Loads configuration from `config.config_by_name` using `FLASK_CONFIG` (`development` | `production` | `testing`).
- Registers blueprints: `auth`, `admin`, `atc`, `defense`.
- Initializes SQLAlchemy, CSRF, Login, SocketIO; registers `register_radar_socketio`.

### Routes (blueprints)

- **`auth`**: `/`, `/login`, `/logout`.
- **`atc`** (ATC or admin): dashboard, flight plan lookup, estimates, transfer, add/edit/manage/delete flight plans, form-parse API, validate-estimates API, flight-plan-by-callsign API, deactivate track.
- **`defense`** (defense or admin): dashboard, radar page, message detail, JSON **`/api/defense/tracks`**, **`/api/defense/new-alerts`**.
- **`admin`**: dashboard, users (toggle, reset password, update), flight plans, track data, logs, data integrity, admin delete flight plan.

### Models (`app/models/__init__.py`)

- **`User`**: credentials, role, active flag, login metadata.
- **`FlightPlan`**: callsign, raw ICAO text.
- **`TrackData`**: parsed track fields, ETO/CFL/SSR, status, defense transfer flags, JSON **`current_position`** for simulation state.
- **`DefenseMessage`**: encrypted payload linked to a track.
- **`SystemLog`**: audit trail rows.
- **`init_db`**: `create_all`, default users, simulation column migration hook.

### Configuration (`config.py`)

- **`Config`**: base settings (see Environment variables below).
- **`DevelopmentConfig`**: `DEBUG = True`; radar test monitor defaults **on** unless overridden by env.
- **`ProductionConfig`**: `DEBUG = False`.
- **`TestingConfig`**: `TESTING = True`, in-memory SQLite, CSRF off, conservative sim/monitor flags for smoke runs.

### Services (selected)

- **`atc_service` / `defense_service`**: track creation, transfer, defense views.
- **`simulation_service`**: advances active defense tracks, builds API/WebSocket payloads; uses **`route_builder`** and **`kinematics`**; can attach separation/conflict hints from **`separation_engine`**.
- **`route_builder`**: resolves FIR entry and route strings to lat/lon paths using **`config/radar_airways.json`**.
- **`radar_service`**: defense radar data assembly.
- **`radar_test_monitor`**: optional per-tick validation and stats for development/diagnostics.
- **`audit_service`**: structured logging for sensitive actions.
- **`encryption`**: Fernet encrypt/decrypt for defense-bound payloads.

### Real-time (`app/socketio_handlers.py`)

- On Socket.IO **connect**, only **defense** or **admin** users are accepted.
- Background loop: advances simulation, emits **`aircraft_update`** with minimal track payloads; may emit **`radar_test_stats`** when enabled.

### Modules

- **`flight_plan_parser`**: ICAO-style parsing, Pakistan FIR entry extraction, route tokenization (e.g. `DCT` stripped per implementation).
- **`validators`**: ATC estimate validation (ETO, CFL, SSR rules as implemented).
- **`flight_plan_form_io`**: Web form field mapping to/from parser.
- **`sample_data`**: Optional demo flight plans for `populate_sample_data()`.

---

## Usage (by role)

1. **Login** at `/login` with the appropriate role.
2. **ATC**
   - Use the dashboard and **flight plan** flow to load a plan by callsign.
   - Enter **estimates** (ETO, CFL, SSR); use **Validate** API as offered by the UI.
   - **Transfer** eligible tracks to defense when ready.
   - **Manage flight plans**: add, edit, or delete stored plans; **deactivate** tracks when needed.
3. **Defense**
   - Open **dashboard** and **radar**; radar consumes **`/api/defense/tracks`** (and optional Socket.IO updates when connected).
   - Open a **message** to inspect stored encrypted/decrypted metadata per implementation.
4. **Admin**
   - Manage **users**, inspect **flight plans** / **track data**, review **logs**, run **data integrity** checks, delete flight plans when required.

Exact button labels and page flows are defined in `templates/` and static JS under `static/`.

---

## Configuration & Environment Variables

Set variables in the process environment before starting the app. `FLASK_CONFIG` selects the config class (`development` default in code if unset—see `app/__init__.py`).

| Variable | Purpose |
|----------|---------|
| `FLASK_CONFIG` | `development` \| `production` \| `testing` |
| `SECRET_KEY` | Flask session secret (default exists for dev only—**override in production**). |
| `DATABASE_URL` | SQLAlchemy URI (default `sqlite:///flight_link.db`). |
| `RADAR_SIM_USE_ETO` | If truthy, tracks respect ETO gate for simulation advance. |
| `RADAR_SIM_ETO_BYPASS` | If truthy (default in base `Config`), ETO gate is bypassed. |
| `RADAR_UI_POLL_MS` | Defense UI poll interval for track API (ms). |
| `RADAR_WS_TICK_MS` | Socket.IO simulation tick interval (ms); defaults to match poll if unset. |
| `RADAR_INTERP_SEGMENT_SEC` | Client interpolation segment length (seconds). |
| `RADAR_DEMO_MODE` | Demo mode flag. |
| `RADAR_DEMO_ANIMATION_SPEED` | Demo animation speed factor. |
| `RADAR_SIM_VISUAL_MULTIPLIER` | Multiplier for along-route advance per tick (capped in code). |
| `RADAR_TEST_MONITOR` | Enable radar test monitor (base: off unless env set; **development** defaults to on unless overridden). |
| `RADAR_TEST_CORRIDOR_NM` | Monitor corridor threshold (NM). |
| `RADAR_TEST_STUCK_TICKS` | Monitor “stuck” tick threshold. |

`config/radar_airways.json` should stay aligned with any client-side route logic in `static/js/radar.js` when you change airways or fixes.

---

## Deployment (brief)

1. Set **`FLASK_CONFIG=production`**, a strong **`SECRET_KEY`**, and a production **`DATABASE_URL`**.
2. Serve with a production WSGI/ASGI stack compatible with **Flask-SocketIO** if you rely on WebSockets (consult Flask-SocketIO deployment docs for your chosen server).
3. Disable **`debug`** (not used when not running `app.py` directly; `ProductionConfig` sets `DEBUG = False`).
4. Restrict network access, use HTTPS, and replace default users/passwords with a proper provisioning process.

---

## Future Improvements (suggestions)

- Harden default credentials and seed data for production.
- Add automated regression tests if quality gates are required again.
- Document production SocketIO worker pairing explicitly for your hosting provider.

---

## Contributing

There is no separate `CONTRIBUTING.md` in the repository. For contributions: follow existing patterns (blueprints in `app/routes`, logic in `app/services`, shared parsers in `modules`), keep secrets out of git, and run the application locally to verify behavior before submitting changes.

---

## License

Not specified in the repository; add a `LICENSE` file and update this section when you choose a license.
