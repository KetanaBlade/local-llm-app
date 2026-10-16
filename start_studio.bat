@echo off
title Local AI Studio — Antigravity Workstation
echo ============================================================================
echo   LOCAL AI STUDIO — 100%% ON-DEVICE WORKSTATION
echo   Desktop (NVIDIA CUDA) ^& Laptop (Intel Core Ultra 258V Arc + NPU) Ready
echo ============================================================================
echo.
cd /d "%~dp0"
start "" "http://localhost:8000"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
pause
