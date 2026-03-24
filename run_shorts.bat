@echo off
title YouTube Shorts Bot
cd /d <FOLDER_PATH_TO_SCRIPT>

echo ============================================
echo   YouTube Shorts Bot Starting...
echo   Time: %date% %time%
echo ============================================

:: Make sure Ollama is running
start /min ollama serve

:: Wait 5 seconds for Ollama to start
timeout /t 5 /nobreak > nul

:: Run the scheduler
python scheduler.py

echo ============================================
echo   Done! Check scheduler.log for details.
echo ============================================
