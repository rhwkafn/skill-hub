"""Config Parser — reads INI/JSON/YAML, supports env overrides, dot-notation, type coercion."""

import configparser
import json
import os
import re
from pathlib import Path
from typing import Any, Optional


class ConfigError(Exception):
    """Base exception for config parsing errors."""


class ConfigValidationError(ConfigError):
    """Raised when a config value fails validation."""


class Config:
    """Unified configuration reader supporting INI, JSON, YAML, env overrides, and validation.

    Usage:
        cfg = Config.from_file("config.json")
        cfg = Config.from_file("config.ini", section="app")
        cfg = Config.from_file("config.yaml")

        # Dot-notation access
        db_host = cfg.get("database.host", default="localhost")
        port = cfg.get_int("server.port", default=8080)
        debug = cfg.get_bool("app.debug", default=False)

        # Env override: CONFIG_DATABASE__HOST overrides database.host
        cfg = Config.from_file("config.json", env_prefix="CONFIG")

        # Validation
        cfg.require("database.host", "database.port")
        cfg.validate("server.port", lambda v: 1 <= v <= 65535, "Port must be 1-65535")
    """

    def __init__(
        self,
        data: dict[str, Any],
        source: str = "<dict>",
        env_prefix: Optional[str] = None,
    ):
        self._data = data
        self._source = source
        self._env_prefix = env_prefix
        if env_prefix:
            self._apply_env_overrides(env_prefix)

    # --- Factory methods ---

    @classmethod
    def from_file(
        cls,
        path: str,
        section: Optional[str] = None,
        env_prefix: Optional[str] = None,
    ) -> "Config":
        """Load config from a file. Auto-detects format by extension.

        Args:
            path: File path (.json, .ini/.cfg, .yaml/.yml).
            section: For INI files, which section to use as root (default: DEFAULT).
            env_prefix: If set, env vars like {PREFIX}_KEY__SUBKEY override config values.
        """
        p = Path(path)
        if not p.exists():
            raise ConfigError(f"Config file not found: {path}")

        ext = p.suffix.lower()
        content = p.read_text(encoding="utf-8")

        if ext == ".json":
            data = cls._parse_json(content)
        elif ext in (".ini", ".cfg"):
            data = cls._parse_ini(content, section)
        elif ext in (".yaml", ".yml"):
            data = cls._parse_yaml(content)
        else:
            raise ConfigError(f"Unsupported config format: {ext}")

        return cls(data, source=str(p), env_prefix=env_prefix)

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], env_prefix: Optional[str] = None
    ) -> "Config":
        """Create config from an existing dict."""
        return cls(data, source="<dict>", env_prefix=env_prefix)

    # --- Parsers ---

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON: {e}") from e

    @staticmethod
    def _parse_ini(content: str, section: Optional[str]) -> dict[str, Any]:
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read_string(content)
        except configparser.Error as e:
            raise ConfigError(f"Invalid INI: {e}") from e

        if section:
            if section not in parser:
                raise ConfigError(f"Section [{section}] not found in INI file")
            raw = dict(parser[section])
        else:
            # Merge all sections into nested dict
            raw = {}
            for sec in parser.sections():
                raw[sec] = dict(parser[sec])
            if parser.defaults():
                raw["DEFAULT"] = dict(parser.defaults())

        # Flatten section-based dict into nested structure
        result: dict[str, Any] = {}
        for key, value in raw.items():
            if isinstance(value, dict):
                result[key] = {k: v for k, v in value.items()}
            else:
                result[key] = value
        return result

    @staticmethod
    def _parse_yaml(content: str) -> dict[str, Any]:
        try:
            import yaml
        except ImportError:
            # Minimal YAML support for flat/nested key-value files
            return Config._parse_simple_yaml(content)
        try:
            data = yaml.safe_load(content)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            raise ConfigError(f"Invalid YAML: {e}") from e

    @staticmethod
    def _parse_simple_yaml(content: str) -> dict[str, Any]:
        """Fallback YAML parser for simple key: value and nested structures."""
        result: dict[str, Any] = {}
        current_section: Optional[dict[str, Any]] = None
        current_key: Optional[str] = None

        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(line) - len(line.lstrip())
            if indent == 0 and ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if val:
                    result[key] = Config._coerce_value(val)
                    current_section = None
                    current_key = None
                else:
                    result[key] = {}
                    current_section = result[key]
                    current_key = key
            elif indent > 0 and current_section is not None and ":" in stripped:
                key, _, val = stripped.partition(":")
                current_section[key.strip()] = Config._coerce_value(val.strip())

        return result

    # --- Env overrides ---

    def _apply_env_overrides(self, prefix: str) -> None:
        """Override config values from env vars. KEY__SUBKEY maps to key.subkey."""
        prefix_upper = prefix.upper() + "_"
        for env_key, env_val in os.environ.items():
            if not env_key.startswith(prefix_upper):
                continue
            # Strip prefix, convert __ to dot
            path = env_key[len(prefix_upper):].lower().replace("__", ".")
            self._set_nested(self._data, path, self._coerce_value(env_val))

    # --- Accessors ---

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value by dot-notation key, returning default if missing."""
        val = self._get_nested(self._data, key)
        return val if val is not None else default

    def get_string(self, key: str, default: str = "") -> str:
        val = self.get(key, default)
        return str(val) if val is not None else default

    def get_int(self, key: str, default: int = 0) -> int:
        val = self.get(key, default)
        try:
            return int(val)
        except (TypeError, ValueError):
            raise ConfigError(f"Cannot convert {key}={val!r} to int")

    def get_float(self, key: str, default: float = 0.0) -> float:
        val = self.get(key, default)
        try:
            return float(val)
        except (TypeError, ValueError):
            raise ConfigError(f"Cannot convert {key}={val!r} to float")

    def get_bool(self, key: str, default: bool = False) -> bool:
        val = self.get(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "yes", "1", "on")
        return bool(val)

    def get_list(self, key: str, default: Optional[list] = None) -> list:
        val = self.get(key, default if default is not None else [])
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            return [v.strip() for v in val.split(",")]
        return [val] if val is not None else []

    def keys(self) -> list[str]:
        """Return top-level keys."""
        return list(self._data.keys())

    def as_dict(self) -> dict[str, Any]:
        """Return a copy of the full config dict."""
        return json.loads(json.dumps(self._data, default=str))

    # --- Validation ---

    def require(self, *keys: str) -> None:
        """Raise ConfigError if any of the given keys are missing or None."""
        missing = [k for k in keys if self.get(k) is None]
        if missing:
            raise ConfigError(
                f"Missing required config keys: {', '.join(missing)} "
                f"(source: {self._source})"
            )

    def validate(
        self, key: str, predicate: callable, message: str = ""
    ) -> None:
        """Validate a config value with a predicate function.

        Args:
            key: Dot-notation config key.
            predicate: Callable that returns True if valid.
            message: Error message on validation failure.
        """
        val = self.get(key)
        if val is not None and not predicate(val):
            raise ConfigValidationError(
                f"Validation failed for {key}={val!r}: {message or 'invalid value'}"
            )

    # --- Internal helpers ---

    @staticmethod
    def _get_nested(data: dict, key: str) -> Any:
        """Traverse nested dict by dot-separated key."""
        parts = key.split(".")
        current = data
        for part in parts:
            if not isinstance(current, dict):
                return None
            if part not in current:
                # Also try numeric index for list access
                if part.isdigit() and isinstance(current, list):
                    idx = int(part)
                    if 0 <= idx < len(current):
                        current = current[idx]
                        continue
                return None
            current = current[part]
        return current

    @staticmethod
    def _set_nested(data: dict, key: str, value: Any) -> None:
        """Set a value in a nested dict by dot-separated key."""
        parts = key.split(".")
        current = data
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    @staticmethod
    def _coerce_value(val: str) -> Any:
        """Coerce a string value to the most likely Python type."""
        if not isinstance(val, str):
            return val
        lower = val.lower()
        if lower in ("true", "yes", "on"):
            return True
        if lower in ("false", "no", "off"):
            return False
        if lower in ("null", "none", "~"):
            return None
        # Try int
        try:
            return int(val)
        except ValueError:
            pass
        # Try float
        try:
            return float(val)
        except ValueError:
            pass
        return val

    def __repr__(self) -> str:
        return f"Config(source={self._source!r}, keys={self.keys()!r})"


# --- Demo / self-test ---
if __name__ == "__main__":
    import tempfile, os

    # Create sample files for testing
    sample_json = {
        "database": {"host": "localhost", "port": 5432, "name": "mydb"},
        "server": {"host": "0.0.0.0", "port": 8080, "debug": True},
        "features": ["auth", "logging", "cache"],
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(sample_json, f)
        json_path = f.name

    # Test JSON config
    cfg = Config.from_file(json_path, env_prefix="APP")
    print(f"Config: {cfg}")
    print(f"database.host = {cfg.get('database.host')}")
    print(f"database.port = {cfg.get_int('database.port')}")
    print(f"server.debug = {cfg.get_bool('server.debug')}")
    print(f"features = {cfg.get_list('features')}")

    cfg.require("database.host", "database.port")
    cfg.validate(
        "database.port",
        lambda v: 1 <= v <= 65535,
        "Port must be between 1 and 65535",
    )

    # Test INI
    ini_content = "[app]\nname = MyApp\nversion = 2.0\ndebug = true\n\n[db]\nhost = db.example.com\nport = 3306\n"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".ini", delete=False
    ) as f:
        f.write(ini_content)
        ini_path = f.name

    ini_cfg = Config.from_file(ini_path, section="app")
    print(f"\nINI app.name = {ini_cfg.get('name')}")
    print(f"INI app.debug = {ini_cfg.get_bool('debug')}")

    # Cleanup
    os.unlink(json_path)
    os.unlink(ini_path)
    print("\nAll tests passed.")
