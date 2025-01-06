#include <stdio.h>
#include <unistd.h>
#include <sys/socket.h>
#include <bluetooth/bluetooth.h>
#include <bluetooth/rfcomm.h>
#include <errno.h>

#include "libsbc/sbc.h"
#include "libsbc/wave.h"

#define RFCOMM_COMMAND_CHANNEL 1
#define RFCOMM_AUDIO_CHANNEL 2
#define SOCKET_BUFFER_SIZE 1024
#define INIT_MESSAGE_LEN 11
#define MSG_ESCAPE_MARGIN 32

const char g_cInitMsg[INIT_MESSAGE_LEN] = {0x7e, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x7e};

int escapePacket(char* sbcData, char* msgData, int len)
{
    int writeIdx = 0;
    for (int i = 0; i < len; i++) {
        if (sbcData[i] == 0x7d || sbcData[i] == 0x7e) {
            msgData[writeIdx++] = 0x7d;
            msgData[writeIdx++] = sbcData[i] ^ 32;
        }
        else {
            msgData[writeIdx++] = sbcData[i];
        }
    }
    return writeIdx;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        printf("usage: audiotx_demo XX:XX:XX:XX:XX:XX file.wav    (the wav file must be 32kHz 16 bit mono)\n");
        return 0;
    }

    struct sockaddr_rc audioSocketAddress = { 0 };
    audioSocketAddress.rc_channel = (uint8_t) RFCOMM_AUDIO_CHANNEL;
    audioSocketAddress.rc_family = AF_BLUETOOTH;
    str2ba(argv[1], &audioSocketAddress.rc_bdaddr);

    printf("Connecting to audio ch, address %s ...\n", argv[1]);
    int audioSocketFd = socket(AF_BLUETOOTH, SOCK_STREAM, BTPROTO_RFCOMM);
    int audioSocketStatus = connect(audioSocketFd, (struct sockaddr *)&audioSocketAddress, sizeof(audioSocketAddress));
    if (audioSocketStatus == 0) {
        printf("Connected to audio ch %d!\n", RFCOMM_AUDIO_CHANNEL);
    }
    else {
        printf("Connection error: %d\n", errno);
    }

    FILE* audioFileFd = fopen(argv[2],"rb");
    if (NULL == audioFileFd) {
        printf("Could not open audio file %s\n", argv[2]);
        return 0;
    }

    int srate_hz, nch, nsamples;
    int pcm_sbits, pcm_sbytes;

    if (wave_read_header(audioFileFd, &pcm_sbits, &pcm_sbytes, &srate_hz, &nch, &nsamples) < 0) {
        printf("Audio file invalid\n");
        return 0;
    }

    struct sbc_frame frame = (struct sbc_frame){
        .mode = SBC_MODE_MONO,
        .nsubbands = 8, .nblocks = 16,
        .bam = SBC_BAM_SNR,
        .bitpool = 18
    };

    uint8_t sbcData[2*SBC_MAX_SAMPLES*sizeof(int16_t)];
    uint8_t msgData[8*SBC_MAX_SAMPLES*sizeof(int16_t) + 3 + MSG_ESCAPE_MARGIN];
    int16_t pcm[2*SBC_MAX_SAMPLES];
    sbc_t sbc;

    int npcm = frame.nblocks * frame.nsubbands;

    sbc_reset(&sbc);

    // Start the transmission (the app sends this but it seems to work without it as well)
    write(audioSocketFd, g_cInitMsg, INIT_MESSAGE_LEN);

    printf("Reading file...\n");

    // Write all data
    while (1) {

        int msgSize = 0;
        bool bBreak = false;

        for (int nFrame = 0; nFrame < 4; nFrame++) {
            int pcmRead = wave_read_pcm(audioFileFd, pcm_sbytes, nch, npcm, pcm);
            if (pcmRead < npcm) {
                bBreak = true;
                break;
            }
            // Encode SBC
            sbc_encode(&sbc, pcm + 0, nch, pcm + 1, 2, &frame, sbcData, sizeof(sbcData));

            unsigned int size = sbc_get_frame_size(&frame);

            // Escape the packet. Bytes 0x7d and 0x7e need to be escaped.
            // Offset msgData by 2 to make space for the header
            int s = escapePacket(sbcData, &(msgData[2 + msgSize]), size);
            msgSize += s;
        }
        if (bBreak) {
            break;
        }

        // Add header
        msgData[0] = 0x7e;
        msgData[1] = 0x00;
        
        // Add stop byte
        msgData[2 + msgSize] = 0x7e;

        // Adjust the msg size of the added bytes
        msgSize += 3;

        // Write to socket
        write(audioSocketFd, msgData, msgSize);
        usleep(500);
    }

    printf("Done!\n");

    // End the transmission (this doesn't require any delay for me)
    write(audioSocketFd, g_cInitMsg, INIT_MESSAGE_LEN);
    
    // Wait 10s before closing the socket 
    usleep(10000000);

    fclose(audioFileFd);

    printf("Closing socket\n");
    close(audioSocketFd);
    return 0;
}
