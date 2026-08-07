' WeChat Article Agent - 完全静默启动（一个端口搞定前后端）
' 启动后自动打开 http://localhost:8001 ，一个端口全部搞定

Dim shell, fso, root, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)

' 启动后端（完全隐藏）
cmd = "powershell -WindowStyle Hidden -NoExit -Command ""& { cd '" & root & "\backend'; uvicorn main:app --reload --port 8001 }"""
shell.Run cmd, 0, False

' 等待5秒后端启动
WScript.Sleep 5000

' 打开浏览器
shell.Run "http://localhost:8001/"

Set shell = Nothing
Set fso = Nothing