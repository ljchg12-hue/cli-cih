"""Storage module for CLI-CIH."""

from cli_cih.storage.config import ConfigStorage, get_config, save_config
from cli_cih.storage.history import HistoryStorage, get_history_storage
from cli_cih.storage.models import (
    HistoryMessage,
    SenderType,
    Session,
    SessionResult,
    SessionStatus,
)

__all__ = [
    # Config
    "ConfigStorage",
    "get_config",
    "save_config",
    # Models
    "Session",
    "SessionStatus",
    "HistoryMessage",
    "SessionResult",
    "SenderType",
    # History
    "HistoryStorage",
    "get_history_storage",
]
