from __future__ import annotations
from typing_extensions import Unpack
import typing as t
from typing_extensions import Self
import sys

from .connection import (
    BleConnection,
    EventHandler,
)

from .message import (
    DeviceInfo,
    Channel,
    ChannelArgs,
    Settings,
    PacketSettings,
    PacketSettingsArgs,
    EventMessage,
    SettingsChangedEvent,
    PacketReceivedEvent,
    ChannelChangedEvent,
    UnknownProtocolMessage,
)


class RadioClient:
    _device_uuid: str
    _is_connected: bool = False
    _conn: BleConnection
    _device_info: DeviceInfo
    _packet_settings: PacketSettings
    _settings: Settings
    _channels: t.List[Channel]
    _message_handler_unsubscribe: t.Callable[[], None]

    def __init__(self, device_uuid: str):
        self._device_uuid = device_uuid
        self._conn = BleConnection(device_uuid)

    def __repr__(self):
        if not self._is_connected:
            return f"<{self.__class__.__name__} {self.device_uuid} (disconnected)>"
        return f"<{self.__class__.__name__} {self.device_uuid} (connected)>"

    @property
    def packet_settings(self) -> PacketSettings:
        self._assert_conn()
        return self._packet_settings

    async def set_packet_settings(self, **packet_settings_args: Unpack[PacketSettingsArgs]):
        self._assert_conn()

        new_packet_settings = self._packet_settings.model_copy(
            update=dict(packet_settings_args)
        )

        await self._conn.set_packet_settings(new_packet_settings)

        self._packet_settings = new_packet_settings

    @property
    def settings(self) -> Settings:
        self._assert_conn()
        return self._settings

    @property
    def device_info(self) -> DeviceInfo:
        self._assert_conn()
        return self._device_info

    @property
    def channels(self) -> t.List[Channel]:
        self._assert_conn()
        return self._channels

    async def set_channel(
        self, channel_id: int, **channel_args: Unpack[ChannelArgs]
    ):
        self._assert_conn()

        new_channel = self._channels[channel_id].model_copy(
            update=dict(channel_args)
        )

        await self._conn.set_channel(new_channel)

        self._channels[channel_id] = new_channel

    @property
    def device_uuid(self) -> str:
        return self._device_uuid

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    async def battery_voltage(self) -> float:
        self._assert_conn()
        return await self._conn.get_battery_voltage()

    async def battery_level(self) -> int:
        self._assert_conn()
        return await self._conn.get_battery_level()

    async def battery_level_as_percentage(self) -> int:
        self._assert_conn()
        return await self._conn.get_battery_level_as_percentage()

    async def rc_battery_level(self) -> int:
        self._assert_conn()
        return await self._conn.get_rc_battery_level()

    def _assert_conn(self) -> None:
        if not self._is_connected:
            raise ValueError("Not connected")

    def register_event_handler(self, handler: EventHandler) -> t.Callable[[], None]:
        return self._conn.register_event_handler(handler)

    async def _hydrate(self) -> None:
        self._device_info = await self._conn.get_device_info()

        self._channels = []

        for i in range(self._device_info.channel_count):
            channel_settings = await self._conn.get_channel(i)
            self._channels.append(channel_settings)

        self._settings = await self._conn.get_settings()

        self._packet_settings = await self._conn.get_packet_settings()

    def _on_event_message(self, event_message: EventMessage) -> None:
        match event_message:
            case ChannelChangedEvent(channel):
                self._channels[channel.channel_id] = channel
            case SettingsChangedEvent(settings):
                self._settings = settings
            case PacketReceivedEvent():
                pass
            case UnknownProtocolMessage(message):
                print(
                    f"[DEBUG] Unknown protocol message: {message}",
                    file=sys.stderr
                )

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: t.Type[BaseException],
        exc_value: t.Type[BaseException],
        traceback: t.Type[BaseException]
    ) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        await self._conn.connect()
        await self._hydrate()
        self._message_handler_unsubscribe = self._conn.register_event_handler(
            self._on_event_message
        )
        self._is_connected = True

    async def disconnect(self) -> None:
        self._message_handler_unsubscribe()
        await self._conn.disconnect()
        self._is_connected = False
