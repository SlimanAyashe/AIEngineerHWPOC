"""Minimal schema validation for tool inputs.

The same schema object that validates inputs also describes the tool in the
MCP-style manifest (``registry.manifest``) -- one source of truth for both
discovery and validation. In production you would back this with pydantic or
JSON Schema; the shape here deliberately mirrors that so the swap is trivial.
"""
from __future__ import annotations
import re

from .errors import ValidationError


def validate(schema: dict, raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValidationError(
            "Arguments must be an object",
            details={"received_type": type(raw).__name__},
        )

    cleaned: dict = {}
    errors: dict[str, str] = {}

    # Reject unexpected fields -- defense against argument injection from the model.
    for key in raw:
        if key not in schema:
            errors[key] = "unexpected field"

    for name, spec in schema.items():
        present = name in raw and raw[name] is not None
        if not present:
            if spec.get("required"):
                errors[name] = "required"
            continue

        value = raw[name]
        expected = spec.get("type", "string")

        if expected == "string":
            if not isinstance(value, str):
                errors[name] = "must be a string"
                continue
            value = value.strip()
            if "min_length" in spec and len(value) < spec["min_length"]:
                errors[name] = f"must be at least {spec['min_length']} characters"
                continue
            if "max_length" in spec and len(value) > spec["max_length"]:
                errors[name] = f"must be at most {spec['max_length']} characters"
                continue
            if "pattern" in spec and not re.fullmatch(spec["pattern"], value):
                errors[name] = f"must match pattern {spec['pattern']}"
                continue
        elif expected == "number":
            # bool is a subclass of int -- exclude it explicitly.
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors[name] = "must be a number"
                continue
            if "min" in spec and value < spec["min"]:
                errors[name] = f"must be >= {spec['min']}"
                continue

        cleaned[name] = value

    if errors:
        raise ValidationError("Input validation failed", details={"fields": errors})
    return cleaned
