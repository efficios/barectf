#ifndef _BARECTF_PLATFORM_LINUX_FS_H
#define _BARECTF_PLATFORM_LINUX_FS_H

/*
 * barectf linux-fs platform
 *
 * Copyright (c) 2015 EfficiOS Inc. and Linux Foundation
 * Copyright (c) 2015 Philippe Proulx <pproulx@efficios.com>
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
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#include <stdint.h>
#include <barectf.h>

struct barectf_platform_linux_fs_ctx;

/**
 * Initializes the platform.
 *
 * @param buf_size			Packet size (bytes)
 * @param trace_dir			Trace directory
 * @param simulate_full_backend		1 to simulate a full back-end sometimes
 * @param full_backend_rand_lt		Back-end will be "full" when a random
 *					value is lower than this parameter
 *					if \p simulate_full_backend is 1
 * @param full_backend_rand_max		Maximum random value for full back-end
 *					simulation when \p simulate_full_backend
 *					is 1
 * @returns				Platform context
 */
struct barectf_platform_linux_fs_ctx *barectf_platform_linux_fs_init(
	unsigned int buf_size, const char *trace_dir, int simulate_full_backend,
	unsigned int full_backend_rand_max, unsigned int full_backend_rand_lt);

/**
 * Finalizes the platform.
 *
 * @param ctx	Platform context
 */
void barectf_platform_linux_fs_fini(struct barectf_platform_linux_fs_ctx *ctx);

/**
 * Returns the barectf stream-specific context of a given platform context.
 *
 * This context is what barectf tracing functions need.
 *
 * @param ctx	Platform context
 * @returns	barectf stream-specific context
 */
struct barectf_default_ctx *barectf_platform_linux_fs_get_barectf_ctx(
	struct barectf_platform_linux_fs_ctx *ctx);

#endif /* _BARECTF_PLATFORM_LINUX_FS_H */
