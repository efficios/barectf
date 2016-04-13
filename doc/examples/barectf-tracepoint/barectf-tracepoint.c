#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <time.h>

#if defined(WITH_LTTNG_UST)
#include "barectf-tracepoint-lttng-ust.h"
#elif defined(WITH_QEMU_ARM_UART)
#include "barectf-tracepoint-qemu-arm-uart.h"
#else
#include "barectf-tracepoint-linux-fs.h"
#endif

enum state_t {
	NEW,
	TERMINATED,
	READY,
	RUNNING,
	WAITING,
};

static void trace_stuff(int argc, char *argv[])
{
	int i;
	const char *str;

	/* record 40000 events */
	for (i = 0; i < 5000; ++i) {
		str = argv[i % argc];
		tracepoint(barectf_tp, simple_uint32, i * 1500);
		tracepoint(barectf_tp, simple_int16, -i * 2);
		tracepoint(barectf_tp, simple_float, (float) i / 1.23);
		tracepoint(barectf_tp, simple_string, str);
		tracepoint(barectf_tp, simple_enum, RUNNING);
		tracepoint(barectf_tp, a_few_fields, -1, 301, -3.14159,
			   str, NEW);
		tracepoint(barectf_tp, bit_packed_integers, 1, -1, 3,
			   -2, 2, 7, 23, -55, 232);
		tracepoint(barectf_tp, simple_enum, TERMINATED);
	}
}

#define NUM_STRINGS	5

static char *strings[] = {
	"orange",
	"mandarine",
	"lemon",
	"lime",
	"grapefruit",
};

int main(int argc, char *argv[])
{
	init_tracing();

	if (argc <= 1) {
		/* use static strings if there's nothing interesting in argv */
		argc = NUM_STRINGS;
		argv = strings;
	}

	trace_stuff(argc, argv);
	fini_tracing();

	return 0;
}
