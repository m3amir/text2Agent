# Prompt Warehouse

A simple system to manage and sync AI prompts with AWS Bedrock from your local files.

## 📁 How It Works

The Prompt Warehouse automatically scans subdirectories in the `Prompts/` folder for `prompt.py` files and syncs any variables ending with `_prompt` to AWS Bedrock.

## 🚀 Quick Start

### 1. Create Your Prompt Files

Create subdirectories under `Prompts/` with a `prompt.py` file:

```
Prompts/
├── collector/
│   └── prompt.py
├── analyzer/
│   └── prompt.py
└── promptwarehouse.py
```

### 2. Define Your Prompts

In each `prompt.py` file, create variables ending with `_prompt`:

```python
# Prompts/collector/prompt.py

collector_prompt = """
You are a Collector Agent that receives a natural language description...
Your job is to understand the user's intent and identify required connectors.
"""

feedback_prompt = """
You are a Feedback Agent that reviews connector suggestions...
Provide clarifying questions to improve the agent building process.
"""
```

### 3. Sync to AWS Bedrock

```python
from Prompts.promptwarehouse import PromptWarehouse

# Initialize with your AWS profile
warehouse = PromptWarehouse('your-aws-profile-name')

# Sync all prompts from files
results = warehouse.sync_prompts_from_files()

# List all prompts
print(warehouse.list_prompts())
```

## 📋 Usage Examples

### Sync Prompts
```python
warehouse = PromptWarehouse('m3')
warehouse.sync_prompts_from_files()
```

**Output:**
```
✓ Created: collector
✓ Created: feedback
- Exists: analyzer
```

### List All Prompts
```python
print(warehouse.list_prompts())
```

**Output:**
```
============================================================
PROMPT WAREHOUSE (3 prompts)
============================================================
📝 collector
   Prompt from collector/collector_prompt
   Updated: 2024-01-15 14:30
   Version: 1
------------------------------------------------------------
📝 feedback
   Prompt from collector/feedback_prompt
   Updated: 2024-01-15 14:30
   Version: 1
------------------------------------------------------------
```

### Get a Specific Prompt
```python
prompt_text = warehouse.get_prompt('collector')
print(prompt_text)
```

**Output:**
```
You are a Collector Agent that receives a natural language description...
Your job is to understand the user's intent and identify required connectors.
```

## 🏗️ File Structure

```
Prompts/
├── README.md                 # This file
├── promptwarehouse.py        # Main warehouse class
├── collector/
│   ├── __init__.py
│   └── prompt.py            # Contains collector_prompt, feedback_prompt
├── analyzer/
│   ├── __init__.py
│   └── prompt.py            # Contains analyzer_prompt, summary_prompt
└── generator/
    ├── __init__.py
    └── prompt.py            # Contains generator_prompt
```

## 📝 Naming Convention

- **Variable names** ending with `_prompt` become the prompt name in Bedrock
- `collector_prompt` → **collector**
- `feedback_prompt` → **feedback**
- `analyzer_prompt` → **analyzer**

## ⚙️ Setup Requirements

1. **AWS Profile**: Configure your AWS credentials with a named profile
2. **Permissions**: Your AWS profile needs Bedrock permissions:
   - `bedrock:CreatePrompt`
   - `bedrock:CreatePromptVersion`
   - `bedrock:ListPrompts`
   - `bedrock:GetPrompt`

3. **Region**: Currently set to `eu-west-2` (modify in `promptwarehouse.py` if needed)

## 🔄 Workflow

1. **Create** prompt files in subdirectories
2. **Define** prompts as variables ending with `_prompt`
3. **Run** `sync_prompts_from_files()` to upload to Bedrock
4. **Use** `get_prompt()` to retrieve prompts in your applications

## 💡 Tips

- **No Duplicates**: The system won't create prompts that already exist
- **Version Control**: Each prompt creation automatically creates a version
- **Error Handling**: Failed syncs are reported but don't stop the process
- **Clean Names**: Use descriptive variable names as they become your prompt names

## 🚨 Common Issues

**"No prompts found"**: Check your AWS profile and region settings
**"Error creating prompt"**: Verify your AWS permissions
**"N/A version"**: The prompt exists but version info couldn't be retrieved

---