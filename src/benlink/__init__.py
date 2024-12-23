"""
# Overview

`benlink` is a Python library for communicating with and controlling
Benshi radios (e.g. Vero VR-N76, RadioOddity GA-5WB, BTech UV-Pro)
over BLE. 

In addition to providing a high-level async Python interface for
controlling Benshi radios, the larger goal of this project is to
document the BLE protocol used by these radios to empower users and
the community to:

1. Control their radios programmatically without relying on proprietary software.

2. Extend the functionality of their radios through custom software and integrations.

3. Preserve the usability of Benshi radios, even when the official "HT" app is no longer supported or updated.

It is a work in progress and is nowhere close to feature complete.
Pull requests are welcome!

# Installation

I plan to publish this package on PyPI once it is more complete. For now,
clone the repo and install it locally:

```bash
pip install .
```

(If you are developing the package, you can use `pip install -e .` to
install it in "editable" mode.)

# Quick start

The following will connect to a radio and print its device info:

```python
import asyncio
from benlink.client import RadioClient

async def main():
    async with RadioClient("XX:XX:XX:XX:XX:XX") as radio:
        print(radio.device_info)

asyncio.run(main())
```

# Handling events

The `RadioClient` class provides a `register_event_handler` method for
registering a callback function to handle events. The callback function
will be called with an `EventMessage` object whenever an event is
received from the radio.

Note that `register_event_handler` returns a function that can be called
to unregister the event handler.

```python
import asyncio
from benlink.client import RadioClient

async def main():
    async with RadioClient("XX:XX:XX:XX:XX:XX") as radio:
        def handle_event(event):
            print(f"Received event: {event}")

        unregister = radio.register_event_handler(handle_event)

        while True:
            print("Try changing the channel or updating a radio setting...")
            await asyncio.sleep(5)

asyncio.run(main())
```

# Interactive Usage

IPython's support of `asyncio` makes it a great tool for interactively
exploring the radio's capabilities. Here's an example session:

```python
from benlink.client import RadioClient

client = RadioClient("XX:XX:XX:XX:XX:XX")

client.connect()

client.device_info # Prints device info

await client.battery_voltage() # Prints battery voltage
"""

from . import client
from . import connection
from . import message

__all__ = ['client', 'connection', 'message']
