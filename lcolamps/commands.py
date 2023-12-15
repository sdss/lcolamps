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

from lcolamps.controller import LampState


if TYPE_CHECKING:
    from .actor import LampsCommand
    from .controller import LampsController


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
        await controller.set_state(lamp_name, True, warm_up_time=warmup)
    except Exception as err:
        return command.fail(f"Failed turning on lamp {lamp.name}: {err}")

    # Give time to the warm-up task to complete if warm-up time is zero.
    await asyncio.sleep(0.1)

    start_time = time()

    if lamp.state & LampState.ON:
        pass
    elif lamp.state & LampState.WARMING:
        command.info(**{lamp.name: lamp.state.name})
        last_warn = 0
        while True:
            await asyncio.sleep(1)
            if lamp.state == LampState.ON:
                command.info(f"{lamp.name}: warm-up complete.")
                break

            if (time() - start_time) > (warm_up_time + 5):
                lamp.state = LampState.UNKNOWN
                command.warning(**{lamp.name: LampState.UNKNOWN})
                return command.fail(f"{lamp.name} timed out warming up.")

            if lamp.on_time is not None:
                elapsed_p = (time() - lamp.on_time) / warm_up_time * 100.0
                elapsed_p_round = int(elapsed_p / 10) * 10
                if elapsed_p_round > (last_warn + 10):
                    command.debug(f"{lamp.name}: {elapsed_p_round}% warmed up.")
                    last_warn = elapsed_p_round

    else:
        command.warning(**{lamp.name: lamp.state.name})
        return command.fail(f"{lamp.name}: invalid status.")

    return command.finish(**{lamp.name: lamp.state.name})


@lamps_parser.command()
@click.argument("lamp_name", metavar="LAMP", type=str, required=False)
@click.option("--all", "all_lamps", is_flag=True, help="Turn off all the lamps.")
async def off(
    command: LampsCommand,
    controller: LampsController,
    lamp_name: str | None = None,
    all_lamps: bool = False,
):
    """Turns off a lamp."""

    if all_lamps is True or lamp_name is None:
        await controller.update()
        results = await asyncio.gather(
            *[
                controller.set_state(lamp_name, False, update_status=False)
                for lamp_name in controller.lamps
            ],
            return_exceptions=True,
        )
        replies = {}
        for ii in range(len(controller.lamps)):
            lamp = list(controller.lamps.values())[ii]
            if isinstance(results[ii], Exception):
                command.error(f"Failed turning off lamp {lamp.name}: {results[ii]!s}.")
                continue
            replies[lamp.name] = "OFF"
        if len(replies) > 0:
            command.info(**replies)
        return command.finish()

    if lamp_name.lower() not in controller.lamps:
        return command.fail(f"Unknown {lamp_name} lamp.")

    lamp_name = lamp_name.lower()
    lamp = controller.lamps[lamp_name]

    try:
        await controller.set_state(lamp_name, False)
    except Exception as err:
        return command.fail(f"Failed turning on lamp {lamp.name}: {err}")

    return command.finish(**{lamp.name: lamp.state.name})
