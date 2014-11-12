BARECTF_CTX = """struct {prefix}{sid}_ctx {{
	/* output buffer (will contain a CTF binary packet) */
	uint8_t* buf;

	/* buffer size in bits */
	uint32_t buf_size;

	/* current position from beginning of buffer in bits */
	uint32_t at;

	/* config-specific members follow */
{ctx_fields}
}};"""

HEADER = """
#ifndef _{ucprefix}_H
#define _{ucprefix}_H

#include <stdint.h>

/* barectf contexts */
{barectf_ctx}

/* barectf error codes */
#define E{ucprefix}_OK		0
#define E{ucprefix}_NOSPC	1

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
