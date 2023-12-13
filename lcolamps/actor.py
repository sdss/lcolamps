#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2022-08-13
# @Filename: actor.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import pathlib
from os import PathLike

from typing import TypeVar

from clu import Command
from clu.legacy import LegacyActor

from lcolamps import OBSERVATORY, __version__, config
from lcolamps.controller import LampsController

from .commands import lamps_parser


T = TypeVar("T", bound="LCOLampsActor")


class LCOLampsActor(LegacyActor):
    """LCO lamps actor."""

    parser = lamps_parser

    def __init__(self, *args, schema: str | PathLike | None = None, **kwargs):
        self.observatory = OBSERVATORY

        schema = schema or pathlib.Path(__file__).parent / "etc/schema.json"

        super().__init__(*args, schema=schema, **kwargs)

        self.version = __version__

        if "m2" in config:
            m2_params = (config["m2.host"], config["m2.port"])
        else:
            m2_params = None

        self.controller = LampsController(
            m2_params=m2_params,
            lamps=config["lamps"],
            actor=self,
        )
        self.parser_args = [self.controller]

    async def start(self: T, **kwargs) -> T:
        """Starts the lamps controller and actor."""

        await super().start(**kwargs)
        await self.controller.update()

        return self


LampsCommand = Command[LCOLampsActor]
