# The MIT License (MIT)
#
# Copyright (c) 2015-2016 Philippe Proulx <pproulx@efficios.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

_CLOCK_CB = '{return_ctype} (*{cname}_clock_get_value)(void *);'


_PLATFORM_CALLBACKS_BEGIN = '''/* barectf platform callbacks */
struct {prefix}platform_callbacks {{
	/* clock callbacks */'''


_PLATFORM_CALLBACKS_END = '''
	/* is back-end full? */
	int (*is_backend_full)(void *);

	/* open packet */
	void (*open_packet)(void *);

	/* close packet */
	void (*close_packet)(void *);
};'''


_CTX_PARENT = '''/* common barectf context */
struct {prefix}ctx {{
	/* platform callbacks */
	struct {prefix}platform_callbacks cbs;

	/* platform data (passed to callbacks) */
	void *data;

	/* output buffer (will contain a CTF binary packet) */
	uint8_t *buf;

	/* packet size in bits */
	uint32_t packet_size;

	/* content size in bits */
	uint32_t content_size;

	/* current position from beginning of packet in bits */
	uint32_t at;

	/* packet header + context size (content offset) */
	uint32_t off_content;

	/* events discarded */
	uint32_t events_discarded;

	/* current packet is opened */
	int packet_is_open;

	/* in tracing code */
	volatile int in_tracing_section;

	/* tracing is enabled */
	volatile int is_tracing_enabled;

	/* use current/last event timestamp when opening/closing packets */
	int use_cur_last_event_ts;
}};'''


_CTX_BEGIN = '''/* context for stream "{sname}" */
struct {prefix}{sname}_ctx {{
	/* parent */
	struct {prefix}ctx parent;

	/* config-specific members follow */'''


_CTX_END = '};'


_FUNC_INIT_PROTO = '''/* initialize context */
void {prefix}init(
	void *vctx,
	uint8_t *buf,
	uint32_t buf_size,
	struct {prefix}platform_callbacks cbs,
	void *data
)'''


_FUNC_INIT_BODY = '''{{
	struct {prefix}ctx *ctx = FROM_VOID_PTR(struct {prefix}ctx, vctx);
	ctx->cbs = cbs;
	ctx->data = data;
	ctx->buf = buf;
	ctx->packet_size = _BYTES_TO_BITS(buf_size);
	ctx->at = 0;
	ctx->events_discarded = 0;
	ctx->packet_is_open = 0;
	ctx->in_tracing_section = 0;
	ctx->is_tracing_enabled = 1;
	ctx->use_cur_last_event_ts = 0;
}}'''


_FUNC_OPEN_PROTO_BEGIN = '''/* open packet for stream "{sname}" */
void {prefix}{sname}_open_packet(
	struct {prefix}{sname}_ctx *ctx'''


_FUNC_OPEN_PROTO_END = ')'


_FUNC_OPEN_BODY_BEGIN = '''{{
{ts}
	const int saved_in_tracing_section = ctx->parent.in_tracing_section;

	/*
	 * This function is either called by a tracing function, or
	 * directly by the platform.
	 *
	 * If it's called by a tracing function, then
	 * ctx->parent.in_tracing_section is 1, so it's safe to open
	 * the packet here (alter the packet), even if tracing was
	 * disabled in the meantime because we're already in a tracing
	 * section (which finishes at the end of the tracing function
	 * call).
	 *
	 * If it's called directly by the platform, then if tracing is
	 * disabled, we don't want to alter the packet, and return
	 * immediately.
	 */
	if (!ctx->parent.is_tracing_enabled && !saved_in_tracing_section) {{
		ctx->parent.in_tracing_section = 0;
		return;
	}}

	/* we can modify the packet */
	ctx->parent.in_tracing_section = 1;
'''


_FUNC_OPEN_BODY_END = '''
	/* save content beginning's offset */
	ctx->parent.off_content = ctx->parent.at;

	/* mark current packet as open */
	ctx->parent.packet_is_open = 1;

	/* not tracing anymore */
	ctx->parent.in_tracing_section = saved_in_tracing_section;
}'''


_FUNC_CLOSE_PROTO = '''/* close packet for stream "{sname}" */
void {prefix}{sname}_close_packet(struct {prefix}{sname}_ctx *ctx)'''


_FUNC_CLOSE_BODY_BEGIN = '''{{
{ts}
	const int saved_in_tracing_section = ctx->parent.in_tracing_section;

	/*
	 * This function is either called by a tracing function, or
	 * directly by the platform.
	 *
	 * If it's called by a tracing function, then
	 * ctx->parent.in_tracing_section is 1, so it's safe to close
	 * the packet here (alter the packet), even if tracing was
	 * disabled in the meantime, because we're already in a tracing
	 * section (which finishes at the end of the tracing function
	 * call).
	 *
	 * If it's called directly by the platform, then if tracing is
	 * disabled, we don't want to alter the packet, and return
	 * immediately.
	 */
	if (!ctx->parent.is_tracing_enabled && !saved_in_tracing_section) {{
		ctx->parent.in_tracing_section = 0;
		return;
	}}

	/* we can modify the packet */
	ctx->parent.in_tracing_section = 1;
'''


_FUNC_CLOSE_BODY_END = '''
	/* go back to end of packet */
	ctx->parent.at = ctx->parent.packet_size;

	/* mark packet as closed */
	ctx->parent.packet_is_open = 0;

	/* not tracing anymore */
	ctx->parent.in_tracing_section = saved_in_tracing_section;
}'''


_DEFINE_DEFAULT_STREAM_TRACE = '#define {prefix}trace_{evname} {prefix}{sname}_trace_{evname}'


_FUNC_TRACE_PROTO_BEGIN = '''/* trace (stream "{sname}", event "{evname}") */
void {prefix}{sname}_trace_{evname}(
	struct {prefix}{sname}_ctx *ctx'''


_FUNC_TRACE_PROTO_END = ')'


_FUNC_TRACE_BODY = '''{{
	uint32_t ev_size;

	/* save timestamp */
	{save_ts}

	if (!ctx->parent.is_tracing_enabled) {{
		return;
	}}

	/* we can modify the packet */
	ctx->parent.in_tracing_section = 1;

	/* get event size */
	ev_size = _get_event_size_{sname}_{evname}(TO_VOID_PTR(ctx){params});

	/* do we have enough space to serialize? */
	if (!_reserve_event_space(TO_VOID_PTR(ctx), ev_size)) {{
		/* no: forget this */
		ctx->parent.in_tracing_section = 0;
		return;
	}}

	/* serialize event */
	_serialize_event_{sname}_{evname}(TO_VOID_PTR(ctx){params});

	/* commit event */
	_commit_event(TO_VOID_PTR(ctx));

	/* not tracing anymore */
	ctx->parent.in_tracing_section = 0;
}}'''


_FUNC_GET_EVENT_SIZE_PROTO_BEGIN = '''static uint32_t _get_event_size_{sname}_{evname}(
	void *vctx'''


_FUNC_GET_EVENT_SIZE_PROTO_END = ')'


_FUNC_GET_EVENT_SIZE_BODY_BEGIN = '''{{
	struct {prefix}ctx *ctx = FROM_VOID_PTR(struct {prefix}ctx, vctx);
	uint32_t at = ctx->at;'''


_FUNC_GET_EVENT_SIZE_BODY_END = '''	return at - ctx->at;
}'''


_FUNC_SERIALIZE_STREAM_EVENT_HEADER_PROTO_BEGIN = '''static void _serialize_stream_event_header_{sname}(
	void *vctx,
	uint32_t event_id'''


_FUNC_SERIALIZE_STREAM_EVENT_HEADER_PROTO_END = ')'


_FUNC_SERIALIZE_STREAM_EVENT_HEADER_BODY_BEGIN = '''{{
	struct {prefix}ctx *ctx = FROM_VOID_PTR(struct {prefix}ctx, vctx);'''


_FUNC_SERIALIZE_STREAM_EVENT_HEADER_BODY_END = '}'


_FUNC_SERIALIZE_STREAM_EVENT_CONTEXT_PROTO_BEGIN = '''static void _serialize_stream_event_context_{sname}(
	void *vctx'''


_FUNC_SERIALIZE_STREAM_EVENT_CONTEXT_PROTO_END = ')'


_FUNC_SERIALIZE_STREAM_EVENT_CONTEXT_BODY_BEGIN = '''{{
	struct {prefix}ctx *ctx = FROM_VOID_PTR(struct {prefix}ctx, vctx);'''


_FUNC_SERIALIZE_STREAM_EVENT_CONTEXT_BODY_END = '}'


_FUNC_SERIALIZE_EVENT_PROTO_BEGIN = '''static void _serialize_event_{sname}_{evname}(
	void *vctx'''


_FUNC_SERIALIZE_EVENT_PROTO_END = ')'


_FUNC_SERIALIZE_EVENT_BODY_BEGIN = '''{{
	struct {prefix}ctx *ctx = FROM_VOID_PTR(struct {prefix}ctx, vctx);'''


_FUNC_SERIALIZE_EVENT_BODY_END = '}'


_HEADER_BEGIN = '''#ifndef _{ucprefix}H
#define _{ucprefix}H

/*
 * The MIT License (MIT)
 *
 * Copyright (c) 2015-2016 Philippe Proulx <pproulx@efficios.com>
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
 *
 * - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
 *
 * The following C code was generated by barectf {version}
 * on {date}.
 *
 * For more details, see <http://barectf.org>.
 */

#include <stdint.h>

#include "{bitfield_header_filename}"

#ifdef __cplusplus
extern "C" {{
#endif

{prefix_def}
{default_stream_def}

{default_stream_trace_defs}

struct {prefix}ctx;

uint32_t {prefix}packet_size(void *ctx);
int {prefix}packet_is_full(void *ctx);
int {prefix}packet_is_empty(void *ctx);
uint32_t {prefix}packet_events_discarded(void *ctx);
uint8_t *{prefix}packet_buf(void *ctx);
void {prefix}packet_set_buf(void *ctx, uint8_t *buf, uint32_t buf_size);
uint32_t {prefix}packet_buf_size(void *ctx);
int {prefix}packet_is_open(void *ctx);
int {prefix}is_in_tracing_section(void *ctx);
volatile const int *{prefix}is_in_tracing_section_ptr(void *ctx);
int {prefix}is_tracing_enabled(void *ctx);
void {prefix}enable_tracing(void *ctx, int enable);'''


_HEADER_END = '''#ifdef __cplusplus
}}
#endif

#endif /* _{ucprefix}H */
'''


_C_SRC = '''/*
 * The MIT License (MIT)
 *
 * Copyright (c) 2015-2016 Philippe Proulx <pproulx@efficios.com>
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
 *
 * - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
 *
 * The following C code was generated by barectf {version}
 * on {date}.
 *
 * For more details, see <http://barectf.org>.
 */

#include <stdint.h>
#include <string.h>
#include <assert.h>

#include "{header_filename}"

#define _ALIGN(_at, _align)					\\
	do {{							\\
		(_at) = ((_at) + ((_align) - 1)) & -(_align);	\\
	}} while (0)

#ifdef __cplusplus
# define TO_VOID_PTR(_value)		static_cast<void *>(_value)
# define FROM_VOID_PTR(_type, _value)	static_cast<_type *>(_value)
#else
# define TO_VOID_PTR(_value)		((void *) (_value))
# define FROM_VOID_PTR(_type, _value)	((_type *) (_value))
#endif

#define _BITS_TO_BYTES(_x)	((_x) >> 3)
#define _BYTES_TO_BITS(_x)	((_x) << 3)

union f2u {{
	float f;
	uint32_t u;
}};

union d2u {{
	double f;
	uint64_t u;
}};

uint32_t {prefix}packet_size(void *ctx)
{{
	return FROM_VOID_PTR(struct {prefix}ctx, ctx)->packet_size;
}}

int {prefix}packet_is_full(void *ctx)
{{
	struct {prefix}ctx *cctx = FROM_VOID_PTR(struct {prefix}ctx, ctx);

	return cctx->at == cctx->packet_size;
}}

int {prefix}packet_is_empty(void *ctx)
{{
	struct {prefix}ctx *cctx = FROM_VOID_PTR(struct {prefix}ctx, ctx);

	return cctx->at <= cctx->off_content;
}}

uint32_t {prefix}packet_events_discarded(void *ctx)
{{
	return FROM_VOID_PTR(struct {prefix}ctx, ctx)->events_discarded;
}}

uint8_t *{prefix}packet_buf(void *ctx)
{{
	return FROM_VOID_PTR(struct {prefix}ctx, ctx)->buf;
}}

uint32_t {prefix}packet_buf_size(void *ctx)
{{
	struct {prefix}ctx *cctx = FROM_VOID_PTR(struct {prefix}ctx, ctx);

	return _BITS_TO_BYTES(cctx->packet_size);
}}

void {prefix}packet_set_buf(void *ctx, uint8_t *buf, uint32_t buf_size)
{{
	struct {prefix}ctx *cctx = FROM_VOID_PTR(struct {prefix}ctx, ctx);

	cctx->buf = buf;
	cctx->packet_size = _BYTES_TO_BITS(buf_size);
}}

int {prefix}packet_is_open(void *ctx)
{{
	return FROM_VOID_PTR(struct {prefix}ctx, ctx)->packet_is_open;
}}

int {prefix}is_in_tracing_section(void *ctx)
{{
	return FROM_VOID_PTR(struct {prefix}ctx, ctx)->in_tracing_section;
}}

volatile const int *{prefix}is_in_tracing_section_ptr(void *ctx)
{{
	return &FROM_VOID_PTR(struct {prefix}ctx, ctx)->in_tracing_section;
}}

int {prefix}is_tracing_enabled(void *ctx)
{{
	return FROM_VOID_PTR(struct {prefix}ctx, ctx)->is_tracing_enabled;
}}

void {prefix}enable_tracing(void *ctx, int enable)
{{
	FROM_VOID_PTR(struct {prefix}ctx, ctx)->is_tracing_enabled = enable;
}}

static
void _write_cstring(struct {prefix}ctx *ctx, const char *src)
{{
	uint32_t sz = strlen(src) + 1;

	memcpy(&ctx->buf[_BITS_TO_BYTES(ctx->at)], src, sz);
	ctx->at += _BYTES_TO_BITS(sz);
}}

static
int _reserve_event_space(void *vctx, uint32_t ev_size)
{{
	struct {prefix}ctx *ctx = FROM_VOID_PTR(struct {prefix}ctx, vctx);

	/* event _cannot_ fit? */
	if (ev_size > (ctx->packet_size - ctx->off_content)) {{
		ctx->events_discarded++;

		return 0;
	}}

	/* packet is full? */
	if ({prefix}packet_is_full(ctx)) {{
		/* yes: is back-end full? */
		if (ctx->cbs.is_backend_full(ctx->data)) {{
			/* yes: discard event */
			ctx->events_discarded++;

			return 0;
		}}

		/* back-end is not full: open new packet */
		ctx->use_cur_last_event_ts = 1;
		ctx->cbs.open_packet(ctx->data);
		ctx->use_cur_last_event_ts = 0;
	}}

	/* event fits the current packet? */
	if (ev_size > (ctx->packet_size - ctx->at)) {{
		/* no: close packet now */
		ctx->use_cur_last_event_ts = 1;
		ctx->cbs.close_packet(ctx->data);
		ctx->use_cur_last_event_ts = 0;

		/* is back-end full? */
		if (ctx->cbs.is_backend_full(ctx->data)) {{
			/* yes: discard event */
			ctx->events_discarded++;

			return 0;
		}}

		/* back-end is not full: open new packet */
		ctx->use_cur_last_event_ts = 1;
		ctx->cbs.open_packet(ctx->data);
		ctx->use_cur_last_event_ts = 0;
		assert(ev_size <= (ctx->packet_size - ctx->at));
	}}

	return 1;
}}

static
void _commit_event(void *vctx)
{{
	struct {prefix}ctx *ctx = FROM_VOID_PTR(struct {prefix}ctx, vctx);

	/* is packet full? */
	if ({prefix}packet_is_full(ctx)) {{
		/* yes: close it now */
		ctx->cbs.close_packet(ctx->data);
	}}
}}'''


_BITFIELD = '''#ifndef _$PREFIX$BITFIELD_H
#define _$PREFIX$BITFIELD_H

/*
 * BabelTrace
 *
 * Bitfields read/write functions.
 *
 * Copyright 2010 - Mathieu Desnoyers <mathieu.desnoyers@efficios.com>
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

#include <limits.h>

#ifdef __cplusplus
# define CAST_PTR(_type, _value) \\
	static_cast<_type>(static_cast<void *>(_value))
#else
# define CAST_PTR(_type, _value)	((void *) (_value))
#endif

#define $PREFIX$BYTE_ORDER $ENDIAN_DEF$

/* We can't shift a int from 32 bit, >> 32 and << 32 on int is undefined */
#define _$prefix$bt_piecewise_rshift(_vtype, _v, _shift) \\
do {									\\
	unsigned long ___shift = (_shift);				\\
	unsigned long sb = (___shift) / (sizeof(_v) * CHAR_BIT - 1);	\\
	unsigned long final = (___shift) % (sizeof(_v) * CHAR_BIT - 1); \\
									\\
	for (; sb; sb--)						\\
		_v >>= sizeof(_v) * CHAR_BIT - 1;			\\
	_v >>= final;							\\
} while (0)

/*
 * $prefix$bt_bitfield_write - write integer to a bitfield in native endianness
 *
 * Save integer to the bitfield, which starts at the "start" bit, has "len"
 * bits.
 * The inside of a bitfield is from high bits to low bits.
 * Uses native endianness.
 * For unsigned "v", pad MSB with 0 if bitfield is larger than v.
 * For signed "v", sign-extend v if bitfield is larger than v.
 *
 * On little endian, bytes are placed from the less significant to the most
 * significant. Also, consecutive bitfields are placed from lower bits to higher
 * bits.
 *
 * On big endian, bytes are places from most significant to less significant.
 * Also, consecutive bitfields are placed from higher to lower bits.
 */

#define _$prefix$bt_bitfield_write_le(_ptr, type, _start, _length, _vtype, _v) \\
do {									\\
	_vtype __v = (_v);					\\
	type *__ptr = CAST_PTR(type *, _ptr);				\\
	unsigned long __start = (_start), __length = (_length);		\\
	type mask, cmask;						\\
	unsigned long ts = sizeof(type) * CHAR_BIT; /* type size */	\\
	unsigned long start_unit, end_unit, this_unit;			\\
	unsigned long end, cshift; /* cshift is "complement shift" */	\\
									\\
	if (!__length)							\\
		break;							\\
									\\
	end = __start + __length;					\\
	start_unit = __start / ts;					\\
	end_unit = (end + (ts - 1)) / ts;				\\
									\\
	/* Trim v high bits */						\\
	if (__length < sizeof(__v) * CHAR_BIT)				\\
		__v &= ~((~(_vtype) 0) << __length);		\\
									\\
	/* We can now append v with a simple "or", shift it piece-wise */ \\
	this_unit = start_unit;						\\
	if (start_unit == end_unit - 1) {				\\
		mask = ~((~(type) 0) << (__start % ts));		\\
		if (end % ts)						\\
			mask |= (~(type) 0) << (end % ts);		\\
		cmask = (type) __v << (__start % ts);			\\
		cmask &= ~mask;						\\
		__ptr[this_unit] &= mask;				\\
		__ptr[this_unit] |= cmask;				\\
		break;							\\
	}								\\
	if (__start % ts) {						\\
		cshift = __start % ts;					\\
		mask = ~((~(type) 0) << cshift);			\\
		cmask = (type) __v << cshift;				\\
		cmask &= ~mask;						\\
		__ptr[this_unit] &= mask;				\\
		__ptr[this_unit] |= cmask;				\\
		_$prefix$bt_piecewise_rshift(_vtype, __v, ts - cshift); \\
		__start += ts - cshift;					\\
		this_unit++;						\\
	}								\\
	for (; this_unit < end_unit - 1; this_unit++) {			\\
		__ptr[this_unit] = (type) __v;				\\
		_$prefix$bt_piecewise_rshift(_vtype, __v, ts); 		\\
		__start += ts;						\\
	}								\\
	if (end % ts) {							\\
		mask = (~(type) 0) << (end % ts);			\\
		cmask = (type) __v;					\\
		cmask &= ~mask;						\\
		__ptr[this_unit] &= mask;				\\
		__ptr[this_unit] |= cmask;				\\
	} else								\\
		__ptr[this_unit] = (type) __v;				\\
} while (0)

#define _$prefix$bt_bitfield_write_be(_ptr, type, _start, _length, _vtype, _v) \\
do {									\\
	_vtype __v = (_v);					\\
	type *__ptr = CAST_PTR(type *, _ptr);				\\
	unsigned long __start = (_start), __length = (_length);		\\
	type mask, cmask;						\\
	unsigned long ts = sizeof(type) * CHAR_BIT; /* type size */	\\
	unsigned long start_unit, end_unit, this_unit;			\\
	unsigned long end, cshift; /* cshift is "complement shift" */	\\
									\\
	if (!__length)							\\
		break;							\\
									\\
	end = __start + __length;					\\
	start_unit = __start / ts;					\\
	end_unit = (end + (ts - 1)) / ts;				\\
									\\
	/* Trim v high bits */						\\
	if (__length < sizeof(__v) * CHAR_BIT)				\\
		__v &= ~((~(_vtype) 0) << __length);			\\
									\\
	/* We can now append v with a simple "or", shift it piece-wise */ \\
	this_unit = end_unit - 1;					\\
	if (start_unit == end_unit - 1) {				\\
		mask = ~((~(type) 0) << ((ts - (end % ts)) % ts));	\\
		if (__start % ts)					\\
			mask |= (~((type) 0)) << (ts - (__start % ts));	\\
		cmask = (type) __v << ((ts - (end % ts)) % ts);		\\
		cmask &= ~mask;						\\
		__ptr[this_unit] &= mask;				\\
		__ptr[this_unit] |= cmask;				\\
		break;							\\
	}								\\
	if (end % ts) {							\\
		cshift = end % ts;					\\
		mask = ~((~(type) 0) << (ts - cshift));			\\
		cmask = (type) __v << (ts - cshift);			\\
		cmask &= ~mask;						\\
		__ptr[this_unit] &= mask;				\\
		__ptr[this_unit] |= cmask;				\\
		_$prefix$bt_piecewise_rshift(_vtype, __v, cshift); \\
		end -= cshift;						\\
		this_unit--;						\\
	}								\\
	for (; (long) this_unit >= (long) start_unit + 1; this_unit--) { \\
		__ptr[this_unit] = (type) __v;				\\
		_$prefix$bt_piecewise_rshift(_vtype, __v, ts); \\
		end -= ts;						\\
	}								\\
	if (__start % ts) {						\\
		mask = (~(type) 0) << (ts - (__start % ts));		\\
		cmask = (type) __v;					\\
		cmask &= ~mask;						\\
		__ptr[this_unit] &= mask;				\\
		__ptr[this_unit] |= cmask;				\\
	} else								\\
		__ptr[this_unit] = (type) __v;				\\
} while (0)

/*
 * $prefix$bt_bitfield_write_le - write integer to a bitfield in little endian
 * $prefix$bt_bitfield_write_be - write integer to a bitfield in big endian
 */

#if ($PREFIX$BYTE_ORDER == LITTLE_ENDIAN)

#define $prefix$bt_bitfield_write_le(ptr, type, _start, _length, _vtype, _v) \\
	_$prefix$bt_bitfield_write_le(ptr, type, _start, _length, _vtype, _v)

#define $prefix$bt_bitfield_write_be(ptr, type, _start, _length, _vtype, _v) \\
	_$prefix$bt_bitfield_write_be(ptr, unsigned char, _start, _length, _vtype, _v)

#elif ($PREFIX$BYTE_ORDER == BIG_ENDIAN)

#define $prefix$bt_bitfield_write_le(ptr, type, _start, _length, _vtype, _v) \\
	_$prefix$bt_bitfield_write_le(ptr, unsigned char, _start, _length, _vtype, _v)

#define $prefix$bt_bitfield_write_be(ptr, type, _start, _length, _vtype, _v) \\
	_$prefix$bt_bitfield_write_be(ptr, type, _start, _length, _vtype, _v)

#else /* ($PREFIX$BYTE_ORDER == PDP_ENDIAN) */

#error "Byte order not supported"

#endif

#endif /* _$PREFIX$BITFIELD_H */
'''
