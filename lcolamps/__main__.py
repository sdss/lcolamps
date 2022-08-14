#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-01-22
# @Filename: __main__.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import logging
import os

import click
from click_default_group import DefaultGroup

from sdsstools.daemonizer import DaemonGroup, cli_coro

from lcolamps import config, log
from lcolamps.actor import LCOLampsActor


@click.group(cls=DefaultGroup, default="actor", default_if_no_args=True)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    allow_from_autoenv=False,
    help="Output extra information to stdout.",
)
def lcolamps(verbose):
    """Command Line Interface for Finger Lakes Instrumentation cameras."""

    if verbose:
        log.set_level(logging.DEBUG)
    else:
        log.set_level(logging.WARNING)


@lcolamps.group(cls=DaemonGroup, prog="sdss-lcolamps", workdir=os.getcwd())
@cli_coro()
async def actor():
    """Start/stop the actor as a daemon."""

    actor = await LCOLampsActor.from_config(config).start()
    await actor.run_forever()


if __name__ == "__main__":
    lcolamps()
