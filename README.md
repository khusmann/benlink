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
