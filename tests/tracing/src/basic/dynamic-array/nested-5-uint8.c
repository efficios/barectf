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
#include <stdint.h>

#include "test-platform.h"
#include "barectf.h"

int main(void)
{
	struct test_platform_ctx *platform_ctx;
	const uint8_t subsubsubsubarray1[] = {1, 2};
	const uint8_t subsubsubsubarray2[] = {3, 4};
	const uint8_t subsubsubsubarray3[] = {5, 6};
	const uint8_t subsubsubsubarray4[] = {7, 8};
	const uint8_t subsubsubsubarray5[] = {9, 10};
	const uint8_t subsubsubsubarray6[] = {11, 12};
	const uint8_t subsubsubsubarray7[] = {13, 14};
	const uint8_t subsubsubsubarray8[] = {15, 16};
	const uint8_t subsubsubsubarray9[] = {17, 18};
	const uint8_t subsubsubsubarray10[] = {19, 20};
	const uint8_t subsubsubsubarray11[] = {21, 22};
	const uint8_t subsubsubsubarray12[] = {23, 24};
	const uint8_t subsubsubsubarray13[] = {25, 26};
	const uint8_t subsubsubsubarray14[] = {27, 28};
	const uint8_t subsubsubsubarray15[] = {29, 30};
	const uint8_t subsubsubsubarray16[] = {31, 32};
	const uint8_t * const subsubsubarray1[] = {subsubsubsubarray1, subsubsubsubarray2};
	const uint8_t * const subsubsubarray2[] = {subsubsubsubarray3, subsubsubsubarray4};
	const uint8_t * const subsubsubarray3[] = {subsubsubsubarray5, subsubsubsubarray6};
	const uint8_t * const subsubsubarray4[] = {subsubsubsubarray7, subsubsubsubarray8};
	const uint8_t * const subsubsubarray5[] = {subsubsubsubarray9, subsubsubsubarray10};
	const uint8_t * const subsubsubarray6[] = {subsubsubsubarray11, subsubsubsubarray12};
	const uint8_t * const subsubsubarray7[] = {subsubsubsubarray13, subsubsubsubarray14};
	const uint8_t * const subsubsubarray8[] = {subsubsubsubarray15, subsubsubsubarray16};
	const uint8_t * const * const subsubarray1[] = {subsubsubarray1, subsubsubarray2};
	const uint8_t * const * const subsubarray2[] = {subsubsubarray3, subsubsubarray4};
	const uint8_t * const * const subsubarray3[] = {subsubsubarray5, subsubsubarray6};
	const uint8_t * const * const subsubarray4[] = {subsubsubarray7, subsubsubarray8};
	const uint8_t * const * const * const subarray1[] = {subsubarray1, subsubarray2};
	const uint8_t * const * const * const subarray2[] = {subsubarray3, subsubarray4};
	const uint8_t * const * const * const subarray3[] = {subsubarray1, subsubarray4};
	const uint8_t * const * const * const * const array[] = {subarray1, subarray2, subarray3};

	platform_ctx = test_platform_init(512);
	assert(platform_ctx);
	barectf_trace_ev(test_platform_barectf_ctx(platform_ctx), 3, array);
	test_platform_fini(platform_ctx);
	return 0;
}
