import pytest
from unittest.mock import Mock, patch
from search_tools import CourseSearchTool, ToolManager
from vector_store import SearchResults


class TestCourseSearchTool:
    """Test CourseSearchTool functionality"""
    
    def test_get_tool_definition(self, mock_vector_store):
        """Test that tool definition is returned correctly"""
        tool = CourseSearchTool(mock_vector_store)
        definition = tool.get_tool_definition()
        
        assert definition["name"] == "search_course_content"
        assert "description" in definition
        assert "input_schema" in definition
        assert definition["input_schema"]["required"] == ["query"]
        
        # Check properties
        properties = definition["input_schema"]["properties"]
        assert "query" in properties
        assert "course_name" in properties
        assert "lesson_number" in properties
    
    def test_execute_successful_search(self, mock_vector_store, sample_search_results):
        """Test successful search execution"""
        mock_vector_store.search.return_value = sample_search_results
        mock_vector_store.get_lesson_link.return_value = "http://example.com/lesson1"
        
        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute("python programming")
        
        # Check that search was called
        mock_vector_store.search.assert_called_once_with(
            query="python programming",
            course_name=None,
            lesson_number=None
        )
        
        # Check result format
        assert isinstance(result, str)
        assert "Python Programming Fundamentals" in result
        assert "Python is a high-level programming language" in result
        assert "Variables store data values in Python" in result
        
        # Check that sources were tracked
        assert len(tool.last_sources) == 2
        assert tool.last_sources[0]["text"] == "Python Programming Fundamentals - Lesson 1"
        assert tool.last_sources[0]["link"] == "http://example.com/lesson1"
    
    def test_execute_with_course_filter(self, mock_vector_store, sample_search_results):
        """Test search with course name filter"""
        mock_vector_store.search.return_value = sample_search_results
        
        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute("variables", course_name="Python Programming")
        
        mock_vector_store.search.assert_called_once_with(
            query="variables",
            course_name="Python Programming",
            lesson_number=None
        )
        
        assert isinstance(result, str)
        assert "Python Programming Fundamentals" in result
    
    def test_execute_with_lesson_filter(self, mock_vector_store, sample_search_results):
        """Test search with lesson number filter"""
        mock_vector_store.search.return_value = sample_search_results
        
        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute("control flow", lesson_number=3)
        
        mock_vector_store.search.assert_called_once_with(
            query="control flow",
            course_name=None,
            lesson_number=3
        )
        
        assert isinstance(result, str)
    
    def test_execute_with_both_filters(self, mock_vector_store, sample_search_results):
        """Test search with both course and lesson filters"""
        mock_vector_store.search.return_value = sample_search_results
        
        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute("loops", course_name="Python", lesson_number=2)
        
        mock_vector_store.search.assert_called_once_with(
            query="loops",
            course_name="Python",
            lesson_number=2
        )
    
    def test_execute_empty_results(self, mock_vector_store, empty_search_results):
        """Test handling of empty search results"""
        mock_vector_store.search.return_value = empty_search_results
        
        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute("nonexistent topic")
        
        assert result == "No relevant content found."
        assert len(tool.last_sources) == 0
    
    def test_execute_empty_results_with_filters(self, mock_vector_store, empty_search_results):
        """Test empty results with filter information"""
        mock_vector_store.search.return_value = empty_search_results
        
        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute("topic", course_name="Nonexistent Course", lesson_number=5)
        
        expected = "No relevant content found in course 'Nonexistent Course' in lesson 5."
        assert result == expected
    
    def test_execute_search_error(self, mock_vector_store, error_search_results):
        """Test handling of search errors"""
        mock_vector_store.search.return_value = error_search_results
        
        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute("test query")
        
        assert result == "Test error message"
        assert len(tool.last_sources) == 0
    
    def test_execute_vector_store_exception(self, mock_vector_store):
        """Test handling when VectorStore.search raises exception"""
        mock_vector_store.search.side_effect = Exception("Database connection failed")
        
        tool = CourseSearchTool(mock_vector_store)
        
        # This should not raise an exception but return error in SearchResults
        # Based on the code, VectorStore.search should catch exceptions and return SearchResults.empty()
        # Let's verify the actual behavior
        result = tool.execute("test query")
        
        # The result should be an error message if VectorStore handles exceptions properly
        assert isinstance(result, str)
    
    def test_format_results_single_document(self, mock_vector_store):
        """Test formatting of single search result"""
        single_result = SearchResults(
            documents=["This is a test document about Python."],
            metadata=[{"course_title": "Test Course", "lesson_number": 1}],
            distances=[0.1]
        )
        mock_vector_store.search.return_value = single_result
        mock_vector_store.get_lesson_link.return_value = "http://test.com/lesson1"
        
        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute("test")
        
        expected_format = "[Test Course - Lesson 1]\nThis is a test document about Python."
        assert result == expected_format
        assert len(tool.last_sources) == 1
        assert tool.last_sources[0]["text"] == "Test Course - Lesson 1"
        assert tool.last_sources[0]["link"] == "http://test.com/lesson1"
    
    def test_format_results_without_lesson(self, mock_vector_store):
        """Test formatting when lesson number is None"""
        result_no_lesson = SearchResults(
            documents=["Course overview content"],
            metadata=[{"course_title": "Test Course", "lesson_number": None}],
            distances=[0.1]
        )
        mock_vector_store.search.return_value = result_no_lesson
        mock_vector_store.get_lesson_link.return_value = None
        
        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute("overview")
        
        expected_format = "[Test Course]\nCourse overview content"
        assert result == expected_format
        assert len(tool.last_sources) == 1
        assert tool.last_sources[0]["text"] == "Test Course"
        assert tool.last_sources[0]["link"] is None
    
    def test_format_results_multiple_documents(self, mock_vector_store):
        """Test formatting of multiple search results"""
        multi_results = SearchResults(
            documents=[
                "First document about variables",
                "Second document about functions"
            ],
            metadata=[
                {"course_title": "Python Course", "lesson_number": 1},
                {"course_title": "Python Course", "lesson_number": 2}
            ],
            distances=[0.1, 0.2]
        )
        mock_vector_store.search.return_value = multi_results
        mock_vector_store.get_lesson_link.side_effect = ["http://test.com/lesson1", "http://test.com/lesson2"]
        
        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute("python concepts")
        
        expected = "[Python Course - Lesson 1]\nFirst document about variables\n\n[Python Course - Lesson 2]\nSecond document about functions"
        assert result == expected
        assert len(tool.last_sources) == 2
    
    def test_source_tracking_reset(self, mock_vector_store, sample_search_results):
        """Test that sources are properly tracked and reset"""
        mock_vector_store.search.return_value = sample_search_results
        
        tool = CourseSearchTool(mock_vector_store)
        
        # First search
        tool.execute("first query")
        first_sources = tool.last_sources.copy()
        assert len(first_sources) > 0
        
        # Second search should replace sources
        tool.execute("second query")
        second_sources = tool.last_sources
        
        # Sources should be updated
        assert len(second_sources) > 0
        # Since we're using the same mock data, sources should be same content but different objects
        assert second_sources is not first_sources


class TestToolManager:
    """Test ToolManager functionality with CourseSearchTool"""
    
    def test_register_course_search_tool(self, mock_vector_store):
        """Test registering CourseSearchTool with ToolManager"""
        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)
        
        manager.register_tool(tool)
        
        definitions = manager.get_tool_definitions()
        assert len(definitions) == 1
        assert definitions[0]["name"] == "search_course_content"
    
    def test_execute_tool_by_name(self, mock_vector_store, sample_search_results):
        """Test executing CourseSearchTool through ToolManager"""
        mock_vector_store.search.return_value = sample_search_results
        
        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(tool)
        
        result = manager.execute_tool("search_course_content", query="test query")
        
        assert isinstance(result, str)
        assert "Python Programming Fundamentals" in result
    
    def test_execute_nonexistent_tool(self, mock_vector_store):
        """Test executing tool that doesn't exist"""
        manager = ToolManager()
        
        result = manager.execute_tool("nonexistent_tool", query="test")
        
        assert result == "Tool 'nonexistent_tool' not found"
    
    def test_get_last_sources(self, mock_vector_store, sample_search_results):
        """Test retrieving sources from last search"""
        mock_vector_store.search.return_value = sample_search_results
        
        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(tool)
        
        # Execute search
        manager.execute_tool("search_course_content", query="test query")
        
        # Get sources
        sources = manager.get_last_sources()
        assert len(sources) > 0
        assert isinstance(sources[0], dict)
        assert "text" in sources[0]
    
    def test_reset_sources(self, mock_vector_store, sample_search_results):
        """Test resetting sources across all tools"""
        mock_vector_store.search.return_value = sample_search_results
        
        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(tool)
        
        # Execute search to populate sources
        manager.execute_tool("search_course_content", query="test query")
        assert len(manager.get_last_sources()) > 0
        
        # Reset sources
        manager.reset_sources()
        assert len(manager.get_last_sources()) == 0
        assert len(tool.last_sources) == 0