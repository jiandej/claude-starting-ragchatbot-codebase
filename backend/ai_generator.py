import anthropic
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import time


class ConversationRound(Enum):
    """Enumeration of conversation round types"""
    FIRST_ROUND = "first_round"
    FOLLOW_UP_ROUND = "follow_up_round"
    FINAL_ROUND = "final_round"


@dataclass
class ToolCallRecord:
    """Record of a tool call for loop detection"""
    tool_name: str
    parameters: Dict[str, Any]
    timestamp: float
    round_num: int


class SequentialToolProcessor:
    """Handles sequential tool calling with state management and loop detection"""
    
    def __init__(self, max_rounds: int = 2, loop_similarity_threshold: float = 0.8):
        self.max_rounds = max_rounds
        self.loop_similarity_threshold = loop_similarity_threshold
        self.tool_call_history: List[ToolCallRecord] = []
        self.conversation_messages: List[Dict[str, Any]] = []
        self.current_round = 0
        self.gathered_info_summary = ""
        
    def reset_state(self):
        """Reset processor state for new conversation"""
        self.tool_call_history.clear()
        self.conversation_messages.clear()
        self.current_round = 0
        self.gathered_info_summary = ""
    
    def add_tool_call_record(self, tool_name: str, parameters: Dict[str, Any]):
        """Record a tool call for loop detection"""
        record = ToolCallRecord(
            tool_name=tool_name,
            parameters=parameters,
            timestamp=time.time(),
            round_num=self.current_round
        )
        self.tool_call_history.append(record)
    
    def detect_loop(self, tool_name: str, parameters: Dict[str, Any]) -> bool:
        """Detect if this tool call would create a loop"""
        if len(self.tool_call_history) < 2:
            return False
            
        # Check recent history for similar calls
        recent_calls = [record for record in self.tool_call_history[-3:]]
        
        for record in recent_calls:
            if (record.tool_name == tool_name and 
                self._calculate_parameter_similarity(record.parameters, parameters) > self.loop_similarity_threshold):
                return True
        
        return False
    
    def _calculate_parameter_similarity(self, params1: Dict[str, Any], params2: Dict[str, Any]) -> float:
        """Calculate similarity between two parameter sets"""
        if not params1 and not params2:
            return 1.0
        if not params1 or not params2:
            return 0.0
            
        # Simple similarity: check if key parameters match
        common_keys = set(params1.keys()) & set(params2.keys())
        if not common_keys:
            return 0.0
            
        total_similarity = 0.0
        for key in common_keys:
            if params1[key] == params2[key]:
                total_similarity += 1.0
            elif isinstance(params1[key], str) and isinstance(params2[key], str):
                # Check string similarity for query parameters
                string_sim = self._string_similarity(params1[key], params2[key])
                total_similarity += string_sim
        
        return total_similarity / len(common_keys)
    
    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calculate simple string similarity"""
        s1_words = set(s1.lower().split())
        s2_words = set(s2.lower().split())
        if not s1_words and not s2_words:
            return 1.0
        if not s1_words or not s2_words:
            return 0.0
        return len(s1_words & s2_words) / len(s1_words | s2_words)
    
    def should_continue_rounds(self) -> bool:
        """Determine if we should continue with more tool rounds"""
        return self.current_round < self.max_rounds
    
    def get_round_type(self) -> ConversationRound:
        """Determine the type of the current round"""
        if self.current_round == 0:
            return ConversationRound.FIRST_ROUND
        elif self.current_round < self.max_rounds:
            return ConversationRound.FOLLOW_UP_ROUND
        else:
            return ConversationRound.FINAL_ROUND
    
    def update_gathered_info(self, tool_results: List[Dict[str, Any]]):
        """Update summary of gathered information"""
        # Simple heuristic: track what types of information we've gathered
        info_types = []
        for result in tool_results:
            content = result.get("content", "")
            if "course" in content.lower() and "outline" in content.lower():
                info_types.append("course_outline")
            elif "lesson" in content.lower():
                info_types.append("lesson_content")
            elif "search" in content.lower() or len(content) > 200:
                info_types.append("search_results")
        
        self.gathered_info_summary = ", ".join(set(info_types))


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Base system prompt components for dynamic generation
    BASE_SYSTEM_PROMPT = """You are an AI assistant specialized in course materials and educational content with access to comprehensive search and outline tools for course information.

Tool Usage Guidelines:
- **Content Search Tool**: Use for questions about specific course content, lessons, or detailed educational materials
- **Course Outline Tool**: Use for questions about course structure, outlines, lesson lists, or course overviews
- **Sequential Tool Strategy**: You can make tool calls across multiple rounds of reasoning
- Synthesize tool results into accurate, fact-based responses
- If tools yield no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course content questions**: Use content search tool first, then answer
- **Course outline/structure questions**: Use outline tool first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, tool explanations, or question-type analysis
 - Do not mention "based on the search results" or "using the outline tool"

For Course Outline Responses:
- Always include the course title, course link (if available), and complete lesson list
- Show lesson numbers and titles clearly
- Include lesson links when available
- Present information in a well-structured, readable format

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
"""

    FIRST_ROUND_PROMPT_ADDITION = """
**Current Round**: First exploration round (you have {remaining_rounds} more rounds available)

Strategy for this round:
- Start with broad searches to understand what information is available
- Consider getting course outlines first if you need to understand course structure
- Focus on gathering foundational information that will inform follow-up searches
- You can make additional tool calls in subsequent rounds to refine or expand your search
"""

    FOLLOW_UP_PROMPT_ADDITION = """
**Current Round**: Follow-up round (you have {remaining_rounds} more rounds available)

Previous information gathered: {gathered_info}

Strategy for this round:
- Build on information from previous searches
- Make targeted searches based on what you learned
- Look for specific details, comparisons, or related content
- Consider cross-referencing between different courses or lessons
"""

    FINAL_ROUND_PROMPT_ADDITION = """
**Final Round**: This is your last opportunity to gather information

Previous information gathered: {gathered_info}

Strategy for this round:
- Make any final targeted searches needed
- Focus on filling gaps in your knowledge
- Prepare to synthesize all gathered information into a comprehensive response
- No more tool calls will be available after this round
"""

    NO_MORE_ROUNDS_PROMPT_ADDITION = """
**Synthesis Phase**: No more tool calls available

Information gathered: {gathered_info}

- Synthesize all previously gathered information into a comprehensive answer
- Use only the information from previous tool results
- Provide a complete, well-structured response to the original question
"""
    
    def __init__(self, api_key: str, model: str, max_tool_rounds: int = 2):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tool_rounds = max_tool_rounds
        self.sequential_processor = SequentialToolProcessor(max_rounds=max_tool_rounds)
        
        # Pre-build base API parameters - increased max_tokens for multi-round reasoning
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 1000
        }
    
    def _build_dynamic_system_prompt(self, conversation_history: Optional[str], 
                                   round_type: ConversationRound, 
                                   remaining_rounds: int,
                                   gathered_info: str = "") -> str:
        """Build dynamic system prompt based on conversation round and context"""
        prompt = self.BASE_SYSTEM_PROMPT
        
        # Add round-specific strategy guidance
        if round_type == ConversationRound.FIRST_ROUND:
            prompt += self.FIRST_ROUND_PROMPT_ADDITION.format(remaining_rounds=remaining_rounds)
        elif round_type == ConversationRound.FOLLOW_UP_ROUND:
            prompt += self.FOLLOW_UP_PROMPT_ADDITION.format(
                remaining_rounds=remaining_rounds,
                gathered_info=gathered_info or "Various search results"
            )
        elif round_type == ConversationRound.FINAL_ROUND:
            prompt += self.FINAL_ROUND_PROMPT_ADDITION.format(
                gathered_info=gathered_info or "Previous search results"
            )
        else:  # No more rounds - synthesis only
            prompt += self.NO_MORE_ROUNDS_PROMPT_ADDITION.format(
                gathered_info=gathered_info or "All previous search results"
            )
        
        # Add conversation history
        if conversation_history:
            prompt += f"\n\nPrevious conversation:\n{conversation_history}"
        
        return prompt
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with sequential tool usage and conversation context.
        
        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            
        Returns:
            Generated response as string
        """
        # Reset processor state for new conversation
        self.sequential_processor.reset_state()
        
        # If no tools available, use simple response generation
        if not tools or not tool_manager:
            return self._generate_simple_response(query, conversation_history)
        
        # Handle sequential tool calling
        return self._handle_sequential_tool_rounds(query, conversation_history, tools, tool_manager)
    
    def _generate_simple_response(self, query: str, conversation_history: Optional[str] = None) -> str:
        """Generate simple response without tools"""
        system_content = self._build_dynamic_system_prompt(
            conversation_history, 
            ConversationRound.FIRST_ROUND, 
            0, 
            ""
        )
        
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content
        }
        
        response = self.client.messages.create(**api_params)
        return response.content[0].text
    
    def _handle_sequential_tool_rounds(self, query: str, conversation_history: Optional[str],
                                     tools: List, tool_manager) -> str:
        """Handle sequential rounds of tool calling"""
        # Initialize conversation with user's query
        messages = [{"role": "user", "content": query}]
        
        while self.sequential_processor.should_continue_rounds():
            self.sequential_processor.current_round += 1
            round_type = self.sequential_processor.get_round_type()
            remaining_rounds = self.max_tool_rounds - self.sequential_processor.current_round
            
            # Build dynamic system prompt for this round
            system_content = self._build_dynamic_system_prompt(
                conversation_history,
                round_type,
                remaining_rounds,
                self.sequential_processor.gathered_info_summary
            )
            
            # Prepare API call with tools
            api_params = {
                **self.base_params,
                "messages": messages,
                "system": system_content,
                "tools": tools,
                "tool_choice": {"type": "auto"}
            }
            
            try:
                # Get Claude's response
                response = self.client.messages.create(**api_params)
                
                # Add Claude's response to conversation
                messages.append({"role": "assistant", "content": response.content})
                
                # Check if Claude wants to use tools
                if response.stop_reason == "tool_use":
                    tool_results = self._execute_tools_with_loop_detection(response, tool_manager)
                    
                    if tool_results:
                        # Add tool results to conversation
                        messages.append({"role": "user", "content": tool_results})
                        
                        # Update gathered info summary
                        self.sequential_processor.update_gathered_info(tool_results)
                    else:
                        # No valid tool results (likely due to loop detection)
                        break
                else:
                    # Claude provided a text response - we're done
                    return response.content[0].text
                    
            except Exception as e:
                # Handle API errors gracefully
                error_msg = f"I encountered an error while processing your request: {str(e)}"
                return error_msg
        
        # Max rounds reached - make final synthesis call without tools
        return self._make_final_synthesis_call(messages, conversation_history)
    
    def _execute_tools_with_loop_detection(self, response, tool_manager) -> Optional[List[Dict[str, Any]]]:
        """Execute tools with loop detection and error handling"""
        tool_results = []
        
        for content_block in response.content:
            if content_block.type == "tool_use":
                # Check for loops before executing
                if self.sequential_processor.detect_loop(content_block.name, content_block.input):
                    # Add loop detection message and stop tool calling
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": "Loop detected: Similar search already performed. Please synthesize available information."
                    })
                    return tool_results
                
                # Record this tool call
                self.sequential_processor.add_tool_call_record(content_block.name, content_block.input)
                
                try:
                    # Execute the tool
                    tool_result = tool_manager.execute_tool(
                        content_block.name, 
                        **content_block.input
                    )
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": tool_result
                    })
                    
                except Exception as e:
                    # Handle tool execution errors gracefully
                    error_msg = f"Tool execution error: {str(e)}. Please work with available information."
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": error_msg
                    })
        
        return tool_results if tool_results else None
    
    def _make_final_synthesis_call(self, messages: List[Dict[str, Any]], 
                                 conversation_history: Optional[str]) -> str:
        """Make final API call to synthesize all gathered information"""
        # Build synthesis prompt
        system_content = self._build_dynamic_system_prompt(
            conversation_history,
            ConversationRound.FINAL_ROUND,  # This will trigger NO_MORE_ROUNDS_PROMPT_ADDITION
            0,
            self.sequential_processor.gathered_info_summary
        )
        
        # Final call without tools
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": system_content
            # No tools parameter - force synthesis
        }
        
        try:
            final_response = self.client.messages.create(**final_params)
            return final_response.content[0].text
        except Exception as e:
            return f"I gathered information but encountered an error during synthesis: {str(e)}"
    
    # Keep the old method for backward compatibility (not used in new flow)
    def _handle_tool_execution(self, initial_response, base_params: Dict[str, Any], tool_manager):
        """
        Handle execution of tool calls and get follow-up response.
        
        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters
            tool_manager: Manager to execute tools
            
        Returns:
            Final response text after tool execution
        """
        # Start with existing messages
        messages = base_params["messages"].copy()
        
        # Add AI's tool use response
        messages.append({"role": "assistant", "content": initial_response.content})
        
        # Execute all tool calls and collect results
        tool_results = []
        for content_block in initial_response.content:
            if content_block.type == "tool_use":
                tool_result = tool_manager.execute_tool(
                    content_block.name, 
                    **content_block.input
                )
                
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": content_block.id,
                    "content": tool_result
                })
        
        # Add tool results as single message
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        
        # Prepare final API call without tools
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": base_params["system"]
        }
        
        # Get final response
        final_response = self.client.messages.create(**final_params)
        return final_response.content[0].text