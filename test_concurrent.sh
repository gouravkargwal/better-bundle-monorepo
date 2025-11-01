#!/bin/bash

# Your token (expires at 1761990338 - replace with a fresh one if expired)
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzaG9wX2lkIjoiYmE0YTJkMzUtMWFjMC00ODg4LTllNjctYjBiOWVkNmFhY2EzIiwic2hvcF9kb21haW4iOiJiZXR0ZXItYnVuZGxlLWRldi1iYXNpYy5teXNob3BpZnkuY29tIiwiaXNfc2VydmljZV9hY3RpdmUiOnRydWUsInNob3BpZnlfcGx1cyI6ZmFsc2UsInRva2VuX3R5cGUiOiJhY2Nlc3MiLCJleHAiOjE3NjE5OTAzMzgsImlhdCI6MTc2MTk4ODUzOH0.9EJ6Ul4D_LCkm-CYcQzGvahLih0xwjPQfi5CKkgDths"

URL="http://localhost:8001/api/session/get-or-create-session"

# Function to make a single request
make_request() {
    local request_num=$1
    echo "Starting request $request_num..."
    
    curl -X POST "$URL" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -H "User-Agent: PostmanRuntime/7.49.1" \
        -d '{
            "shop_domain": "better-bundle-dev-basic.myshopify.com",
            "customer_id": null,
            "browser_session_id": "bb_5d9f9f6653f8",
            "client_id": null
        }' \
        -w "\n[Request $request_num] Status: %{http_code} | Time: %{time_total}s\n" \
        -s
    
    echo "Request $request_num completed"
}

# Launch 10 concurrent requests
echo "🚀 Launching 50 concurrent requests..."
start_time=$(date +%s)

for i in {1..50}; do
    make_request $i &
done

# Wait for all background jobs to complete
wait

end_time=$(date +%s)
duration=$((end_time - start_time))

echo ""
echo "✅ All 50 requests completed in ${duration} seconds"