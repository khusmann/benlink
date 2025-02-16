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

### pairing radios

For some reason, pairing the radio in my blueman-applet doesn't always work. I
think it's because it doesn't always connect to my system's notification system
so that I can confirm that I trust the device. I've found it's better to pair
through `bluetoothctl`. It sometimes takes a few tries to have ot prompt me to
confirm the pairing (by typing "yes" in the console)

Quick access `bluetoothctl` commands:

```
# To pair
scan on
pair <mac>

# Other useful ones
trust <mac>
list-attributes
attribute-info
acquire-notify
select-attribute
```
