#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2022-08-13
# @Filename: actor.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import pathlib

from typing import TypeVar

from clu import Command
from clu.legacy import LegacyActor

from lcolamps import OBSERVATORY, __version__, config
from lcolamps.lamps import LampsController

from .commands import lamps_parser  # noqa


T = TypeVar("T", bound="LCOLampsActor")


class LCOLampsActor(LegacyActor):
    """LCO lamps actor."""

    parser = lamps_parser

    def __init__(self, *args, **kwargs):

        self.observatory = OBSERVATORY
        # if self.observatory != "LCO":
        #     raise ValueError("lcolamps can only be run at LCO.")

        super().__init__(*args, **kwargs)
        self.load_schema(str(pathlib.Path(__file__).parent / "etc/schema.json"))

        self.version = __version__

        self.controller = LampsController(**config["m2"], lamps=config["lamps"])
        self.parser_args = [self.controller]

    async def start(self: T, **kwargs) -> T:
        """Starts the lamps controller and actor."""

        await self.controller.update()

        return await super().start(**kwargs)


LampsCommand = Command[LCOLampsActor]
