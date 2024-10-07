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
