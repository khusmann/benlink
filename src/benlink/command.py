"""
# Overview

This module defines a low-level interface for communicating
with a radio over BLE or Rfcomm.

Unless you know what you are doing, you probably want to use the
`benlink.controller` module instead.

# Messages

The `RadioMessage` type is a union of all the possible messages that can
sent or received from the radio.

It `RadioMessage`s are divided into three categories:

1. `CommandMessage`: Messages that are sent to the radio to request
    information or to change settings.

2. `ReplyMessage`: Messages that are received in response to a
    `CommandMessage`.

3. `EventMessage`: Messages that are received from the radio to indicate
    that an event has occurred. (e.g. a channel has changed, a packet has
    been received)

# Data

The data objects (e.g. `DeviceInfo`, `Settings`) are used to represent
the data that is sent or received in the messages. Some of these data
objects have accompanying `Args` types that are used in the API to allow
for functions that take keyword arguments to set these parameters.
"""

from __future__ import annotations
import typing as t
import asyncio
from pydantic import BaseModel, ConfigDict
from . import protocol as p
from .link import CommandLink, BleCommandLink, RfcommCommandLink

RADIO_SERVICE_UUID = "00001100-d102-11e1-9b23-00025b00a5a5"
"""@private"""

RADIO_WRITE_UUID = "00001101-d102-11e1-9b23-00025b00a5a5"
"""@private"""

RADIO_INDICATE_UUID = "00001102-d102-11e1-9b23-00025b00a5a5"
"""@private"""


class CommandConnection:
    _link: CommandLink
    _handlers: t.List[RadioMessageHandler] = []

    def __init__(self, link: CommandLink):
        self._link = link
        self._handlers = []

    @classmethod
    def new_ble(cls, device_uuid: str) -> CommandConnection:
        return cls(BleCommandLink(device_uuid))

    @classmethod
    def new_rfcomm(cls, device_uuid: str, channel: int | t.Literal["auto"] = "auto") -> CommandConnection:
        return cls(RfcommCommandLink(device_uuid, channel))

    def is_connected(self) -> bool:
        return self._link.is_connected()

    async def connect(self) -> None:
        await self._link.connect(self._on_recv)

    async def disconnect(self) -> None:
        self._handlers.clear()
        await self._link.disconnect()

    async def send_bytes(self, data: bytes) -> None:
        await self._link.send_bytes(data)

    async def send_message(self, command: CommandMessage) -> None:
        await self._link.send(command_message_to_protocol(command))

    async def send_message_expect_reply(self, command: CommandMessage, expect: t.Type[RadioMessageT]) -> RadioMessageT | MessageReplyError:
        queue: asyncio.Queue[RadioMessageT |
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

        remove_handler = self._add_message_handler(reply_handler)

        await self.send_message(command)

        out = await queue.get()

        remove_handler()

        return out

    def add_event_handler(self, handler: EventHandler) -> t.Callable[[], None]:
        def event_handler(msg: RadioMessage):
            if isinstance(msg, EventMessage):
                handler(msg)
        return self._add_message_handler(event_handler)

    def _add_message_handler(self, handler: RadioMessageHandler) -> t.Callable[[], None]:
        self._handlers.append(handler)

        def remove_handler():
            self._handlers.remove(handler)

        return remove_handler

    def _on_recv(self, msg: p.Message) -> None:
        radio_message = radio_message_from_protocol(msg)
        for handler in self._handlers:
            handler(radio_message)

    # Command API

    async def enable_events(self) -> None:
        """Enable an event"""
        # This event doesn't get a reply version of EnableEvents. It does, however
        # does trigger a StatusChangedEvent... but we don't wait for it here.
        # Instead, we just fire and forget
        await self.send_message(EnableEvents())

    async def send_tnc_data_fragment(self, tnc_data_fragment: TncDataFragment) -> None:
        """Send Tnc data"""
        reply = await self.send_message_expect_reply(SendTncDataFragment(tnc_data_fragment), SendTncDataFragmentReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()

    async def get_beacon_settings(self) -> BeaconSettings:
        """Get the current packet settings"""
        reply = await self.send_message_expect_reply(GetBeaconSettings(), GetBeaconSettingsReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()
        return reply.tnc_settings

    async def set_beacon_settings(self, packet_settings: BeaconSettings):
        """Set the packet settings"""
        reply = await self.send_message_expect_reply(SetBeaconSettings(packet_settings), SetBeaconSettingsReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()

    async def get_battery_level(self) -> int:
        """Get the battery level"""
        reply = await self.send_message_expect_reply(GetBatteryLevel(), GetBatteryLevelReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()
        return reply.battery_level

    async def get_battery_level_as_percentage(self) -> int:
        """Get the battery level as a percentage"""
        reply = await self.send_message_expect_reply(GetBatteryLevelAsPercentage(), GetBatteryLevelAsPercentageReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()
        return reply.battery_level_as_percentage

    async def get_rc_battery_level(self) -> int:
        """Get the RC battery level"""
        reply = await self.send_message_expect_reply(GetRCBatteryLevel(), GetRCBatteryLevelReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()
        return reply.rc_battery_level

    async def get_battery_voltage(self) -> float:
        """Get the battery voltage"""
        reply = await self.send_message_expect_reply(GetBatteryVoltage(), GetBatteryVoltageReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()
        return reply.battery_voltage

    async def get_device_info(self) -> DeviceInfo:
        """Get the device info"""
        reply = await self.send_message_expect_reply(GetDeviceInfo(), GetDeviceInfoReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()
        return reply.device_info

    async def get_settings(self) -> Settings:
        """Get the settings"""
        reply = await self.send_message_expect_reply(GetSettings(), GetSettingsReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()
        return reply.settings

    async def set_settings(self, settings: Settings) -> None:
        """Set the settings"""
        reply = await self.send_message_expect_reply(SetSettings(settings), SetSettingsReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()

    async def get_channel(self, channel_id: int) -> Channel:
        """Get a channel"""
        reply = await self.send_message_expect_reply(GetChannel(channel_id), GetChannelReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()
        return reply.channel

    async def set_channel(self, channel: Channel):
        """Set a channel"""
        reply = await self.send_message_expect_reply(SetChannel(channel), SetChannelReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()

    async def get_status(self) -> Status:
        """Get the radio status"""
        reply = await self.send_message_expect_reply(GetStatus(), GetStatusReply)
        if isinstance(reply, MessageReplyError):
            raise reply.as_exception()
        return reply.status

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


class ImmutableBaseModel(BaseModel):
    """@private (A base class for immutable data objects)"""

    model_config = ConfigDict(frozen=True)
    """@private"""


def command_message_to_protocol(m: CommandMessage) -> p.Message:
    """@private (Protocol helper)"""
    match m:
        case EnableEvents():
            # For some reason, enabling the HT_STATUS_CHANGED event
            # also enables the DATA_RXD event, and maybe others...
            # need to investigate further.
            return p.Message(
                command_group=p.CommandGroup.BASIC,
                is_reply=False,
                command=p.BasicCommand.REGISTER_NOTIFICATION,
                body=p.RegisterNotificationBody(
                    event_type=p.EventType.HT_STATUS_CHANGED,
                )
            )
        case SendTncDataFragment(tnc_data_fragment):
            return p.Message(
                command_group=p.CommandGroup.BASIC,
                is_reply=False,
                command=p.BasicCommand.HT_SEND_DATA,
                body=p.HTSendDataBody(
                    tnc_data_fragment=tnc_data_fragment.to_protocol()
                )
            )
        case GetBeaconSettings():
            return p.Message(
                command_group=p.CommandGroup.BASIC,
                is_reply=False,
                command=p.BasicCommand.READ_BSS_SETTINGS,
                body=p.ReadBSSSettingsBody()
            )
        case SetBeaconSettings(packet_settings):
            return p.Message(
                command_group=p.CommandGroup.BASIC,
                is_reply=False,
                command=p.BasicCommand.WRITE_BSS_SETTINGS,
                body=p.WriteBSSSettingsBody(
                    bss_settings=packet_settings.to_protocol()
                )
            )
        case GetSettings():
            return p.Message(
                command_group=p.CommandGroup.BASIC,
                is_reply=False,
                command=p.BasicCommand.READ_SETTINGS,
                body=p.ReadSettingsBody()
            )
        case SetSettings(settings):
            return p.Message(
                command_group=p.CommandGroup.BASIC,
                is_reply=False,
                command=p.BasicCommand.WRITE_SETTINGS,
                body=p.WriteSettingsBody(
                    settings=settings.to_protocol()
                )
            )
        case GetDeviceInfo():
            return p.Message(
                command_group=p.CommandGroup.BASIC,
                is_reply=False,
                command=p.BasicCommand.GET_DEV_INFO,
                body=p.GetDevInfoBody()
            )
        case GetChannel(channel_id):
            return p.Message(
                command_group=p.CommandGroup.BASIC,
                is_reply=False,
                command=p.BasicCommand.READ_RF_CH,
                body=p.ReadRFChBody(channel_id=channel_id)
            )
        case SetChannel(channel):
            return p.Message(
                command_group=p.CommandGroup.BASIC,
                is_reply=False,
                command=p.BasicCommand.WRITE_RF_CH,
                body=p.WriteRFChBody(
                    rf_ch=channel.to_protocol()
                )
            )
        case GetBatteryVoltage():
            return p.Message(
                command_group=p.CommandGroup.BASIC,
                is_reply=False,
                command=p.BasicCommand.READ_STATUS,
                body=p.ReadPowerStatusBody(
                    status_type=p.PowerStatusType.BATTERY_VOLTAGE
                )
            )
        case GetBatteryLevel():
            return p.Message(
                command_group=p.CommandGroup.BASIC,
                is_reply=False,
                command=p.BasicCommand.READ_STATUS,
                body=p.ReadPowerStatusBody(
                    status_type=p.PowerStatusType.BATTERY_LEVEL
                )
            )
        case GetBatteryLevelAsPercentage():
            return p.Message(
                command_group=p.CommandGroup.BASIC,
                is_reply=False,
                command=p.BasicCommand.READ_STATUS,
                body=p.ReadPowerStatusBody(
                    status_type=p.PowerStatusType.BATTERY_LEVEL_AS_PERCENTAGE
                )
            )
        case GetRCBatteryLevel():
            return p.Message(
                command_group=p.CommandGroup.BASIC,
                is_reply=False,
                command=p.BasicCommand.READ_STATUS,
                body=p.ReadPowerStatusBody(
                    status_type=p.PowerStatusType.RC_BATTERY_LEVEL
                )
            )
        case GetStatus():
            return p.Message(
                command_group=p.CommandGroup.BASIC,
                is_reply=False,
                command=p.BasicCommand.GET_HT_STATUS,
                body=p.GetHtStatusBody()
            )


def radio_message_from_protocol(mf: p.Message) -> RadioMessage:
    """@private (Protocol helper)"""
    match mf.body:
        case p.GetHtStatusReplyBody(reply_status=reply_status, status=status):
            if status is None:
                return MessageReplyError(
                    message_type=GetStatusReply,
                    reason=reply_status.name,
                )
            return GetStatusReply(Status.from_protocol(status))
        case p.HTSendDataReplyBody(
            reply_status=reply_status
        ):
            if reply_status != p.ReplyStatus.SUCCESS:
                return MessageReplyError(
                    message_type=SendTncDataFragmentReply,
                    reason=reply_status.name,
                )
            return SendTncDataFragmentReply()
        case p.ReadBSSSettingsReplyBody(
            reply_status=reply_status,
            bss_settings=bss_settings,
        ):
            if bss_settings is None:
                return MessageReplyError(
                    message_type=GetBeaconSettingsReply,
                    reason=reply_status.name,
                )

            return GetBeaconSettingsReply(BeaconSettings.from_protocol(bss_settings))
        case p.WriteBSSSettingsReplyBody(
            reply_status=reply_status,
        ):
            if reply_status != p.ReplyStatus.SUCCESS:
                return MessageReplyError(
                    message_type=SetBeaconSettingsReply,
                    reason=reply_status.name,
                )
            return SetBeaconSettingsReply()
        case p.ReadPowerStatusReplyBody(
            reply_status=reply_status,
            status=power_status
        ):
            if power_status is None:
                return MessageReplyError(
                    message_type=GetBatteryVoltageReply,
                    reason=reply_status.name,
                )

            match power_status.value:
                case p.BatteryVoltageStatus(
                    battery_voltage=battery_voltage
                ):
                    return GetBatteryVoltageReply(
                        battery_voltage=battery_voltage
                    )
                case p.BatteryLevelPercentageStatus(
                    battery_level_as_percentage=battery_level_as_percentage
                ):
                    return GetBatteryLevelAsPercentageReply(
                        battery_level_as_percentage=battery_level_as_percentage
                    )
                case p.BatteryLevelStatus(
                    battery_level=battery_level
                ):
                    return GetBatteryLevelReply(
                        battery_level=battery_level
                    )
                case p.RCBatteryLevelStatus(
                    rc_battery_level=rc_battery_level
                ):
                    return GetRCBatteryLevelReply(
                        rc_battery_level=rc_battery_level
                    )
        case p.EventNotificationBody(
            event=event
        ):
            match event:
                case p.HTSettingsChangedEvent(
                    settings=settings
                ):
                    return SettingsChangedEvent(Settings.from_protocol(settings))
                case p.DataRxdEvent(
                    tnc_data_fragment=tnc_data_fragment
                ):
                    return TncDataFragmentReceivedEvent(
                        tnc_data_fragment=TncDataFragment.from_protocol(
                            tnc_data_fragment
                        )
                    )
                case p.HTChChangedEvent(
                    rf_ch=rf_ch
                ):
                    return ChannelChangedEvent(Channel.from_protocol(rf_ch))
                case p.HTStatusChangedEvent(
                    status=status
                ):
                    return StatusChangedEvent(Status.from_protocol(status))
                case _:
                    return UnknownProtocolMessage(mf)
        case p.ReadSettingsReplyBody(
            reply_status=reply_status,
            settings=settings
        ):
            if settings is None:
                return MessageReplyError(
                    message_type=GetSettingsReply,
                    reason=reply_status.name,
                )
            return GetSettingsReply(Settings.from_protocol(settings))
        case p.WriteSettingsReplyBody(
            reply_status=reply_status,
        ):
            if reply_status != p.ReplyStatus.SUCCESS:
                return MessageReplyError(
                    message_type=SetSettingsReply,
                    reason=reply_status.name,
                )
            return SetSettingsReply()
        case p.GetDevInfoReplyBody(
            reply_status=reply_status,
            dev_info=dev_info
        ):
            if dev_info is None:
                return MessageReplyError(
                    message_type=GetDeviceInfoReply,
                    reason=reply_status.name,
                )
            return GetDeviceInfoReply(DeviceInfo.from_protocol(dev_info))
        case p.ReadRFChReplyBody(
            reply_status=reply_status,
            rf_ch=rf_ch
        ):
            if rf_ch is None:
                return MessageReplyError(
                    message_type=GetChannelReply,
                    reason=reply_status.name,
                )
            return GetChannelReply(Channel.from_protocol(rf_ch))
        case p.WriteRFChReplyBody(
            reply_status=reply_status,
        ):
            if reply_status != p.ReplyStatus.SUCCESS:
                return MessageReplyError(
                    message_type=SetChannelReply,
                    reason=reply_status.name,
                )
            return SetChannelReply()

        case _:
            return UnknownProtocolMessage(mf)


#####################
# CommandMessage

class EnableEvents(t.NamedTuple):
    pass


class GetBeaconSettings(t.NamedTuple):
    pass


class SetBeaconSettings(t.NamedTuple):
    tnc_settings: BeaconSettings


class SetSettings(t.NamedTuple):
    settings: Settings


class GetBatteryLevelAsPercentage(t.NamedTuple):
    pass


class GetRCBatteryLevel(t.NamedTuple):
    pass


class GetBatteryLevel(t.NamedTuple):
    pass


class GetBatteryVoltage(t.NamedTuple):
    pass


class GetDeviceInfo(t.NamedTuple):
    pass


class GetChannel(t.NamedTuple):
    channel_id: int


class SetChannel(t.NamedTuple):
    channel: Channel


class GetSettings(t.NamedTuple):
    pass


class GetStatus(t.NamedTuple):
    pass


class SendTncDataFragment(t.NamedTuple):
    tnc_data_fragment: TncDataFragment


CommandMessage = t.Union[
    GetBeaconSettings,
    SetBeaconSettings,
    GetRCBatteryLevel,
    GetBatteryLevelAsPercentage,
    GetBatteryLevel,
    GetBatteryVoltage,
    GetDeviceInfo,
    GetChannel,
    SetChannel,
    GetSettings,
    SetSettings,
    SendTncDataFragment,
    EnableEvents,
    GetStatus,
]

#####################
# ReplyMessage


class SendTncDataFragmentReply(t.NamedTuple):
    pass


class GetBeaconSettingsReply(t.NamedTuple):
    tnc_settings: BeaconSettings


class SetBeaconSettingsReply(t.NamedTuple):
    pass


class SetSettingsReply(t.NamedTuple):
    pass


class GetBatteryLevelAsPercentageReply(t.NamedTuple):
    battery_level_as_percentage: int


class GetRCBatteryLevelReply(t.NamedTuple):
    rc_battery_level: int


class GetBatteryLevelReply(t.NamedTuple):
    battery_level: int


class GetBatteryVoltageReply(t.NamedTuple):
    battery_voltage: float


class GetDeviceInfoReply(t.NamedTuple):
    device_info: DeviceInfo


class GetChannelReply(t.NamedTuple):
    channel: Channel


class SetChannelReply(t.NamedTuple):
    pass


class GetStatusReply(t.NamedTuple):
    status: Status


class GetSettingsReply(t.NamedTuple):
    settings: Settings


ReplyStatus = t.Literal[
    "SUCCESS",
    "NOT_SUPPORTED",
    "NOT_AUTHENTICATED",
    "INSUFFICIENT_RESOURCES",
    "AUTHENTICATING",
    "INVALID_PARAMETER",
    "INCORRECT_STATE",
    "IN_PROGRESS",
]


class MessageReplyError(t.NamedTuple):
    message_type: t.Type[t.Any]
    reason: ReplyStatus

    def as_exception(self):
        return ValueError(f"{self.message_type.__name__} failed: {self.reason}")


ReplyMessage = t.Union[
    GetBeaconSettingsReply,
    SetBeaconSettingsReply,
    GetBatteryLevelAsPercentageReply,
    GetRCBatteryLevelReply,
    GetBatteryLevelReply,
    GetBatteryVoltageReply,
    GetDeviceInfoReply,
    GetChannelReply,
    SetChannelReply,
    GetSettingsReply,
    SetSettingsReply,
    SendTncDataFragmentReply,
    GetStatusReply,
    MessageReplyError,
]

#####################
# EventMessage


class StatusChangedEvent(t.NamedTuple):
    status: Status


class ChannelChangedEvent(t.NamedTuple):
    channel: Channel


class TncDataFragmentReceivedEvent(t.NamedTuple):
    tnc_data_fragment: TncDataFragment


class SettingsChangedEvent(t.NamedTuple):
    settings: Settings


class UnknownProtocolMessage(t.NamedTuple):
    message: p.Message


EventMessage = t.Union[
    TncDataFragmentReceivedEvent,
    SettingsChangedEvent,
    UnknownProtocolMessage,
    ChannelChangedEvent,
    StatusChangedEvent,
]

RadioMessage = ReplyMessage | EventMessage

RadioMessageT = t.TypeVar("RadioMessageT", bound=RadioMessage)

#####################
# Handlers

RadioMessageHandler = t.Callable[[RadioMessage], None]
"""@private"""

EventHandler = t.Callable[[EventMessage], None]
"""@private"""

#####################
# Protocol to data object conversions


class IntSplit(t.NamedTuple):
    """@private (A helper for working with integers split into upper and lower parts)"""

    n_upper: int
    n_lower: int

    def from_parts(self, upper: int, lower: int) -> int:
        if upper >= 1 << self.n_upper:
            raise ValueError(
                f"Upper part {upper} is too large for {self.n_upper} bits")
        if lower >= 1 << self.n_lower:
            raise ValueError(
                f"Lower part {lower} is too large for {self.n_lower} bits")

        return (upper << self.n_lower) | lower

    def get_upper(self, n: int) -> int:
        if n >= 1 << (self.n_upper + self.n_lower):
            raise ValueError(
                f"Value {n} is too large for {self.n_upper + self.n_lower} bits"
            )
        return n >> self.n_lower

    def get_lower(self, n: int) -> int:
        if n >= 1 << (self.n_upper + self.n_lower):
            raise ValueError(
                f"Value {n} is too large for {self.n_upper + self.n_lower} bits"
            )
        return n & ((1 << self.n_lower) - 1)


class TncDataFragment(ImmutableBaseModel):
    """A data object representing a message packet"""
    is_final_fragment: bool
    fragment_id: int
    data: bytes
    channel_id: int | None = None

    @classmethod
    def from_protocol(cls, mp: p.TncDataFragment) -> TncDataFragment:
        """@private (Protocol helper)"""
        return TncDataFragment(
            is_final_fragment=mp.is_final_fragment,
            fragment_id=mp.fragment_id,
            data=mp.data,
            channel_id=mp.channel_id
        )

    def to_protocol(self) -> p.TncDataFragment:
        """@private (Protocol helper)"""
        return p.TncDataFragment(
            is_final_fragment=self.is_final_fragment,
            with_channel_id=self.channel_id is not None,
            fragment_id=self.fragment_id,
            data=self.data,
            channel_id=self.channel_id
        )


ModulationType = t.Literal["AM", "FM", "DMR"]

BandwidthType = t.Literal["NARROW", "WIDE"]


class DCS(t.NamedTuple):
    """A type for setting Digital Coded Squelch (DCS) on channels"""

    n: int
    """The DCS Normal (N) code"""


def sub_audio_from_protocol(x: float | p.DCS | None) -> float | DCS | None:
    """@private (Protocol helper)"""
    match x:
        case p.DCS(n):
            return DCS(n=n)
        case _:
            return x


def sub_audio_to_protocol(x: float | DCS | None) -> float | p.DCS | None:
    """@private (Protocol helper)"""
    match x:
        case DCS(n):
            return p.DCS(n=n)
        case _:
            return x


class ChannelArgs(t.TypedDict, total=False):
    """A dictionary of the parameters that can be set on a channel"""
    tx_mod: ModulationType
    tx_freq: float
    rx_mod: ModulationType
    rx_freq: float
    tx_sub_audio: float | DCS | None
    rx_sub_audio: float | DCS | None
    scan: bool
    tx_at_max_power: bool
    talk_around: bool
    bandwidth: BandwidthType
    pre_de_emph_bypass: bool
    sign: bool
    tx_at_med_power: bool
    tx_disable: bool
    fixed_freq: bool
    fixed_bandwidth: bool
    fixed_tx_power: bool
    mute: bool
    name: str


class Channel(ImmutableBaseModel):
    """A data object representing a radio channel"""
    channel_id: int
    tx_mod: ModulationType
    tx_freq: float
    rx_mod: ModulationType
    rx_freq: float
    tx_sub_audio: float | DCS | None
    rx_sub_audio: float | DCS | None
    scan: bool
    tx_at_max_power: bool
    talk_around: bool
    bandwidth: BandwidthType
    pre_de_emph_bypass: bool
    sign: bool
    tx_at_med_power: bool
    tx_disable: bool
    fixed_freq: bool
    fixed_bandwidth: bool
    fixed_tx_power: bool
    mute: bool
    name: str

    @classmethod
    def from_protocol(cls, cs: p.RfCh) -> Channel:
        """@private (Protocol helper)"""
        return Channel(
            channel_id=cs.channel_id,
            tx_mod=cs.tx_mod.name,
            tx_freq=cs.tx_freq,
            rx_mod=cs.rx_mod.name,
            rx_freq=cs.rx_freq,
            tx_sub_audio=sub_audio_from_protocol(cs.tx_sub_audio),
            rx_sub_audio=sub_audio_from_protocol(cs.rx_sub_audio),
            scan=cs.scan,
            tx_at_max_power=cs.tx_at_max_power,
            talk_around=cs.talk_around,
            bandwidth=cs.bandwidth.name,
            pre_de_emph_bypass=cs.pre_de_emph_bypass,
            sign=cs.sign,
            tx_at_med_power=cs.tx_at_med_power,
            tx_disable=cs.tx_disable,
            fixed_freq=cs.fixed_freq,
            fixed_bandwidth=cs.fixed_bandwidth,
            fixed_tx_power=cs.fixed_tx_power,
            mute=cs.mute,
            name=cs.name_str
        )

    def to_protocol(self) -> p.RfCh:
        """@private (Protocol helper)"""
        return p.RfCh(
            channel_id=self.channel_id,
            tx_mod=p.ModulationType[self.tx_mod],
            tx_freq=self.tx_freq,
            rx_mod=p.ModulationType[self.rx_mod],
            rx_freq=self.rx_freq,
            tx_sub_audio=sub_audio_to_protocol(self.tx_sub_audio),
            rx_sub_audio=sub_audio_to_protocol(self.rx_sub_audio),
            scan=self.scan,
            tx_at_max_power=self.tx_at_max_power,
            talk_around=self.talk_around,
            bandwidth=p.BandwidthType[self.bandwidth],
            pre_de_emph_bypass=self.pre_de_emph_bypass,
            sign=self.sign,
            tx_at_med_power=self.tx_at_med_power,
            tx_disable=self.tx_disable,
            fixed_freq=self.fixed_freq,
            fixed_bandwidth=self.fixed_bandwidth,
            fixed_tx_power=self.fixed_tx_power,
            mute=self.mute,
            name_str=self.name
        )


class SettingsArgs(t.TypedDict, total=False):
    """A dictionary of the parameters that can be set in the radio settings"""
    channel_a: int
    channel_b: int
    scan: bool
    aghfp_call_mode: int
    double_channel: int
    squelch_level: int
    tail_elim: bool
    auto_relay_en: bool
    auto_power_on: bool
    keep_aghfp_link: bool
    mic_gain: int
    tx_hold_time: int
    tx_time_limit: int
    local_speaker: int
    bt_mic_gain: int
    adaptive_response: bool
    dis_tone: bool
    power_saving_mode: bool
    auto_power_off: int
    auto_share_loc_ch: int | t.Literal["current"]
    hm_speaker: int
    positioning_system: int
    time_offset: int
    use_freq_range_2: bool
    ptt_lock: bool
    leading_sync_bit_en: bool
    pairing_at_power_on: bool
    screen_timeout: int
    vfo_x: int
    imperial_unit: bool
    wx_mode: int
    noaa_ch: int
    vfol_tx_power_x: int
    vfo2_tx_power_x: int
    dis_digital_mute: bool
    signaling_ecc_en: bool
    ch_data_lock: bool
    vfo1_mod_freq_x: int
    vfo2_mod_freq_x: int


class Settings(ImmutableBaseModel):
    """A data object representing the radio settings"""
    _channel_split: t.ClassVar[IntSplit] = IntSplit(4, 4)
    channel_a: int
    channel_b: int
    scan: bool
    aghfp_call_mode: int
    double_channel: int
    squelch_level: int
    tail_elim: bool
    auto_relay_en: bool
    auto_power_on: bool
    keep_aghfp_link: bool
    mic_gain: int
    tx_hold_time: int
    tx_time_limit: int
    local_speaker: int
    bt_mic_gain: int
    adaptive_response: bool
    dis_tone: bool
    power_saving_mode: bool
    auto_power_off: int
    auto_share_loc_ch: int | t.Literal["current"]
    hm_speaker: int
    positioning_system: int
    time_offset: int
    use_freq_range_2: bool
    ptt_lock: bool
    leading_sync_bit_en: bool
    pairing_at_power_on: bool
    screen_timeout: int
    vfo_x: int
    imperial_unit: bool
    wx_mode: int
    noaa_ch: int
    vfol_tx_power_x: int
    vfo2_tx_power_x: int
    dis_digital_mute: bool
    signaling_ecc_en: bool
    ch_data_lock: bool
    vfo1_mod_freq_x: int
    vfo2_mod_freq_x: int

    @classmethod
    def from_protocol(cls, rs: p.Settings) -> Settings:
        """@private (Protocol helper)"""
        return Settings(
            channel_a=cls._channel_split.from_parts(
                rs.channel_a_upper, rs.channel_a_lower
            ),
            channel_b=cls._channel_split.from_parts(
                rs.channel_b_upper, rs.channel_b_lower
            ),
            scan=rs.scan,
            aghfp_call_mode=rs.aghfp_call_mode,
            double_channel=rs.double_channel,
            squelch_level=rs.squelch_level,
            tail_elim=rs.tail_elim,
            auto_relay_en=rs.auto_relay_en,
            auto_power_on=rs.auto_power_on,
            keep_aghfp_link=rs.keep_aghfp_link,
            mic_gain=rs.mic_gain,
            tx_hold_time=rs.tx_hold_time,
            tx_time_limit=rs.tx_time_limit,
            local_speaker=rs.local_speaker,
            bt_mic_gain=rs.bt_mic_gain,
            adaptive_response=rs.adaptive_response,
            dis_tone=rs.dis_tone,
            power_saving_mode=rs.power_saving_mode,
            auto_power_off=rs.auto_power_off,
            auto_share_loc_ch=rs.auto_share_loc_ch,
            hm_speaker=rs.hm_speaker,
            positioning_system=rs.positioning_system,
            time_offset=rs.time_offset,
            use_freq_range_2=rs.use_freq_range_2,
            ptt_lock=rs.ptt_lock,
            leading_sync_bit_en=rs.leading_sync_bit_en,
            pairing_at_power_on=rs.pairing_at_power_on,
            screen_timeout=rs.screen_timeout,
            vfo_x=rs.vfo_x,
            imperial_unit=rs.imperial_unit,
            wx_mode=rs.wx_mode,
            noaa_ch=rs.noaa_ch,
            vfol_tx_power_x=rs.vfol_tx_power_x,
            vfo2_tx_power_x=rs.vfo2_tx_power_x,
            dis_digital_mute=rs.dis_digital_mute,
            signaling_ecc_en=rs.signaling_ecc_en,
            ch_data_lock=rs.ch_data_lock,
            vfo1_mod_freq_x=rs.vfo1_mod_freq_x,
            vfo2_mod_freq_x=rs.vfo2_mod_freq_x
        )

    def to_protocol(self):
        """@private (Protocol helper)"""
        return p.Settings(
            channel_a_lower=self._channel_split.get_lower(self.channel_a),
            channel_b_lower=self._channel_split.get_lower(self.channel_b),
            scan=self.scan,
            aghfp_call_mode=self.aghfp_call_mode,
            double_channel=self.double_channel,
            squelch_level=self.squelch_level,
            tail_elim=self.tail_elim,
            auto_relay_en=self.auto_relay_en,
            auto_power_on=self.auto_power_on,
            keep_aghfp_link=self.keep_aghfp_link,
            mic_gain=self.mic_gain,
            tx_hold_time=self.tx_hold_time,
            tx_time_limit=self.tx_time_limit,
            local_speaker=self.local_speaker,
            bt_mic_gain=self.bt_mic_gain,
            adaptive_response=self.adaptive_response,
            dis_tone=self.dis_tone,
            power_saving_mode=self.power_saving_mode,
            auto_power_off=self.auto_power_off,
            auto_share_loc_ch=self.auto_share_loc_ch,
            hm_speaker=self.hm_speaker,
            positioning_system=self.positioning_system,
            time_offset=self.time_offset,
            use_freq_range_2=self.use_freq_range_2,
            ptt_lock=self.ptt_lock,
            leading_sync_bit_en=self.leading_sync_bit_en,
            pairing_at_power_on=self.pairing_at_power_on,
            screen_timeout=self.screen_timeout,
            vfo_x=self.vfo_x,
            imperial_unit=self.imperial_unit,
            channel_a_upper=self._channel_split.get_upper(self.channel_a),
            channel_b_upper=self._channel_split.get_upper(self.channel_b),
            wx_mode=self.wx_mode,
            noaa_ch=self.noaa_ch,
            vfol_tx_power_x=self.vfol_tx_power_x,
            vfo2_tx_power_x=self.vfo2_tx_power_x,
            dis_digital_mute=self.dis_digital_mute,
            signaling_ecc_en=self.signaling_ecc_en,
            ch_data_lock=self.ch_data_lock,
            vfo1_mod_freq_x=self.vfo1_mod_freq_x,
            vfo2_mod_freq_x=self.vfo2_mod_freq_x
        )


class DeviceInfo(ImmutableBaseModel):
    """A data object representing the device information"""
    vendor_id: int
    product_id: int
    hardware_version: int
    firmware_version: int
    supports_radio: bool
    supports_medium_power: bool
    fixed_location_speaker_volume: bool
    has_speaker: bool
    has_hand_microphone_speaker: bool
    region_count: int
    supports_noaa: bool
    supports_gmrs: bool
    supports_vfo: bool
    supports_dmr: bool
    supports_software_power_control: bool
    channel_count: int
    frequency_range_count: int

    @classmethod
    def from_protocol(cls, info: p.DevInfo) -> DeviceInfo:
        """@private (Protocol helper)"""
        return DeviceInfo(
            vendor_id=info.vendor_id,
            product_id=info.product_id,
            hardware_version=info.hw_ver,
            firmware_version=info.soft_ver,
            supports_radio=info.support_radio,
            supports_medium_power=info.support_medium_power,
            fixed_location_speaker_volume=info.fixed_loc_speaker_vol,
            supports_software_power_control=not info.not_support_soft_power_ctrl,
            has_speaker=not info.have_no_speaker,
            has_hand_microphone_speaker=info.have_hm_speaker,
            region_count=info.region_count,
            supports_noaa=info.support_noaa,
            supports_gmrs=info.gmrs,
            supports_vfo=info.support_vfo,
            supports_dmr=info.support_dmr,
            channel_count=info.channel_count,
            frequency_range_count=info.freq_range_count
        )

    def to_protocol(self) -> p.DevInfo:
        """@private (Protocol helper)"""
        return p.DevInfo(
            vendor_id=self.vendor_id,
            product_id=self.product_id,
            hw_ver=self.hardware_version,
            soft_ver=self.firmware_version,
            support_radio=self.supports_radio,
            support_medium_power=self.supports_medium_power,
            fixed_loc_speaker_vol=self.fixed_location_speaker_volume,
            not_support_soft_power_ctrl=not self.supports_software_power_control,
            have_no_speaker=not self.has_speaker,
            have_hm_speaker=self.has_hand_microphone_speaker,
            region_count=self.region_count,
            support_noaa=self.supports_noaa,
            gmrs=self.supports_gmrs,
            support_vfo=self.supports_vfo,
            support_dmr=self.supports_dmr,
            channel_count=self.channel_count,
            freq_range_count=self.frequency_range_count
        )


class BeaconSettingsArgs(t.TypedDict, total=False):
    """A dictionary of the parameters that can be set in the beacon settings"""
    max_fwd_times: int
    time_to_live: int
    ptt_release_send_location: bool
    ptt_release_send_id_info: bool
    ptt_release_send_bss_user_id: bool
    should_share_location: bool
    send_pwr_voltage: bool
    packet_format: t.Literal["BSS", "APRS"]
    allow_position_check: bool
    aprs_ssid: int
    location_share_interval: int
    bss_user_id: int
    ptt_release_id_info: str
    beacon_message: str
    aprs_symbol: str
    aprs_callsign: str


class BeaconSettings(ImmutableBaseModel):
    """A data object representing the beacon settings"""
    _bss_user_id_split: t.ClassVar[IntSplit] = IntSplit(32, 32)
    max_fwd_times: int
    time_to_live: int
    ptt_release_send_location: bool
    ptt_release_send_id_info: bool
    ptt_release_send_bss_user_id: bool
    should_share_location: bool
    send_pwr_voltage: bool
    packet_format: t.Literal["BSS", "APRS"]
    allow_position_check: bool
    aprs_ssid: int
    location_share_interval: int
    bss_user_id: int
    ptt_release_id_info: str
    beacon_message: str
    aprs_symbol: str
    aprs_callsign: str

    @classmethod
    def from_protocol(cls, bs: p.BSSSettingsExt | p.BSSSettings) -> BeaconSettings:
        """@private (Protocol helper)"""

        if not isinstance(bs, p.BSSSettingsExt):
            raise ValueError(
                "Radio replied with old BSSSettings message version. Upgrade your firmware!"
            )

        return BeaconSettings(
            max_fwd_times=bs.max_fwd_times,
            time_to_live=bs.time_to_live,
            ptt_release_send_location=bs.ptt_release_send_location,
            ptt_release_send_id_info=bs.ptt_release_send_id_info,
            ptt_release_send_bss_user_id=bs.ptt_release_send_bss_user_id,
            should_share_location=bs.should_share_location,
            send_pwr_voltage=bs.send_pwr_voltage,
            packet_format=bs.packet_format.name,
            allow_position_check=bs.allow_position_check,
            aprs_ssid=bs.aprs_ssid,
            location_share_interval=bs.location_share_interval,
            bss_user_id=cls._bss_user_id_split.from_parts(
                bs.bss_user_id_upper, bs.bss_user_id_lower
            ),
            ptt_release_id_info=bs.ptt_release_id_info,
            beacon_message=bs.beacon_message,
            aprs_symbol=bs.aprs_symbol,
            aprs_callsign=bs.aprs_callsign
        )

    def to_protocol(self) -> p.BSSSettingsExt:
        """@private (Protocol helper)"""
        return p.BSSSettingsExt(
            max_fwd_times=self.max_fwd_times,
            time_to_live=self.time_to_live,
            ptt_release_send_location=self.ptt_release_send_location,
            ptt_release_send_id_info=self.ptt_release_send_id_info,
            ptt_release_send_bss_user_id=self.ptt_release_send_bss_user_id,
            should_share_location=self.should_share_location,
            send_pwr_voltage=self.send_pwr_voltage,
            packet_format=p.PacketFormat[self.packet_format],
            allow_position_check=self.allow_position_check,
            aprs_ssid=self.aprs_ssid,
            location_share_interval=self.location_share_interval,
            bss_user_id_lower=self._bss_user_id_split.get_lower(
                self.bss_user_id
            ),
            ptt_release_id_info=self.ptt_release_id_info,
            beacon_message=self.beacon_message,
            aprs_symbol=self.aprs_symbol,
            aprs_callsign=self.aprs_callsign,
            bss_user_id_upper=self._bss_user_id_split.get_upper(
                self.bss_user_id
            ),
        )


ChannelType = t.Literal["OFF", "A", "B"]


class Status(ImmutableBaseModel):
    """A data object representing the radio status"""
    _channel_split: t.ClassVar[IntSplit] = IntSplit(4, 4)
    is_power_on: bool
    is_in_tx: bool
    is_sq: bool
    is_in_rx: bool
    double_channel: ChannelType
    is_scan: bool
    is_radio: bool
    curr_ch_id: int
    is_gps_locked: bool
    is_hfp_connected: bool
    is_aoc_connected: bool
    rssi: float
    curr_region: int

    @classmethod
    def from_protocol(cls, s: p.Status | p.StatusExt) -> Status:
        """@private (Protocol helper)"""
        if not isinstance(s, p.StatusExt):
            raise ValueError(
                "Radio replied with old Status message version. Upgrade your firmware!"
            )

        return Status(
            is_power_on=s.is_power_on,
            is_in_tx=s.is_in_tx,
            is_sq=s.is_sq,
            is_in_rx=s.is_in_rx,
            double_channel=s.double_channel.name,
            is_scan=s.is_scan,
            is_radio=s.is_radio,
            curr_ch_id=cls._channel_split.from_parts(
                s.curr_channel_id_upper, s.curr_ch_id_lower
            ),
            is_gps_locked=s.is_gps_locked,
            is_hfp_connected=s.is_hfp_connected,
            is_aoc_connected=s.is_aoc_connected,
            rssi=s.rssi,
            curr_region=s.curr_region
        )

    def to_protocol(self) -> p.StatusExt:
        """@private (Protocol helper)"""
        return p.StatusExt(
            is_power_on=self.is_power_on,
            is_in_tx=self.is_in_tx,
            is_sq=self.is_sq,
            is_in_rx=self.is_in_rx,
            double_channel=p.ChannelType[self.double_channel],
            is_scan=self.is_scan,
            is_radio=self.is_radio,
            curr_ch_id_lower=self._channel_split.get_lower(self.curr_ch_id),
            is_gps_locked=self.is_gps_locked,
            is_hfp_connected=self.is_hfp_connected,
            is_aoc_connected=self.is_aoc_connected,
            rssi=self.rssi,
            curr_region=self.curr_region,
            curr_channel_id_upper=self._channel_split.get_upper(
                self.curr_ch_id)
        )
