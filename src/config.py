import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)


class Config:
    # Trello credentials
    TRELLO_API_KEY = os.getenv("TRELLO_API_KEY", "").strip()
    TRELLO_TOKEN = os.getenv("TRELLO_TOKEN", "").strip()
    
    # Comma-separated board IDs or empty for all open boards
    _board_ids_raw = os.getenv("TRELLO_BOARD_IDS", "").strip()
    TRELLO_BOARD_IDS = [b.strip() for b in _board_ids_raw.split(",") if b.strip()]

    # Telegram credentials
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    # Time thresholds & options
    HOURS_BEFORE_DUE = int(os.getenv("HOURS_BEFORE_DUE", "24"))
    INCLUDE_OVERDUE = os.getenv("INCLUDE_OVERDUE", "true").lower() in ("true", "1", "yes")
    MAX_OVERDUE_HOURS = int(os.getenv("MAX_OVERDUE_HOURS", "72"))
    REMIND_INTERVAL_HOURS = int(os.getenv("REMIND_INTERVAL_HOURS", "12"))
    CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "30"))

    # Timezone & output options
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh").strip()
    SEND_MODE = os.getenv("SEND_MODE", "detailed").strip().lower()

    # State file to avoid duplicate alerts
    STATE_FILE = BASE_DIR / "data" / "state.json"

    @classmethod
    def validate(cls, check_trello: bool = True, check_telegram: bool = True):
        """Validate required configuration settings."""
        missing = []
        if check_trello:
            if not cls.TRELLO_API_KEY or cls.TRELLO_API_KEY == "your_trello_api_key_here":
                missing.append("TRELLO_API_KEY (vào https://trello.com/app-key để lấy)")
            if not cls.TRELLO_TOKEN or cls.TRELLO_TOKEN == "your_trello_token_here":
                missing.append("TRELLO_TOKEN (tạo token trên trang https://trello.com/app-key)")
        
        if check_telegram:
            if not cls.TELEGRAM_BOT_TOKEN or cls.TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
                missing.append("TELEGRAM_BOT_TOKEN (tạo bot qua @BotFather trên Telegram)")
            if not cls.TELEGRAM_CHAT_ID or cls.TELEGRAM_CHAT_ID == "your_telegram_chat_id_here":
                missing.append("TELEGRAM_CHAT_ID (lấy ID qua @userinfobot hoặc @RawDataBot)")

        if missing:
            msg = "\n[!] THIẾU CẤU HÌNH TRONG FILE .env:\n"
            for item in missing:
                msg += f"  - {item}\n"
            msg += "\nHướng dẫn: Hãy sao chép file .env.example thành .env và điền các thông tin trên.\n"
            raise ValueError(msg)
