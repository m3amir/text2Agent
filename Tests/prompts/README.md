# Prompt Warehouse Test Suite

This directory contains comprehensive tests for the PromptWarehouse functionality in the text2Agent system.

## Test Structure

### Unit Tests (`test_promptwarehouse.py`)
- **TestPromptWarehouse**: Core functionality tests with mocked AWS services
  - AWS session initialization with profile fallback
  - Prompt creation, listing, and retrieval
  - File synchronization from prompt.py files
  - Error handling for malformed files
  - Existing prompt detection

- **TestPromptWarehouseIntegration**: Tests with real prompt files
  - Validates real prompt file structure
  - Ensures prompt files are importable
  - Checks for expected prompt variables

### Integration Tests (`test_prompt_integration.py`)
- **TestPromptWarehouseIntegration**: Real AWS service integration
  - Tests real AWS Bedrock connection (when credentials available)
  - Validates prompt file discovery and content
  - Tests AWS profile fallback to environment variables
  - Validates all real prompt files in the project

- **TestPromptWarehouseErrorHandling**: Edge cases and error scenarios
  - Invalid AWS profile handling
  - Empty directory handling
  - Malformed prompt file handling

### Test Data
- `test_prompts/`: Sample prompt files for testing sync functionality
  - `test_collector/prompt.py`: Test collector prompts
  - `test_str/prompt.py`: Test STR prompts

## Key Features Tested

### AWS Profile Fallback
The tests verify that PromptWarehouse properly handles AWS credential scenarios:
1. **Local Development**: Uses AWS profile `m3` when available
2. **CI/GitHub Actions**: Falls back to environment variables when profile fails
3. **No Credentials**: Gracefully handles missing credentials

### Prompt File Discovery
Tests validate the automatic discovery and synchronization of prompt files:
- Scans subdirectories for `prompt.py` files
- Identifies variables ending with `_prompt`
- Creates prompts in AWS Bedrock Prompt Management
- Handles existing prompts (no duplicates)

### Content Validation
Integration tests ensure real prompt files contain:
- Valid Python syntax
- String content with substantial length
- Proper agent instruction patterns:
  - "You are/must", "Your task"
  - "As an", "I have/will" (for different prompt styles)

### Error Handling
Tests verify graceful handling of:
- Missing AWS credentials
- Invalid AWS profiles
- Malformed Python files
- Empty directories
- Network/service errors

## Running Tests

```bash
# Run all prompt tests
cd Tests/prompts
python -m pytest . -v

# Run only unit tests
python -m pytest test_promptwarehouse.py -v

# Run only integration tests
python -m pytest test_prompt_integration.py -v

# Run with output (to see discovered prompts)
python -m pytest . -v -s
```

## Test Coverage

The test suite covers:
- ✅ **19 total tests** (all passing)
- ✅ **AWS credential scenarios** (profile + environment variables)
- ✅ **Real prompt file validation** (9 real prompts discovered)
- ✅ **Error handling** (malformed files, missing credentials)
- ✅ **Integration with AWS Bedrock** (when credentials available)
- ✅ **File synchronization** (prompt.py → AWS Bedrock)

## Real Prompts Validated

The tests automatically discover and validate these real prompt files:
- `collector.collector_prompt` - Main collector agent
- `collector.feedback_prompt` - Feedback agent
- `collector.tools_prompt` - Tools selection agent
- `task_expansion.expansion_prompt` - Task expansion agent
- `STR.format_str_prompt` - STR formatting agent
- `STR.generation_prompt` - STR generation agent
- `STR.orchestrator_prompt` - STR orchestrator agent
- `poolOfColleagues.poc_judge_prompt` - Colleague evaluation agent
- `poolOfColleagues.poc_prompt` - Pool of colleagues agent

## Dependencies

The tests require:
- `pytest` - Test framework
- `boto3` - AWS SDK (for real integration tests)
- `unittest.mock` - For mocking AWS services in unit tests

## Notes

- Tests automatically skip AWS integration tests when credentials are unavailable
- The PromptWarehouse class now includes AWS profile fallback logic
- All tests work in both local development and CI/GitHub Actions environments
- Real AWS calls are only made in integration tests when credentials are present 