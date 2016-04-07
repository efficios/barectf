# Example using `barectf-tracepoint.h`

This example is based on the [linux-fs-simple example](../linux-fs-simple),
but it uses the `tracepoint()` macro defined in
[`barectf-tracepoint.h`](../../../extra/barectf-tracepoint.h) instead of
calling the generated tracing functions directly.

This example also shows the compatibility with
[LTTng-UST](http://lttng.org/) that this `barectf-tracepoint.h` allows.


## Building

To build both barectf and LTTng-UST targets, make sure both tools are
installed, and do:

    make

To build only the example using barectf:

    make -f Makefile.barectf

To build only the example using LTTng-UST:

    make -f Makefile.lttng-ust


## barectf tracing

Run this example:

    ./barectf-tracepoint-barectf

The complete CTF trace is written to the `ctf` directory.

You may run the example with any arguments; they will be recorded,
as string fields in the events of the binary stream, e.g.:

    ./barectf-tracepoint-barectf this argument and this one will be recorded


## LTTng-UST tracing

Create an LTTng tracing session:

    lttng create my-session

Enable the events of this example:

    lttng enable-event --userspace 'barectf_tp:*'

Start tracing:

    lttng start

Run this example:

    ./barectf-tracepoint-lttng-ust

You may run the example with any arguments; they will be recorded,
as string fields in the events of the binary stream, e.g.:

    ./barectf-tracepoint-lttng-ust this argument and this one will be recorded

Stop tracing and inspect the recorded events:

    lttng stop
    lttng view
