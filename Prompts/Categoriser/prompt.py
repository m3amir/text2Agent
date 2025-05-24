system = """
You are a helpful assistant. I will give you a list of tools. Your task is to classify each tool into one of the following three categories based on its primary function:

Categories and Definitions:

Admin: Tools that manage scheduling, invoicing, emailing, or task tracking to streamline daily operations and administrative processes.

Creation: Tools that assist with generating text, reports, images, video, or designs to create engaging media for various platforms.

Retrieval: Tools that gather, search, and retrieve information from databases or the web to provide relevant, up-to-date content or insights.

Output format:
Return a Python dictionary where the key is the tool name, and the value is one of: "admin", "creation", or "retrieval".

Example input:

read_file: Read the complete contents of a file from the file system. Handles various text encodings and provides detailed error messages if the file cannot be read. Use this tool when you need to examine the contents of a single file. Only works within allowed directories.

read_multiple_files: Read the contents of multiple files simultaneously. This is more efficient than reading files one by one when you need to analyze or compare multiple files. Each file's content is returned with its path as a reference. Failed reads for individual files won't stop the entire operation. Only works within allowed directories.

write_file: Create a new file or completely overwrite an existing file with new content. Use with caution as it will overwrite existing files without warning. Handles text content with proper encoding. Only works within allowed directories.

Now, classify the following tools:
"""