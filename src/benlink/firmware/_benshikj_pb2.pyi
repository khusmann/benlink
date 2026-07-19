from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CheckFirmwareUpdateRequest(_message.Message):
    __slots__ = ("product_id", "firmware_version", "beta", "user_id", "invite_code")
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    FIRMWARE_VERSION_FIELD_NUMBER: _ClassVar[int]
    BETA_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    INVITE_CODE_FIELD_NUMBER: _ClassVar[int]
    product_id: int
    firmware_version: int
    beta: bool
    user_id: int
    invite_code: int
    def __init__(self, product_id: _Optional[int] = ..., firmware_version: _Optional[int] = ..., beta: _Optional[bool] = ..., user_id: _Optional[int] = ..., invite_code: _Optional[int] = ...) -> None: ...

class FirmwareInfo(_message.Message):
    __slots__ = ("version", "url", "md5", "release_notes", "release_date")
    VERSION_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    MD5_FIELD_NUMBER: _ClassVar[int]
    RELEASE_NOTES_FIELD_NUMBER: _ClassVar[int]
    RELEASE_DATE_FIELD_NUMBER: _ClassVar[int]
    version: int
    url: str
    md5: str
    release_notes: str
    release_date: str
    def __init__(self, version: _Optional[int] = ..., url: _Optional[str] = ..., md5: _Optional[str] = ..., release_notes: _Optional[str] = ..., release_date: _Optional[str] = ...) -> None: ...

class CheckFirmwareUpdateResult(_message.Message):
    __slots__ = ("firmware", "base")
    FIRMWARE_FIELD_NUMBER: _ClassVar[int]
    BASE_FIELD_NUMBER: _ClassVar[int]
    firmware: FirmwareInfo
    base: FirmwareInfo
    def __init__(self, firmware: _Optional[_Union[FirmwareInfo, _Mapping]] = ..., base: _Optional[_Union[FirmwareInfo, _Mapping]] = ...) -> None: ...
