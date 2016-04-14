/*
 * The MIT License (MIT)
 *
 * Copyright (c) 2016 Philippe Proulx <pproulx@efficios.com>
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <time.h>
#include <barectf-platform-linux-fs.h>
#include <barectf.h>

enum state_t {
	NEW,
	TERMINATED,
	READY,
	RUNNING,
	WAITING,
};

static void trace_stuff(struct barectf_default_ctx *ctx, int argc,
			char *argv[])
{
	int i;
	const char *str;

	/* record 40000 events */
	for (i = 0; i < 5000; ++i) {
		barectf_trace_simple_uint32(ctx, i * 1500);
		barectf_trace_simple_int16(ctx, -i * 2);
		barectf_trace_simple_float(ctx, (float) i / 1.23);

		if (argc > 0) {
			str = argv[i % argc];
		} else {
			str = "hello there!";
		}

		barectf_trace_simple_string(ctx, str);
		barectf_trace_context_no_payload(ctx, i, "ctx");
		barectf_trace_simple_enum(ctx, RUNNING);
		barectf_trace_a_few_fields(ctx, -1, 301, -3.14159,
						     str, NEW);
		barectf_trace_bit_packed_integers(ctx, 1, -1, 3,
							    -2, 2, 7, 23,
							    -55, 232);
		barectf_trace_no_context_no_payload(ctx);
		barectf_trace_simple_enum(ctx, TERMINATED);
	}
}

int main(int argc, char *argv[])
{
	struct barectf_platform_linux_fs_ctx *platform_ctx;

	/* initialize platform */
	platform_ctx = barectf_platform_linux_fs_init(512, "ctf", 1, 2, 7);

	if (!platform_ctx) {
		fprintf(stderr, "Error: could not initialize platform\n");
		return 1;
	}

	/* trace stuff (will create/write packets as it runs) */
	trace_stuff(barectf_platform_linux_fs_get_barectf_ctx(platform_ctx),
		argc, argv);

	/* finalize platform */
	barectf_platform_linux_fs_fini(platform_ctx);

	return 0;
}
