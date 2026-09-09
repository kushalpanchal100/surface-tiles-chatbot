import threading
import logging
from collections import OrderedDict, deque
from typing import List, Optional

from config.settings import settings
from api.schemas import ChatMessage

logger = logging.getLogger(__name__)


class ChatSessionManager:
    """
    Thread-safe in-memory session manager that maintains the last N messages
    (default: 10) per active conversation session.
    """

    def __init__(self, max_history: Optional[int] = None, max_sessions: int = 5000):
        self.max_history = max_history if max_history is not None else getattr(settings, "max_chat_history", 10)
        self.max_sessions = max_sessions
        self._lock = threading.Lock()
        # OrderedDict mapping session_id -> deque of ChatMessage
        self._sessions: OrderedDict[str, deque] = OrderedDict()

    def get_history(self, session_id: str) -> List[ChatMessage]:
        """Retrieve recent chat history for the given session ID (up to max_history)."""
        if not session_id:
            return []
        with self._lock:
            if session_id in self._sessions:
                # Mark as recently used
                self._sessions.move_to_end(session_id)
                return list(self._sessions[session_id])
            return []

    def add_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str
    ) -> List[ChatMessage]:
        """
        Append a user message and an assistant response turn to the session,
        keeping only the last max_history (10) messages.
        """
        if not session_id:
            return []

        with self._lock:
            if session_id not in self._sessions:
                # Evict oldest session if capacity reached
                if len(self._sessions) >= self.max_sessions:
                    oldest, _ = self._sessions.popitem(last=False)
                    logger.debug(f"Evicted oldest session {oldest} from session manager.")
                self._sessions[session_id] = deque(maxlen=self.max_history)

            q = self._sessions[session_id]
            q.append(ChatMessage(role="user", content=user_message))
            q.append(ChatMessage(role="assistant", content=assistant_response))
            self._sessions.move_to_end(session_id)
            return list(q)

    def set_history(self, session_id: str, messages: List[ChatMessage]) -> List[ChatMessage]:
        """Explicitly set or overwrite the history for a session (clamped to max_history)."""
        if not session_id:
            return []

        with self._lock:
            if session_id not in self._sessions and len(self._sessions) >= self.max_sessions:
                self._sessions.popitem(last=False)

            q = deque(maxlen=self.max_history)
            for m in messages[-self.max_history:]:
                q.append(m)
            self._sessions[session_id] = q
            self._sessions.move_to_end(session_id)
            return list(q)

    def clear_session(self, session_id: str) -> bool:
        """Clear history for a given session ID."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def get_session_count(self) -> int:
        """Return the number of active sessions currently in memory."""
        with self._lock:
            return len(self._sessions)


# Global singleton instance
session_manager = ChatSessionManager()
