# 🔔 Nhắc Hạn Trello (Trello to Telegram Due Tasks Notifier)

Hệ thống tự động quét các thẻ (card) trên Trello có hạn chót (due date), phát hiện các công việc **sắp hết hạn** hoặc **đã quá hạn** và gửi thông báo cảnh báo tức thì về nhóm/kênh hoặc tin nhắn riêng trên **Telegram** thông qua Bot.

---

## 🌟 Tính Năng Nổi Bật

- ⏰ **Cảnh báo trước khi hết hạn:** Tự động phát hiện các task sắp đến hạn theo ngưỡng thời gian cấu hình (mặc định 24 giờ).
- 🚨 **Cảnh báo task quá hạn:** Nhắc nhở các việc đã trễ hạn để kịp thời xử lý.
- 🛡️ **Cơ chế chống spam thông minh (Deduplication):**
  - Không gửi tin nhắn lặp lại liên tục cho cùng một thẻ trong mỗi chu kỳ quét.
  - Tự động nhắc lại sau một khoảng thời gian quy định (ví dụ: mỗi 12 giờ) nếu task vẫn chưa hoàn thành.
  - Tự động phát hiện và gửi lại ngay nếu người dùng đổi hạn chót hoặc task chuyển trạng thái từ "sắp hạn" sang "quá hạn".
- 📱 **Tin nhắn Telegram trực quan, chi tiết:**
  - Tên thẻ kèm liên kết mở trực tiếp trên Trello.
  - Bảng (Board) và Danh sách (List) tương ứng (VD: To Do, Doing, Review).
  - Người phụ trách (Assignees) & Nhãn công việc (Labels).
  - Thời gian còn lại hoặc thời gian đã trễ hạn tính theo múi giờ Việt Nam.
- ⚙️ **Linh hoạt & Đa chế độ chạy:**
  - Chạy quét 1 lần (`--once`) phù hợp gắn vào Windows Task Scheduler hoặc Cron Job.
  - Chạy nền thường trực (`--daemon`) tự động lặp lại theo chu kỳ phút.
  - Hỗ trợ kiểm tra kết nối (`--test`), quét giả lập không gửi tin (`--dry-run`), xem ID bảng (`--list-boards`).
  - Menu khởi chạy nhanh trên Windows (`run.bat`).

---

## 📁 Cấu Trúc Dự Án

```
NhachanTrello/
├── .env.example            # File mẫu cấu hình biến môi trường
├── .gitignore              # Bỏ qua file nhạy cảm và cache
├── requirements.txt        # Danh sách thư viện Python
├── README.md               # Hướng dẫn chi tiết
├── run.bat                 # File tiện ích chạy nhanh trên Windows (menu tương tác)
├── main.py                 # File thực thi chính của chương trình
├── src/                    # Mã nguồn các module
│   ├── config.py           # Quản lý & kiểm tra file cấu hình .env
│   ├── trello_client.py    # Giao tiếp với Trello REST API
│   ├── telegram_client.py  # Giao tiếp với Telegram Bot API
│   ├── state_manager.py    # Quản lý trạng thái đã cảnh báo (chống spam)
│   └── notifier.py         # Bộ máy quét thẻ và xử lý cảnh báo
└── tests/
    └── test_all.py         # Kiểm thử tự động (Unit & End-to-end tests)
```

---

## 🔑 Hướng Dẫn Lấy API Key & Token

### 1. Lấy Trello API Key & Token
1. Đăng nhập vào tài khoản Trello trên trình duyệt.
2. Truy cập: [https://trello.com/app-key](https://trello.com/app-key).
3. Tại mục **API Key**, bạn sẽ thấy một chuỗi ký tự (đây là `TRELLO_API_KEY`).
4. Ngay dưới dòng API Key, tìm liên kết **Token** (chữ *Token* có thể bấm được). Nhấn vào đó, chọn **Allow** để cấp quyền.
5. Sao chép chuỗi mã được hiển thị (đây là `TRELLO_TOKEN`).

### 2. Tạo Telegram Bot & Lấy Token
1. Mở Telegram, tìm kiếm bot có tên `@BotFather`.
2. Gửi lệnh `/newbot`.
3. Nhập tên cho bot (ví dụ: `Trello Alert Bot`).
4. Nhập username cho bot (phải kết thúc bằng `bot`, ví dụ: `my_trello_notifier_bot`).
5. `@BotFather` sẽ gửi cho bạn **HTTP API Token** (dạng `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`). Đây là `TELEGRAM_BOT_TOKEN`.

### 3. Lấy Telegram Chat ID
- **Nhận tin nhắn riêng:**
  1. Mở chat với bot bạn vừa tạo và bấm **/start**.
  2. Tìm bot `@userinfobot` trên Telegram và bấm `/start`. Bot này sẽ trả về `Id` tài khoản của bạn (ví dụ: `987654321`).
- **Nhận tin nhắn trong Nhóm (Group):**
  1. Thêm bot vừa tạo vào nhóm chat của bạn.
  2. Cấp quyền gửi tin nhắn cho bot trong nhóm.
  3. Thêm bot `@RawDataBot` vào nhóm, bot sẽ hiển thị thông tin JSON, tìm mục `"chat": { "id": -100xxxxxxxxxx }`. Chuỗi số âm đó là `TELEGRAM_CHAT_ID` của nhóm. (Sau đó có thể xóa RawDataBot ra khỏi nhóm).

---

## ⚙️ Cài Đặt & Cấu Hình

### Bước 1: Tạo file cấu hình `.env`
Sao chép file `.env.example` thành file `.env`:
```powershell
copy .env.example .env
```
Mở file `.env` bằng Notepad hoặc VS Code và điền các thông tin đã lấy ở trên:
```env
TRELLO_API_KEY=điền_trello_api_key
TRELLO_TOKEN=điền_trello_token
TRELLO_BOARD_IDS=  # Để trống nếu muốn quét TẤT CẢ bảng, hoặc điền ID bảng cách nhau bởi dấu phẩy

TELEGRAM_BOT_TOKEN=điền_bot_token_telegram
TELEGRAM_CHAT_ID=điền_chat_id

HOURS_BEFORE_DUE=24       # Cảnh báo task sắp hạn trước 24 giờ
INCLUDE_OVERDUE=true      # Có cảnh báo task đã quá hạn
MAX_OVERDUE_HOURS=72      # Chỉ cảnh báo task trễ trong 3 ngày trở lại
REMIND_INTERVAL_HOURS=12  # Nhắc lại sau mỗi 12 giờ nếu chưa hoàn thành
CHECK_INTERVAL_MINUTES=30 # Tần suất quét định kỳ (phút) khi chạy nền
TIMEZONE=Asia/Ho_Chi_Minh # Múi giờ Việt Nam
SEND_MODE=detailed        # Gửi thẻ chi tiết ("detailed") hoặc tổng hợp ("summary")
```

---

## 🚀 Hướng Dẫn Sử Dụng

### Cách 1: Sử dụng Menu nhanh trên Windows (`run.bat`)
Bạn chỉ cần nhấp đúp chuột vào file **`run.bat`** (hoặc chạy trong terminal `.\run.bat`). Chương trình sẽ tự động cài đặt môi trường và hiển thị menu:
```
========================================================
       HỆ THỐNG CẢNH BÁO HẠN CHÓT TRELLO QUA TELEGRAM
========================================================

 1. Kiểm tra kết nối Trello và Telegram (--test)
 2. Xem danh sách các bảng Trello để lấy ID (--list-boards)
 3. Quét và gửi cảnh báo 1 lần (--once)
 4. Quét thử nghiệm không gửi tin (--dry-run)
 5. Chạy thường trực kiểm tra định kỳ (--daemon)
 6. Cài đặt lại thư viện (pip install)
 0. Thoát
```

### Cách 2: Sử dụng dòng lệnh Python

#### 1. Kiểm tra kết nối:
```powershell
.\venv\Scripts\python.exe main.py --test
```
*Lệnh này sẽ kiểm tra tài khoản Trello và gửi một tin nhắn test đến Telegram của bạn để xác nhận mọi thứ hoạt động.*

#### 2. Xem danh sách Bảng & Lấy Board ID:
```powershell
.\venv\Scripts\python.exe main.py --list-boards
```

#### 3. Chạy thử nghiệm giả lập (Dry Run):
```powershell
.\venv\Scripts\python.exe main.py --dry-run
```
*Quét và in toàn bộ thông báo ra màn hình console, không gửi tới Telegram và không lưu trạng thái.*

#### 4. Quét và gửi cảnh báo 1 lần:
```powershell
.\venv\Scripts\python.exe main.py --once
```

#### 5. Chạy thường trực định kỳ (Daemon mode):
```powershell
.\venv\Scripts\python.exe main.py --daemon
```
*Chương trình sẽ chạy liên tục, tự động quét sau mỗi `CHECK_INTERVAL_MINUTES` phút (mặc định 30 phút).*

---

## ⏰ Hướng Dẫn Cài Đặt Chạy Tự Động Định Kỳ Trên Windows (Windows Task Scheduler)

Nếu không muốn để cửa sổ console chạy liên tục, bạn có thể thiết lập Windows tự động chạy chương trình mỗi 30 phút hoặc 1 giờ:

1. Nhấn tổ hợp phím **Windows + R**, gõ `taskschd.msc` và nhấn **Enter**.
2. Ở cột bên phải, chọn **Create Task...** (Tạo tác vụ mới).
3. Tại tab **General**:
   - Name: `Trello Telegram Notifier`
   - Tích chọn: *Run whether user is logged on or not* (hoặc *Run only when user is logged on*).
4. Tại tab **Triggers**:
   - Nhấn **New...**
   - Begin the task: *On a schedule* -> Chọn *Daily*.
   - Tại mục Advanced settings, tích chọn **Repeat task every**: chọn `30 minutes` (hoặc `1 hour`), for a duration of: `Indefinitely`.
5. Tại tab **Actions**:
   - Nhấn **New...**
   - Action: *Start a program*
   - Program/script: Duyệt tới file `python.exe` trong thư mục venv, ví dụ:
     `E:\AntiGravity\NhachanTrello\venv\Scripts\python.exe`
   - Add arguments: `main.py --once`
   - Start in: Đường dẫn thư mục dự án:
     `E:\AntiGravity\NhachanTrello`
6. Nhấn **OK** để lưu. Từ giờ Windows sẽ tự động chạy quét định kỳ ngầm.

---

## 🧪 Chạy Kiểm Thử Tự Động (Tests)

Để đảm bảo hệ thống hoạt động ổn định và các thuật toán tính giờ, lọc thẻ, định dạng mã hóa HTML không có lỗi:
```powershell
.\venv\Scripts\python.exe -m unittest tests/test_all.py
```
