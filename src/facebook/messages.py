"""Deterministic classification/summarisation of Page messages."""

from __future__ import annotations

_SPAM_WORDS = (
    "buy now", "click here", "free money", "earn money", "crypto",
    "bitcoin giveaway", "guaranteed profit", "investment opportunity",
    "discount code", "promo code", "http://", "https://", "www.",
    "dm me", "whatsapp me", "telegram me",
)
_INQUIRY_WORDS = (
    "price", "cost", "quote", "book", "hire", "order", "subscribe",
    "sign up", "enquiry", "enquire", "interested", "available",
    "how much", "where can i buy", "want to buy", "contact",
)
_FEEDBACK_WORDS = (
    "thank", "great", "excellent", "amazing", "love", "well done",
    "helpful", "informative", "terrible", "awful", "worst", "disappointed",
    "complaint", "feedback", "suggestion",
)
_QUESTION_WORDS = (
    "?", "how do", "how can", "what is", "what are", "when will",
    "where can", "can you", "could you", "why does", "why is",
    "is it possible", "does anyone know",
)


def classify_message(text: str) -> str:
    """Classify a message as question, inquiry, feedback, spam or other."""
    lowered = (text or "").strip().lower()
    if not lowered:
        return "other"
    if any(word in lowered for word in _SPAM_WORDS):
        return "spam"
    if any(word in lowered for word in _INQUIRY_WORDS):
        return "inquiry"
    if any(word in lowered for word in _QUESTION_WORDS):
        return "question"
    if any(word in lowered for word in _FEEDBACK_WORDS):
        return "feedback"
    return "other"


def summarize_conversations(conversations: list) -> list[dict]:
    """Summarise raw conversation dicts for monitoring output.

    Each input dict may carry ``id``, ``snippet``/``message``/``messages``,
    and ``unread``/``unread_count``. Returns a list of dicts with keys
    ``id``, ``snippet``, ``unread`` and ``classification``.
    """
    summaries: list[dict] = []
    for conv in conversations or []:
        if not isinstance(conv, dict):
            continue
        snippet = str(
            conv.get("snippet")
            or conv.get("message")
            or conv.get("last_message")
            or ""
        )
        # Some Graph responses nest messages under data.
        if not snippet:
            messages = conv.get("messages") or {}
            data = messages.get("data") if isinstance(messages, dict) else None
            if data:
                snippet = str(data[-1].get("message", "")) if data else ""
        snippet = snippet[:200]
        unread = bool(conv.get("unread") or conv.get("unread_count"))
        summaries.append(
            {
                "id": str(conv.get("id", "")),
                "snippet": snippet,
                "unread": unread,
                "classification": classify_message(snippet),
            }
        )
    return summaries
