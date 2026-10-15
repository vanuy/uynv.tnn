import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any


class StateManager:
    def __init__(self, state_file_path: Path):
        self.state_file_path = state_file_path
        self.state: Dict[str, Any] = {"cards": {}}
        self._load()

    def _load(self):
        """Load state from JSON file."""
        if self.state_file_path.exists():
            try:
                with open(self.state_file_path, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
                    if "cards" not in self.state:
                        self.state["cards"] = {}
            except Exception as e:
                print(f"[Warning] Không thể đọc file trạng thái {self.state_file_path}: {e}")
                self.state = {"cards": {}}
        else:
            self.state = {"cards": {}}

    def save(self):
        """Save state to JSON file."""
        try:
            self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Error] Không thể lưu file trạng thái {self.state_file_path}: {e}")

    def should_notify(
        self,
        card_id: str,
        current_alert_type: str,
        current_due: str,
        remind_interval_hours: int,
    ) -> bool:
        """
        Check whether this card should trigger a notification.
        - Returns True if never notified.
        - Returns True if due date changed on Trello.
        - Returns True if status escalated from 'due_soon' to 'overdue'.
        - Returns True if remind_interval_hours has elapsed since last notification.
        """
        card_info = self.state.get("cards", {}).get(card_id)
        if not card_info:
            return True

        last_due = card_info.get("last_due")
        last_alert_type = card_info.get("last_alert_type")
        last_notified_str = card_info.get("last_notified_at")

        # Due date changed on Trello
        if last_due != current_due:
            return True

        # Status escalated from due_soon to overdue
        if last_alert_type == "due_soon" and current_alert_type == "overdue":
            return True

        # Check remind interval
        if remind_interval_hours > 0 and last_notified_str:
            try:
                last_notified_at = datetime.fromisoformat(last_notified_str)
                now_utc = datetime.now(timezone.utc)
                hours_since_last = (now_utc - last_notified_at).total_seconds() / 3600.0
                if hours_since_last >= remind_interval_hours:
                    return True
            except Exception:
                return True

        return False

    def record_notification(self, card_id: str, alert_type: str, due: str):
        """Record that a notification was sent for this card."""
        now_iso = datetime.now(timezone.utc).isoformat()
        if "cards" not in self.state:
            self.state["cards"] = {}

        self.state["cards"][card_id] = {
            "last_notified_at": now_iso,
            "last_alert_type": alert_type,
            "last_due": due,
        }
        self.save()

    def prune_completed_cards(self, active_card_ids: set):
        """Remove cards from state that are no longer active/present."""
        cards = self.state.get("cards", {})
        to_delete = [cid for cid in cards if cid not in active_card_ids]
        if to_delete:
            for cid in to_delete:
                del cards[cid]
            self.save()
