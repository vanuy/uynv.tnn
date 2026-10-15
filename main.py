import sys
import time
import argparse
from datetime import datetime

# Configure Windows console UTF-8 output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from src.config import Config
from src.state_manager import StateManager
from src.trello_client import TrelloClient
from src.telegram_client import TelegramClient
from src.notifier import Notifier


def parse_args():
    parser = argparse.ArgumentParser(
        description="Trello to Telegram Due Tasks Alert Bot - Gửi cảnh báo task Trello sắp hết hạn về Telegram",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Kiểm tra kết nối tới Trello API và Telegram Bot API (gửi tin nhắn test)",
    )
    parser.add_argument(
        "--list-boards",
        action="store_true",
        help="Hiển thị danh sách tất cả các bảng Trello để lấy ID cấu hình",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Chạy quét 1 lần duy nhất rồi thoát (phù hợp cho Task Scheduler / Cron job)",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Chạy thường trực nền (lặp lại định kỳ theo CHECK_INTERVAL_MINUTES)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ quét và in kết quả ra màn hình console, không gửi tin nhắn Telegram",
    )
    return parser.parse_args()


def handle_test(trello: TrelloClient, telegram: TelegramClient):
    print("=" * 60)
    print("🧪 KIỂM TRA KẾT NỐI HỆ THỐNG")
    print("=" * 60)

    # 1. Test Trello
    print("\n[1/2] Đang kiểm tra kết nối Trello...")
    trello_res = trello.test_connection()
    if trello_res.get("success"):
        print(f"  ✅ Kết nối Trello thành công!")
        print(f"     - Tên người dùng: {trello_res.get('fullName')} (@{trello_res.get('username')})")
    else:
        print(f"  ❌ Kết nối Trello thất bại: {trello_res.get('error')}")

    # 2. Test Telegram
    print("\n[2/2] Đang kiểm tra kết nối Telegram...")
    tele_res = telegram.test_connection()
    if tele_res.get("success"):
        print(f"  ✅ Kết nối Telegram thành công!")
        print(f"     - Tên Bot: {tele_res.get('bot_name')} (@{tele_res.get('bot_username')})")
        print(f"     - Đã gửi 1 tin nhắn kiểm tra tới Chat ID: {Config.TELEGRAM_CHAT_ID}")
    else:
        print(f"  ❌ Kết nối Telegram thất bại: {tele_res.get('error')}")

    print("\n" + "=" * 60)


def handle_list_boards(trello: TrelloClient):
    print("=" * 60)
    print("📋 DANH SÁCH BẢNG TRELLO CỦA BẠN")
    print("=" * 60)
    try:
        boards = trello.get_my_boards()
        if not boards:
            print("Không tìm thấy bảng Trello nào đang mở.")
            return

        print(f"Tìm thấy {len(boards)} bảng:\n")
        print(f"{'STT':<5} | {'TÊN BẢNG':<35} | {'BOARD ID'}")
        print("-" * 75)
        for idx, b in enumerate(boards, start=1):
            print(f"{idx:<5} | {b['name'][:33]:<35} | {b['id']}")

        print("-" * 75)
        print("💡 Mẹo: Sao chép các BOARD ID bạn muốn theo dõi vào biến TRELLO_BOARD_IDS trong file .env")
        print("        Nếu muốn theo dõi TẤT CẢ các bảng, chỉ cần để trống TRELLO_BOARD_IDS.")
    except Exception as e:
        print(f"❌ Lỗi khi lấy danh sách bảng: {e}")
    print("=" * 60)


def main():
    args = parse_args()

    # If no flags provided, default to --once
    if not (args.test or args.list_boards or args.daemon or args.once or args.dry_run):
        args.once = True

    # Validate config
    try:
        if args.list_boards:
            Config.validate(check_trello=True, check_telegram=False)
        elif args.dry_run:
            Config.validate(check_trello=True, check_telegram=False)
        else:
            Config.validate(check_trello=True, check_telegram=True)
    except ValueError as e:
        print(e)
        sys.exit(1)

    trello = TrelloClient(Config.TRELLO_API_KEY, Config.TRELLO_TOKEN)
    telegram = TelegramClient(Config.TELEGRAM_BOT_TOKEN, Config.TELEGRAM_CHAT_ID)
    state_mgr = StateManager(Config.STATE_FILE)
    notifier = Notifier(Config, trello, telegram, state_mgr)

    if args.test:
        handle_test(trello, telegram)
        return

    if args.list_boards:
        handle_list_boards(trello)
        return

    if args.daemon:
        interval_secs = max(60, Config.CHECK_INTERVAL_MINUTES * 60)
        print("=" * 60)
        print(f"🚀 BẮT ĐẦU CHẠY CHẾ ĐỘ NỀN (DAEMON)")
        print(f"   - Tần suất kiểm tra: mỗi {Config.CHECK_INTERVAL_MINUTES} phút")
        print(f"   - Nhấn Ctrl+C để dừng chương trình bất cứ lúc nào.")
        print("=" * 60)

        while True:
            try:
                notifier.scan_and_alert(dry_run=args.dry_run)
                print(f"💤 Tạm nghỉ {Config.CHECK_INTERVAL_MINUTES} phút trước lần quét tiếp theo...")
                time.sleep(interval_secs)
            except KeyboardInterrupt:
                print("\n🛑 Đã nhận tín hiệu dừng từ người dùng. Thoát chương trình.")
                break
            except Exception as e:
                print(f"❌ Đã xảy ra lỗi không mong muốn trong chu kỳ quét: {e}")
                print(f"Đợi 1 phút trước khi thử lại...")
                time.sleep(60)
    else:
        # Run once mode
        notifier.scan_and_alert(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
