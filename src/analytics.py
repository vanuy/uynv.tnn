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

    def get_unassigned_tasks(self, target_board_ids: List[str] = None) -> Dict[str, Any]:
        """
        Scan all open cards across boards that are unassigned, have no label, or have no due date.
        """
        if not target_board_ids:
            target_board_ids = self.config.TRELLO_BOARD_IDS
        if not target_board_ids:
            boards = self.trello.get_my_boards()
            target_board_ids = [b["id"] for b in boards]

        unassigned_cards = []
        total_open_cards = 0
        count_no_member = 0
        count_no_label = 0
        count_no_due = 0
        count_all_three = 0

        for board_id in target_board_ids:
            try:
                board_info = self.trello._request("GET", f"/boards/{board_id}", {"fields": "id,name,url"})
                board_name = board_info.get("name", "Bảng Trello")
                lists_map = self.trello.get_board_lists(board_id)

                cards_data = self.trello._request(
                    "GET",
                    f"/boards/{board_id}/cards",
                    {
                        "filter": "open",
                        "fields": "id,name,due,dueComplete,url,idList,idMembers,labels,closed",
                    },
                )
            except Exception as e:
                print(f"[Analytics] Lỗi tải dữ liệu bảng {board_id}: {e}")
                continue

            for card in cards_data:
                if card.get("closed"):
                    continue

                list_name = lists_map.get(card.get("idList", ""), "Mặc định")
                # Skip completed cards
                if bool(card.get("dueComplete")) or self.is_list_completed(list_name):
                    continue

                total_open_cards += 1
                has_member = bool(card.get("idMembers"))
                has_label = bool(card.get("labels"))
                has_due = bool(card.get("due"))

                if not has_member:
                    count_no_member += 1
                if not has_label:
                    count_no_label += 1
                if not has_due:
                    count_no_due += 1
                if not has_member and not has_label and not has_due:
                    count_all_three += 1

                # If card lacks member (unassigned), or lacks all three
                if not has_member:
                    missing_parts = ["[Chưa có người thực hiện]"]
                    if not has_label:
                        missing_parts.append("[Chưa gán nhãn]")
                    if not has_due:
                        missing_parts.append("[Chưa có hạn]")

                    unassigned_cards.append({
                        "id": card["id"],
                        "name": card["name"],
                        "url": card["url"],
                        "board_name": board_name,
                        "list_name": list_name,
                        "no_member": not has_member,
                        "no_label": not has_label,
                        "no_due": not has_due,
                        "is_all_three": (not has_member and not has_label and not has_due),
                        "missing_desc": " | ".join(missing_parts),
                    })

        return {
            "time_str": datetime.now(self.tz).strftime("%H:%M ngày %d/%m/%Y"),
            "total_open": total_open_cards,
            "count_no_member": count_no_member,
            "count_no_label": count_no_label,
            "count_no_due": count_no_due,
            "count_all_three": count_all_three,
            "cards": unassigned_cards,
        }

    def format_unassigned_html(self, data: Dict[str, Any]) -> List[str]:
        """
        Format unassigned tasks into clean, clickable HTML messages for Telegram.
        """
        escape = html.escape
        time_str = data["time_str"]
        count_no_member = data["count_no_member"]
        count_all_three = data["count_all_three"]
        cards = data["cards"]

        lines = []
        lines.append("📋 <b>DANH SÁCH CÁC TASK CHƯA GIAO (CHƯA CÓ NGƯỜI THỰC HIỆN)</b>")
        lines.append(f"⏱ <i>Cập nhật lúc: {time_str} (Giờ VN)</i>")
        lines.append("━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        lines.append("📊 <b>TỔNG QUAN:</b>")
        lines.append(f"• Thẻ chưa có người thực hiện: <b>{count_no_member} thẻ</b> 👤")
        lines.append(f"• Thẻ thiếu cả 3 mục (Chưa người + Chưa nhãn + Chưa hạn): <b>{count_all_three} thẻ</b> ⚠️")
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🔗 <b>DANH SÁCH CHI TIẾT CÁC THẺ CẦN PHÂN CÔNG:</b>")
        lines.append("<i>(Bấm vào link [chưa có người thực hiện...] để mở thẻ trên Trello)</i>")
        lines.append("")

        if not cards:
            lines.append("🎉 <b>Tuyệt vời!</b> Tất cả các thẻ công việc đều đã được phân công đầy đủ.")
        else:
            # Group cards by board
            boards_dict: Dict[str, List[Dict[str, Any]]] = {}
            for c in cards:
                bname = c["board_name"]
                if bname not in boards_dict:
                    boards_dict[bname] = []
                boards_dict[bname].append(c)

            card_counter = 1
            for bname, bcards in boards_dict.items():
                lines.append(f"📋 <b>Bảng: {escape(bname)}</b> ({len(bcards)} thẻ):")
                for c in bcards:
                    name_escaped = escape(c["name"])
                    url = c["url"]
                    list_name = escape(c["list_name"])
                    
                    # Highlight cards with all three missing
                    tag = "⚠️" if c["is_all_three"] else "📌"
                    
                    lines.append(
                        f"{tag} {card_counter}. <a href=\"{url}\">[chưa có người thực hiện] <b>{name_escaped}</b></a>\n"
                        f"   📂 <i>Cột: {list_name}</i> | <i>{escape(c['missing_desc'])}</i>"
                    )
                    card_counter += 1
                lines.append("")

        lines.append("<i>💡 Hãy bấm vào từng thẻ để gán người phụ trách, nhãn và ngày hạn chót nhé!</i>")

        # Split into chunks of <= 3900 chars
        chunks = []
        current_chunk = []
        current_len = 0
        for line in lines:
            if current_len + len(line) + 1 > 3800:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_len = len(line) + 1
            else:
                current_chunk.append(line)
                current_len += len(line) + 1
        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks
