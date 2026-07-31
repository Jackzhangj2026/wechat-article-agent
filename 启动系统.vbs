' WeChat Article Agent - 完全静默启动（双击运行，无任何窗口）
' 如果杀毒软件弹窗，请选择"允许运行"

Dim shell
Set shell = CreateObject("WScript.Shell")

' 启动后端（完全隐藏）
shell.Run "powershell -WindowStyle Hidden -NoExit -Command cd """ & _
  CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & _
  "\backend""; uvicorn main:app --reload --port 8001", 0, False

' 等待3秒
WScript.Sleep 3000

' 启动前端（完全隐藏）
shell.Run "powershell -WindowStyle Hidden -NoExit -Command cd """ & _
  CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & _
  "\frontend""; npx http-server . -p 5173 -c-1 --cors", 0, False

' 打开浏览器
WScript.Sleep 1000
shell.Run "http://localhost:5173"

Set shell = Nothing