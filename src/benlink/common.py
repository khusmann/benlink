import typing as t
from pydantic import BaseModel, ConfigDict


class ImmutableBaseModel(BaseModel):
    """A base class for immutable Pydantic models"""
    model_config = ConfigDict(frozen=True)


class DCS(t.NamedTuple):
    """A type for setting Digital Coded Squelch (DCS) on channels"""

    n: int
    """The DCS Normal (N) code"""
