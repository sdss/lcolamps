#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2022-08-14
# @Filename: lamps.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import enum
import re
import warnings
from dataclasses import dataclass
from time import time

from typing import TYPE_CHECKING, Any, Callable


if TYPE_CHECKING:
    from .actor import LCOLampsActor


WARM_UP_CALLBACK_CO = Callable[["Lamp"], Any] | None


class LampState(enum.Flag):
    """Status of a lamp."""

    OFF = 0x1
    WARMING = 0x2
    ON = 0x4
    UNKNOWN = 0x100


@dataclass
class Lamp:
    """One of the connected lamps."""

    name: str
    m2_name: str
    relay: int | None = None
    warm_up_time: float = 0
    on_time: float | None = None
    state: LampState = LampState.UNKNOWN

    def __post_init__(self):

        self._warmup_task: asyncio.Task | None = None

    def on(self, warm_up_time: float | None = None):
        """Sets the lamp as on."""

        if self.state & (LampState.ON | LampState.WARMING):
            return

        self.state = LampState.WARMING

        warm_up_time = warm_up_time or self.warm_up_time
        self._warm_up_task = asyncio.create_task(self._warm_up(warm_up_time))

        self.on_time = time()

    def off(self):
        """Sets the lamp as off."""

        if self.state & LampState.OFF:
            return

        self.state = LampState.OFF
        self.on_time = None

        if self._warmup_task is not None:
            self._warmup_task.cancel()
            self._warmup_task = None

    async def _warm_up(self, warm_up_time: float):
        """Waits until the lamps has been warmed up and changes the status."""

        await asyncio.sleep(warm_up_time)

        self.state = LampState.ON
        self._warmup_task = None


class LampsController:
    """Connection to the M2 LCO device."""

    def __init__(
        self,
        host: str,
        port: int,
        lamps: dict[str, dict] = {},
        actor: LCOLampsActor | None = None,
    ):

        self.host = host
        self.port = port

        self.actor = actor

        self.writer: asyncio.StreamWriter | None = None
        self.reader: asyncio.StreamReader | None = None

        self.lamps: dict[str, Lamp] = {}
        self._m2_to_lamp: dict[str, str] = {}

        for lamp in lamps:
            self.add_lamp(lamp, **lamps[lamp])

    def __repr__(self):

        lamps_status = []
        for lamp in self.lamps:
            status = self.lamps[lamp].state.name
            lamps_status.append(f"{lamp}={status}")

        lamps_status_str = ", ".join(lamps_status)

        return f"<LampsController ({lamps_status_str})>"

    def add_lamp(
        self,
        name: str,
        m2_name: str,
        relay: int | None = None,
        warm_up_time: float = 0.0,
    ):
        """Adds a lamp."""

        self.lamps[name.lower()] = Lamp(
            name=name,
            m2_name=m2_name,
            relay=relay,
            warm_up_time=warm_up_time,
        )
        self._m2_to_lamp[m2_name] = name

    async def connect(self):
        """Connects/reconnects to the server."""

        if self.writer is not None:
            await self.disconnect()

        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), 5
            )
        except asyncio.TimeoutError:
            raise RuntimeError("Timed out connecting to M2 controller.")

    async def disconnect(self):
        """Disconnects from the server."""

        if self.writer is None:
            return

        if not self.writer.is_closing():
            self.writer.close()
        await self.writer.wait_closed()

        self.writer = None
        self.reader = None

    def is_connected(self):
        """Returns whether the device is connected."""

        if self.writer is None:
            return False

        return self.writer.is_closing()

    async def send_command(self, command: str, disconnect: bool = True):
        """Sends a command to the device and returns the reply."""

        if not self.is_connected():
            await self.connect()

        if self.writer is None or self.reader is None:
            raise RuntimeError("Failed connecting to M2 server.")

        self.writer.write(command.encode())
        await self.writer.drain()

        try:
            reply = await asyncio.wait_for(self.reader.readline(), 3)
        except TimeoutError:
            raise RuntimeError(f"Timed out waiting for reply to command {command!r}.")
        finally:
            if disconnect:
                await self.disconnect()

        return reply.decode().strip()

    async def update(self):
        """Updates the status of the lamps."""

        status_str = await self.send_command("getlamps")

        status_list = re.findall(r"([A-Za-z0-9]+)=(\d)", status_str)

        for index, (m2_name, status_id) in enumerate(status_list):

            # Ignore unassigned lamps.
            if re.match("t[0-9]+", m2_name):
                continue

            # Add lamp if it's not in our current list.
            if m2_name not in self._m2_to_lamp:
                self.add_lamp(m2_name, m2_name=m2_name, relay=index + 1)

            lamp_name = self._m2_to_lamp[m2_name].lower()
            lamp = self.lamps[lamp_name]

            # If the lamp does not know its relay number, add it.
            if lamp.relay is None:
                lamp.relay = index + 1

            if status_id == "0":
                lamp.off()
            elif status_id == "1":
                lamp.on()
            else:
                # Use off because logic is similar but do not notify yet.
                lamp.off()
                lamp.state = LampState.UNKNOWN

    async def set(self, lamp_name, on: bool, warm_up_time: float | None = None):
        """Sets a lamp on or off."""

        if lamp_name.lower() not in self.lamps:
            raise ValueError(f"Unknown lamp {lamp_name}.")

        lamp_name = lamp_name.lower()
        lamp = self.lamps[lamp_name]

        await self.update()

        if on and (lamp.state & (LampState.ON | LampState.WARMING)):
            return
        elif on is False and (lamp.state & LampState.OFF):
            return
        elif lamp.state & LampState.UNKNOWN:
            warnings.warn(
                f"Status of lamp {lamp.name} is unknown. Will try to modify.",
                UserWarning,
            )

        m2_name = lamp.m2_name
        relay = lamp.relay

        if relay is None:
            raise RuntimeError(f"Missing relay number for lamp {lamp.name}.")

        command = "1" if on else "0"
        reply = await self.send_command(f"lamp {relay} {command}")

        if (on and m2_name not in reply) or ((on is False and m2_name in reply)):
            raise ValueError(f"Invalid reply {reply!r}")

        if on:
            lamp.on(warm_up_time=warm_up_time)
        else:
            lamp.off()
