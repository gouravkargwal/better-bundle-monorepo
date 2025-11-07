#!/bin/bash

# Verify Nginx Proxy Manager Setup for BetterBundle
# This script checks if all requirements are met for Shopify app automated checks
#
# Usage: bash scripts/verify-nginx-setup.sh
#        (or make it executable: chmod +x scripts/verify-nginx-setup.sh && ./scripts/verify-nginx-setup.sh)

DOMAIN="betterbundle.site"
TIMEOUT=10

# Detect if running on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    USE_TIMEOUT="gtimeout"
    DATE_CMD="date -j"
else
    USE_TIMEOUT="timeout"
    DATE_CMD="date -d"
fi

# Check if timeout command exists, fallback to no timeout
if ! command -v timeout &> /dev/null && ! command -v gtimeout &> /dev/null; then
    USE_TIMEOUT=""
fi

echo "🔍 Verifying Nginx Proxy Manager Setup for ${DOMAIN}"
echo "=================================================="
echo ""

# Function to print status (works with both bash and sh)
print_status() {
    if [ $1 -eq 0 ]; then
        printf "\033[0;32m✅ %s\033[0m\n" "$2"
    else
        printf "\033[0;31m❌ %s\033[0m\n" "$2"
    fi
}

print_warning() {
    printf "\033[1;33m⚠️  %s\033[0m\n" "$1"
}

# Check 1: DNS Resolution
echo "1. Checking DNS resolution..."
if dig +short ${DOMAIN} | grep -q '^[0-9]'; then
    print_status 0 "DNS resolves correctly"
    IP=$(dig +short ${DOMAIN} | head -n1)
    echo "   IP Address: ${IP}"
else
    print_status 1 "DNS does not resolve correctly"
fi
echo ""

# Check 2: HTTP to HTTPS Redirect
echo "2. Checking HTTP to HTTPS redirect..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -L http://${DOMAIN} 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
    print_status 0 "HTTP redirects to HTTPS (HTTP code: ${HTTP_CODE})"
else
    print_status 1 "HTTP redirect not working (HTTP code: ${HTTP_CODE})"
fi
echo ""

# Check 3: SSL Certificate
echo "3. Checking SSL certificate..."
if [ -n "$USE_TIMEOUT" ]; then
    SSL_CHECK=$(echo | $USE_TIMEOUT $TIMEOUT openssl s_client -servername ${DOMAIN} -connect ${DOMAIN}:443 -quiet 2>/dev/null | openssl x509 -noout -dates 2>/dev/null)
else
    SSL_CHECK=$(echo | openssl s_client -servername ${DOMAIN} -connect ${DOMAIN}:443 -quiet 2>/dev/null | openssl x509 -noout -dates 2>/dev/null)
fi

if [ $? -eq 0 ] && [ -n "$SSL_CHECK" ]; then
    print_status 0 "SSL certificate is valid"
    echo "$SSL_CHECK" | while IFS= read -r line; do
        echo "   $line"
    done
else
    print_status 1 "SSL certificate check failed or timed out"
fi
echo ""

# Check 4: Certificate Expiration
echo "4. Checking certificate expiration..."
if [ -n "$USE_TIMEOUT" ]; then
    EXPIRY=$(echo | $USE_TIMEOUT $TIMEOUT openssl s_client -servername ${DOMAIN} -connect ${DOMAIN}:443 -quiet 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
else
    EXPIRY=$(echo | openssl s_client -servername ${DOMAIN} -connect ${DOMAIN}:443 -quiet 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
fi

if [ -n "$EXPIRY" ]; then
    # Handle macOS date format
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS date format: "Jan 15 12:00:00 2025 GMT"
        EXPIRY_EPOCH=$(date -j -f "%b %d %H:%M:%S %Y %Z" "$EXPIRY" +%s 2>/dev/null || echo "0")
    else
        # Linux date format
        EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s 2>/dev/null || echo "0")
    fi
    
    if [ "$EXPIRY_EPOCH" != "0" ]; then
        NOW_EPOCH=$(date +%s)
        DAYS_LEFT=$(( ($EXPIRY_EPOCH - $NOW_EPOCH) / 86400 ))
        
        if [ $DAYS_LEFT -gt 30 ]; then
            print_status 0 "Certificate expires in ${DAYS_LEFT} days"
        elif [ $DAYS_LEFT -gt 0 ]; then
            print_warning "Certificate expires in ${DAYS_LEFT} days (renewal recommended)"
        else
            print_status 1 "Certificate has expired!"
        fi
    else
        print_warning "Could not parse certificate expiration date"
    fi
else
    print_status 1 "Could not determine certificate expiration"
fi
echo ""

# Check 5: Security Headers
echo "5. Checking security headers..."
HEADERS=$(curl -sI https://${DOMAIN} 2>/dev/null)

# Check Content-Security-Policy
if echo "$HEADERS" | grep -qi "Content-Security-Policy"; then
    print_status 0 "Content-Security-Policy header present"
else
    print_status 1 "Content-Security-Policy header missing"
fi

# Check X-Frame-Options
if echo "$HEADERS" | grep -qi "X-Frame-Options"; then
    print_status 0 "X-Frame-Options header present"
else
    print_warning "X-Frame-Options header missing (may be intentional)"
fi

# Check Strict-Transport-Security (HSTS)
if echo "$HEADERS" | grep -qi "Strict-Transport-Security"; then
    print_status 0 "HSTS header present"
else
    print_status 1 "HSTS header missing"
fi

# Check X-Content-Type-Options
if echo "$HEADERS" | grep -qi "X-Content-Type-Options"; then
    print_status 0 "X-Content-Type-Options header present"
else
    print_warning "X-Content-Type-Options header missing"
fi
echo ""

# Check 6: Webhook Endpoints
echo "6. Checking webhook endpoints..."
WEBHOOK_ENDPOINTS=(
    "/webhooks/app/uninstalled"
    "/webhooks/gdpr/customers_data_request"
    "/webhooks/gdpr/customers_redact"
    "/webhooks/gdpr/shop_redact"
)

for endpoint in "${WEBHOOK_ENDPOINTS[@]}"; do
    if [ -n "$USE_TIMEOUT" ]; then
        HTTP_CODE=$($USE_TIMEOUT $TIMEOUT curl -s -o /dev/null -w "%{http_code}" -X POST https://${DOMAIN}${endpoint} --max-time $TIMEOUT 2>/dev/null || echo "000")
    else
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST https://${DOMAIN}${endpoint} --max-time $TIMEOUT 2>/dev/null || echo "000")
    fi
    
    if [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "200" ]; then
        print_status 0 "${endpoint} is accessible (HTTP ${HTTP_CODE})"
    elif [ "$HTTP_CODE" = "405" ]; then
        print_warning "${endpoint} returns 405 (Method Not Allowed for GET - this is OK)"
    elif [ "$HTTP_CODE" = "000" ]; then
        print_status 1 "${endpoint} connection failed or timed out"
    else
        print_status 1 "${endpoint} returned unexpected code: ${HTTP_CODE}"
    fi
done
echo ""

# Check 7: App Route Accessibility
echo "7. Checking app routes..."
APP_ROUTES=(
    "/"
    "/app"
    "/auth"
)

for route in "${APP_ROUTES[@]}"; do
    if [ -n "$USE_TIMEOUT" ]; then
        HTTP_CODE=$($USE_TIMEOUT $TIMEOUT curl -s -o /dev/null -w "%{http_code}" https://${DOMAIN}${route} --max-time $TIMEOUT 2>/dev/null || echo "000")
    else
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://${DOMAIN}${route} --max-time $TIMEOUT 2>/dev/null || echo "000")
    fi
    
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ] || [ "$HTTP_CODE" = "301" ]; then
        print_status 0 "${route} is accessible (HTTP ${HTTP_CODE})"
    elif [ "$HTTP_CODE" = "000" ]; then
        print_status 1 "${route} connection failed or timed out"
    else
        print_status 1 "${route} returned unexpected code: ${HTTP_CODE}"
    fi
done
echo ""

# Check 8: WebSocket Support (if needed)
echo "8. Checking WebSocket support..."
WS_UPGRADE=$(curl -sI -H "Upgrade: websocket" -H "Connection: Upgrade" https://${DOMAIN} 2>/dev/null | grep -i "upgrade" || echo "")
if [ -n "$WS_UPGRADE" ]; then
    print_status 0 "WebSocket upgrade header supported"
else
    print_warning "WebSocket support may not be configured (optional)"
fi
echo ""

# Summary
echo "=================================================="
echo "📊 Verification Summary"
echo "=================================================="
echo ""
echo "If all checks pass, your setup should meet Shopify's requirements:"
echo "  ✅ Valid TLS certificate"
echo "  ✅ Proper security headers"
echo "  ✅ Webhook endpoints accessible"
echo "  ✅ App routes accessible"
echo ""
echo "Next steps:"
echo "  1. Test app installation in Shopify"
echo "  2. Verify webhook delivery in Partner Dashboard"
echo "  3. Check app loads correctly in Shopify Admin"
echo ""

