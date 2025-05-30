# benlink

[![Project Status: Active – The project has reached a stable, usable state and is being actively developed.](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)
![PyPI - Version](https://img.shields.io/pypi/v/benlink)
![PyPI - Downloads](https://img.shields.io/pypi/dm/benlink)

<img src="https://raw.githubusercontent.com/khusmann/benlink/main/assets/logo-white.png" align="right" height="140" />

<!-- BEGIN CONTENT -->

`benlink` is a cross-platform Python library for communicating with and
controlling Benshi radios (e.g. Vero VR-N76, RadioOddity GA-5WB, BTech UV-Pro)
over BLE and Bluetooth Classic (RFCOMM).

In addition to providing a high-level async Python interface for controlling
Benshi radios, the larger goal of this project is to document their BLE / RFCOMM
protocol. An understanding of the protocol used by these radios will empower
Benshi radio owners and the wider open source community to:

1. Control their radios without relying on proprietary apps or software.

2. Extend the functionality of their radios through custom software and
   integrations.

3. Preserve the usability of their radios, even when the official "HT" app is no
   longer supported or updated.

It is a work in progress and is nowhere close to feature complete.
[Pull requests](https://github.com/khusmann/benlink) are welcome!

### Software / Hardware Support

benlink uses [bleak](https://github.com/hbldh/bleak) for BLE communication,
making it compatible with Windows, macOS, and Linux. RFCOMM support is via
python's built-in `socket` module, and also works on Windows, macOS, and Linux.
(Although automatic service discovery for RFCOMM
[isn't supported yet](https://github.com/khusmann/benlink/issues/9)).

The following radios should work with this library:

- BTech UV-Pro
- RadioOddity GA-5WB
- Vero VR-N76 (untested)
- Vero VR-N7500 (untested)
- BTech GMRS-Pro (untested)

If you know of other radios that use the same Benshi BLE / RFCOMM protocol,
please [open an issue](https://github.com/khusmann/benlink/issues) to let me
know!

## Installation

To install the latest stable version of benlink from PyPI:

```bash
pip install benlink
```

If you're wanting to contribute to the project, clone the repository and install
it in "editable" mode with

```bash
pip install -e .
```

## Quick Start

First, make sure your radio is paired with your computer, and get its device
UUID (e.g. `XX:XX:XX:XX:XX:XX`).

The following will connect to the radio and print its device info:

```python
import asyncio
from benlink.controller import RadioController

async def main():
    async with RadioController.new_ble("XX:XX:XX:XX:XX:XX") as radio:
        print(radio.device_info)

asyncio.run(main())
```

## Next Steps

To see what else you can do with this library, check out the examples in the
[benlink.controller](https://benlink.kylehusmann.com/benlink/controller.html)
module documentation.

## Other Projects

Benlink has already begun to inspire other projects! Here are some that I know
of so far:

- [HTCommander](https://github.com/Ylianst/HTCommander)

If you've found benlink's documentation of the Benshi protocol helpful, or use
benlink in your own project, please let me know so I can add it to this list.

## Known issues

Audio sending / receiving is a awkward because it relies on pyav for decoding /
encoding. In the long run, I hope to make
[Python bindings for libsbc](https://github.com/khusmann/benlink/issues/11).

## Roadmap

Things to do:

- [ ] Improve audio sending / receiving with bindings to libsbc
      ([issue](https://github.com/khusmann/benlink/issues/11))
- [ ] Make a higher-level interface for sending / receiving TNC data (auto
      retry, queue message fragments)
      ([issue](https://github.com/khusmann/benlink/issues/1))
- [ ] Figure out firmware flashing process / protocol (this is key for long-term
      independence from the HT app)
      ([issue](https://github.com/khusmann/benlink/issues/10))
- [ ] Implement more commands and settings
- [ ] Find more radios that use this protocol and test them with this library

## Acknowledgements

[@spohtl](https://github.com/spohtl) for help figuring out audio transmit /
receive

[@na7q](https://github.com/na7q) for early testing and feedback

## Disclaimer

This project is an independent grassroots effort, and is **not** affiliated with
or endorsed by Benshi, Vero, RadioOddity, BTech, or any other company.

Use this library at your own risk. I am **not** responsible for any damage
caused to your radio or any other equipment while using this library.
