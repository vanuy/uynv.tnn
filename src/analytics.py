from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import List, Dict, Any, Tuple
import html
from .config import Config
from .trello_client import TrelloClient
from .telegram_client import TelegramClient


COMPLETED_KEYWORDS = [
    "hoàn thành",
    "done",
    "đã xong",
    "completed",
    "finish",
    "finished",
    "nghiệm thu",
    "đã xử lý",
    "đã hoàn thành",
    "đóng",
    "close",
    "closed",
]


class TrelloAnalytics:
    def __init__(self, config: Config, trello: TrelloClient, telegram: TelegramClient):
        self.config = config
        self.trello = trello
        self.telegram = telegram
        
        try:
            self.tz = ZoneInfo(self.config.TIMEZONE)
        except Exception:
            self.tz = timezone.utc

    def is_list_completed(self, list_name: str) -> bool:
        """Check if a list represents a completed state."""
        norm = list_name.lower().strip()
        return any(kw in norm for kw in COMPLETED_KEYWORDS)

    def analyze(self, target_board_ids: List[str] = None) -> Dict[str, Any]:
        """
        Analyze all open cards across Trello boards to calculate workload,
        completion rates, overdue tasks, and rank members.
        """
        if not target_board_ids:
            target_board_ids = self.config.TRELLO_BOARD_IDS
        if not target_board_ids:
            boards = self.trello.get_my_boards()
            target_board_ids = [b["id"] for b in boards]

        now_utc = datetime.now(timezone.utc)

        total_cards_count = 0
        total_completed_count = 0
        total_uncompleted_count = 0
        total_overdue_count = 0
        unassigned_cards_count = 0

        # Member stats dictionary: member_id -> dict
        members_data: Dict[str, Dict[str, Any]] = {}
        board_summaries = []

        for board_id in target_board_ids:
            try:
                board_info = self.trello._request("GET", f"/boards/{board_id}", {"fields": "id,name,url"})
                board_name = board_info.get("name", "Bảng Trello")
                lists_map = self.trello.get_board_lists(board_id)
                members_map = self.trello.get_board_members(board_id)

                cards_data = self.trello._request(
                    "GET",
                    f"/boards/{board_id}/cards",
                    {
                        "filter": "open",
                        "fields": "id,name,due,dueComplete,url,idList,idMembers,closed",
                    },
                )
            except Exception as e:
                print(f"[Analytics] Lỗi tải dữ liệu bảng {board_id}: {e}")
                continue

            board_total = len(cards_data)
            board_completed = 0
            board_overdue = 0

            # Register all board members in members_data
            for mid, mname in members_map.items():
                if mid not in members_data:
                    members_data[mid] = {
                        "id": mid,
                        "name": mname,
                        "total_assigned": 0,
                        "completed": 0,
                        "uncompleted": 0,
                        "overdue": 0,
                        "cards": [],
                    }

            for card in cards_data:
                if card.get("closed"):
                    continue

                total_cards_count += 1
                list_name = lists_map.get(card.get("idList", ""), "")
                is_completed = bool(card.get("dueComplete")) or self.is_list_completed(list_name)
                
                # Check overdue
                is_overdue = False
                due_str = card.get("due")
                if due_str and not is_completed:
                    clean_due = due_str[:-1] + "+00:00" if due_str.endswith("Z") else due_str
                    due_dt = datetime.fromisoformat(clean_due).astimezone(timezone.utc)
                    if (due_dt - now_utc).total_seconds() < 0:
                        is_overdue = True
                        total_overdue_count += 1
                        board_overdue += 1

                if is_completed:
                    total_completed_count += 1
                    board_completed += 1
                else:
                    total_uncompleted_count += 1

                member_ids = card.get("idMembers", [])
                if not member_ids:
                    unassigned_cards_count += 1
                else:
                    for mid in member_ids:
                        if mid not in members_data:
                            members_data[mid] = {
                                "id": mid,
                                "name": members_map.get(mid, "Thành viên ẩn"),
                                "total_assigned": 0,
                                "completed": 0,
                                "uncompleted": 0,
                                "overdue": 0,
                                "cards": [],
                            }
                        
                        m_stat = members_data[mid]
                        m_stat["total_assigned"] += 1
                        if is_completed:
                            m_stat["completed"] += 1
                        else:
                            m_stat["uncompleted"] += 1
                        
                        if is_overdue:
                            m_stat["overdue"] += 1

            board_summaries.append({
                "name": board_name,
                "total": board_total,
                "completed": board_completed,
                "overdue": board_overdue,
            })

        # Filter out members with 0 assigned tasks to keep report clean
        active_members = [m for m in members_data.values() if m["total_assigned"] > 0]

        # Calculate metrics & performance rating for each member
        for m in active_members:
            tot = m["total_assigned"]
            comp = m["completed"]
            uncomp = m["uncompleted"]
            over = m["overdue"]

            comp_rate = (comp / tot * 100.0) if tot > 0 else 0.0
            uncomp_rate = (uncomp / tot * 100.0) if tot > 0 else 0.0

            m["completion_rate"] = comp_rate
            m["uncompleted_rate"] = uncomp_rate

            # Evaluation & Badge
            if comp_rate >= 80:
                badge = "⭐ Xuất sắc (Hoàn thành cao)"
            elif comp_rate >= 50:
                badge = "👍 Tốt (Tiến độ ổn định)"
            elif over > (tot * 0.4):
                badge = "⚠️ Quá tải / Nhiều task trễ hạn"
            elif uncomp > 5:
                badge = "⏳ Đang tồn đọng nhiều việc"
            else:
                badge = "🔄 Đang thực hiện"

            m["badge"] = badge

        # Sort ranking by total tasks assigned (who has the most tasks)
        active_members.sort(key=lambda x: (x["total_assigned"], x["completed"]), reverse=True)

        return {
            "time_str": datetime.now(self.tz).strftime("%H:%M ngày %d/%m/%Y"),
            "total_cards": total_cards_count,
            "completed_cards": total_completed_count,
            "uncompleted_cards": total_uncompleted_count,
            "overdue_cards": total_overdue_count,
            "unassigned_cards": unassigned_cards_count,
            "members": active_members,
            "boards": board_summaries,
        }

    def format_report_html(self, data: Dict[str, Any]) -> List[str]:
        """
        Format analysis data into beautiful Telegram HTML messages.
        Returns a list of message chunks (if content is large).
        """
        escape = html.escape
        time_str = data["time_str"]
        total = data["total_cards"]
        completed = data["completed_cards"]
        uncompleted = data["uncompleted_cards"]
        overdue = data["overdue_cards"]
        unassigned = data["unassigned_cards"]
        members = data["members"]

        overall_comp_rate = (completed / total * 100.0) if total > 0 else 0.0

        lines = []
        lines.append("📊 <b>BÁO CÁO PHÂN TÍCH TIẾN ĐỘ & HIỆU SUẤT TRELLO</b>")
        lines.append(f"⏱ <i>Cập nhật lúc: {time_str} (Giờ VN)</i>")
        lines.append("━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        lines.append("📌 <b>TỔNG QUAN CÔNG VIỆC:</b>")
        lines.append(f"• Tổng số công việc (Cards): <b>{total}</b>")
        lines.append(f"• Đã hoàn thành: <b>{completed}</b> ({overall_comp_rate:.1f}%) ✅")
        lines.append(f"• Chưa hoàn thành: <b>{uncompleted}</b> ({100 - overall_comp_rate:.1f}%) ⏳")
        lines.append(f"• Đang quá hạn (Overdue): <b>{overdue}</b> 🚨")
        lines.append(f"• Chưa phân công người: <b>{unassigned}</b> 👤")
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🏆 <b>XẾP HẠNG THÀNH VIÊN THEO KHỐI LƯỢNG & TIẾN ĐỘ:</b>")
        lines.append("<i>(Thứ tự theo số lượng công việc được giao & xử lý)</i>")
        lines.append("")

        if not members:
            lines.append("<i>Chưa có thành viên nào được phân công thẻ công việc cụ thể.</i>")
        else:
            rank_emojis = ["🥇", "🥈", "🥉"]
            for idx, m in enumerate(members, start=1):
                icon = rank_emojis[idx - 1] if idx <= 3 else f"#{idx}"
                name = escape(m["name"])
                tot = m["total_assigned"]
                comp = m["completed"]
                uncomp = m["uncompleted"]
                over = m["overdue"]
                comp_pct = m["completion_rate"]
                badge = m["badge"]

                lines.append(f"{icon} <b>{name}</b>")
                lines.append(f"  • Tổng task được giao: <b>{tot}</b>")
                lines.append(f"  • Chưa xong / Đang làm: <b>{uncomp} / {tot}</b> ({100 - comp_pct:.1f}%)")
                lines.append(f"  • Đã hoàn thành: <b>{comp}</b> ({comp_pct:.1f}%)")
                if over > 0:
                    lines.append(f"  • ⚠️ Quá hạn: <b>{over} task</b>")
                lines.append(f"  • Đánh giá: <i>{badge}</i>")
                lines.append("")

        lines.append("━━━━━━━━━━━━━━━━━━━━━")
        lines.append("💡 <b>TỔNG KẾT & KHUYẾN NGHỊ:</b>")
        if members:
            top_worker = members[0]
            lines.append(f"• 👑 <b>Làm nhiều task nhất:</b> <b>{escape(top_worker['name'])}</b> ({top_worker['total_assigned']} task).")

            # Most completed
            best_finisher = max(members, key=lambda x: (x["completed"], x["completion_rate"]))
            if best_finisher["completed"] > 0:
                lines.append(f"• 🎯 <b>Hoàn thành nhiều nhất:</b> <b>{escape(best_finisher['name'])}</b> ({best_finisher['completed']} task).")

            # Most overdue
            overdue_members = [m for m in members if m["overdue"] > 0]
            if overdue_members:
                most_overdue = max(overdue_members, key=lambda x: x["overdue"])
                lines.append(f"• ⚠️ <b>Cần hỗ trợ giải phóng task trễ:</b> <b>{escape(most_overdue['name'])}</b> ({most_overdue['overdue']} task quá hạn).")

        lines.append("<i>Hãy cùng hỗ trợ nhau để đẩy nhanh tiến độ dự án nhé! 🚀</i>")

        # Split into chunks of <= 4000 chars if message is too long
        full_text = "\n".join(lines)
        if len(full_text) <= 4000:
            return [full_text]

        chunks = []
        current_chunk = []
        current_len = 0
        for line in lines:
            if current_len + len(line) + 1 > 3900:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_len = len(line) + 1
            else:
                current_chunk.append(line)
                current_len += len(line) + 1
        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks
