from __future__ import annotations
import hashlib
import json
import os
import pickle
import time
from pathlib import Path
from typing import Any, Optional


class DiskCache:
    def __init__(self, cache_dir: str = ".cache/osint_pipeline", ttl_seconds: int = 3600) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_seconds

    def _key(self, namespace: str, *args: Any) -> str:
        raw = f"{namespace}:{json.dumps(args, sort_keys=True, default=str)}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _path(self, key: str) -> Path:
        return self.cache_dir / key[:2] / key

    def get(self, namespace: str, *args: Any) -> Optional[Any]:
        path = self._path(self._key(namespace, *args))
        if not path.exists():
            return None
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            if data.get("expires", 0) < time.time():
                path.unlink(missing_ok=True)
                return None
            return data.get("value")
        except (pickle.UnpicklingError, EOFError, OSError):
            return None

    def set(self, namespace: str, value: Any, *args: Any, ttl: Optional[int] = None) -> None:
        key = self._key(namespace, *args)
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "value": value,
            "expires": time.time() + (ttl or self.ttl),
            "created": time.time(),
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)

    def clear(self, namespace: Optional[str] = None) -> None:
        if namespace:
            for path in self.cache_dir.rglob("*"):
                if path.is_file():
                    path.unlink()
        else:
            import shutil
            shutil.rmtree(self.cache_dir, ignore_errors=True)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
