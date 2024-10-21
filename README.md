# Capturing all the things

To download the btsnoop bug report:

```
adb bugreport <report_name>
```

This will create a `<report_name>.zip`. Put it into the `input` directory, along
with a `<report_name>.txt` file describing the things you pressed.

Then run:

```
make
```

And it will populate the logs directory with parsed logs from the input folder.

## Notes

tshark 3.x has a [bug](https://gitlab.com/wireshark/wireshark/-/issues/2234) and
cannot read from stdin (you get "Error: illegal seek"). You need 4.x or later.

It looks like the phone sends `7e:02:00:00:00:00:00:00:00:00:7e` for each sound
clip received from the radio.

## Receiving APRS messages

When there was three parts of a message, their prefixes were:

1.`ff:01:00:37:00:02:00:09:02:00`

2.`ff:01:00:37:00:02:00:09:02:01`

3.`ff:01:00:11:00:02:00:09:02:82` (len = 0x0f)

When there was two parts of a message, their prefixes were:

1. `ff:01:00:37:00:02:00:09:02:00` (len = 0x35)

2. `ff:01:00:15:00:02:00:09:02:81` (len = 0x13)

Ok, so we're probably look at this for APRS:

`ff:01:00:<LEN>:00:02:00:09:02:<0000XYYY>` where LEN is the message length + 2,
and X is set if it's the finall part, and YYY is the message number.

So perhaps the first part: `ff:01:00:<LEN>:00:02:00:09` is the header, and the
body is `02:<0000XYYY>:<MESSAGE>`

## Message Type List

```
0x00    UNKNOWN,
0x01    GET_DEV_ID,
0x02    SET_REG_TIMES,
0x03    GET_REG_TIMES,
0x04    GET_DEV_INFO,
0x05    READ_STATUS,
0x06    REGISTER_NOTIFICATION,
0x07    CANCEL_NOTIFICATION,
0x08    GET_NOTIFICATION,
0x09    EVENT_NOTIFICATION,
0x0a    READ_SETTINGS,
0x0b    WRITE_SETTINGS,
0x0c    STORE_SETTINGS,
0x0d    READ_RF_CH,
0x0e    WRITE_RF_CH,
0x0f    GET_IN_SCAN,
0x10    SET_IN_SCAN,
0x11    SET_REMOTE_DEVICE_ADDR,
0x12    GET_TRUSTED_DEVICE,
0x13    DEL_TRUSTED_DEVICE,
0x14    GET_HT_STATUS,
0x15    SET_HT_ON_OFF,
0x16    GET_VOLUME,
0x17    SET_VOLUME,
0x18    RADIO_GET_STATUS,
0x19    RADIO_SET_MODE,
0x1a    RADIO_SEEK_UP,
0x1b    RADIO_SEEK_DOWN,
0x1c    RADIO_SET_FREQ,
0x1d    READ_ADVANCED_SETTINGS,
0x1e    WRITE_ADVANCED_SETTINGS,
0x1f    HT_SEND_DATA,
0x20    SET_POSITION,
0x21    READ_BSS_SETTINGS,
0x22    WRITE_BSS_SETTINGS,
0x23    FREQ_MODE_SET_PAR,
0x24    FREQ_MODE_GET_STATUS,
0x25    READ_RDA1846S_AGC,
0x26    WRITE_RDA1846S_AGC,
0x27    READ_FREQ_RANGE,
0x28    WRITE_DE_EMPH_COEFFS,
0x29    STOP_RINGING,
0x2a    SET_TX_TIME_LIMIT,
0x2b    SET_IS_DIGITAL_SIGNAL,
0x2c    SET_HL,
0x2d    SET_DID,
0x2e    SET_IBA,
0x2f    GET_IBA,
0x30    SET_TRUSTED_DEVICE_NAME,
0x31    SET_VOC,
0x32    GET_VOC,
0x33    SET_PHONE_STATUS,
0x34    READ_RF_STATUS,
0x35    PLAY_TONE,
0x36    GET_DID,
0x37    GET_PF,
0x38    SET_PF,
0x39    RX_DATA,
0x3a    WRITE_REGION_CH,
0x3b    WRITE_REGION_NAME,
0x3c    SET_REGION,
0x3d    SET_PP_ID,
0x3e    GET_PP_ID,
0x3f    READ_ADVANCED_SETTINGS2,
0x40    WRITE_ADVANCED_SETTINGS2,
0x41    UNLOCK,
0x42    DO_PROG_FUNC,
0x43    SET_MSG,
0x44    GET_MSG,
0x45    BLE_CONN_PARAM,
0x46    SET_TIME,
0x47    SET_APRS_PATH,
0x48    GET_APRS_PATH,
0x49    READ_REGION_NAME,
0x4a    SET_DEV_ID,
0x4b    GET_PF_ACTIONS;
```
