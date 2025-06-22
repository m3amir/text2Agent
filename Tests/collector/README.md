# Collector Agent Tests

This directory contains comprehensive tests for the Collector agent functionality located in `Global/Collector/agent.py`.

## Overview

The Collector agent is responsible for:
- Analyzing user agent descriptions
- Selecting appropriate connectors and tools
- Gathering feedback from users
- Validating and finalizing tool selections
- Creating agent blueprints

## Test Structure

### Test Files

- `test.py` - Main test suite for the Collector class
- `conftest.py` - Shared fixtures and configuration
- `README.md` - This documentation file

### Test Classes

1. **TestCollector** - Unit tests for individual Collector methods
2. **TestCollectorModels** - Tests for Pydantic models used by the Collector
3. **TestCollectorIntegration** - Integration tests for the complete workflow

## Running Tests

### Prerequisites

Make sure you have pytest installed:
```bash
pip install pytest pytest-asyncio
```

### Run All Collector Tests

From the project root:
```bash
cd Tests/collector
python -m pytest -v
```

### Run Specific Test Classes

```bash
# Run only unit tests
python -m pytest test.py::TestCollector -v

# Run only model tests
python -m pytest test.py::TestCollectorModels -v

# Run only integration tests
python -m pytest test.py::TestCollectorIntegration -v
```

### Run Specific Test Methods

```bash
# Test collector initialization
python -m pytest test.py::TestCollector::test_collector_initialization -v

# Test task description expansion
python -m pytest test.py::TestCollector::test_expand_task_description -v

# Test full workflow without feedback
python -m pytest test.py::TestCollectorIntegration::test_full_workflow_without_feedback -v

# Test full workflow with feedback and answers
python -m pytest test.py::TestCollectorIntegration::test_full_workflow_with_feedback_and_answers -v
```

## Test Coverage

The tests cover:

### Core Functionality
- ✅ Collector initialization
- ✅ Task description expansion
- ✅ Connector selection and validation
- ✅ Tool loading and formatting
- ✅ Feedback question generation
- ✅ Human approval workflow
- ✅ Final result generation

### Edge Cases
- ✅ Error handling in LLM calls
- ✅ Empty or invalid inputs
- ✅ Missing dependencies
- ✅ Malformed responses

### Integration
- ✅ Complete workflow execution
- ✅ State transitions
- ✅ Mock external dependencies
- ✅ Feedback workflow with user answers
- ✅ Multiple feedback rounds handling

## Fixtures Available

### From conftest.py

- `mock_connectors` - Sample connector data
- `mock_connector_tools` - Sample tool schemas
- `sample_agent_descriptions` - Various agent description examples
- `sample_feedback_questions` - Example feedback questions
- `sample_state_data` - Different state configurations
- `mock_llm_responses` - Predefined LLM responses
- `mock_external_dependencies` - Auto-mocked external dependencies
- `collector_test_config` - Test configuration settings (includes amir@m3labs.co.uk as test email)

### From test.py

- `sample_agent_description` - Basic agent description
- `sample_user_email` - Test user email (amir@m3labs.co.uk)
- `collector` - Configured Collector instance
- `sample_state` - Basic state dictionary

## Mocking Strategy

The tests use extensive mocking to:

1. **Isolate the Collector logic** from external dependencies
2. **Control LLM responses** for predictable testing
3. **Mock connector loading** to avoid dependency issues
4. **Simulate user interactions** without actual human input

### Key Mocked Components

- `Global.Collector.agent.LLM` - Language model interactions
- `Global.Collector.agent.load_connectors` - Connector loading
- `Global.Collector.agent.PromptWarehouse` - Prompt management
- `Global.Collector.agent.get_multiple_connector_tools_sync` - Tool loading

## Example Test Scenarios

### Basic Collector Test
```python
def test_collector_initialization(collector, sample_agent_description):
    """Test that Collector initializes correctly"""
    assert collector.agent_description == sample_agent_description
    assert hasattr(collector, 'warehouse')
    assert hasattr(collector, 'connectors')
```

### Workflow Integration Test
```python
@pytest.mark.asyncio
async def test_full_workflow_without_feedback(mock_get_tools, mock_llm, collector):
    """Test the complete workflow without feedback questions"""
    # Setup mocks and run workflow
    workflow = collector.init_agent()
    result = await workflow.ainvoke(initial_state)
    
    assert result is not None
    assert isinstance(result, dict)
```

### Feedback Workflow Test
```python
async def test_full_workflow_with_feedback_and_answers(collector):
    """Test the complete workflow by simulating feedback questions and answers"""
    # Test state with answered questions (simulating user feedback)
    state_with_answers = {
        'input': 'I want an agent that generates charts and creates PDF reports',
        'answered_questions': [
            {
                'What type of charts do you need?': 'Bar charts and pie charts for data visualization',
                'What data sources will you use?': 'JSON files and CSV exports from database',
                'Any specific styling requirements?': 'Professional styling with company branding'
            }
        ],
        'reviewed': True,
        # ... other state fields
    }
    
    # Test human approval method with answered questions
    result = collector.human_approval(state_with_answers)
    assert result == state_with_answers
```

## Debugging Tests

### Verbose Output
```bash
python -m pytest -v -s
```

### Show Print Statements
```bash
python -m pytest -s
```

### Run Single Test with Debug
```bash
python -m pytest test.py::TestCollector::test_collector_initialization -v -s --tb=long
```

## Adding New Tests

When adding new tests:

1. **Follow the naming convention**: `test_<functionality>`
2. **Use appropriate fixtures** from conftest.py
3. **Mock external dependencies** properly
4. **Test both success and error cases**
5. **Add docstrings** explaining what the test does

### Example New Test
```python
def test_new_functionality(collector, sample_state):
    """Test description of what this test validates"""
    # Arrange
    # ... setup test data
    
    # Act
    result = collector.new_method(sample_state)
    
    # Assert
    assert expected_condition
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure the project root is in Python path
2. **Mock Failures**: Check that all external dependencies are properly mocked
3. **Async Issues**: Use `@pytest.mark.asyncio` for async tests
4. **Fixture Conflicts**: Check fixture scope and dependencies

### Getting Help

- Check the main project documentation
- Review existing test patterns
- Look at the actual Collector implementation in `Global/Collector/agent.py` 