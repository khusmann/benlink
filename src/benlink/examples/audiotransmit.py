import typing as t
import sys
import asyncio
import pyaudio
from io import BytesIO
from benlink.audio import AudioConnection

import av
from av.container import Container, InputContainer, OutputContainer
import av.logging
av.logging.set_level(av.logging.DEBUG)

BUFFER_SIZE = 512


def print_usage():
    print("Usage: python -m benlink.examples.audiotransmit <UUID> [channel]")
    print("  <UUID>    : A valid UUID string.")
    print("  [channel] : An integer or 'auto' (default: 'auto').")


def sbc_encode(pcm: bytes) -> bytes:
    input_pcm: Container | None = None
    output_sbc: Container | None = None

    buffer = BytesIO()

    try:
        input_pcm = av.open(
            BytesIO(pcm),
            format="s16le",
            options={
                "ar": "32000",
            },
        )

        assert isinstance(input_pcm, InputContainer)

        output_sbc = av.open(buffer, 'w',  format="sbc")

        assert isinstance(input_pcm, OutputContainer)

        output_stream = output_sbc.add_stream(  # type: ignore
            'sbc', rate=32000, options={
                'b': "128k",
                'sbc_delay': '0.013',
                'msbc': 'false',
            },
            layout="mono",
        )

        assert isinstance(output_stream, av.AudioStream)

        for frame in input_pcm.decode(audio=0):
            packet = output_stream.encode(frame)
            if packet:
                output_sbc.mux(packet)

        packet = output_stream.encode(None)  # Flush remaining frames

        if packet:
            output_sbc.mux(packet)

        return buffer.getvalue()
    finally:
        if input_pcm:
            input_pcm.close()
        if output_sbc:
            output_sbc.close()


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
            pcm = mic_stream.read(BUFFER_SIZE, exception_on_overflow=False)

            sbc = sbc_encode(pcm)

            print(f"Chunk size: {len(pcm)} -> sbc size: {len(sbc)}")

            await radio_audio.send_audio_data(sbc)

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
