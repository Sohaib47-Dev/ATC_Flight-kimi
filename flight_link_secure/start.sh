#!/bin/bash

# Flight-Link Secure Startup Script

echo "================================"
echo "Flight-Link Secure"
echo "ATC-Defense Flight Plan System"
echo "================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is not installed"
    exit 1
fi

# Install dependencies if needed
echo "Checking dependencies..."
pip3 install -q -r requirements.txt

# Start the application
echo ""
echo "Starting Flight-Link Secure..."
echo ""
echo "Access the application at:"
echo "  - Local: http://127.0.0.1:5000"
echo "  - Network: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "Default Credentials:"
echo "  - Admin: admin / admin123"
echo "  - ATC: atc / atc123"
echo "  - Defense: defense / defense123"
echo ""
echo "Press Ctrl+C to stop the server"
echo "================================"
echo ""

python3 app.py
