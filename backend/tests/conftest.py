import os
import sys
import tempfile
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_generator import AIGenerator
from config import Config
from models import Course, CourseChunk, Lesson
from search_tools import CourseSearchTool, ToolManager
from vector_store import SearchResults, VectorStore


@pytest.fixture
def sample_course():
    """Sample course data for testing"""
    lessons = [
        Lesson(
            lesson_number=1,
            title="Introduction to Python",
            lesson_link="http://example.com/lesson1",
        ),
        Lesson(
            lesson_number=2,
            title="Variables and Data Types",
            lesson_link="http://example.com/lesson2",
        ),
        Lesson(
            lesson_number=3,
            title="Control Flow",
            lesson_link="http://example.com/lesson3",
        ),
    ]
    return Course(
        title="Python Programming Fundamentals",
        course_link="http://example.com/course",
        instructor="Jane Smith",
        lessons=lessons,
    )


@pytest.fixture
def sample_course_chunks(sample_course):
    """Sample course chunks for testing"""
    return [
        CourseChunk(
            content="Python is a high-level programming language known for its simplicity and readability.",
            course_title=sample_course.title,
            lesson_number=1,
            chunk_index=0,
        ),
        CourseChunk(
            content="Variables in Python are used to store data values. Python has different data types including strings, integers, and floats.",
            course_title=sample_course.title,
            lesson_number=2,
            chunk_index=1,
        ),
        CourseChunk(
            content="Control flow in Python includes if statements, for loops, and while loops.",
            course_title=sample_course.title,
            lesson_number=3,
            chunk_index=2,
        ),
    ]


@pytest.fixture
def mock_vector_store():
    """Mock VectorStore for testing"""
    mock_store = Mock(spec=VectorStore)

    # Default successful search result
    mock_store.search.return_value = SearchResults(
        documents=["Python is a high-level programming language"],
        metadata=[
            {"course_title": "Python Programming Fundamentals", "lesson_number": 1}
        ],
        distances=[0.1],
    )

    mock_store._resolve_course_name.return_value = "Python Programming Fundamentals"
    mock_store.get_lesson_link.return_value = "http://example.com/lesson1"

    return mock_store


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing"""
    mock_client = Mock()

    # Mock successful response
    mock_response = Mock()
    mock_response.stop_reason = "end_turn"
    mock_content = Mock()
    mock_content.text = "This is a test response about Python programming."
    mock_response.content = [mock_content]

    mock_client.messages.create.return_value = mock_response

    return mock_client


@pytest.fixture
def mock_anthropic_client_with_tools():
    """Mock Anthropic client that triggers tool use"""
    mock_client = Mock()

    # First response with tool use
    mock_response1 = Mock()
    mock_response1.stop_reason = "tool_use"

    mock_tool_use = Mock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.name = "search_course_content"
    mock_tool_use.input = {"query": "test query"}
    mock_tool_use.id = "tool_123"

    mock_response1.content = [mock_tool_use]

    # Second response after tool execution
    mock_response2 = Mock()
    mock_response2.stop_reason = "end_turn"
    mock_content2 = Mock()
    mock_content2.text = "Based on the search results, here's information about Python."
    mock_response2.content = [mock_content2]

    mock_client.messages.create.side_effect = [mock_response1, mock_response2]

    return mock_client


@pytest.fixture
def sample_search_results():
    """Sample search results for testing"""
    return SearchResults(
        documents=[
            "Python is a high-level programming language",
            "Variables store data values in Python",
        ],
        metadata=[
            {"course_title": "Python Programming Fundamentals", "lesson_number": 1},
            {"course_title": "Python Programming Fundamentals", "lesson_number": 2},
        ],
        distances=[0.1, 0.2],
    )


@pytest.fixture
def empty_search_results():
    """Empty search results for testing"""
    return SearchResults(documents=[], metadata=[], distances=[])


@pytest.fixture
def error_search_results():
    """Search results with error for testing"""
    return SearchResults.empty("Test error message")


@pytest.fixture
def test_config():
    """Test configuration"""
    return Config(
        ANTHROPIC_API_KEY="test-api-key",
        ANTHROPIC_MODEL="claude-sonnet-4-20250514",
        EMBEDDING_MODEL="all-MiniLM-L6-v2",
        CHUNK_SIZE=800,
        CHUNK_OVERLAP=100,
        MAX_RESULTS=5,
        MAX_HISTORY=2,
        CHROMA_PATH="./test_chroma_db",
    )


@pytest.fixture
def temp_chroma_db():
    """Temporary ChromaDB directory for testing"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def mock_tool_manager():
    """Mock ToolManager for testing"""
    mock_manager = Mock(spec=ToolManager)

    mock_manager.get_tool_definitions.return_value = [
        {
            "name": "search_course_content",
            "description": "Search course materials",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "course_name": {"type": "string"},
                    "lesson_number": {"type": "integer"},
                },
                "required": ["query"],
            },
        }
    ]

    mock_manager.execute_tool.return_value = "Test search result"
    mock_manager.get_last_sources.return_value = [
        {"text": "Test Source", "link": "http://test.com"}
    ]

    return mock_manager
