"""Deterministic comment classification for HeyMariner Facebook posts.

Keyword rules only -- no model calls -- so results are reproducible.
Order matters: spam and misinformation are checked before the
friendlier categories, so a spammy "question" is still spam.
"""

from __future__ import annotations

_SPAM_WORDS = (
    "buy now", "click here", "free money", "earn money", "make money fast",
    "crypto", "bitcoin giveaway", "double your", "limited offer",
    "discount code", "promo code", "visit my profile", "dm me for",
    "whatsapp me", "telegram me", "investment opportunity", "guaranteed profit",
    "http://", "https://", "www.", "check my bio",
)
_MISINFO_WORDS = (
    "fake news", "hoax", "conspiracy", "government cover up", "cover-up",
    "they are lying", "lie about", "false flag", "chemtrail",
    "flat earth", "not real", "staged",
)
_NEGATIVE_WORDS = (
    "terrible", "awful", "worst", "hate this", "disgusting", "useless",
    "scam", "fraud", "fake page", "unfollow", "disappointed", "angry",
    "rubbish", "horrible",
)
_POSITIVE_WORDS = (
    "great", "excellent", "amazing", "love this", "well done", "brilliant",
    "thank you", "thanks", "helpful", "informative", "interesting",
    "awesome", "fantastic", "good job", "nice work", "👍", "❤️", "👏",
)
_QUESTION_WORDS = (
    "?", "how do", "how can", "how much", "what is", "what are",
    "when will", "where can", "can you", "could you", "is it possible",
    "why does", "why is", "does anyone know",
)
_CUSTOMER_WORDS = (
    "price", "cost", "how much does", "where can i buy", "order",
    "subscribe", "sign up", "book", "hire", "quote", "enquiry", "enquire",
    "interested in", "want to buy", "available", "contact",
)
_MARITIME_WORDS = (
    "ship", "vessel", "port", "harbour", "harbor", "cargo", "container",
    "seafarer", "crew", "captain", "sailing", "maritime", "imo", "ais",
    "berth", "dock", "fleet", "shipping", "nautical", "offshore",
    "tanker", "bulk carrier", "ferry", "cruise", "anchor", "draft",
)

# Categories that get an automatic reply; everything else needs a human.
_REPLYABLE = {
    "genuine_question",
    "positive_feedback",
    "potential_customer_inquiry",
    "maritime_professional_discussion",
}


def classify_comment(text: str) -> str:
    """Classify a comment into one of the fixed categories."""
    lowered = (text or "").strip().lower()
    if not lowered:
        return "irrelevant"
    if any(word in lowered for word in _SPAM_WORDS):
        return "spam"
    if any(word in lowered for word in _MISINFO_WORDS):
        return "misinformation"
    is_question = any(word in lowered for word in _QUESTION_WORDS)
    is_customer = any(word in lowered for word in _CUSTOMER_WORDS)
    is_maritime = any(word in lowered for word in _MARITIME_WORDS)
    is_positive = any(word in lowered for word in _POSITIVE_WORDS)
    is_negative = any(word in lowered for word in _NEGATIVE_WORDS)

    if is_customer and (is_question or "interested" in lowered):
        return "potential_customer_inquiry"
    if is_question:
        return "genuine_question"
    if is_maritime and not is_negative:
        return "maritime_professional_discussion"
    if is_negative:
        return "negative_feedback"
    if is_positive:
        return "positive_feedback"
    if is_customer:
        return "potential_customer_inquiry"
    if len(lowered.split()) <= 2:
        return "irrelevant"
    return "irrelevant"


def should_reply(category: str) -> bool:
    """True only for categories safe to auto-reply to.

    Spam, negative feedback, misinformation and irrelevant comments
    need human review and must not be auto-replied to.
    """
    return category in _REPLYABLE
