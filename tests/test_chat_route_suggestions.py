import pytest

from app.application.services.chat_route_suggestions import model_parameter_size, suggest_route


def test_only_explicit_model_size_tokens_are_compared():
    assert model_parameter_size("llama3.2:3b") == 3
    assert model_parameter_size("qwen2.5:7b-instruct") == 7
    assert model_parameter_size("gemini-2.5-flash") is None


def test_simple_prompt_keeps_default_and_complex_prompt_gets_nonbinding_hint():
    installed = ("llama3.2:3b", "qwen2.5:7b", "qwen2.5:14b")
    simple = suggest_route("What is the capital of Japan?", "llama3.2:3b", installed)
    assert simple.complexity == "simple"
    assert simple.suggested_model is None

    complex_result = suggest_route("Compare the options and explain trade-offs.",
                                   "llama3.2:3b", installed)
    assert complex_result.complexity == "complex"
    assert complex_result.suggested_model == "qwen2.5:7b"
    assert "uncertain" in complex_result.reason
    assert "hardware-fit" in complex_result.reason

    uncertain = suggest_route("Describe the current configuration in a neutral and fairly detailed way without requesting a recommendation, comparison, or implementation action, and focus only on what is already present.",
                              "llama3.2:3b", installed)
    assert uncertain.complexity == "unknown"
    assert uncertain.suggested_model is None
    assert "keep the configured model" in uncertain.reason


def test_unknown_model_sizes_never_claim_a_larger_alternative():
    result = suggest_route("Design a migration plan", "custom-local-model",
                           ("another-custom-model",))
    assert result.complexity == "complex"
    assert result.suggested_model is None
    partially_known = suggest_route("Design a migration plan", "custom-local-model",
                                    ("qwen2.5:7b",))
    assert partially_known.suggested_model is None


def test_prompt_and_inventory_are_bounded():
    with pytest.raises(ValueError, match="limits"):
        suggest_route("x" * 8193, "llama3.2:3b", ())
    with pytest.raises(TypeError, match="immutable"):
        suggest_route("hello", "llama3.2:3b", ["qwen:7b"])
