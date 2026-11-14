Option Explicit
Dim shell, files, folder, python, command
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
folder = files.GetParentFolderName(WScript.ScriptFullName)
python = files.BuildPath(files.GetParentFolderName(folder), ".venv\Scripts\pythonw.exe")
If Not files.FileExists(python) Then python = "pythonw.exe"
shell.CurrentDirectory = folder
command = Chr(34) & python & Chr(34) & " " & Chr(34) & files.BuildPath(folder, "start_workbench.py") & Chr(34)
shell.Run command, 0, False
