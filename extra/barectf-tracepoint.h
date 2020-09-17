#ifndef _BARECTF_TRACEPOINT_H
#define _BARECTF_TRACEPOINT_H

/*
 * The MIT License (MIT)
 *
 * Copyright (c) 2016-2020 Philippe Proulx <pproulx@efficios.com>
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

/* Get identifier prefix */
#ifdef BARECTF_TRACEPOINT_PREFIX
# define _BARECTF_TRACEPOINT_PREFIX BARECTF_TRACEPOINT_PREFIX
#else
# ifdef _BARECTF_IDENTIFIER_PREFIX
#  define _BARECTF_TRACEPOINT_PREFIX _BARECTF_IDENTIFIER_PREFIX
# else
#  error You must define `BARECTF_TRACEPOINT_PREFIX` to use this header.
# endif
#endif

/* Get data stream type name to use */
#ifdef BARECTF_TRACEPOINT_STREAM
# define _BARECTF_TRACEPOINT_DST_NAME BARECTF_TRACEPOINT_STREAM
#elif defined(BARECTF_TRACEPOINT_DATA_STREAM_TYPE_NAME)
# define _BARECTF_TRACEPOINT_DST_NAME BARECTF_TRACEPOINT_DATA_STREAM_TYPE_NAME
#else
# ifdef _BARECTF_DEFAULT_DATA_STREAM_TYPE_NAME
#  define _BARECTF_TRACEPOINT_DST_NAME _BARECTF_DEFAULT_DATA_STREAM_TYPE_NAME
# else
#  error You must define `BARECTF_TRACEPOINT_DATA_STREAM_TYPE_NAME` to use this header.
# endif
#endif

/* Get context to use */
#ifndef BARECTF_TRACEPOINT_CTX
# error You must define `BARECTF_TRACEPOINT_CTX` to use this header.
#endif

/*
 * Combines 6 token. Inspired by __TP_COMBINE_TOKENS4() in
 * <lttng/tracepoint.h>. See sections 6.10.3 and 6.10.3.1 of
 * ISO/IEC 9899:1999.
 */
#define __COMBINE_TOKENS6(_a, _b, _c, _d, _e, _f) \
	_a ## _b ## _c ## _d ## _e ## _f
#define _COMBINE_TOKENS6(_a, _b, _c, _d, _e, _f) \
	__COMBINE_TOKENS6(_a, _b, _c, _d, _e, _f)

/* tracepoint() used by the user */
#undef tracepoint
#define tracepoint(_prov_name, _tp_name, ...) \
	_COMBINE_TOKENS6(_BARECTF_TRACEPOINT_PREFIX, _BARECTF_TRACEPOINT_DST_NAME, _trace_, _prov_name, _, _tp_name)(BARECTF_TRACEPOINT_CTX, ##__VA_ARGS__)

#endif /* _BARECTF_TRACEPOINT_H */
