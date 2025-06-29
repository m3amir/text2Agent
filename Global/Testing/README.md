# Blueprint Testing Framework

An intelligent testing system that validates agent blueprints using AI-powered test generation and analysis.

## Overview

`test.py` automatically tests blueprint tools by:
1. **Generating test questions** for each tool using LLM
2. **Creating realistic arguments** based on tool schemas and context
3. **Executing tools** and capturing results
4. **Analyzing coverage** to see if questions were answered
5. **Outputting clean JSON** with comprehensive statistics

## Usage

```bash
python Global/Testing/test.py
```

## How It Works

### 1. Blueprint Analysis & Setup
**Function: `_extract_tools_from_blueprint()`**
- Parses the blueprint's `node_tools` dictionary
- Extracts unique tool names across all nodes
- Sets up test environment with logging and result directories
- Determines appropriate task description based on tool types:
  - Email tools → "Send professional email notification"
  - SharePoint/search tools → "Find SOW for Xen project"
  - Default → "Test tools for correctness"

### 2. Tool Loading & Authentication
**Function: `test_tools()` → `_load_tools_from_session()`**
- Establishes persistent MCP session with tool server
- Loads actual tool instances from MCP server
- Maps tool names to executable tool objects
- Handles credential management through MCP

### 3. Intelligent Question Generation
**Function: `_generate_tool_question()`**
- Uses LLM with focused prompt to generate specific test questions
- Inputs: task description, tool name, tool description
- Applies `_extract_core_question()` to clean up LLM response
- Removes commentary, formatting, and extracts just the core question
- Example: "Can the microsoft_sharepoint_search_files tool find SOW documents for the Xen project?"

### 4. Schema Extraction & Analysis
**Function: `_get_tool_schema()`**
- Attempts multiple methods to extract tool parameter schema:
  - `tool.get_input_jsonschema()` - Built-in schema method
  - `tool.get_input_schema()` - Alternative schema method
  - `_parse_schema_from_description()` - Parse from tool docstring
  - Function signature inspection as fallback
- Identifies parameter types, required fields, and descriptions
- Updates tool's `args_schema` for LLM binding

### 5. Dynamic Argument Generation
**Function: `_generate_tool_args()`**
- **Primary Method**: Uses `bind_tools()` to let LLM understand tool schema
- **Context Building**: `_build_previous_context()` extracts useful data from previous tool results
  - File IDs from search results for download tools
  - Drive names, user emails, etc.
- **LLM Invocation**: Generates realistic arguments based on:
  - Tool schema and parameter types
  - Test question context
  - Previous tool results
  - Task description
- **Fallback Logic**: `_generate_fallback_args()` provides sensible defaults when LLM fails:
  - `file_id` → Extracts from previous context or uses "test-file-id-123"
  - `query` → Uses task keywords or "test query"
  - `email` parameters → Uses configured user email
  - Type-based defaults for strings, integers, booleans, arrays

### 6. Tool Execution
**Function: `_test_single_tool()`**
- Adds credential handling for Microsoft tools (`secret_name` parameter)
- Executes tools using either `ainvoke()` (async) or `invoke()` (sync)
- Captures both successful results and detailed error information
- Stores raw results for context chaining to subsequent tools
- Formats results using `_format_result()` for readability

### 7. Question Coverage Analysis
**Function: `analyze_question_coverage()`**
- Uses LLM to determine if each generated question was actually answered
- Analyzes the relationship between:
  - Original test question
  - Tool execution result
  - Whether the result addresses the question
- Returns structured analysis with:
  - `question_answered`: boolean
  - `explanation`: why it was/wasn't answered
  - `relevant_information`: specific data that addresses the question
- Provides fallback analysis using simple error detection if LLM fails

### 8. Results Export & Logging
**Functions: `export_results()` & `export_results_with_analysis()`**
- **Basic Export**: Tool results, questions, execution metadata
- **Comprehensive Export**: Includes LLM coverage analysis and statistics
- **S3 Storage**: Saves results to user-specific S3 paths
- **Log Management**: Syncs detailed logs to S3 for audit trails
- **JSON Structure**: Machine-readable format for CI/CD integration

## Technical Implementation Details

### AI/LLM Integration
The framework leverages multiple LLM interactions:

**Question Generation Prompt:**
```python
f"""Based on the task "{task_description}" and this tool:

Tool Name: {tool_name}
Description: {tool_description or 'No description available'}

Generate ONE specific test question that would verify if this tool works correctly for the given task.
Output only the question, no explanations or commentary."""
```

**Argument Generation Process:**
- Uses `bind_tools()` from LangChain to create tool-aware LLM
- Passes tool schema, context, and generation prompt
- LLM understands parameter types and generates appropriate values
- Falls back to rule-based generation if LLM fails

**Analysis Prompt Structure:**
- Compares question intent with actual tool results
- Determines factual coverage rather than just success/failure
- Provides structured feedback for result interpretation

### Context Chaining Logic
**Function: `_build_previous_context()`**
- Scans previous tool results for reusable data
- Extracts patterns like:
  - File IDs: `"id": "file_123"` → Used for download operations
  - Drive names: `"drive_name": "Documents"` → Used for SharePoint operations
  - User data: Email addresses, names for notification tools
- Maintains context state across tool executions
- Enables realistic workflow testing (search → download → analyze)

### Schema Parsing Robustness
The system handles multiple schema formats:
1. **JSON Schema**: Direct parameter extraction with types and descriptions
2. **Pydantic Models**: Automatic field inspection
3. **Docstring Parsing**: Regex extraction of parameter documentation
4. **Function Signatures**: Inspection-based parameter detection
5. **Fallback Defaults**: When all else fails, intelligent parameter guessing

### Error Recovery Mechanisms
- **Graceful Degradation**: Continues testing even if individual tools fail
- **Multiple Fallbacks**: Schema → Arguments → Execution → Analysis
- **Context Preservation**: Failed tools don't break context for subsequent tools
- **Detailed Logging**: Captures full error traces for debugging

### Data Flow Architecture

```
Blueprint → Tool Extraction → Question Generation → Schema Analysis
     ↓              ↓                   ↓               ↓
Tool Loading → Context Building → Argument Generation → Tool Execution
     ↓              ↓                   ↓               ↓
Result Capture → Coverage Analysis → Statistics → Export to S3
```

**Key Data Structures:**
- `blueprint_results`: Stores per-blueprint execution data
- `tool_results`: Maps tool names to execution results and metadata
- `previous_context`: Maintains state between tool executions
- `coverage_analysis`: LLM-generated question coverage assessments

**Threading Model:**
- Synchronous execution within each blueprint
- Context preservation across tool calls
- Async support for individual tool execution
- Sequential processing to maintain context chain integrity

### Performance Optimizations
- **Schema Caching**: Tool schemas cached after first extraction
- **Context Reuse**: Previous results available to subsequent tools
- **Lazy Loading**: Tools loaded only when needed
- **Error Isolation**: Failed tools don't block other tool execution
- **Batch Analysis**: Coverage analysis performed in batches when possible

## Output Format

```json
{
  "timestamp": "2025-06-30T00:35:12.206451",
  "total_blueprints": 1,
  "successful_blueprints": 1,
  "failed_blueprints": 0,
  "blueprints": {
    "blueprint_1": {
      "success": true,
      "tools_tested": [
        "microsoft_sharepoint_search_files",
        "microsoft_sharepoint_download_and_extract_text"
      ],
      "total_tools": 2,
      "error": null
    }
  },
  "overall_statistics": {
    "total_tools_tested": 2,
    "successful_tools": 2,
    "failed_tools": 0,
    "success_rate": 100.0
  }
}
```

## Configuration

### Blueprint Structure
Edit the `example_blueprints` in `test.py` to test different configurations:

```python
example_blueprints = [
    {
        "nodes": ["search_node", "process_node", "finish"],
        "node_tools": {
            "search_node": ["tool1", "tool2"],
            "process_node": ["tool3"]
        }
    }
]
```

### Environment Variables
```bash
# AWS Configuration (required for secrets and S3)
AWS_PROFILE=m3                                    # AWS profile for authentication
AWS_REGION=eu-west-2                             # AWS region for S3 operations

# User Configuration (for tool personalization)
USER_EMAIL=your_email@company.com                # Default email for email-based tools
```

### Required Setup
- **AWS Credentials**: Configured via AWS CLI or environment variables
- **MCP Server**: Running and accessible via `mcp_session` import
- **Blueprint Files**: JSON files in `blueprints/` directory (if loading from files)
- **Secrets Manager**: Microsoft credentials stored in AWS Secrets Manager as `test_`
- **S3 Bucket**: For result export and log storage

### Credential Format (AWS Secrets Manager)
For Microsoft tools, store credentials in AWS Secrets Manager under key `test_`:
```json
{
  "MICROSOFT_TENANT_ID": "your-tenant-id",
  "MICROSOFT_CLIENT_ID": "your-client-id", 
  "MICROSOFT_CLIENT_SECRET": "your-client-secret",
  "MICROSOFT_USER_EMAIL": "your-email@company.com"
}
```

## Requirements

### Python Dependencies
- `boto3` - AWS service integration (S3, Secrets Manager)
- `langchain` - LLM interactions and tool binding
- `langchain-openai` - OpenAI LLM provider
- `pydantic` - Schema validation and parsing
- `asyncio` - Async tool execution support
- `json`, `logging`, `datetime` - Standard library modules

### External Services
- **OpenAI API**: For LLM-powered generation and analysis
- **AWS Services**: S3 for storage, Secrets Manager for credentials
- **MCP Server**: Must be running with required tools loaded
- **Microsoft Graph API**: For SharePoint and email tools (if used)

## Error Handling

The framework handles:
- Missing tool schemas (parses from descriptions)
- LLM generation failures (fallback arguments)
- Tool execution errors (comprehensive error reporting)
- Credential format variations (supports both prefixed and standard keys) 