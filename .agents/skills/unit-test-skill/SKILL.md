---
name: unit-test-skill
description: Expert QA and testing specialist. Identifies high-value test targets, designs robust edge-case scenarios, applies AAA patterns, and enforces strict English docstring documentation for maximum test readability and coverage.
---
# Agent Skill: Automated Unit Testing Framework & Best Practices

## Purpose
This skill empowers the agent to analyze source code, identify high-value test targets, and generate robust, readable, and maintainable unit tests. The agent must ensure all generated test functions follow strict structural patterns and include comprehensive English docstrings.

---

## 1. Test Identification Strategy
The agent must not test blindly. It should prioritize code components that impact application stability and correctness.

### What to Test (High Priority)
* **Pure Functions & Core Business Logic:** Functions that calculate values, transform data, or enforce business rules based on inputs.
* **Edge Cases & Boundary Values:** Inputs at the extreme ends of expected ranges (e.g., empty strings, `None`/`null` values, negative numbers, maximum limits).
* **Error Handling & Exceptions:** Verifying that functions throw the correct exceptions when given invalid inputs or when dependencies fail.
* **Data Validation:** Logic that checks the integrity of incoming payloads or configurations.

### What NOT to Test (Low Priority)
* Third-party libraries or framework built-ins (assume they work).
* Trivial getters, setters, or pass-through methods without logic.
* Strict UI/UX rendering details (unless testing explicit component state logic).

---

## 2. Test Architecture & Best Practices

### The AAA Pattern (Arrange, Act, Assert)
Every test function must visually separate its execution steps to maximize readability:
1.  **Arrange:** Set up the objects, mock dependencies, and prepare the inputs.
2.  **Act:** Execute the target function or method.
3.  **Assert:** Verify that the outcome matches expectations.

### Best Practices
* **Isolation:** Use mocks, stubs, or fakes for external dependencies (APIs, databases, file systems) to ensure tests are fast and deterministic.
* **Single Responsibility:** Each test function should focus on testing *one specific behavior* or path. Do not pack multiple unrelated assertions into a single test function.
* **Independence:** Tests must be executable in any order and must not rely on the state left by previous tests.

---

## 3. Code & Documentation Standards

To maintain high code quality, the agent must adhere to the following rules when generating test files:

* **Language:** All code, test names, comments, and docstrings must be written exclusively in **English**.
* **Naming Convention:** Use descriptive names that indicate the function being tested and the expected outcome (e.g., `test_calculate_total_with_valid_items`, `test_user_login_raises_value_error_on_empty_email`).
* **Required Docstring Format:** Every single test function must contain a docstring explicitly stating:
    1.  The specific target function being tested.
    2.  The scenario or condition being evaluated.
    3.  The expected outcome.

---

## 4. Code Examples

### Example 1: Python (pytest)

```python
import pytest
from app.calculator import divide

def test_divide_by_zero_raises_value_error():
    """
    Target: divide()
    Scenario: Test division when the denominator is zero.
    Expectation: It should raise a ValueError with an appropriate message.
    """
    # Arrange
    numerator = 10
    denominator = 0

    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        divide(numerator, denominator)
    
    assert "Cannot divide by zero" in str(exc_info.value)