arguments_prompt = """
You need to call the {tool_name} tool for testing purposes.

Tool Description: {tool_description}

Tool Schema: {tool_schema}

Testing Question: {tool_question}

Available configuration:
- User email: {user_email}
- Recipient email: {recipient}
- Today's date: {today}

Generate appropriate test arguments that address the testing question and are based on the tool's description and schema requirements. The tool's own documentation will guide you on proper usage. Use realistic values that would properly test the tool's functionality in the context of the testing question.

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