import functools
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


@functools.lru_cache(maxsize=None)
def _load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name) as f:
        return yaml.safe_load(f)


def load_companies() -> dict:
    return _load_yaml("companies.yaml")


def load_pipeline_config() -> dict:
    return _load_yaml("pipeline.yaml")
