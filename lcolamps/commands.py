#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2022-08-14
# @Filename: commands.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
from time import time

from typing import TYPE_CHECKING

import click

from clu.parsers.click import command_parser as lamps_parser

from lcolamps.lamps import LampState


if TYPE_CHECKING:
    from .actor import LampsCommand
    from .lamps import LampsController


@lamps_parser.command()
async def status(command: LampsCommand, controller: LampsController):
    """Returns the status of the lamps."""

    try:
        await controller.update()
    except Exception as err:
        command.warning(
            f"Failed updating lamps status with error {err!r}. "
            "Outputting cached status."
        )

    lamps = controller.lamps

    output = {}
    for lamp_name in lamps:
        lamp = lamps[lamp_name]
        state = lamp.state.name
        if state is None:
            continue

        output[lamp.name] = state.upper()
        if state.upper() == "UNKNOWN":
            command.warning(f"Lamp {lamp.name} status is unknown.")

    return command.finish(**output)


@lamps_parser.command()
@click.argument("lamp_name", metavar="LAMP", type=str)
@click.option("-w", "--warmup", type=float, help="Warm-up time for the lamp.")
async def on(
    command: LampsCommand,
    controller: LampsController,
    lamp_name: str,
    warmup: float | None = None,
):
    """Turns on a lamp, blocking until it has warmed up."""

    if lamp_name.lower() not in controller.lamps:
        return command.fail(f"Unknown {lamp_name} lamp.")

    lamp_name = lamp_name.lower()

    lamp = controller.lamps[lamp_name]
    warm_up_time = warmup or lamp.warm_up_time

    try:
        await controller.set(lamp_name, True, warm_up_time=warmup)
    except Exception as err:
        return command.fail(f"Failed turning on lamp {lamp.name}: {err}")

    # Give time to the warm-up task to complete if warm-up time is zero.
    await asyncio.sleep(0.1)

    start_time = time()

    if lamp.state & LampState.ON:
        pass
    elif lamp.state & LampState.WARMING:
        last_warn = 0
        while True:
            await asyncio.sleep(1)
            if lamp.state == LampState.ON:
                command.info(f"{lamp.name}: warm-up complete.")
                break

            if (time() - start_time) > (warm_up_time + 5):
                return command.fail(f"{lamp.name} timed out warming up.")

            if lamp.on_time is not None:
                elapsed_p = (time() - lamp.on_time) / warm_up_time * 100.0
                elapsed_p_round = int(elapsed_p / 10) * 10
                if elapsed_p_round > (last_warn + 10):
                    command.debug(f"{lamp.name}: {elapsed_p_round}% warmed up.")
                    last_warn = elapsed_p_round

    else:
        return command.fail(f"{lamp.name}: invalid status.")

    return command.finish(**{lamp.name: lamp.state.name})


@lamps_parser.command()
@click.argument("lamp_name", metavar="LAMP", type=str)
async def off(command: LampsCommand, controller: LampsController, lamp_name: str):
    """Turns off a lamp."""

    if lamp_name.lower() not in controller.lamps:
        return command.fail(f"Unknown {lamp_name} lamp.")

    lamp_name = lamp_name.lower()
    lamp = controller.lamps[lamp_name]

    try:
        await controller.set(lamp_name, False)
    except Exception as err:
        return command.fail(f"Failed turning on lamp {lamp.name}: {err}")

    return command.finish(**{lamp.name: lamp.state.name})
