#include <stdio.h>
#include <unistd.h>
#include <sys/socket.h>
#include <bluetooth/bluetooth.h>
#include <bluetooth/rfcomm.h>
#include <errno.h>

#include "libsbc/sbc.h"
#include "libsbc/bits.h"
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
        char* sbcData = &(data[2]); // strip the first two bytes
        int sbcDataLen = *pLen - 3; // account for the two header bytes - "0x7e 0x00", and the trailing byte "0x7e"
        if (data[*pLen-1] & 0xff != 0x7e) {
            sbcDataLen++;
        }

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

        while(nBytesToRead >= SBC_HEADER_SIZE) {
            int nOffset = sbcDataLen - nBytesToRead;

            int nStartPos = nOffset;
            while ((sbcData[nStartPos] & 0xff) != 0x9c) {
                nStartPos++;
                if (nStartPos >= sbcDataLen) {
                    break;
                }
            }
            if (nStartPos >= sbcDataLen) {
                break;
            }

            // A "hack" to make the decoder happy: if there were too many bytes in the previous frame, copy them to this frame
            if (nStartPos != nOffset) {
                int nDiff = nStartPos - nOffset;
                for (int diff = nDiff-1; diff >= 0; diff--) {
                    for (int i = nOffset; i < nOffset + 11; i++) {
                        char temp = sbcData[i + diff];
                        sbcData[i + diff] = sbcData[i + diff + 1];
                        sbcData[i + diff + 1] = temp;
                    }
                }
            }

            if (nBytesToRead <= SBC_HEADER_SIZE) {
                break;   
            }

            err = sbc_decode(&g_sbcContext, sbcData + nOffset, nBytesToRead, &sbcFrame, pcmData + 0, nChannels, pcmData + 1, 2);
            if (err) {
                printf("sbc_decode failed\n");
                break;
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