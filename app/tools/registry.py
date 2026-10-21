from copy import deepcopy
import re

from .base import TOOL_RISK_CLASSES, Tool

class ToolRegistry:
    """
    Registry for managing available tools in the Corporation.
    """
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Registers a tool in the registry."""
        if not isinstance(tool, Tool):
            raise TypeError("Only Tool instances can be registered")
        
        if tool.id in self._tools:
            raise ValueError(f"Tool already registered: {tool.id}")
            
        self._tools[tool.id] = tool

    def get(self, tool_id: str) -> Tool:
        """Retrieves a tool by its ID."""
        try:
            return self._tools[tool_id]
        except KeyError:
            raise ValueError(f"Tool not found: {tool_id}")

    def exists(self, tool_id: str) -> bool:
        """Checks if a tool exists in the registry."""
        return tool_id in self._tools

    def all(self) -> list[Tool]:
        """Returns all registered tools."""
        return list(self._tools.values())

    def risk_class(self, tool_id: str) -> str:
        """Unknown/malformed risk metadata is treated as the highest risk."""
        tool = self.get(tool_id)
        risk = getattr(tool, "risk_class", None)
        return risk if isinstance(risk, str) and risk in TOOL_RISK_CLASSES else "control"

    def describe(self, tool_id: str) -> dict:
        tool = self.get(tool_id)
        return {"id": tool.id, "name": tool.name, "description": tool.description[:512],
                "risk_class": self.risk_class(tool_id),
                "input_schema": deepcopy(tool.input_schema),
                "supports_dry_run": callable(getattr(tool, "dry_run", None)),
                "supports_undo": type(tool).undo is not Tool.undo}

    def validate_arguments(self, tool_id: str, arguments: dict) -> dict:
        """Validate the deliberately small JSON-schema subset used by Agents."""
        tool = self.get(tool_id)
        schema = tool.input_schema
        if (not isinstance(schema, dict) or schema.get("type") != "object"
                or schema.get("additionalProperties", True) is not False
                or not isinstance(schema.get("properties"), dict)
                or not isinstance(schema.get("required", []), list)
                or set(schema) - {"type", "properties", "required", "additionalProperties"}):
            raise ValueError("Registered tool schema is invalid; action denied")
        if (any(not isinstance(key, str) or not key for key in schema["properties"])
                or any(not isinstance(key, str) for key in schema.get("required", []))
                or len(set(schema.get("required", []))) != len(schema.get("required", []))):
            raise ValueError("Registered tool schema is invalid; action denied")
        if (not isinstance(arguments, dict) or set(arguments) - set(schema["properties"])
                or _contains_sensitive_key(arguments)):
            raise ValueError("Tool arguments do not match the registered schema")
        if any(key not in arguments for key in schema.get("required", [])):
            raise ValueError("Required tool argument is missing")
        for key, value in arguments.items():
            rule = schema["properties"].get(key)
            if (not isinstance(key, str) or not isinstance(rule, dict)
                    or set(rule) - {"type", "maxLength", "minimum", "maximum", "enum"}
                    or rule.get("type") not in {"string", "integer", "number", "boolean"}
                    or not _matches_type(value, rule.get("type"))):
                raise ValueError("Tool argument type does not match the registered schema")
            max_length = rule.get("maxLength", 8192)
            if type(max_length) is not int or not 0 <= max_length <= 8192:
                raise ValueError("Tool string limit is invalid")
            if isinstance(value, str) and len(value.encode("utf-8")) > max_length:
                raise ValueError("Tool argument exceeds the registered size limit")
            if type(value) in (int, float):
                lower, upper = rule.get("minimum", value), rule.get("maximum", value)
                if (type(lower) not in (int, float) or type(upper) not in (int, float)
                        or lower > upper or value < lower or value > upper):
                    raise ValueError("Tool argument is outside the registered numeric range")
            elif "minimum" in rule or "maximum" in rule:
                raise ValueError("Registered numeric range is invalid")
            if "enum" in rule and not isinstance(rule["enum"], list):
                raise ValueError("Registered enum constraint is invalid")
            if "enum" in rule and value not in rule["enum"]:
                raise ValueError("Tool argument is not an allowed value")
        return deepcopy(arguments)

    def preview(self, tool_id: str, arguments: dict) -> dict:
        validated = self.validate_arguments(tool_id, arguments)
        tool = self.get(tool_id)
        preview = tool.preview(validated)
        if not isinstance(preview, dict):
            raise ValueError("Tool preview is invalid; action denied")
        return preview


def _matches_type(value, expected):
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return type(value) is int
    if expected == "number":
        return type(value) in (int, float)
    if expected == "boolean":
        return type(value) is bool
    return False


def _contains_sensitive_key(value):
    if isinstance(value, dict):
        return any(re.search(r"(?i)(?:api[_-]?key|token|password|secret|credential)", str(key))
                   or _contains_sensitive_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False
