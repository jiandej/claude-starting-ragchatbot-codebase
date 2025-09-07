#!/usr/bin/env python3
"""
Demo script showing sequential tool calling capabilities
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from unittest.mock import Mock
from ai_generator import AIGenerator


def demo_sequential_tool_calling():
    """Demonstrate sequential tool calling with mock responses"""
    
    print("=== Sequential Tool Calling Demo ===\n")
    
    # Create mock tool manager
    mock_tool_manager = Mock()
    
    def mock_execute_tool(tool_name, **kwargs):
        query = kwargs.get('query', '')
        course_name = kwargs.get('course_name', '')
        
        if tool_name == "get_course_outline":
            if "MCP" in course_name or "mcp" in course_name.lower():
                return """**MCP: Build Rich-Context AI Apps with Anthropic**
Instructor: DeepLearning.AI

**Lessons (4 total):**
1. Introduction to MCP
2. Setting Up Your First MCP Server  
3. Creating Custom Tools and Resources
4. Building Production MCP Applications - [Link](https://learn.deeplearning.ai/courses/mcp/lesson/4)"""
            else:
                return "Course not found"
                
        elif tool_name == "search_course_content":
            if "MCP server" in query or "server creation" in query:
                return """[Introduction to Python Programming - Lesson 2]
Creating an MCP server involves setting up the server architecture, defining tools and resources, and implementing the communication protocol. MCP servers act as intermediaries between AI applications and external data sources or services."""
            elif "lesson 4" in query.lower():
                return """[MCP Course - Lesson 4]
Lesson 4 covers building production MCP applications with proper error handling, authentication, and scalability considerations. Topics include deployment strategies and monitoring."""
            else:
                return f"Search results for: {query}"
    
    mock_tool_manager.execute_tool = mock_execute_tool
    
    # Create AI generator with mock client
    generator = AIGenerator("demo-key", "claude-sonnet-4", max_tool_rounds=2)
    
    # Mock Anthropic client to simulate sequential behavior
    mock_client = Mock()
    generator.client = mock_client
    
    # Scenario: User asks to find courses similar to MCP lesson 4
    print("User Query: 'Find a course that discusses similar topics to lesson 4 of the MCP course'")
    print("\nExpected Sequential Flow:")
    print("1. Claude gets MCP course outline to understand lesson 4")
    print("2. Claude searches for courses with similar content to lesson 4 topic")
    print("3. Claude synthesizes findings\n")
    
    # Mock the sequential API responses
    def mock_api_calls(*args, **kwargs):
        # Track which call this is
        mock_api_calls.call_count += 1
        
        if mock_api_calls.call_count == 1:
            # First round: Claude wants course outline
            response = Mock()
            response.stop_reason = "tool_use"
            tool_use = Mock()
            tool_use.type = "tool_use"
            tool_use.name = "get_course_outline"
            tool_use.input = {"course_name": "MCP"}
            tool_use.id = "outline_call"
            response.content = [tool_use]
            print(f"Round 1: Claude requests course outline for MCP")
            return response
            
        elif mock_api_calls.call_count == 2:
            # Second round: Claude wants to search based on lesson 4
            response = Mock()
            response.stop_reason = "tool_use"
            tool_use = Mock()
            tool_use.type = "tool_use"
            tool_use.name = "search_course_content"
            tool_use.input = {"query": "MCP server creation production applications"}
            tool_use.id = "search_call"
            response.content = [tool_use]
            print(f"Round 2: Claude searches for similar content: 'MCP server creation production applications'")
            return response
            
        else:
            # Final synthesis
            response = Mock()
            response.stop_reason = "end_turn"
            content = Mock()
            content.text = """Based on my search, I found that lesson 4 of the MCP course covers "Building Production MCP Applications" which focuses on server architecture, deployment, and scalability.

The "Introduction to Python Programming" course has a similar lesson (Lesson 2) that discusses creating server applications and communication protocols, which aligns with the MCP server creation concepts taught in MCP lesson 4.

Both lessons cover:
- Server architecture design
- Production deployment considerations  
- Error handling and authentication
- Scalability planning

The Python Programming course would be a good complement to the MCP course for understanding the underlying server development principles."""
            response.content = [content]
            print(f"Final synthesis: Claude provides comprehensive answer")
            return response
    
    mock_api_calls.call_count = 0
    mock_client.messages.create = mock_api_calls
    
    # Tools available
    tools = [
        {
            "name": "get_course_outline",
            "description": "Get course outline with lesson details"
        },
        {
            "name": "search_course_content", 
            "description": "Search course materials"
        }
    ]
    
    # Execute the query with sequential tool calling
    try:
        result = generator.generate_response(
            "Find a course that discusses similar topics to lesson 4 of the MCP course",
            tools=tools,
            tool_manager=mock_tool_manager
        )
        
        print(f"\n=== Final Response ===")
        print(result)
        
        print(f"\n=== Summary ===")
        print(f"✓ Total API calls made: {mock_api_calls.call_count}")
        print(f"✓ Tool executions: 2 (outline + search)")
        print(f"✓ Sequential reasoning: Claude used lesson 4 info to guide search")
        print(f"✓ Comprehensive synthesis: Combined multiple sources of information")
        
    except Exception as e:
        print(f"Error during demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    demo_sequential_tool_calling()