/*
 * barectf Parallella platform
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
#include <stdio.h>
#include <string.h>
#include <e_lib.h>

#include "barectf-platform-parallella-common.h"
#include "barectf-platform-parallella.h"
#include "barectf.h"

static struct tracing_ctx {
	struct barectf_default_ctx barectf_ctx;
	volatile struct ringbuf *ringbuf;
	uint64_t last_backend_check;
	uint64_t clock_high;
	e_memseg_t smem;

	/*
	 * Use a producer index's shadow in local memory to avoid
	 * reading the old value of the producer index in shared memory
	 * after having incremented it.
	 *
	 * NEVER read or write the producer index or its shadow
	 * directly: always use get_prod_index() and incr_prod_index().
	 */
	uint32_t producer_index_shadow;

	unsigned int row, col;
	uint8_t local_packet[PACKET_SZ];
	uint8_t initialized;
	uint8_t backend_wait_period;
} g_tracing_ctx;

struct barectf_default_ctx *tracing_get_barectf_ctx(void)
{
	return &g_tracing_ctx.barectf_ctx;
}

static inline void incr_prod_index(struct tracing_ctx *tracing_ctx)
{
	tracing_ctx->producer_index_shadow++;
	tracing_ctx->ringbuf->producer_index =
		tracing_ctx->producer_index_shadow;
}

static inline uint32_t get_prod_index(struct tracing_ctx *tracing_ctx)
{
	return tracing_ctx->producer_index_shadow;
}

static uint64_t get_clock(void* data)
{
	struct tracing_ctx *tracing_ctx = data;

	uint64_t low = (uint64_t)
		((uint32_t) (E_CTIMER_MAX - e_ctimer_get(E_CTIMER_1)));

	return tracing_ctx->clock_high | low;
}

static int is_backend_full(void *data)
{
	struct tracing_ctx *tracing_ctx = data;
	int check_shared = 0;
	int full;

	/* are we in a back-end checking waiting period? */
	if (tracing_ctx->backend_wait_period) {
		/* yes: check if we may check in shared memory now */
		uint64_t cur_clock = get_clock(data);

		if (cur_clock - tracing_ctx->last_backend_check >=
				BACKEND_CHECK_TIMEOUT) {
			/* check in shared memory */
			check_shared = 1;
			tracing_ctx->last_backend_check = cur_clock;
		}
	} else {
		/* no: check in shared memory */
		check_shared = 1;
	}

	if (check_shared) {
		full = (get_prod_index(tracing_ctx) -
			tracing_ctx->ringbuf->consumer_index) == RINGBUF_SZ;
		tracing_ctx->backend_wait_period = full;

		if (full) {
			tracing_ctx->last_backend_check = get_clock(data);
		}
	} else {
		/* no shared memory checking: always considered full */
		full = 1;
	}

	return full;
}

static void open_packet(void *data)
{
	struct tracing_ctx *tracing_ctx = data;

	barectf_default_open_packet(&tracing_ctx->barectf_ctx,
		tracing_ctx->row, tracing_ctx->col);
}

static void close_packet(void *data)
{
	struct tracing_ctx *tracing_ctx = data;
	void *dst;
	unsigned int index;

	/* close packet now */
	barectf_default_close_packet(&tracing_ctx->barectf_ctx);

	/*
	 * We know for sure that there is space in the back-end (ring
	 * buffer) for this packet, so "upload" it to shared memory now.
	 */
	index = get_prod_index(tracing_ctx) & (RINGBUF_SZ - 1);
	dst = (void *) &(tracing_ctx->ringbuf->packets[index][0]);
	memcpy(dst, tracing_ctx->local_packet, PACKET_SZ);

	/* update producer index after copy */
	incr_prod_index(tracing_ctx);
}

static struct barectf_platform_callbacks cbs = {
	.default_clock_get_value = get_clock,
	.is_backend_full = is_backend_full,
	.open_packet = open_packet,
	.close_packet = close_packet,
};

static void __attribute__((interrupt)) timer1_trace_isr()
{
	/* CTIMER1 reaches 0: reset to max value and start */
	g_tracing_ctx.clock_high += (1ULL << 32);
	e_ctimer_set(E_CTIMER_1, E_CTIMER_MAX);
	e_ctimer_start(E_CTIMER_1, E_CTIMER_CLK);
	return;
}

static void init_clock(void)
{
	/* stop and reset CTIMER1 */
	e_ctimer_stop(E_CTIMER_1);
	e_ctimer_set(E_CTIMER_1, E_CTIMER_MAX);
	g_tracing_ctx.clock_high = 0;

	/* enable CTIMER1 interrupt */
	e_irq_global_mask(E_FALSE);
	e_irq_attach(E_TIMER1_INT, timer1_trace_isr);
	e_irq_mask(E_TIMER1_INT, E_FALSE);
}

static void stop_clock(void)
{
	e_ctimer_stop(E_CTIMER_1);
	e_irq_mask(E_TIMER1_INT, E_TRUE);
}

void tracing_reset_clock(void)
{
	e_ctimer_set(E_CTIMER_1, E_CTIMER_MAX);
	g_tracing_ctx.clock_high = 0;
	g_tracing_ctx.backend_wait_period = 0;
	g_tracing_ctx.last_backend_check = 0;
	e_ctimer_start(E_CTIMER_1, E_CTIMER_CLK);
}

int tracing_init(void)
{
	e_coreid_t coreid;

	if (g_tracing_ctx.initialized) {
		/* already initialized */
		return 0;
	}

	barectf_init(&g_tracing_ctx.barectf_ctx,
		g_tracing_ctx.local_packet, PACKET_SZ, cbs, &g_tracing_ctx);

	/* zero local packet */
	memset(g_tracing_ctx.local_packet, 0, PACKET_SZ);

	/* attach to shared memory */
	if (e_shm_attach(&g_tracing_ctx.smem, SMEM_NAME) != E_OK) {
		return -1;
	}

	/* get core's row and column */
	coreid = e_get_coreid();
	e_coords_from_coreid(coreid, &g_tracing_ctx.row, &g_tracing_ctx.col);

	/* get core's ring buffer */
	g_tracing_ctx.ringbuf =
		get_ringbuf((void *) g_tracing_ctx.smem.ephy_base,
			g_tracing_ctx.row, g_tracing_ctx.col);

	/* initialize tracing clock */
	init_clock();

	/* start tracing clock */
	tracing_reset_clock();

	/* open first packet */
	open_packet(&g_tracing_ctx);

	/* acknowledge initialization */
	g_tracing_ctx.initialized = 1;

	return 0;
}

void tracing_fini(void)
{
	if (!g_tracing_ctx.initialized) {
		/* not initialized yet */
		return;
	}

	/* close last packet if open and not empty */
	if (barectf_packet_is_open(&g_tracing_ctx.barectf_ctx) &&
			!barectf_packet_is_empty(&g_tracing_ctx.barectf_ctx)) {
		close_packet(&g_tracing_ctx);
	}

	/* stop CTIMER1 */
	stop_clock();
}
