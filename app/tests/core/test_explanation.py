import json
import pytest
from unittest.mock import MagicMock, patch
from app.core.explanation import generate_batch_course_explanations

@patch("app.core.explanation.groq_client")
def test_generate_batch_course_explanations_success(mock_groq_client):
    """
    Target: generate_batch_course_explanations()
    Scenario: Test generating course explanations when Groq API returns a valid JSON response.
    Expectation: It should format inputs, query Groq with JSON structure format, truncate learning outcomes, and return parsed dict.
    """
    # Arrange
    courses = [
        {
            "id": "c1",
            "name": "Intro to Python",
            "learning_outcomes": "A" * 400  # Longer than 300 chars to test truncation
        },
        {
            "id": "c2",
            "name": "Data Structures",
            "learning_outcomes": None  # Test handling None
        }
    ]
    tech_reqs = "Requires Python programming and data structure design."
    
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='{"c1": "Covers Python basics", "c2": "Teaches data structures"}'))
    ]
    mock_groq_client.chat.completions.create.return_value = mock_response

    # Act
    result = generate_batch_course_explanations(courses, tech_reqs)

    # Assert
    mock_groq_client.chat.completions.create.assert_called_once()
    called_kwargs = mock_groq_client.chat.completions.create.call_args[1]
    
    # Verify parameter matching
    assert called_kwargs["temperature"] == 0.2
    assert called_kwargs["response_format"] == {"type": "json_object"}
    
    # Verify truncation logic in the prompt
    prompt = called_kwargs["messages"][0]["content"]
    expected_courses_summary = [
        {
            "id": "c1",
            "name": "Intro to Python",
            "learning_outcomes": "A" * 300  # Truncated
        },
        {
            "id": "c2",
            "name": "Data Structures",
            "learning_outcomes": ""  # Handled None
        }
    ]
    assert json.dumps(expected_courses_summary) in prompt
    assert tech_reqs in prompt
    
    # Verify final output structure
    assert result == {"c1": "Covers Python basics", "c2": "Teaches data structures"}


@patch("app.core.explanation.groq_client")
def test_generate_batch_course_explanations_invalid_json_fallback(mock_groq_client):
    """
    Target: generate_batch_course_explanations()
    Scenario: Test explanation generation when Groq API returns malformed JSON or throws an exception.
    Expectation: It should gracefully catch the exception and return an empty dictionary.
    """
    # Arrange
    courses = [{"id": "c1", "name": "Web Dev"}]
    tech_reqs = "Web skills"
    
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="Malformed response that is not JSON"))
    ]
    mock_groq_client.chat.completions.create.return_value = mock_response

    # Act
    result = generate_batch_course_explanations(courses, tech_reqs)

    # Assert
    assert result == {}


@patch("app.core.explanation.groq_client")
def test_generate_batch_course_explanations_exception_propagation(mock_groq_client):
    """
    Target: generate_batch_course_explanations()
    Scenario: Test explanation generation when Groq API call raises an unexpected exception.
    Expectation: It should propagate the exception to the caller.
    """
    # Arrange
    courses = [{"id": "c1", "name": "Web Dev"}]
    tech_reqs = "Web skills"
    mock_groq_client.chat.completions.create.side_effect = RuntimeError("API service offline")

    # Act & Assert
    with pytest.raises(RuntimeError) as exc_info:
        generate_batch_course_explanations(courses, tech_reqs)

    assert "API service offline" in str(exc_info.value)
