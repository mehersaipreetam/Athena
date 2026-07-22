"""
Athena Unified Memory Engine - Single-file memory system.
Combines: vector/keyword memory, conversation history, relationship memory, mood context.
Lightweight SQLite backend with auto-consolidation and pruning.
"""
import sqlite3
import json
import time
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from contextlib import contextmanager
import logging

from athena.config import config

logger = logging.getLogger(__name__)


@dataclass
class Memory:
    """Unified memory entry."""
    id: Optional[int] = None
    type: str = "fact"  # fact, preference, conversation, skill_usage, reflection
    content: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_accessed: float = 0.0


@dataclass
class ConversationTurn:
    """A single conversation exchange."""
    session_id: str
    user_input: str
    assistant_response: str
    timestamp: float
    sentiment: str = "neutral"
    skills_used: List[str] = field(default_factory=list)


@dataclass
class UserProfile:
    """Aggregated user profile from memory."""
    name: str = "Sir"
    preferences: Dict[str, str] = field(default_factory=dict)
    frequent_topics: List[str] = field(default_factory=list)
    interaction_count: int = 0
    last_interaction: float = 0
    sentiment_trend: str = "neutral"


class MemoryEngine:
    """
    Unified memory engine with:
    - Keyword-based search (SQLite FTS5 would be better but adds complexity)
    - Auto-consolidation of old conversations
    - Access tracking for LRU pruning
    - Thread-safe operations
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.memory_db
        self._lock = threading.RLock()
        self._init_db()
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def _init_db(self):
        """Initialize database schema."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT,  -- JSON array
                    metadata TEXT,  -- JSON object
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    last_accessed REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_input TEXT NOT NULL,
                    assistant_response TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    sentiment TEXT DEFAULT 'neutral',
                    skills_used TEXT  -- JSON array
                );

                CREATE TABLE IF NOT EXISTS skills_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_name TEXT NOT NULL,
                    invoked_at REAL NOT NULL,
                    success BOOLEAN NOT NULL,
                    args_hash TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type);
                CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
                CREATE INDEX IF NOT EXISTS idx_memories_accessed ON memories(last_accessed);
                CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
                CREATE INDEX IF NOT EXISTS idx_conversations_time ON conversations(timestamp);
                CREATE INDEX IF NOT EXISTS idx_skills_usage_name ON skills_usage(skill_name);
                CREATE INDEX IF NOT EXISTS idx_skills_usage_time ON skills_usage(invoked_at);
            """)

    @contextmanager
    def _get_conn(self):
        """Thread-safe connection with WAL mode for better concurrency."""
        with self._lock:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    # ==================== Core Memory Operations ====================

    def remember(
        self,
        content: str,
        type: str = "fact",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Store a new memory."""
        tags_json = json.dumps(tags or [])
        metadata_json = json.dumps(metadata or {})
        now = time.time()

        with self._get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO memories (type, content, tags, metadata, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (type, content, tags_json, metadata_json, now, now)
            )
            return cursor.lastrowid

    def recall(
        self,
        query: str,
        types: Optional[List[str]] = None,
        limit: int = 5,
        min_score: int = 1
    ) -> List[Memory]:
        limit = int(limit) if limit is not None else 5
        query_words = [w.lower() for w in query.split() if len(w) > 2]
        if not query_words:
            query_words = [query.lower()]

        type_filter = ""
        params = []
        if types:
            placeholders = ",".join("?" * len(types))
            type_filter = f"AND type IN ({placeholders})"
            params.extend(types)

        with self._get_conn() as conn:
            rows = conn.execute(
                f"""SELECT id, type, content, tags, metadata, created_at, updated_at,
                           access_count, last_accessed
                    FROM memories
                    WHERE 1=1 {type_filter}
                    ORDER BY created_at DESC""",
                params
            ).fetchall()

        # Score and filter results
        scored = []
        for row in rows:
            tags = json.loads(row["tags"] or "[]")
            metadata = json.loads(row["metadata"] or "{}")
            text_to_search = f"{row['type']} {row['content']} {' '.join(tags)}".lower()

            score = sum(1 for word in query_words if word in text_to_search)
            if score >= min_score:
                scored.append((score, Memory(
                    id=row["id"],
                    type=row["type"],
                    content=row["content"],
                    tags=tags,
                    metadata=metadata,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    access_count=row["access_count"],
                    last_accessed=row["last_accessed"]
                )))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [m for _, m in scored[:limit]]

        # Update access stats
        if results:
            self._update_access([m.id for m in results])

        return results

    def _update_access(self, memory_ids: List[int]):
        """Update access count and last_accessed for memories."""
        if not memory_ids:
            return
        placeholders = ",".join("?" * len(memory_ids))
        now = time.time()
        with self._get_conn() as conn:
            conn.execute(
                f"""UPDATE memories
                    SET access_count = access_count + 1, last_accessed = ?
                    WHERE id IN ({placeholders})""",
                [now] + memory_ids
            )

    def get_context(self, query: str, max_tokens: int = 2000) -> str:
        """Get relevant memories formatted for LLM context."""
        memories = self.recall(query, limit=10)
        if not memories:
            return ""

        lines = ["[RELEVANT MEMORIES]"]
        token_estimate = 0
        for m in memories:
            entry = f"- [{m.type}] {m.content}"
            if m.tags:
                entry += f" (tags: {', '.join(m.tags)})"
            # Rough token estimate: 1 token ≈ 4 chars
            entry_tokens = len(entry) // 4
            if token_estimate + entry_tokens > max_tokens:
                break
            lines.append(entry)
            token_estimate += entry_tokens

        return "\n".join(lines)

    # ==================== Conversation History ====================

    def record_interaction(
        self,
        user_input: str,
        assistant_response: str,
        sentiment: str = "neutral",
        skills_used: Optional[List[str]] = None
    ):
        """Record a conversation turn."""
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO conversations
                   (session_id, user_input, assistant_response, timestamp, sentiment, skills_used)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (self._session_id, user_input, assistant_response,
                 time.time(), sentiment, json.dumps(skills_used or []))
            )

    def get_recent_conversations(self, limit: int = 10) -> List[ConversationTurn]:
        """Get recent conversation history."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT session_id, user_input, assistant_response, timestamp, sentiment, skills_used
                   FROM conversations
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (limit,)
            ).fetchall()

        return [ConversationTurn(
            session_id=row["session_id"],
            user_input=row["user_input"],
            assistant_response=row["assistant_response"],
            timestamp=row["timestamp"],
            sentiment=row["sentiment"],
            skills_used=json.loads(row["skills_used"] or "[]")
        ) for row in reversed(rows)]

    # ==================== User Profile ====================

    def get_user_profile(self) -> UserProfile:
        """Build user profile from memories and conversations."""
        with self._get_conn() as conn:
            # Get preferences
            pref_rows = conn.execute(
                "SELECT content, tags FROM memories WHERE type = 'preference'"
            ).fetchall()

            preferences = {}
            for row in pref_rows:
                tags = json.loads(row["tags"] or "[]")
                for tag in tags:
                    preferences[tag] = row["content"]

            # Get interaction stats
            stats = conn.execute(
                """SELECT COUNT(*) as cnt, MAX(timestamp) as last_ts, sentiment
                   FROM conversations
                   GROUP BY sentiment"""
            ).fetchall()

            interaction_count = sum(r["cnt"] for r in stats)
            last_interaction = max((r["last_ts"] for r in stats), default=0)
            sentiments = {r["sentiment"]: r["cnt"] for r in stats}
            sentiment_trend = max(sentiments, key=sentiments.get) if sentiments else "neutral"

            # Get frequent topics from conversation
            topic_rows = conn.execute(
                """SELECT user_input FROM conversations ORDER BY timestamp DESC LIMIT 50"""
            ).fetchall()

        # Simple topic extraction from recent inputs
        topics = []
        for row in topic_rows:
            words = [w.lower() for w in row["user_input"].split() if len(w) > 4]
            topics.extend(words[:3])

        from collections import Counter
        freq_topics = [t for t, _ in Counter(topics).most_common(5)]

        return UserProfile(
            name=config.user_name,
            preferences=preferences,
            frequent_topics=freq_topics,
            interaction_count=interaction_count,
            last_interaction=last_interaction,
            sentiment_trend=sentiment_trend
        )

    def update_preference(self, key: str, value: str):
        """Store or update a user preference."""
        # Check if exists
        existing = self.recall(key, types=["preference"], limit=1)
        if existing:
            # Update
            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE memories SET content = ?, updated_at = ? WHERE id = ?",
                    (value, time.time(), existing[0].id)
                )
        else:
            # Create new
            self.remember(value, type="preference", tags=[key])

    # ==================== Skill Usage Tracking ====================

    def record_skill_usage(self, skill_name: str, success: bool, args: Dict = None):
        """Track skill invocation for analytics and pruning."""
        args_hash = str(hash(json.dumps(args or {}, sort_keys=True)))
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO skills_usage (skill_name, invoked_at, success, args_hash)
                   VALUES (?, ?, ?, ?)""",
                (skill_name, time.time(), success, args_hash)
            )

    def get_skill_stats(self, days: int = 30) -> Dict[str, Dict]:
        """Get usage statistics for skills."""
        cutoff = time.time() - (days * 86400)
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT skill_name,
                          COUNT(*) as total_calls,
                          SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
                          MAX(invoked_at) as last_used
                   FROM skills_usage
                   WHERE invoked_at > ?
                   GROUP BY skill_name""",
                (cutoff,)
            ).fetchall()

        return {
            row["skill_name"]: {
                "total_calls": row["total_calls"],
                "successes": row["successes"],
                "success_rate": row["successes"] / row["total_calls"] if row["total_calls"] > 0 else 0,
                "last_used": row["last_used"]
            }
            for row in rows
        }

    def get_unused_skills(self, days: int = 30) -> List[str]:
        """Get skills not used in N days."""
        cutoff = time.time() - (days * 86400)
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT DISTINCT skill_name
                   FROM skills_usage
                   WHERE invoked_at < ?
                   AND skill_name NOT IN (
                       SELECT skill_name FROM skills_usage WHERE invoked_at >= ?
                   )""",
                (cutoff, cutoff)
            ).fetchall()
        return [row["skill_name"] for row in rows]

    # ==================== Maintenance ====================

    def consolidate(self, days: int = None):
        """Consolidate old conversations into summary memories."""
        days = days or config.memory_consolidate_days
        cutoff = time.time() - (days * 86400)

        with self._get_conn() as conn:
            # Get old conversations not yet consolidated
            rows = conn.execute(
                """SELECT id, user_input, assistant_response, timestamp
                   FROM conversations
                   WHERE timestamp < ?
                   ORDER BY timestamp""",
                (cutoff,)
            ).fetchall()

            if not rows:
                return 0

            # Group by day and create summaries
            from collections import defaultdict
            by_day = defaultdict(list)
            for row in rows:
                day = datetime.fromtimestamp(row["timestamp"]).strftime("%Y-%m-%d")
                by_day[day].append((row["id"], f"User: {row['user_input']}\nAthena: {row['assistant_response']}"))

            created = 0
            for day, exchanges in by_day.items():
                # Check if a summary for this date already exists
                existing = conn.execute(
                    "SELECT 1 FROM memories WHERE type = 'conversation_summary' AND metadata LIKE ?",
                    (f'%"{day}"%',)
                ).fetchone()
                
                if existing:
                    continue

                ids = [ex[0] for ex in exchanges]
                texts = [ex[1] for ex in exchanges]

                summary = f"Conversation summary for {day}:\n" + "\n---\n".join(texts[-10:])
                self.remember(
                    summary,
                    type="conversation_summary",
                    tags=["conversation", "summary", day],
                    metadata={"date": day, "exchange_count": len(exchanges), "min_id": min(ids), "max_id": max(ids)}
                )
                created += 1

            logger.info(f"[MEMORY] Consolidated {created} daily summaries")
            return created

    def prune_old_memories(self, max_entries: int = None, max_age_days: int = 90):
        """Remove old, rarely accessed memories."""
        max_entries = config.memory_max_entries if max_entries is None else max_entries
        cutoff = time.time() - (max_age_days * 86400)

        with self._get_conn() as conn:
            # Count total
            total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            if total <= max_entries:
                return 0

            # Delete oldest, least accessed memories beyond limit
            # Keep: preferences, recent, highly accessed
            deleted = conn.execute(
                """DELETE FROM memories
                   WHERE id IN (
                       SELECT id FROM memories
                       WHERE type NOT IN ('preference', 'conversation_summary')
                       AND created_at < ?
                       ORDER BY access_count ASC, last_accessed ASC
                       LIMIT ?
                   )""",
                (cutoff, total - max_entries)
            ).rowcount

            if deleted:
                logger.info(f"[MEMORY] Pruned {deleted} old memories")
            return deleted

    def vacuum(self):
        """Reclaim disk space."""
        with self._get_conn() as conn:
            conn.execute("VACUUM")

    def get_stats(self) -> Dict[str, Any]:
        """Get memory engine statistics."""
        with self._get_conn() as conn:
            mem_count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            conv_count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
            skill_count = conn.execute("SELECT COUNT(DISTINCT skill_name) FROM skills_usage").fetchone()[0]

            type_dist = dict(conn.execute(
                "SELECT type, COUNT(*) FROM memories GROUP BY type"
            ).fetchall())

            db_size = Path(self.db_path).stat().st_size / 1024 / 1024

        return {
            "total_memories": mem_count,
            "total_conversations": conv_count,
            "tracked_skills": skill_count,
            "memory_by_type": type_dist,
            "db_size_mb": round(db_size, 2),
            "session_id": self._session_id
        }