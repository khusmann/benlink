import typing as t
import sys
import asyncio
import pyaudio
from io import BytesIO

import av
import av.container

from benlink.audio import AudioConnection

# Uncomment for troubleshooting pyav errors
# import av.logging
# av.logging.set_level(av.logging.DEBUG)


def print_usage():
    print("Usage: python -m benlink.examples.audiotransmit <UUID> [channel]")
    print("  <UUID>    : A valid UUID string.")
    print("  [channel] : An integer or 'auto' (default: 'auto').")


class SbcEncoder:
    _rate: int
    _bitpool: int
    _sbc_delay: float
    _output_buffer: BytesIO
    _output_container: av.container.OutputContainer
    _output_stream: av.AudioStream

    @property
    def subbands(self) -> int:
        # see https://github.com/FFmpeg/FFmpeg/blob/a0a89efd0778a8021c2d7077f82531d4f955f459/libavcodec/sbcenc.c#L233
        if self._sbc_delay < 0.003:
            return 4
        else:
            return 8

    @property
    def blocks(self) -> int:
        # see https://github.com/FFmpeg/FFmpeg/blob/a0a89efd0778a8021c2d7077f82531d4f955f459/libavcodec/sbcenc.c#L247
        # sbc_delay = ((blocks + 10) * subbands - 2) / sample_rate
        return int((self._rate*self._sbc_delay+2)/self.subbands - 10)

    @property
    def rate(self) -> int:
        return self._rate

    @property
    def frame_size(self) -> int:
        return self.blocks * self.subbands

    def __repr__(self) -> str:
        return f"SbcEncoder(rate={self._rate}, bitpool={self._bitpool}, subbands={self.subbands}, blocks={self.blocks})"

    def __init__(self, rate: int = 32000, bitpool: int = 16, sbc_delay: float = 0.0064375):
        self._rate = rate
        self._bitpool = bitpool
        self._sbc_delay = sbc_delay
        self._output_buffer = BytesIO()
        self._output_container = av.open(
            self._output_buffer, 'w', format="sbc"
        )

        output_stream = self._output_container.add_stream(  # type: ignore
            'sbc', rate=rate, options={
                # 'b' can set the bitrate (e.g. 'b': '128k')
                # but instead of using it, we use 'global_quality'
                # to set the bitpool directly
                # https://github.com/FFmpeg/FFmpeg/blob/a0a89efd0778a8021c2d7077f82531d4f955f459/libavcodec/sbcenc.c#L258
                'global_quality': str(bitpool*118),
                'sbc_delay': str(sbc_delay),
                'msbc': 'false',
            },
        )

        assert isinstance(output_stream, av.AudioStream)

        self._output_stream = output_stream

    def encode(self, input_pcm: bytes, input_rate: int, input_format: str = "s16le") -> bytes | None:
        input_container = av.open(
            BytesIO(input_pcm),
            format=input_format,
            options={
                "ar": str(input_rate),
            },
        )

        input_stream = input_container.streams.audio[0]

        assert isinstance(input_container, av.container.InputContainer)

        for packet in input_container.demux(input_stream):
            for frame in packet.decode():
                assert isinstance(frame, av.AudioFrame)

                # Ignore time base info
                frame.pts = None  # type: ignore

                encoded_packet = self._output_stream.encode(frame)

                if encoded_packet:
                    self._output_container.mux(encoded_packet)

        n_bytes_available = self._output_buffer.tell()
        self._output_buffer.seek(0)

        if n_bytes_available == 0:
            return None

        return self._output_buffer.getvalue()[:n_bytes_available]

    def close(self) -> None:
        self._output_container.close()


SAMPLE_RATE = 32000


async def main(uuid: str, channel: int | t.Literal["auto"]):
    p = pyaudio.PyAudio()

    mic_stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SAMPLE_RATE,
        input=True
    )

    encoder = SbcEncoder(rate=SAMPLE_RATE)

    radio_audio = AudioConnection.create_rfcomm(uuid, channel)

    await radio_audio.connect()

    async def transmit_task():
        while True:
            pcm = await asyncio.to_thread(
                mic_stream.read,
                encoder.frame_size*2, exception_on_overflow=False
            )

            sbc = encoder.encode(pcm, input_rate=SAMPLE_RATE)

            if sbc:
                await radio_audio.send_audio_data(sbc)

    transmit_task_handle = asyncio.create_task(transmit_task())

    print("Transmitting audio. Press Enter to quit...")

    await asyncio.to_thread(input)

    transmit_task_handle.cancel()

    try:
        await transmit_task_handle
    except asyncio.CancelledError:
        pass

    await radio_audio.send_audio_end()
    # Wait for the audio end message to be fully sent
    # (no ack, unfortunately)
    await asyncio.sleep(1)

    await radio_audio.disconnect()

    encoder.close()

    mic_stream.stop_stream()
    mic_stream.close()
    p.terminate()


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
