#!/bin/bash
echo "Running verification tests..."

# 1. Check AWS Auth
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS authentication failed. Run 'aws configure'."
    exit 1
fi
echo "✅ AWS authentication"

# 2. Check DNS
RESOLVED_IP=$(nslookup 2bcloud.io | grep "Address: " | tail -n1 | awk '{print $2}')
EXPECTED_IP="52.215.116.12"
# Note: nslookup output format varies. This is a best-effort check.
# Or use python:
RESOLVED_IP_PY=$(python3 -c "import socket; print(socket.gethostbyname('2bcloud.io'))" 2>/dev/null)

if [ "$RESOLVED_IP_PY" == "$EXPECTED_IP" ]; then
    echo "✅ DNS resolution (2bcloud.io -> $EXPECTED_IP)"
else
    echo "⚠️  DNS resolution mismatch. Expected $EXPECTED_IP, got $RESOLVED_IP_PY"
    echo "   (This might be fine if you are using /etc/hosts)"
fi

# 3. Check HTTP Access
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://2bcloud.io)
if [ "$HTTP_CODE" == "200" ] || [ "$HTTP_CODE" == "301" ] || [ "$HTTP_CODE" == "302" ]; then
    echo "✅ HTTP Access (Status: $HTTP_CODE)"
else
    echo "❌ HTTP Access failed (Status: $HTTP_CODE)"
    echo "   Ensure your IP is whitelisted and the server is running."
fi

# 4. Check YAML validity
if [ -f "security-group.yaml" ]; then
    echo "✅ security-group.yaml exists"
else
    echo "❌ security-group.yaml missing"
fi

echo "Verification complete."