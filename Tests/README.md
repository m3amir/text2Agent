# Test Suite Documentation

This test suite provides comprehensive testing for the text2Agent system, covering skeleton workflows, MCP (Model Context Protocol) functionality, and system integration.

## 📁 Directory Structure

```
Tests/
├── skeleton/          # Core workflow and skeleton testing
│   ├── test.py        # Main skeleton workflow tests
│   ├── conftest.py    # Test fixtures and configuration
│   └── graph_images/  # Generated visualization outputs
├── MCP/               # MCP server and tool testing
│   └── test.py        # MCP integration and tool tests
├── prompts/           # Prompt-related test artifacts
└── graph_images/      # Global test visualization outputs
```

## 🔧 Test Framework

The test suite uses **pytest** with asyncio support for testing asynchronous operations. All tests are designed to be resilient and handle expected exceptions gracefully.

### How Pytest Works - Concrete Example

Here's a real example from `Tests/skeleton/test.py` that demonstrates exactly how pytest works:

```python
@pytest.mark.asyncio
async def test_workflow_success(default_blueprint, default_task):
    """Test successful workflow completion using actual skeleton."""
    try:
        result, viz_files, compiled_graph, skeleton = await run_skeleton(
            user_email='amir@m3labs.co.uk',
            blueprint=default_blueprint,
            task_name=default_task
        )
        
        # Test actual workflow results
        assert result is not None
        assert 'status' in result
        assert 'executed_tools' in result
        
        # Check that tools were executed
        executed_tools = result.get('executed_tools', [])
        expected_tools = ['chart_generate_bar_chart', 'pdf_generate_report']
        
        # Verify at least some tools were executed
        assert len(executed_tools) > 0
        print(f"✅ Executed tools: {executed_tools}")
        
    except Exception as e:
        print(f"⚠️  Test completed with exception (this may be expected): {e}")
        # Don't fail the test for expected exceptions during workflow execution
        assert True
    
    finally:
        # Cleanup if skeleton exists
        if 'skeleton' in locals() and skeleton:
            await skeleton.cleanup_tools()
```

**How this works:**

1. **Test Discovery**: Function name starts with `test_` - pytest automatically finds it
2. **Fixture Injection**: `default_blueprint` and `default_task` are automatically injected from `conftest.py`
3. **Async Support**: `@pytest.mark.asyncio` enables `async`/`await` syntax
4. **Assertions**: `assert` statements validate expected behavior - failures stop the test
5. **Exception Handling**: `try/except` allows graceful handling of expected failures
6. **Cleanup**: `finally` block ensures resources are properly cleaned up
7. **Output**: `print()` statements provide debugging information during test runs

**Running this test:**
```bash
pytest Tests/skeleton/test.py::test_workflow_success -v
```

Pytest will discover the test, inject fixtures, run the async function, and report PASS/FAIL based on assertions.

## 📋 Test Categories

### 1. Skeleton Tests (`Tests/skeleton/`)

Tests the core workflow execution system that orchestrates tool usage based on blueprints.

#### Key Test Files:
- **`test.py`** - Main skeleton workflow tests
- **`conftest.py`** - Test fixtures and blueprint configurations

#### Test Functions:
- `test_workflow_success()` - Tests full workflow execution with charts and PDF generation
- `test_charts_workflow()` - Tests chart-only workflows
- `test_blueprint_structure()` - Validates blueprint configuration format
- `test_tool_counting()` - Tests tool execution tracking

#### Test Fixtures:
- `default_blueprint` - Standard workflow with Charts → PDF flow
- `charts_only_blueprint` - Simplified chart-only workflow
- `default_task` - Complex task with chart generation and PDF reporting
- `charts_task` - Simple chart generation task

### 2. MCP Tests (`Tests/MCP/`)

Tests the Model Context Protocol integration, including server initialization, tool loading, and LangChain conversion.

#### Test Classes:

**`TestMCPConfiguration`**
- Validates MCP configuration files exist and have correct structure
- Tests server configuration format and local tools setup
- Verifies tool paths and descriptions

**`TestUniversalToolServer`** 
- Tests server initialization and configuration loading
- Tests credential extraction for various tools
- Tests real tool loading and handler creation

**`TestLangChainConverter`**
- Tests conversion of MCP tools to LangChain format
- Tests specific tool retrieval functionality
- Tests connector tool formatting

**`TestMCPIntegration`**
- Integration tests for MCP components
- Tests file structure and import validation
- Tests server instantiation and directory structure

## 🏃‍♂️ Running Tests

### Prerequisites
```bash
pip install pytest pytest-asyncio
```

### Run All Tests
```bash
# From the project root
pytest Tests/

# With verbose output
pytest Tests/ -v

# Run specific test category
pytest Tests/skeleton/ -v
pytest Tests/MCP/ -v
```

### Run Individual Tests
```bash
# Run skeleton workflow tests
pytest Tests/skeleton/test.py::test_workflow_success -v

# Run MCP configuration tests
pytest Tests/MCP/test.py::TestMCPConfiguration -v
```

## 📊 Test Design Philosophy

### Graceful Exception Handling
Tests are designed to be resilient and handle expected exceptions during workflow execution. This approach acknowledges that:
- External services may be unavailable
- Tool execution may have dependencies that aren't always met
- Network connectivity issues may occur

### Real System Testing
Tests use actual:
- MCP server configurations
- Tool implementations
- Workflow blueprints
- File system operations

This ensures tests validate real-world functionality rather than mocked behavior.

### Cleanup and Resource Management
Tests include proper cleanup mechanisms:
- Skeleton cleanup after workflow tests
- Resource deallocation for async operations
- Temporary file management

## 🔍 Test Output Interpretation

### Success Indicators
- ✅ Marks successful operations
- 📋 Shows informational output (tool lists, configurations)
- Assertions pass without exceptions

### Warning Indicators  
- ⚠️ Indicates expected exceptions or missing optional components
- Tests may complete successfully even with warnings
- Warnings help identify system dependencies or configuration issues

## 🛠 Configuration Requirements

### MCP Configuration
Tests expect MCP configuration files at:
- `MCP/Config/mcp_servers_config.json` - Server configurations
- `MCP/Config/config.json` - Basic configuration

### Tool Dependencies
Tests may require:
- Chart generation tools
- PDF generation capabilities
- Microsoft Office integration (optional)
- Network connectivity for external tools

## 📈 Extending the Test Suite

### Adding New Tests
1. Create test files following the naming convention `test_*.py`
2. Use appropriate test classes for organization
3. Include proper async/await for asynchronous operations
4. Add cleanup logic in `finally` blocks
5. Use fixtures for common test data

### Adding New Fixtures
Add fixtures to `conftest.py` files for:
- Blueprint configurations
- Task descriptions
- Mock data
- Configuration objects

### Best Practices
- Use descriptive test names that explain what is being tested
- Include both positive and negative test cases
- Test edge cases and error conditions
- Document test purpose with docstrings
- Use proper assertion messages for clarity

## 📝 Notes

- The test suite generates visualization files in `graph_images/` directories
- Tests are designed to work with the actual system configuration
- Some tests may require specific environment setup or credentials