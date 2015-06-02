# Parallella example

This example shows how to use the barectf
[Parallella platform](../../../platforms/parallella).


## Building

Make sure you have the latest version of barectf installed.

Build this example:

    make


## Running

Make sure the consumer application is running first
(see the Parallella platform's
[`README.md`](../../../platforms/parallella/README.md) file):

    e-reset
    ./consumer /path/to/the/ctf/directory/here

Load and start this example on all 16 cores:

    e-loader -s parallella.srec 0 0 4 4

When you've had enough, kill the consumer with `SIGINT` (Ctrl+C) and
reset the platform with `e-reset` to stop the Epiphany cores.

The complete CTF trace is written to the `ctf` directory.
