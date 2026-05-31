from __future__ import annotations
import os
from typing import Dict, Optional
from .base import LLMProvider, ProviderConfig
from .deepseek import DeepSeekProvider


_providers: Dict[str, LLMProvider] = {}


def _load_config() -> dict:
    import yaml
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "config", "providers.yaml"
    )
    if os.path.exists(config_path):
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def init_providers(config: Optional[dict] = None) -> Dict[str, LLMProvider]:
    provider_configs = config or _load_config()

    for name, cfg in provider_configs.items():
        api_key = os.environ.get(cfg.get("api_key_env", ""), "") or cfg.get("api_key", "")
        if not api_key:
            continue

        pconfig = ProviderConfig(
            name=name,
            model=cfg.get("model", ""),
            api_key=api_key,
            base_url=cfg.get("base_url", ""),
            temperature=cfg.get("temperature", 0.1),
            max_tokens=cfg.get("max_tokens", 4096),
        )

        if name == "deepseek":
            _providers[name] = DeepSeekProvider(pconfig)

    return _providers


def get_provider(name: str) -> LLMProvider:
    if name not in _providers:
        init_providers()
    if name not in _providers:
        raise ValueError(
            f"Provider '{name}' not initialized. "
            f"Available: {list(_providers.keys())}. "
            f"Set {name.upper()}_API_KEY env var."
        )
    return _providers[name]
