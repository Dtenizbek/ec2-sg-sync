# EC2 Security Group Sync

Automated tool to sync AWS EC2 Security Group rules with Cloudflare IP ranges and your current home IP.

## Features
- **Dynamic Detection**: Automatically finds your public IP and target Security Group.
- **Cloudflare Sync**: Fetches latest Cloudflare IPv4 ranges.
- **State Management**: Maintains a `security-group.yaml` source of truth.
- **Git Integration**: Automatically commits and pushes changes.
- **Dual Mode**: Includes both Python and Shell implementations.

## Prerequisites
- AWS CLI configured (`aws configure`) with permissions to manage Security Groups.
- Python 3.x installed.
- Git configured.

## DNS Setup (Important)
To access `http://2bcloud.io`, you must map the domain to the EC2 IP in your local hosts file.
Run this command:
```bash
echo "52.215.116.12 2bcloud.io" | sudo tee -a /etc/hosts
```

## Quick Start
See [QUICKSTART.md](QUICKSTART.md) for a 5-minute setup guide.

## Usage

### Python Version (Recommended)
```bash
./sync_security_group.py
```

### Shell Version
```bash
./sync_security_group.sh
```

## Configuration
The `security-group.yaml` file defines the desired state. The script updates this file automatically, but you can also edit it manually.

```yaml
name: security-group
rules:
  ssh:
    - 0.0.0.0/0
  http:
    - YOUR_HOME_IP/32
    - CLOUDFLARE_IP_1
    - CLOUDFLARE_IP_2
    ...
```

## Credentials
- **SSH User**: `user7`
- **SSH Password**: `p6L2f7Dw`
- **SSH Command**: `ssh user7@2bcloud.io`

## Troubleshooting
Run the verification script to diagnose issues:
```bash
./test_deployment.sh
```
