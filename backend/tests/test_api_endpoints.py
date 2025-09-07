"""
API endpoint tests for the RAG system FastAPI application.

Tests the main API endpoints for proper request/response handling:
- /api/query: Query processing endpoint
- /api/courses: Course statistics endpoint  
- /api/session/{session_id}/clear: Session management endpoint
- /: Root endpoint
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.api
def test_root_endpoint(client):
    """Test the root endpoint returns correct response"""
    response = client.get("/")
    
    assert response.status_code == 200
    assert response.json() == {"message": "RAG System API"}


@pytest.mark.api
def test_query_endpoint_basic(client):
    """Test basic query functionality"""
    query_data = {
        "query": "What is Python?",
        "session_id": None
    }
    
    response = client.post("/api/query", json=query_data)
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "answer" in data
    assert "sources" in data
    assert "session_id" in data
    
    # Check content
    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 0
    assert isinstance(data["sources"], list)
    assert isinstance(data["session_id"], str)
    assert len(data["session_id"]) > 0


@pytest.mark.api
def test_query_endpoint_with_session(client):
    """Test query with existing session ID"""
    query_data = {
        "query": "Explain variables in Python",
        "session_id": "existing-session-123"
    }
    
    response = client.post("/api/query", json=query_data)
    
    assert response.status_code == 200
    data = response.json()
    
    # Should use the provided session ID
    assert data["session_id"] == "existing-session-123"
    assert "answer" in data
    assert "sources" in data


@pytest.mark.api
def test_query_endpoint_source_format(client):
    """Test that sources are properly formatted"""
    query_data = {
        "query": "What are Python data types?"
    }
    
    response = client.post("/api/query", json=query_data)
    
    assert response.status_code == 200
    data = response.json()
    
    sources = data["sources"]
    assert len(sources) > 0
    
    # Check source structure - should be SourceData objects or strings
    for source in sources:
        if isinstance(source, dict):
            assert "text" in source
            # link is optional
            if "link" in source:
                assert isinstance(source["link"], (str, type(None)))
        else:
            assert isinstance(source, str)


@pytest.mark.api
def test_query_endpoint_missing_query(client):
    """Test query endpoint with missing query parameter"""
    query_data = {}  # Missing required 'query' field
    
    response = client.post("/api/query", json=query_data)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.api
def test_query_endpoint_empty_query(client):
    """Test query endpoint with empty query"""
    query_data = {
        "query": ""
    }
    
    response = client.post("/api/query", json=query_data)
    
    # Should still process, even if query is empty
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert "session_id" in data


@pytest.mark.api
def test_courses_endpoint(client):
    """Test course statistics endpoint"""
    response = client.get("/api/courses")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "total_courses" in data
    assert "course_titles" in data
    
    # Check data types
    assert isinstance(data["total_courses"], int)
    assert isinstance(data["course_titles"], list)
    
    # Check content consistency
    assert data["total_courses"] >= 0
    assert len(data["course_titles"]) == data["total_courses"]


@pytest.mark.api
def test_clear_session_endpoint(client):
    """Test session clearing endpoint"""
    session_id = "test-session-456"
    
    response = client.post(f"/api/session/{session_id}/clear")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data == {"message": "Session cleared successfully"}


@pytest.mark.api
def test_clear_session_with_special_characters(client):
    """Test session clearing with session ID containing special characters"""
    session_id = "test-session-123_abc"
    
    response = client.post(f"/api/session/{session_id}/clear")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data == {"message": "Session cleared successfully"}


@pytest.mark.api
def test_query_endpoint_invalid_json(client):
    """Test query endpoint with invalid JSON"""
    response = client.post(
        "/api/query",
        data="invalid json",
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 422  # JSON parsing error


@pytest.mark.api
def test_query_endpoint_wrong_content_type(client):
    """Test query endpoint with wrong content type"""
    response = client.post(
        "/api/query",
        data="query=test",
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    assert response.status_code == 422  # Content type validation error


@pytest.mark.api
def test_nonexistent_endpoint(client):
    """Test accessing non-existent endpoint"""
    response = client.get("/api/nonexistent")
    
    assert response.status_code == 404


@pytest.mark.api
def test_wrong_method_on_query(client):
    """Test using wrong HTTP method on query endpoint"""
    response = client.get("/api/query")
    
    assert response.status_code == 405  # Method not allowed


@pytest.mark.api
def test_wrong_method_on_courses(client):
    """Test using wrong HTTP method on courses endpoint"""
    response = client.post("/api/courses")
    
    assert response.status_code == 405  # Method not allowed


@pytest.mark.api
def test_cors_headers(client):
    """Test that CORS headers are properly set"""
    response = client.get("/api/courses")
    
    assert response.status_code == 200
    # Note: TestClient may not show all CORS headers, but the middleware is configured


@pytest.mark.api
@pytest.mark.integration
def test_query_to_courses_workflow(client):
    """Test a typical workflow: query -> get courses"""
    # First make a query
    query_response = client.post("/api/query", json={"query": "What is Python?"})
    assert query_response.status_code == 200
    
    # Then get course statistics
    courses_response = client.get("/api/courses")
    assert courses_response.status_code == 200
    
    # Both should work independently
    query_data = query_response.json()
    courses_data = courses_response.json()
    
    assert "answer" in query_data
    assert "total_courses" in courses_data


@pytest.mark.api
@pytest.mark.integration
def test_session_workflow(client):
    """Test session management workflow"""
    # Create a query which should create a new session
    query1_response = client.post("/api/query", json={"query": "What is Python?"})
    assert query1_response.status_code == 200
    
    session_id = query1_response.json()["session_id"]
    
    # Use the same session for another query
    query2_response = client.post("/api/query", json={
        "query": "Tell me more about variables",
        "session_id": session_id
    })
    assert query2_response.status_code == 200
    assert query2_response.json()["session_id"] == session_id
    
    # Clear the session
    clear_response = client.post(f"/api/session/{session_id}/clear")
    assert clear_response.status_code == 200