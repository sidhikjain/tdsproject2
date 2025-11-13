#!/bin/bash
# health_check.sh - Test if your app is running correctly

echo "🔍 Testing FastAPI Quiz Solver Application..."
echo ""

# Check if server is running
echo "1️⃣ Checking if server is responding..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs)
if [ "$HTTP_CODE" -eq 200 ]; then
    echo "✅ Server is running (HTTP $HTTP_CODE)"
else
    echo "❌ Server is not responding (HTTP $HTTP_CODE)"
    exit 1
fi

echo ""
echo "2️⃣ Testing /docs endpoint (Swagger UI)..."
curl -s http://localhost:8000/docs > /dev/null && echo "✅ Swagger UI accessible at http://localhost:8000/docs"

echo ""
echo "3️⃣ Testing /endpoint with invalid secret..."
RESPONSE=$(curl -s -X POST http://localhost:8000/endpoint \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","secret":"wrong_secret","url":"https://example.com"}')
if [[ "$RESPONSE" == *"Invalid secret"* ]]; then
    echo "✅ Security validation working (rejected invalid secret)"
else
    echo "❌ Unexpected response: $RESPONSE"
fi

echo ""
echo "4️⃣ Testing /endpoint with missing fields..."
RESPONSE=$(curl -s -X POST http://localhost:8000/endpoint \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com"}')
if [[ "$RESPONSE" == *"detail"* ]]; then
    echo "✅ Input validation working (rejected incomplete payload)"
else
    echo "❌ Unexpected response: $RESPONSE"
fi

echo ""
echo "5️⃣ OpenAPI spec available..."
curl -s http://localhost:8000/openapi.json > /dev/null && echo "✅ OpenAPI spec accessible at http://localhost:8000/openapi.json"

echo ""
echo "🎉 Basic health checks passed!"
echo ""
echo "📝 Next steps:"
echo "   • Visit: http://localhost:8000/docs (Interactive API docs)"
echo "   • Test with valid secret from your .env file"
echo "   • Use test_quiz.py for full integration testing"
