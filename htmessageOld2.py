from __future__ import annotations
from dataclasses import dataclass
import typing as t
import sys

from stream import ByteStream, BitStream


@dataclass(frozen=True)
class TypeId:
    group: int
    is_reply: bool
    command: int

    @classmethod
    def from_bytes(cls, data: bytes):
        stream = BitStream(data)
        command_group = stream.read_int(16)
        is_reply = stream.read_bool()
        command_id = stream.read_int(15)

        assert stream.eof()

        return cls(command_group, is_reply, command_id)


@dataclass(frozen=True)
class UnknownMessage:
    data: bytes
    tid: TypeId

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetDevId:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 1)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetDevIdReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 1)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetRegTimes:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 2)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetRegTimesReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 2)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetRegTimes:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 3)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetRegTimesReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 3)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetDevInfo:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 4)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetDevInfoReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 4)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadStatus:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 5)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadStatusReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 5)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class RegisterNotification:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 6)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class RegisterNotificationReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 6)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class CancelNotification:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 7)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class CancelNotificationReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 7)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetNotification:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 8)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetNotificationReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 8)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class EventNotification:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 9)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class EventNotificationReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 9)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadSettings:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 10)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadSettingsReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 10)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class WriteSettings:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 11)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class WriteSettingsReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 11)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class StoreSettings:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 12)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class StoreSettingsReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 12)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadRfCh:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 13)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadRfChReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 13)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class WriteRfCh:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 14)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class WriteRfChReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 14)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetInScan:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 15)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetInScanReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 15)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetInScan:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 16)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetInScanReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 16)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetRemoteDeviceAddr:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 17)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetRemoteDeviceAddrReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 17)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetTrustedDevice:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 18)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetTrustedDeviceReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 18)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class DelTrustedDevice:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 19)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class DelTrustedDeviceReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 19)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetHtStatus:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 20)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetHtStatusReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 20)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetHtOnOff:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 21)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetHtOnOffReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 21)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetVolume:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 22)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetVolumeReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 22)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetVolume:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 23)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetVolumeReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 23)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class RadioGetStatus:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 24)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class RadioGetStatusReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 24)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class RadioSetMode:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 25)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class RadioSetModeReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 25)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class RadioSeekUp:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 26)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class RadioSeekUpReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 26)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class RadioSeekDown:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 27)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class RadioSeekDownReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 27)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class RadioSetFreq:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 28)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class RadioSetFreqReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 28)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadAdvancedSettings:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 29)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadAdvancedSettingsReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 29)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class WriteAdvancedSettings:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 30)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class WriteAdvancedSettingsReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 30)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class HtSendData:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 31)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class HtSendDataReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 31)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetPosition:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 32)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetPositionReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 32)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadBssSettings:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 33)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadBssSettingsReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 33)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class WriteBssSettings:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 34)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class WriteBssSettingsReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 34)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class FreqModeSetPar:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 35)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class FreqModeSetParReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 35)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class FreqModeGetStatus:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 36)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class FreqModeGetStatusReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 36)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadRda1846sAgc:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 37)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadRda1846sAgcReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 37)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class WriteRda1846sAgc:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 38)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class WriteRda1846sAgcReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 38)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadFreqRange:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 39)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadFreqRangeReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 39)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class WriteDeEmphCoeffs:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 40)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class WriteDeEmphCoeffsReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 40)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class StopRinging:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 41)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class StopRingingReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 41)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetTxTimeLimit:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 42)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetTxTimeLimitReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 42)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetIsDigitalSignal:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 43)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetIsDigitalSignalReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 43)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetHl:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 44)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetHlReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 44)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetDid:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 45)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetDidReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 45)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetIba:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 46)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetIbaReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 46)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetIba:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 47)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetIbaReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 47)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetTrustedDeviceName:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 48)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetTrustedDeviceNameReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 48)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetVoc:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 49)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetVocReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 49)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetVoc:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 50)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetVocReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 50)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetPhoneStatus:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 51)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetPhoneStatusReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 51)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadRfStatus:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 52)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadRfStatusReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 52)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class PlayTone:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 53)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class PlayToneReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 53)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetDid:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 54)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetDidReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 54)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetPf:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 55)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetPfReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 55)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetPf:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 56)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetPfReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 56)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class RxData:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 57)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class RxDataReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 57)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class WriteRegionCh:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 58)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class WriteRegionChReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 58)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class WriteRegionName:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 59)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class WriteRegionNameReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 59)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetRegion:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 60)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetRegionReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 60)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetPpId:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 61)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetPpIdReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 61)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetPpId:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 62)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetPpIdReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 62)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadAdvancedSettings2:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 63)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadAdvancedSettings2Reply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 63)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class WriteAdvancedSettings2:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 64)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class WriteAdvancedSettings2Reply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 64)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class Unlock:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 65)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class UnlockReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 65)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class DoProgFunc:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 66)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class DoProgFuncReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 66)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetMsg:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 67)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetMsgReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 67)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetMsg:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 68)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetMsgReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 68)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class BleConnParam:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 69)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class BleConnParamReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 69)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetTime:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 70)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetTimeReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 70)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetAprsPath:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 71)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetAprsPathReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 71)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetAprsPath:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 72)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetAprsPathReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 72)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadRegionName:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 73)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class ReadRegionNameReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 73)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetDevId:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 74)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class SetDevIdReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 74)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetPfActions:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, False, 75)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


@dataclass(frozen=True)
class GetPfActionsReply:
    data: bytes
    tid: t.ClassVar[t.Final[TypeId]] = TypeId(2, True, 75)

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.data


Message = t.Union[
    GetDevId,               GetDevIdReply,                # 1
    SetRegTimes,            SetRegTimesReply,             # 2
    GetRegTimes,            GetRegTimesReply,             # 3
    GetDevInfo,             GetDevInfoReply,              # 4
    ReadStatus,             ReadStatusReply,              # 5
    RegisterNotification,   RegisterNotificationReply,    # 6
    CancelNotification,     CancelNotificationReply,      # 7
    GetNotification,        GetNotificationReply,         # 8
    EventNotification,      EventNotificationReply,       # 9
    ReadSettings,           ReadSettingsReply,            # 10
    WriteSettings,          WriteSettingsReply,           # 11
    StoreSettings,          StoreSettingsReply,           # 12
    ReadRfCh,               ReadRfChReply,                # 13
    WriteRfCh,              WriteRfChReply,               # 14
    GetInScan,              GetInScanReply,               # 15
    SetInScan,              SetInScanReply,               # 16
    SetRemoteDeviceAddr,    SetRemoteDeviceAddrReply,     # 17
    GetTrustedDevice,       GetTrustedDeviceReply,        # 18
    DelTrustedDevice,       DelTrustedDeviceReply,        # 19
    GetHtStatus,            GetHtStatusReply,             # 20
    SetHtOnOff,             SetHtOnOffReply,              # 21
    GetVolume,              GetVolumeReply,               # 22
    SetVolume,              SetVolumeReply,               # 23
    RadioGetStatus,         RadioGetStatusReply,          # 24
    RadioSetMode,           RadioSetModeReply,            # 25
    RadioSeekUp,            RadioSeekUpReply,             # 26
    RadioSeekDown,          RadioSeekDownReply,           # 27
    RadioSetFreq,           RadioSetFreqReply,            # 28
    ReadAdvancedSettings,   ReadAdvancedSettingsReply,    # 29
    WriteAdvancedSettings,  WriteAdvancedSettingsReply,   # 30
    HtSendData,             HtSendDataReply,              # 31
    SetPosition,            SetPositionReply,             # 32
    ReadBssSettings,        ReadBssSettingsReply,         # 33
    WriteBssSettings,       WriteBssSettingsReply,        # 34
    FreqModeSetPar,         FreqModeSetParReply,          # 35
    FreqModeGetStatus,      FreqModeGetStatusReply,       # 36
    ReadRda1846sAgc,        ReadRda1846sAgcReply,         # 37
    WriteRda1846sAgc,       WriteRda1846sAgcReply,        # 38
    ReadFreqRange,          ReadFreqRangeReply,           # 39
    WriteDeEmphCoeffs,      WriteDeEmphCoeffsReply,       # 40
    StopRinging,            StopRingingReply,             # 41
    SetTxTimeLimit,         SetTxTimeLimitReply,          # 42
    SetIsDigitalSignal,     SetIsDigitalSignalReply,      # 43
    SetHl,                  SetHlReply,                   # 44
    SetDid,                 SetDidReply,                  # 45
    SetIba,                 SetIbaReply,                  # 46
    GetIba,                 GetIbaReply,                  # 47
    SetTrustedDeviceName,   SetTrustedDeviceNameReply,    # 48
    SetVoc,                 SetVocReply,                  # 49
    GetVoc,                 GetVocReply,                  # 50
    SetPhoneStatus,         SetPhoneStatusReply,          # 51
    ReadRfStatus,           ReadRfStatusReply,            # 52
    PlayTone,               PlayToneReply,                # 53
    GetDid,                 GetDidReply,                  # 54
    GetPf,                  GetPfReply,                   # 55
    SetPf,                  SetPfReply,                   # 56
    RxData,                 RxDataReply,                  # 57
    WriteRegionCh,          WriteRegionChReply,           # 58
    WriteRegionName,        WriteRegionNameReply,         # 59
    SetRegion,              SetRegionReply,               # 60
    SetPpId,                SetPpIdReply,                 # 61
    GetPpId,                GetPpIdReply,                 # 62
    ReadAdvancedSettings2,  ReadAdvancedSettings2Reply,   # 63
    WriteAdvancedSettings2, WriteAdvancedSettings2Reply,  # 64
    Unlock,                 UnlockReply,                  # 65
    DoProgFunc,             DoProgFuncReply,              # 66
    SetMsg,                 SetMsgReply,                  # 67
    GetMsg,                 GetMsgReply,                  # 68
    BleConnParam,           BleConnParamReply,            # 69
    SetTime,                SetTimeReply,                 # 70
    SetAprsPath,            SetAprsPathReply,             # 71
    GetAprsPath,            GetAprsPathReply,             # 72
    ReadRegionName,         ReadRegionNameReply,          # 73
    SetDevId,               SetDevIdReply,                # 74
    GetPfActions,           GetPfActionsReply,            # 75
]

MESSAGE_TYPES: t.Tuple[Message] = t.get_args(Message)

MESSAGE_TYPE_MAP: t.Mapping[TypeId, Message] = {
    TypeId(i.tid.group, i.tid.is_reply, i.tid.command): i for i in MESSAGE_TYPES
}


def read_next_message(stream: ByteStream) -> Message | UnknownMessage | None:
    if stream.eof():
        return None

    if stream.peek() != b"\xff":
        print(
            f"Expected frame_start = 0xff, got {stream.peek()}. Skipping to next frame.",
            file=sys.stderr
        )
        while stream.peek() != b"\xff":
            stream.read()
            if stream.eof():
                return None

    if stream.available() < 8:
        return None

    frame_header = stream.peek(8)

    reserved_1 = frame_header[1:3]
    frame_len = frame_header[3]
    tid_raw = frame_header[4:]

    assert reserved_1 == b"\x01\x00"  # Haven't seen this change yet...

    if stream.available() < frame_len + 8:
        return None

    stream.read(8)

    frame_body = stream.read(frame_len)

    tid = TypeId.from_bytes(tid_raw)
    message_class = MESSAGE_TYPE_MAP.get(tid)

    if message_class is not None:
        return message_class.from_bytes(frame_body)
    else:
        return UnknownMessage(frame_body, tid)
