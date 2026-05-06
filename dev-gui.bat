@echo off
REM 작업대 개발 빌드 실행 — 코드 수정하고 다시 더블클릭하면 즉시 반영.
REM 콘솔 창에 logger 출력이 같이 뜨니 디버깅하기 좋아요.
REM
REM 조용히 띄우고 싶으면 바탕화면의 "작업대 (개발).lnk" 사용하세요.

cd /d "%~dp0"
".venv\Scripts\python.exe" -m keymacro gui
pause
