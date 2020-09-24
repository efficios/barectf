#ifndef _BARECTF_TRACEPOINT_LINUX_FS
#define _BARECTF_TRACEPOINT_LINUX_FS

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
static struct barectf_platform_linux_fs_ctx *global_barectf_platform_ctx;

/* init function for this version */
static void init_tracing(void)
{
	/* initialize platform */
	global_barectf_platform_ctx =
		barectf_platform_linux_fs_init(512, "ctf-linux-fs/stream",
			1, 2, 7);

	if (!global_barectf_platform_ctx) {
		fprintf(stderr, "Error: could not initialize platform\n");
		exit(1);
	}

	global_barectf_ctx = barectf_platform_linux_fs_get_barectf_ctx(
		global_barectf_platform_ctx);
}

/* finalization function for this version */
static void fini_tracing(void)
{
	/* finalize platform */
	barectf_platform_linux_fs_fini(global_barectf_platform_ctx);
}

#endif /* _BARECTF_TRACEPOINT_LINUX_FS */
