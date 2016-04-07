#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <time.h>

#ifdef WITH_LTTNG_UST
#include "tp.h"
#else /* #ifdef WITH_LTTNG_UST */
#include <barectf-platform-linux-fs.h>

/*
 * Include generated barectf header file: this contains the prefix and
 * default stream name to be used by the tracepoint() macro.
 */
#include "barectf.h"

/* define how the context is to be found by tracepoint() calls */
#define BARECTF_TRACEPOINT_CTX	(global_barectf_ctx)

/* then include this: */
#include <barectf-tracepoint.h>

/* global barectf context (default stream) */
static struct barectf_default_ctx *global_barectf_ctx;

/* global barectf platform context */
struct barectf_platform_linux_fs_ctx *global_barectf_platform_ctx;
#endif /* #ifdef WITH_LTTNG_UST */

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
		tracepoint(barectf_tp, simple_uint32, i * 1500);
		tracepoint(barectf_tp, simple_int16, -i * 2);
		tracepoint(barectf_tp, simple_float, (float) i / 1.23);

		if (argc > 0) {
			str = argv[i % argc];
		} else {
			str = "hello there!";
		}

		tracepoint(barectf_tp, simple_string, str);
		tracepoint(barectf_tp, simple_enum, RUNNING);
		tracepoint(barectf_tp, a_few_fields, -1, 301, -3.14159,
			   str, NEW);
		tracepoint(barectf_tp, bit_packed_integers, 1, -1, 3,
			   -2, 2, 7, 23, -55, 232);
		tracepoint(barectf_tp, simple_enum, TERMINATED);
	}
}

#ifdef WITH_LTTNG_UST
#define init_barectf()
#define fini_barectf()
#else /* #ifdef WITH_LTTNG_UST */
static void init_barectf(void)
{
	/* initialize platform */
	global_barectf_platform_ctx =
		barectf_platform_linux_fs_init(512, "ctf", 1, 2, 7);

	if (!global_barectf_platform_ctx) {
		fprintf(stderr, "Error: could not initialize platform\n");
		exit(1);
	}

	global_barectf_ctx = barectf_platform_linux_fs_get_barectf_ctx(
		global_barectf_platform_ctx);
}

static void fini_barectf(void)
{
	/* finalize platform */
	barectf_platform_linux_fs_fini(global_barectf_platform_ctx);
}
#endif /* #ifdef WITH_LTTNG_UST */

int main(int argc, char *argv[])
{
	init_barectf();
	trace_stuff(argc, argv);
	fini_barectf();

	return 0;
}
