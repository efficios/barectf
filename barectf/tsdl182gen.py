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

import barectf.codegen as barectf_codegen
import barectf.version as barectf_version
import barectf.config as barectf_config


def _bool_to_string(b):
    return 'true' if b else 'false'


_byte_order_to_string_map = {
    barectf_config.ByteOrder.LITTLE_ENDIAN: 'le',
    barectf_config.ByteOrder.BIG_ENDIAN: 'be',
}


def _byte_order_to_string(byte_order):
    return _byte_order_to_string_map[byte_order]


_display_base_to_int_map = {
    barectf_config.DisplayBase.BINARY: 2,
    barectf_config.DisplayBase.OCTAL: 8,
    barectf_config.DisplayBase.DECIMAL: 10,
    barectf_config.DisplayBase.HEXADECIMAL: 16,
}


def _display_base_to_int(disp_base):
    return _display_base_to_int_map[disp_base]


def _gen_int_ft(ft, cg):
    cg.add_line('integer {')
    cg.indent()
    cg.add_line(f'size = {ft.size};')
    cg.add_line(f'align = {ft.alignment};')
    is_signed = isinstance(ft, barectf_config.SignedIntegerFieldType)
    cg.add_line(f'signed = {_bool_to_string(is_signed)};')
    cg.add_line(f'byte_order = {_byte_order_to_string(ft.byte_order)};')
    cg.add_line(f'base = {_display_base_to_int(ft.preferred_display_base)};')

    if isinstance(ft, barectf_config.UnsignedIntegerFieldType) and ft._mapped_clk_type_name is not None:
        cg.add_line(f'map = clock.{ft._mapped_clk_type_name}.value;')

    cg.unindent()
    cg.add_line('}')


def _gen_enum_ft(ft, cg):
    cg.add_line('enum : ')
    cg.add_glue()
    _gen_int_ft(ft, cg)
    cg.append_to_last_line(' {')
    cg.indent()

    for label, mapping in ft.mappings.items():
        for rg in mapping.ranges:
            if rg.lower == rg.upper:
                rg_str = str(rg.lower)
            else:
                rg_str = f'{rg.lower} ... {rg.upper}'

        line = f'"{label}" = {rg_str},'
        cg.add_line(line)

    cg.unindent()
    cg.add_line('}')


def _gen_real_ft(ft, cg):
    cg.add_line('floating_point {')
    cg.indent()

    if ft.size == 32:
        exp_dig = 8
        mant_dig = 24
    else:
        assert ft.size == 64
        exp_dig = 11
        mant_dig = 53

    cg.add_line(f'exp_dig = {exp_dig};')
    cg.add_line(f'mant_dig = {mant_dig};')
    cg.add_line(f'align = {ft.alignment};')
    cg.add_line(f'byte_order = {_byte_order_to_string(ft.byte_order)};')
    cg.unindent()
    cg.add_line('}')


def _gen_string_ft(ft, cg):
    cg.add_line('string {')
    cg.indent()
    cg.add_line('encoding = UTF8;')
    cg.unindent()
    cg.add_line('}')


def _find_deepest_array_ft_element_ft(ft):
    if isinstance(ft, barectf_config._ArrayFieldType):
        return _find_deepest_array_ft_element_ft(ft.element_field_type)

    return ft


def _static_array_ft_lengths(ft, lengths):
    if type(ft) is barectf_config.StaticArrayFieldType:
        lengths.append(ft.length)
        _static_array_ft_lengths(ft.element_field_type, lengths)


def _gen_struct_ft_entry(name, ft, cg):
    elem_ft = _find_deepest_array_ft_element_ft(ft)
    _gen_ft(elem_ft, cg)
    cg.append_to_last_line(f' {name}')

    # array
    lengths = []
    _static_array_ft_lengths(ft, lengths)

    if lengths:
        for length in reversed(lengths):
            cg.append_to_last_line(f'[{length}]')

    cg.append_to_last_line(';')


def _gen_struct_ft(ft, cg):
    cg.add_line('struct {')
    cg.indent()

    for name, member in ft.members.items():
        _gen_struct_ft_entry(name, member.field_type, cg)

    cg.unindent()

    if len(ft.members) == 0:
        cg.add_glue()

    cg.add_line(f'}} align({ft.minimum_alignment})')


_ft_to_gen_ft_func = {
    barectf_config.UnsignedIntegerFieldType: _gen_int_ft,
    barectf_config.SignedIntegerFieldType: _gen_int_ft,
    barectf_config.UnsignedEnumerationFieldType: _gen_enum_ft,
    barectf_config.SignedEnumerationFieldType: _gen_enum_ft,
    barectf_config.RealFieldType: _gen_real_ft,
    barectf_config.StringFieldType: _gen_string_ft,
    barectf_config.StructureFieldType: _gen_struct_ft,
}


def _gen_ft(ft, cg):
    _ft_to_gen_ft_func[type(ft)](ft, cg)


def _gen_root_ft(name, ft, cg):
    cg.add_line('{} := '.format(name))
    cg.add_glue()
    _gen_ft(ft, cg)
    cg.append_to_last_line(';')


def _try_gen_root_ft(name, ft, cg):
    if ft is None:
        return

    _gen_root_ft(name, ft, cg)


def _gen_start_block(name, cg):
    cg.add_line(f'{name} {{')
    cg.indent()


def _gen_end_block(cg):
    cg.unindent()
    cg.add_line('};')
    cg.add_empty_line()


def _gen_trace_type_block(config, cg):
    trace_type = config.trace.type
    _gen_start_block('trace', cg)
    cg.add_line('major = 1;')
    cg.add_line('minor = 8;')
    default_byte_order = trace_type.default_byte_order

    if default_byte_order is None:
        default_byte_order = barectf_config.ByteOrder.LITTLE_ENDIAN

    cg.add_line(f'byte_order = {_byte_order_to_string(default_byte_order)};')

    if trace_type.uuid is not None:
        cg.add_line(f'uuid = "{trace_type.uuid}";')

    _try_gen_root_ft('packet.header', trace_type._pkt_header_ft, cg)
    _gen_end_block(cg)


def _escape_literal_string(s):
    esc = s.replace('\\', '\\\\')
    esc = esc.replace('\n', '\\n')
    esc = esc.replace('\r', '\\r')
    esc = esc.replace('\t', '\\t')
    esc = esc.replace('"', '\\"')
    return esc


def _gen_trace_env_block(config, cg):
    env = config.trace.environment
    assert env is not None
    _gen_start_block('env', cg)

    for name, value in env.items():
        if type(value) is int:
            value_string = str(value)
        else:
            value_string = f'"{_escape_literal_string(value)}"'

        cg.add_line(f'{name} = {value_string};')

    _gen_end_block(cg)


def _gen_clk_type_block(clk_type, cg):
    _gen_start_block('clock', cg)
    cg.add_line(f'name = {clk_type.name};')

    if clk_type.description is not None:
        cg.add_line(f'description = "{_escape_literal_string(clk_type.description)}";')

    if clk_type.uuid is not None:
        cg.add_line(f'uuid = "{clk_type.uuid}";')

    cg.add_line(f'freq = {clk_type.frequency};')
    cg.add_line(f'offset_s = {clk_type.offset.seconds};')
    cg.add_line(f'offset = {clk_type.offset.cycles};')
    cg.add_line(f'precision = {clk_type.precision};')
    cg.add_line(f'absolute = {_bool_to_string(clk_type.origin_is_unix_epoch)};')
    _gen_end_block(cg)


def _gen_clk_type_blocks(config, cg):
    for stream_type in sorted(config.trace.type.stream_types):
        if stream_type.default_clock_type is not None:
            _gen_clk_type_block(stream_type.default_clock_type, cg)


def _gen_stream_type_block(config, stream_type, cg):
    cg.add_cc_line(stream_type.name.replace('/', ''))
    _gen_start_block('stream', cg)

    if config.trace.type.features.stream_type_id_field_type is not None:
        cg.add_line(f'id = {stream_type.id};')

    _try_gen_root_ft('packet.context', stream_type._pkt_ctx_ft, cg)
    _try_gen_root_ft('event.header', stream_type._ev_header_ft, cg)
    _try_gen_root_ft('event.context', stream_type.event_common_context_field_type, cg)
    _gen_end_block(cg)


def _gen_ev_type_block(config, stream_type, ev_type, cg):
    _gen_start_block('event', cg)
    cg.add_line(f'name = "{ev_type.name}";')

    if stream_type.features.event_features.type_id_field_type is not None:
        cg.add_line(f'id = {ev_type.id};')

    if config.trace.type.features.stream_type_id_field_type is not None:
        cg.add_line(f'stream_id = {stream_type.id};')
        cg.append_cc_to_last_line(f'Stream type `{stream_type.name.replace("/", "")}`')

    if ev_type.log_level is not None:
        cg.add_line(f'loglevel = {ev_type.log_level};')

    _try_gen_root_ft('context', ev_type.specific_context_field_type, cg)
    payload_ft = ev_type.payload_field_type

    if payload_ft is None:
        payload_ft = barectf_config.StructureFieldType(8)

    _try_gen_root_ft('fields', ev_type.payload_field_type, cg)
    _gen_end_block(cg)


def _gen_stream_type_ev_type_blocks(config, cg):
    for stream_type in sorted(config.trace.type.stream_types):
        _gen_stream_type_block(config, stream_type, cg)

        for ev_type in sorted(stream_type.event_types):
            _gen_ev_type_block(config, stream_type, ev_type, cg)


def _from_config(config):
    cg = barectf_codegen._CodeGenerator('\t')

    # version/magic
    cg.add_line('/* CTF 1.8 */')
    cg.add_empty_line()
    cg.add_line('''/*
 * The MIT License (MIT)
 *
 * Copyright (c) 2015-2020 Philippe Proulx <pproulx@efficios.com>
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
    cg.add_line(f' * The following TSDL code was generated by barectf v{barectf_version.__version__}')
    cg.add_line(f' * on {config.trace.environment["barectf_gen_date"]}.')
    cg.add_line(' *')
    cg.add_line(' * For more details, see <https://barectf.org/>.')
    cg.add_line(' */')
    cg.add_empty_line()

    # trace type block
    _gen_trace_type_block(config, cg)

    # trace environment block
    _gen_trace_env_block(config, cg)

    # clock type blocks
    _gen_clk_type_blocks(config, cg)

    # stream and type blocks
    _gen_stream_type_ev_type_blocks(config, cg)

    return cg.code
