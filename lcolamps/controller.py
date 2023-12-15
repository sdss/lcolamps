#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2022-08-14
# @Filename: controller.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import enum
import re
import warnings
from dataclasses import dataclass
from time import time

from typing import TYPE_CHECKING, Any, Callable, ClassVar

from clu.legacy.tron import KeysDictionary, TronKey, TronModel


if TYPE_CHECKING:
    from lcolamps.actor import LCOLampsActor


WARM_UP_CALLBACK_CO = Callable[["Lamp"], Any] | None


class LampState(enum.Flag):
    """Status of a lamp."""

    OFF = 0x1
    WARMING = 0x2
    ON = 0x4
    UNKNOWN = 0x100


@dataclass(kw_only=True)
class Lamp:
    """One of the connected lamps."""

    name: str
    warm_up_time: float = 0

    mode: ClassVar[str]

    def __post_init__(self):
        self.on_time: float | None = None
        self.state: LampState = LampState.UNKNOWN

        self._warmup_task: asyncio.Task | None = None

    def _on(self, warm_up_time: float | None = None):
        """Sets the lamp as on.

        This does not change the actual state of the lamp, just register its
        status as far as we know.

        """

        # If we start with the lamps on, just skip warming.
        if self.state == LampState.UNKNOWN:
            self.state = LampState.ON
            return

        if self.state & (LampState.ON | LampState.WARMING):
            return

        self.state = LampState.WARMING

        warm_up_time = warm_up_time or self.warm_up_time
        self._warm_up_task = asyncio.create_task(self._warm_up(warm_up_time))

        self.on_time = time()

    def _off(self):
        """Sets the lamp as off.

        This does not change the actual state of the lamp, just register its
        status as far as we know.

        """

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


@dataclass(kw_only=True)
class M2Lamp(Lamp):
    """An M2 lamp."""

    m2_name: str
    relay: int | None = None

    mode = "m2"


@dataclass(kw_only=True)
class ActorLamp(Lamp):
    """A lamp that's controlled by another actor."""

    actor_name: str
    command_on: str
    command_off: str
    command_status: str
    status_keyword: str
    actor: LCOLampsActor | None = None

    mode = "actor"

    def __post_init__(self):
        actor_name = self.actor_name

        if self.actor and self.actor.tron:
            tron = self.actor.tron
            if actor_name not in tron.models:
                tron.keyword_dicts[actor_name] = KeysDictionary.load(actor_name)

                model = TronModel(tron.keyword_dicts[actor_name])
                model[self.status_keyword].register_callback(self._update_state)
                tron.models[actor_name] = model

        return super().__post_init__()

    def _set_unknown(self, msg: str | None = None):
        """Sets the state to UNKNOWN."""

        self.state = LampState.UNKNOWN

        raise RuntimeError(msg or None)

    def _update_state(self, key: TronKey):
        """Sets the state of the lamp based on the lamp keyword."""

        assert self.actor is not None, "Actor not defined."

        if key.keyword:
            is_valid = str(key.keyword.values[0]).lower() != key.keyword[0].invalid
            if not is_valid:
                self._set_unknown(f"Invalid state for lamp {self.name!r}.")
                return

        state_value = key.value[0]
        if isinstance(state_value, (bool, int)):
            self._on() if bool(state_value) else self._off()
        elif isinstance(state_value, str):
            self._on() if bool(state_value) else self._off()
        else:
            self._set_unknown(f"Invalid state {state_value!r} for lamp {self.name!r}.")

    async def update(self):
        """Updates the state of the lamp."""

        if self.actor is None:
            self._set_unknown(f"No actor available. Cannot command lamp {self.name!r}.")
            return

        cmd = await self.actor.send_command(self.actor_name, self.command_status)
        if cmd.status.did_fail:
            self._set_unknown(f"Failed getting status for lamp {self.name!r}.")

    async def set_state(self, state: bool):
        """Sets the state of the lamp."""

        if self.actor is None:
            self._set_unknown(f"No actor available. Cannot command lamp {self.name!r}.")
            return

        cmd = await self.actor.send_command(
            self.actor_name,
            self.command_on if state else self.command_off,
        )
        if cmd.status.did_fail:
            self._set_unknown(f"Failed setting state for lamp {self.name!r}.")


@dataclass
class M2Controller:
    """A controller for the M2 lamps."""

    controller: LampsController
    host: str
    port: int

    def __post_init__(self):
        self.writer: asyncio.StreamWriter | None = None
        self.reader: asyncio.StreamReader | None = None

        self.lock = asyncio.Lock()

    async def connect(self):
        """Connects/reconnects to the server."""

        if self.writer is not None:
            await self.disconnect()

        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=5,
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

    async def send_command(self, command: str):
        """Sends a command to the device and returns the reply."""

        async with self.lock:
            if not self.is_connected():
                await self.connect()

            if self.writer is None or self.reader is None:
                raise RuntimeError("Failed connecting to M2 server.")

            self.writer.write(command.encode())
            await self.writer.drain()

            try:
                reply = await asyncio.wait_for(self.reader.readline(), 3)
            except TimeoutError:
                raise RuntimeError(f"Timed out waiting for reply to {command!r}.")
            finally:
                await self.disconnect()

        return reply.decode().strip()

    def get_m2_lamp(self, m2_name: str):
        """Returns the lamp with the given M2 name."""

        for lamp in self.controller.lamps.values():
            if lamp.mode == "m2" and getattr(lamp, "m2_name", "") == m2_name:
                return lamp

        return None

    async def update(self):
        """Updates the status of the M2 lamps."""

        status_str = await self.send_command("getlamps")

        status_list = re.findall(r"([A-Za-z0-9]+)=(\d)", status_str)

        for index, (m2_name, status_id) in enumerate(status_list):
            # Ignore unassigned lamps.
            if re.match("t[0-9]+", m2_name):
                continue

            m2_lamp = self.get_m2_lamp(m2_name)

            # Add lamp if it's not in our current list.
            if m2_lamp is None:
                m2_lamp = self.controller.add_lamp(
                    m2_name,
                    "m2",
                    m2_name=m2_name,
                    relay=index + 1,
                )

            assert isinstance(m2_lamp, M2Lamp)

            # If the lamp does not know its relay number, add it.
            if m2_lamp.relay is None:
                m2_lamp.relay = index + 1

            if status_id == "0":
                m2_lamp._off()
            elif status_id == "1":
                m2_lamp._on()
            else:
                # Use off because logic is similar but do not notify yet.
                m2_lamp._off()
                m2_lamp.state = LampState.UNKNOWN

    async def set_state(self, lamp: M2Lamp, state: bool):
        """Turns the lamp on or off."""

        m2_name = lamp.m2_name
        relay = lamp.relay

        if relay is None:
            raise RuntimeError(f"Missing relay number for lamp {lamp.name}.")

        command = "1" if state is True else "0"
        reply = await self.send_command(f"lamp {relay} {command}")

        if (state and m2_name not in reply) or ((state is False and m2_name in reply)):
            raise ValueError(f"Invalid reply {reply!r}")

        return True


class LampsController:
    """Controller for the lamps.

    Parameters
    ----------
    m2_params
        A tuple with the host and port of the M2 GUI server.
    lamps
        A dictionary of lamp name to lamp parameters. The value is passed
        directly to `.add_lamp`.

    """

    def __init__(
        self,
        m2_params: tuple[str, int] | None = None,
        lamps: dict[str, dict] = {},
        actor: LCOLampsActor | None = None,
    ):
        if m2_params:
            self.m2_controller = M2Controller(self, *m2_params)
        else:
            self.m2_controller = None

        self.actor = actor

        self.lamps: dict[str, Lamp] = {}
        if lamps:
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
        mode: str,
        **lamp_kwargs,
    ):
        """Adds a lamp."""

        if mode == "m2":
            lamp = M2Lamp(name=name, **lamp_kwargs)
        elif mode == "actor":
            lamp = ActorLamp(name=name, actor=self.actor, **lamp_kwargs)
        else:
            raise ValueError('Invalid mode. Must be "m2" or "actor".')

        self.lamps[name.lower()] = lamp

        return lamp

    async def update(self):
        """Updates the status of the lamps."""

        if self.m2_controller is not None:
            await self.m2_controller.update()

        await asyncio.gather(
            *[
                lamp.update()
                for lamp in self.lamps.values()
                if isinstance(lamp, ActorLamp)
            ]
        )

    async def set_state(
        self,
        lamp_name,
        state: bool,
        warm_up_time: float | None = None,
        update_status: bool = True,
    ):
        """Sets a lamp on or off."""

        if lamp_name.lower() not in self.lamps:
            raise ValueError(f"Unknown lamp {lamp_name}.")

        lamp_name = lamp_name.lower()
        lamp = self.lamps[lamp_name]

        if update_status:
            await self.update()

        if state and (lamp.state & (LampState.ON | LampState.WARMING)):
            return
        elif state is False and (lamp.state & LampState.OFF):
            return
        elif lamp.state & LampState.UNKNOWN:
            warnings.warn(
                f"Status of lamp {lamp.name} is unknown. Will try to modify.",
                UserWarning,
            )

        if isinstance(lamp, M2Lamp):
            if not self.m2_controller:
                raise RuntimeError("No M2 controller defined.")
            await self.m2_controller.set_state(lamp, state)

        elif isinstance(lamp, ActorLamp):
            await lamp.set_state(state)

        if state is True:
            lamp._on(warm_up_time=warm_up_time)
        else:
            lamp._off()
