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
}};'''


_CTX_BEGIN = '''/* context for stream "{sname}" */
struct {prefix}{sname}_ctx {{
	/* parent */
	struct {prefix}ctx parent;

	/* config-specific members follow */'''


_CTX_END = '};'


_FUNC_INIT_PROTO = '''/* initialize context */
void {prefix}init(
	void *ctx,
	uint8_t *buf,
	uint32_t buf_size,
	struct {prefix}platform_callbacks cbs,
	void *data
)'''


_FUNC_INIT_BODY = '''{{
	struct {prefix}ctx *{prefix}ctx = ctx;
	{prefix}ctx->cbs = cbs;
	{prefix}ctx->data = data;
	{prefix}ctx->buf = buf;
	{prefix}ctx->packet_size = _BYTES_TO_BITS(buf_size);
	{prefix}ctx->at = 0;
	{prefix}ctx->events_discarded = 0;
	{prefix}ctx->packet_is_open = 0;
}}'''


_FUNC_OPEN_PROTO_BEGIN = '''/* open packet for stream "{sname}" */
void {prefix}{sname}_open_packet(
	struct {prefix}{sname}_ctx *ctx'''


_FUNC_OPEN_PROTO_END = ')'


_FUNC_OPEN_BODY_BEGIN = '{'


_FUNC_OPEN_BODY_END = '''
	ctx->parent.off_content = ctx->parent.at;

	/* mark current packet as open */
	ctx->parent.packet_is_open = 1;
}'''


_FUNC_CLOSE_PROTO = '''/* close packet for stream "{sname}" */
void {prefix}{sname}_close_packet(struct {prefix}{sname}_ctx *ctx)'''


_FUNC_CLOSE_BODY_BEGIN = '{'


_FUNC_CLOSE_BODY_END = '''
	/* go back to end of packet */
	ctx->parent.at = ctx->parent.packet_size;

	/* mark packet as closed */
	ctx->parent.packet_is_open = 0;
}'''


_DEFINE_DEFAULT_STREAM_TRACE = '#define {prefix}trace_{evname} {prefix}{sname}_trace_{evname}'


_FUNC_TRACE_PROTO_BEGIN = '''/* trace (stream "{sname}", event "{evname}") */
void {prefix}{sname}_trace_{evname}(
	struct {prefix}{sname}_ctx *ctx'''


_FUNC_TRACE_PROTO_END = ')'


_FUNC_TRACE_BODY = '''{{
	uint32_t ev_size;

	/* get event size */
	ev_size = _get_event_size_{sname}_{evname}((void *) ctx{params});

	/* do we have enough space to serialize? */
	if (!_reserve_event_space((void *) ctx, ev_size)) {{
		/* no: forget this */
		return;
	}}

	/* serialize event */
	_serialize_event_{sname}_{evname}((void *) ctx{params});

	/* commit event */
	_commit_event((void *) ctx);
}}'''


_FUNC_GET_EVENT_SIZE_PROTO_BEGIN = '''static uint32_t _get_event_size_{sname}_{evname}(
	struct {prefix}ctx *ctx'''


_FUNC_GET_EVENT_SIZE_PROTO_END = ')'


_FUNC_GET_EVENT_SIZE_BODY_BEGIN = '''{
	uint32_t at = ctx->at;'''


_FUNC_GET_EVENT_SIZE_BODY_END = '''	return at - ctx->at;
}'''


_FUNC_SERIALIZE_STREAM_EVENT_HEADER_PROTO_BEGIN = '''static void _serialize_stream_event_header_{sname}(
	struct {prefix}ctx *ctx,
	uint32_t event_id'''


_FUNC_SERIALIZE_STREAM_EVENT_HEADER_PROTO_END = ')'


_FUNC_SERIALIZE_STREAM_EVENT_HEADER_BODY_BEGIN = '{'


_FUNC_SERIALIZE_STREAM_EVENT_HEADER_BODY_END = '}'


_FUNC_SERIALIZE_STREAM_EVENT_CONTEXT_PROTO_BEGIN = '''static void _serialize_stream_event_context_{sname}(
	struct {prefix}ctx *ctx'''


_FUNC_SERIALIZE_STREAM_EVENT_CONTEXT_PROTO_END = ')'


_FUNC_SERIALIZE_STREAM_EVENT_CONTEXT_BODY_BEGIN = '{'


_FUNC_SERIALIZE_STREAM_EVENT_CONTEXT_BODY_END = '}'


_FUNC_SERIALIZE_EVENT_PROTO_BEGIN = '''static void _serialize_event_{sname}_{evname}(
	struct {prefix}ctx *ctx'''


_FUNC_SERIALIZE_EVENT_PROTO_END = ')'


_FUNC_SERIALIZE_EVENT_BODY_BEGIN = '{'


_FUNC_SERIALIZE_EVENT_BODY_END = '}'


_HEADER_BEGIN = '''#ifndef _{ucprefix}H
#define _{ucprefix}H

/*
 * The following C code was generated by barectf {version}
 * on {date}.
 *
 * For more details, see <https://github.com/efficios/barectf>.
 */

#include <stdint.h>

#include "{bitfield_header_filename}"

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
int {prefix}packet_is_open(void *ctx);'''


_HEADER_END = '#endif /* _{ucprefix}H */'


_C_SRC = '''/*
 * The following C code was generated by barectf {version}
 * on {date}.
 *
 * For more details, see <https://github.com/efficios/barectf>.
 */

#include <stdint.h>
#include <string.h>
#include <assert.h>

#include "{header_filename}"

#define _ALIGN(_at, _align)					\\
	do {{							\\
		(_at) = ((_at) + ((_align) - 1)) & -(_align);	\\
	}} while (0)

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
	return ((struct {prefix}ctx *) ctx)->packet_size;
}}

int {prefix}packet_is_full(void *ctx)
{{
	struct {prefix}ctx *cctx = ctx;

	return cctx->at == cctx->packet_size;
}}

int {prefix}packet_is_empty(void *ctx)
{{
	struct {prefix}ctx *cctx = ctx;

	return cctx->at <= cctx->off_content;
}}

uint32_t {prefix}packet_events_discarded(void *ctx)
{{
	return ((struct {prefix}ctx *) ctx)->events_discarded;
}}

uint8_t *{prefix}packet_buf(void *ctx)
{{
	return ((struct {prefix}ctx *) ctx)->buf;
}}

uint32_t {prefix}packet_buf_size(void *ctx)
{{
	return _BITS_TO_BYTES(((struct {prefix}ctx *) ctx)->packet_size);
}}

void {prefix}packet_set_buf(void *ctx, uint8_t *buf, uint32_t buf_size)
{{
	struct {prefix}ctx *{prefix}ctx = ctx;

	{prefix}ctx->buf = buf;
	{prefix}ctx->packet_size = _BYTES_TO_BITS(buf_size);
}}

int {prefix}packet_is_open(void *ctx)
{{
	return ((struct {prefix}ctx *) ctx)->packet_is_open;
}}

static
void _write_cstring(struct {prefix}ctx *ctx, const char *src)
{{
	uint32_t sz = strlen(src) + 1;

	memcpy(&ctx->buf[_BITS_TO_BYTES(ctx->at)], src, sz);
	ctx->at += _BYTES_TO_BITS(sz);
}}

static inline
int _packet_is_full(struct {prefix}ctx *ctx)
{{
	return {prefix}packet_is_full(ctx);
}}

static
int _reserve_event_space(struct {prefix}ctx *ctx, uint32_t ev_size)
{{
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
		ctx->cbs.open_packet(ctx->data);
	}}

	/* event fits the current packet? */
	if (ev_size > (ctx->packet_size - ctx->at)) {{
		/* no: close packet now */
		ctx->cbs.close_packet(ctx->data);

		/* is back-end full? */
		if (ctx->cbs.is_backend_full(ctx->data)) {{
			/* yes: discard event */
			ctx->events_discarded++;

			return 0;
		}}

		/* back-end is not full: open new packet */
		ctx->cbs.open_packet(ctx->data);
		assert(ev_size <= (ctx->packet_size - ctx->at));
	}}

	return 1;
}}

static
void _commit_event(struct {prefix}ctx *ctx)
{{
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

#include <stdint.h>	/* C99 5.2.4.2 Numerical limits */
#include <limits.h>

#define $PREFIX$BYTE_ORDER $ENDIAN_DEF$

/* We can't shift a int from 32 bit, >> 32 and << 32 on int is undefined */
#define _$prefix$bt_piecewise_rshift(_v, _shift) \\
__extension__ ({									\\
	__typeof__(_v) ___v = (_v);					\\
	__typeof__(_shift) ___shift = (_shift);				\\
	unsigned long sb = (___shift) / (sizeof(___v) * CHAR_BIT - 1);	\\
	unsigned long final = (___shift) % (sizeof(___v) * CHAR_BIT - 1); \\
									\\
	for (; sb; sb--)						\\
		___v >>= sizeof(___v) * CHAR_BIT - 1;			\\
	___v >>= final;							\\
})

#define _$prefix$bt_piecewise_lshift(_v, _shift) \\
__extension__ ({									\\
	__typeof__(_v) ___v = (_v);					\\
	__typeof__(_shift) ___shift = (_shift);				\\
	unsigned long sb = (___shift) / (sizeof(___v) * CHAR_BIT - 1);	\\
	unsigned long final = (___shift) % (sizeof(___v) * CHAR_BIT - 1); \\
									\\
	for (; sb; sb--)						\\
		___v <<= sizeof(___v) * CHAR_BIT - 1;			\\
	___v <<= final;							\\
})

#define _$prefix$bt_is_signed_type(type)	((type) -1 < (type) 0)

#define _$prefix$bt_unsigned_cast(type, v) \\
__extension__ ({									\\
	(sizeof(v) < sizeof(type)) ?					\\
		((type) (v)) & (~(~(type) 0 << (sizeof(v) * CHAR_BIT))) : \\
		(type) (v);						\\
})

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

#define _$prefix$bt_bitfield_write_le(_ptr, type, _start, _length, _v) \\
do {									\\
	__typeof__(_v) __v = (_v);					\\
	type *__ptr = (void *) (_ptr);					\\
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
		__v &= ~((~(__typeof__(__v)) 0) << __length);		\\
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
		__v = _$prefix$bt_piecewise_rshift(__v, ts - cshift); \\
		__start += ts - cshift;					\\
		this_unit++;						\\
	}								\\
	for (; this_unit < end_unit - 1; this_unit++) {			\\
		__ptr[this_unit] = (type) __v;				\\
		__v = _$prefix$bt_piecewise_rshift(__v, ts); \\
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

#define _$prefix$bt_bitfield_write_be(_ptr, type, _start, _length, _v) \\
do {									\\
	__typeof__(_v) __v = (_v);					\\
	type *__ptr = (void *) (_ptr);					\\
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
		__v &= ~((~(__typeof__(__v)) 0) << __length);		\\
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
		__v = _$prefix$bt_piecewise_rshift(__v, cshift); \\
		end -= cshift;						\\
		this_unit--;						\\
	}								\\
	for (; (long) this_unit >= (long) start_unit + 1; this_unit--) { \\
		__ptr[this_unit] = (type) __v;				\\
		__v = _$prefix$bt_piecewise_rshift(__v, ts); \\
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

#define $prefix$bt_bitfield_write_le(ptr, type, _start, _length, _v) \\
	_$prefix$bt_bitfield_write_le(ptr, type, _start, _length, _v)

#define $prefix$bt_bitfield_write_be(ptr, type, _start, _length, _v) \\
	_$prefix$bt_bitfield_write_be(ptr, unsigned char, _start, _length, _v)

#elif ($PREFIX$BYTE_ORDER == BIG_ENDIAN)

#define $prefix$bt_bitfield_write_le(ptr, type, _start, _length, _v) \\
	_$prefix$bt_bitfield_write_le(ptr, unsigned char, _start, _length, _v)

#define $prefix$bt_bitfield_write_be(ptr, type, _start, _length, _v) \\
	_$prefix$bt_bitfield_write_be(ptr, type, _start, _length, _v)

#else /* ($PREFIX$BYTE_ORDER == PDP_ENDIAN) */

#error "Byte order not supported"

#endif

#endif /* _$PREFIX$BITFIELD_H */
'''
