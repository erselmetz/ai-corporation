"""Deterministic, fail-closed chat routing over already-authorized capabilities."""
from __future__ import annotations

from dataclasses import dataclass
import re


_GREETING = re.compile(r"^(?:hi|hello|hey|good morning|good afternoon|good evening|kumusta|kamusta)(?:[!.?\s].*)?$", re.I)
_BRAIN_CUE = re.compile(r"\b(?:brain|notes?|knowledge|files?|documents?|my records)\b", re.I)
_UNSUPPORTED_CUES = {
    "web": re.compile(r"\b(?:web|internet|browse|search online)\b", re.I),
    "screen": re.compile(r"\b(?:screen|camera|screenshot|see my desktop)\b", re.I),
    "code": re.compile(r"\b(?:code|open a terminal|shell command)\b", re.I),
}
_SUPPORTED_TOOLS = frozenset({"calculator", "local-document-lookup"})


@dataclass(frozen=True, slots=True)
class ChatRouteDecision:
    mode: str
    capability: str
    reason: str
    fallback: bool = False

    def as_trace(self) -> dict:
        return {"mode": self.mode, "capability": self.capability,
                "reason": self.reason, "fallback": self.fallback}


def classify_chat_route(text: str, *, brain_selected: bool = False,
                        reviewed_tools: tuple[str, ...] = (),
                        delegation_selected: bool = False) -> ChatRouteDecision:
    """Select only existing paths explicitly selected or already previewed by the owner.

    The router never treats a text mention as permission. Web, screen, and code
    execution are not available as automatic chat tools and therefore fall back
    to an ordinary Coordinator answer.
    """
    if not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > 8192:
        raise ValueError("Chat routing requires bounded user text")
    if (type(brain_selected) is not bool or type(delegation_selected) is not bool
            or not isinstance(reviewed_tools, tuple)):
        raise ValueError("Chat routing inputs are invalid")
    if any(not isinstance(item, str) for item in reviewed_tools):
        raise ValueError("Chat routing tool selection is invalid")

    normalized = text.strip()
    unknown = set(reviewed_tools) - _SUPPORTED_TOOLS
    if unknown:
        return ChatRouteDecision("direct_fallback", "none", "unsupported_selected_tool", True)
    if reviewed_tools:
        return ChatRouteDecision("agentic", "reviewed_read_tool", "owner_selected_supported_tool")
    if delegation_selected:
        return ChatRouteDecision("agentic", "delegation", "owner_confirmed_delegation")

    for capability, pattern in _UNSUPPORTED_CUES.items():
        if pattern.search(normalized):
            return ChatRouteDecision("direct_fallback", "none", f"{capability}_tool_unavailable", True)
    if brain_selected:
        return ChatRouteDecision("agentic", "brain", "owner_selected_brain")
    if _GREETING.fullmatch(normalized):
        return ChatRouteDecision("direct", "none", "greeting")
    if _BRAIN_CUE.search(normalized):
        return ChatRouteDecision("direct_fallback", "none", "brain_selection_required", True)
    return ChatRouteDecision("direct", "none", "ordinary_chat")


def classify_chat_route_safely(text: str, *, brain_selected: bool = False,
                               reviewed_tools: tuple[str, ...] = (),
                               delegation_selected: bool = False) -> ChatRouteDecision:
    """A broken classifier cannot prevent a normal direct response."""
    try:
        return classify_chat_route(text, brain_selected=brain_selected,
                                   reviewed_tools=reviewed_tools,
                                   delegation_selected=delegation_selected)
    except Exception:
        return ChatRouteDecision("direct_fallback", "none", "classifier_failed", True)
