from __future__ import annotations
from typing_extensions import Unpack
import typing as t
from .connection import (
    RadioConnection,
    DeviceInfo,
    ChannelSettings,
    ChannelSettingsArgs,
    RadioSettings,
    MessageHandler,
)
# from contextlib import contextmanager


class RadioClient:
    _device_uuid: str
    _is_connected: bool = False
    _conn: RadioConnection
    _device_info: DeviceInfo
    _settings: RadioSettings
    _channels: t.List[ChannelSettings]

    def __init__(self, device_uuid: str):
        self._device_uuid = device_uuid
        self._conn = RadioConnection(device_uuid)

    def __repr__(self):
        if not self._is_connected:
            return f"<RadioClient {self.device_uuid} (disconnected)>"
        return f"<RadioClient {self.device_uuid} (connected)>"

    @property
    def settings(self):
        self._assert_conn()
        return self._settings

    @property
    def device_info(self):
        self._assert_conn()
        return self._device_info

    @property
    def channels(self):
        self._assert_conn()
        return self._channels

    @property
    def device_uuid(self):
        return self._device_uuid

    @property
    def is_connected(self):
        return self._is_connected

    def _assert_conn(self):
        if not self._is_connected:
            raise ValueError("Not connected")

    def register_event_handler(self, handler: MessageHandler):
        return self._conn.register_message_handler(handler)

    async def set_channel(
        self, channel_id: int, **settings: Unpack[ChannelSettingsArgs]
    ):
        self._assert_conn()

        new_settings = self._channels[channel_id].model_copy(
            update=dict(settings)
        )

        await self._conn.set_channel_settings(new_settings)

        self._channels[channel_id] = new_settings

    async def _hydrate(self):
        self._device_info = await self._conn.get_device_info()

        self._channels = []

        for i in range(self._device_info.channel_count):
            channel_settings = await self._conn.get_channel_settings(i)
            self._channels.append(channel_settings)

        self._settings = await self._conn.get_radio_settings()

    async def connect(self):
        await self._conn.connect()
        await self._hydrate()
        self._is_connected = True

    async def disconnect(self):
        await self._conn.disconnect()
        self._is_connected = False
