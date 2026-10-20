import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_config(path=None) -> dict:
    config_path = Path(path or os.environ.get("QQ_BRIDGE_CONFIG", ROOT / "config.yaml"))
    if not config_path.exists():
        raise FileNotFoundError(f"config not found: {config_path}")
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid config: {config_path}")
    return data


def project_path(*parts) -> Path:
    return ROOT.joinpath(*parts)
