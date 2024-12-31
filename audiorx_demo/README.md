This is a crude proof-of-concept of receiving audio from the radio, with the purpose of documenting the audio protocol.

The audio is encoded as SBC frames, with the following settings:
```
blockSize = 16
subBands = 8
sampleRate = 32000
bitPool = 18
mode = SBC_MODE_MONO;
```
Despite these settings being seemingly constant, they are sent every time as part of the SBC header. The audio message format seems to be:
```
    7e         00      9c 71 12 a2   [301 - 307 bytes]      7e
start byte | command | SBC header | ---- SBC data ---- | stop byte
```
The app then replies to each received frame with:
```
7e 02 00 00 00 00 00 00 00 00 7e
```
When the radio sends the following frame, it's indicating that it finished sending audio frames:
```
7e 01 00 00 00 00 00 00 00 00 7e
```

To run the demo, build it with `make` and then run it with `./audiorx_demo XX:XX:XX:XX:XX:XX`
It will connect to the RFCOMM audio channel (hardcoded to 2, change it in the code if your radio uses a different channel) and start receiving audio frames. Once it receives the end of audio frame from the radio, it will write the audio to file `1.wav`. The next time it receives audio, it will write to file `2.wav`, and so on.

The SBC decoding seems to fail every once in a while. I'm still unsure why that is, but the result can be heard as skipped audio and artifacts in the decoded audio.
