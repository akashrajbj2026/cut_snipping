#!/usr/bin/env bash
cd "$(dirname "$0")"
if [ ! -d venv ]; then
  python3 -m venv venv
  source venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
else
  source venv/bin/activate
fi
[ -f .env ] || cp .env.example .env
echo
echo " Open http://127.0.0.1:8000 in your browser"
echo
uvicorn main:app --reload --port 8000
