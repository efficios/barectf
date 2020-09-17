# linux-fs-simple example

This very simple example shows how to use the barectf
[linux-fs platform](../../../platforms/linux-fs).


## Building

Make sure you have the latest version of barectf installed.

Build this example:

    make


## Running

Run this example:

    ./linux-fs-simple

The complete CTF trace is written to the `ctf` directory.

You may run the example with any arguments; they will be recorded,
as string fields in the events of the binary stream, e.g.:

    ./linux-fs-simple this argument and this one will be recorded
