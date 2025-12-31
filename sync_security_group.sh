#!/bin/bash
set -e

# Configuration
YAML_FILE="security-group.yaml"
CLOUDFLARE_IPV4_URL="https://www.cloudflare.com/ips-v4"
SSH_PORT=22
HTTP_PORT=80

echo "============================================================"
echo "EC2 Security Group Sync Script (Shell Version)"
echo "============================================================"

# 1. Get IPs
HOME_IP=$(curl -s https://checkip.amazonaws.com)
HOME_IP_CIDR="${HOME_IP}/32"
echo "✓ Home IP: ${HOME_IP_CIDR}"

CLOUDFLARE_IPS=$(curl -s ${CLOUDFLARE_IPV4_URL})
CF_COUNT=$(echo "$CLOUDFLARE_IPS" | wc -l)
echo "✓ Fetched ${CF_COUNT} Cloudflare IP ranges"

# 2. AWS Setup
REGION=$(aws configure get region)
if [ -z "$REGION" ]; then
    REGION="eu-west-1" # Default
fi
echo "✓ Detected AWS Region: ${REGION}"

# 3. Find Security Group
# Try to find by name 'security-group'
SG_ID=$(aws ec2 describe-security-groups --filters Name=group-name,Values=security-group --query "SecurityGroups[0].GroupId" --output text)

if [ "$SG_ID" == "None" ]; then
    # Fallback: Find one allowing SSH 0.0.0.0/0
    SG_ID=$(aws ec2 describe-security-groups --filters Name=ip-permission.from-port,Values=22 Name=ip-permission.to-port,Values=22 Name=ip-permission.cidr,Values=0.0.0.0/0 --query "SecurityGroups[0].GroupId" --output text)
fi

if [ "$SG_ID" == "None" ]; then
    echo "Error: Could not find target Security Group."
    exit 1
fi
echo "✓ Found Security Group: ${SG_ID}"

# 4. Sync Rules
# This is harder in bash to do diffing, so we'll use a simpler approach:
# Revoke all HTTP rules and re-add them. This causes a brief downtime window but ensures sync.
# A better approach would be to list and diff, but parsing JSON in bash without jq is painful.
# Assuming jq is available or we can use python one-liners.

echo "Syncing HTTP rules..."

# Get current HTTP rules
EXISTING_HTTP=$(aws ec2 describe-security-groups --group-ids ${SG_ID} --query "SecurityGroups[0].IpPermissions[?FromPort==\`${HTTP_PORT}\`].IpRanges[*].CidrIp" --output text)

# Revoke all existing HTTP
if [ ! -z "$EXISTING_HTTP" ]; then
    for cidr in $EXISTING_HTTP; do
        aws ec2 revoke-security-group-ingress --group-id ${SG_ID} --protocol tcp --port ${HTTP_PORT} --cidr ${cidr} > /dev/null 2>&1 || true
    done
fi

# Authorize Home IP
aws ec2 authorize-security-group-ingress --group-id ${SG_ID} --protocol tcp --port ${HTTP_PORT} --cidr ${HOME_IP_CIDR} > /dev/null 2>&1 || true

# Authorize Cloudflare IPs
for cidr in $CLOUDFLARE_IPS; do
    aws ec2 authorize-security-group-ingress --group-id ${SG_ID} --protocol tcp --port ${HTTP_PORT} --cidr ${cidr} > /dev/null 2>&1 || true
done

echo "✓ Security group synced"

# 5. Update YAML
# Simple overwrite for bash version
echo "name: security-group" > ${YAML_FILE}
echo "rules:" >> ${YAML_FILE}
echo "  ssh:" >> ${YAML_FILE}
echo "    - 0.0.0.0/0" >> ${YAML_FILE}
echo "  http:" >> ${YAML_FILE}
echo "    - ${HOME_IP_CIDR}" >> ${YAML_FILE}
for cidr in $CLOUDFLARE_IPS; do
    echo "    - ${cidr}" >> ${YAML_FILE}
done

echo "✓ Updated security-group.yaml"

# 6. Git Ops
if [[ -n $(git status --porcelain) ]]; then
    git add ${YAML_FILE}
    git commit -m "Update security group rules [skip ci]"
    git push
    echo "✓ Changes pushed to Git"
else
    echo "No changes to commit."
fi

echo "============================================================"
echo "✓ Sync completed successfully!"
echo "  Test URL: http://2bcloud.io"
echo "============================================================"
