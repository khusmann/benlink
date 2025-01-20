from ..audio import AudioConnection, AudioEvent, AudioData
from ..link import RfcommAudioLink
import pyaudio
import av
import ctypes
import sys
import asyncio


def print_usage():
    print("Usage: python -m benlink.examples.audiomonitor <UUID> [channel]")
    print("  <UUID>    : A valid UUID string.")
    print("  [channel] : An integer or 'auto' (default: 'auto').")


async def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print_usage()
        sys.exit(1)

    uuid = sys.argv[1]

    if len(sys.argv) == 3:
        channel_str = sys.argv[2]
    else:
        channel_str = "auto"

    if channel_str == "auto":
        raise NotImplementedError(
            "Auto channel selection not implemented yet.")
    else:
        try:
            channel = int(channel_str)
        except ValueError:
            print("Invalid channel number.")
            print_usage()
            sys.exit(1)

    pa: pyaudio.PyAudio | None = None
    audio_out: pyaudio.Stream | None = None
    radio_audio: AudioConnection | None = None

    try:
        pa = pyaudio.PyAudio()

        audio_out = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=32000,
            output=True,
        )

        codec = av.CodecContext.create("sbc", "r")

        assert isinstance(codec, av.AudioCodecContext)

        def on_audio_message(msg: AudioEvent):
            assert audio_out

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
                            audio_out.write(pcm_data)

                case _:
                    print(f"Received message: {msg}")

        radio_audio = AudioConnection(
            RfcommAudioLink(uuid, channel)
        )

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

        if audio_out:
            audio_out.stop_stream()
            audio_out.close()

        if pa:
            pa.terminate()


if __name__ == "__main__":
    asyncio.run(main())
