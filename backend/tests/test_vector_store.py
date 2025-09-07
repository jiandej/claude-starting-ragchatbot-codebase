import json
import os
import tempfile
from unittest.mock import MagicMock, Mock, patch

import pytest
from models import Course, CourseChunk, Lesson
from vector_store import SearchResults, VectorStore


class TestVectorStore:
    """Test VectorStore functionality with ChromaDB"""

    @pytest.fixture
    def temp_vector_store(self, temp_chroma_db):
        """Create VectorStore with temporary database"""
        return VectorStore(
            chroma_path=temp_chroma_db,
            embedding_model="all-MiniLM-L6-v2",
            max_results=5,
        )

    @patch("vector_store.chromadb")
    def test_vector_store_initialization(self, mock_chromadb, temp_chroma_db):
        """Test VectorStore initialization"""
        mock_client = Mock()
        mock_collection = Mock()
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2", max_results=3)

        assert store.max_results == 3
        mock_chromadb.PersistentClient.assert_called_once_with(
            path=temp_chroma_db,
            settings=mock_chromadb.config.Settings(anonymized_telemetry=False),
        )

        # Should create both collections
        assert mock_client.get_or_create_collection.call_count == 2

    def test_search_results_from_chroma(self):
        """Test SearchResults creation from ChromaDB response"""
        chroma_results = {
            "documents": [["Doc 1", "Doc 2"]],
            "metadatas": [[{"title": "Course 1"}, {"title": "Course 2"}]],
            "distances": [[0.1, 0.2]],
        }

        results = SearchResults.from_chroma(chroma_results)

        assert results.documents == ["Doc 1", "Doc 2"]
        assert results.metadata == [{"title": "Course 1"}, {"title": "Course 2"}]
        assert results.distances == [0.1, 0.2]
        assert results.error is None

    def test_search_results_empty(self):
        """Test empty SearchResults creation"""
        results = SearchResults.empty("No results found")

        assert results.documents == []
        assert results.metadata == []
        assert results.distances == []
        assert results.error == "No results found"
        assert results.is_empty() is True

    def test_search_results_is_empty(self):
        """Test is_empty method"""
        empty_results = SearchResults([], [], [])
        assert empty_results.is_empty() is True

        non_empty_results = SearchResults(["doc"], [{}], [0.1])
        assert non_empty_results.is_empty() is False

    @patch("vector_store.chromadb")
    def test_add_course_metadata(self, mock_chromadb, sample_course, temp_chroma_db):
        """Test adding course metadata to vector store"""
        mock_client = Mock()
        mock_collection = Mock()
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2")
        store.add_course_metadata(sample_course)

        # Verify collection.add was called
        mock_collection.add.assert_called_once()

        call_args = mock_collection.add.call_args
        assert call_args[1]["documents"] == [sample_course.title]
        assert call_args[1]["ids"] == [sample_course.title]

        metadata = call_args[1]["metadatas"][0]
        assert metadata["title"] == sample_course.title
        assert metadata["instructor"] == sample_course.instructor
        assert metadata["course_link"] == sample_course.course_link
        assert "lessons_json" in metadata
        assert metadata["lesson_count"] == len(sample_course.lessons)

        # Verify lessons are serialized correctly
        lessons_data = json.loads(metadata["lessons_json"])
        assert len(lessons_data) == len(sample_course.lessons)
        assert lessons_data[0]["lesson_number"] == 1
        assert lessons_data[0]["lesson_title"] == "Introduction to Python"

    @patch("vector_store.chromadb")
    def test_add_course_content(
        self, mock_chromadb, sample_course_chunks, temp_chroma_db
    ):
        """Test adding course content chunks to vector store"""
        mock_client = Mock()
        mock_collection = Mock()
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2")
        store.add_course_content(sample_course_chunks)

        mock_collection.add.assert_called_once()

        call_args = mock_collection.add.call_args

        # Verify documents
        expected_documents = [chunk.content for chunk in sample_course_chunks]
        assert call_args[1]["documents"] == expected_documents

        # Verify metadata
        expected_metadata = [
            {
                "course_title": chunk.course_title,
                "lesson_number": chunk.lesson_number,
                "chunk_index": chunk.chunk_index,
            }
            for chunk in sample_course_chunks
        ]
        assert call_args[1]["metadatas"] == expected_metadata

        # Verify IDs format
        expected_ids = [
            f"{chunk.course_title.replace(' ', '_')}_{chunk.chunk_index}"
            for chunk in sample_course_chunks
        ]
        assert call_args[1]["ids"] == expected_ids

    def test_add_course_content_empty_chunks(self, temp_vector_store):
        """Test adding empty chunk list does nothing"""
        # This should not raise an error
        temp_vector_store.add_course_content([])

    @patch("vector_store.chromadb")
    def test_search_without_filters(self, mock_chromadb, temp_chroma_db):
        """Test search without course or lesson filters"""
        mock_client = Mock()
        mock_collection = Mock()
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        # Mock search results
        mock_collection.query.return_value = {
            "documents": [["Python is a programming language"]],
            "metadatas": [[{"course_title": "Python Course", "lesson_number": 1}]],
            "distances": [[0.1]],
        }

        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2", max_results=3)
        results = store.search("python programming")

        assert not results.is_empty()
        assert results.documents == ["Python is a programming language"]
        assert results.metadata[0]["course_title"] == "Python Course"

        # Verify query parameters
        mock_collection.query.assert_called_once_with(
            query_texts=["python programming"], n_results=3, where=None
        )

    @patch("vector_store.chromadb")
    def test_search_with_course_filter(self, mock_chromadb, temp_chroma_db):
        """Test search with course name filter"""
        mock_client = Mock()
        mock_collections = {}

        def get_collection_side_effect(name, embedding_function):
            if name not in mock_collections:
                mock_collections[name] = Mock()
            return mock_collections[name]

        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.side_effect = get_collection_side_effect

        # Mock course resolution
        mock_collections["course_catalog"].query.return_value = {
            "documents": [["Python Fundamentals"]],
            "metadatas": [[{"title": "Python Programming Fundamentals"}]],
        }

        # Mock content search
        mock_collections["course_content"].query.return_value = {
            "documents": [["Variables in Python"]],
            "metadatas": [
                [
                    {
                        "course_title": "Python Programming Fundamentals",
                        "lesson_number": 2,
                    }
                ]
            ],
            "distances": [[0.15]],
        }

        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2")
        results = store.search("variables", course_name="Python")

        assert not results.is_empty()
        assert results.documents == ["Variables in Python"]

        # Verify course resolution was called
        mock_collections["course_catalog"].query.assert_called_once_with(
            query_texts=["Python"], n_results=1
        )

        # Verify content search with filter
        mock_collections["course_content"].query.assert_called_once_with(
            query_texts=["variables"],
            n_results=5,
            where={"course_title": "Python Programming Fundamentals"},
        )

    @patch("vector_store.chromadb")
    def test_search_with_lesson_filter(self, mock_chromadb, temp_chroma_db):
        """Test search with lesson number filter"""
        mock_client = Mock()
        mock_collection = Mock()
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        mock_collection.query.return_value = {
            "documents": [["Control flow concepts"]],
            "metadatas": [[{"course_title": "Python Course", "lesson_number": 3}]],
            "distances": [[0.2]],
        }

        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2")
        results = store.search("control flow", lesson_number=3)

        assert not results.is_empty()

        # Verify search with lesson filter
        mock_collection.query.assert_called_with(
            query_texts=["control flow"], n_results=5, where={"lesson_number": 3}
        )

    @patch("vector_store.chromadb")
    def test_search_with_both_filters(self, mock_chromadb, temp_chroma_db):
        """Test search with both course and lesson filters"""
        mock_client = Mock()
        mock_collections = {}

        def get_collection_side_effect(name, embedding_function):
            if name not in mock_collections:
                mock_collections[name] = Mock()
            return mock_collections[name]

        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.side_effect = get_collection_side_effect

        # Mock course resolution
        mock_collections["course_catalog"].query.return_value = {
            "documents": [["Advanced Python"]],
            "metadatas": [[{"title": "Advanced Python Programming"}]],
        }

        # Mock content search
        mock_collections["course_content"].query.return_value = {
            "documents": [["Advanced loop concepts"]],
            "metadatas": [
                [{"course_title": "Advanced Python Programming", "lesson_number": 2}]
            ],
            "distances": [[0.1]],
        }

        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2")
        results = store.search("loops", course_name="Advanced", lesson_number=2)

        assert not results.is_empty()

        # Verify content search with combined filter
        expected_filter = {
            "$and": [
                {"course_title": "Advanced Python Programming"},
                {"lesson_number": 2},
            ]
        }
        mock_collections["course_content"].query.assert_called_with(
            query_texts=["loops"], n_results=5, where=expected_filter
        )

    @patch("vector_store.chromadb")
    def test_search_course_not_found(self, mock_chromadb, temp_chroma_db):
        """Test search when course name cannot be resolved"""
        mock_client = Mock()
        mock_collection = Mock()
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        # Mock empty course resolution
        mock_collection.query.return_value = {"documents": [[]], "metadatas": [[]]}

        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2")
        results = store.search("test", course_name="NonexistentCourse")

        assert results.error == "No course found matching 'NonexistentCourse'"
        assert results.is_empty()

    @patch("vector_store.chromadb")
    def test_search_chromadb_exception(self, mock_chromadb, temp_chroma_db):
        """Test search when ChromaDB raises exception"""
        mock_client = Mock()
        mock_collection = Mock()
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        # Mock ChromaDB exception
        mock_collection.query.side_effect = Exception("Database connection failed")

        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2")
        results = store.search("test query")

        assert results.error == "Search error: Database connection failed"
        assert results.is_empty()

    @patch("vector_store.chromadb")
    def test_resolve_course_name_success(self, mock_chromadb, temp_chroma_db):
        """Test successful course name resolution"""
        mock_client = Mock()
        mock_collection = Mock()
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        mock_collection.query.return_value = {
            "documents": [["Python Programming"]],
            "metadatas": [[{"title": "Python Programming Fundamentals"}]],
        }

        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2")
        result = store._resolve_course_name("Python")

        assert result == "Python Programming Fundamentals"

    @patch("vector_store.chromadb")
    def test_resolve_course_name_no_results(self, mock_chromadb, temp_chroma_db):
        """Test course name resolution with no results"""
        mock_client = Mock()
        mock_collection = Mock()
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        mock_collection.query.return_value = {"documents": [[]], "metadatas": [[]]}

        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2")
        result = store._resolve_course_name("NonexistentCourse")

        assert result is None

    @patch("vector_store.chromadb")
    def test_resolve_course_name_exception(self, mock_chromadb, temp_chroma_db):
        """Test course name resolution with exception"""
        mock_client = Mock()
        mock_collection = Mock()
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        mock_collection.query.side_effect = Exception("Network error")

        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2")
        result = store._resolve_course_name("TestCourse")

        assert result is None

    def test_build_filter_no_filters(self, temp_vector_store):
        """Test filter building with no parameters"""
        result = temp_vector_store._build_filter(None, None)
        assert result is None

    def test_build_filter_course_only(self, temp_vector_store):
        """Test filter building with course only"""
        result = temp_vector_store._build_filter("Test Course", None)
        assert result == {"course_title": "Test Course"}

    def test_build_filter_lesson_only(self, temp_vector_store):
        """Test filter building with lesson only"""
        result = temp_vector_store._build_filter(None, 2)
        assert result == {"lesson_number": 2}

    def test_build_filter_both(self, temp_vector_store):
        """Test filter building with both course and lesson"""
        result = temp_vector_store._build_filter("Test Course", 3)
        expected = {"$and": [{"course_title": "Test Course"}, {"lesson_number": 3}]}
        assert result == expected

    @patch("vector_store.chromadb")
    def test_get_existing_course_titles(self, mock_chromadb, temp_chroma_db):
        """Test getting existing course titles"""
        mock_client = Mock()
        mock_collection = Mock()
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        mock_collection.get.return_value = {"ids": ["Course 1", "Course 2", "Course 3"]}

        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2")
        titles = store.get_existing_course_titles()

        assert titles == ["Course 1", "Course 2", "Course 3"]

    @patch("vector_store.chromadb")
    def test_get_existing_course_titles_empty(self, mock_chromadb, temp_chroma_db):
        """Test getting course titles when database is empty"""
        mock_client = Mock()
        mock_collection = Mock()
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        mock_collection.get.return_value = {"ids": []}

        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2")
        titles = store.get_existing_course_titles()

        assert titles == []

    @patch("vector_store.chromadb")
    def test_get_course_count(self, mock_chromadb, temp_chroma_db):
        """Test getting course count"""
        mock_client = Mock()
        mock_collection = Mock()
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        mock_collection.get.return_value = {"ids": ["Course 1", "Course 2"]}

        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2")
        count = store.get_course_count()

        assert count == 2

    @patch("vector_store.chromadb")
    def test_get_lesson_link(self, mock_chromadb, temp_chroma_db):
        """Test getting lesson link"""
        mock_client = Mock()
        mock_collection = Mock()
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        lessons_data = [
            {
                "lesson_number": 1,
                "lesson_title": "Intro",
                "lesson_link": "http://example.com/lesson1",
            },
            {
                "lesson_number": 2,
                "lesson_title": "Variables",
                "lesson_link": "http://example.com/lesson2",
            },
        ]

        mock_collection.get.return_value = {
            "metadatas": [{"lessons_json": json.dumps(lessons_data)}]
        }

        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2")
        link = store.get_lesson_link("Test Course", 2)

        assert link == "http://example.com/lesson2"

    @patch("vector_store.chromadb")
    def test_get_lesson_link_not_found(self, mock_chromadb, temp_chroma_db):
        """Test getting lesson link when lesson doesn't exist"""
        mock_client = Mock()
        mock_collection = Mock()
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        lessons_data = [
            {
                "lesson_number": 1,
                "lesson_title": "Intro",
                "lesson_link": "http://example.com/lesson1",
            }
        ]

        mock_collection.get.return_value = {
            "metadatas": [{"lessons_json": json.dumps(lessons_data)}]
        }

        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2")
        link = store.get_lesson_link("Test Course", 5)  # Non-existent lesson

        assert link is None

    @patch("vector_store.chromadb")
    def test_clear_all_data(self, mock_chromadb, temp_chroma_db):
        """Test clearing all data"""
        mock_client = Mock()
        mock_chromadb.PersistentClient.return_value = mock_client

        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2")
        store.clear_all_data()

        # Should delete both collections
        expected_calls = [(("course_catalog",), {}), (("course_content",), {})]
        assert mock_client.delete_collection.call_args_list == expected_calls

        # Should recreate collections
        assert (
            mock_client.get_or_create_collection.call_count >= 4
        )  # 2 initial + 2 recreated
