from ..audio import AudioConnection, AudioEvent, AudioData
import typing as t
import pyaudio
import av
import ctypes
import sys
import asyncio


def print_usage():
    print("Usage: python -m benlink.examples.audiomonitor <UUID> [channel]")
    print("  <UUID>    : A valid UUID string.")
    print("  [channel] : An integer or 'auto' (default: 'auto').")


async def main(uuid: str, channel: int | t.Literal["auto"]):
    pa: pyaudio.PyAudio | None = None
    stream: pyaudio.Stream | None = None
    radio_audio: AudioConnection | None = None

    try:
        pa = pyaudio.PyAudio()

        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=32000,
            output=True,
        )

        codec = av.CodecContext.create("sbc", "r")

        assert isinstance(codec, av.AudioCodecContext)

        def on_audio_message(msg: AudioEvent):
            assert stream

            match msg:
                case AudioData(sbc_data=sbc_data):
                    packets = codec.parse(sbc_data)

                    print(f"Received {len(packets)} audio packets")

                    for p in packets:
                        frames = codec.decode(p)
                        for f in frames:
                            pcm_data = ctypes.string_at(
                                f.planes[0].buffer_ptr, f.planes[0].buffer_size
                            )
                            print(len(pcm_data))
                            stream.write(pcm_data)

                case _:
                    print(f"Received message: {msg}")

        radio_audio = AudioConnection.create_rfcomm(uuid, channel)

        radio_audio.register_event_handler(on_audio_message)

        await radio_audio.connect()

        print("Monitoring radio audio. Press Enter to quit...")

        await asyncio.to_thread(input)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("Cleaning up...")
        if radio_audio and radio_audio.is_connected():
            await radio_audio.disconnect()

        if stream:
            stream.stop_stream()
            stream.close()

        if pa:
            pa.terminate()


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
