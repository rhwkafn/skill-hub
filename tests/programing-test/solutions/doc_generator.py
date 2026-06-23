"""
Markdown API documentation generator.

Introspects a Python module using the inspect module, extracts docstrings,
parameters, return types, and nested classes, then outputs clean Markdown.
"""

import inspect
import importlib
import types
from typing import Any, Optional, get_type_hints


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_annotation(annotation: Any) -> str:
    """Return a human-readable string for a type annotation."""
    if annotation is inspect.Parameter.empty or annotation is inspect.Signature.empty:
        return ""
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return str(annotation)


def _format_default(default: Any) -> str:
    """Return a human-readable string for a default value."""
    if default is inspect.Parameter.empty:
        return ""
    return repr(default)


def _extract_function_info(func: object) -> dict:
    """
    Extract documentation metadata from a function or method.

    Returns a dict with: name, signature, docstring, params, return_type.
    """
    info: dict = {
        "name": getattr(func, "__name__", "<lambda>"),
        "qualname": getattr(func, "__qualname__", ""),
        "docstring": inspect.getdoc(func) or "",
        "params": [],
        "return_type": "",
        "is_async": inspect.iscoroutinefunction(func),
    }

    try:
        sig = inspect.signature(func)
    except (ValueError, TypeError):
        return info

    info["signature"] = str(sig)

    # Try to resolve type hints (may fail for forward refs)
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    for name, param in sig.parameters.items():
        annotation = hints.get(name, param.annotation)
        info["params"].append({
            "name": name,
            "kind": str(param.kind).split(".")[-1],
            "type": _format_annotation(annotation),
            "default": _format_default(param.default),
        })

    ret = hints.get("return", sig.return_annotation)
    info["return_type"] = _format_annotation(ret)

    return info


def _extract_class_info(cls: type) -> dict:
    """
    Extract documentation metadata from a class, including nested classes.
    """
    info: dict = {
        "name": cls.__name__,
        "qualname": cls.__qualname__,
        "docstring": inspect.getdoc(cls) or "",
        "bases": [b.__name__ for b in cls.__bases__ if b is not object],
        "methods": [],
        "nested_classes": [],
    }

    for name, obj in inspect.getmembers(cls):
        if name.startswith("_") and name != "__init__":
            continue
        if inspect.isfunction(obj) or inspect.ismethod(obj):
            method_info = _extract_function_info(obj)
            # Mark as classmethod / staticmethod
            if isinstance(cls.__dict__.get(name), classmethod):
                method_info["decorator"] = "classmethod"
            elif isinstance(cls.__dict__.get(name), staticmethod):
                method_info["decorator"] = "staticmethod"
            info["methods"].append(method_info)
        elif inspect.isclass(obj) and obj.__module__ == cls.__module__:
            info["nested_classes"].append(_extract_class_info(obj))

    return info


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def _render_function_md(func_info: dict, heading_level: int = 3) -> str:
    """Render a function/method info dict to Markdown."""
    parts: list[str] = []
    prefix = "#" * heading_level
    name = func_info["name"]
    sig = func_info.get("signature", "")
    deco = func_info.get("decorator", "")

    deco_label = f" *{deco}*" if deco else ""
    async_label = " *async*" if func_info.get("is_async") else ""
    parts.append(f"{prefix} `{name}`{deco_label}{async_label}\n")

    # Signature
    parts.append(f"```python\n{name}{sig}\n```\n")

    # Parameters table
    params = func_info.get("params", [])
    if params:
        parts.append("| Parameter | Type | Default | Kind |")
        parts.append("|-----------|------|---------|------|")
        for p in params:
            p_type = p["type"] or "-"
            p_default = p["default"] or "-"
            p_kind = p["kind"] if p["kind"] != "POSITIONAL_OR_KEYWORD" else ""
            parts.append(f"| `{p['name']}` | `{p_type}` | `{p_default}` | {p_kind} |")
        parts.append("")

    # Return type
    ret = func_info.get("return_type", "")
    if ret:
        parts.append(f"**Returns:** `{ret}`\n")

    # Docstring
    if func_info["docstring"]:
        parts.append(func_info["docstring"] + "\n")

    return "\n".join(parts)


def _render_class_md(class_info: dict, heading_level: int = 2) -> str:
    """Render a class info dict to Markdown."""
    parts: list[str] = []
    prefix = "#" * heading_level
    name = class_info["name"]
    bases = class_info.get("bases", [])
    bases_str = f"({', '.join(bases)})" if bases else ""

    parts.append(f"{prefix} Class `{name}`{bases_str}\n")

    if class_info["docstring"]:
        parts.append(class_info["docstring"] + "\n")

    # Methods
    for method in class_info.get("methods", []):
        parts.append(_render_function_md(method, heading_level=heading_level + 1))

    # Nested classes
    for nested in class_info.get("nested_classes", []):
        parts.append(_render_class_md(nested, heading_level=heading_level + 1))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_docs(module: types.ModuleType, title: Optional[str] = None) -> str:
    """
    Generate Markdown API documentation for a Python module.

    Args:
        module: The Python module object to document.
        title: Optional title for the document. Defaults to module.__name__.

    Returns:
        A Markdown string with full API documentation.
    """
    title = title or getattr(module, "__name__", "API Documentation")
    parts: list[str] = [f"# {title}\n"]

    module_doc = inspect.getdoc(module)
    if module_doc:
        parts.append(module_doc + "\n")

    # --- Module-level functions ---
    functions = []
    classes = []

    for name, obj in inspect.getmembers(module):
        if name.startswith("_"):
            continue
        # Only include items defined in this module
        if getattr(obj, "__module__", None) != module.__name__:
            continue
        if inspect.isfunction(obj):
            functions.append(obj)
        elif inspect.isclass(obj):
            classes.append(obj)

    if functions:
        parts.append("## Functions\n")
        for func in sorted(functions, key=lambda f: f.__name__):
            parts.append(_render_function_md(_extract_function_info(func)))

    if classes:
        parts.append("## Classes\n")
        for cls in sorted(classes, key=lambda c: c.__name__):
            parts.append(_render_class_md(_extract_class_info(cls)))

    return "\n".join(parts)


def generate_docs_from_source(source: str, title: Optional[str] = None) -> str:
    """
    Generate Markdown docs from a Python source string.

    Args:
        source: Python source code.
        title: Optional document title.

    Returns:
        Markdown documentation string.
    """
    mod_name = title or "__generated__"
    module = types.ModuleType(mod_name)
    module.__name__ = mod_name
    exec(compile(source, "<string>", "exec"), module.__dict__)
    return generate_docs(module, title=title)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python doc_generator.py <module_name_or_path> [title]")
        sys.exit(1)

    target = sys.argv[1]
    doc_title = sys.argv[2] if len(sys.argv) > 2 else None

    if target.endswith(".py"):
        # Load from file path
        import importlib.util
        spec = importlib.util.spec_from_file_location("_doc_target", target)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        else:
            print(f"Cannot load {target}", file=sys.stderr)
            sys.exit(1)
    else:
        # Load as module name
        mod = importlib.import_module(target)

    print(generate_docs(mod, title=doc_title))
