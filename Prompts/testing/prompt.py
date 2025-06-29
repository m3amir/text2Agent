arguments_prompt = """
You need to call the {tool_name} tool for testing purposes.

Tool Description: {tool_description}

Testing Question: {tool_question}

Available configuration:
- User email: {user_email}
- Recipient email: {recipient}  
- Today's date: {today}

CRITICAL CONTEXT FROM PREVIOUS TOOLS:
{previous_context}

Generate appropriate test arguments that address the testing question and are based on the tool's description. The tool's own documentation will guide you on proper usage. Use realistic values that would properly test the tool's functionality in the context of the testing question.

CRITICAL: If previous tool results are available above, use them as context for generating arguments:
- If a search tool returned file IDs, use those EXACT file IDs instead of making up fake ones
- If a tool returned drive names or other identifiers, use those actual values  
- Look for "🎯 IMPORTANT" markers in the context - these contain critical values to use
- Build upon the previous results to create a realistic workflow
- NEVER EVER make up file IDs when real ones are provided

For email tools, use the provided user_email and recipient appropriately.

Call the {tool_name} tool now with appropriate arguments.

"""

tool_question_prompt = """
Given this task description: "{task_description}"

And this tool: {tool_name}
Tool Description: {tool_description}

Generate a specific testing question that relates the task to this tool's functionality. The question should guide what arguments and scenarios should be tested for this tool in the context of the given task.

For example:
- If task is about "latest product XYZ" and tool is "search_files", question might be: "Does the search tool correctly find files related to product XYZ?"
- If task is about "customer support" and tool is "send_email", question might be: "Can the email tool send appropriate customer support responses?"

Generate ONE specific, actionable testing question for this tool and task combination:
"""

focus_prompt = """
Task: {task_description}
Tool: {tool_name}
Tool Description: {tool_description}

Generate a single, specific testing question for this tool in the context of the given task. 
Output ONLY the question itself, no commentary, explanations, or additional scenarios.
The question should be actionable and directly test the tool's functionality for the task.
"""

analysis_prompt = """
Analyze whether the following question was adequately answered by the tool result.

QUESTION: {question}

TOOL RESULT: {result}

Determine:
1. Was the question answered? (Yes/No)
2. Provide a brief explanation of why or why not
3. What specific information from the result addresses the question (if any)

Output your response in this exact JSON format:
{{
    "question_answered": true/false,
    "explanation": "Brief explanation of why the question was or wasn't answered",
    "relevant_information": "Specific information from the result that addresses the question, or 'None' if not answered"
}}

Only output valid JSON, nothing else.
"""