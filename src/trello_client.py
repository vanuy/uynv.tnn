import requests
from typing import List, Dict, Any, Optional


class TrelloClient:
    BASE_URL = "https://api.trello.com/1"

    def __init__(self, api_key: str, token: str):
        self.api_key = api_key
        self.token = token
        self.session = requests.Session()

    def _get_auth_params(self) -> Dict[str, str]:
        return {
            "key": self.api_key,
            "token": self.token,
        }

    def _request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.BASE_URL}{endpoint}"
        all_params = self._get_auth_params()
        if params:
            all_params.update(params)

        response = self.session.request(method, url, params=all_params, timeout=15)
        response.raise_for_status()
        return response.json()

    def test_connection(self) -> Dict[str, Any]:
        """Test API credentials and return user info."""
        try:
            user = self._request("GET", "/members/me", {"fields": "id,fullName,username"})
            return {
                "success": True,
                "username": user.get("username"),
                "fullName": user.get("fullName"),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def get_my_boards(self) -> List[Dict[str, Any]]:
        """Get all open boards accessible to this account."""
        return self._request(
            "GET",
            "/members/me/boards",
            {
                "filter": "open",
                "fields": "id,name,url,closed",
            },
        )

    def get_board_lists(self, board_id: str) -> Dict[str, str]:
        """Get mapping of list_id -> list_name for a board."""
        lists_data = self._request(
            "GET",
            f"/boards/{board_id}/lists",
            {
                "fields": "id,name,closed",
            },
        )
        return {item["id"]: item["name"] for item in lists_data}

    def get_board_members(self, board_id: str) -> Dict[str, str]:
        """Get mapping of member_id -> display_name for a board."""
        members_data = self._request(
            "GET",
            f"/boards/{board_id}/members",
            {
                "fields": "id,fullName,username",
            },
        )
        return {
            item["id"]: item.get("fullName") or item.get("username")
            for item in members_data
        }

    def get_board_cards(self, board_id: str) -> List[Dict[str, Any]]:
        """Get cards with due dates on a board."""
        # Get board info
        board_info = self._request("GET", f"/boards/{board_id}", {"fields": "id,name,url"})
        board_name = board_info.get("name", "Bảng Trello")
        board_url = board_info.get("url", "")

        # Get lists & members lookup map
        lists_map = self.get_board_lists(board_id)
        members_map = self.get_board_members(board_id)

        # Get open cards
        cards_data = self._request(
            "GET",
            f"/boards/{board_id}/cards",
            {
                "filter": "open",
                "fields": "id,name,due,dueComplete,url,idList,idMembers,labels,closed",
            },
        )

        due_cards = []
        for card in cards_data:
            # Skip cards with no due date, or marked as complete, or closed
            if card.get("closed") or not card.get("due") or card.get("dueComplete"):
                continue

            # Resolve list name
            list_name = lists_map.get(card.get("idList", ""), "Mặc định")

            # Resolve member names
            card_member_ids = card.get("idMembers", [])
            member_names = [members_map[mid] for mid in card_member_ids if mid in members_map]

            # Resolve labels
            labels = card.get("labels", [])
            label_names = [lbl["name"] for lbl in labels if lbl.get("name")]

            due_cards.append({
                "id": card["id"],
                "name": card["name"],
                "due": card["due"],
                "url": card["url"],
                "board_id": board_id,
                "board_name": board_name,
                "board_url": board_url,
                "list_name": list_name,
                "members": member_names,
                "labels": label_names,
            })

        return due_cards

    def get_current_user(self) -> Dict[str, Any]:
        """Get current user details."""
        return self._request("GET", "/members/me", {"fields": "id,fullName,username"})

    def add_member_to_card(self, card_id: str, member_id: str) -> bool:
        """Add a member to a card."""
        try:
            self._request("POST", f"/cards/{card_id}/idMembers", {"value": member_id})
            return True
        except Exception as e:
            if "member is already on the card" in str(e).lower():
                return True
            try:
                self._request("PUT", f"/cards/{card_id}", {"idMembers": member_id})
                return True
            except Exception:
                return False

