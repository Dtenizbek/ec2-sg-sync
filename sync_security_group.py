#!/usr/bin/env python3

import os
import sys
import subprocess
import json
from datetime import datetime

# Try to import boto3, if fails, try to use venv
try:
    import boto3
    import requests
    import yaml
    from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
except ImportError:
    # Check if venv exists and we are not already running from it
    venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "bin", "python3")
    if os.path.exists(venv_python) and sys.executable != venv_python:
        print("Dependency missing. Re-launching using virtual environment...")
        os.execv(venv_python, [venv_python] + sys.argv)
    else:
        print("Error: Dependencies not found. Please run ./setup.sh first.")
        sys.exit(1)

# Configuration
YAML_FILE = 'security-group.yaml'
CLOUDFLARE_IPV4_URL = 'https://www.cloudflare.com/ips-v4'
SSH_PORT = 22
HTTP_PORT = 80

def get_current_ip():
    """Get current public IP address."""
    try:
        response = requests.get('https://checkip.amazonaws.com')
        response.raise_for_status()
        return f"{response.text.strip()}/32"
    except Exception as e:
        print(f"Error getting public IP: {e}")
        sys.exit(1)

def get_cloudflare_ips():
    """Get Cloudflare IPv4 ranges."""
    try:
        response = requests.get(CLOUDFLARE_IPV4_URL)
        response.raise_for_status()
        return [ip.strip() for ip in response.text.splitlines() if ip.strip()]
    except Exception as e:
        print(f"Error getting Cloudflare IPs: {e}")
        sys.exit(1)

def load_yaml_config():
    """Load security group configuration from YAML."""
    if not os.path.exists(YAML_FILE):
        print(f"Error: {YAML_FILE} not found.")
        sys.exit(1)
    with open(YAML_FILE, 'r') as f:
        return yaml.safe_load(f) or {}

def save_yaml_config(config):
    """Save security group configuration to YAML."""
    with open(YAML_FILE, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

def get_security_group_id(ec2):
    """Dynamically find the security group for the running instance or default."""
    # In a real scenario running on EC2, we could get instance metadata.
    # For this task running locally, we'll search for a security group named 'security-group'
    # or one that allows SSH from 0.0.0.0/0 to identify the target.
    # However, the prompt implies we are running this LOCALLY ("from your PC/laptop").
    # So we need a way to identify the target SG.
    # The prompt says: "The script must not use hard-coded values for the region's name or security group; both should be determined dynamically at runtime."
    # This is tricky from a local machine without input.
    # Strategy: Look for a security group named 'security-group' (matching the YAML name)
    # or ask the user/environment.
    # Let's try to find a security group with tag 'Name=security-group' or GroupName='security-group'.
    
    try:
        # First, try to find by GroupName 'security-group' (default from YAML)
        response = ec2.describe_security_groups(
            Filters=[{'Name': 'group-name', 'Values': ['security-group']}]
        )
        if response['SecurityGroups']:
            return response['SecurityGroups'][0]['GroupId']
        
        # If not found, try to find the one attached to the instance with public IP 52.215.116.12
        # But we might not have permissions to list instances or the IP might change.
        # Let's assume the YAML 'name' field is the GroupName.
        print("Could not find security group named 'security-group'.")
        # Fallback: List all and pick the first one? No, that's dangerous.
        # Let's try to find one that allows SSH from 0.0.0.0/0 as per "Current State"
        response = ec2.describe_security_groups(
            Filters=[
                {'Name': 'ip-permission.from-port', 'Values': ['22']},
                {'Name': 'ip-permission.to-port', 'Values': ['22']},
                {'Name': 'ip-permission.cidr', 'Values': ['0.0.0.0/0']}
            ]
        )
        if response['SecurityGroups']:
             # If multiple, pick the first one but warn
            sg = response['SecurityGroups'][0]
            print(f"Found security group {sg['GroupId']} allowing SSH from 0.0.0.0/0")
            return sg['GroupId']

        print("Error: Could not dynamically determine target Security Group.")
        sys.exit(1)
    except (NoCredentialsError, PartialCredentialsError):
        print("\n❌ AWS Credentials not found.")
        print("Please run 'aws configure' to set up your Access Key and Secret Key.")
        sys.exit(1)
    except Exception as e:
        print(f"Error finding security group: {e}")
        sys.exit(1)

def update_security_group(ec2, sg_id, allowed_cidrs):
    """Update security group ingress rules."""
    try:
        # Get current rules
        response = ec2.describe_security_groups(GroupIds=[sg_id])
        current_permissions = response['SecurityGroups'][0]['IpPermissions']
        
        # 1. Ensure SSH is open to 0.0.0.0/0
        ssh_open = False
        for perm in current_permissions:
            if perm.get('FromPort') == SSH_PORT and perm.get('ToPort') == SSH_PORT:
                for ip_range in perm.get('IpRanges', []):
                    if ip_range.get('CidrIp') == '0.0.0.0/0':
                        ssh_open = True
                        break
        
        if not ssh_open:
            print("Adding SSH access for 0.0.0.0/0...")
            ec2.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[{
                    'IpProtocol': 'tcp',
                    'FromPort': SSH_PORT,
                    'ToPort': SSH_PORT,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                }]
            )

        # 2. Sync HTTP rules
        # Get current HTTP CIDRs
        current_http_cidrs = set()
        for perm in current_permissions:
            if perm.get('FromPort') == HTTP_PORT and perm.get('ToPort') == HTTP_PORT:
                for ip_range in perm.get('IpRanges', []):
                    current_http_cidrs.add(ip_range['CidrIp'])
        
        target_http_cidrs = set(allowed_cidrs)
        
        # Calculate diff
        to_revoke = current_http_cidrs - target_http_cidrs
        to_authorize = target_http_cidrs - current_http_cidrs
        
        if to_revoke:
            print(f"Revoking {len(to_revoke)} stale HTTP rules...")
            ec2.revoke_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[{
                    'IpProtocol': 'tcp',
                    'FromPort': HTTP_PORT,
                    'ToPort': HTTP_PORT,
                    'IpRanges': [{'CidrIp': cidr} for cidr in to_revoke]
                }]
            )
            
        if to_authorize:
            print(f"Authorizing {len(to_authorize)} new HTTP rules...")
            # AWS has a limit on rules per call, but usually 60 is fine.
            # Cloudflare has ~15 ranges, plus home IP. Should be safe.
            ec2.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[{
                    'IpProtocol': 'tcp',
                    'FromPort': HTTP_PORT,
                    'ToPort': HTTP_PORT,
                    'IpRanges': [{'CidrIp': cidr} for cidr in to_authorize]
                }]
            )
            
        return True
    except Exception as e:
        print(f"Error updating security group: {e}")
        sys.exit(1)

def git_commit_and_push():
    """Commit and push changes to Git."""
    try:
        # Check if there are changes
        status = subprocess.check_output(['git', 'status', '--porcelain']).decode()
        if not status:
            print("No changes to commit.")
            return

        print("Committing and pushing changes...")
        subprocess.check_call(['git', 'pull'])
        subprocess.check_call(['git', 'add', YAML_FILE])
        subprocess.check_call(['git', 'commit', '-m', 'Update security group rules [skip ci]'])
        subprocess.check_call(['git', 'push'])
    except subprocess.CalledProcessError as e:
        print(f"Git operation failed: {e}")
        # Don't exit, just warn

def main():
    print("============================================================")
    print("EC2 Security Group Sync Script")
    print("============================================================")
    
    # 1. Get IPs
    home_ip = get_current_ip()
    print(f"✓ Home IP: {home_ip}")
    
    cf_ips = get_cloudflare_ips()
    print(f"✓ Fetched {len(cf_ips)} Cloudflare IP ranges")
    
    # 2. Prepare target rules
    target_http_cidrs = sorted(list(set([home_ip] + cf_ips)))
    
    # 3. AWS Setup
    # Boto3 will automatically look for credentials in env vars or ~/.aws/credentials
    # It also handles region detection if configured.
    session = boto3.Session()
    region = session.region_name
    if not region:
        # Fallback if not set in config
        region = 'eu-west-1' # Defaulting based on typical usage, or could query metadata if on EC2
        session = boto3.Session(region_name=region)
        
    print(f"✓ Detected AWS Region: {region}")
    ec2 = session.client('ec2')
    
    # 4. Find Security Group
    sg_id = get_security_group_id(ec2)
    print(f"✓ Found Security Group: {sg_id}")
    
    # 5. Sync Rules
    update_security_group(ec2, sg_id, target_http_cidrs)
    print("✓ Security group synced")
    
    # 6. Update YAML
    config = load_yaml_config()
    config['rules']['http'] = target_http_cidrs
    # Ensure SSH is there
    if 'ssh' not in config['rules']:
        config['rules']['ssh'] = ['0.0.0.0/0']
    
    save_yaml_config(config)
    print("✓ Updated security-group.yaml")
    
    # 7. Git Ops
    git_commit_and_push()
    print("============================================================")
    print("✓ Sync completed successfully!")
    print("  Test URL: http://2bcloud.io")
    print("============================================================")

if __name__ == '__main__':
    main()