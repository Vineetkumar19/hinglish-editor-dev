Option Explicit
Dim sh, fs, py, app, req, i, ready
Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
py = "D:\Full Drive\remove silence\.venv\Scripts\pythonw.exe"
app = "D:\Workflow_Automation\gaming-meme-inbox\app.py"
sh.Run Chr(34) & py & Chr(34) & " -X utf8 " & Chr(34) & app & Chr(34), 0, False
If WScript.Arguments.Count = 0 Then
 ready = False
 For i = 1 To 25
  On Error Resume Next
  Set req = CreateObject("MSXML2.XMLHTTP")
  req.open "GET", "http://127.0.0.1:8880/health", False
  req.send
  If Err.Number = 0 Then
   If req.status = 200 Then ready = True
  End If
  Err.Clear
  On Error GoTo 0
  If ready Then Exit For
  WScript.Sleep 400
 Next
 sh.Run "http://127.0.0.1:8880/", 1, False
End If
