/*
 * Copyright (c) 2020 Philippe Proulx <pproulx@efficios.com>
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

#include "barectf.h"
#include "test-platform.h"

struct test_platform_ctx {
	struct barectf_default_ctx ctx;
	FILE *fh;
};

static void write_packet(struct test_platform_ctx * const platform_ctx)
{
	const size_t nmemb = fwrite(barectf_packet_buf(&platform_ctx->ctx),
		barectf_packet_buf_size(&platform_ctx->ctx), 1,
			platform_ctx->fh);

	assert(nmemb == 1);
}

static int is_backend_full(void * const data)
{
	return 0;
}

static void open_packet(void * const data)
{
	struct test_platform_ctx * const platform_ctx = (void *) data;

	memset(barectf_packet_buf(&platform_ctx->ctx), 0,
		barectf_packet_buf_size(&platform_ctx->ctx));
	barectf_default_open_packet(&platform_ctx->ctx, 23, "salut");
}

static void close_packet(void * const data)
{
	struct test_platform_ctx * const platform_ctx = (void *) data;

	barectf_default_close_packet(&platform_ctx->ctx);
	write_packet(platform_ctx);
}

struct test_platform_ctx *test_platform_init(const size_t buf_size)
{
	uint8_t *buf;
	struct test_platform_ctx *platform_ctx;
	struct barectf_platform_callbacks cbs;

	cbs.is_backend_full = is_backend_full;
	cbs.open_packet = open_packet;
	cbs.close_packet = close_packet;
	platform_ctx = malloc(sizeof(*platform_ctx));
	assert(platform_ctx);
	buf = malloc(buf_size);
	assert(buf);
	platform_ctx->fh = fopen("stream", "wb");
	assert(platform_ctx->fh);
	barectf_init(&platform_ctx->ctx, buf, buf_size, cbs, platform_ctx);
	open_packet(platform_ctx);
	return platform_ctx;
}

void test_platform_fini(struct test_platform_ctx * const platform_ctx)
{
	if (barectf_packet_is_open(&platform_ctx->ctx)) {
		close_packet(platform_ctx);
	}

	fclose(platform_ctx->fh);
	free(barectf_packet_buf(&platform_ctx->ctx));
	free(platform_ctx);
}

struct barectf_default_ctx *test_platform_barectf_ctx(
	struct test_platform_ctx * const platform_ctx)
{
	return &platform_ctx->ctx;
}
