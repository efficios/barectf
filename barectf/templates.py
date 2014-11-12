BARECTF_CTX = """struct {prefix}{sid}_ctx {{
	/* output buffer (will contain a CTF binary packet) */
	uint8_t* buf;

	/* buffer size in bits */
	uint32_t buf_size;

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

FUNC_OPEN = """{si}int {prefix}{sid}_open(
	struct {prefix}{sid}_ctx* ctx{params}
)"""

FUNC_CLOSE = """{si}void {prefix}{sid}_close(
	struct {prefix}{sid}_ctx* ctx{params}
)"""

FUNC_TRACE = """{si}int {prefix}{sid}_trace_{evname}(
	struct {prefix}{sid}_ctx* ctx{params}
)"""

WRITE_INTEGER = """{ucprefix}_CHK_OFFSET_V(ctx->at, ctx->buf_size, {sz});
{prefix}_bitfield_write_{bo}(ctx->buf, {type}, ctx->at, {sz}, {src_name});
ctx->at += {sz};"""

HEADER = """#ifndef _{ucprefix}_H
#define _{ucprefix}_H

#include <stdint.h>

#include "{prefix}_bitfields.h"

/* barectf contexts */
{barectf_ctx}

/* barectf error codes */
#define E{ucprefix}_OK 0
#define E{ucprefix}_NOSPC 1

/* alignment macro */
#define {ucprefix}_ALIGN_OFFSET(_at, _align) \\
	do {{ \\
		_at = ((_at) + (_align)) & ~((_at) + (_align)); \\
	}} while (0)

/* buffer overflow check macro */
#define {ucprefix}_CHK_OFFSET_V(_at, _bufsize, _size) \\
	do {{ \\
		if ((_at) + (_size) > (_bufsize)) {{ \\
			return -E{ucprefix}_NOSPC; \\
		}} \\
	}} while (0)

/* generated functions follow */
{functions}

#endif /* _{ucprefix}_H */
"""

CSRC = """#include "{prefix}.h"

{functions}
"""
