#!/bin/bash
cd /Users/pro/Desktop/attendance_system
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
