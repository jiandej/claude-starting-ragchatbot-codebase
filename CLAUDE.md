# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Starting the Application
```bash
# Quick start (recommended)
./run.sh

# Manual start
cd backend && uv run uvicorn app:app --reload --port 8000
```

### Package Management
```bash
# Install/sync dependencies
uv sync

# Add new dependency
uv add package_name
```

## Architecture Overview

This is a full-stack RAG (Retrieval-Augmented Generation) system for course materials with the following structure:

### Core Components

- **RAGSystem** (`backend/rag_system.py`): Main orchestrator that coordinates all components
- **VectorStore** (`backend/vector_store.py`): ChromaDB integration for semantic search
- **DocumentProcessor** (`backend/document_processor.py`): Handles course document parsing and chunking
- **AIGenerator** (`backend/ai_generator.py`): Anthropic Claude API integration
- **SessionManager** (`backend/session_manager.py`): Conversation context management
- **ToolManager/CourseSearchTool** (`backend/search_tools.py`): Search functionality

### Data Models (`backend/models.py`)
- **Course**: Represents a complete course with lessons
- **Lesson**: Individual lesson within a course
- **CourseChunk**: Text chunks for vector storage

### API Structure (`backend/app.py`)
- FastAPI application serving both API endpoints and static frontend
- `/api/query`: Main query endpoint for RAG functionality
- `/api/courses`: Course statistics and analytics
- Serves frontend from `/frontend/` directory

### Frontend (`frontend/`)
- Simple HTML/CSS/JavaScript interface
- Communicates with backend via REST API

## Configuration

- Environment variables in `.env` file (use `.env.example` as template)
- Main config in `backend/config.py` using dataclasses
- Key settings: ANTHROPIC_API_KEY, chunk sizes, ChromaDB path

## Document Processing Flow

1. Documents placed in `docs/` directory are auto-loaded on startup
2. DocumentProcessor parses course structure and creates chunks
3. VectorStore stores both course metadata and content chunks in ChromaDB
4. RAGSystem coordinates retrieval and generation for queries

## Development Notes

- Uses `uv` for Python package management (faster than pip)
- ChromaDB for vector storage (persisted in `./backend/chroma_db/`)
- Anthropic Claude Sonnet-4 for AI generation
- FastAPI with hot reload for development
- CORS enabled for frontend-backend communication