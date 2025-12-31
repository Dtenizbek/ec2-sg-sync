#!/bin/bash
echo "Setting up EC2 Security Group Sync..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 could not be found."
    exit 1
fi

# Create venv
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Created Python virtual environment."
fi

# Install dependencies
source venv/bin/activate
pip install -r requirements.txt

# Make scripts executable
chmod +x sync_security_group.py
chmod +x sync_security_group.sh

echo "Setup complete! Run ./sync_security_group.py to start."
