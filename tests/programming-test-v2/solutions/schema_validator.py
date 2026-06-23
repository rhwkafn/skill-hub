"""
JSON Schema Validator — supports a useful subset of JSON Schema (draft 2020-12).

Features:
  - type checking (string, number, integer, boolean, null, array, object)
  - required fields
  - patternProperties and additionalProperties
  - nested object validation
  - array items / prefixItems validation
  - enum, const
  - minLength / maxLength (strings)
  - minimum / maximum / exclusiveMinimum / exclusiveMaximum (numbers)
  - minItems / maxItems (arrays)
  - minProperties / maxProperties (objects)
  - $ref (local pointer only, ``#/$defs/...``)
  - allOf, anyOf, oneOf, not
  - Clear error messages with JSON-pointer paths
"""

from __future__ import annotations

import re
from typing import Any


class ValidationError:
    """A single validation failure."""

    __slots__ = ("path", "message")

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message

    def __repr__(self) -> str:
        return f"ValidationError({self.path!r}, {self.message!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ValidationError):
            return NotImplemented
        return self.path == other.path and self.message == other.message


class ValidationResult:
    """Aggregated result of a validation run."""

    __slots__ = ("errors",)

    def __init__(self) -> None:
        self.errors: list[ValidationError] = []

    @property
    def valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, path: str, message: str) -> None:
        self.errors.append(ValidationError(path, message))

    def __bool__(self) -> bool:
        return self.valid

    def __repr__(self) -> str:
        if self.valid:
            return "ValidationResult(VALID)"
        lines = [f"ValidationResult({len(self.errors)} error(s)):"] + [
            f"  {e.path}: {e.message}" for e in self.errors
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_pointer_escape(token: str) -> str:
    """Escape a single JSON-pointer token for display."""
    return token.replace("~", "~0").replace("/", "~1")


def _append(path: str, token: str) -> str:
    """Append *token* to a JSON-pointer *path*."""
    return f"{path}/{_json_pointer_escape(token)}"


_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
    "array": list,
    "object": dict,
}

# Python ``bool`` is a subclass of ``int``; JSON Schema treats them as
# distinct types.  We need special handling.
_PYTHON_TYPE_PRIORITY: dict[str, type] = {
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
    "array": list,
    "object": dict,
}


def _json_type_name(value: Any) -> str:
    """Return the JSON-Schema type name for a Python value."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _resolve_ref(schema: dict, root_schema: dict) -> dict:
    """Resolve a simple local ``$ref`` (``#/$defs/...``)."""
    ref = schema.get("$ref")
    if not isinstance(ref, str):
        return schema
    if not ref.startswith("#/"):
        raise ValueError(f"Only local $ref supported, got: {ref}")
    parts = ref.lstrip("#/").split("/")
    node = root_schema
    for part in parts:
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            raise ValueError(f"$ref not found: {ref}")
        node = node[part]
    # Carry over sibling keywords (draft 2020-12 behavior)
    merged = dict(node)
    for k, v in schema.items():
        if k != "$ref":
            merged[k] = v
    return merged


# ---------------------------------------------------------------------------
# Core validator
# ---------------------------------------------------------------------------

def _validate(schema: Any, instance: Any, path: str, root: dict, result: ValidationResult) -> None:
    """Recursively validate *instance* against *schema*."""

    # Boolean schemas: true = accept everything, false = reject everything
    if schema is True:
        return
    if schema is False:
        result.add(path, "Nothing is valid against a false schema")
        return
    if not isinstance(schema, dict):
        return  # Invalid schema format — skip gracefully

    # Resolve $ref
    schema = _resolve_ref(schema, root)

    # --- const ---
    if "const" in schema:
        if instance != schema["const"]:
            result.add(path, f"Expected {schema['const']!r}, got {instance!r}")
            return  # const failure is terminal for this sub-schema

    # --- enum ---
    if "enum" in schema:
        if instance not in schema["enum"]:
            allowed = ", ".join(repr(v) for v in schema["enum"])
            result.add(path, f"Value {instance!r} not in enum [{allowed}]")
            return

    # --- type ---
    expected_type = schema.get("type")
    if expected_type is not None:
        types = expected_type if isinstance(expected_type, list) else [expected_type]
        actual = _json_type_name(instance)
        if actual not in types:
            expected_str = " | ".join(types)
            result.add(path, f"Expected type {expected_str}, got {actual}")
            return  # Wrong type — no point checking further constraints

    # --- String constraints ---
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            result.add(path, f"String length {len(instance)} < minLength {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            result.add(path, f"String length {len(instance)} > maxLength {schema['maxLength']}")
        if "pattern" in schema:
            if not re.search(schema["pattern"], instance):
                result.add(path, f"String does not match pattern {schema['pattern']!r}")

    # --- Number / integer constraints ---
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            result.add(path, f"Value {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            result.add(path, f"Value {instance} > maximum {schema['maximum']}")
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            result.add(path, f"Value {instance} <= exclusiveMinimum {schema['exclusiveMinimum']}")
        if "exclusiveMaximum" in schema and instance >= schema["exclusiveMaximum"]:
            result.add(path, f"Value {instance} >= exclusiveMaximum {schema['exclusiveMaximum']}")
        if "multipleOf" in schema and schema["multipleOf"] != 0:
            if instance % schema["multipleOf"] != 0:
                result.add(path, f"Value {instance} is not a multiple of {schema['multipleOf']}")

    # --- Array constraints ---
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            result.add(path, f"Array length {len(instance)} < minItems {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            result.add(path, f"Array length {len(instance)} > maxItems {schema['maxItems']}")
        if "items" in schema:
            for i, item in enumerate(instance):
                _validate(schema["items"], item, _append(path, str(i)), root, result)
        if "prefixItems" in schema:
            for i, sub in enumerate(schema["prefixItems"]):
                if i < len(instance):
                    _validate(sub, instance[i], _append(path, str(i)), root, result)
        if "contains" in schema:
            # At least one item must match
            if not any(_try_valid(schema["contains"], item, root) for item in instance):
                result.add(path, "Array does not contain a matching item")

    # --- Object constraints ---
    if isinstance(instance, dict):
        if "minProperties" in schema and len(instance) < schema["minProperties"]:
            result.add(path, f"Object has {len(instance)} properties, minProperties {schema['minProperties']}")
        if "maxProperties" in schema and len(instance) > schema["maxProperties"]:
            result.add(path, f"Object has {len(instance)} properties, maxProperties {schema['maxProperties']}")

        # required
        for req in schema.get("required", []):
            if req not in instance:
                result.add(_append(path, req), f"Missing required property '{req}'")

        # properties
        properties = schema.get("properties", {})
        pattern_properties = schema.get("patternProperties", {})
        additional = schema.get("additionalProperties")

        validated_keys: set[str] = set()

        # Named properties
        for key, sub_schema in properties.items():
            if key in instance:
                _validate(sub_schema, instance[key], _append(path, key), root, result)
                validated_keys.add(key)

        # Pattern properties
        for pattern, sub_schema in pattern_properties.items():
            regex = re.compile(pattern)
            for key in instance:
                if regex.search(key):
                    _validate(sub_schema, instance[key], _append(path, key), root, result)
                    validated_keys.add(key)

        # additionalProperties
        for key in instance:
            if key not in validated_keys:
                if additional is False:
                    result.add(_append(path, key), f"Additional property '{key}' is not allowed")
                elif isinstance(additional, dict):
                    _validate(additional, instance[key], _append(path, key), root, result)

    # --- Combinators ---
    if "allOf" in schema:
        for sub in schema["allOf"]:
            _validate(sub, instance, path, root, result)

    if "anyOf" in schema:
        if not any(_try_valid(sub, instance, root) for sub in schema["anyOf"]):
            result.add(path, "Does not match any schema in anyOf")

    if "oneOf" in schema:
        matches = sum(1 for sub in schema["oneOf"] if _try_valid(sub, instance, root))
        if matches != 1:
            result.add(path, f"Matches {matches} schemas in oneOf (expected exactly 1)")

    if "not" in schema:
        if _try_valid(schema["not"], instance, root):
            result.add(path, "Instance matches the 'not' schema (expected no match)")


def _try_valid(schema: Any, instance: Any, root: dict) -> bool:
    """Return True if *instance* validates against *schema* (discard errors)."""
    r = ValidationResult()
    _validate(schema, instance, "", root, r)
    return r.valid


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate(instance: Any, schema: dict) -> ValidationResult:
    """Validate *instance* against a JSON *schema*.

    Returns a :class:`ValidationResult` with ``.valid`` (bool) and
    ``.errors`` (list of :class:`ValidationError`).
    """
    result = ValidationResult()
    _validate(schema, instance, "", schema, result)
    return result


def is_valid(instance: Any, schema: dict) -> bool:
    """Return ``True`` if *instance* satisfies *schema*."""
    return validate(instance, schema).valid


# ---------------------------------------------------------------------------
# Demo / self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _demo_schema = {
        "type": "object",
        "required": ["name", "age", "email"],
        "properties": {
            "name": {"type": "string", "minLength": 1, "maxLength": 100},
            "age": {"type": "integer", "minimum": 0, "maximum": 200},
            "email": {"type": "string", "pattern": r"^[^@\s]+@[^@\s]+\.[^@\s]+$"},
            "tags": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "address": {
                "type": "object",
                "required": ["street", "city"],
                "properties": {
                    "street": {"type": "string"},
                    "city": {"type": "string"},
                    "zip": {"type": "string", "pattern": r"^\d{5}$"},
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    }

    print("=== VALID CASE ===")
    good = {
        "name": "Alice",
        "age": 30,
        "email": "alice@example.com",
        "tags": ["admin"],
        "address": {"street": "123 Main St", "city": "Springfield", "zip": "12345"},
    }
    r = validate(good, _demo_schema)
    print(r)

    print("\n=== INVALID CASE ===")
    bad = {
        "name": "",
        "age": -5,
        "email": "not-an-email",
        "address": {"street": "123 Main St", "city": "Springfield", "zip": "123"},
        "extra_field": "should not be here",
    }
    r = validate(bad, _demo_schema)
    print(r)

    print("\n=== ONEOF / ALLOF ===")
    combo_schema = {
        "oneOf": [
            {"type": "string", "minLength": 5},
            {"type": "integer", "minimum": 100},
        ]
    }
    print(validate("hi", combo_schema))
    print(validate("hello world", combo_schema))
    print(validate(50, combo_schema))
    print(validate(150, combo_schema))

    print("\n=== $REF ===")
    ref_schema = {
        "$defs": {
            "positiveInt": {"type": "integer", "minimum": 1}
        },
        "type": "object",
        "properties": {
            "id": {"$ref": "#/$defs/positiveInt"},
        },
        "required": ["id"],
    }
    print(validate({"id": 42}, ref_schema))
    print(validate({"id": -1}, ref_schema))
