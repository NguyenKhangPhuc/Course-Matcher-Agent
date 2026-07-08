from unittest.mock import MagicMock, patch
from app.core.summarizer import summarize_jd

@patch("app.core.summarizer.groq_client")
def test_summarize_jd_success(mock_groq_client):
    """
    Target: summarize_jd()
    Scenario: Test summarizing job description when Groq API returns a valid summary.
    Expectation: It should call Groq completions API with correct prompt, parameters, and return stripped summary string.
    """
    # Arrange
    jd = "Need a Python backend developer. Salary is competitive. Location: Boston."
    expected_summary = "This is a summarized output focusing on technical skills like Python."
    
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="  " + expected_summary + "  "))
    ]
    mock_groq_client.chat.completions.create.return_value = mock_response

    # Act
    summary = summarize_jd(jd)

    # Assert
    mock_groq_client.chat.completions.create.assert_called_once()
    called_kwargs = mock_groq_client.chat.completions.create.call_args[1]
    
    # Verify API parameters
    assert called_kwargs["max_tokens"] == 300
    assert called_kwargs["temperature"] == 0.3
    
    # Verify prompt contents
    prompt_content = called_kwargs["messages"][0]["content"]
    assert jd in prompt_content
    assert "Extract ONLY the technical skills" in prompt_content
    
    # Verify stripped output
    assert summary == expected_summary
