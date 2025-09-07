# Proposed fixes for RAG system error handling

# Fix 1: Enhanced RAGSystem.query() with better error handling
def enhanced_query_method():
    """
    Replacement for RAGSystem.query() method with proper error handling
    """
    def query(self, query: str, session_id: Optional[str] = None) -> Tuple[str, List[str]]:
        """
        Process a user query using the RAG system with robust error handling.
        
        Args:
            query: User's question
            session_id: Optional session ID for conversation context
            
        Returns:
            Tuple of (response, sources list)
        """
        try:
            # Validate API key first
            if not self.config.ANTHROPIC_API_KEY or self.config.ANTHROPIC_API_KEY == "":
                return ("I'm sorry, but the system is not properly configured with an API key. Please contact your administrator.", [])
            
            # Create prompt for the AI with clear instructions
            prompt = f"""Answer this question about course materials: {query}"""
            
            # Get conversation history if session exists
            history = None
            if session_id:
                history = self.session_manager.get_conversation_history(session_id)
            
            # Generate response using AI with tools
            response = self.ai_generator.generate_response(
                query=prompt,
                conversation_history=history,
                tools=self.tool_manager.get_tool_definitions(),
                tool_manager=self.tool_manager
            )
            
            # Get sources from the search tool
            sources = self.tool_manager.get_last_sources()

            # Reset sources after retrieving them
            self.tool_manager.reset_sources()
            
            # Update conversation history
            if session_id:
                self.session_manager.add_exchange(session_id, query, response)
            
            return response, sources
            
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


# Fix 2: Configuration validation at startup
def validate_configuration():
    """
    Validate system configuration at startup
    """
    def __init__(self, config):
        # Validate configuration before initializing components
        validation_errors = []
        
        if not config.ANTHROPIC_API_KEY or config.ANTHROPIC_API_KEY.strip() == "":
            validation_errors.append("ANTHROPIC_API_KEY is not set or empty")
            
        if not config.CHROMA_PATH:
            validation_errors.append("CHROMA_PATH is not configured")
            
        if validation_errors:
            error_message = "Configuration validation failed:\n" + "\n".join(f"- {error}" for error in validation_errors)
            print(f"WARNING: {error_message}")
            print("The system may not function properly. Please check your .env file.")
        
        # Continue with initialization
        self.config = config
        # ... rest of initialization


# Fix 3: Enhanced FastAPI error handling
def enhanced_fastapi_endpoint():
    """
    Improved FastAPI endpoint with better error handling
    """
    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        """Process a query and return response with sources"""
        try:
            # Create session if not provided
            session_id = request.session_id
            if not session_id:
                session_id = rag_system.session_manager.create_session()
            
            # Process query using RAG system
            answer, sources = rag_system.query(request.query, session_id)
            
            # Check if this was an error response from RAG system
            if answer.startswith("I'm sorry") or answer.startswith("Authentication failed") or answer.startswith("The system is currently"):
                # This is an error response, return it with appropriate status
                # But still return 200 so frontend can display the message
                formatted_sources = []
            else:
                # Convert sources to SourceData objects if they're dictionaries
                formatted_sources = []
                for source in sources:
                    if isinstance(source, dict):
                        formatted_sources.append(SourceData(text=source['text'], link=source.get('link')))
                    else:
                        # Handle backward compatibility with string sources
                        formatted_sources.append(source)
            
            return QueryResponse(
                answer=answer,
                sources=formatted_sources,
                session_id=session_id
            )
            
        except Exception as e:
            # Log the full error for debugging
            import traceback
            print(f"Unhandled error in query endpoint: {e}")
            traceback.print_exc()
            
            # Return user-friendly error message
            raise HTTPException(
                status_code=500, 
                detail="An internal server error occurred while processing your request. Please try again later."
            )


# Fix 4: Health check endpoint
def add_health_check():
    """
    Add health check endpoint to verify system status
    """
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
        
        # Check document processor
        try:
            # Simple test of tool system
            tools = rag_system.tool_manager.get_tool_definitions()
            health_status["components"]["tools"] = f"operational ({len(tools)} tools)"
        except Exception as e:
            health_status["components"]["tools"] = f"error: {str(e)}"
            health_status["status"] = "unhealthy"
        
        return health_status