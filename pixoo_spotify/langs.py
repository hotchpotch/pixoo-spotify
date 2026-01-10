from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from langdetect import detector_factory

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_langdetect_languages() -> list[str]:
    profiles_dir = Path(detector_factory.PROFILES_DIRECTORY)
    if not profiles_dir.exists():
        logger.debug("Langdetect profiles directory not found: %s", profiles_dir)
        return []
    langs = sorted(
        {
            path.name
            for path in profiles_dir.iterdir()
            if path.is_file() and not path.name.startswith(".")
        }
    )
    logger.debug("Langdetect supports %d languages", len(langs))
    return langs
