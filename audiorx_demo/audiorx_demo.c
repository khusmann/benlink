#include <stdio.h>
#include <unistd.h>
#include <sys/socket.h>
#include <bluetooth/bluetooth.h>
#include <bluetooth/rfcomm.h>
#include <errno.h>

#include "sbc/wave.h"
#include "sbc/oi_codec_sbc.h"

#define RFCOMM_AUDIO_CHANNEL 2
#define SOCKET_BUFFER_SIZE 1024
#define PCM_BUFFER_SIZE 2*SOCKET_BUFFER_SIZE*sizeof(int16_t)
#define ACK_MESSAGE_LEN 11

const int g_cReplyMsg[ACK_MESSAGE_LEN] = {0x7e, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x7e};

FILE* g_audioFileFd;
int g_audioFileCnt;
OI_CODEC_SBC_DECODER_CONTEXT g_sbcContext;
static uint32_t g_sbcContextData[CODEC_DATA_WORDS(2, SBC_CODEC_FAST_FILTER_BUFFERS)];
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
        char* sbcData = &(data[2]); // strip the first two bytes
        int sbcDataLen = *pLen - 3; // account for the two header bytes - "0x7e 0x00", and the trailing byte "0x7e"
        if (data[*pLen-1] & 0xff != 0x7e) {
            sbcDataLen++;
        }

        int16_t pcmData[PCM_BUFFER_SIZE];
        int nBytesToRead = sbcDataLen;

        if (g_audioFileFd == NULL) {
            OI_CODEC_SBC_DecoderReset(&g_sbcContext, (uint32_t*)g_sbcContextData, sizeof(g_sbcContextData), SBC_MAX_CHANNELS, 1, 0);
        }

        while(nBytesToRead >= 4) {
            int nOffset = sbcDataLen - nBytesToRead;

            if (nBytesToRead <= 4) {
                break;   
            }

            int pcmBytes = PCM_BUFFER_SIZE;
            int err = OI_CODEC_SBC_DecodeFrame(&g_sbcContext, (const OI_BYTE**)&sbcData,
                           (uint32_t*)&nBytesToRead, pcmData,
                           (uint32_t*)&pcmBytes);


            if (err) {
                printf("sbc_decode failed\n");
                break;
            }

            if (g_audioFileFd == NULL) {
                openAudioFile();
                wave_write_header(g_audioFileFd, 16, sizeof(int16_t), 32000, 1, -1);
            }

            int nSamples = pcmBytes/sizeof(int16_t);
            wave_write_pcm(g_audioFileFd, sizeof(int16_t), pcmData, 1, 0, nSamples);
            g_samplesCnt += nSamples;
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

    while(1) {
        int nBytes = read(socketFd, socketBuffer, SOCKET_BUFFER_SIZE);
        if (nBytes) {
            if (socketBuffer[0] == 0x7e) {
                nBytes = (int)recv(socketFd, socketBuffer, nBytes, 6);
                decodeAudioFrame(socketBuffer, &nBytes);
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
