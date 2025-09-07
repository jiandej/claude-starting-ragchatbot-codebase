import pytest
from unittest.mock import Mock, patch, MagicMock
from ai_generator import AIGenerator, ConversationRound, SequentialToolProcessor
import anthropic


class TestSequentialToolCalling:
    """Test sequential tool calling behavior focusing on external API behavior"""
    
    @pytest.fixture
    def mock_anthropic_client_sequential(self):
        """Mock Anthropic client for sequential tool calling scenarios"""
        mock_client = Mock()
        
        # Mock responses for a 2-round scenario
        # Round 1: Claude wants to search for React authentication
        round1_response = Mock()
        round1_response.stop_reason = "tool_use"
        round1_tool_use = Mock()
        round1_tool_use.type = "tool_use"
        round1_tool_use.name = "search_course_content"
        round1_tool_use.input = {"query": "React authentication"}
        round1_tool_use.id = "tool_round1"
        round1_response.content = [round1_tool_use]
        
        # Round 2: Claude wants to search for Node authentication
        round2_response = Mock()
        round2_response.stop_reason = "tool_use"
        round2_tool_use = Mock()
        round2_tool_use.type = "tool_use"
        round2_tool_use.name = "search_course_content"
        round2_tool_use.input = {"query": "Node.js authentication"}
        round2_tool_use.id = "tool_round2"
        round2_response.content = [round2_tool_use]
        
        # Final response: Claude synthesizes the results
        final_response = Mock()
        final_response.stop_reason = "end_turn"
        final_content = Mock()
        final_content.text = "React uses JWT tokens for authentication while Node.js uses session-based authentication with middleware."
        final_response.content = [final_content]
        
        mock_client.messages.create.side_effect = [round1_response, round2_response, final_response]
        return mock_client
    
    @pytest.fixture
    def mock_tool_manager_sequential(self):
        """Mock tool manager that returns realistic sequential responses"""
        mock_manager = Mock()
        
        def execute_tool_side_effect(tool_name, **kwargs):
            if "React" in kwargs.get("query", ""):
                return "[React Authentication Course]\nReact uses JWT tokens and OAuth for user authentication. Components handle login state through context providers."
            elif "Node" in kwargs.get("query", ""):
                return "[Node.js Backend Course]\nNode.js implements authentication using Express middleware, session stores, and passport strategies."
            else:
                return "No relevant content found."
        
        mock_manager.execute_tool.side_effect = execute_tool_side_effect
        mock_manager.get_last_sources.return_value = [
            {"text": "React Course - Lesson 3", "link": "http://example.com/react/3"},
            {"text": "Node Course - Lesson 5", "link": "http://example.com/node/5"}
        ]
        
        return mock_manager
    
    @patch('ai_generator.anthropic.Anthropic')
    def test_course_comparison_sequential_behavior(self, mock_anthropic_class):
        """Test that comparing courses uses sequential rounds (external behavior test)"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        # Mock responses for a 2-round scenario
        # Round 1: Claude wants to search for React authentication
        round1_response = Mock()
        round1_response.stop_reason = "tool_use"
        round1_tool_use = Mock()
        round1_tool_use.type = "tool_use"
        round1_tool_use.name = "search_course_content"
        round1_tool_use.input = {"query": "React authentication"}
        round1_tool_use.id = "tool_round1"
        round1_response.content = [round1_tool_use]
        
        # Round 2: Claude wants to search for Node authentication
        round2_response = Mock()
        round2_response.stop_reason = "tool_use"
        round2_tool_use = Mock()
        round2_tool_use.type = "tool_use"
        round2_tool_use.name = "search_course_content"
        round2_tool_use.input = {"query": "Node.js authentication"}
        round2_tool_use.id = "tool_round2"
        round2_response.content = [round2_tool_use]
        
        # Final response: Claude synthesizes the results
        final_response = Mock()
        final_response.stop_reason = "end_turn"
        final_content = Mock()
        final_content.text = "React uses JWT tokens for authentication while Node.js uses session-based authentication with middleware."
        final_response.content = [final_content]
        
        mock_client.messages.create.side_effect = [round1_response, round2_response, final_response]
        
        # Mock tool manager
        mock_tool_manager = Mock()
        def execute_tool_side_effect(tool_name, **kwargs):
            if "React" in kwargs.get("query", ""):
                return "[React Authentication Course]\nReact uses JWT tokens and OAuth for user authentication."
            elif "Node" in kwargs.get("query", ""):
                return "[Node.js Backend Course]\nNode.js implements authentication using Express middleware."
            else:
                return "No relevant content found."
        
        mock_tool_manager.execute_tool.side_effect = execute_tool_side_effect
        
        generator = AIGenerator("test-api-key", "claude-sonnet-4")
        
        # Test the complete behavior without caring about internal rounds
        result = generator.generate_response(
            "Compare authentication approaches in React vs Node.js courses",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager
        )
        
        # Verify external behavior
        assert "React" in result and "Node" in result
        assert "authentication" in result.lower()
        assert "JWT" in result or "session" in result
        
        # Verify that multiple API calls were made (sequential behavior)
        assert mock_client.messages.create.call_count == 3
        
        # Verify tool manager was called multiple times (sequential searches)
        assert mock_tool_manager.execute_tool.call_count == 2
    
    @patch('ai_generator.anthropic.Anthropic')
    def test_outline_then_search_behavior(self, mock_anthropic_class):
        """Test outline-then-search pattern behavior"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        # Round 1: Get course outline
        outline_response = Mock()
        outline_response.stop_reason = "tool_use"
        outline_tool = Mock()
        outline_tool.type = "tool_use"
        outline_tool.name = "get_course_outline"
        outline_tool.input = {"course_name": "Python Programming"}
        outline_tool.id = "outline_tool"
        outline_response.content = [outline_tool]
        
        # Round 2: Search specific lesson content
        search_response = Mock()
        search_response.stop_reason = "tool_use"
        search_tool = Mock()
        search_tool.type = "tool_use"
        search_tool.name = "search_course_content"
        search_tool.input = {"query": "variables", "lesson_number": 2}
        search_tool.id = "search_tool"
        search_response.content = [search_tool]
        
        # Final synthesis
        final_response = Mock()
        final_response.stop_reason = "end_turn"
        final_content = Mock()
        final_content.text = "The Python Programming course has 5 lessons. Lesson 2 covers variables and data types, including string, integer, and float types."
        final_response.content = [final_content]
        
        mock_client.messages.create.side_effect = [outline_response, search_response, final_response]
        
        # Mock tool manager
        mock_tool_manager = Mock()
        def outline_search_side_effect(tool_name, **kwargs):
            if tool_name == "get_course_outline":
                return "**Python Programming**\n1. Introduction\n2. Variables and Data Types\n3. Control Flow\n4. Functions\n5. Classes"
            elif tool_name == "search_course_content":
                return "[Python Course - Lesson 2]\nVariables in Python store data values. Python supports string, integer, float, and boolean types."
        
        mock_tool_manager.execute_tool.side_effect = outline_search_side_effect
        
        generator = AIGenerator("test-api-key", "claude-sonnet-4")
        
        result = generator.generate_response(
            "Show me the Python course outline and then find details about variables in lesson 2",
            tools=[{"name": "get_course_outline"}, {"name": "search_course_content"}],
            tool_manager=mock_tool_manager
        )
        
        # Verify sequential behavior worked
        assert "Python Programming" in result
        assert "lesson" in result.lower()
        assert "variables" in result.lower()
        assert mock_client.messages.create.call_count == 3
        assert mock_tool_manager.execute_tool.call_count == 2
    
    @patch('ai_generator.anthropic.Anthropic') 
    def test_loop_detection_behavior(self, mock_anthropic_class):
        """Test that loop detection prevents repetitive searches"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        # Claude tries to make the same search twice
        same_search_response1 = Mock()
        same_search_response1.stop_reason = "tool_use"
        tool1 = Mock()
        tool1.type = "tool_use"
        tool1.name = "search_course_content"
        tool1.input = {"query": "python basics"}
        tool1.id = "tool1"
        same_search_response1.content = [tool1]
        
        same_search_response2 = Mock()
        same_search_response2.stop_reason = "tool_use"
        tool2 = Mock()
        tool2.type = "tool_use"
        tool2.name = "search_course_content"
        tool2.input = {"query": "python basics"}  # Same search
        tool2.id = "tool2"
        same_search_response2.content = [tool2]
        
        mock_client.messages.create.side_effect = [same_search_response1, same_search_response2]
        
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Python basics content"
        
        generator = AIGenerator("test-api-key", "claude-sonnet-4")
        
        result = generator.generate_response(
            "Tell me about Python basics",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager
        )
        
        # Should detect loop and continue with loop detection message 
        # The first call should succeed, second should be detected as loop
        assert mock_tool_manager.execute_tool.call_count >= 1
        # Should still return a result (not crash)
        assert isinstance(result, str)
        assert len(result) > 0
    
    @patch('ai_generator.anthropic.Anthropic')
    def test_error_recovery_behavior(self, mock_anthropic_class):
        """Test graceful handling of tool execution errors"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        # Claude wants to search, but tool fails
        tool_response = Mock()
        tool_response.stop_reason = "tool_use"
        tool_use = Mock()
        tool_use.type = "tool_use"
        tool_use.name = "search_course_content"
        tool_use.input = {"query": "test"}
        tool_use.id = "tool_fail"
        tool_response.content = [tool_use]
        
        # Final response after error
        final_response = Mock()
        final_response.stop_reason = "end_turn"
        final_content = Mock()
        final_content.text = "I encountered an error while searching, but I can tell you about Python programming from my general knowledge."
        final_response.content = [final_content]
        
        mock_client.messages.create.side_effect = [tool_response, final_response]
        
        # Mock tool manager that raises exception
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = Exception("Database connection failed")
        
        generator = AIGenerator("test-api-key", "claude-sonnet-4")
        
        result = generator.generate_response(
            "What is Python?",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager
        )
        
        # Should handle error gracefully and still return response
        assert isinstance(result, str)
        assert len(result) > 0
        # Should not contain raw exception details
        assert "Traceback" not in result
    
    @patch('ai_generator.anthropic.Anthropic')
    def test_max_rounds_termination(self, mock_anthropic_class):
        """Test that system respects maximum round limits"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        # Claude keeps wanting to use tools beyond max rounds
        persistent_tool_response = Mock()
        persistent_tool_response.stop_reason = "tool_use"
        tool_use = Mock()
        tool_use.type = "tool_use"
        tool_use.name = "search_course_content"
        tool_use.input = {"query": "more info"}
        tool_use.id = "persistent_tool"
        persistent_tool_response.content = [tool_use]
        
        # Final synthesis response
        final_response = Mock()
        final_response.stop_reason = "end_turn"
        final_content = Mock()
        final_content.text = "Based on the searches performed, here's what I found about the courses."
        final_response.content = [final_content]
        
        # Return tool responses for max rounds, then final response
        mock_client.messages.create.side_effect = [
            persistent_tool_response,  # Round 1
            persistent_tool_response,  # Round 2
            final_response             # Final synthesis
        ]
        
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Some search results"
        
        generator = AIGenerator("test-api-key", "claude-sonnet-4", max_tool_rounds=2)
        
        result = generator.generate_response(
            "Tell me everything about all courses",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager
        )
        
        # Should respect max rounds (2) and make final synthesis call
        assert mock_client.messages.create.call_count == 3  # 2 tool rounds + 1 synthesis
        assert mock_tool_manager.execute_tool.call_count == 2  # Only 2 tool calls
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_single_round_fallback_behavior(self):
        """Test that single responses still work (no tools or immediate text response)"""
        with patch('ai_generator.anthropic.Anthropic') as mock_anthropic_class:
            mock_client = Mock()
            mock_anthropic_class.return_value = mock_client
            
            # Claude gives direct text response (no tools)
            direct_response = Mock()
            direct_response.stop_reason = "end_turn"
            direct_content = Mock()
            direct_content.text = "Python is a high-level programming language known for its simplicity."
            direct_response.content = [direct_content]
            
            mock_client.messages.create.return_value = direct_response
            
            generator = AIGenerator("test-api-key", "claude-sonnet-4")
            
            # Test without tools
            result = generator.generate_response("What is Python?")
            
            assert result == "Python is a high-level programming language known for its simplicity."
            assert mock_client.messages.create.call_count == 1
    
    def test_conversation_history_preservation(self):
        """Test that conversation history is preserved across sequential rounds"""
        with patch('ai_generator.anthropic.Anthropic') as mock_anthropic_class:
            mock_client = Mock()
            mock_anthropic_class.return_value = mock_client
            
            # Simple response for this test
            response = Mock()
            response.stop_reason = "end_turn"
            content = Mock()
            content.text = "Response with history context"
            response.content = [content]
            
            mock_client.messages.create.return_value = response
            
            generator = AIGenerator("test-api-key", "claude-sonnet-4")
            
            history = "User: What is Python?\nAssistant: Python is a programming language."
            
            result = generator.generate_response(
                "Tell me more about it",
                conversation_history=history
            )
            
            # Check that history was included in system prompt
            call_args = mock_client.messages.create.call_args[1]
            assert "Previous conversation:" in call_args["system"]
            assert "What is Python?" in call_args["system"]


class TestSequentialToolProcessor:
    """Test the SequentialToolProcessor class directly"""
    
    def test_loop_detection_basic(self):
        """Test basic loop detection functionality"""
        processor = SequentialToolProcessor(max_rounds=2)
        
        # First call - no loop
        assert not processor.detect_loop("search_course_content", {"query": "python"})
        processor.add_tool_call_record("search_course_content", {"query": "python"})
        
        # Different call - no loop
        assert not processor.detect_loop("search_course_content", {"query": "javascript"})
        processor.add_tool_call_record("search_course_content", {"query": "javascript"})
        
        # Same call as first - should detect loop
        assert processor.detect_loop("search_course_content", {"query": "python"})
    
    def test_parameter_similarity_calculation(self):
        """Test parameter similarity calculation"""
        processor = SequentialToolProcessor()
        
        # Identical parameters
        params1 = {"query": "python programming"}
        params2 = {"query": "python programming"}
        assert processor._calculate_parameter_similarity(params1, params2) == 1.0
        
        # Similar but different parameters (should have some word overlap)
        params3 = {"query": "python basics"}
        params4 = {"query": "python programming"}
        similarity = processor._calculate_parameter_similarity(params3, params4)
        assert similarity > 0  # At least some similarity due to "python"
        
        # Completely different parameters
        params5 = {"query": "javascript"}
        params6 = {"query": "python"}
        similarity = processor._calculate_parameter_similarity(params5, params6)
        assert similarity < 0.5
    
    def test_gathered_info_tracking(self):
        """Test that gathered info is tracked correctly"""
        processor = SequentialToolProcessor()
        
        # Simulate course outline results
        outline_results = [{"content": "Course outline for Python Programming with 5 lessons"}]
        processor.update_gathered_info(outline_results)
        assert "course_outline" in processor.gathered_info_summary
        
        # Simulate search results
        search_results = [{"content": "Lesson 2 content about variables in Python programming"}]
        processor.update_gathered_info(search_results)
        assert "lesson_content" in processor.gathered_info_summary
    
    def test_round_management(self):
        """Test round counting and type determination"""
        processor = SequentialToolProcessor(max_rounds=2)
        
        # Initial state
        assert processor.current_round == 0
        assert processor.should_continue_rounds()
        assert processor.get_round_type() == ConversationRound.FIRST_ROUND
        
        # After first round
        processor.current_round = 1
        assert processor.should_continue_rounds()
        assert processor.get_round_type() == ConversationRound.FOLLOW_UP_ROUND
        
        # After max rounds
        processor.current_round = 2
        assert not processor.should_continue_rounds()
        assert processor.get_round_type() == ConversationRound.FINAL_ROUND