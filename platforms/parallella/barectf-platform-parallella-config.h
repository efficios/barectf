#ifndef _BARECTF_PLATFORM_PARALLELLA_CONFIG_H
#define _BARECTF_PLATFORM_PARALLELLA_CONFIG_H

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

/* barectf Parallella platform parameters */

/* cores/row (4 for the Parallella) */
#define CORES_ROWS		4

/* cores/row (4 for the Parallella) */
#define CORES_COLS		4

/* packet size (must be a power of two) */
#ifndef PACKET_SZ
#define PACKET_SZ		256
#endif

/* ring buffer size (at least 2) */
#ifndef RINGBUF_SZ
#define RINGBUF_SZ		4
#endif

/* shared memory region name */
#ifndef SMEM_NAME
#define SMEM_NAME		"barectf-tracing"
#endif

/* backend check timeout (cycles) */
#ifndef BACKEND_CHECK_TIMEOUT
#define BACKEND_CHECK_TIMEOUT	(10000000ULL)
#endif

/* consumer poll delay (µs) */
#ifndef CONSUMER_POLL_DELAY
#define CONSUMER_POLL_DELAY	(5000)
#endif

#endif /* _BARECTF_PLATFORM_PARALLELLA_CONFIG_H */
