# barectf Parallella platform

This platform targets the [Parallella](http://parallella.org/) system.

This platform implements a ring buffer of packets in shared memory
between the Epiphany cores and the ARM host. A consumer application
on the host side is responsible for consuming the packets produced by
the Epiphany cores and for writing them to the file system.


## Requirements

  * Possessing a Parallella board
  * ESDK 2015.1
  * barectf prefix: `barectf_`
  * A single stream named `default`
  * One clock named `default`, returning `uint64_t`, and having a
    frequency of 1000000000 Hz

The `default` stream must have in its packet context two unsigned
integers with a size of at least 6 bits named `row` and `col` which will
hold the row and column numbers of the Epiphany core producing this
packet.

Example of packet context:

```yaml
class: struct
fields:
  timestamp_begin: clock_int
  timestamp_end: clock_int
  packet_size: uint32
  content_size: uint32
  events_discarded: uint32
  row: uint6
  col: uint6
```


## Files

  * `barectf-platform-parallella.h`: include this in your application
     running on Epiphany cores
  * `barectf-platform-parallella-config.h`: platform parameters
  * `barectf-platform-parallella-common.h`: definitions, data
    structures, and functions shared by the platform and the consumer
    application
  * `barectf-platform-parallella.c`: link your application with this
  * `consumer/consumer.c`: consumer application
  * `consumer/Makefile`: consumer application Makefile

## Using

### Platform API

See [`barectf-platform-parallella.h`](barectf-platform-parallella.h).


### Consumer application

#### Building

Do:

    make

in the [`consumer`](consumer) directory to build the consumer
application.

The optional `CROSS_COMPILE` environment variable specifies a
cross-compiling toolchain prefix.


#### Running

Accepted arguments are:

  * `-v`: enable verbose mode
  * Unnamed argument: output directory of stream files (default: `ctf`)

Example:

    ./consumer -v /path/to/my-trace

The output directory should also contain the `metadata` file produced
by the `barectf` command-line tool to form a complete CTF trace.

Start the consumer application _before_ starting the Epiphany cores
running the platform and your application. To make sure your Epiphany
application is not running, use the `e-reset` command.

Stop the consumer application by killing it with the `SIGINT` signal
(Ctrl+C). Stop the consumer application _before_ resetting the
platform with `e-reset` (once the Epiphany application is started).
When killed with `SIGINT`, the consumer application will finish writing
any incomplete packet, then quit.
