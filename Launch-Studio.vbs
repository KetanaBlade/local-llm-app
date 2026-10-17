Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
strDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strDir

' Check if pythonw exists, otherwise fallback to python
Dim pythonCmd
pythonCmd = "pythonw launcher.py"
WshShell.Run pythonCmd, 0, False
