# Quick Start Guide

## 1. Setup
Run the setup script to install dependencies and configure the environment:
```bash
chmod +x setup.sh
./setup.sh
```

## 2. Configure AWS
Ensure you have valid AWS credentials:
```bash
aws configure
```

## 3. Run Sync
Execute the sync script:
```bash
./sync_security_group.py
```

## 4. Verify
Check if everything is working:
```bash
./test_deployment.sh
```

## 5. Access
Open [http://2bcloud.io](http://2bcloud.io) in your browser.
