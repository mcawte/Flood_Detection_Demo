"""Shared locations for model configuration and checkpoints.

We avoid hard-coding the Granite flood model asset names across modules by
centralising the environment-variable lookups here.
"""

from __future__ import annotations

import os
from pathlib import Path

# The container mounts /app/configs and /app/models as writable volumes.
_DEFAULT_CONFIG = "config_granite_geospatial_uki_flood_detection_v1.yaml"
_DEFAULT_CHECKPOINT = "granite_geospatial_uki_flood_detection_v1.ckpt"

MODEL_CONFIG_FILENAME = os.environ.get("MODEL_CONFIG_FILE", _DEFAULT_CONFIG)
MODEL_CHECKPOINT_FILENAME = os.environ.get(
    "MODEL_CHECKPOINT_FILE", _DEFAULT_CHECKPOINT
)

CONFIG_PATH = str(Path("/app/configs") / MODEL_CONFIG_FILENAME)
CHECKPOINT_PATH = str(Path("/app/models") / MODEL_CHECKPOINT_FILENAME)

# Terratorch needs to run from the root of the application where the
# `custom_modules` package lives.
PROJECT_CODE_DIR = "/app"

__all__ = [
    "MODEL_CONFIG_FILENAME",
    "MODEL_CHECKPOINT_FILENAME",
    "CONFIG_PATH",
    "CHECKPOINT_PATH",
    "PROJECT_CODE_DIR",
]
