from unittest.mock import MagicMock, patch
import pytest
from app.core.course_search import search_courses

@patch("app.core.course_search.embed_text")
@patch("app.core.course_search.supabase")
def test_search_courses_success(mock_supabase, mock_embed_text):
    """
    Target: search_courses()
    Scenario: Test successful course search when supabase returns matching courses.
    Expectation: It should embed query text, call supabase RPC with correct parameters, and return list of courses.
    """
    # Arrange
    tech_reqs = "Python and machine learning"
    source_id = "src_123"
    programme = "Master"
    limit = 5
    mock_vector = [0.1, 0.2, 0.3]
    mock_embed_text.return_value = mock_vector
    
    mock_rpc_builder = MagicMock()
    mock_response = MagicMock()
    mock_response.data = [{"id": 1, "name": "ML Course"}]
    mock_rpc_builder.execute.return_value = mock_response
    mock_supabase.rpc.return_value = mock_rpc_builder

    # Act
    results = search_courses(tech_reqs, source_id, programme, limit=limit)

    # Assert
    mock_embed_text.assert_called_once_with(tech_reqs)
    mock_supabase.rpc.assert_called_once()
    called_args, called_kwargs = mock_supabase.rpc.call_args
    assert called_args[0] == "match_courses"
    assert called_args[1]["query_embedding"] == "[0.1,0.2,0.3]"
    assert called_args[1]["source_id"] == source_id
    assert called_args[1]["match_count"] == limit
    assert called_args[1]["filter_programme"] == programme
    assert results == [{"id": 1, "name": "ML Course"}]


@patch("app.core.course_search.embed_text")
@patch("app.core.course_search.supabase")
def test_search_courses_empty_result(mock_supabase, mock_embed_text):
    """
    Target: search_courses()
    Scenario: Test course search when supabase returns no results.
    Expectation: It should safely return an empty list.
    """
    # Arrange
    tech_reqs = "Go development"
    source_id = "src_456"
    programme = "Bachelor"
    mock_vector = [0.9, 0.8, 0.7]
    mock_embed_text.return_value = mock_vector
    
    mock_rpc_builder = MagicMock()
    mock_response = MagicMock()
    mock_response.data = None
    mock_rpc_builder.execute.return_value = mock_response
    mock_supabase.rpc.return_value = mock_rpc_builder

    # Act
    results = search_courses(tech_reqs, source_id, programme)

    # Assert
    mock_embed_text.assert_called_once_with(tech_reqs)
    mock_supabase.rpc.assert_called_once()
    called_args, called_kwargs = mock_supabase.rpc.call_args
    assert called_args[0] == "match_courses"
    assert called_args[1]["query_embedding"] == "[0.9,0.8,0.7]"
    assert called_args[1]["source_id"] == source_id
    assert called_args[1]["filter_programme"] == programme
    assert results == []
