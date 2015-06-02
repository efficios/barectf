# barectf linux-fs platform

This is a very simple barectf platform, written for demonstration purposes,
which writes the binary packets to a stream file on the file system.

This platform can also simulate a full back-end from time to time,
with a configurable ratio.


## Requirements

  * barectf prefix: `barectf_`
  * No custom trace packet header fields
  * A single stream named `default`, with no custom stream packet context
    fields
  * One clock named `default` returning `uint64_t`.


## Files

  * `barectf-platform-linux-fs.h`: include this in your application
  * `barectf-platform-linux-fs.c`: link your application with this


## Using

See [`barectf-platform-linux-fs.h`](barectf-platform-linux-fs.h).
