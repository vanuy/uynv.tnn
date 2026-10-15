import time
import requests
import threading
from typing import Optional
from .config import Config
from .trello_client import TrelloClient
from .telegram_client import TelegramClient
from .state_manager import StateManager
from .notifier import Notifier
from .analytics import TrelloAnalytics


class TelegramBotListener:
    def __init__(
        self,
        config: Config,
        trello: TrelloClient,
        telegram: TelegramClient,
        notifier: Notifier,
        analytics: TrelloAnalytics,
    ):
        self.config = config
        self.trello = trello
        self.telegram = telegram
        self.notifier = notifier
        self.analytics = analytics
        self.last_update_id = 0
        self.is_running = False

    def handle_command(self, text: str, chat_id: str, message_thread_id: Optional[int] = None):
        """Process incoming slash commands from Telegram chat."""
        cmd = text.strip().split()[0].lower()
        # Remove @botname suffix if present (e.g. /phantich@yteProgressbot)
        if "@" in cmd:
            cmd = cmd.split("@")[0]

        print(f"[Telegram Bot] Nhận lệnh '{cmd}' từ Chat ID: {chat_id} (Thread: {message_thread_id})")

        if cmd in ("/phantich", "/baocao", "/report", "/analytics"):
            # 1. Send typing / wait message
            self.telegram.send_message(
                "⏳ <b>Đang thu thập và phân tích dữ liệu các bảng Trello...</b>\n"
                "<i>Hệ thống đang tính toán khối lượng công việc và xếp hạng thành viên, vui lòng đợi trong giây lát!</i>",
                chat_id=chat_id,
                message_thread_id=message_thread_id,
            )

            try:
                data = self.analytics.analyze()
                messages = self.analytics.format_report_html(data)
                for msg in messages:
                    self.telegram.send_message(
                        msg,
                        chat_id=chat_id,
                        message_thread_id=message_thread_id,
                    )
                    time.sleep(0.5)
            except Exception as e:
                err_msg = f"❌ <b>Lỗi trong quá trình phân tích:</b> {e}"
                print(f"[Analytics Error] {e}")
                self.telegram.send_message(
                    err_msg,
                    chat_id=chat_id,
                    message_thread_id=message_thread_id,
                )

        elif cmd in ("/quet", "/scan", "/check"):
            self.telegram.send_message(
                "🔍 <b>Đang bắt đầu quét các task Trello sắp hết hạn và quá hạn...</b>",
                chat_id=chat_id,
                message_thread_id=message_thread_id,
            )
            try:
                res = self.notifier.scan_and_alert()
                if res["sent"] == 0:
                    self.telegram.send_message(
                        f"✅ <b>Quét hoàn tất:</b> Không có cảnh báo mới nào cần gửi!\n"
                        f"(Có {res['due_soon']} thẻ sắp hạn, {res['overdue']} thẻ quá hạn - tất cả đã được thông báo trước đó).",
                        chat_id=chat_id,
                        message_thread_id=message_thread_id,
                    )
            except Exception as e:
                self.telegram.send_message(
                    f"❌ <b>Lỗi khi quét:</b> {e}",
                    chat_id=chat_id,
                    message_thread_id=message_thread_id,
                )

        elif cmd in ("/chuagiao", "/unassigned", "/chuaphancong"):
            self.telegram.send_message(
                "⏳ <b>Đang quét các task chưa gán người thực hiện, chưa có nhãn hoặc chưa có hạn...</b>\n"
                "<i>Hệ thống đang tổng hợp link các thẻ, vui lòng đợi trong giây lát!</i>",
                chat_id=chat_id,
                message_thread_id=message_thread_id,
            )
            try:
                data = self.analytics.get_unassigned_tasks()
                messages = self.analytics.format_unassigned_html(data)
                for msg in messages:
                    self.telegram.send_message(
                        msg,
                        chat_id=chat_id,
                        message_thread_id=message_thread_id,
                    )
                    time.sleep(0.5)
            except Exception as e:
                self.telegram.send_message(
                    f"❌ <b>Lỗi khi quét thẻ chưa giao:</b> {e}",
                    chat_id=chat_id,
                    message_thread_id=message_thread_id,
                )

        elif cmd in ("/start", "/help"):
            help_msg = (
                "👋 <b>Chào mừng bạn đến với Bot Quản Lý & Cảnh Báo Trello!</b>\n\n"
                "📌 <b>Danh sách lệnh bạn có thể sử dụng:</b>\n\n"
                "📊 <b>/phantich</b> - Xuất báo cáo công việc chi tiết: ai làm nhiều task nhất, tỉ lệ chưa xong/đã xong, và bảng xếp hạng thành viên.\n\n"
                "📋 <b>/chuagiao</b> - Xuất danh sách link các task chưa có người thực hiện, chưa gán nhãn hoặc chưa có hạn.\n\n"
                "⏰ <b>/quet</b> - Kích hoạt quét ngay các thẻ sắp hết hạn hoặc quá hạn trên Trello.\n\n"
                "ℹ️ <b>/help</b> - Hiển thị menu hướng dẫn này.\n\n"
                "<i>Bot sẽ tự động chạy ngầm và gửi cảnh báo khi có thẻ sắp hết hạn theo chu kỳ cấu hình.</i>"
            )
            self.telegram.send_message(
                help_msg,
                chat_id=chat_id,
                message_thread_id=message_thread_id,
            )

    def start_polling(self, stop_event: Optional[threading.Event] = None):
        """Start long-polling loop to listen for Telegram commands."""
        self.is_running = True
        print("🤖 [Telegram Bot Listener] Bắt đầu lắng nghe các lệnh (/phantich, /quet, /help)...")

        url = f"{self.telegram.base_url}/getUpdates"

        while self.is_running:
            if stop_event and stop_event.is_set():
                break

            params = {
                "offset": self.last_update_id + 1,
                "timeout": 20,
            }

            try:
                resp = requests.get(url, params=params, timeout=25)
                if resp.status_code != 200:
                    time.sleep(3)
                    continue

                data = resp.json()
                if not data.get("ok"):
                    time.sleep(3)
                    continue

                for update in data.get("result", []):
                    self.last_update_id = update["update_id"]
                    msg = update.get("message")
                    if not msg:
                        continue

                    text = msg.get("text", "")
                    sender = msg.get("from", {})
                    sender_username = (sender.get("username") or "").strip().lower()
                    chat = msg.get("chat", {})
                    chat_type = chat.get("type", "private")  # "private", "group", "supergroup"
                    sender_chat_id = str(chat.get("id", ""))
                    thread_id = msg.get("message_thread_id")

                    if text.startswith("/"):
                        # Only accept commands in private chat directly with the bot (keep group clean)
                        if chat_type != "private":
                            # Ignore commands typed in groups
                            continue

                        # Only allow authorized admin username (e.g. @nguyenvanuy)
                        if self.config.ADMIN_USERNAMES:
                            if sender_username not in self.config.ADMIN_USERNAMES:
                                print(f"[Telegram Bot] Bỏ qua lệnh '{text}' từ @{sender_username} (không có trong danh sách admin).")
                                continue

                        self.handle_command(text, sender_chat_id, message_thread_id=thread_id)

            except requests.exceptions.Timeout:
                # Normal long polling timeout, just loop
                continue
            except requests.exceptions.RequestException as e:
                time.sleep(3)
            except Exception as e:
                print(f"[Telegram Listener] Lỗi không mong muốn: {e}")
                time.sleep(3)

        print("🛑 [Telegram Bot Listener] Đã dừng lắng nghe lệnh.")

    def stop(self):
        self.is_running = False
