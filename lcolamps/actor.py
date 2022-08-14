#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2022-08-13
# @Filename: actor.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from clu.legacy import LegacyActor

from lcolamps import OBSERVATORY, __version__


class LCOLampsActor(LegacyActor):
    """LCO lamps actor."""

    def __init__(self, *args, **kwargs):

        self.observatory = OBSERVATORY
        # if self.observatory != "LCO":
        #     raise ValueError("lcolamps can only be run at LCO.")

        super().__init__(*args, **kwargs)

        self.version = __version__
