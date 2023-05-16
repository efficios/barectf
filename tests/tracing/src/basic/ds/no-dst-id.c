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
	struct test_platform_ctx * const platform_ctx = test_platform_init(128);

	assert(platform_ctx);
	barectf_default_trace_my_event(test_platform_barectf_ctx(platform_ctx),
		"When she was younger, Akko went to a magic show hosted by a witch named Shiny Chariot.");
	barectf_default_trace_my_event(test_platform_barectf_ctx(platform_ctx),
		"Akko was so inspired that she dreamed to someday be a cool witch.");
	test_platform_fini(platform_ctx);
	return 0;
}
