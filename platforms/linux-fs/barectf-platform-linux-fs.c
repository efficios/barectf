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

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <barectf.h>
#include <time.h>

#include "barectf-platform-linux-fs.h"

struct barectf_platform_linux_fs_ctx {
	struct barectf_default_ctx ctx;
	FILE *fh;
	int simulate_full_backend;
	unsigned int full_backend_rand_lt;
	unsigned int full_backend_rand_max;
};

static uint64_t get_clock(void* data)
{
	struct timespec ts;

	clock_gettime(CLOCK_MONOTONIC, &ts);

	return ts.tv_sec * 1000000000ULL + ts.tv_nsec;
}

static void write_packet(struct barectf_platform_linux_fs_ctx *ctx)
{
	size_t nmemb = fwrite(barectf_packet_buf(&ctx->ctx),
		barectf_packet_buf_size(&ctx->ctx), 1, ctx->fh);
	assert(nmemb == 1);
}

static int is_backend_full(void *data)
{
	struct barectf_platform_linux_fs_ctx *ctx = data;

	if (ctx->simulate_full_backend) {
		if (rand() % ctx->full_backend_rand_max <
				ctx->full_backend_rand_lt) {
			return 1;
		}
	}

	return 0;
}

static void open_packet(void *data)
{
	struct barectf_platform_linux_fs_ctx *ctx = data;

	barectf_default_open_packet(&ctx->ctx);
}

static void close_packet(void *data)
{
	struct barectf_platform_linux_fs_ctx *ctx = data;

	/* close packet now */
	barectf_default_close_packet(&ctx->ctx);

	/* write packet to file */
	write_packet(ctx);
}

struct barectf_platform_linux_fs_ctx *barectf_platform_linux_fs_init(
	unsigned int buf_size, const char *trace_dir, int simulate_full_backend,
	unsigned int full_backend_rand_lt, unsigned int full_backend_rand_max)
{
	char stream_path[256];
	uint8_t *buf;
	struct barectf_platform_linux_fs_ctx *ctx;
	struct barectf_platform_callbacks cbs = {
		.default_clock_get_value = get_clock,
		.is_backend_full = is_backend_full,
		.open_packet = open_packet,
		.close_packet = close_packet,
	};

	ctx = malloc(sizeof(*ctx));

	if (!ctx) {
		return NULL;
	}

	buf = malloc(buf_size);

	if (!buf) {
		free(ctx);
		return NULL;
	}

	memset(buf, 0, buf_size);

	sprintf(stream_path, "%s/stream", trace_dir);
	ctx->fh = fopen(stream_path, "wb");

	if (!ctx->fh) {
		free(ctx);
		free(buf);
		return NULL;
	}

	ctx->simulate_full_backend = simulate_full_backend;
	ctx->full_backend_rand_lt = full_backend_rand_lt;
	ctx->full_backend_rand_max = full_backend_rand_max;

	barectf_init(&ctx->ctx, buf, buf_size, cbs, ctx);
	open_packet(ctx);

	return ctx;
}

void barectf_platform_linux_fs_fini(struct barectf_platform_linux_fs_ctx *ctx)
{
	if (barectf_packet_is_open(&ctx->ctx) &&
			!barectf_packet_is_empty(&ctx->ctx)) {
		close_packet(ctx);
	}

	fclose(ctx->fh);
	free(barectf_packet_buf(&ctx->ctx));
	free(ctx);
}

struct barectf_default_ctx *barectf_platform_linux_fs_get_barectf_ctx(
	struct barectf_platform_linux_fs_ctx *ctx)
{
	return &ctx->ctx;
}
