# The MIT License (MIT)
#
# Copyright (c) 2015 Philippe Proulx <pproulx@efficios.com>
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

from barectf import metadata
from barectf import codegen
import datetime
import barectf


_bo_to_string_map = {
    metadata.ByteOrder.LE: 'le',
    metadata.ByteOrder.BE: 'be',
}


_encoding_to_string_map = {
    metadata.Encoding.NONE: 'none',
    metadata.Encoding.ASCII: 'ASCII',
    metadata.Encoding.UTF8: 'UTF8',
}


def _bo_to_string(bo):
    return _bo_to_string_map[bo]


def _encoding_to_string(encoding):
    return _encoding_to_string_map[encoding]


def _bool_to_string(b):
    return 'true' if b else 'false'


def _gen_integer(t, cg):
    cg.add_line('integer {')
    cg.indent()
    cg.add_line('size = {};'.format(t.size))
    cg.add_line('align = {};'.format(t.align))
    cg.add_line('signed = {};'.format(_bool_to_string(t.signed)))
    cg.add_line('byte_order = {};'.format(_bo_to_string(t.byte_order)))
    cg.add_line('base = {};'.format(t.base))
    cg.add_line('encoding = {};'.format(_encoding_to_string(t.encoding)))

    if t.property_mappings:
        clock_name = t.property_mappings[0].object.name
        cg.add_line('map = clock.{}.value;'.format(clock_name))

    cg.unindent()
    cg.add_line('}')


def _gen_float(t, cg):
    cg.add_line('floating_point {')
    cg.indent()
    cg.add_line('exp_dig = {};'.format(t.exp_size))
    cg.add_line('mant_dig = {};'.format(t.mant_size))
    cg.add_line('align = {};'.format(t.align))
    cg.add_line('byte_order = {};'.format(_bo_to_string(t.byte_order)))
    cg.unindent()
    cg.add_line('}')


def _gen_enum(t, cg):
    cg.add_line('enum : ')
    cg.add_glue()
    _gen_type(t.value_type, cg)
    cg.append_to_last_line(' {')
    cg.indent()

    for label, (mn, mx) in t.members.items():
        if mn == mx:
            rg = str(mn)
        else:
            rg = '{} ... {}'.format(mn, mx)

        line = '"{}" = {},'.format(label, rg)
        cg.add_line(line)

    cg.unindent()
    cg.add_line('}')


def _gen_string(t, cg):
    cg.add_line('string {')
    cg.indent()
    cg.add_line('encoding = {};'.format(_encoding_to_string(t.encoding)))
    cg.unindent()
    cg.add_line('}')


def _find_deepest_array_element_type(t):
    if type(t) is metadata.Array:
        return _find_deepest_array_element_type(t.element_type)

    return t


def _fill_array_lengths(t, lengths):
    if type(t) is metadata.Array:
        lengths.append(t.length)
        _fill_array_lengths(t.element_type, lengths)


def _gen_struct_variant_entry(name, t, cg):
    real_t = _find_deepest_array_element_type(t)
    _gen_type(real_t, cg)
    cg.append_to_last_line(' {}'.format(name))

    # array
    lengths = []
    _fill_array_lengths(t, lengths)

    if lengths:
        for length in reversed(lengths):
            cg.append_to_last_line('[{}]'.format(length))

    cg.append_to_last_line(';')


def _gen_struct(t, cg):
    cg.add_line('struct {')
    cg.indent()

    for field_name, field_type in t.fields.items():
        _gen_struct_variant_entry(field_name, field_type, cg)

    cg.unindent()

    if not t.fields:
        cg.add_glue()

    cg.add_line('}} align({})'.format(t.min_align))


def _gen_variant(t, cg):
    cg.add_line('variant <{}> {{'.format(t.tag))
    cg.indent()

    for type_name, type_type in t.types.items():
        _gen_struct_variant_entry(type_name, type_type, cg)

    cg.unindent()

    if not t.types:
        cg.add_glue()

    cg.add_line('}')


_type_to_gen_type_func = {
    metadata.Integer: _gen_integer,
    metadata.FloatingPoint: _gen_float,
    metadata.Enum: _gen_enum,
    metadata.String: _gen_string,
    metadata.Struct: _gen_struct,
    metadata.Variant: _gen_variant,
}


def _gen_type(t, cg):
    _type_to_gen_type_func[type(t)](t, cg)


def _gen_entity(name, t, cg):
    cg.add_line('{} := '.format(name))
    cg.add_glue()
    _gen_type(t, cg)
    cg.append_to_last_line(';')


def _gen_start_block(name, cg):
    cg.add_line('{} {{'.format(name))
    cg.indent()


def _gen_end_block(cg):
    cg.unindent()
    cg.add_line('};')
    cg.add_empty_line()


def _gen_trace_block(meta, cg):
    trace = meta.trace

    _gen_start_block('trace', cg)
    cg.add_line('major = 1;')
    cg.add_line('minor = 8;')
    line = 'byte_order = {};'.format(_bo_to_string(trace.byte_order))
    cg.add_line(line)

    if trace.uuid is not None:
        line = 'uuid = "{}";'.format(trace.uuid)
        cg.add_line(line)

    if trace.packet_header_type is not None:
        _gen_entity('packet.header', trace.packet_header_type, cg)

    _gen_end_block(cg)


def _escape_literal_string(s):
    esc = s.replace('\\', '\\\\')
    esc = esc.replace('\n', '\\n')
    esc = esc.replace('\r', '\\r')
    esc = esc.replace('\t', '\\t')
    esc = esc.replace('"', '\\"')

    return esc


def _gen_env_block(meta, cg):
    env = meta.env

    if not env:
        return

    _gen_start_block('env', cg)

    for name, value in env.items():
        if type(value) is int:
            value_string = str(value)
        else:
            value_string = '"{}"'.format(_escape_literal_string(value))

        cg.add_line('{} = {};'.format(name, value_string))

    _gen_end_block(cg)


def _gen_clock_block(clock, cg):
    _gen_start_block('clock', cg)
    cg.add_line('name = {};'.format(clock.name))

    if clock.description is not None:
        desc = _escape_literal_string(clock.description)
        cg.add_line('description = "{}";'.format(desc))

    if clock.uuid is not None:
        cg.add_line('uuid = "{}";'.format(clock.uuid))

    cg.add_line('freq = {};'.format(clock.freq))
    cg.add_line('offset_s = {};'.format(clock.offset_seconds))
    cg.add_line('offset = {};'.format(clock.offset_cycles))
    cg.add_line('precision = {};'.format(clock.error_cycles))
    cg.add_line('absolute = {};'.format(_bool_to_string(clock.absolute)))
    _gen_end_block(cg)


def _gen_clock_blocks(meta, cg):
    clocks = meta.clocks

    for clock in clocks.values():
        _gen_clock_block(clock, cg)


def _gen_stream_block(meta, stream, cg):
    cg.add_cc_line(stream.name.replace('/', ''))
    _gen_start_block('stream', cg)

    if meta.trace.packet_header_type is not None:
        if 'stream_id' in meta.trace.packet_header_type.fields:
            cg.add_line('id = {};'.format(stream.id))

    if stream.packet_context_type is not None:
        _gen_entity('packet.context', stream.packet_context_type, cg)

    if stream.event_header_type is not None:
        _gen_entity('event.header', stream.event_header_type, cg)

    if stream.event_context_type is not None:
        _gen_entity('event.context', stream.event_context_type, cg)

    _gen_end_block(cg)


def _gen_event_block(meta, stream, ev, cg):
    _gen_start_block('event', cg)
    cg.add_line('name = "{}";'.format(ev.name))
    cg.add_line('id = {};'.format(ev.id))

    if meta.trace.packet_header_type is not None:
        if 'stream_id' in meta.trace.packet_header_type.fields:
            cg.add_line('stream_id = {};'.format(stream.id))

    cg.append_cc_to_last_line(stream.name.replace('/', ''))

    if ev.log_level is not None:
        add_fmt = ''

        if ev.log_level.name is not None:
            name = ev.log_level.name.replace('*/', '')
            add_fmt = ' /* {} */'.format(name)

        fmt = 'loglevel = {};' + add_fmt
        cg.add_line(fmt.format(ev.log_level.value))

    if ev.context_type is not None:
        _gen_entity('context', ev.context_type, cg)

    if ev.payload_type is not None:
        _gen_entity('fields', ev.payload_type, cg)
    else:
        fake_payload = metadata.Struct()
        fake_payload.min_align = 8
        _gen_entity('fields', fake_payload, cg)

    _gen_end_block(cg)


def _gen_streams_events_blocks(meta, cg):
    for stream in meta.streams.values():
        _gen_stream_block(meta, stream, cg)

        for ev in stream.events.values():
            _gen_event_block(meta, stream, ev, cg)


def from_metadata(meta):
    cg = codegen.CodeGenerator('\t')

    # version/magic
    cg.add_line('/* CTF 1.8 */')
    cg.add_empty_line()
    cg.add_line('''/*
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
 *''')
    v = barectf.__version__
    line = ' * The following TSDL code was generated by barectf v{}'.format(v)
    cg.add_line(line)
    now = datetime.datetime.now()
    line = ' * on {}.'.format(now)
    cg.add_line(line)
    cg.add_line(' *')
    cg.add_line(' * For more details, see <http://barectf.org>.')
    cg.add_line(' */')
    cg.add_empty_line()

    # trace block
    _gen_trace_block(meta, cg)

    # environment
    _gen_env_block(meta, cg)

    # clocks
    _gen_clock_blocks(meta, cg)

    # streams and contained events
    _gen_streams_events_blocks(meta, cg)

    return cg.code
