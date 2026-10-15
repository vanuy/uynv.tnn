import sys
import time
import argparse
import threading
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
from src.analytics import TrelloAnalytics
from src.bot_listener import TelegramBotListener


def parse_args():
    parser = argparse.ArgumentParser(
        description="Trello to Telegram Due Tasks Alert Bot - Gửi cảnh báo & Phân tích tiến độ Trello",
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
        "--phantich",
        action="store_true",
        help="Phân tích khối lượng công việc, tỉ lệ hoàn thành và xếp hạng thành viên",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Chạy quét cảnh báo 1 lần duy nhất rồi thoát (phù hợp cho Task Scheduler)",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Chạy thường trực: tự động quét định kỳ VÀ lắng nghe lệnh Telegram (/phantich, /quet)",
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


def handle_phantich(analytics: TrelloAnalytics, telegram: TelegramClient, dry_run: bool = False):
    print("=" * 60)
    print("📊 BẮT ĐẦU PHÂN TÍCH TIẾN ĐỘ & XẾP HẠNG THÀNH VIÊN TRELLO")
    print("=" * 60)
    data = analytics.analyze()
    messages = analytics.format_report_html(data)

    for msg in messages:
        if dry_run:
            print("\n" + msg)
        else:
            res = telegram.send_message(msg)
            if res.get("success"):
                print("✅ Đã gửi báo cáo phân tích thành công tới Telegram!")
            else:
                print(f"❌ Lỗi khi gửi báo cáo: {res.get('error')}")


def run_daemon_mode(notifier: Notifier, listener: TelegramBotListener, dry_run: bool = False):
    print("=" * 60)
    print("🚀 BẮT ĐẦU CHẠY THƯỜNG TRỰC (DAEMON + TELEGRAM LISTENER)")
    print(f"   • Tần suất quét hạn chót: mỗi {Config.CHECK_INTERVAL_MINUTES} phút")
    print("   • Đang lắng nghe lệnh Telegram: /phantich, /quet, /help")
    print("   • Nhấn Ctrl+C để dừng chương trình bất cứ lúc nào.")
    print("=" * 60)

    stop_event = threading.Event()
    interval_secs = max(60, Config.CHECK_INTERVAL_MINUTES * 60)

    def periodic_scanner():
        last_triggered_date = None
        daily_time = Config.DAILY_ALERT_TIME.strip()  # e.g. "16:00"

        if daily_time:
            print(f"⏰ [Lịch cố định] Đã bật chế độ gửi cảnh báo đúng {daily_time} hàng ngày.")
        else:
            # Run first scan immediately if interval mode
            try:
                notifier.scan_and_alert(dry_run=dry_run)
            except Exception as e:
                print(f"[Scanner] Lỗi quét lần đầu: {e}")

        while not stop_event.is_set():
            if daily_time:
                # Check every 30 seconds for daily time match
                if stop_event.wait(timeout=30):
                    break
                now_local = datetime.now(notifier.tz)
                cur_hm = now_local.strftime("%H:%M")
                cur_date = now_local.strftime("%Y-%m-%d")

                if cur_hm == daily_time and last_triggered_date != cur_date:
                    print(f"\n🔔 Đúng {daily_time}! Bắt đầu kích hoạt gửi cảnh báo công việc...")
                    try:
                        notifier.scan_and_alert(dry_run=dry_run)
                        last_triggered_date = cur_date
                    except Exception as e:
                        print(f"[Scanner] Lỗi quét vào lúc {daily_time}: {e}")
            else:
                # Interval mode
                if stop_event.wait(timeout=interval_secs):
                    break
                try:
                    notifier.scan_and_alert(dry_run=dry_run)
                except Exception as e:
                    print(f"[Scanner] Lỗi quét định kỳ: {e}")

    # Start periodic scanner thread
    scan_thread = threading.Thread(target=periodic_scanner, daemon=True)
    scan_thread.start()

    # Start Telegram listener in main thread
    try:
        listener.start_polling(stop_event=stop_event)
    except KeyboardInterrupt:
        print("\n🛑 Nhận tín hiệu dừng từ người dùng...")
    finally:
        stop_event.set()
        listener.stop()
        print("✅ Đã dừng an toàn tất cả các tiến trình.")


def main():
    args = parse_args()

    # If no flags provided, default to --once
    if not (args.test or args.list_boards or args.phantich or args.daemon or args.once or args.dry_run):
        args.once = True

    # Validate config
    try:
        if args.list_boards or args.dry_run:
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
    analytics = TrelloAnalytics(Config, trello, telegram)
    listener = TelegramBotListener(Config, trello, telegram, notifier, analytics)

    if args.test:
        handle_test(trello, telegram)
        return

    if args.list_boards:
        handle_list_boards(trello)
        return

    if args.phantich:
        handle_phantich(analytics, telegram, dry_run=args.dry_run)
        return

    if args.daemon:
        run_daemon_mode(notifier, listener, dry_run=args.dry_run)
    else:
        # Run once mode
        notifier.scan_and_alert(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
