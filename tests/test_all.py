import os
import sys
import unittest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Fix Windows console UTF-8 encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from src.state_manager import StateManager
from src.telegram_client import TelegramClient
from src.notifier import Notifier
from src.config import Config


class DummyConfig:
    TRELLO_API_KEY = "test_key"
    TRELLO_TOKEN = "test_token"
    TRELLO_BOARD_IDS = []
    TELEGRAM_BOT_TOKEN = "test_bot_token"
    TELEGRAM_CHAT_ID = "123456789"
    TELEGRAM_GROUP_CHAT_ID = "-1004404557034"
    TELEGRAM_ADMIN_CHAT_ID = "851630770"
    HOURS_BEFORE_DUE = 24
    INCLUDE_OVERDUE = True
    MAX_OVERDUE_HOURS = 72
    REMIND_INTERVAL_HOURS = 12
    CHECK_INTERVAL_MINUTES = 30
    TIMEZONE = "Asia/Ho_Chi_Minh"
    SEND_MODE = "detailed"
    STATE_FILE = Path("")


class TestTrelloNotifier(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "state.json"
        self.state_mgr = StateManager(self.state_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_telegram_html_escape(self):
        raw = '<b>Task <test> & "quotes"</b>'
        escaped = TelegramClient.escape_html(raw)
        self.assertEqual(escaped, "&lt;b&gt;Task &lt;test&gt; &amp; &quot;quotes&quot;&lt;/b&gt;")

    def test_state_manager_lifecycle(self):
        card_id = "card_123"
        due_iso = "2026-10-16T12:00:00.000Z"

        # 1. New card should notify
        self.assertTrue(self.state_mgr.should_notify(card_id, "due_soon", due_iso, 12))

        # 2. Record notification
        self.state_mgr.record_notification(card_id, "due_soon", due_iso)

        # 3. Same card immediately after should NOT notify
        self.assertFalse(self.state_mgr.should_notify(card_id, "due_soon", due_iso, 12))

        # 4. Due date changed should notify
        new_due_iso = "2026-10-17T12:00:00.000Z"
        self.assertTrue(self.state_mgr.should_notify(card_id, "due_soon", new_due_iso, 12))

        # 5. Status escalated to overdue should notify
        self.assertTrue(self.state_mgr.should_notify(card_id, "overdue", due_iso, 12))

    def test_duration_formatting(self):
        # 1 hour
        self.assertEqual(Notifier._format_duration_vi(3600), "1 giờ")
        # 2 days 3 hours
        self.assertEqual(Notifier._format_duration_vi(86400 * 2 + 3600 * 3), "2 ngày 3 giờ")
        # 30 seconds
        self.assertEqual(Notifier._format_duration_vi(30), "chưa đầy 1 phút")
        # 45 minutes
        self.assertEqual(Notifier._format_duration_vi(2700), "45 phút")

    def test_card_message_generation(self):
        cfg = DummyConfig()
        notifier = Notifier(cfg, None, TelegramClient("fake", "fake"), self.state_mgr)
        card = {
            "id": "c1",
            "name": "Hoàn thiện báo cáo & gửi sếp",
            "url": "https://trello.com/c/123",
            "board_name": "Dự án Marketing",
            "board_url": "https://trello.com/b/123",
            "list_name": "Đang làm",
            "members": ["Nguyễn Văn A"],
            "labels": ["Gấp", "Ưu tiên"],
            "due_local": "17:00 ngày 16/10/2026",
            "duration_str": "3 giờ 30 phút",
            "alert_type": "due_soon",
        }
        msg = notifier._build_card_message(card)
        self.assertIn("NHẮC NHỞ TASK SẮP ĐẾN HẠN", msg)
        self.assertIn("Hoàn thiện báo cáo &amp; gửi sếp", msg)
        self.assertIn("Dự án Marketing", msg)
        self.assertIn("Nguyễn Văn A", msg)
        self.assertIn("#Gấp", msg)
        self.assertIn("còn 3 giờ 30 phút", msg)


class MockTrelloClient:
    def __init__(self, boards, cards):
        self._boards = boards
        self._cards = cards

    def get_my_boards(self):
        return self._boards

    def get_board_cards(self, board_id):
        return self._cards.get(board_id, [])


class MockTelegramClient:
    def __init__(self):
        self.sent_messages = []

    def escape_html(self, text):
        return TelegramClient.escape_html(text)

    def send_message(self, text, parse_mode="HTML", **kwargs):
        self.sent_messages.append({"text": text, "parse_mode": parse_mode, "kwargs": kwargs})
        return {"success": True}


class TestNotifierEndToEnd(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "state.json"
        self.state_mgr = StateManager(self.state_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_scan_and_alert_filtering_and_deduplication(self):
        now_utc = datetime.now(timezone.utc)
        
        # 1. Card due in 5 hours (should alert)
        due_soon_iso = (now_utc + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        # 2. Card due in 48 hours (outside 24h threshold -> should NOT alert)
        due_far_iso = (now_utc + timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        # 3. Card overdue by 3 hours (should alert)
        overdue_iso = (now_utc - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        mock_boards = [{"id": "b1", "name": "Bảng Dự Án", "url": "https://trello.com/b/1"}]
        mock_cards = {
            "b1": [
                {
                    "id": "card_soon",
                    "name": "Nộp báo cáo tuần",
                    "due": due_soon_iso,
                    "url": "https://trello.com/c/soon",
                    "board_id": "b1",
                    "board_name": "Bảng Dự Án",
                    "board_url": "https://trello.com/b/1",
                    "list_name": "Đang làm",
                    "members": ["Tuấn Anh"],
                    "labels": ["Báo cáo"],
                },
                {
                    "id": "card_far",
                    "name": "Lập kế hoạch tháng sau",
                    "due": due_far_iso,
                    "url": "https://trello.com/c/far",
                    "board_id": "b1",
                    "board_name": "Bảng Dự Án",
                    "board_url": "https://trello.com/b/1",
                    "list_name": "Ý tưởng",
                    "members": [],
                    "labels": [],
                },
                {
                    "id": "card_overdue",
                    "name": "Fix bug thanh toán",
                    "due": overdue_iso,
                    "url": "https://trello.com/c/overdue",
                    "board_id": "b1",
                    "board_name": "Bảng Dự Án",
                    "board_url": "https://trello.com/b/1",
                    "list_name": "Bug",
                    "members": ["Huy"],
                    "labels": ["Khẩn cấp"],
                },
            ]
        }

        mock_trello = MockTrelloClient(mock_boards, mock_cards)
        mock_telegram = MockTelegramClient()
        cfg = DummyConfig()
        cfg.HOURS_BEFORE_DUE = 24
        cfg.INCLUDE_OVERDUE = True
        cfg.REMIND_INTERVAL_HOURS = 12

        notifier = Notifier(cfg, mock_trello, mock_telegram, self.state_mgr)

        # First scan
        res = notifier.scan_and_alert()
        self.assertEqual(res["due_soon"], 1)
        self.assertEqual(res["overdue"], 1)
        self.assertEqual(len(mock_telegram.sent_messages), 2)

        # Check message content
        sent_texts = " ".join([m["text"] for m in mock_telegram.sent_messages])
        self.assertIn("Nộp báo cáo tuần", sent_texts)
        self.assertIn("Fix bug thanh toán", sent_texts)
        self.assertNotIn("Lập kế hoạch tháng sau", sent_texts)

        # Second scan immediately after -> should NOT send any alerts due to deduplication
        mock_telegram.sent_messages.clear()
        res2 = notifier.scan_and_alert()
        self.assertEqual(res2["sent"], 0)
        self.assertEqual(len(mock_telegram.sent_messages), 0)


if __name__ == "__main__":
    unittest.main()
