#ifndef _BARECTF_TRACEPOINT_QEMU_ARM_UART
#define _BARECTF_TRACEPOINT_QEMU_ARM_UART

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

#include <barectf-platform-qemu-arm-uart.h>

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

/* init function for this version */
static void init_tracing(void)
{
	/* initialize platform */
	barectf_platform_qemu_arm_uart_init();
	global_barectf_ctx = barectf_platform_qemu_arm_uart_get_barectf_ctx();
}

/* finalization function for this version */
static void fini_tracing(void)
{
	/* finalize platform */
	barectf_platform_qemu_arm_uart_fini();
}

#endif /* _BARECTF_TRACEPOINT_QEMU_ARM_UART */
