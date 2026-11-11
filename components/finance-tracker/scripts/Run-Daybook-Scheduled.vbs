Option Explicit
Dim shell, fs, node, script, mode
If WScript.Arguments.Count <> 2 Then WScript.Quit 2
node = WScript.Arguments(0)
mode = WScript.Arguments(1)
Set fs = CreateObject("Scripting.FileSystemObject")
If Not fs.FileExists(node) Then WScript.Quit 2
If mode = "bootstrap" Or mode = "worker" Then
    script = fs.BuildPath(fs.GetParentFolderName(fs.GetParentFolderName(WScript.ScriptFullName)), "server\" & mode & ".mjs")
Else
    WScript.Quit 2
End If
If Not fs.FileExists(script) Then WScript.Quit 2
Set shell = CreateObject("WScript.Shell")
WScript.Quit shell.Run("""" & node & """ """ & script & """", 0, True)
