"""
# Overview

`benlink` is a Python library for communicating with and controlling Benshi
radios (e.g. Vero VR-N76, RadioOddity GA-5WB, BTech UV-Pro) over BLE.

In addition to providing a high-level async Python interface for controlling
Benshi radios, the larger goal of this project is to document their BLE
protocol. An understanding of the BLE protocol used by these radios will empower
Benshi radio owners and the wider open source community to:

1. Control their radios without relying on proprietary apps or software.

2. Extend the functionality of their radios through custom software and
   integrations.

3. Preserve the usability of their radios, even when the official "HT" app is no
   longer supported or updated.

It is a work in progress and is nowhere close to feature complete.
[Pull requests](https://github.com/khusmann/benlink) are welcome!

## Radio Support

The following radios should work with this library:

- BTech UV-Pro
- RadioOddity GA-5WB
- Vero VR-N76 (untested)
- Vero VR-N7500 (untested)
- BTech GMRS-Pro (untested)

If you know of other radios that use the same Benshi BLE protocol, please
[open an issue](https://github.com/khusmann/benlink/issues) to let me know!

# Installation

I plan to publish this package on PyPI once it is more complete. For now, clone
the repo and install it locally:

```bash
pip install .
```

(If you are developing the package, you can use `pip install -e .` to install it
in "editable" mode.)

# Quick Start

First, make sure your radio is paired with your computer, and get its device
UUID (e.g. `XX:XX:XX:XX:XX:XX`).

The following will connect to the radio and print its device info:

```python
import asyncio
from benlink.client import RadioClient

async def main():
    async with RadioClient("XX:XX:XX:XX:XX:XX") as radio:
        print(radio.device_info)

asyncio.run(main())
```

## Next Steps

To see what else you can do with this library, check out the examples in the
`benlink.client` module documentation.

# Roadmap

Things to do, in no particular order:

- [ ] Implement more commands and settings
- [ ] Make a higher-level interface for sending / receiving TNC data (right now
      you have to break it into fragments)
- [ ] Find more radios that use this protocol and test them with this library
- [ ] Figure out firmware flashing process / protocol (this is key for long-term
      independence from the HT app)

# Disclaimer

This project is an independent grassroots effort, and is **not** affiliated with
or endorsed by Benshi, Vero, RadioOddity, BTech, or any other company.

Use this library at your own risk. I am **not** responsible for any damage
caused to your radio or any other equipment while using this library.
"""

from . import client
from . import connection
from . import message

__all__ = ['client', 'connection', 'message']