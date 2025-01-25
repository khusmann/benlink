import typing as t
import sys
import asyncio
import pyaudio
from io import BytesIO
from benlink.audio import AudioConnection

import av
from av.container import Container, InputContainer

# Uncomment for troubleshooting pyav errors
# import av.logging
# av.logging.set_level(av.logging.DEBUG)


def print_usage():
    print("Usage: python -m benlink.examples.audiotransmit <UUID> [channel]")
    print("  <UUID>    : A valid UUID string.")
    print("  [channel] : An integer or 'auto' (default: 'auto').")


def print_sbc_info(rate: int, sbc_delay: float, bitpool: int) -> None:
    if sbc_delay < 0.003:
        subbands = 4
    else:
        subbands = 8

    # sbc_delay = ((blocks + 10) * subbands - 2) / sample_rate
    blocks = int((rate*sbc_delay+2)/subbands - 10)

    print(f"Rate: {rate} Hz")
    print(f"Bitpool: {bitpool}")
    print(f"Subbands: {subbands}")
    print(f"Blocks: {blocks}")


def sbc_encode(pcm: bytes, rate: int = 32000, sbc_delay: float = 0.0064375, bitpool: int = 18) -> bytes:
    if sbc_delay < 0.001 or sbc_delay > 0.013:
        raise ValueError("SBC delay must be between 0.001 and 0.013 seconds")

    input_pcm: Container | None = None
    output_sbc: Container | None = None

    buffer = BytesIO()

    try:
        input_pcm = av.open(
            BytesIO(pcm),
            format="s16le",
            options={
                "ar": str(rate),
            },
        )

        assert isinstance(input_pcm, InputContainer)

        output_sbc = av.open(buffer, 'w',  format="sbc")

        output_stream = output_sbc.add_stream(  # type: ignore
            'sbc', rate=rate, options={
                'global_quality': str(bitpool*118),
                'sbc_delay': str(sbc_delay),
                'msbc': 'false',
                # 'b' can set the bitrate (e.g. 'b': '128k')
                # but instead of using it, we use 'global_quality'
                # to set the bitpool directly
            },
            layout="mono",
        )

        assert isinstance(output_stream, av.AudioStream)

        for frame in input_pcm.decode(audio=0):
            packet = output_stream.encode(frame)
            if packet:
                output_sbc.mux(packet)

        # Flush remaining frames
        packet = output_stream.encode(None)

        if packet:
            output_sbc.mux(packet)

    except:
        raise
    finally:
        if input_pcm is not None:
            input_pcm.close()
        if output_sbc is not None:
            output_sbc.close()

    return buffer.getvalue()


SAMPLE_RATE = 32000
FRAME_BUFFER_SIZE = 512


async def main(uuid: str, channel: int | t.Literal["auto"]):
    p = pyaudio.PyAudio()

    mic_stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SAMPLE_RATE,
        input=True
    )

    radio_audio = AudioConnection.create_rfcomm(uuid, channel)

    await radio_audio.connect()

    async def transmit_task(radio_audio: AudioConnection):
        while True:
            pcm = await asyncio.to_thread(
                mic_stream.read,
                FRAME_BUFFER_SIZE, exception_on_overflow=False
            )

            sbc = sbc_encode(pcm, rate=SAMPLE_RATE)

            await radio_audio.send_audio_data(sbc)

    transmit_task_handle = asyncio.create_task(transmit_task(radio_audio))

    print("Transmitting audio. Press Enter to quit...")

    await asyncio.to_thread(input)

    transmit_task_handle.cancel()

    try:
        await transmit_task_handle
    except asyncio.CancelledError:
        pass

    mic_stream.stop_stream()
    mic_stream.close()
    p.terminate()

    await radio_audio.send_audio_end()
    # Wait for the audio end message to be fully sent
    # (no ack, unfortunately)
    await asyncio.sleep(1)

    await radio_audio.disconnect()


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
