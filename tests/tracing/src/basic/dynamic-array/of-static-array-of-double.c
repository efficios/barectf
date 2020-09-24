/*
 * The MIT License (MIT)
 *
 * Copyright (c) 2020 Philippe Proulx <pproulx@efficios.com>
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

#include <assert.h>

#include "test-platform.h"
#include "barectf.h"

int main(void)
{
	struct test_platform_ctx *platform_ctx;
	const double subarray1[] = {-17.5, 15.48, 1001.};
	const double subarray2[] = {.1534, 555.555, 1e9};
	const double * const array[] = {subarray1, subarray2, subarray1};

	platform_ctx = test_platform_init(512);
	assert(platform_ctx);
	barectf_trace_ev(test_platform_barectf_ctx(platform_ctx), 3, array);
	test_platform_fini(platform_ctx);
	return 0;
}
