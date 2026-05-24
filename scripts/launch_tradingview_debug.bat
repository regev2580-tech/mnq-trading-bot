@echo off
echo סוגר TradingView...
taskkill /F /IM TradingView.exe >nul 2>&1
timeout /t 3 /nobreak >nul

echo פותח TradingView עם debug mode...
start "" "C:\Program Files\WindowsApps\TradingView.Desktop_3.1.0.7818_x64__n534cwy3pjxzj\TradingView.exe" --remote-debugging-port=9222

echo ממתין לטעינה...
timeout /t 8 /nobreak >nul

echo בודק חיבור...
curl -s http://localhost:9222/json/version
echo.
echo מוכן!
