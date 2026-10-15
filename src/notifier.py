import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import List, Dict, Any, Tuple
from .config import Config
from .trello_client import TrelloClient
from .telegram_client import TelegramClient
from .state_manager import StateManager


def _resolve_timezone(tz_name: str):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz_name)
    except Exception:
        pass

    # Fallback offset for common VN timezone
    if any(k in tz_name for k in ("Ho_Chi_Minh", "Saigon", "Bangkok", "+07", "GMT+7", "UTC+7")):
        from datetime import timedelta
        return timezone(timedelta(hours=7))
    return timezone.utc


class Notifier:
    def __init__(
        self,
        config: Config,
        trello: TrelloClient,
        telegram: TelegramClient,
        state_mgr: StateManager,
    ):
        self.config = config
        self.trello = trello
        self.telegram = telegram
        self.state_mgr = state_mgr
        self.tz = _resolve_timezone(self.config.TIMEZONE)


    @staticmethod
    def _format_duration_vi(seconds: float) -> str:
        """Format seconds into friendly Vietnamese duration."""
        abs_seconds = int(abs(seconds))
        days = abs_seconds // 86400
        hours = (abs_seconds % 86400) // 3600
        minutes = (abs_seconds % 3600) // 60

        parts = []
        if days > 0:
            parts.append(f"{days} ngày")
        if hours > 0:
            parts.append(f"{hours} giờ")
        if minutes > 0 and days == 0:
            parts.append(f"{minutes} phút")

        if not parts:
            return "chưa đầy 1 phút"
        return " ".join(parts)

    def _parse_due_date(self, due_str: str) -> Tuple[datetime, str]:
        """Parse ISO due string and return (datetime_utc, formatted_local_str)."""
        # Handle formats like 2026-10-15T15:30:00.000Z
        if due_str.endswith("Z"):
            due_clean = due_str[:-1] + "+00:00"
        else:
            due_clean = due_str

        due_dt_utc = datetime.fromisoformat(due_clean).astimezone(timezone.utc)
        due_dt_local = due_dt_utc.astimezone(self.tz)
        formatted_local = due_dt_local.strftime("%H:%M ngày %d/%m/%Y")
        return due_dt_utc, formatted_local

    def scan_and_alert(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Scan Trello boards, find due/overdue cards, and send alerts to Telegram.
        """
        print(f"\n🔍 Bắt đầu quét các thẻ Trello lúc: {datetime.now(self.tz).strftime('%H:%M:%S %d/%m/%Y')}")

        # 1. Determine target boards
        target_board_ids = self.config.TRELLO_BOARD_IDS
        if not target_board_ids:
            boards = self.trello.get_my_boards()
            target_board_ids = [b["id"] for b in boards]
            print(f"📋 Quét toàn bộ {len(target_board_ids)} bảng Trello của bạn.")
        else:
            print(f"📋 Quét {len(target_board_ids)} bảng được chỉ định trong cấu hình.")

        now_utc = datetime.now(timezone.utc)
        due_soon_cards = []
        overdue_cards = []
        active_card_ids = set()

        # 2. Iterate boards and fetch cards
        for board_id in target_board_ids:
            try:
                cards = self.trello.get_board_cards(board_id)
            except Exception as e:
                print(f"⚠️ Lỗi khi tải dữ liệu từ bảng ID '{board_id}': {e}")
                continue

            for card in cards:
                active_card_ids.add(card["id"])
                due_dt_utc, formatted_local = self._parse_due_date(card["due"])
                diff_seconds = (due_dt_utc - now_utc).total_seconds()

                card["due_local"] = formatted_local
                card["diff_seconds"] = diff_seconds

                if diff_seconds < 0:
                    # Overdue
                    if not self.config.INCLUDE_OVERDUE:
                        continue
                    overdue_hours = abs(diff_seconds) / 3600.0
                    if self.config.MAX_OVERDUE_HOURS > 0 and overdue_hours > self.config.MAX_OVERDUE_HOURS:
                        # Exceeds max overdue threshold
                        continue
                    
                    card["alert_type"] = "overdue"
                    card["duration_str"] = self._format_duration_vi(diff_seconds)
                    if self.state_mgr.should_notify(card["id"], "overdue", card["due"], self.config.REMIND_INTERVAL_HOURS):
                        overdue_cards.append(card)

                else:
                    # Due soon
                    diff_hours = diff_seconds / 3600.0
                    if diff_hours <= self.config.HOURS_BEFORE_DUE:
                        card["alert_type"] = "due_soon"
                        card["duration_str"] = self._format_duration_vi(diff_seconds)
                        if self.state_mgr.should_notify(card["id"], "due_soon", card["due"], self.config.REMIND_INTERVAL_HOURS):
                            due_soon_cards.append(card)

        # Prune state
        if not dry_run:
            self.state_mgr.prune_completed_cards(active_card_ids)

        total_alerts = len(due_soon_cards) + len(overdue_cards)
        print(f"📊 Kết quả: Tìm thấy {len(due_soon_cards)} thẻ sắp hết hạn, {len(overdue_cards)} thẻ quá hạn cần gửi thông báo.")

        if total_alerts == 0:
            print("✅ Không có cảnh báo mới cần gửi.")
            return {"sent": 0, "due_soon": 0, "overdue": 0}

        # 3. Send alerts
        cards_to_send = overdue_cards + due_soon_cards
        sent_count = 0

        if self.config.SEND_MODE in ("summary", "both"):
            summary_msg = self._build_summary_message(due_soon_cards, overdue_cards)
            if dry_run:
                print("\n[DRY-RUN TỔNG HỢP]:\n" + summary_msg)
            else:
                res = self.telegram.send_message(summary_msg)
                if res.get("success"):
                    sent_count += 1
                else:
                    print(f"❌ Lỗi gửi tin nhắn tổng hợp Telegram: {res.get('error')}")

        if self.config.SEND_MODE in ("detailed", "both"):
            for card in cards_to_send:
                msg = self._build_card_message(card)
                if dry_run:
                    print(f"\n[DRY-RUN THẺ {card['name']}]:\n" + msg)
                else:
                    res = self.telegram.send_message(msg)
                    if res.get("success"):
                        self.state_mgr.record_notification(card["id"], card["alert_type"], card["due"])
                        sent_count += 1
                    else:
                        print(f"❌ Lỗi gửi tin nhắn thẻ '{card['name']}': {res.get('error')}")
                    
                    # Avoid Telegram rate limit
                    time.sleep(0.8)

        print(f"🎉 Hoàn tất! Đã gửi {sent_count} thông báo tới Telegram.")
        return {
            "sent": sent_count,
            "due_soon": len(due_soon_cards),
            "overdue": len(overdue_cards),
        }

    def _build_card_message(self, card: Dict[str, Any]) -> str:
        """Build HTML message for an individual card."""
        escape = self.telegram.escape_html
        name = escape(card["name"])
        url = card["url"]
        board_name = escape(card["board_name"])
        board_url = card.get("board_url", "")
        list_name = escape(card["list_name"])
        due_local = card["due_local"]
        duration_str = card["duration_str"]

        members_str = ", ".join(escape(m) for m in card["members"]) if card["members"] else "<i>Chưa giao</i>"
        labels_str = ", ".join(f"#{escape(l)}" for l in card["labels"]) if card["labels"] else "<i>Không có</i>"

        if card["alert_type"] == "overdue":
            header = "🚨 <b>[CẢNH BÁO TASK QUÁ HẠN]</b>"
            time_info = f"⏳ <b>Hạn chót:</b> {due_local} (<b>đã quá hạn {duration_str}</b>)"
            status = "❌ <b>TRẠNG THÁI: ĐÃ QUÁ HẠN!</b>"
        else:
            header = "⏰ <b>[NHẮC NHỞ TASK SẮP ĐẾN HẠN]</b>"
            time_info = f"⏳ <b>Hạn chót:</b> {due_local} (<b>còn {duration_str}</b>)"
            status = "⚠️ <b>TRẠNG THÁI: SẮP ĐẾN HẠN!</b>"

        board_display = f'<a href="{board_url}">{board_name}</a>' if board_url else board_name

        message = (
            f"{header}\n\n"
            f"📌 <b>Thẻ:</b> <a href=\"{url}\"><b>{name}</b></a>\n"
            f"📋 <b>Bảng:</b> {board_display}\n"
            f"📂 <b>Danh sách:</b> {list_name}\n"
            f"👤 <b>Phụ trách:</b> {members_str}\n"
            f"🏷️ <b>Nhãn:</b> {labels_str}\n"
            f"{time_info}\n"
            f"{status}\n\n"
            f"👉 <a href=\"{url}\">Nhấn vào đây để xem thẻ trên Trello</a>"
        )
        return message

    def _build_summary_message(self, due_soon: List[Dict[str, Any]], overdue: List[Dict[str, Any]]) -> str:
        """Build aggregated summary message."""
        escape = self.telegram.escape_html
        lines = ["📋 <b>[BÁO CÁO TIẾN ĐỘ TRELLO HÔM NAY]</b>\n"]

        if overdue:
            lines.append(f"🚨 <b>QUÁ HẠN ({len(overdue)} thẻ):</b>")
            for c in overdue:
                lines.append(
                    f"• <a href=\"{c['url']}\">{escape(c['name'])}</a> "
                    f"({escape(c['board_name'])} | trễ {c['duration_str']})"
                )
            lines.append("")

        if due_soon:
            lines.append(f"⏰ <b>SẮP HẾT HẠN ({len(due_soon)} thẻ):</b>")
            for c in due_soon:
                lines.append(
                    f"• <a href=\"{c['url']}\">{escape(c['name'])}</a> "
                    f"({escape(c['board_name'])} | còn {c['duration_str']})"
                )
            lines.append("")

        lines.append("<i>Hãy cập nhật tiến độ để đảm bảo công việc hoàn thành đúng hạn nhé! 💪</i>")
        return "\n".join(lines)
