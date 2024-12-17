import typing as t
from pydantic import BaseModel, ConfigDict


class ImmutableBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class DCS(t.NamedTuple):
    n: int
