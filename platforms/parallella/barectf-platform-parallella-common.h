#ifndef _BARECTF_PLATFORM_PARALLELLA_COMMON_H
#define _BARECTF_PLATFORM_PARALLELLA_COMMON_H

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

#include "barectf-platform-parallella-config.h"

struct ringbuf {
	uint32_t consumer_index;
	uint32_t producer_index;
	uint8_t packets[RINGBUF_SZ][PACKET_SZ];

#ifdef DEBUG
	char error_buf[256];
#endif
};

#define CORES_COUNT		(CORES_ROWS * CORES_COLS)
#define SMEM_SZ			(sizeof(struct ringbuf) * CORES_COUNT)

static inline unsigned int rowcol2index(unsigned int row, unsigned int col)
{
	return row * CORES_COLS + col;
}

static inline volatile struct ringbuf *get_ringbuf(void *base,
	unsigned int row, unsigned int col)
{
	unsigned int index = rowcol2index(row, col);
	volatile struct ringbuf *ringbufs = (struct ringbuf *) base;

	return &ringbufs[index];
}

#endif /* _BARECTF_PLATFORM_PARALLELLA_COMMON_H */
