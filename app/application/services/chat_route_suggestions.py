"""Conservative, local-only prompt complexity hints for optional route choices."""
from dataclasses import dataclass
import re


_COMPLEXITY_CUES = re.compile(
    r"\b(compare|analy[sz]e|debug|design|step[- ]by[- ]step|multiple|trade[- ]offs?|"
    r"architecture|investigate|evaluate|implement|plan)\b",
    re.IGNORECASE,
)
_MODEL_SIZE = re.compile(r"(?:^|[-_:])(\d+(?:\.\d+)?)b(?:$|[-_:])", re.IGNORECASE)


@dataclass(frozen=True)
class RouteSuggestion:
    complexity: str
    reason: str
    suggested_model: str | None


def model_parameter_size(model_id: str) -> float | None:
    """Read an explicit B-size token only; never infer compatibility or quality."""
    match = _MODEL_SIZE.search(model_id) if isinstance(model_id, str) else None
    return float(match.group(1)) if match else None


def suggest_route(prompt: str, current_model: str, installed_models: tuple[str, ...]) -> RouteSuggestion:
    """Suggest a larger named local model only for a conservative complexity cue.

    This deterministic hint runs locally and is not a model-quality or fit claim.
    """
    if not isinstance(prompt, str) or not isinstance(installed_models, tuple):
        raise TypeError("Prompt and immutable installed-model inventory are required")
    if len(prompt.encode("utf-8")) > 8192 or len(installed_models) > 100:
        raise ValueError("Routing suggestion input exceeds limits")
    if len(prompt) > 280 or _COMPLEXITY_CUES.search(prompt) is not None:
        complexity = "complex"
    elif len(prompt) <= 140:
        complexity = "simple"
    else:
        complexity = "unknown"
    if complexity == "simple":
        return RouteSuggestion("simple", "Simple-prompt heuristic; keep the configured local model.", None)
    if complexity == "unknown":
        return RouteSuggestion("unknown", "Prompt difficulty is uncertain; keep the configured model.", None)
    current_size = model_parameter_size(current_model)
    larger = sorted(
        ((model_parameter_size(model), model) for model in installed_models
         if model != current_model and current_size is not None
         and model_parameter_size(model) is not None
         and model_parameter_size(model) > current_size),
        key=lambda item: item[0],
    )
    return RouteSuggestion(
        "complex",
        "Complexity heuristic matched; difficulty is uncertain and this suggestion is not a quality or hardware-fit claim.",
        larger[0][1] if larger else None,
    )
