from ..audio import AudioConnection, AudioEvent, AudioData
import typing as t
import pyaudio
import av
import ctypes
import sys
import asyncio
from contextlib import contextmanager


def print_usage():
    print("Usage: python -m benlink.examples.audiomonitor <UUID> [channel]")
    print("  <UUID>    : A valid UUID string.")
    print("  [channel] : An integer or 'auto' (default: 'auto').")


@contextmanager
def open_output_stream(rate: int):
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=rate,
        output=True,
    )
    try:
        yield stream
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


SAMPLE_RATE = 32000


async def main(uuid: str, channel: int | t.Literal["auto"]):

    with open_output_stream(SAMPLE_RATE) as output_stream:
        async with AudioConnection.new_rfcomm(uuid, channel) as radio_audio:
            codec = av.CodecContext.create("sbc", "r")

            assert isinstance(codec, av.AudioCodecContext)

            def on_audio_message(msg: AudioEvent):
                assert output_stream

                match msg:
                    case AudioData(sbc_data=sbc_data):
                        packets = codec.parse(sbc_data)

                        for p in packets:
                            frames = codec.decode(p)
                            for f in frames:
                                pcm_data = ctypes.string_at(
                                    f.planes[0].buffer_ptr, f.planes[0].buffer_size
                                )
                                output_stream.write(pcm_data)
                    case _:
                        print(f"Received message: {msg}")

            radio_audio.add_event_handler(on_audio_message)

            print("Monitoring radio audio. Press Enter to quit...")

            await asyncio.to_thread(input)

            print("Exiting...")

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
