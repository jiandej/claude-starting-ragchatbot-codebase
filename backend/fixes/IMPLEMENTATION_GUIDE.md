# RAG System Fix Implementation Guide

## Critical Fix: API Key Configuration

### Step 1: Create Environment File
```bash
# Create .env file from template
cp .env.example .env

# Add your actual Anthropic API key
echo "ANTHROPIC_API_KEY=your-actual-api-key-here" > .env
```

**This single fix will resolve the "query failed" issue.**

## Recommended Fixes (Priority Order)

### Priority 1: Enhanced Error Handling in RAGSystem

**File:** `backend/rag_system.py`

Replace the current `query` method (lines 104-142) with the enhanced version:

```python
def query(self, query: str, session_id: Optional[str] = None) -> Tuple[str, List[str]]:
    """Process a user query using the RAG system with robust error handling."""
    try:
        # Validate API key first
        if not self.config.ANTHROPIC_API_KEY or self.config.ANTHROPIC_API_KEY.strip() == "":
            return ("I'm sorry, but the system is not properly configured with an API key. Please contact your administrator.", [])
        
        # ... existing code ...
        
    except anthropic.AuthenticationError as e:
        error_msg = "Authentication failed. Please check the API key configuration."
        print(f"Anthropic API Authentication Error: {e}")
        return (error_msg, [])
        
    except anthropic.RateLimitError as e:
        error_msg = "The system is currently experiencing high demand. Please try again in a few moments."
        print(f"Anthropic API Rate Limit Error: {e}")
        return (error_msg, [])
        
    except anthropic.APIError as e:
        error_msg = "I'm experiencing technical difficulties. Please try again later."
        print(f"Anthropic API Error: {e}")
        return (error_msg, [])
        
    except Exception as e:
        error_msg = "An unexpected error occurred while processing your request."
        print(f"Unexpected error in RAG query: {e}")
        import traceback
        traceback.print_exc()
        return (error_msg, [])
```

**Required Import:** Add to top of `rag_system.py`:
```python
import anthropic
```

### Priority 2: Add Health Check Endpoint

**File:** `backend/app.py`

Add this new endpoint after existing endpoints:

```python
from datetime import datetime

@app.get("/api/health")
async def health_check():
    """Check system health and configuration"""
    health_status = {
        "status": "healthy",
        "components": {},
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Check API key configuration
    if rag_system.config.ANTHROPIC_API_KEY:
        health_status["components"]["anthropic_api"] = "configured"
    else:
        health_status["components"]["anthropic_api"] = "not_configured"
        health_status["status"] = "degraded"
    
    # Check ChromaDB
    try:
        count = rag_system.vector_store.get_course_count()
        health_status["components"]["vector_store"] = f"operational ({count} courses)"
    except Exception as e:
        health_status["components"]["vector_store"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Check tools
    try:
        tools = rag_system.tool_manager.get_tool_definitions()
        health_status["components"]["tools"] = f"operational ({len(tools)} tools)"
    except Exception as e:
        health_status["components"]["tools"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    return health_status
```

### Priority 3: Configuration Validation

**File:** `backend/rag_system.py`

Add validation to the `__init__` method (after line 14):

```python
def __init__(self, config):
    self.config = config
    
    # Validate configuration
    validation_errors = []
    
    if not config.ANTHROPIC_API_KEY or config.ANTHROPIC_API_KEY.strip() == "":
        validation_errors.append("ANTHROPIC_API_KEY is not set or empty")
        
    if not config.CHROMA_PATH:
        validation_errors.append("CHROMA_PATH is not configured")
        
    if validation_errors:
        error_message = "Configuration validation failed:\n" + "\n".join(f"- {error}" for error in validation_errors)
        print(f"WARNING: {error_message}")
        print("The system may not function properly. Please check your .env file.")
    
    # Continue with existing initialization...
```

## Testing the Fixes

### Test the Critical Fix
```bash
# After setting up .env with valid API key
cd backend
uv run python3 -c "
import sys; sys.path.append('.')
from rag_system import RAGSystem
from config import config
rag = RAGSystem(config)
response, sources = rag.query('What is Python programming?')
print('Response:', response[:100])
print('Sources count:', len(sources))
"
```

### Test Health Check
```bash
# Start the server
./run.sh

# In another terminal
curl http://localhost:8000/api/health
```

## Test Infrastructure Fixes (Optional)

If you want to fix the failing tests, apply these changes:

### Fix 1: Vector Store Test Mocking
**File:** `backend/tests/test_vector_store.py`

Replace the problematic test methods with the fixed versions from `fixes/test_fixes.py`.

### Fix 2: AI Generator Exception Tests
**File:** `backend/tests/test_ai_generator.py`

Update the exception handling tests with proper Anthropic error construction.

## Verification Steps

After implementing the fixes:

1. **Test API Key Configuration:**
   ```bash
   curl -X POST http://localhost:8000/api/query \
   -H "Content-Type: application/json" \
   -d '{"query": "What is Python programming?"}'
   ```

2. **Check Health Status:**
   ```bash
   curl http://localhost:8000/api/health
   ```

3. **Verify Error Handling:**
   ```bash
   # Temporarily rename .env to test error handling
   mv .env .env.backup
   curl -X POST http://localhost:8000/api/query \
   -H "Content-Type: application/json" \
   -d '{"query": "test"}'
   # Should return user-friendly error message
   mv .env.backup .env
   ```

## Expected Results

After implementing these fixes:

- ✅ "Query failed" errors should be resolved
- ✅ Users will receive helpful error messages instead of generic failures  
- ✅ System status can be monitored via health check endpoint
- ✅ Configuration issues will be detected at startup
- ✅ API errors will be handled gracefully

The system should successfully process queries and return relevant course content with proper source attribution.