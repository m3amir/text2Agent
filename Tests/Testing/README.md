# Testing Module - Real Integration Tests

This directory contains **real integration tests** for the `Test` class located in `Global/Testing/test.py`.

## What These Tests Do

These tests use **actual imports and real module invocations** - no mocks or fake data. They test the complete system end-to-end:

✅ **Real LLM calls** - Uses actual language models  
✅ **Real AWS services** - Connects to actual AWS/S3  
✅ **Real email tools** - Tests actual Microsoft email integration  
✅ **Real file operations** - Creates and uploads actual files  
✅ **Real workflows** - Tests the complete testing workflow  

## Current Files

```
Tests/Testing/
├── test.py          # Real integration tests
└── README.md        # This documentation
```

## Test File: `test.py`

### Test Classes:

**`TestTestClassReal`** - Core functionality tests:
- `test_real_initialization` - Tests class setup with real dependencies
- `test_real_agent_run_id_generation` - Tests unique ID generation
- `test_real_llm_integration` - Tests actual LLM API calls  
- `test_real_skeleton_integration` - Tests real tool loading (MCP)
- `test_real_tool_question_generation` - Tests LLM-generated questions
- `test_real_tool_args_generation` - Tests LLM-generated tool arguments
- `test_real_email_tool_execution` - Tests email tool structure (dry run)
- `test_real_full_workflow_dry_run` - Tests complete workflow without sending emails
- `test_real_export_functionality` - Tests real file creation and S3 upload

**`TestRealMainFunction`** - Main function tests:
- `test_real_main_execution` - Tests the main() function

**Utility Functions:**
- `test_real_module_imports` - Verifies all modules can be imported
- `test_real_dependencies_available` - Checks which services are available

### Test Fixtures:
- `sample_user_email` - Returns `amir@m3labs.co.uk`
- `sample_recipient` - Returns `info@m3labs.co.uk`  
- `sample_task_description` - Test task for email notifications
- `sample_secret_name` - Returns `test_`
- `real_log_manager` - Real LogManager instance
- `real_test_instance` - Real Test class instance with actual dependencies

## How to Run Tests

### Run All Tests
```bash
source venv/bin/activate
python -m pytest Tests/Testing/test.py -v
```

### Run Specific Test Class
```bash
python -m pytest Tests/Testing/test.py::TestTestClassReal -v
```

### Run Specific Test
```bash
python -m pytest Tests/Testing/test.py::TestTestClassReal::test_real_llm_integration -v
```

### Run with More Details
```bash
python -m pytest Tests/Testing/test.py -v -s
```

### Run Only Fast Tests (skip slow LLM tests)
```bash
python -m pytest Tests/Testing/test.py -v -m "not slow"
```

### Run Only Integration Tests
```bash
python -m pytest Tests/Testing/test.py -v -m "integration"
```

## What You'll See

### ✅ When Services Are Available:
- Real LLM responses to questions
- Actual tool loading from MCP servers
- Generated questions and arguments using LLM
- File creation and S3 uploads
- Complete workflow execution

### ⚠️ When Services Are Not Available:
- Tests gracefully skip with informative messages
- Shows which dependencies are missing
- Continues testing available components

## Configuration

### Email Settings:
- **From**: `amir@m3labs.co.uk`
- **To**: `info@m3labs.co.uk`  
- **Secret**: `test_`

### AWS Settings:
- **Region**: `eu-west-2`
- **Bucket**: `text2agent-testing-bucket`

## Test Safety

### Dry Run Features:
- Email tools are tested but **don't actually send emails**
- File operations create real files but in test directories  
- S3 uploads use test bucket paths
- Workflow tests override actual execution to prevent side effects

### Real vs Simulated:
- **Real**: LLM calls, file creation, AWS connections, tool loading
- **Simulated**: Email sending, destructive operations

## Expected Behavior

### First Time Running:
1. Tests import all real modules (`LLM`, `Skeleton`, `PromptWarehouse`, etc.)
2. Initialize actual services (LLM, AWS, MCP)
3. Test each component individually  
4. Run complete workflow in dry-run mode
5. Export real test results to files

### Success Indicators:
- ✅ All modules import successfully
- ✅ LLM responds to prompts (e.g., "What is the capital of France?")
- ✅ Tools load from MCP servers
- ✅ Arguments generated correctly for email tools
- ✅ Files created and uploaded to S3
- ✅ Workflow completes without errors

### Example Output:
```
✅ LLM response: The capital of France is Paris...
✅ Loaded tools: ['microsoft_mail_send_email_as_user']
✅ Generated question: How should we test email functionality?
✅ Generated args: {'to': 'info@m3labs.co.uk', 'subject': 'Test Email'}
✅ Local file created: /path/to/test_results.json
```

## Troubleshooting:

- **LLM tests fail**: Check API keys and model access
- **Tool tests fail**: Check MCP server configuration  
- **S3 tests fail**: Check AWS credentials and permissions
- **Import tests fail**: Check virtual environment and dependencies

## Test Markers

The tests use pytest markers for organization:

- `@pytest.mark.real` - Real integration tests
- `@pytest.mark.integration` - Integration tests  
- `@pytest.mark.slow` - Slow tests that make API calls

## Why Real Tests Matter

1. **Validates Actual Integration** - Ensures components work together
2. **Catches Real Issues** - Finds problems mocks can't detect  
3. **Tests Configuration** - Verifies settings and credentials work
4. **Demonstrates Functionality** - Shows the system actually works
5. **Builds Confidence** - Proves the testing system is production-ready

These tests give you confidence that the `Test` class actually works with real services, not just in isolation. 