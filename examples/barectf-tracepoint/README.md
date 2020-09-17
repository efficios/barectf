# Example using `barectf-tracepoint.h`

This example is based on the [linux-fs-simple example](../linux-fs-simple)
example, but it uses the `tracepoint()` macro defined in
[`barectf-tracepoint.h`](../../../extra/barectf-tracepoint.h) instead of
calling the generated tracing functions directly.

This example also shows the compatibility with
[LTTng-UST](http://lttng.org/) that this `barectf-tracepoint.h` allows.

This example also includes a QEMU ARM target to simulate barectf used by
a true bare-metal application.

All the targets of this example use the same application source:
[`barectf-tracepoint.c`](barectf-tracepoint.c).


## barectf tracing

### linux-fs platform

#### Building

Do:

    make -f Makefile.barectf-linux-fs


#### Running

Run this example:

    ./barectf-tracepoint-barectf-linux-fs

The complete CTF trace is written to the `ctf-linux-fs` directory.

You may run the example with any arguments; they will be recorded,
as string fields in the events of the binary stream, e.g.:

    ./barectf-tracepoint-barectf-linux-fs this argument and this one will be recorded


### QEMU ARM platform

#### Building

To build this example, you need an ARM cross-compiler toolchain
(`gcc-arm-none-eabi`, `binutils-arm-none-eabi`, and
`libnewlib-arm-none-eabi` Ubuntu packages), then do:

    make -f Makefile.barectf-qemu-arm-uart


#### Running

To run this example, you need `qemu-system-arm` (`qemu-system-arm`
Ubuntu package).

Run this example:

    make -f Makefile.barectf-qemu-arm-uart sim

The complete CTF trace is written to the `ctf-qemu-arm-uart` directory.


#### What happens when running?

When you run this example, here's what happens:

  1. The `barectf-tracepoint-barectf-qemu-arm-uart.sh` Bash script
     is executed.
  2. This Bash script executes `qemu-system-arm` with the appropriate
     options to simulate the bare-metal application on an ARM system.
     The simulated board is a Versatile platform baseboard from ARM. The
     simulated CPU is an ARM926EJ-S. This is a 2001 ARM9 core
     implementing the ARMv5TE architecture. QEMU is set to execute the
     `barectf-tracepoint-barectf-qemu-arm-uart` ELF file (previously
     built), and to connect the board's first UART with QEMU's standard
     input/output streams, and the board's second UART to the
     `ctf-qemu-arm-uart/stream` file (output only). The Bash script
     reads each line printed by QEMU, and kills the QEMU process when
     it reads the ending line written by the bare-metal application.
  3. QEMU starts. Eventually, the bare-metal application's
     `main()` function is called.
  4. `main()` calls `init_tracing()`, which for this example, calls
     `barectf_platform_qemu_arm_uart_init()`. This is a custom barectf
     platform created specifically for this example. The platform
     initializes a barectf context to get its clock source from a timer
     on the simulated board, and to flush its packets by writing the
     bytes to the second UART (which is connected to the
     `ctf-qemu-arm-uart/stream` file by QEMU). The platform uses a
     global buffer of 4 kiB to hold the current packet.
  5. `main()` calls `trace_stuff()` which contains the `tracepoint()`
     macro invocations. Events are recorded to the current packet by
     the barectf machinery. When this packet is full, it is flushed
     by the platform to the second UART.
  6. `main()` calls `fini_tracing()`, which calls
     `barectf_platform_qemu_arm_uart_fini()`, which prints the
     ending line that `barectf-tracepoint-barectf-qemu-arm-uart.sh`
     is waiting for to kill QEMU.


## LTTng-UST tracing

### Building

Make sure [LTTng-UST](http://lttng.org/) is installed.

Do:

    make -f Makefile.lttng-ust


### Running

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
