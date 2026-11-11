Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = root
command = "node.exe """ & root & "\server\launch.mjs"""
If WScript.Arguments.Named.Exists("no-browser") Then command = command & " --no-browser"
shell.Run command, 0, False
