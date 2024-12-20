from __future__ import annotations
import asyncio
from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from .message import *

import typing as t

RADIO_SERVICE_UUID = "00001100-d102-11e1-9b23-00025b00a5a5"
RADIO_WRITE_UUID = "00001101-d102-11e1-9b23-00025b00a5a5"
RADIO_INDICATE_UUID = "00001102-d102-11e1-9b23-00025b00a5a5"

RadioMessageHandler = t.Callable[[RadioMessage], None]

EventHandler = t.Callable[[EventMessage], None]


class RadioConnection:
    _client: BleakClient
    handlers: t.List[RadioMessageHandler] = []

    def __init__(self, device_uuid: str):
        self.device_uuid = device_uuid
        self._client = BleakClient(device_uuid)

    async def connect(self):
        await self._client.connect()

        await self._client.start_notify(
            RADIO_INDICATE_UUID, self._on_indication
        )

    async def disconnect(self):
        await self._client.disconnect()

    async def send_command(self, command: CommandMessage):
        await self._client.write_gatt_char(
            RADIO_WRITE_UUID,
            command_message_to_bytes(command),
            response=True
        )

    async def send_command_expect_reply(self, command: CommandMessage, expect: t.Type[ReplyMessageT]) -> ReplyMessageT | MessageReplyError:
        queue: asyncio.Queue[ReplyMessageT |
                             MessageReplyError] = asyncio.Queue()

        def reply_handler(reply: RadioMessage):
            if (
                isinstance(reply, expect) or
                (
                    isinstance(reply, MessageReplyError) and
                    reply.message_type is expect
                )
            ):
                queue.put_nowait(reply)

        remove_handler = self._register_message_handler(reply_handler)

        await self.send_command(command)

        out = await queue.get()

        remove_handler()

        return out

    def register_event_handler(self, handler: EventHandler):
        def event_handler(msg: RadioMessage):
            if isinstance(msg, EventMessage):
                handler(msg)
        return self._register_message_handler(event_handler)

    def _register_message_handler(self, handler: RadioMessageHandler):
        self.handlers.append(handler)

        def remove_handler():
            self.handlers.remove(handler)

        return remove_handler

    def _on_indication(self, characteristic: BleakGATTCharacteristic, data: bytearray):
        assert characteristic.uuid == RADIO_INDICATE_UUID
        radio_message = radio_message_from_bytes(data)
        for handler in self.handlers:
            handler(radio_message)

    # Commands

    async def get_packet_settings(self) -> PacketSettings:
        reply = await self.send_command_expect_reply(GetPacketSettings(), GetPacketSettingsReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()
        return reply.packet_settings

    async def set_packet_settings(self, packet_settings: PacketSettings):
        reply = await self.send_command_expect_reply(SetPacketSettings(packet_settings), SetPacketSettingsReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()

    async def get_battery_level(self) -> int:
        reply = await self.send_command_expect_reply(GetBatteryLevel(), GetBatteryLevelReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()
        return reply.battery_level

    async def get_battery_level_as_percentage(self) -> int:
        reply = await self.send_command_expect_reply(GetBatteryLevelAsPercentage(), GetBatteryLevelAsPercentageReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()
        return reply.battery_level_as_percentage

    async def get_rc_battery_level(self) -> int:
        reply = await self.send_command_expect_reply(GetRCBatteryLevel(), GetRCBatteryLevelReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()
        return reply.rc_battery_level

    async def get_battery_voltage(self) -> float:
        reply = await self.send_command_expect_reply(GetBatteryVoltage(), GetBatteryVoltageReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()
        return reply.battery_voltage

    async def get_device_info(self) -> DeviceInfo:
        reply = await self.send_command_expect_reply(GetDeviceInfo(), GetDeviceInfoReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()
        return reply.device_info

    async def get_settings(self) -> Settings:
        reply = await self.send_command_expect_reply(GetSettings(), GetSettingsReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()
        return reply.settings

    async def get_channel(self, channel_id: int) -> Channel:
        reply = await self.send_command_expect_reply(GetChannel(channel_id), GetChannelReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()
        return reply.channel

    async def set_channel(self, channel: Channel):
        reply = await self.send_command_expect_reply(SetChannel(channel), SetChannelReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()