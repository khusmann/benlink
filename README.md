# benlink; Control your Benshi radio with Python

This is a Python library to control the Benshi radios like the Vero VR-N76,
RadioOddity GA5WB, BTech UV-Pro, and others.

In addition to providing a convenient Python interface to control these radios,
this project aims to serve as a reference implementation for the Bluetooth
classic / BLE protocol shared by all these radios.

It is very much a work in progress.

## Installation

When it is more stable I will publish to PyPI, but for now you can install the
dev version in editable mode by checking out the repo and running:

```bash
pip install -e .
```

## Usage

Use iPython to get an interactive shell and explore the API:

```bash
ipython
```

```python
from benlink.client import RadioClient

client = RadioClient("<device_uuid>")

await client.connect()

print(client.device_info)
print(client.channel_settings)

await client.set_channel_settings(channel_id=0, name = "helloworld")
print(client.channel_settings[0])

await client.set_channel_settings(channel_id=0, name = "foo", rx_freq = 146.460)
print(client.channel_settings[0])

await client.disconnect()
```

## Contributing

Coming soon...
