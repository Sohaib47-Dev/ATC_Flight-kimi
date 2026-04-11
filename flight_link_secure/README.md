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
SULOM, MERUN, VIKIT, GUGAL, PURPA, BIROS, NOKID, TIGER, ORPOR, LELIM, DUDAT, SARAB, PABLA, KARON, NISAR, KAMIL, MEPAN, TOSAR

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

## API Endpoints

### Authentication Required
- `GET /api/defense/tracks` - Get active tracks for radar
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

## License

This project is developed for educational purposes as a Final Year Project.

## Author

Flight-Link Secure Development Team
