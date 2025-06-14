pdf_prompt = """
You need to generate a PDF report. Use the {tool_name} tool for: {task}{context}

CRITICAL: PDF report tools require 'report_content' parameter with text content. To include charts, use placeholder format {{chart_name}} NOT markdown syntax.

For pdf_generate_report:
- report_content: Text content with sections and chart placeholders
- title: Report title  
- author: Report author
- include_header: true/false
- include_footer: true/false

IMPORTANT: To include charts in the report, use simple chart placeholders like {{bar_chart}} or {{pie_chart}} that will match any chart of that type. Do NOT use markdown ![](path) syntax.

Example report_content:
"# Executive Summary\\n\\nThis report analyzes quarterly sales performance...\\n\\n## Chart Analysis\\n\\n{{bar_chart}}\\n\\nThe chart above shows sales trends...\\n\\n## Conclusions\\n\\nBased on the analysis..."

Call the {tool_name} tool with proper arguments including 'report_content', 'title', and chart placeholders in {{}} format.
"""

chart_prompt = """
You need to generate a chart. Use the {tool_name} tool for: {task}{context}

CRITICAL: Chart tools require a data parameter with a list of dictionaries. Use the provided {data} as input.

Call the {tool_name} tool with proper arguments, including data, title, and appropriate labels.
"""