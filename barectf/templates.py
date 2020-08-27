# The MIT License (MIT)
#
# Copyright (c) 2015-2020 Philippe Proulx <pproulx@efficios.com>
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

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


_FUNC_OPEN_PROTO_BEGIN = '''/* open packet for stream `{sname}` */
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


_FUNC_CLOSE_PROTO = '''/* close packet for stream `{sname}` */
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


_FUNC_TRACE_PROTO_BEGIN = '''/* trace (stream `{sname}`, event `{evname}`) */
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


_C_SRC = '''/*
 * The MIT License (MIT)
 *
 * Copyright (c) 2015-2020 Philippe Proulx <pproulx@efficios.com>
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
#include "{bitfield_header_filename}"

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
