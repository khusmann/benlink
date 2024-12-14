import asyncio
from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
import sys

# Define the UUIDs
device_address = sys.argv[1]
# The UUID for the characteristic
indicate_uuid = "00001102-d102-11e1-9b23-00025b00a5a5"
# The UUID for writing
write_uuid = "00001101-d102-11e1-9b23-00025b00a5a5"

# Define a callback to handle indications


def indication_handler(characteristic: BleakGATTCharacteristic, data: bytearray) -> None:
    """
    Callback to handle indications received from the BLE device.

    :param characteristic: The characteristic from which the indication was received.
    :param data: The data received in the indication.
    """
    print(f"Received indication from {characteristic.uuid}: {data.hex()}")


async def run() -> None:
    """
    Runs the Bleak client to connect to a BLE device and listen for indications on a characteristic.
    """
    async with BleakClient(device_address) as client:
        print(f"Connected to {device_address}")

        # Start receiving indications for the characteristic UUID
        # This subscribes to indications (notifications) for the specific UUID
        await client.start_notify(  # type: ignore
            indicate_uuid, indication_handler
        )

        await client.write_gatt_char(write_uuid, b'\x00\x02\x00\x06\x01')

        print(
            f"Subscribed to indications for {indicate_uuid}. Waiting for data...")

        # Let it run for some time, you can adjust the duration as needed
        try:
            await asyncio.sleep(600)  # Listen for indications for 60 seconds
        except asyncio.CancelledError:
            pass
        finally:
            # Stop receiving indications after the time is over
            await client.stop_notify(indicate_uuid)
            print("Unsubscribed from indications.")

# Run the async function
asyncio.run(run())
