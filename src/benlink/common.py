"""
Shared building blocks for benlink's data objects.

Kept separate from `benlink.command` so that modules which don't talk to a radio
(e.g. `benlink.firmware`) can use them without pulling in the Bluetooth stack.
"""

from __future__ import annotations
from pydantic import BaseModel, ConfigDict


class ImmutableBaseModel(BaseModel):
    """@private (A base class for immutable data objects)"""

    model_config = ConfigDict(frozen=True)
    """@private"""
