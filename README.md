# 🔔 Nhắc Hạn Trello (Trello to Telegram Due Tasks Notifier)

Hệ thống tự động quét các thẻ (card) trên Trello có hạn chót (due date), phát hiện các công việc **sắp hết hạn** hoặc **đã quá hạn** và gửi thông báo cảnh báo tức thì về nhóm/kênh hoặc tin nhắn riêng trên **Telegram** thông qua Bot.

---

## 🌟 Tính Năng Nổi Bật

- 📊 **Lệnh phân tích & Xếp hạng thành viên (`/phantich`):**
  - Thống kê ai gánh nhiều task nhất trong nhóm.
  - Tỉ lệ số task chưa hoàn thành trên tổng số task được giao (ví dụ: `69 / 149 (46.3%)`).
  - Đếm số lượng task quá hạn của từng thành viên.
  - Tự động xếp hạng (🥇, 🥈, 🥉) và đánh giá danh hiệu (Xuất sắc, Tốt, Quá tải, Cần hỗ trợ).
  - *Chỉ gửi về chat riêng của Admin (`@nguyenvanuy`).*
- 📌 **Lệnh liệt kê task chưa giao (`/chuagiao`):**
  - Tự động lọc các thẻ chưa gán người phụ trách, chưa có nhãn (label) và chưa có deadline.
  - Trả về danh sách link trực tiếp kèm format `[chưa có người thực hiện ....]`.
  - Phân nhóm rõ ràng theo từng Bảng Trello.
  - *Chỉ gửi về chat riêng của Admin (`@nguyenvanuy`).*
- 🤖 **Tương tác trực tiếp trên Telegram:**
  - Nhắn tin `/phantich` hoặc `/chuagiao` vào chat riêng với bot để nhận báo cáo.
  - Chỉ duy nhất Admin `@nguyenvanuy` mới có quyền thực thi lệnh bot.
  - Nhóm chung không bị ảnh hưởng hay spam lệnh.
- ⏰ **Cảnh báo trước khi hết hạn:** Tự động phát hiện các task sắp đến hạn theo ngưỡng thời gian cấu hình (mặc định 24 giờ).
- 🚨 **Cảnh báo task quá hạn:** Nhắc nhở các việc đã trễ hạn để kịp thời xử lý (gửi vào nhóm chung).
- ☁️ **Deploy Cloud 24/7 với GitHub Actions:** Tự động gửi cảnh báo hàng ngày vào lúc 16:00 chiều mà không cần bật máy tính.
- 🛡️ **Cơ chế chống spam thông minh (Deduplication):**
  - Không gửi tin nhắn lặp lại liên tục cho cùng một thẻ trong mỗi chu kỳ quét.
  - Tự động nhắc lại sau một khoảng thời gian quy định (ví dụ: mỗi 12 giờ) nếu task vẫn chưa hoàn thành.
  - Tự động phát hiện và gửi lại ngay nếu người dùng đổi hạn chót hoặc task chuyển trạng thái từ "sắp hạn" sang "quá hạn".
- 📱 **Tin nhắn Telegram trực quan, chi tiết:**
  - Tên thẻ kèm liên kết mở trực tiếp trên Trello.
  - Bảng (Board) và Danh sách (List) tương ứng (VD: To Do, Doing, Review).
  - Người phụ trách (Assignees) & Nhãn công việc (Labels).
  - Thời gian còn lại hoặc thời gian đã trễ hạn tính theo múi giờ Việt Nam.

---

## 📁 Cấu Trúc Dự Án

```
NhachanTrello/
├── .github/workflows/
│   ├── daily_alert.yml     # GitHub Actions: Tự động gửi cảnh báo 16:00 VN hàng ngày
│   ├── phantich.yml        # GitHub Actions: Kích hoạt xuất báo cáo phân tích
│   └── chuagiao.yml        # GitHub Actions: Kích hoạt xuất danh sách task chưa giao
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
│   ├── notifier.py         # Bộ máy quét thẻ và xử lý cảnh báo quá hạn
│   ├── analytics.py        # Phân tích KPI thành viên & quét task chưa giao
│   └── bot_listener.py     # Lắng nghe & phản hồi lệnh Telegram từ Admin
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
 5. Chạy thường trực kiểm tra định kỳ & lắng nghe lệnh Telegram (--daemon)
 6. Xuất báo cáo phân tích khối lượng & xếp hạng thành viên (--phantich)
 7. Xuất danh sách link các task chưa giao / chưa gán người (--chuagiao)
 8. Gán tài khoản Uy Nguyễn vào các task chưa giao (--assign-chuagiao)
 9. Cài đặt lại thư viện (pip install)
 0. Thoát
```

### Cách 2: Sử dụng dòng lệnh Python

#### 1. Kiểm tra kết nối:
```powershell
.\venv\Scripts\python.exe main.py --test
```

#### 2. Xem danh sách Bảng & Lấy Board ID:
```powershell
.\venv\Scripts\python.exe main.py --list-boards
```

#### 3. Báo cáo phân tích khối lượng & xếp hạng thành viên:
```powershell
.\venv\Scripts\python.exe main.py --phantich
```
*Gửi trực tiếp bảng phân tích, xếp hạng 🥇, 🥈, 🥉 và task quá hạn vào Telegram cá nhân của Admin.*

#### 4. Danh sách task chưa gán người phụ trách:
```powershell
.\venv\Scripts\python.exe main.py --chuagiao
```
*Gửi danh sách thẻ chưa giao (không người, không label, không deadline) kèm link dạng `[chưa có người thực hiện ....]` về Telegram Admin.*

#### 5. Gán tài khoản Uy Nguyễn vào các task chưa giao:
```powershell
.\venv\Scripts\python.exe main.py --assign-chuagiao
```
*Tự động gán Uy Nguyễn vào các task chưa có người + chưa có nhãn + chưa có hạn.*

#### 6. Quét và gửi cảnh báo 1 lần vào nhóm chung:
```powershell
.\venv\Scripts\python.exe main.py --once
```

#### 7. Chạy thường trực định kỳ & Lắng nghe lệnh Telegram:
```powershell
.\venv\Scripts\python.exe main.py --daemon
```

---

## ☁️ Triển Khai Chạy Hoàn Toàn Trên GitHub Actions (Không Cần Bật Máy Tính)

Dự án đã được tích hợp sẵn 4 Workflows trên GitHub Actions:
1. **Daily Trello Due Alert (`daily_alert.yml`):** Tự động kích hoạt hàng ngày vào lúc **16:00 (giờ Việt Nam)** để quét và gửi cảnh báo vào nhóm chung.
2. **Trello Workload Analytics (`phantich.yml`):** Kích hoạt thủ công khi cần gửi báo cáo phân tích về chat riêng của Admin.
3. **Trello Unassigned Tasks Report (`chuagiao.yml`):** Kích hoạt thủ công khi cần gửi danh sách task chưa giao về chat riêng của Admin.
4. **Trello Assign Uy Nguyễn (`assign_chuagiao.yml`):** Kích hoạt thủ công khi cần tự động gán Uy Nguyễn vào các task chưa giao.

### Cấu hình Secrets trên GitHub:
Vào GitHub Repository -> **Settings** -> **Secrets and variables** -> **Actions** -> Chọn **New repository secret**:
- `TRELLO_API_KEY`: Key Trello của bạn
- `TRELLO_TOKEN`: Token Trello của bạn
- `TELEGRAM_BOT_TOKEN`: Token của Telegram Bot
- `TELEGRAM_GROUP_CHAT_ID`: Chat ID nhóm chung nhận cảnh báo quá hạn (VD: `-1004404557034`)
- `TELEGRAM_ADMIN_CHAT_ID`: Chat ID riêng của Admin nhận phân tích (VD: `851630770`)
- `ADMIN_USERNAMES`: `nguyenvanuy`
- `HOURS_BEFORE_DUE`: `24`
- `MAX_OVERDUE_HOURS`: `0`

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
