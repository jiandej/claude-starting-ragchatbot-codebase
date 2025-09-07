import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from fastapi.testclient import TestClient

from rag_system import RAGSystem
from config import Config
from session_manager import SessionManager
import anthropic


class TestRAGSystemIntegration:
    """Integration tests for the full RAG system pipeline"""
    
    @pytest.fixture
    def test_rag_config(self, temp_chroma_db):
        """Test configuration with temporary database"""
        return Config(
            ANTHROPIC_API_KEY="test-api-key",
            ANTHROPIC_MODEL="claude-sonnet-4-20250514",
            EMBEDDING_MODEL="all-MiniLM-L6-v2",
            CHUNK_SIZE=800,
            CHUNK_OVERLAP=100,
            MAX_RESULTS=5,
            MAX_HISTORY=2,
            CHROMA_PATH=temp_chroma_db
        )
    
    @patch('rag_system.AIGenerator')
    @patch('rag_system.VectorStore')
    def test_rag_system_initialization(self, mock_vector_store, mock_ai_generator, test_rag_config):
        """Test RAG system initializes all components correctly"""
        rag = RAGSystem(test_rag_config)
        
        # Verify all components are initialized
        assert rag.config == test_rag_config
        assert rag.document_processor is not None
        assert rag.vector_store is not None
        assert rag.ai_generator is not None
        assert rag.session_manager is not None
        assert rag.tool_manager is not None
        assert rag.search_tool is not None
        assert rag.outline_tool is not None
        
        # Verify tools are registered
        definitions = rag.tool_manager.get_tool_definitions()
        tool_names = [tool["name"] for tool in definitions]
        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names
    
    @patch('rag_system.AIGenerator')
    @patch('rag_system.VectorStore')
    def test_query_without_session(self, mock_vector_store_class, mock_ai_generator_class, test_rag_config):
        """Test query processing without session ID"""
        # Mock AI generator
        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.return_value = "Python is a programming language."
        mock_ai_generator_class.return_value = mock_ai_generator
        
        # Mock vector store
        mock_vector_store = Mock()
        mock_vector_store_class.return_value = mock_vector_store
        
        rag = RAGSystem(test_rag_config)
        
        # Mock the tool manager to return sources
        rag.tool_manager.get_last_sources = Mock(return_value=[
            {"text": "Python Course - Lesson 1", "link": "http://example.com/lesson1"}
        ])
        rag.tool_manager.reset_sources = Mock()
        
        response, sources = rag.query("What is Python?")
        
        assert response == "Python is a programming language."
        assert len(sources) == 1
        assert sources[0]["text"] == "Python Course - Lesson 1"
        
        # Verify AI generator was called with tools
        mock_ai_generator.generate_response.assert_called_once()
        call_args = mock_ai_generator.generate_response.call_args
        
        assert call_args[1]["query"] == "Answer this question about course materials: What is Python?"
        assert "tools" in call_args[1]
        assert "tool_manager" in call_args[1]
        assert call_args[1]["conversation_history"] is None
    
    @patch('rag_system.AIGenerator')
    @patch('rag_system.VectorStore')
    def test_query_with_session_management(self, mock_vector_store_class, mock_ai_generator_class, test_rag_config):
        """Test query processing with session management"""
        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.return_value = "Variables store data in Python."
        mock_ai_generator_class.return_value = mock_ai_generator
        
        mock_vector_store = Mock()
        mock_vector_store_class.return_value = mock_vector_store
        
        rag = RAGSystem(test_rag_config)
        rag.tool_manager.get_last_sources = Mock(return_value=[])
        rag.tool_manager.reset_sources = Mock()
        
        # Create a session
        session_id = rag.session_manager.create_session()
        
        # Add some history
        rag.session_manager.add_exchange(session_id, "What is Python?", "Python is a programming language.")
        
        # Make query with session
        response, sources = rag.query("What are variables?", session_id)
        
        assert response == "Variables store data in Python."
        
        # Verify conversation history was passed
        call_args = mock_ai_generator.generate_response.call_args[1]
        assert call_args["conversation_history"] is not None
        assert "What is Python?" in call_args["conversation_history"]
        
        # Verify new exchange was added to session
        history = rag.session_manager.get_conversation_history(session_id)
        assert "What are variables?" in history
        assert "Variables store data in Python." in history
    
    @patch('rag_system.anthropic.Anthropic')
    def test_query_with_real_ai_generator_mock(self, mock_anthropic_class, test_rag_config):
        """Test query with real AIGenerator but mocked Anthropic client"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        # Mock tool use response
        mock_response1 = Mock()
        mock_response1.stop_reason = "tool_use"
        
        mock_tool_use = Mock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.name = "search_course_content"
        mock_tool_use.input = {"query": "python"}
        mock_tool_use.id = "tool_123"
        mock_response1.content = [mock_tool_use]
        
        # Mock final response
        mock_response2 = Mock()
        mock_response2.stop_reason = "end_turn"
        mock_content2 = Mock()
        mock_content2.text = "Python is a versatile programming language used for web development, data science, and automation."
        mock_response2.content = [mock_content2]
        
        mock_client.messages.create.side_effect = [mock_response1, mock_response2]
        
        rag = RAGSystem(test_rag_config)
        
        # Mock the search tool to return a result
        rag.search_tool.execute = Mock(return_value="[Python Course]\nPython is a high-level programming language.")
        rag.search_tool.last_sources = [{"text": "Python Course", "link": "http://example.com"}]
        
        response, sources = rag.query("What is Python?")
        
        assert "Python is a versatile programming language" in response
        assert len(sources) == 1
        assert sources[0]["text"] == "Python Course"
        
        # Verify tool was executed
        rag.search_tool.execute.assert_called_once_with(query="python")
    
    @patch('rag_system.AIGenerator')
    @patch('rag_system.VectorStore')
    def test_query_error_handling(self, mock_vector_store_class, mock_ai_generator_class, test_rag_config):
        """Test error handling in query processing"""
        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.side_effect = Exception("API connection failed")
        mock_ai_generator_class.return_value = mock_ai_generator
        
        mock_vector_store = Mock()
        mock_vector_store_class.return_value = mock_vector_store
        
        rag = RAGSystem(test_rag_config)
        
        # Should raise exception since no error handling in query method
        with pytest.raises(Exception) as exc_info:
            rag.query("What is Python?")
        
        assert "API connection failed" in str(exc_info.value)
    
    @patch('rag_system.VectorStore')
    def test_course_analytics(self, mock_vector_store_class, test_rag_config):
        """Test course analytics functionality"""
        mock_vector_store = Mock()
        mock_vector_store.get_course_count.return_value = 3
        mock_vector_store.get_existing_course_titles.return_value = [
            "Python Fundamentals", 
            "Advanced Python", 
            "Data Science with Python"
        ]
        mock_vector_store_class.return_value = mock_vector_store
        
        rag = RAGSystem(test_rag_config)
        
        analytics = rag.get_course_analytics()
        
        assert analytics["total_courses"] == 3
        assert len(analytics["course_titles"]) == 3
        assert "Python Fundamentals" in analytics["course_titles"]


class TestFastAPIIntegration:
    """Integration tests for the FastAPI application"""
    
    @pytest.fixture
    def test_app(self):
        """Create test FastAPI app"""
        # Import here to avoid circular imports
        from app import app
        return TestClient(app)
    
    @patch('app.rag_system')
    def test_query_endpoint_success(self, mock_rag_system, test_app):
        """Test successful query through API endpoint"""
        mock_rag_system.query.return_value = (
            "Python is a programming language.",
            [{"text": "Python Course", "link": "http://example.com"}]
        )
        mock_rag_system.session_manager.create_session.return_value = "session_123"
        
        response = test_app.post("/api/query", json={
            "query": "What is Python?"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["answer"] == "Python is a programming language."
        assert len(data["sources"]) == 1
        assert data["sources"][0]["text"] == "Python Course"
        assert data["sources"][0]["link"] == "http://example.com"
        assert "session_id" in data
    
    @patch('app.rag_system')
    def test_query_endpoint_with_session(self, mock_rag_system, test_app):
        """Test query endpoint with existing session"""
        mock_rag_system.query.return_value = (
            "Variables store data.",
            []
        )
        
        response = test_app.post("/api/query", json={
            "query": "What are variables?",
            "session_id": "existing_session"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify session was passed to RAG system
        mock_rag_system.query.assert_called_once_with("What are variables?", "existing_session")
        assert data["session_id"] == "existing_session"
    
    @patch('app.rag_system')
    def test_query_endpoint_error_handling(self, mock_rag_system, test_app):
        """Test API error handling"""
        mock_rag_system.query.side_effect = Exception("Internal server error")
        
        response = test_app.post("/api/query", json={
            "query": "Test query"
        })
        
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]
    
    @patch('app.rag_system')
    def test_courses_endpoint(self, mock_rag_system, test_app):
        """Test courses analytics endpoint"""
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 2,
            "course_titles": ["Course 1", "Course 2"]
        }
        
        response = test_app.get("/api/courses")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_courses"] == 2
        assert len(data["course_titles"]) == 2
    
    @patch('app.rag_system')
    def test_clear_session_endpoint(self, mock_rag_system, test_app):
        """Test session clearing endpoint"""
        response = test_app.post("/api/session/test_session/clear")
        
        assert response.status_code == 200
        assert response.json()["message"] == "Session cleared successfully"
        
        mock_rag_system.session_manager.clear_session.assert_called_once_with("test_session")


class TestEndToEndFlow:
    """End-to-end integration tests"""
    
    @patch('vector_store.chromadb')
    @patch('ai_generator.anthropic.Anthropic')
    def test_complete_query_flow_with_mocks(self, mock_anthropic_class, mock_chromadb, test_config):
        """Test complete flow from query to response with all external dependencies mocked"""
        # Mock ChromaDB
        mock_client = Mock()
        mock_collection = Mock()
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection
        
        # Mock search results
        mock_collection.query.return_value = {
            'documents': [['Python is a programming language for beginners']],
            'metadatas': [[{'course_title': 'Python Basics', 'lesson_number': 1}]],
            'distances': [[0.1]]
        }
        
        # Mock course resolution
        mock_collection.get.return_value = {
            'ids': ['Python Basics'],
            'metadatas': [{'title': 'Python Basics'}]
        }
        
        # Mock Anthropic API
        mock_anthropic_client = Mock()
        mock_anthropic_class.return_value = mock_anthropic_client
        
        # First response: tool use
        mock_response1 = Mock()
        mock_response1.stop_reason = "tool_use"
        mock_tool_use = Mock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.name = "search_course_content"
        mock_tool_use.input = {"query": "python programming"}
        mock_tool_use.id = "tool_123"
        mock_response1.content = [mock_tool_use]
        
        # Second response: final answer
        mock_response2 = Mock()
        mock_response2.stop_reason = "end_turn"
        mock_content2 = Mock()
        mock_content2.text = "Python is an excellent programming language for beginners because it has simple syntax and is widely used."
        mock_response2.content = [mock_content2]
        
        mock_anthropic_client.messages.create.side_effect = [mock_response1, mock_response2]
        
        # Create RAG system and execute query
        rag = RAGSystem(test_config)
        response, sources = rag.query("What is Python programming?")
        
        # Verify response
        assert "Python is an excellent programming language" in response
        
        # Verify tool execution happened
        assert mock_anthropic_client.messages.create.call_count == 2
        
        # Verify ChromaDB was queried
        mock_collection.query.assert_called()
    
    def test_session_manager_integration(self, test_config):
        """Test session management integration"""
        session_manager = SessionManager(max_history=2)
        
        # Create session and add exchanges
        session_id = session_manager.create_session()
        
        session_manager.add_exchange(session_id, "What is Python?", "Python is a programming language.")
        session_manager.add_exchange(session_id, "Is it easy to learn?", "Yes, Python is beginner-friendly.")
        
        history = session_manager.get_conversation_history(session_id)
        
        assert "What is Python?" in history
        assert "Python is a programming language." in history
        assert "Is it easy to learn?" in history
        assert "Yes, Python is beginner-friendly." in history
        
        # Test history limit
        session_manager.add_exchange(session_id, "What about libraries?", "Python has many libraries.")
        
        history = session_manager.get_conversation_history(session_id)
        
        # Should only keep last 2 exchanges (max_history=2)
        # So first exchange should be gone
        assert "What is Python?" not in history
        assert "Is it easy to learn?" in history
        assert "What about libraries?" in history