import html
import time
import requests
from typing import Dict, Any


class TelegramClient:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.session = requests.Session()

    @staticmethod
    def escape_html(text: str) -> str:
        """Escape text for HTML parse mode in Telegram."""
        if not text:
            return ""
        return html.escape(str(text))

    def test_connection(self) -> Dict[str, Any]:
        """Test Telegram Bot token and send a test message to Chat ID."""
        try:
            # 1. Test Bot Token
            get_me_url = f"{self.base_url}/getMe"
            resp = self.session.get(get_me_url, timeout=10)
            data = resp.json()
            if not data.get("ok"):
                return {
                    "success": False,
                    "error": f"Bot Token không hợp lệ: {data.get('description', 'Unknown error')}",
                }

            bot_info = data.get("result", {})
            bot_username = bot_info.get("username", "")

            # 2. Test sending a message to Chat ID
            test_msg = (
                f"🤖 <b>[KẾT NỐI THÀNH CÔNG]</b>\n\n"
                f"Bot <b>@{bot_username}</b> đã kết nối thành công với nhóm/kênh này!\n"
                f"Hệ thống cảnh báo Trello đã sẵn sàng hoạt động. 🚀"
            )
            send_res = self.send_message(test_msg)
            if not send_res.get("success"):
                return {
                    "success": False,
                    "error": f"Token bot đúng (@{bot_username}), nhưng không gửi được tới Chat ID {self.chat_id}: {send_res.get('error')}",
                }

            return {
                "success": True,
                "bot_username": bot_username,
                "bot_name": bot_info.get("first_name", ""),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def send_message(self, text: str, parse_mode: str = "HTML", disable_web_page_preview: bool = False) -> Dict[str, Any]:
        """Send message via Telegram Bot API with retry for rate limits."""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = self.session.post(url, json=payload, timeout=15)
                data = resp.json()

                if data.get("ok"):
                    return {"success": True, "result": data.get("result")}

                # Rate limiting: 429 Too Many Requests
                if resp.status_code == 429:
                    retry_after = data.get("parameters", {}).get("retry_after", 3)
                    print(f"[Telegram API] Bị giới hạn tần suất, đợi {retry_after}s trước khi thử lại...")
                    time.sleep(retry_after)
                    continue

                return {
                    "success": False,
                    "error": f"[{resp.status_code}] {data.get('description', 'Unknown error')}",
                }

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "Đã thử gửi tối đa nhưng không thành công."}
