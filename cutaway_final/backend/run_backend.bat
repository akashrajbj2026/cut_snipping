@echo off
cd /d "%~dp0"
if not exist venv (
  python -m venv venv
  call venv\Scripts\activate
  python -m pip install --upgrade pip
  pip install -r requirements.txt
) else (
  call venv\Scripts\activate
)
if not exist .env copy .env.example .env
echo.
echo  Open http://127.0.0.1:8000 in your browser
echo.
uvicorn main:app --reload --port 8000
