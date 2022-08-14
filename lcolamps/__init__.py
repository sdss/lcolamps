# encoding: utf-8
# isort:skip

import os
import pathlib

from sdsstools import get_config, get_logger, get_package_version


NAME = "sdss-lcolamps"

__version__ = get_package_version(__file__, NAME) or "dev"

config = get_config(
    "lcolamps",
    config_file=str(pathlib.Path(__file__).parent / "etc/lcolamps.yaml"),
)

log = get_logger(NAME)

OBSERVATORY = os.environ.get("OBSERVATORY", "UNKNOWN")
