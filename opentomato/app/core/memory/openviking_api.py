from __future__ import annotations


class OpenVikingAPI:
    HEALTH = "/health"
    SESSIONS_PREFIX = "/api/v1/sessions/"
    SEARCH_PREFIX = "/api/v1/search/"

    # Content
    CONTENT_ABSTRACT = "/api/v1/content/abstract"
    CONTENT_OVERVIEW = "/api/v1/content/overview"

    # Filesystem

    # Search
    SEARCH_FIND = "/api/v1/search/find"

    # Admin
    ADMIN_ACCOUNTS = "/api/v1/admin/accounts"

    @staticmethod
    def admin_account_users(account_id: str) -> str:
        return f"/api/v1/admin/accounts/{account_id}/users"

    @staticmethod
    def admin_account_user_key(account_id: str, user_id: str) -> str:
        return f"/api/v1/admin/accounts/{account_id}/users/{user_id}/key"

    # Sessions
    @staticmethod
    def session_root(session_id: str) -> str:
        return f"/api/v1/sessions/{session_id}"

    @staticmethod
    def session_messages(session_id: str) -> str:
        return f"/api/v1/sessions/{session_id}/messages"

    @staticmethod
    def session_commit(session_id: str) -> str:
        return f"/api/v1/sessions/{session_id}/commit"

    @staticmethod
    def session_extract(session_id: str) -> str:
        return f"/api/v1/sessions/{session_id}/extract"

    @staticmethod
    def session_used(session_id: str) -> str:
        return f"/api/v1/sessions/{session_id}/used"
