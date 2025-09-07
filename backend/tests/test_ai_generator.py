import pytest
from unittest.mock import Mock, patch, MagicMock
from ai_generator import AIGenerator
import anthropic


class TestAIGenerator:
    """Test AIGenerator functionality"""
    
    def test_init(self):
        """Test AIGenerator initialization"""
        generator = AIGenerator("test-api-key", "claude-sonnet-4")
        
        assert generator.model == "claude-sonnet-4"
        assert generator.base_params["model"] == "claude-sonnet-4"
        assert generator.base_params["temperature"] == 0
        assert generator.base_params["max_tokens"] == 1000  # Updated for sequential calling
        assert generator.max_tool_rounds == 2
        assert generator.sequential_processor is not None
    
    @patch('ai_generator.anthropic.Anthropic')
    def test_generate_response_without_tools(self, mock_anthropic_class):
        """Test basic response generation without tools"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        # Mock response
        mock_response = Mock()
        mock_response.stop_reason = "end_turn"
        mock_content = Mock()
        mock_content.text = "This is a response about Python programming."
        mock_response.content = [mock_content]
        mock_client.messages.create.return_value = mock_response
        
        generator = AIGenerator("test-api-key", "claude-sonnet-4")
        result = generator.generate_response("What is Python?")
        
        assert result == "This is a response about Python programming."
        
        # Verify API call
        mock_client.messages.create.assert_called_once()
        call_args = mock_client.messages.create.call_args[1]
        
        assert call_args["model"] == "claude-sonnet-4"
        assert call_args["temperature"] == 0
        assert call_args["max_tokens"] == 1000
        assert len(call_args["messages"]) == 1
        assert call_args["messages"][0]["role"] == "user"
        assert call_args["messages"][0]["content"] == "What is Python?"
        assert AIGenerator.BASE_SYSTEM_PROMPT in call_args["system"]
    
    @patch('ai_generator.anthropic.Anthropic')
    def test_generate_response_with_conversation_history(self, mock_anthropic_class):
        """Test response generation with conversation history"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        mock_response = Mock()
        mock_response.stop_reason = "end_turn"
        mock_content = Mock()
        mock_content.text = "Based on our previous conversation..."
        mock_response.content = [mock_content]
        mock_client.messages.create.return_value = mock_response
        
        generator = AIGenerator("test-api-key", "claude-sonnet-4")
        history = "Previous conversation context"
        
        result = generator.generate_response("Follow up question", conversation_history=history)
        
        assert result == "Based on our previous conversation..."
        
        # Check that history was included in system message
        call_args = mock_client.messages.create.call_args[1]
        assert "Previous conversation context" in call_args["system"]
    
    @patch('ai_generator.anthropic.Anthropic')
    def test_generate_response_with_tools_no_tool_use(self, mock_anthropic_class):
        """Test response generation with tools available but not used"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        mock_response = Mock()
        mock_response.stop_reason = "end_turn"  # No tool use
        mock_content = Mock()
        mock_content.text = "Direct answer without using tools."
        mock_response.content = [mock_content]
        mock_client.messages.create.return_value = mock_response
        
        generator = AIGenerator("test-api-key", "claude-sonnet-4")
        
        tools = [{
            "name": "search_course_content",
            "description": "Search course materials",
            "input_schema": {"type": "object"}
        }]
        
        result = generator.generate_response("General question", tools=tools)
        
        assert result == "Direct answer without using tools."
        
        # Verify tools were passed to API
        call_args = mock_client.messages.create.call_args[1]
        assert "tools" in call_args
        assert call_args["tools"] == tools
        assert call_args["tool_choice"] == {"type": "auto"}
    
    @patch('ai_generator.anthropic.Anthropic')
    def test_generate_response_with_tool_execution(self, mock_anthropic_class):
        """Test response generation with tool execution"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        # First response with tool use
        mock_response1 = Mock()
        mock_response1.stop_reason = "tool_use"
        
        mock_tool_use = Mock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.name = "search_course_content"
        mock_tool_use.input = {"query": "python basics"}
        mock_tool_use.id = "tool_123"
        
        mock_response1.content = [mock_tool_use]
        
        # Second response after tool execution
        mock_response2 = Mock()
        mock_response2.stop_reason = "end_turn"
        mock_content2 = Mock()
        mock_content2.text = "Based on the search results, Python is..."
        mock_response2.content = [mock_content2]
        
        mock_client.messages.create.side_effect = [mock_response1, mock_response2]
        
        # Mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Python is a programming language"
        
        generator = AIGenerator("test-api-key", "claude-sonnet-4")
        
        tools = [{"name": "search_course_content", "description": "Search course materials"}]
        
        result = generator.generate_response(
            "What is Python?", 
            tools=tools, 
            tool_manager=mock_tool_manager
        )
        
        assert result == "Based on the search results, Python is..."
        
        # Verify tool was executed
        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content",
            query="python basics"
        )
        
        # Verify two API calls were made
        assert mock_client.messages.create.call_count == 2
    
    @patch('ai_generator.anthropic.Anthropic')
    def test_handle_tool_execution_multiple_tools(self, mock_anthropic_class):
        """Test handling multiple tool executions in one response"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        # Mock initial response with multiple tool uses
        mock_response1 = Mock()
        mock_response1.stop_reason = "tool_use"
        
        mock_tool_use1 = Mock()
        mock_tool_use1.type = "tool_use"
        mock_tool_use1.name = "search_course_content"
        mock_tool_use1.input = {"query": "python"}
        mock_tool_use1.id = "tool_123"
        
        mock_tool_use2 = Mock()
        mock_tool_use2.type = "tool_use"
        mock_tool_use2.name = "get_course_outline"
        mock_tool_use2.input = {"course_name": "Python Course"}
        mock_tool_use2.id = "tool_456"
        
        mock_response1.content = [mock_tool_use1, mock_tool_use2]
        
        # Mock final response
        mock_response2 = Mock()
        mock_response2.stop_reason = "end_turn"
        mock_content2 = Mock()
        mock_content2.text = "Combined results from both tools"
        mock_response2.content = [mock_content2]
        
        mock_client.messages.create.side_effect = [mock_response1, mock_response2]
        
        # Mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = [
            "Search result about Python",
            "Course outline result"
        ]
        
        generator = AIGenerator("test-api-key", "claude-sonnet-4")
        
        result = generator.generate_response(
            "Tell me about Python courses",
            tools=[{"name": "search_course_content"}, {"name": "get_course_outline"}],
            tool_manager=mock_tool_manager
        )
        
        assert result == "Combined results from both tools"
        
        # Verify both tools were executed
        assert mock_tool_manager.execute_tool.call_count == 2
        mock_tool_manager.execute_tool.assert_any_call("search_course_content", query="python")
        mock_tool_manager.execute_tool.assert_any_call("get_course_outline", course_name="Python Course")
    
    @patch('ai_generator.anthropic.Anthropic')
    def test_api_error_handling(self, mock_anthropic_class):
        """Test handling of Anthropic API errors"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        # Mock API error
        mock_client.messages.create.side_effect = anthropic.APIError("API rate limit exceeded", 
                                                                     response=Mock(status_code=429), 
                                                                     body=None)
        
        generator = AIGenerator("test-api-key", "claude-sonnet-4")
        
        # Should raise the original exception
        with pytest.raises(anthropic.APIError):
            generator.generate_response("Test question")
    
    @patch('ai_generator.anthropic.Anthropic')
    def test_tool_execution_error_handling(self, mock_anthropic_class):
        """Test handling of tool execution errors"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        # First response with tool use
        mock_response1 = Mock()
        mock_response1.stop_reason = "tool_use"
        
        mock_tool_use = Mock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.name = "search_course_content"
        mock_tool_use.input = {"query": "test"}
        mock_tool_use.id = "tool_123"
        
        mock_response1.content = [mock_tool_use]
        
        # Second response after tool execution
        mock_response2 = Mock()
        mock_response2.stop_reason = "end_turn"
        mock_content2 = Mock()
        mock_content2.text = "I couldn't find information about that."
        mock_response2.content = [mock_content2]
        
        mock_client.messages.create.side_effect = [mock_response1, mock_response2]
        
        # Mock tool manager that returns error
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Error: Tool execution failed"
        
        generator = AIGenerator("test-api-key", "claude-sonnet-4")
        
        result = generator.generate_response(
            "Search for something",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager
        )
        
        # Should still return a response, even if tool failed
        assert result == "I couldn't find information about that."
        
        # Verify second API call included the error result
        second_call_args = mock_client.messages.create.call_args_list[1][1]
        messages = second_call_args["messages"]
        
        # Should have: original user message, assistant tool use, user tool results
        assert len(messages) == 3
        assert messages[2]["role"] == "user"
        assert "Error: Tool execution failed" in str(messages[2]["content"])
    
    @patch('ai_generator.anthropic.Anthropic')
    def test_tool_execution_without_tool_manager(self, mock_anthropic_class):
        """Test tool execution when no tool manager is provided"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        # Response with tool use
        mock_response = Mock()
        mock_response.stop_reason = "tool_use"
        
        mock_tool_use = Mock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.name = "search_course_content"
        mock_tool_use.input = {"query": "test"}
        mock_tool_use.id = "tool_123"
        
        mock_response.content = [mock_tool_use]
        mock_client.messages.create.return_value = mock_response
        
        generator = AIGenerator("test-api-key", "claude-sonnet-4")
        
        # Should return the tool use response directly since no tool manager
        result = generator.generate_response(
            "Search for something",
            tools=[{"name": "search_course_content"}]
            # No tool_manager provided
        )
        
        # Should return the tool use content since it can't be executed
        assert mock_tool_use in result or result is mock_response.content[0]
    
    def test_system_prompt_content(self):
        """Test that system prompt contains expected guidelines"""
        system_prompt = AIGenerator.SYSTEM_PROMPT
        
        # Check for key instruction elements
        assert "Tool Usage Guidelines" in system_prompt
        assert "Content Search Tool" in system_prompt
        assert "Course Outline Tool" in system_prompt
        assert "Maximum one tool call per query" in system_prompt
        assert "No meta-commentary" in system_prompt
        assert "Brief, Concise and focused" in system_prompt
    
    @patch('ai_generator.anthropic.Anthropic')
    def test_message_structure_with_history(self, mock_anthropic_class):
        """Test proper message structure when conversation history is included"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        mock_response = Mock()
        mock_response.stop_reason = "end_turn"
        mock_content = Mock()
        mock_content.text = "Response with history"
        mock_response.content = [mock_content]
        mock_client.messages.create.return_value = mock_response
        
        generator = AIGenerator("test-api-key", "claude-sonnet-4")
        
        history = "User: Previous question\nAssistant: Previous answer"
        generator.generate_response("Current question", conversation_history=history)
        
        call_args = mock_client.messages.create.call_args[1]
        
        # Check system message includes both prompt and history
        system_content = call_args["system"]
        assert AIGenerator.SYSTEM_PROMPT in system_content
        assert "Previous conversation:" in system_content
        assert history in system_content
        
        # Check messages structure
        assert len(call_args["messages"]) == 1
        assert call_args["messages"][0]["role"] == "user"
        assert call_args["messages"][0]["content"] == "Current question"