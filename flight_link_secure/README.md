# Flight-Link Secure

## ATC-Defense Flight Plan Processing & Radar Simulation System

A comprehensive Python-based ATC (Air Traffic Control) system built with Flask that processes ICAO flight plans, validates ATC estimates, securely transfers data to Defense systems, and provides a radar simulator for monitoring aircraft movement within Pakistan FIR (Flight Information Region).

## Features

### User Roles & Authentication
- **Admin**: System monitoring, user management, logs viewing
- **ATC Operator**: Flight plan retrieval, estimate entry, data transfer
- **Defense Operator**: Receive encrypted messages, radar monitoring

### Core Functionality
- **Two-Layer Flight Plan Parser**: Robust ICAO message parsing with regex extraction and semantic validation
- **ATC Estimate Validation**: Real-time validation of ETO, CFL, and SSR codes with auto-correction
- **Secure Data Transfer**: Encrypted JSON data transfer from ATC to Defense
- **Radar Simulator**: Visual aircraft tracking with Pakistan FIR boundary
- **Session Management**: Complete audit trail and activity logging

## Technology Stack

- **Backend**: Python 3, Flask
- **Database**: SQLite (with PostgreSQL support)
- **Authentication**: Flask-Login with role-based access control
- **Encryption**: Fernet symmetric encryption (cryptography library)
- **Frontend**: Bootstrap 5, jQuery
- **Visualization**: SVG-based radar display

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd flight_link_secure
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Access the application:
- Open browser: http://localhost:5000
- Default credentials:
  - Admin: `admin` / `admin123`
  - ATC: `atc` / `atc123`
  - Defense: `defense` / `defense123`

## Project Structure

```
flight_link_secure/
├── app.py                 # Main Flask application
├── models.py              # Database models
├── requirements.txt       # Python dependencies
├── modules/
│   ├── flight_plan_parser.py  # Two-layer ICAO parser
│   ├── validators.py           # ATC estimate validation
│   ├── encryption.py           # Secure data transfer
│   └── sample_data.py          # Test flight plans
├── templates/
│   ├── base.html          # Base template
│   ├── index.html         # Landing page
│   ├── login.html         # Login page
│   ├── admin/             # Admin templates
│   ├── atc/               # ATC templates
│   └── defense/           # Defense templates
└── static/                # CSS, JS, images
```

## Database Schema

### Users Table
- `id`, `username`, `password_hash`, `role`
- `last_login_ip`, `last_login_time`, `is_active`

### Flight Plans Table
- `id`, `callsign` (UNIQUE), `raw_flight_plan`, `created_at`

### Track Data Table
- `id`, `flight_plan_id`, `callsign`, `aircraft_type`
- `departure`, `destination`, `fir_entry`, `speed`, `route`
- `eto_utc`, `eto_pst`, `cfl`, `ssr`
- `status`, `sent_to_defense`, `sent_at`

### System Logs Table
- `id`, `timestamp`, `user_id`, `username`
- `action`, `details`, `ip_address`

### Defense Messages Table
- `id`, `track_data_id`, `encrypted_data`
- `received_at`, `decrypted_at`, `processed`

## Flight Plan Parser

### Two-Layer Architecture

**Layer 1: Regex Candidate Extraction**
- Extracts all possible values using regex patterns
- Collects candidates for callsign, aircraft type, aerodromes, speed

**Layer 2: Semantic Validation**
- Callsign: From FPL- header
- Aircraft Type: From -TYPE/WTC field only
- Departure: First ICAO+time occurrence
- Destination: Second ICAO+time occurrence (before RALT/ALTN/RMK)
- FIR Entry: Match against Pakistan FIR entry points list

### Pakistan FIR Entry Points
Canonical names in code (`PAKISTAN_FIR_ENTRY_POINTS`): SULOM, MERUN, VIKIT, GUGAL, PURPA, BIROS, DOBAT, SIRKA, TELEM, REGET, LAJAK, ASSVIB. Legacy route text may still use **DODAT**; it is normalized to **DOBAT**.

## ATC Estimate Validation

### ETO (Estimated Time Over)
- Format: HHMM (UTC)
- Auto-converts to Pakistan Time (UTC+5)
- Handles rollover (1900 UTC → 0000 PST)

### CFL (Cleared Flight Level)
- Exactly 3 digits
- Maximum: 500
- Example: 350 = FL350

### SSR Code
- Exactly 4 digits
- No letters
- No repeated digits (1111, 2222, etc.)
- Auto-corrects invalid codes (generates new starting with 4)

## Radar Simulator

### Features
- Pakistan FIR boundary visualization (simplified polygon)
- FIR entry points marked
- Real-time aircraft movement simulation
- Aircraft labels: CALLSIGN | FL | SSR
- Speed-based movement interpolation
- Dark radar-style theme with sweep animation

### Aircraft Movement Logic
- Starts at FIR entry point
- Moves toward center then exit
- Time-based speed calculation
- Linear interpolation for smooth movement

### Real-time WebSocket updates (defense radar)
- Run the app with **`python app.py`**, which uses **`socketio.run(...)`** (Flask-SocketIO, threading mode) so the browser can connect with Socket.IO.
- The radar page performs **one** `GET /api/defense/tracks` to hydrate full rows (including `resolved_path` for route lines), then receives **`aircraft_update`** events with slim `{ id, lat, lon, cfl, callsign, … }` payloads.
- Simulation advances on the **server tick** (`RADAR_WS_TICK_MS`), not per browser poll.
- **Why the marker can look slow:** each tick moves the aircraft by roughly `(speed in knots / 3600) × dt` nautical miles along the route. With a short `dt` (fast ticks), that step is often a tiny fraction of a degree—almost invisible on the SVG until you tune the knobs below.

#### Making motion more noticeable (Tier A — client / timing, no change to filed speed in the database)

| Variable | Role |
|----------|------|
| `RADAR_DEMO_MODE` | When `true`, speeds up **only** how fast the browser lerps toward each new server position (not the stored `speed` field or NM math on the server). |
| `RADAR_DEMO_ANIMATION_SPEED` | Multiplier used with demo mode (e.g. `3.0`). |
| `RADAR_INTERP_SEGMENT_SEC` | Seconds to blend from previous to next lat/lon (default **0.2**). **Lower** = snappier; **higher** = softer easing. |
| `RADAR_WS_TICK_MS` | Milliseconds between server simulation steps. **Higher** (e.g. `800`–`1500`) = **larger** geographic jump per update (more visible, fewer updates/sec). **Lower** = smoother but smaller steps per message. |

Example (PowerShell) for a livelier demo without editing code:

```text
$env:RADAR_DEMO_MODE="true"
$env:RADAR_DEMO_ANIMATION_SPEED="3"
$env:RADAR_INTERP_SEGMENT_SEC="0.18"
$env:RADAR_WS_TICK_MS="900"
python app.py
```

#### Server-side demo speed (Tier B — optional)

- `RADAR_SIM_VISUAL_MULTIPLIER` — Multiplies **only** the distance advanced along the simulated route each tick (`along_nm`). Default **3.0** (set `1` for stricter realism). Separation uses the same advanced positions. Not a substitute for real-world filed speed.

The defense radar client also **dead-reckons** briefly along the last true bearing at filed ground speed between WebSocket snapshots (capped lead vs. last server position), so motion feels more continuous—similar in spirit to consumer map apps.

## API Endpoints

### Authentication Required
- `GET /api/defense/tracks` - Full track snapshot for radar (hydration, tests, debugging)
- `POST /api/validate-estimates` - Validate ATC estimates (AJAX)
- `GET /api/flight-plan/<callsign>` - Get flight plan by callsign

## Security Features

- Password hashing with Werkzeug
- Session-based authentication
- Role-based access control
- Fernet symmetric encryption for data transfer
- IP address logging
- Comprehensive audit trail

## Development

### Adding Sample Flight Plans
Edit `modules/sample_data.py` and add to `SAMPLE_FLIGHT_PLANS` list:

```python
{
    'callsign': 'NEW123',
    'flight_plan': '(FPL-NEW123-IS\n-A320/M-SDE2E3FGHIRWY/LB1\n-ADEP0000\n-N0450F350 ROUTE\n-ADES0100\n-REG/ABC RMK/TCAS)'
}
```

### Environment Variables
- `SECRET_KEY` - Flask secret key
- `DATABASE_URL` - Database connection string (default: SQLite)
- `RADAR_WS_TICK_MS` - Socket.IO broadcast interval (ms); each tick advances server simulation once (see radar section for visibility tradeoffs)
- `RADAR_INTERP_SEGMENT_SEC` - Client lat/lon lerp segment length (seconds) between server snapshots
- `RADAR_DEMO_MODE` - When `true`, multiplies only the **interpolation progress** on the radar (not the stored aircraft speed field)
- `RADAR_DEMO_ANIMATION_SPEED` - Demo multiplier (e.g. `3.0`) used with `RADAR_DEMO_MODE`
- `RADAR_SIM_VISUAL_MULTIPLIER` - Multiplies server `along_nm` advance per tick for demo visibility (default **3.0**; use `1` for nominal NM/sec; see radar Tier B)
- `RADAR_TEST_AUTO_SEED` - When `true`, first defense Socket.IO connect seeds one active track per FIR entry (callsigns `RTST00`…; skips if any `RTST%` flight plan already exists). On by default in **development** only.
- `RADAR_TEST_MONITOR` - When `true`, each sim tick validates entry resolution, non-empty path, motion, and route corridor; logs structured errors and optional autofixes. Emits `radar_test_stats` over Socket.IO for the small radar overlay.
- `RADAR_TEST_CORRIDOR_NM` / `RADAR_TEST_STUCK_TICKS` - Monitor thresholds (defaults **12** NM corridor, **12** ticks without `along_nm` progress mid-route).
- When the monitor detects an issue it emits **`RADAR_TEST_EVENT`** lines with a JSON payload (search the app log for that prefix).

## License

This project is developed for educational purposes as a Final Year Project.

## Author

Flight-Link Secure Development Team
