from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppConfig:
    windowed: bool

    @classmethod
    def from_environment(cls) -> AppConfig:
        return cls(windowed=os.environ.get("DESKOS_WINDOWED", "0") == "1")
