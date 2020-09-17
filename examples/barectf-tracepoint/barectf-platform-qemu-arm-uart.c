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

#include <stdint.h>
#include <stdio.h>
#include <barectf.h>

#include "barectf-platform-qemu-arm-uart.h"

#define BUF_SIZE		4096
#define TIMER_CTRL_32BIT	(1 << 1)
#define TIMER_CTRL_ENABLE	(1 << 7)

volatile uint32_t * const uart0 = (uint32_t *) 0x101f1000;
volatile uint32_t * const uart1 = (uint32_t *) 0x101f2000;
volatile uint32_t * const timer0_ctrl = (uint32_t *) 0x101e2008;
volatile uint32_t * const timer0_value = (uint32_t *) 0x101e2004;

static struct barectf_default_ctx barectf_ctx;

static uint8_t buf[BUF_SIZE];

static uint64_t get_clock(void* data)
{
	return (uint64_t) -*timer0_value;
}

static void flush_packet(void)
{
	size_t i;

	/* flush packet to UART 1 */
	for (i = 0; i < BUF_SIZE; ++i) {
		*uart1 = (uint32_t) buf[i];
	}
}

static int is_backend_full(void *data)
{
	return 0;
}

static void open_packet(void *data)
{
	barectf_default_open_packet(&barectf_ctx);
}

static void close_packet(void *data)
{
	/* close packet now */
	barectf_default_close_packet(&barectf_ctx);

	/* flush current packet */
	flush_packet();
}

void barectf_platform_qemu_arm_uart_init(void)
{
	struct barectf_platform_callbacks cbs = {
		.default_clock_get_value = get_clock,
		.is_backend_full = is_backend_full,
		.open_packet = open_packet,
		.close_packet = close_packet,
	};

	/* enable/start timer (clock source) */
	*timer0_ctrl |= TIMER_CTRL_32BIT | TIMER_CTRL_ENABLE;

	/* initialize barectf context */
	barectf_init(&barectf_ctx, buf, BUF_SIZE, cbs, NULL);

	/* open first packet */
	open_packet(NULL);

	/* indicate that tracing is starting */
	puts("tracing: starting");
}

void barectf_platform_qemu_arm_uart_fini(void)
{
	/* close last packet if it contains at least one event */
	if (barectf_packet_is_open(&barectf_ctx) &&
			!barectf_packet_is_empty(&barectf_ctx)) {
		close_packet(NULL);
	}

	/* indicate that tracing is done */
	puts("tracing: done");
}

struct barectf_default_ctx *barectf_platform_qemu_arm_uart_get_barectf_ctx()
{
	return &barectf_ctx;
}

#define STDOUT	1
#define STDERR	2

/* custom write "syscall" for newlib's stdio: write to UART 0 */
int _write(int file, char *ptr, int len) {
	if (file == STDOUT || file == STDERR) {
		int i;

		for (i = 0; i < len; i++) {
			*uart0 = (uint32_t) ptr[i];
		}
	}

	return 0;
}
