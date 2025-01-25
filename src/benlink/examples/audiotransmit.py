import typing as t
import sys
import av
import av.container
import av.logging
import asyncio
import pyaudio
from io import BytesIO
from benlink.audio import AudioConnection

av.logging.set_level(av.logging.DEBUG)

BUFFER_SIZE = 512


def print_usage():
    print("Usage: python -m benlink.examples.audiotransmit <UUID> [channel]")
    print("  <UUID>    : A valid UUID string.")
    print("  [channel] : An integer or 'auto' (default: 'auto').")


async def main(uuid: str, channel: int | t.Literal["auto"]):
    try:
        p = pyaudio.PyAudio()

        mic_stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=32000,
            input=True,
            frames_per_buffer=BUFFER_SIZE,
        )

        radio_audio = AudioConnection.create_rfcomm(uuid, channel)

        await radio_audio.connect()

        while True:
            chunk = mic_stream.read(BUFFER_SIZE, exception_on_overflow=False)

            print(f"Chunk size: {len(chunk)}")

            chunk_av = av.open(
                BytesIO(chunk),
                format="s16le",
                options={
                    "ar": "32000",
                },
            )

            assert isinstance(chunk_av, av.container.InputContainer)

            output_io = BytesIO()

            output_av = av.open(
                output_io,
                'w',  format="sbc"
            )

            output_stream = output_av.add_stream(
                'sbc', rate=32000, options={
                    'b': "128k",
                    'msbc': 'false',
                    'sbc_delay': '0.013',
                },
                layout="mono",
            )

            assert isinstance(output_stream, av.AudioStream)

            for f in chunk_av.decode(audio=0):
                packet = output_stream.encode(f)
                if packet:
                    output_av.mux(packet)

            packet = output_stream.encode(None)
            if packet:
                output_av.mux(packet)

            chunk_av.close()
            output_av.close()

            print(f"encoded size: {len(output_io.getvalue())}")

            await radio_audio.send_audio_data(output_io.getvalue())

    except Exception as e:
        print(e)
    finally:
        pass


if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print_usage()
        sys.exit(1)

    uuid = sys.argv[1]

    if len(sys.argv) == 3:
        channel_str = sys.argv[2]
    else:
        channel_str = "auto"

    if channel_str == "auto":
        channel = channel_str
    else:
        try:
            channel = int(channel_str)
        except ValueError:
            print("Invalid channel number.")
            print_usage()
            sys.exit(1)

    asyncio.run(main(uuid, channel))
