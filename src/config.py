from __future__ import annotations
import os
from typing import Any, Dict, Optional
import yaml


DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "config", "default.yaml",
)


class Config:
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or DEFAULT_CONFIG_PATH
        self._data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.path):
            with open(self.path) as f:
                return yaml.safe_load(f) or {}
        return {}

    def get(self, *keys: str, default: Any = None) -> Any:
        val: Any = self._data
        for key in keys:
            if isinstance(val, dict):
                val = val.get(key)
                if val is None:
                    return default
            else:
                return default
        return val if val is not None else default

    @property
    def pipeline(self) -> Dict[str, Any]:
        return self._data.get("pipeline", {})

    @property
    def providers(self) -> Dict[str, Any]:
        return self._data.get("providers", {})

    @property
    def sources(self) -> Dict[str, Any]:
        return self._data.get("sources", {})

    @property
    def multilingual(self) -> Dict[str, Any]:
        return self._data.get("multilingual", {})

    @property
    def graphrag(self) -> Dict[str, Any]:
        return self._data.get("graphrag", {})

    @property
    def output(self) -> Dict[str, Any]:
        return self._data.get("output", {})
