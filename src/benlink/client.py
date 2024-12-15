from __future__ import annotations
from .messageframe import (
    Command,
    CommandGroupId,
    BasicCommandId,
    GetDevInfo,
    # GetDevInfoReply,
)
import typing as t
import asyncio
from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic

# from contextlib import contextmanager


class RadioClient:
    device_uuid: str
    is_connected: bool = False
    _connection: RadioConnection

    def __init__(self, device_uuid: str):
        self.device_uuid = device_uuid
        self._connection = RadioConnection(device_uuid)

    async def connect(self):
        await self._connection.connect()

        self.is_connected = True

    async def disconnect(self):
        await self._connection.disconnect()
        self.is_connected = False


RADIO_SERVICE_UUID = "00001100-d102-11e1-9b23-00025b00a5a5"
RADIO_WRITE_UUID = "00001101-d102-11e1-9b23-00025b00a5a5"
RADIO_INDICATE_UUID = "00001102-d102-11e1-9b23-00025b00a5a5"

CommandHandler = t.Callable[[Command], None]


class RadioConnection:
    _client: BleakClient
    handlers: t.List[CommandHandler] = []

    def __init__(self, device_uuid: str):
        self.device_uuid = device_uuid
        self._client = BleakClient(device_uuid)

    async def connect(self):
        await self._client.connect()

        await self._client.start_notify(
            RADIO_INDICATE_UUID, self._on_indication
        )

        reply = await self.send_command_expect_reply(
            Command(
                group_id=CommandGroupId.BASIC,
                is_reply=False,
                id=BasicCommandId.GET_DEV_INFO,
                body=GetDevInfo()
            )
        )

        print(reply)

    async def disconnect(self):
        await self._client.disconnect()

    async def send_command(self, command: Command):
        await self._client.write_gatt_char(
            RADIO_WRITE_UUID,
            command.to_bytes(),
            response=True
        )

    async def send_command_expect_reply(self, command: Command) -> Command:
        queue: asyncio.Queue[Command] = asyncio.Queue()

        def reply_handler(reply: Command):
            if reply.is_reply and reply.id == command.id:
                assert command.group_id == reply.group_id
                queue.put_nowait(reply)

        self.add_handler(reply_handler)

        await self.send_command(command)

        out = await queue.get()

        self.remove_handler(reply_handler)

        return out

    def add_handler(self, handler: CommandHandler):
        self.handlers.append(handler)

    def remove_handler(self, handler: CommandHandler):
        self.handlers.remove(handler)

    def _on_indication(self, characteristic: BleakGATTCharacteristic, data: bytearray):
        assert characteristic.uuid == RADIO_INDICATE_UUID
        command = Command.from_bytes(data)
        for handler in self.handlers:
            handler(command)
