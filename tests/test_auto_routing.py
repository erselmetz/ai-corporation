from app.auto_routing import classify_chat_route, classify_chat_route_safely


def test_greetings_and_ordinary_chat_choose_direct_provider_response():
    assert classify_chat_route("hello").as_trace() == {
        "mode": "direct", "capability": "none", "reason": "greeting", "fallback": False,
    }
    assert classify_chat_route("What is a good way to organize my day?").mode == "direct"


def test_brain_and_reviewed_tool_routes_require_existing_owner_selected_paths():
    assert classify_chat_route("What did I write in my notes?").as_trace() == {
        "mode": "direct_fallback", "capability": "none",
        "reason": "brain_selection_required", "fallback": True,
    }
    assert classify_chat_route("What did I write in my notes?", brain_selected=True).as_trace() == {
        "mode": "agentic", "capability": "brain", "reason": "owner_selected_brain", "fallback": False,
    }
    assert classify_chat_route("Calculate 21 * 2", reviewed_tools=("calculator",)).as_trace() == {
        "mode": "agentic", "capability": "reviewed_read_tool",
        "reason": "owner_selected_supported_tool", "fallback": False,
    }
    assert classify_chat_route("Find a Researcher", delegation_selected=True).as_trace() == {
        "mode": "agentic", "capability": "delegation",
        "reason": "owner_confirmed_delegation", "fallback": False,
    }


def test_unsupported_web_screen_and_code_cues_fall_back_to_direct_without_action():
    for prompt, reason in (
        ("Search the web for the latest result", "web_tool_unavailable"),
        ("Read my screen", "screen_tool_unavailable"),
        ("Run this code", "code_tool_unavailable"),
    ):
        result = classify_chat_route(prompt).as_trace()
        assert result == {"mode": "direct_fallback", "capability": "none",
                          "reason": reason, "fallback": True}


def test_unknown_selected_tool_and_classifier_failure_fail_closed_to_direct(monkeypatch):
    assert classify_chat_route("Please help", reviewed_tools=("unknown",)).mode == "direct_fallback"

    def broken(*_args, **_kwargs):
        raise RuntimeError("sensitive provider text must not escape")

    import app.auto_routing as routing
    monkeypatch.setattr(routing, "classify_chat_route", broken)
    result = classify_chat_route_safely("hello").as_trace()
    assert result == {"mode": "direct_fallback", "capability": "none",
                      "reason": "classifier_failed", "fallback": True}
