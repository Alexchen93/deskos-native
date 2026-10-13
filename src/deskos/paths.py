from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parents[1]
ASSET_DIR = Path(os.environ.get("DESKOS_ASSET_DIR", PROJECT_DIR / "assets")).expanduser()
DATA_DIR = Path(
    os.environ.get("DESKOS_DATA_DIR", Path.home() / ".local" / "share" / "deskos")
).expanduser()
DATABASE_PATH = DATA_DIR / "deskos.db"
MODEL_PATH = ASSET_DIR / "models" / "raspberry_pi_4_model.glb"
MODEL_PREVIEW_PATH = ASSET_DIR / "models" / "raspberry_pi_4_preview.png"


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
