@echo off
REM ============================================================
REM Start Hysteria2 SOCKS5 proxy
REM Config: config.yaml (same directory)
REM Proxy:  socks5://127.0.0.1:1080
REM ============================================================
cd /d "%~dp0"
echo [INFO] Starting Hysteria2 proxy...
echo [INFO] Binary: %~dp0hysteria-windows-amd64.exe
echo [INFO] Config: %~dp0config.yaml
echo [INFO] Proxy:  socks5://127.0.0.1:1080
echo.
echo [INFO] Press Ctrl+C to stop the proxy.
echo.
"%~dp0hysteria-windows-amd64.exe" client -c "%~dp0config.yaml"
if %errorlevel% neq 0 (
    echo [ERROR] Hysteria2 exited with code %errorlevel%
    pause
)
