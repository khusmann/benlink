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

### tshark version

tshark 3.x has a [bug](https://gitlab.com/wireshark/wireshark/-/issues/2234) and
cannot read from stdin (you get "Error: illegal seek"). You need 4.x or later.

It looks like the phone sends `7e:02:00:00:00:00:00:00:00:00:7e` for each sound
clip received from the radio.

### max message length

It looks like the max message body length is 53 bytes (based on the HT_SEND_DATA
code). The message header is 8 bytes, plus a possible checksum of 1 byte. So I
wonder if the max message frame length is 62 bytes?
