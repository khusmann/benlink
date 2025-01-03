#include <stdio.h>
#include <unistd.h>
#include <sys/socket.h>
#include <bluetooth/bluetooth.h>
#include <bluetooth/rfcomm.h>
#include <errno.h>

#include "libsbc/sbc.h"
#include "libsbc/wave.h"

#define RFCOMM_AUDIO_CHANNEL 2
#define SOCKET_BUFFER_SIZE 1024
#define ACK_MESSAGE_LEN 11

const int g_cReplyMsg[ACK_MESSAGE_LEN] = {0x7e, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x7e};

FILE* g_audioFileFd;
int g_audioFileCnt;
sbc_t g_sbcContext;
long g_samplesCnt;
long g_bytesCnt;

void openAudioFile()
{
    char sFilename[256];
    g_audioFileCnt++;
    sprintf(sFilename, "%d.wav", g_audioFileCnt);
    printf("Opening audio file %s\n", sFilename);
    g_audioFileFd = (FILE*)fopen(sFilename, "wb");
    if (g_audioFileFd == NULL) {
        printf("Error opening output file %s", sFilename);
    }
    g_samplesCnt = 0;
    g_bytesCnt = 0;
}

void decodeAudioFrame(char* data, int* pLen)
{
    if (data[1] == 0x00) {
        char* sbcData = &(data[2]);
        int sbcDataLen = *pLen - 3;
        
        bool bWriteHeader = false;

        int16_t pcmData[2*SOCKET_BUFFER_SIZE*sizeof(int16_t)];
        struct sbc_frame sbcFrame;

        if (g_audioFileFd == NULL) {
            sbc_reset(&g_sbcContext);
        }

        int err = sbc_probe(sbcData, &sbcFrame);
        if (err) {
            printf("sbc_probe failed\n");
            return;
        }

        int nChannels = 1 + (sbcFrame.mode != SBC_MODE_MONO);

        int nBytesToRead = sbcDataLen;

        while(nBytesToRead) {
            int nOffset = sbcDataLen - nBytesToRead;
            err = sbc_decode(&g_sbcContext, sbcData + nOffset, nBytesToRead, &sbcFrame, pcmData + 0, nChannels, pcmData + 1, 2);
            if (err) {
                printf("sbc_decode failed\n");
                return;
            }

            if (g_audioFileFd == NULL) {
                printf("Channels: %d, Sample rate: %d, Bitrate: %f, Bitpool: %d, Blocks: %d, Subbands: %d\n",
                    nChannels,
                    sbc_get_freq_hz(sbcFrame.freq),
                    sbc_get_frame_bitrate(&sbcFrame) * 1e-3,
                    sbcFrame.bitpool,
                    sbcFrame.nblocks,
                    sbcFrame.nsubbands);
                openAudioFile();
                wave_write_header(g_audioFileFd, 16, sizeof(int16_t), sbc_get_freq_hz(sbcFrame.freq), nChannels, -1);
            }

            int nSamples = sbcFrame.nblocks * sbcFrame.nsubbands;
            wave_write_pcm(g_audioFileFd, sizeof(int16_t), pcmData, nChannels, 0, nSamples);
            g_samplesCnt += nSamples;
            nBytesToRead -= sbc_get_frame_size(&sbcFrame);
        }
        g_bytesCnt += *pLen;

        for (int i = 0; i < ACK_MESSAGE_LEN; i++) {
            data[i] = g_cReplyMsg[i];
        }
        *pLen = ACK_MESSAGE_LEN;
    }
    else if (data[1] == 0x01 && g_audioFileFd != NULL) {
        printf("Closing audio file, wrote %ld samples from %ld received bytes\n", g_samplesCnt, g_bytesCnt);
        fclose(g_audioFileFd);
        g_audioFileFd = NULL;
    }
}


int unescapePacket(char* data, int len)
{
    int writeIdx = 0;
    for (int i = 0; i < len; i++) {
        if (data[i] == 0x7d) {
            i++;
            data[writeIdx++] = data[i] ^ 0x20;
        }
        else {
            data[writeIdx++] = data[i];
        }
    }
    return writeIdx;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        printf("usage: audiorx_demo XX:XX:XX:XX:XX:XX");
        return 0;
    }
    g_audioFileCnt = 0;
    g_audioFileFd = NULL;

    struct sockaddr_rc socketAddress = { 0 };
    socketAddress.rc_channel = (uint8_t) RFCOMM_AUDIO_CHANNEL;
    socketAddress.rc_family = AF_BLUETOOTH;
    str2ba(argv[1], &socketAddress.rc_bdaddr);

    char socketBuffer[SOCKET_BUFFER_SIZE] = { 0 };

    printf("Connecting to address %s ...\n", argv[1]);
    int socketFd = socket(AF_BLUETOOTH, SOCK_STREAM, BTPROTO_RFCOMM);
    int socketStatus = connect(socketFd, (struct sockaddr *)&socketAddress, sizeof(socketAddress));
    if (socketStatus == 0) {
        printf("Connected!\n");
    }
    else {
        printf("Connection error: %d\n", errno);
    }

    

    while(true) {
        int nBytes = (int)recv(socketFd, socketBuffer, SOCKET_BUFFER_SIZE, MSG_PEEK);
        if (nBytes) {
            // Look for the start of the packet
            if (socketBuffer[0] == 0x7e) {
                // Look for the end of the packet
                int i = 1;
                while (i < nBytes && socketBuffer[i] != 0x7e) {
                    i++;
                }

                if (i == nBytes) {
                    // No end of packet found yet, wait for more data
                    continue;
                }

                int packetBytes = read(socketFd, socketBuffer, i + 1);

                if (packetBytes != i + 1) {
                    printf("Error reading packet\n");
                    break;
                }

                packetBytes = unescapePacket(socketBuffer, packetBytes);
                decodeAudioFrame(socketBuffer, &packetBytes);
            }
        }
        else {
            break;
        }
    }

    printf("Closing socket\n");
    close(socketFd);
    return 0;
}
