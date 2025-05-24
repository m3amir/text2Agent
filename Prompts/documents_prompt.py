system_folder = """You need to find the next most probable folder to search in to get the information you need to complete a task. 
The information or file you seek is called {file_name}."""

human_folder = """The current folders you have access to are {folder_names}.
Only output the name of the folder you think is the next best place to search and nothing else. 
Only use the names in the folders list."""

system_file = """
You need to find the most relevant files to retrieve in order for you to complete a specific task, outlined below. Pay attention to the file names
as these could give hints as to the files you need to retrieve.
You have information regarding the task you need to complete and a list of documents."""

human_file = """
The task you need to complete is : {task}. 
Only output files within the files list. Output the names of the files that are most relevent to complete the task and nothing else. 
If you cant find relevant files in the list, output "I cant find the file I need".
You can output multiple files in a valid python list.

The following files were found in the {folder} folder.

The files are: {file_names}

Relevant files:
"""

system_done = """

Your task is to identify the most relevant files based on the provided task description. Use the given folders and files as context to make your selection.

Instructions:

Output the files you find most relevant to the task description in a single JSON object.
Carefully evaluate the task description to ensure a strong link of relevancy between the files you chose and the task description.
Pay attention to the folder directory structure, as there may be other directories at the same level that could contain relevant files.
Decide whether the current files are sufficient or if additional files might be more relevant.
Important:

Do not output multiple JSON objects.
Output the files you believe to be most relevent to the task description. If you believe there are no files relevent then simply output a empty list.

If you believe the current files are not relevant, or if there may be other directories or files at the same level that could yield better results, choose to continue examining new files by outputting True for continue.
Output Requirements:

After selecting the relevant files, you must output a single JSON object in the following format:

{
    "folders": [
        {
            "folder_name": "folder_name1",
            "files": ["file1", "file2", "file3"]
        },
        {
            "folder_name": "folder_name2",
            "files": ["file1_name", "file2_name", "file3_name"]
        }
    ],
    "continue": "true" or "false"
}

Folders Array: There should only be one array of folders. Each folder entry includes its name and an array of relevant files within that folder.
Continue:
Output "True" if you believe that additional files (not currently observed) may be more relevant, or if there are other directories at the same level that should be searched.
Output "False" if you are confident that you have found all the files most relevant to the task.
Note: The JSON should be correctly formatted, with no additional commentary or explanation. Only one JSON object should be output, which you should update as you continue to find relevant files.
"""

human_done = """
The task description is: {task_description}
The files are: {file_names}

"""