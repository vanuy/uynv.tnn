@echo off
chcp 65001 > nul
setlocal

cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [!] Đang tạo môi trường ảo Python venv...
    python -m venv venv
    if errorlevel 1 (
        echo [X] Lỗi: Không tìm thấy Python. Vui lòng cài đặt Python 3.9+ trước.
        pause
        exit /b 1
    )
    echo [!] Đang cài đặt thư viện cần thiết...
    .\venv\Scripts\python.exe -m pip install -r requirements.txt
)

if "%~1"=="" goto menu
.\venv\Scripts\python.exe main.py %*
goto end

:menu
cls
echo ========================================================
echo        HỆ THỐNG CẢNH BÁO HẠN CHÓT TRELLO QUA TELEGRAM
echo ========================================================
echo.
echo  1. Kiểm tra kết nối Trello và Telegram (--test)
echo  2. Xem danh sách các bảng Trello để lấy ID (--list-boards)
echo  3. Quét và gửi cảnh báo 1 lần (--once)
echo  4. Quét thử nghiệm không gửi tin (--dry-run)
echo  5. Chạy thường trực kiểm tra định kỳ & lắng nghe lệnh Telegram (--daemon)
echo  6. Xuất báo cáo phân tích khối lượng & xếp hạng thành viên (--phantich)
echo  7. Xuất danh sách link các task chưa giao / chưa gán người (--chuagiao)
echo  8. Gán tài khoản Uy Nguyễn vào các task chưa giao (--assign-chuagiao)
echo  9. Cài đặt lại thư viện (pip install)
echo  0. Thoát
echo.
set /p opt="Vui lòng chọn chức năng (0-9): "

if "%opt%"=="1" (
    .\venv\Scripts\python.exe main.py --test
    pause
    goto menu
)
if "%opt%"=="2" (
    .\venv\Scripts\python.exe main.py --list-boards
    pause
    goto menu
)
if "%opt%"=="3" (
    .\venv\Scripts\python.exe main.py --once
    pause
    goto menu
)
if "%opt%"=="4" (
    .\venv\Scripts\python.exe main.py --dry-run
    pause
    goto menu
)
if "%opt%"=="5" (
    .\venv\Scripts\python.exe main.py --daemon
    pause
    goto menu
)
if "%opt%"=="6" (
    .\venv\Scripts\python.exe main.py --phantich
    pause
    goto menu
)
if "%opt%"=="7" (
    .\venv\Scripts\python.exe main.py --chuagiao
    pause
    goto menu
)
if "%opt%"=="8" (
    .\venv\Scripts\python.exe main.py --assign-chuagiao
    pause
    goto menu
)
if "%opt%"=="9" (
    .\venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    goto menu
)
if "%opt%"=="0" goto end

:end
