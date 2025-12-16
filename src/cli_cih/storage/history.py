"""SQLite history storage for CLI-CIH."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from cli_cih.storage.models import (
    HistoryMessage,
    SenderType,
    Session,
    SessionResult,
    SessionStatus,
)

# Default data directory
DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "cli-cih"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "history.db"


class HistoryStorage:
    """SQLite-based history storage for conversation sessions."""

    def __init__(self, db_path: str | None = None):
        """Initialize history storage.

        Args:
            db_path: Path to SQLite database file.
        """
        if db_path:
            self.db_path = Path(db_path).expanduser()
        else:
            self.db_path = DEFAULT_DB_PATH

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_query TEXT NOT NULL,
                    task_type TEXT DEFAULT 'general',
                    participating_ais TEXT,
                    total_rounds INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'in_progress',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    sender_type TEXT NOT NULL,
                    sender_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    round_num INTEGER DEFAULT 0,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS results (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL UNIQUE,
                    summary TEXT NOT NULL,
                    key_points TEXT,
                    consensus_reached INTEGER DEFAULT 0,
                    confidence REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at);
                CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
                CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
                CREATE INDEX IF NOT EXISTS idx_results_session_id ON results(session_id);
            """)

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def save_session(self, session: Session) -> str:
        """Save a session to the database.

        Args:
            session: Session to save.

        Returns:
            Session ID.
        """
        with self._get_connection() as conn:
            # Insert or update session
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions (
                    id, user_query, task_type, participating_ais,
                    total_rounds, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    session.id,
                    session.user_query,
                    session.task_type,
                    json.dumps(session.participating_ais),
                    session.total_rounds,
                    session.status.value,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                ),
            )

            # Save messages
            for msg in session.messages:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO messages (
                        id, session_id, sender_type, sender_id,
                        content, round_num, metadata, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        msg.id,
                        msg.session_id,
                        msg.sender_type.value,
                        msg.sender_id,
                        msg.content,
                        msg.round_num,
                        json.dumps(msg.metadata),
                        msg.created_at.isoformat(),
                    ),
                )

            # Save result if exists
            if session.result:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO results
                    (id, session_id, summary, key_points, consensus_reached, confidence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        session.result.id,
                        session.result.session_id,
                        session.result.summary,
                        json.dumps(session.result.key_points),
                        1 if session.result.consensus_reached else 0,
                        session.result.confidence,
                        session.result.created_at.isoformat(),
                    ),
                )

            conn.commit()

        return session.id

    async def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID.

        Args:
            session_id: Session ID.

        Returns:
            Session if found, None otherwise.
        """
        with self._get_connection() as conn:
            # Get session
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()

            if not row:
                return None

            session = self._row_to_session(row)

            # Get messages
            messages = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at", (session_id,)
            ).fetchall()

            session.messages = [self._row_to_message(m) for m in messages]

            # Get result
            result_row = conn.execute(
                "SELECT * FROM results WHERE session_id = ?", (session_id,)
            ).fetchone()

            if result_row:
                session.result = self._row_to_result(result_row)

            return session

    async def get_recent(self, limit: int = 10, offset: int = 0) -> list[Session]:
        """Get recent sessions.

        Args:
            limit: Maximum number of sessions to return.
            offset: Number of sessions to skip.

        Returns:
            List of sessions (without messages loaded).
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM sessions
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """,
                (limit, offset),
            ).fetchall()

            return [self._row_to_session(row) for row in rows]

    async def search(self, query: str, limit: int = 20) -> list[Session]:
        """Search sessions by query content.

        Args:
            query: Search query.
            limit: Maximum results.

        Returns:
            List of matching sessions.
        """
        search_pattern = f"%{query}%"

        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT s.* FROM sessions s
                LEFT JOIN messages m ON s.id = m.session_id
                LEFT JOIN results r ON s.id = r.session_id
                WHERE s.user_query LIKE ?
                   OR m.content LIKE ?
                   OR r.summary LIKE ?
                ORDER BY s.created_at DESC
                LIMIT ?
            """,
                (search_pattern, search_pattern, search_pattern, limit),
            ).fetchall()

            return [self._row_to_session(row) for row in rows]

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and all related data.

        Args:
            session_id: Session ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0

    async def get_stats(self) -> dict:
        """Get storage statistics.

        Returns:
            Dictionary with stats.
        """
        with self._get_connection() as conn:
            total_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]

            completed_sessions = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE status = ?", (SessionStatus.COMPLETED.value,)
            ).fetchone()[0]

            total_messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

            # AI usage stats
            ai_usage = {}
            rows = conn.execute("SELECT participating_ais FROM sessions").fetchall()

            for row in rows:
                ais = json.loads(row[0] or "[]")
                for ai in ais:
                    ai_usage[ai] = ai_usage.get(ai, 0) + 1

            return {
                "total_sessions": total_sessions,
                "completed_sessions": completed_sessions,
                "total_messages": total_messages,
                "ai_usage": ai_usage,
                "db_path": str(self.db_path),
            }

    async def export_session(
        self,
        session_id: str,
        format: str = "md",
    ) -> str | None:
        """Export a session in the specified format.

        Args:
            session_id: Session ID to export.
            format: Export format ('md', 'json', 'txt').

        Returns:
            Exported content string, or None if session not found.
        """
        session = await self.get_session(session_id)
        if not session:
            return None

        if format == "json":
            return self._export_json(session)
        elif format == "txt":
            return self._export_txt(session)
        else:  # Default to markdown
            return self._export_markdown(session)

    def _export_markdown(self, session: Session) -> str:
        """Export session as markdown."""
        lines = [
            "# CLI-CIH Discussion",
            "",
            f"**Date:** {session.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**AIs:** {', '.join(session.participating_ais)}",
            f"**Rounds:** {session.total_rounds}",
            f"**Status:** {session.status.value}",
            "",
            "## Question",
            "",
            f"{session.user_query}",
            "",
            "## Discussion",
            "",
        ]

        current_round = 0
        for msg in session.messages:
            if msg.round_num != current_round:
                current_round = msg.round_num
                lines.append(f"### Round {current_round}")
                lines.append("")

            if msg.sender_type == SenderType.USER:
                lines.append(f"**User:** {msg.content}")
            elif msg.sender_type == SenderType.AI:
                lines.append(f"**{msg.sender_id.upper()}:** {msg.content}")
            else:
                lines.append(f"*{msg.content}*")

            lines.append("")

        if session.result:
            lines.extend(
                [
                    "## Result",
                    "",
                    f"{session.result.summary}",
                    "",
                ]
            )

            if session.result.key_points:
                lines.append("**Key Points:**")
                for point in session.result.key_points:
                    lines.append(f"- {point}")
                lines.append("")

        return "\n".join(lines)

    def _export_json(self, session: Session) -> str:
        """Export session as JSON."""
        data = {
            "id": session.id,
            "user_query": session.user_query,
            "task_type": session.task_type,
            "participating_ais": session.participating_ais,
            "total_rounds": session.total_rounds,
            "status": session.status.value,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "messages": [
                {
                    "sender_type": m.sender_type.value,
                    "sender_id": m.sender_id,
                    "content": m.content,
                    "round_num": m.round_num,
                    "created_at": m.created_at.isoformat(),
                }
                for m in session.messages
            ],
        }

        if session.result:
            data["result"] = {
                "summary": session.result.summary,
                "key_points": session.result.key_points,
                "consensus_reached": session.result.consensus_reached,
                "confidence": session.result.confidence,
            }

        return json.dumps(data, indent=2, ensure_ascii=False)

    def _export_txt(self, session: Session) -> str:
        """Export session as plain text."""
        lines = [
            f"CLI-CIH Discussion - {session.created_at.strftime('%Y-%m-%d %H:%M')}",
            "=" * 60,
            f"Question: {session.user_query}",
            f"AIs: {', '.join(session.participating_ais)}",
            "-" * 60,
        ]

        for msg in session.messages:
            if msg.sender_type == SenderType.AI:
                lines.append(f"[{msg.sender_id.upper()}] {msg.content}")
            elif msg.sender_type == SenderType.USER:
                lines.append(f"[USER] {msg.content}")

        if session.result:
            lines.extend(
                [
                    "-" * 60,
                    "Result:",
                    session.result.summary,
                ]
            )

        return "\n".join(lines)

    def _row_to_session(self, row: sqlite3.Row) -> Session:
        """Convert database row to Session object."""
        return Session(
            id=row["id"],
            user_query=row["user_query"],
            task_type=row["task_type"],
            participating_ais=json.loads(row["participating_ais"] or "[]"),
            total_rounds=row["total_rounds"],
            status=SessionStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _row_to_message(self, row: sqlite3.Row) -> HistoryMessage:
        """Convert database row to HistoryMessage object."""
        return HistoryMessage(
            id=row["id"],
            session_id=row["session_id"],
            sender_type=SenderType(row["sender_type"]),
            sender_id=row["sender_id"],
            content=row["content"],
            round_num=row["round_num"],
            metadata=json.loads(row["metadata"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _row_to_result(self, row: sqlite3.Row) -> SessionResult:
        """Convert database row to SessionResult object."""
        return SessionResult(
            id=row["id"],
            session_id=row["session_id"],
            summary=row["summary"],
            key_points=json.loads(row["key_points"] or "[]"),
            consensus_reached=bool(row["consensus_reached"]),
            confidence=row["confidence"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )


# Global history storage instance
_history_storage: HistoryStorage | None = None


def get_history_storage() -> HistoryStorage:
    """Get global history storage instance."""
    global _history_storage
    if _history_storage is None:
        _history_storage = HistoryStorage()
    return _history_storage
