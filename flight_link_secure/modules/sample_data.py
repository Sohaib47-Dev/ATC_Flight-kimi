"""
Sample Data Generator for Flight-Link Secure
Pre-populates database with test flight plans
"""
from models import db, FlightPlan

# Sample ICAO flight plans for testing
SAMPLE_FLIGHT_PLANS = [
    {
        'callsign': 'PIA123',
        'flight_plan': '(FPL-PIA123-IS\n-A320/M-SDE2E3FGHIRWY/LB1\n-OPLA2300\n-N0450F350 SULOM DCT TELEM DCT\n-EGLL0500\n-REG/APABC EET/EPZR 0150 SEL/ABCD RMK/TCAS)'
    },
    {
        'callsign': 'UAE456',
        'flight_plan': '(FPL-UAE456-IS\n-B77W/H-SDE2E3FGHIRWY/LB1\n-OMDB2200\n-N0480F370 MERUN DCT SULOM DCT PURPA DCT\n-OPKC0500\n-REG/A6EABC EET/OPKR 0200 SEL/EFGH RMK/TCAS)'
    },
    {
        'callsign': 'QTR789',
        'flight_plan': '(FPL-QTR789-IS\n-A359/H-SDE2E3FGHIRWY/LB1\n-OTHH2100\n-N0460F390 VIKIT DCT GUGAL DCT REGET DCT\n-OPLA0600\n-REG/A7ABC EET/OPKR 0220 SEL/IJKL RMK/TCAS)'
    },
    {
        'callsign': 'THY321',
        'flight_plan': '(FPL-THY321-IS\n-B738/M-SDE2E3FGHIRWY/LB1\n-LTFM2000\n-N0420F340 MERUN DCT VIKIT DCT GUGAL DCT\n-OPIS0700\n-REG/TCLABC EET/OPKR 0250 SEL/MNOP RMK/TCAS)'
    },
    {
        'callsign': 'ETD654',
        'flight_plan': '(FPL-ETD654-IS\n-A20N/M-SDE2E3FGHIRWY/LB1\n-OMAA1900\n-N0440F360 DOBAT DCT SIRKA DCT BIROS DCT\n-OPPS0800\n-REG/A6ABC EET/OPKR 0230 SEL/QRST RMK/TCAS)'
    },
    {
        'callsign': 'KLM987',
        'flight_plan': '(FPL-KLM987-IS\n-B78X/H-SDE2E3FGHIRWY/LB1\n-EHAM1800\n-N0490F380 BIROS DCT SIRKA DCT DOBAT DCT\n-OPQT0900\n-REG/PHABC EET/OPKR 0300 SEL/UVWX RMK/TCAS)'
    },
    {
        'callsign': 'SVA111',
        'flight_plan': '(FPL-SVA111-IS\n-B77L/H-SDE2E3FGHIRWY/LB1\n-OEJN1700\n-N0470F370 SULOM DCT SIRKA DCT TELEM DCT\n-OPKC1000\n-REG/HZABC EET/OPKR 0210 SEL/YZAB RMK/TCAS)'
    },
    {
        'callsign': 'IRA222',
        'flight_plan': '(FPL-IRA222-IS\n-A310/M-SDE2E3FGHIRWY/LB1\n-OIII1600\n-N0430F350 MERUN DCT VIKIT DCT GUGAL DCT\n-OPLA1100\n-REG/EPABC EET/OPKR 0240 SEL/CDEF RMK/TCAS)'
    },
    {
        'callsign': 'PAK333',
        'flight_plan': '(FPL-PAK333-IS\n-A320/M-SDE2E3FGHIRWY/LB1\n-OPIS0500\n-N0410F330 PURPA DCT REGET DCT BIROS DCT\n-EGLL1200\n-REG/APDEF EET/EPZR 0400 SEL/GHIJ RMK/TCAS)'
    },
    {
        'callsign': 'AFL444',
        'flight_plan': '(FPL-AFL444-IS\n-B77W/H-SDE2E3FGHIRWY/LB1\n-UUEE1500\n-N0500F390 VIKIT DCT GUGAL DCT MERUN DCT\n-OPKC1300\n-REG/VQABC EET/OPKR 0320 SEL/KLMN RMK/TCAS)'
    }
]


def populate_sample_data():
    """Populate database with sample flight plans"""
    print("Populating sample flight plans...")
    
    count = 0
    for data in SAMPLE_FLIGHT_PLANS:
        # Check if flight plan already exists
        existing = FlightPlan.query.filter_by(callsign=data['callsign']).first()
        if not existing:
            flight_plan = FlightPlan(
                callsign=data['callsign'],
                raw_flight_plan=data['flight_plan']
            )
            db.session.add(flight_plan)
            count += 1
            print(f"  Added: {data['callsign']}")
        else:
            print(f"  Skipped (exists): {data['callsign']}")
    
    db.session.commit()
    print(f"\nAdded {count} new flight plans")
    print(f"Total flight plans in database: {FlightPlan.query.count()}")


def get_sample_callsigns():
    """Return list of sample callsigns"""
    return [fp['callsign'] for fp in SAMPLE_FLIGHT_PLANS]


if __name__ == '__main__':
    # For standalone testing
    from app import app
    with app.app_context():
        populate_sample_data()
