#undef TRACEPOINT_PROVIDER
#define TRACEPOINT_PROVIDER barectf_tp

#undef TRACEPOINT_INCLUDE
#define TRACEPOINT_INCLUDE "./tp.h"

#if !defined(_TP_H) || defined(TRACEPOINT_HEADER_MULTI_READ)
#define _TP_H

#include <lttng/tracepoint.h>
#include <stdint.h>

TRACEPOINT_EVENT(
	barectf_tp,
	simple_uint32,
	TP_ARGS(
		uint32_t, value
	),
	TP_FIELDS(
		ctf_integer(uint32_t, value, value)
	)
)

TRACEPOINT_LOGLEVEL(barectf_tp, simple_uint32, TRACE_CRIT)

TRACEPOINT_EVENT(
	barectf_tp,
	simple_int16,
	TP_ARGS(
		int16_t, value
	),
	TP_FIELDS(
		ctf_integer(int16_t, value, value)
	)
)

TRACEPOINT_EVENT(
	barectf_tp,
	simple_float,
	TP_ARGS(
		float, value
	),
	TP_FIELDS(
		ctf_float(float, value, value)
	)
)

TRACEPOINT_EVENT(
	barectf_tp,
	simple_string,
	TP_ARGS(
		const char *, value
	),
	TP_FIELDS(
		ctf_string(value, value)
	)
)

TRACEPOINT_LOGLEVEL(barectf_tp, simple_string, TRACE_WARNING)

TRACEPOINT_ENUM(
	barectf_tp,
	state,
	TP_ENUM_VALUES(
        	ctf_enum_value("NEW", 0)
        	ctf_enum_value("TERMINATED", 1)
        	ctf_enum_value("READY", 2)
        	ctf_enum_value("RUNNING", 3)
        	ctf_enum_value("WAITING", 4)
	)
)

TRACEPOINT_EVENT(
	barectf_tp,
	simple_enum,
	TP_ARGS(
		int, value
	),
	TP_FIELDS(
		ctf_enum(barectf_tp, state, int, value, value)
	)
)

TRACEPOINT_EVENT(
	barectf_tp,
	a_few_fields,
	TP_ARGS(
		int32_t, int32,
		uint16_t, int16,
		double, dbl,
		const char *, str,
		int, state
	),
	TP_FIELDS(
		ctf_integer(int32_t, int32, int32)
		ctf_integer(int16_t, int16, int16)
		ctf_float(double, dbl, dbl)
		ctf_string(str, str)
		ctf_enum(barectf_tp, state, int, state, state)
	)
)

TRACEPOINT_EVENT(
	barectf_tp,
	bit_packed_integers,
	TP_ARGS(
		uint8_t, uint1,
		int8_t, int1,
		uint8_t, uint2,
		int8_t, int3,
		uint8_t, uint4,
		int8_t, int5,
		uint8_t, uint6,
		int8_t, int7,
		uint8_t, uint8
	),
	TP_FIELDS(
		ctf_integer(uint8_t, uint1, uint1)
		ctf_integer(int8_t, int1, int1)
		ctf_integer(uint8_t, uint2, uint2)
		ctf_integer(int8_t, int3, int3)
		ctf_integer(uint8_t, uint4, uint4)
		ctf_integer(int8_t, int5, int5)
		ctf_integer(uint8_t, uint6, uint6)
		ctf_integer(int8_t, int7, int7)
		ctf_integer(uint8_t, uint8, uint8)
	)
)

TRACEPOINT_LOGLEVEL(barectf_tp, bit_packed_integers, 513)

#endif /* _TP_H */

#include <lttng/tracepoint-event.h>
