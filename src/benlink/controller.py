"""
# Overview

This module provides a high-level async interface for communicating
with and controlling Benshi radios over BLE.

# Examples

To run the examples below, you will need to pair your radio with your computer,
locate the radio's device UUID (e.g. `XX:XX:XX:XX:XX:XX`), and substitute it
into the example code.

## Connecting To The Device

The following will connect to a radio and print its device info:

```python
import asyncio
from benlink.controller import RadioController

async def main():
    async with RadioController.new_ble("XX:XX:XX:XX:XX:XX") as radio:
        print(radio.device_info)

asyncio.run(main())
```

You can also connect to the radio over RFCOMM:

```python
import asyncio
from benlink.controller import RadioController

async def main():
    async with RadioController.new_rfcomm("XX:XX:XX:XX:XX:XX", channel=1) as radio:
        print(radio.device_info)

asyncio.run(main())
```

At the present, you have to figure out the correct channel number yourself (in Linux,
you can get a list of the available channels by running `sdptool records XX:XX:XX:XX:XX:XX`).
Planned support of channel autodetection can be tracked in [this issue](https://github.com/khusmann/benlink/issues/9).

## Changing Settings

The following will connect to a radio and change the name of the first channel:

```python
import asyncio
from benlink.controller import RadioController


async def main():
    async with RadioController.new_ble("XX:XX:XX:XX:XX:XX") as radio:
        print(f"Channel 0 name: {radio.channels[0].name}")
        print("Setting 0 name to Foo...")
        await radio.set_channel(0, name="Foo")
        print("Done")

asyncio.run(main())
```

## Handling Events

The `RadioController` class provides a `add_event_handler` method for
registering a callback function to handle events. The callback function
will be called with an `EventMessage` object whenever an event is
received from the radio.

Note that `add_event_handler` returns a function that can be called
to unregister the event handler.

```python
import asyncio
from benlink.controller import RadioController

async def main():
    async with RadioController.new_ble("XX:XX:XX:XX:XX:XX") as radio:
        def handle_event(event):
            print(f"Received event: {event}")

        unregister = radio.add_event_handler(handle_event)

        print("Try changing the channel or updating a radio setting")
        print()
        print("Press enter to quit...")
        await asyncio.to_thread(input)

asyncio.run(main())
```

# Interactive Usage

Python's async REPL is a great tool for interactively exploring the radio's
capabilities. To run Python's REPL in async mode, run:

```bash
python -m asyncio
```

Instead of using the async context manager (`async with RadioController(...) as radio:`),
you can use `await radio.connect()` and `await radio.disconnect()` to manage the
connection manually:

```python
from benlink.controller import RadioController

radio = RadioController.new_ble("XX:XX:XX:XX:XX:XX")

await radio.connect()

print(radio.device_info) # Prints device info

print(await radio.battery_voltage()) # Prints battery voltage

await radio.disconnect() # When you're done with your session disconnect nicely
```

Events registered with `add_event_handler` will run in the background:

```python
import asyncio
from benlink.controller import RadioController

radio = RadioController.new_ble("XX:XX:XX:XX:XX:XX")

await radio.connect()

unsubscribe = radio.add_event_handler(lambda x: print(f"Received event: {x}\n"))

# Change the channel on the radio a few times to generate some events

unsubscribe() # Unsubscribe the event handler

# Change the channel on the radio a few times to generate some events and
# observe that the event handler is no longer called

await radio.disconnect() # When you're done with your session disconnect nicely
```

(Note for IPython users: The IPython async REPL blocks the async event
loop while waiting for a prompt, so events will queue up until you defer 
execution to the event loop by running something like `await asyncio.sleep(0)`.)
"""


from __future__ import annotations
from typing_extensions import Unpack
from dataclasses import dataclass
import typing as t
import sys

from .command import (
    CommandConnection,
    EventHandler,
    DeviceInfo,
    Channel,
    ChannelArgs,
    Settings,
    SettingsArgs,
    BeaconSettings,
    BeaconSettingsArgs,
    TncDataFragment,
    EventMessage,
    SettingsChangedEvent,
    TncDataFragmentReceivedEvent,
    ChannelChangedEvent,
    StatusChangedEvent,
    UnknownProtocolMessage,
    Status
)


@dataclass
class _RadioState:
    device_info: DeviceInfo
    beacon_settings: BeaconSettings
    status: Status
    settings: Settings
    channels: t.List[Channel]


class RadioController:
    _conn: CommandConnection
    _state: _RadioState | None

    def __init__(self, connection: CommandConnection):
        self._conn = connection
        self._state = None

    @classmethod
    def new_ble(cls, device_uuid: str) -> RadioController:
        return RadioController(CommandConnection.new_ble(device_uuid))

    @classmethod
    def new_rfcomm(cls, device_uuid: str, channel: int | t.Literal["auto"] = "auto") -> RadioController:
        return RadioController(CommandConnection.new_rfcomm(device_uuid, channel))

    def __repr__(self):
        if not self.is_connected():
            return f"<{self.__class__.__name__} (disconnected)>"
        return f"<{self.__class__.__name__} (connected)>"

    @property
    def beacon_settings(self) -> BeaconSettings:
        if self._state is None:
            raise StateNotInitializedError()
        return self._state.beacon_settings

    async def set_beacon_settings(self, **packet_settings_args: Unpack[BeaconSettingsArgs]):
        if self._state is None:
            raise StateNotInitializedError()

        new_beacon_settings = self._state.beacon_settings.model_copy(
            update=dict(packet_settings_args)
        )

        await self._conn.set_beacon_settings(new_beacon_settings)

        self._state.beacon_settings = new_beacon_settings

    @property
    def status(self) -> Status:
        if self._state is None:
            raise StateNotInitializedError()
        return self._state.status

    @property
    def settings(self) -> Settings:
        if self._state is None:
            raise StateNotInitializedError()
        return self._state.settings

    async def set_settings(self, **settings_args: Unpack[SettingsArgs]):
        if self._state is None:
            raise StateNotInitializedError()

        new_settings = self._state.settings.model_copy(
            update=dict(settings_args)
        )

        await self._conn.set_settings(new_settings)

        self._state.settings = new_settings

    @property
    def device_info(self) -> DeviceInfo:
        if self._state is None:
            raise StateNotInitializedError()
        return self._state.device_info

    @property
    def channels(self) -> t.List[Channel]:
        if self._state is None:
            raise StateNotInitializedError()
        return self._state.channels

    async def set_channel(
        self, channel_id: int, **channel_args: Unpack[ChannelArgs]
    ):
        if self._state is None:
            raise StateNotInitializedError()

        new_channel = self._state.channels[channel_id].model_copy(
            update=dict(channel_args)
        )

        await self._conn.set_channel(new_channel)

        self._state.channels[channel_id] = new_channel

    def is_connected(self) -> bool:
        return self._state is not None and self._conn.is_connected()

    async def send_bytes(self, command: bytes) -> None:
        """For debugging - Use at your own risk!"""
        await self._conn.send_bytes(command)

    async def battery_voltage(self) -> float:
        return await self._conn.get_battery_voltage()

    async def battery_level(self) -> int:
        return await self._conn.get_battery_level()

    async def battery_level_as_percentage(self) -> int:
        return await self._conn.get_battery_level_as_percentage()

    async def rc_battery_level(self) -> int:
        return await self._conn.get_rc_battery_level()

    async def send_tnc_data(self, data: bytes) -> None:
        if len(data) > 50:
            raise ValueError("Data too long -- TODO: implement fragmentation")

        await self._conn.send_tnc_data_fragment(TncDataFragment(
            is_final_fragment=True,
            fragment_id=0,
            data=data
        ))

    def add_event_handler(self, handler: EventHandler) -> t.Callable[[], None]:
        return self._conn.add_event_handler(handler)

    async def _hydrate(self) -> None:
        device_info = await self._conn.get_device_info()

        channels: t.List[Channel] = []

        for i in range(device_info.channel_count):
            channel_settings = await self._conn.get_channel(i)
            channels.append(channel_settings)

        settings = await self._conn.get_settings()

        beacon_settings = await self._conn.get_beacon_settings()

        status = await self._conn.get_status()

        # No need to save the remove event handler function, since we don't
        # need to unregister it when we disconnect (the connection will take care of that)
        self._conn.add_event_handler(
            self._on_event_message
        )

        await self._conn.enable_events()

        self._state = _RadioState(
            device_info=device_info,
            beacon_settings=beacon_settings,
            status=status,
            settings=settings,
            channels=channels,
        )

    def _on_event_message(self, event_message: EventMessage) -> None:
        if self._state is None:
            raise ValueError(
                "Radio state not initialized. Try calling connect() first."
            )

        match event_message:
            case ChannelChangedEvent(channel):
                self._state.channels[channel.channel_id] = channel
            case SettingsChangedEvent(settings):
                self._state.settings = settings
            case TncDataFragmentReceivedEvent():
                pass
            case StatusChangedEvent(status):
                self._state.status = status
            case UnknownProtocolMessage(message):
                print(
                    f"[DEBUG] Unknown protocol message: {message}",
                    file=sys.stderr
                )

    # Async Context Manager
    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: t.Any,
        exc_value: t.Any,
        traceback: t.Any,
    ) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        if self._state is not None:
            raise RuntimeError("Already connected")

        await self._conn.connect()
        await self._hydrate()

    async def disconnect(self) -> None:
        if self._state is None:
            raise StateNotInitializedError()

        await self._conn.disconnect()
        self._state = None


class StateNotInitializedError(RuntimeError):
    """Raised when trying to access radio state before it has been initialized."""

    def __init__(self):
        super().__init__(
            "Radio state not initialized. Try calling connect() first."
        )
