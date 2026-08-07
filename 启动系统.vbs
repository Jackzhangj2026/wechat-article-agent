' WeChat Article Agent - 完全静默启动（双击运行，无任何窗口）
' 如果杀毒软件弹窗，请选择"允许运行"

Dim shell, fso, root, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)

' 启动后端（完全隐藏，使用单引号避免路径空格问题）
cmd = "powershell -WindowStyle Hidden -NoExit -Command ""& { cd '" & root & "\backend'; uvicorn main:app --reload --port 8001 }"""
shell.Run cmd, 0, False

' 等待3秒
WScript.Sleep 3000

' 启动前端（完全隐藏）
cmd = "powershell -WindowStyle Hidden -NoExit -Command ""& { cd '" & root & "\frontend'; npx http-server . -p 5173 -c-1 --cors }"""
shell.Run cmd, 0, False

' 打开浏览器
WScript.Sleep 1000
shell.Run "http://localhost:5173"

Set shell = Nothing
Set fso = Nothing