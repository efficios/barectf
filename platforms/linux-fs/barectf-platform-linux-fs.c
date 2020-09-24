/*
 * Copyright (c) 2015 EfficiOS Inc. and Linux Foundation
 * Copyright (c) 2015-2020 Philippe Proulx <pproulx@efficios.com>
 *
 * Permission is hereby granted, free of charge, to any person obtaining
 * a copy of this software and associated documentation files (the
 * "Software"), to deal in the Software without restriction, including
 * without limitation the rights to use, copy, modify, merge, publish,
 * distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to
 * the following conditions:
 *
 * The above copyright notice and this permission notice shall be
 * included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
 * BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
 * ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <assert.h>
#include <time.h>

#include "barectf-platform-linux-fs.h"
#include "barectf.h"

#ifdef __cplusplus
# define _FROM_VOID_PTR(_type, _value)	static_cast<_type *>(_value)
#else
# define _FROM_VOID_PTR(_type, _value)	((_type *) (_value))
#endif

struct barectf_platform_linux_fs_ctx {
	struct barectf_default_ctx ctx;
	FILE *fh;
	int simulate_full_backend;
	unsigned int full_backend_rand_lt;
	unsigned int full_backend_rand_max;
};

static uint64_t get_clock(void * const data)
{
	struct timespec ts;

	clock_gettime(CLOCK_REALTIME, &ts);
	return ts.tv_sec * 1000000000ULL + ts.tv_nsec;
}

static void write_packet(const struct barectf_platform_linux_fs_ctx * const platform_ctx)
{
	const size_t nmemb = fwrite(barectf_packet_buf(&platform_ctx->ctx),
		barectf_packet_buf_size(&platform_ctx->ctx), 1, platform_ctx->fh);

	assert(nmemb == 1);
}

static int is_backend_full(void * const data)
{
	int is_backend_full = 0;
	const struct barectf_platform_linux_fs_ctx * const platform_ctx =
		_FROM_VOID_PTR(const struct barectf_platform_linux_fs_ctx, data);

	if (platform_ctx->simulate_full_backend) {
		if (rand() % platform_ctx->full_backend_rand_max <
				platform_ctx->full_backend_rand_lt) {
			is_backend_full = 1;
			goto end;
		}
	}

end:
	return is_backend_full;
}

static void open_packet(void * const data)
{
	struct barectf_platform_linux_fs_ctx * const platform_ctx =
		_FROM_VOID_PTR(struct barectf_platform_linux_fs_ctx, data);

	barectf_default_open_packet(&platform_ctx->ctx);
}

static void close_packet(void * const data)
{
	struct barectf_platform_linux_fs_ctx * const platform_ctx =
		_FROM_VOID_PTR(struct barectf_platform_linux_fs_ctx, data);

	/* Close packet now */
	barectf_default_close_packet(&platform_ctx->ctx);

	/* Write packet to file */
	write_packet(platform_ctx);
}

struct barectf_platform_linux_fs_ctx *barectf_platform_linux_fs_init(
	const unsigned int buf_size, const char * const data_stream_file_path,
	const int simulate_full_backend,
	const unsigned int full_backend_rand_lt,
	const unsigned int full_backend_rand_max)
{
	uint8_t *buf = NULL;
	struct barectf_platform_linux_fs_ctx *platform_ctx;
	struct barectf_platform_callbacks cbs;

	cbs.default_clock_get_value = get_clock;
	cbs.is_backend_full = is_backend_full;
	cbs.open_packet = open_packet;
	cbs.close_packet = close_packet;
	platform_ctx = _FROM_VOID_PTR(struct barectf_platform_linux_fs_ctx,
		malloc(sizeof(*platform_ctx)));

	if (!platform_ctx) {
		goto error;
	}

	buf = _FROM_VOID_PTR(uint8_t, malloc(buf_size));

	if (!buf) {
		goto error;
	}

	platform_ctx->fh = fopen(data_stream_file_path, "wb");

	if (!platform_ctx->fh) {
		goto error;
	}

	platform_ctx->simulate_full_backend = simulate_full_backend;
	platform_ctx->full_backend_rand_lt = full_backend_rand_lt;
	platform_ctx->full_backend_rand_max = full_backend_rand_max;
	barectf_init(&platform_ctx->ctx, buf, buf_size, cbs, platform_ctx);
	open_packet(platform_ctx);
	goto end;

error:
	free(platform_ctx);
	free(buf);

end:
	return platform_ctx;
}

void barectf_platform_linux_fs_fini(struct barectf_platform_linux_fs_ctx * const platform_ctx)
{
	if (barectf_packet_is_open(&platform_ctx->ctx) &&
			!barectf_packet_is_empty(&platform_ctx->ctx)) {
		close_packet(platform_ctx);
	}

	fclose(platform_ctx->fh);
	free(barectf_packet_buf(&platform_ctx->ctx));
	free(platform_ctx);
}

struct barectf_default_ctx *barectf_platform_linux_fs_get_barectf_ctx(
	struct barectf_platform_linux_fs_ctx * const platform_ctx)
{
	return &platform_ctx->ctx;
}
