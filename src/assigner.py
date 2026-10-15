import time
import logging
from typing import Dict, Any, List, Optional
from .trello_client import TrelloClient

logger = logging.getLogger("TrelloNotifier")


class TaskAssigner:
    """
    Utility to assign a specific member to unassigned cards across Trello boards.
    """

    def __init__(self, trello_client: TrelloClient, board_ids: Optional[List[str]] = None):
        self.client = trello_client
        self.board_ids = board_ids or []

    def get_target_member(self, target_name_or_username: Optional[str] = None) -> Dict[str, Any]:
        """
        Identify member ID for assignment. Defaults to current authenticated user.
        """
        me = self.client.get_current_user()
        return {
            "id": me.get("id"),
            "username": me.get("username"),
            "fullName": me.get("fullName", "Uy nguyễn"),
        }

    def assign_cards(
        self,
        mode: str = "chuagiao",
        member_id: Optional[str] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Assign member to cards.
        mode:
          - 'chuagiao': Cards with no member, no labels, and no due date.
          - 'all_unassigned': Any cards with no member assigned.
        """
        if not member_id:
            target_mem = self.get_target_member()
            member_id = target_mem["id"]
            member_name = target_mem["fullName"]
        else:
            member_name = "Uy nguyễn"

        # Determine boards to scan
        if self.board_ids:
            all_boards = [{"id": bid, "name": f"Board {bid}"} for bid in self.board_ids]
        else:
            all_boards = self.client.get_my_boards()

        matched_cards: List[Dict[str, Any]] = []

        # Find target cards
        for board in all_boards:
            board_id = board["id"]
            board_name = board.get("name", "Bảng Trello")

            try:
                cards_data = self.client._request(
                    "GET",
                    f"/boards/{board_id}/cards",
                    {
                        "filter": "open",
                        "fields": "id,name,url,idList,idMembers,labels,due,closed",
                    },
                )
            except Exception as e:
                logger.error(f"Error fetching cards for board {board_name}: {e}")
                continue

            for card in cards_data:
                if card.get("closed"):
                    continue

                has_member = bool(card.get("idMembers"))
                has_label = bool(card.get("labels"))
                has_due = bool(card.get("due"))

                if mode == "chuagiao":
                    # Lọc task chưa có người + chưa có nhãn + chưa có hạn
                    if not has_member and not has_label and not has_due:
                        matched_cards.append({
                            "id": card["id"],
                            "name": card["name"],
                            "url": card["url"],
                            "board_name": board_name,
                        })
                else:
                    # Lọc tất cả task chưa có người
                    if not has_member:
                        matched_cards.append({
                            "id": card["id"],
                            "name": card["name"],
                            "url": card["url"],
                            "board_name": board_name,
                        })

        total = len(matched_cards)
        print(f"🔍 Tìm thấy {total} thẻ thỏa điều kiện (mode='{mode}').")

        success_count = 0
        fail_count = 0
        details = []

        for idx, card in enumerate(matched_cards, start=1):
            card_id = card["id"]
            card_name = card["name"]
            board_name = card["board_name"]

            if dry_run:
                print(f"[DRY RUN] [{idx}/{total}] [{board_name}] Sẽ gán '{member_name}' vào: {card_name}")
                success_count += 1
                details.append({
                    "card": card,
                    "status": "dry_run",
                })
            else:
                ok = self.client.add_member_to_card(card_id, member_id)
                if ok:
                    success_count += 1
                    print(f"[{idx}/{total}] ✅ Đã gán '{member_name}' -> [{board_name}] {card_name}")
                    details.append({
                        "card": card,
                        "status": "success",
                    })
                else:
                    fail_count += 1
                    print(f"[{idx}/{total}] ❌ Thất bại khi gán -> [{board_name}] {card_name}")
                    details.append({
                        "card": card,
                        "status": "failed",
                    })

                # Avoid hitting Trello rate limits (max 300 req/10s)
                time.sleep(0.08)

        return {
            "total": total,
            "success": success_count,
            "failed": fail_count,
            "member_id": member_id,
            "member_name": member_name,
            "mode": mode,
            "dry_run": dry_run,
        }
