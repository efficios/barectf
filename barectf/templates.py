BARECTF_CTX = """struct {prefix}{sid}_ctx {{
	/* output buffer (will contain a CTF binary packet) */
	uint8_t* buf;

	/* buffer size in bits */
	uint32_t packet_size;

	/* current position from beginning of buffer in bits */
	uint32_t at;

	/* clock value callback */
{clock_cb}

	/* packet header + context size */
	uint32_t packet_header_context_size;

	/* config-specific members follow */
{ctx_fields}
}};"""

FUNC_INIT = """{si}int {prefix}{sid}_init(
	struct {prefix}{sid}_ctx* ctx,
	uint8_t* buf,
	uint32_t buf_size{params}
)"""

FUNC_OPEN = """{si}int {prefix}{sid}_open_packet(
	struct {prefix}{sid}_ctx* ctx{params}
)"""

FUNC_CLOSE = """{si}int {prefix}{sid}_close_packet(
	struct {prefix}{sid}_ctx* ctx{params}
)"""

FUNC_TRACE = """{si}int {prefix}{sid}_trace_{evname}(
	struct {prefix}{sid}_ctx* ctx{params}
)"""

WRITE_INTEGER = """{ucprefix}_CHK_OFFSET_V(ctx->at, ctx->packet_size, {sz});
{prefix}_bt_bitfield_write_{bo}(ctx->buf, uint8_t, ctx->at, {sz}, {src_name});
ctx->at += {sz};"""

HEADER = """#ifndef _{ucprefix}_H
#define _{ucprefix}_H

#include <stdint.h>
#include <string.h>

#include "{prefix}_bitfield.h"

/* barectf contexts */
{barectf_ctx}

/* barectf error codes */
#define E{ucprefix}_OK 0
#define E{ucprefix}_NOSPC 1

/* alignment macro */
#define {ucprefix}_ALIGN_OFFSET(_at, _align) \\
	do {{ \\
		_at = ((_at) + (_align - 1)) & -_align; \\
	}} while (0)

/* buffer overflow check macro */
#define {ucprefix}_CHK_OFFSET_V(_at, _bufsize, _size) \\
	do {{ \\
		if ((_at) + (_size) > (_bufsize)) {{ \\
			_at = ctx_at_begin; \\
			return -E{ucprefix}_NOSPC; \\
		}} \\
	}} while (0)

/* generated functions follow */
{functions}

#endif /* _{ucprefix}_H */
"""

CSRC = """#include <stdint.h>
#include <string.h>

#include "{prefix}.h"

{functions}
"""

BITFIELD = """#ifndef _$PREFIX$_BITFIELD_H
#define _$PREFIX$_BITFIELD_H

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

#define $PREFIX$_BYTE_ORDER $ENDIAN_DEF$

/* We can't shift a int from 32 bit, >> 32 and << 32 on int is undefined */
#define _$prefix$_bt_piecewise_rshift(_v, _shift)				\\
({									\\
	typeof(_v) ___v = (_v);						\\
	typeof(_shift) ___shift = (_shift);				\\
	unsigned long sb = (___shift) / (sizeof(___v) * CHAR_BIT - 1);	\\
	unsigned long final = (___shift) % (sizeof(___v) * CHAR_BIT - 1); \\
									\\
	for (; sb; sb--)						\\
		___v >>= sizeof(___v) * CHAR_BIT - 1;			\\
	___v >>= final;							\\
})

#define _$prefix$_bt_piecewise_lshift(_v, _shift)				\\
({									\\
	typeof(_v) ___v = (_v);						\\
	typeof(_shift) ___shift = (_shift);				\\
	unsigned long sb = (___shift) / (sizeof(___v) * CHAR_BIT - 1);	\\
	unsigned long final = (___shift) % (sizeof(___v) * CHAR_BIT - 1); \\
									\\
	for (; sb; sb--)						\\
		___v <<= sizeof(___v) * CHAR_BIT - 1;			\\
	___v <<= final;							\\
})

#define _$prefix$_bt_is_signed_type(type)	((type) -1 < (type) 0)

#define _$prefix$_bt_unsigned_cast(type, v)					\\
({									\\
	(sizeof(v) < sizeof(type)) ?					\\
		((type) (v)) & (~(~(type) 0 << (sizeof(v) * CHAR_BIT))) : \\
		(type) (v);						\\
})

/*
 * $prefix$_bt_bitfield_write - write integer to a bitfield in native endianness
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

#define _$prefix$_bt_bitfield_write_le(_ptr, type, _start, _length, _v)		\\
do {									\\
	typeof(_v) __v = (_v);						\\
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
		__v &= ~((~(typeof(__v)) 0) << __length);		\\
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
		__v = _$prefix$_bt_piecewise_rshift(__v, ts - cshift);		\\
		__start += ts - cshift;					\\
		this_unit++;						\\
	}								\\
	for (; this_unit < end_unit - 1; this_unit++) {			\\
		__ptr[this_unit] = (type) __v;				\\
		__v = _$prefix$_bt_piecewise_rshift(__v, ts);			\\
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

#define _$prefix$_bt_bitfield_write_be(_ptr, type, _start, _length, _v)		\\
do {									\\
	typeof(_v) __v = (_v);						\\
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
		__v &= ~((~(typeof(__v)) 0) << __length);		\\
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
		__v = _$prefix$_bt_piecewise_rshift(__v, cshift);		\\
		end -= cshift;						\\
		this_unit--;						\\
	}								\\
	for (; (long) this_unit >= (long) start_unit + 1; this_unit--) { \\
		__ptr[this_unit] = (type) __v;				\\
		__v = _$prefix$_bt_piecewise_rshift(__v, ts);			\\
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
 * $prefix$_bt_bitfield_write - write integer to a bitfield in native endianness
 * $prefix$_bt_bitfield_write_le - write integer to a bitfield in little endian
 * $prefix$_bt_bitfield_write_be - write integer to a bitfield in big endian
 */

#if ($PREFIX$_BYTE_ORDER == LITTLE_ENDIAN)

#define $prefix$_bt_bitfield_write(ptr, type, _start, _length, _v)		\\
	_$prefix$_bt_bitfield_write_le(ptr, type, _start, _length, _v)

#define $prefix$_bt_bitfield_write_le(ptr, type, _start, _length, _v)		\\
	_$prefix$_bt_bitfield_write_le(ptr, type, _start, _length, _v)

#define $prefix$_bt_bitfield_write_be(ptr, type, _start, _length, _v)		\\
	_$prefix$_bt_bitfield_write_be(ptr, unsigned char, _start, _length, _v)

#elif ($PREFIX$_BYTE_ORDER == BIG_ENDIAN)

#define $prefix$_bt_bitfield_write(ptr, type, _start, _length, _v)		\\
	_$prefix$_bt_bitfield_write_be(ptr, type, _start, _length, _v)

#define $prefix$_bt_bitfield_write_le(ptr, type, _start, _length, _v)		\\
	_$prefix$_bt_bitfield_write_le(ptr, unsigned char, _start, _length, _v)

#define $prefix$_bt_bitfield_write_be(ptr, type, _start, _length, _v)		\\
	_$prefix$_bt_bitfield_write_be(ptr, type, _start, _length, _v)

#else /* ($PREFIX$_BYTE_ORDER == PDP_ENDIAN) */

#error "Byte order not supported"

#endif

#endif /* _$PREFIX$_BITFIELD_H */
"""
