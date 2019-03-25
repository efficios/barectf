# The MIT License (MIT)
#
# Copyright (c) 2014-2019 Philippe Proulx <pproulx@efficios.com>
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

from barectf import templates
from barectf import metadata
import barectf.codegen
import collections
import itertools
import argparse
import datetime
import barectf
import copy
import sys
import os
import re


def _align(v, align):
    return (v + (align - 1)) & -align


class _SerializationAction:
    def __init__(self, offset_in_byte, type, names):
        assert(offset_in_byte >= 0 and offset_in_byte < 8)
        self._offset_in_byte = offset_in_byte
        self._type = type
        self._names = copy.deepcopy(names)

    @property
    def offset_in_byte(self):
        return self._offset_in_byte

    @property
    def type(self):
        return self._type

    @property
    def names(self):
        return self._names


class _AlignSerializationAction(_SerializationAction):
    def __init__(self, offset_in_byte, type, names, value):
        super().__init__(offset_in_byte, type, names)
        self._value = value

    @property
    def value(self):
        return self._value


class _SerializeSerializationAction(_SerializationAction):
    def __init__(self, offset_in_byte, type, names):
        super().__init__(offset_in_byte, type, names)


class _SerializationActions:
    def __init__(self):
        self.reset()

    def reset(self):
        self._last_alignment = None
        self._last_bit_array_size = None
        self._actions = []
        self._names = []
        self._offset_in_byte = 0

    def append_root_scope_type(self, t, name):
        if t is None:
            return

        assert(type(t) is metadata.Struct)
        self._names = [name]
        self._append_type(t)

    @property
    def actions(self):
        return self._actions

    def align(self, alignment):
        do_align = self._must_align(alignment)
        self._last_alignment = alignment
        self._last_bit_array_size = alignment
        self._try_append_align_action(alignment, do_align)

    def _must_align(self, align_req):
        return self._last_alignment != align_req or self._last_bit_array_size % align_req != 0

    def _append_type(self, t):
        assert(type(t) in (metadata.Struct, metadata.String, metadata.Integer,
                           metadata.FloatingPoint, metadata.Enum,
                           metadata.Array))

        if type(t) in (metadata.String, metadata.Array):
            assert(type(t) is metadata.String or self._names[-1] == 'uuid')
            do_align = self._must_align(8)
            self._last_alignment = 8
            self._last_bit_array_size = 8
            self._try_append_align_action(8, do_align, t)
            self._append_serialize_action(t)
        elif type(t) in (metadata.Integer, metadata.FloatingPoint,
                         metadata.Enum, metadata.Struct):
            do_align = self._must_align(t.align)
            self._last_alignment = t.align

            if type(t) is metadata.Struct:
                self._last_bit_array_size = t.align
            else:
                self._last_bit_array_size = t.size

            self._try_append_align_action(t.align, do_align, t)

            if type(t) is metadata.Struct:
                for field_name, field_type in t.fields.items():
                    self._names.append(field_name)
                    self._append_type(field_type)
                    del self._names[-1]
            else:
                self._append_serialize_action(t, t.size)

    def _try_append_align_action(self, alignment, do_align, t=None):
        offset_in_byte = self._offset_in_byte
        self._offset_in_byte = _align(self._offset_in_byte, alignment) % 8

        if do_align and alignment > 1:
            self._actions.append(_AlignSerializationAction(offset_in_byte,
                                                           t, self._names,
                                                           alignment))

    def _append_serialize_action(self, t, size=None):
        assert(type(t) in (metadata.Integer, metadata.FloatingPoint,
                           metadata.Enum, metadata.String,
                           metadata.Array))

        offset_in_byte = self._offset_in_byte

        if t.size is not None:
            self._offset_in_byte += t.size
            self._offset_in_byte %= 8

        self._actions.append(_SerializeSerializationAction(offset_in_byte,
                                                           t, self._names))


_PREFIX_TPH = 'tph_'
_PREFIX_SPC = 'spc_'
_PREFIX_SEH = 'seh_'
_PREFIX_SEC = 'sec_'
_PREFIX_EC = 'ec_'
_PREFIX_EP = 'ep_'
_PREFIX_TO_NAME = {
    _PREFIX_TPH: 'trace packet header',
    _PREFIX_SPC: 'stream packet context',
    _PREFIX_SEH: 'stream event header',
    _PREFIX_SEC: 'stream event context',
    _PREFIX_EC: 'event context',
    _PREFIX_EP: 'event payload',
}


class CCodeGenerator:
    def __init__(self, cfg):
        self._cfg = cfg
        self._cg = barectf.codegen.CodeGenerator('\t')
        self._type_to_get_ctype_func = {
            metadata.Integer: self._get_int_ctype,
            metadata.FloatingPoint: self._get_float_ctype,
            metadata.Enum: self._get_enum_ctype,
            metadata.String: self._get_string_ctype,
        }
        self._type_to_generate_serialize_func = {
            metadata.Integer: self._generate_serialize_int,
            metadata.FloatingPoint: self._generate_serialize_float,
            metadata.Enum: self._generate_serialize_enum,
            metadata.String: self._generate_serialize_string,
        }
        self._saved_serialization_actions = {}

    def _get_stream_clock(self, stream):
        field = None

        if stream.event_header_type is not None:
            if 'timestamp' in stream.event_header_type.fields:
                field = stream.event_header_type['timestamp']

        if stream.packet_context_type is not None:
            if field is None and 'timestamp_begin' in stream.packet_context_type.fields:
                field = stream.packet_context_type['timestamp_begin']

            if field is None and 'timestamp_end' in stream.packet_context_type.fields:
                field = stream.packet_context_type['timestamp_end']

        if field is None:
            return

        if field.property_mappings:
            return field.property_mappings[0].object

    def _generate_ctx_parent(self):
        tmpl = templates._CTX_PARENT
        self._cg.add_lines(tmpl.format(prefix=self._cfg.prefix))

    def _generate_ctx(self, stream):
        tmpl = templates._CTX_BEGIN
        self._cg.add_lines(tmpl.format(prefix=self._cfg.prefix,
                                       sname=stream.name))
        tmpl = 'uint32_t off_tph_{fname};'
        self._cg.indent()
        trace_packet_header_type = self._cfg.metadata.trace.packet_header_type

        if trace_packet_header_type is not None:
            for field_name in trace_packet_header_type.fields:
                self._cg.add_lines(tmpl.format(fname=field_name))

        tmpl = 'uint32_t off_spc_{fname};'

        if stream.packet_context_type is not None:
            for field_name in stream.packet_context_type.fields:
                self._cg.add_lines(tmpl.format(fname=field_name))

        clock = self._get_stream_clock(stream)

        if clock is not None:
            line = '{} cur_last_event_ts;'.format(clock.return_ctype)
            self._cg.add_line(line)

        self._cg.unindent()
        tmpl = templates._CTX_END
        self._cg.add_lines(tmpl)

    def _generate_ctxs(self):
        for stream in self._cfg.metadata.streams.values():
            self._generate_ctx(stream)

    def _generate_clock_cb(self, clock):
        tmpl = templates._CLOCK_CB
        self._cg.add_lines(tmpl.format(return_ctype=clock.return_ctype,
                                       cname=clock.name))

    def _generate_clock_cbs(self):
        for clock in self._cfg.metadata.clocks.values():
            self._generate_clock_cb(clock)

    def _generate_platform_callbacks(self):
        tmpl = templates._PLATFORM_CALLBACKS_BEGIN
        self._cg.add_lines(tmpl.format(prefix=self._cfg.prefix))
        self._cg.indent()
        self._generate_clock_cbs()
        self._cg.unindent()
        tmpl = templates._PLATFORM_CALLBACKS_END
        self._cg.add_lines(tmpl)

    def generate_bitfield_header(self):
        self._cg.reset()
        tmpl = templates._BITFIELD
        tmpl = tmpl.replace('$prefix$', self._cfg.prefix)
        tmpl = tmpl.replace('$PREFIX$', self._cfg.prefix.upper())

        if self._cfg.metadata.trace.byte_order == metadata.ByteOrder.BE:
            endian_def = 'BIG_ENDIAN'
        else:
            endian_def = 'LITTLE_ENDIAN'

        tmpl = tmpl.replace('$ENDIAN_DEF$', endian_def)
        self._cg.add_lines(tmpl)

        return self._cg.code

    def _generate_func_init_proto(self):
        tmpl = templates._FUNC_INIT_PROTO
        self._cg.add_lines(tmpl.format(prefix=self._cfg.prefix))

    def _get_int_ctype(self, t):
        signed = 'u' if not t.signed else ''

        if t.size <= 8:
            sz = '8'
        elif t.size <= 16:
            sz = '16'
        elif t.size <= 32:
            sz = '32'
        elif t.size == 64:
            sz = '64'

        return '{}int{}_t'.format(signed, sz)

    def _get_float_ctype(self, t):
        if t.exp_size == 8 and t.mant_size == 24 and t.align == 32:
            ctype = 'float'
        elif t.exp_size == 11 and t.mant_size == 53 and t.align == 64:
            ctype = 'double'
        else:
            ctype = 'uint64_t'

        return ctype

    def _get_enum_ctype(self, t):
        return self._get_int_ctype(t.value_type)

    def _get_string_ctype(self, t):
        return 'const char *'

    def _get_type_ctype(self, t):
        return self._type_to_get_ctype_func[type(t)](t)

    def _generate_type_ctype(self, t):
        ctype = self._get_type_ctype(t)
        self._cg.append_to_last_line(ctype)

    def _generate_proto_param(self, t, name):
        self._generate_type_ctype(t)
        self._cg.append_to_last_line(' ')
        self._cg.append_to_last_line(name)

    def _generate_proto_params(self, t, name_prefix, exclude_list):
        self._cg.indent()

        for field_name, field_type in t.fields.items():
            if field_name in exclude_list:
                continue

            name = name_prefix + field_name
            self._cg.append_to_last_line(',')
            self._cg.add_line('')
            self._generate_proto_param(field_type, name)

        self._cg.unindent()

    def _generate_func_open_proto(self, stream):
        tmpl = templates._FUNC_OPEN_PROTO_BEGIN
        self._cg.add_lines(tmpl.format(prefix=self._cfg.prefix,
                                       sname=stream.name))
        trace_packet_header_type = self._cfg.metadata.trace.packet_header_type

        if trace_packet_header_type is not None:
            exclude_list = ['magic', 'stream_id', 'uuid']
            self._generate_proto_params(trace_packet_header_type, _PREFIX_TPH,
                                        exclude_list)

        if stream.packet_context_type is not None:
            exclude_list = [
                'timestamp_begin',
                'timestamp_end',
                'packet_size',
                'content_size',
                'events_discarded',
            ]
            self._generate_proto_params(stream.packet_context_type,
                                        _PREFIX_SPC, exclude_list)

        tmpl = templates._FUNC_OPEN_PROTO_END
        self._cg.add_lines(tmpl)

    def _generate_func_close_proto(self, stream):
        tmpl = templates._FUNC_CLOSE_PROTO
        self._cg.add_lines(tmpl.format(prefix=self._cfg.prefix,
                                       sname=stream.name))

    def _generate_func_trace_proto_params(self, stream, event):
        if stream.event_header_type is not None:
            exclude_list = [
                'id',
                'timestamp',
            ]
            self._generate_proto_params(stream.event_header_type,
                                        _PREFIX_SEH, exclude_list)

        if stream.event_context_type is not None:
            self._generate_proto_params(stream.event_context_type,
                                        _PREFIX_SEC, [])

        if event.context_type is not None:
            self._generate_proto_params(event.context_type,
                                        _PREFIX_EC, [])

        if event.payload_type is not None:
            self._generate_proto_params(event.payload_type,
                                        _PREFIX_EP, [])

    def _generate_func_trace_proto(self, stream, event):
        tmpl = templates._FUNC_TRACE_PROTO_BEGIN
        self._cg.add_lines(tmpl.format(prefix=self._cfg.prefix,
                                       sname=stream.name, evname=event.name))
        self._generate_func_trace_proto_params(stream, event)
        tmpl = templates._FUNC_TRACE_PROTO_END
        self._cg.add_lines(tmpl)

    def _punctuate_proto(self):
        self._cg.append_to_last_line(';')

    def generate_header(self):
        self._cg.reset()
        dt = datetime.datetime.now().isoformat()
        bh_filename = self.get_bitfield_header_filename()
        prefix_def = ''
        default_stream_def = ''

        if self._cfg.options.gen_prefix_def:
            prefix_def = '#define _BARECTF_PREFIX {}'.format(self._cfg.prefix)

        if self._cfg.options.gen_default_stream_def and self._cfg.metadata.default_stream_name is not None:
            default_stream_def = '#define _BARECTF_DEFAULT_STREAM {}'.format(self._cfg.metadata.default_stream_name)

        default_stream_trace_defs = ''
        default_stream_name = self._cfg.metadata.default_stream_name

        if default_stream_name is not None:
            default_stream = self._cfg.metadata.streams[default_stream_name]
            lines = []

            for ev_name in default_stream.events.keys():
                tmpl = templates._DEFINE_DEFAULT_STREAM_TRACE
                define = tmpl.format(prefix=self._cfg.prefix,
                                     sname=default_stream_name,
                                     evname=ev_name)
                lines.append(define)

            default_stream_trace_defs = '\n'.join(lines)

        tmpl = templates._HEADER_BEGIN
        self._cg.add_lines(tmpl.format(prefix=self._cfg.prefix,
                                       ucprefix=self._cfg.prefix.upper(),
                                       bitfield_header_filename=bh_filename,
                                       version=barectf.__version__, date=dt,
                                       prefix_def=prefix_def,
                                       default_stream_def=default_stream_def,
                                       default_stream_trace_defs=default_stream_trace_defs))
        self._cg.add_empty_line()

        # platform callbacks structure
        self._generate_platform_callbacks()
        self._cg.add_empty_line()

        # context parent
        self._generate_ctx_parent()
        self._cg.add_empty_line()

        # stream contexts
        self._generate_ctxs()
        self._cg.add_empty_line()

        # initialization function prototype
        self._generate_func_init_proto()
        self._punctuate_proto()
        self._cg.add_empty_line()

        for stream in self._cfg.metadata.streams.values():
            self._generate_func_open_proto(stream)
            self._punctuate_proto()
            self._cg.add_empty_line()
            self._generate_func_close_proto(stream)
            self._punctuate_proto()
            self._cg.add_empty_line()

            for ev in stream.events.values():
                self._generate_func_trace_proto(stream, ev)
                self._punctuate_proto()
                self._cg.add_empty_line()

        tmpl = templates._HEADER_END
        self._cg.add_lines(tmpl.format(ucprefix=self._cfg.prefix.upper()))

        return self._cg.code

    def _get_call_event_param_list_from_struct(self, t, prefix, exclude_list):
        lst = ''

        for field_name in t.fields:
            if field_name in exclude_list:
                continue

            lst += ', {}{}'.format(prefix, field_name)

        return lst

    def _get_call_event_param_list(self, stream, event):
        lst = ''
        gcp_func = self._get_call_event_param_list_from_struct

        if stream.event_header_type is not None:
            exclude_list = [
                'id',
                'timestamp',
            ]
            lst += gcp_func(stream.event_header_type, _PREFIX_SEH, exclude_list)

        if stream.event_context_type is not None:
            lst += gcp_func(stream.event_context_type, _PREFIX_SEC, [])

        if event.context_type is not None:
            lst += gcp_func(event.context_type, _PREFIX_EC, [])

        if event.payload_type is not None:
            lst += gcp_func(event.payload_type, _PREFIX_EP, [])

        return lst

    def _generate_align(self, at, align):
        self._cg.add_line('_ALIGN({}, {});'.format(at, align))

    def _generate_align_type(self, at, t):
        if t.align == 1:
            return

        self._generate_align(at, t.align)

    def _generate_incr_pos(self, var, value):
        self._cg.add_line('{} += {};'.format(var, value))

    def _generate_incr_pos_bytes(self, var, value):
        self._generate_incr_pos(var, '_BYTES_TO_BITS({})'.format(value))

    def _generate_func_get_event_size_proto(self, stream, event):
        tmpl = templates._FUNC_GET_EVENT_SIZE_PROTO_BEGIN
        self._cg.add_lines(tmpl.format(prefix=self._cfg.prefix,
                                       sname=stream.name, evname=event.name))
        self._generate_func_trace_proto_params(stream, event)
        tmpl = templates._FUNC_GET_EVENT_SIZE_PROTO_END
        self._cg.add_lines(tmpl)

    def _generate_func_get_event_size(self, stream, event):
        self._generate_func_get_event_size_proto(stream, event)
        tmpl = templates._FUNC_GET_EVENT_SIZE_BODY_BEGIN
        lines = tmpl.format(prefix=self._cfg.prefix)
        self._cg.add_lines(lines)
        self._cg.add_empty_line()
        self._cg.indent()
        ser_actions = _SerializationActions()
        ser_actions.append_root_scope_type(stream.event_header_type,
                                            _PREFIX_SEH)
        ser_actions.append_root_scope_type(stream.event_context_type,
                                            _PREFIX_SEC)
        ser_actions.append_root_scope_type(event.context_type, _PREFIX_EC)
        ser_actions.append_root_scope_type(event.payload_type, _PREFIX_EP)

        for action in ser_actions.actions:
            if type(action) is _AlignSerializationAction:
                if action.names:
                    if len(action.names) == 1:
                        line = 'align {} structure'.format(_PREFIX_TO_NAME[action.names[0]])
                    else:
                        fmt = 'align field "{}" ({})'
                        line = fmt.format(action.names[-1],
                                          _PREFIX_TO_NAME[action.names[0]])

                    self._cg.add_cc_line(line)

                self._generate_align('at', action.value)
                self._cg.add_empty_line()
            elif type(action) is _SerializeSerializationAction:
                assert(len(action.names) >= 2)
                fmt = 'add size of field "{}" ({})'
                line = fmt.format(action.names[-1], _PREFIX_TO_NAME[action.names[0]])
                self._cg.add_cc_line(line)

                if type(action.type) is metadata.String:
                    param = ''.join(action.names)
                    self._generate_incr_pos_bytes('at',
                                                  'strlen({}) + 1'.format(param))
                else:
                    self._generate_incr_pos('at', action.type.size)

                self._cg.add_empty_line()

        self._cg.unindent()
        tmpl = templates._FUNC_GET_EVENT_SIZE_BODY_END
        self._cg.add_lines(tmpl)

    def _generate_func_serialize_event_proto(self, stream, event):
        tmpl = templates._FUNC_SERIALIZE_EVENT_PROTO_BEGIN
        self._cg.add_lines(tmpl.format(prefix=self._cfg.prefix,
                                       sname=stream.name, evname=event.name))
        self._generate_func_trace_proto_params(stream, event)
        tmpl = templates._FUNC_SERIALIZE_EVENT_PROTO_END
        self._cg.add_lines(tmpl)

    def _generate_bitfield_write(self, ctype, var, ctx, action):
        ptr = '&{ctx}->buf[_BITS_TO_BYTES({ctx}->at)]'.format(ctx=ctx)
        start = action.offset_in_byte
        suffix = 'le' if action.type.byte_order is metadata.ByteOrder.LE else 'be'
        func = '{}bt_bitfield_write_{}'.format(self._cfg.prefix, suffix)
        call_fmt = '{func}({ptr}, uint8_t, {start}, {size}, {ctype}, ({ctype}) {var});'
        call = call_fmt.format(func=func, ptr=ptr, start=start,
                               size=action.type.size, ctype=ctype, var=var)
        self._cg.add_line(call)

    def _generate_serialize_int(self, var, ctx, action):
        ctype = self._get_int_ctype(action.type)
        self._generate_bitfield_write(ctype, var, ctx, action)
        self._generate_incr_pos('{}->at'.format(ctx), action.type.size)

    def _generate_serialize_float(self, var, ctx, action):
        ctype = self._get_type_ctype(action.type)
        flt_dbl = False

        if ctype == 'float' or ctype == 'double':
            flt_dbl = True

            if ctype == 'float':
                union_name = 'f2u'
                int_ctype = 'uint32_t'
            elif ctype == 'double':
                union_name = 'd2u'
                int_ctype = 'uint64_t'

            # union for reading the bytes of the floating point number
            self._cg.add_empty_line()
            self._cg.add_line('{')
            self._cg.indent()
            self._cg.add_line('union {name} {name};'.format(name=union_name))
            self._cg.add_empty_line()
            self._cg.add_line('{}.f = {};'.format(union_name, var))
            bf_var = '{}.u'.format(union_name)
        else:
            bf_var = '({}) {}'.format(ctype, var)
            int_ctype = ctype

        self._generate_bitfield_write(int_ctype, bf_var, ctx, action)

        if flt_dbl:
            self._cg.unindent()
            self._cg.add_line('}')
            self._cg.add_empty_line()

        self._generate_incr_pos('{}->at'.format(ctx), action.type.size)

    def _generate_serialize_enum(self, var, ctx, action):
        sub_action = _SerializeSerializationAction(action.offset_in_byte,
                                                   action.type.value_type,
                                                   action.names)
        self._generate_serialize_from_action(var, ctx, sub_action)

    def _generate_serialize_string(self, var, ctx, action):
        tmpl = '_write_cstring({}, {});'.format(ctx, var)
        self._cg.add_lines(tmpl)

    def _generate_serialize_from_action(self, var, ctx, action):
        func = self._type_to_generate_serialize_func[type(action.type)]
        func(var, ctx, action)

    def _generate_serialize_statements_from_actions(self, prefix, action_iter,
                                                    spec_src=None):
        for action in action_iter:
            if type(action) is _AlignSerializationAction:
                if action.names:
                    if len(action.names) == 1:
                        line = 'align {} structure'.format(_PREFIX_TO_NAME[action.names[0]])
                    else:
                        fmt = 'align field "{}" ({})'
                        line = fmt.format(action.names[-1],
                                          _PREFIX_TO_NAME[action.names[0]])

                    self._cg.add_cc_line(line)

                self._generate_align('ctx->at', action.value)
                self._cg.add_empty_line()
            elif type(action) is _SerializeSerializationAction:
                assert(len(action.names) >= 2)
                fmt = 'serialize field "{}" ({})'
                line = fmt.format(action.names[-1],
                                  _PREFIX_TO_NAME[action.names[0]])
                self._cg.add_cc_line(line)
                field_name = action.names[-1]
                src = prefix + field_name

                if spec_src is not None and field_name in spec_src:
                    src = spec_src[field_name]

                self._generate_serialize_from_action(src, 'ctx', action)
                self._cg.add_empty_line()

    def _generate_func_serialize_event(self, stream, event, orig_ser_actions):
        self._generate_func_serialize_event_proto(stream, event)
        tmpl = templates._FUNC_SERIALIZE_EVENT_BODY_BEGIN
        lines = tmpl.format(prefix=self._cfg.prefix)
        self._cg.add_lines(lines)
        self._cg.indent()
        self._cg.add_empty_line()

        if stream.event_header_type is not None:
            t = stream.event_header_type
            exclude_list = ['timestamp', 'id']
            params = self._get_call_event_param_list_from_struct(t, _PREFIX_SEH,
                                                                 exclude_list)
            tmpl = '_serialize_stream_event_header_{sname}(ctx, {evid}{params});'
            self._cg.add_cc_line('stream event header')
            self._cg.add_line(tmpl.format(sname=stream.name, evid=event.id,
                                          params=params))
            self._cg.add_empty_line()

        if stream.event_context_type is not None:
            t = stream.event_context_type
            params = self._get_call_event_param_list_from_struct(t, _PREFIX_SEC,
                                                                 [])
            tmpl = '_serialize_stream_event_context_{sname}(ctx{params});'
            self._cg.add_cc_line('stream event context')
            self._cg.add_line(tmpl.format(sname=stream.name, params=params))
            self._cg.add_empty_line()

        if event.context_type is not None or event.payload_type is not None:
            ser_actions = copy.deepcopy(orig_ser_actions)

        if event.context_type is not None:
            ser_action_index = len(ser_actions.actions)
            ser_actions.append_root_scope_type(event.context_type, _PREFIX_EC)
            ser_action_iter = itertools.islice(ser_actions.actions,
                                               ser_action_index, None)
            self._generate_serialize_statements_from_actions(_PREFIX_EC,
                                                             ser_action_iter)

        if event.payload_type is not None:
            ser_action_index = len(ser_actions.actions)
            ser_actions.append_root_scope_type(event.payload_type, _PREFIX_EP)
            ser_action_iter = itertools.islice(ser_actions.actions,
                                               ser_action_index, None)
            self._generate_serialize_statements_from_actions(_PREFIX_EP,
                                                             ser_action_iter)

        self._cg.unindent()
        tmpl = templates._FUNC_SERIALIZE_EVENT_BODY_END
        self._cg.add_lines(tmpl)

    def _generate_func_serialize_stream_event_header_proto(self, stream):
        tmpl = templates._FUNC_SERIALIZE_STREAM_EVENT_HEADER_PROTO_BEGIN
        clock_ctype = 'const int'
        self._cg.add_lines(tmpl.format(prefix=self._cfg.prefix,
                                       sname=stream.name))

        if stream.event_header_type is not None:
            exclude_list = [
                'id',
                'timestamp',
            ]
            self._generate_proto_params(stream.event_header_type,
                                        _PREFIX_SEH, exclude_list)

        tmpl = templates._FUNC_SERIALIZE_STREAM_EVENT_HEADER_PROTO_END
        self._cg.add_lines(tmpl)

    def _generate_func_serialize_stream_event_context_proto(self, stream):
        tmpl = templates._FUNC_SERIALIZE_STREAM_EVENT_CONTEXT_PROTO_BEGIN
        self._cg.add_lines(tmpl.format(prefix=self._cfg.prefix,
                                       sname=stream.name))

        if stream.event_context_type is not None:
            self._generate_proto_params(stream.event_context_type,
                                        _PREFIX_SEC, [])

        tmpl = templates._FUNC_SERIALIZE_STREAM_EVENT_CONTEXT_PROTO_END
        self._cg.add_lines(tmpl)

    def _generate_func_serialize_stream_event_header(self, stream,
                                                     ser_action_iter):
        self._generate_func_serialize_stream_event_header_proto(stream)
        tmpl = templates._FUNC_SERIALIZE_STREAM_EVENT_HEADER_BODY_BEGIN
        lines = tmpl.format(prefix=self._cfg.prefix, sname=stream.name)
        self._cg.add_lines(lines)
        self._cg.indent()
        clock = self._get_stream_clock(stream)

        if clock is not None:
            tmpl = 'struct {prefix}{sname}_ctx *s_ctx = FROM_VOID_PTR(struct {prefix}{sname}_ctx, vctx);'
            line = tmpl.format(prefix=self._cfg.prefix,
                               sname=stream.name)
            self._cg.add_line(line)
            tmpl = 'const {} ts = s_ctx->cur_last_event_ts;'
            line = tmpl.format(clock.return_ctype)
            self._cg.add_line(line)

        self._cg.add_empty_line()

        if stream.event_header_type is not None:
            spec_src = {}

            if 'id' in stream.event_header_type.fields:
                id_t = stream.event_header_type.fields['id']
                id_t_ctype = self._get_int_ctype(id_t)
                spec_src['id'] = '({}) event_id'.format(id_t_ctype)

            if 'timestamp' in stream.event_header_type.fields:
                field = stream.event_header_type.fields['timestamp']
                ts_ctype = self._get_int_ctype(field)
                spec_src['timestamp'] = '({}) ts'.format(ts_ctype)

            self._generate_serialize_statements_from_actions(_PREFIX_SEH,
                                                             ser_action_iter,
                                                             spec_src)

        self._cg.unindent()
        tmpl = templates._FUNC_SERIALIZE_STREAM_EVENT_HEADER_BODY_END
        self._cg.add_lines(tmpl)

    def _generate_func_serialize_stream_event_context(self, stream,
                                                      ser_action_iter):
        self._generate_func_serialize_stream_event_context_proto(stream)
        tmpl = templates._FUNC_SERIALIZE_STREAM_EVENT_CONTEXT_BODY_BEGIN
        lines = tmpl.format(prefix=self._cfg.prefix)
        self._cg.add_lines(lines)
        self._cg.indent()

        if stream.event_context_type is not None:
            self._generate_serialize_statements_from_actions(_PREFIX_SEC,
                                                             ser_action_iter)

        self._cg.unindent()
        tmpl = templates._FUNC_SERIALIZE_STREAM_EVENT_CONTEXT_BODY_END
        self._cg.add_lines(tmpl)

    def _generate_func_trace(self, stream, event):
        self._generate_func_trace_proto(stream, event)
        params = self._get_call_event_param_list(stream, event)
        clock = self._get_stream_clock(stream)

        if clock is not None:
            tmpl = 'ctx->cur_last_event_ts = ctx->parent.cbs.{}_clock_get_value(ctx->parent.data);'
            save_ts_line = tmpl.format(clock.name)
        else:
            save_ts_line = '/* (no clock) */'

        tmpl = templates._FUNC_TRACE_BODY
        self._cg.add_lines(tmpl.format(sname=stream.name, evname=event.name,
                                       params=params, save_ts=save_ts_line))

    def _generate_func_init(self):
        self._generate_func_init_proto()
        tmpl = templates._FUNC_INIT_BODY
        self._cg.add_lines(tmpl.format(prefix=self._cfg.prefix))

    def _generate_field_name_cc_line(self, field_name):
        self._cg.add_cc_line('"{}" field'.format(field_name))

    def _save_serialization_action(self, name, action):
        self._saved_serialization_actions[name] = action

    def _get_open_close_ts_line(self, stream):
        clock = self._get_stream_clock(stream)

        if clock is None:
            return ''

        tmpl = '\tconst {} ts = ctx->parent.use_cur_last_event_ts ? ctx->cur_last_event_ts : ctx->parent.cbs.{}_clock_get_value(ctx->parent.data);'
        line = tmpl.format(clock.return_ctype, clock.name)
        return line

    def _generate_func_open(self, stream):
        def generate_save_offset(name, action):
            tmpl = 'ctx->off_spc_{} = ctx->parent.at;'.format(name)
            self._cg.add_line(tmpl)
            self._save_serialization_action(name, action)

        self._generate_func_open_proto(stream)
        tmpl = templates._FUNC_OPEN_BODY_BEGIN
        spc_type = stream.packet_context_type
        ts_line = self._get_open_close_ts_line(stream)
        lines = tmpl.format(ts=ts_line)
        self._cg.add_lines(lines)
        self._cg.indent()
        self._cg.add_cc_line('do not open a packet that is already open')
        self._cg.add_line('if (ctx->parent.packet_is_open) {')
        self._cg.indent()
        self._cg.add_line('ctx->parent.in_tracing_section = saved_in_tracing_section;')
        self._cg.add_line('return;')
        self._cg.unindent()
        self._cg.add_line('}')
        self._cg.add_empty_line()
        self._cg.add_line('ctx->parent.at = 0;')
        tph_type = self._cfg.metadata.trace.packet_header_type
        ser_actions = _SerializationActions()

        if tph_type is not None:
            self._cg.add_empty_line()
            self._cg.add_cc_line('trace packet header')
            self._cg.add_line('{')
            self._cg.indent()
            ser_actions.append_root_scope_type(tph_type, _PREFIX_TPH)

            for action in ser_actions.actions:
                if type(action) is _AlignSerializationAction:
                    if action.names:
                        if len(action.names) == 1:
                            line = 'align trace packet header structure'
                        else:
                            line = 'align field "{}"'.format(action.names[-1])

                        self._cg.add_cc_line(line)

                    self._generate_align('ctx->parent.at', action.value)
                    self._cg.add_empty_line()
                elif type(action) is _SerializeSerializationAction:
                    assert(len(action.names) >= 2)
                    fmt = 'serialize field "{}"'
                    line = fmt.format(action.names[-1])
                    self._cg.add_cc_line(line)
                    field_name = action.names[-1]
                    src = _PREFIX_TPH + field_name

                    if field_name == 'magic':
                        src = '0xc1fc1fc1UL'
                    elif field_name == 'stream_id':
                        stream_id_ctype = self._get_int_ctype(action.type)
                        src = '({}) {}'.format(stream_id_ctype, stream.id)
                    elif field_name == 'uuid':
                        self._cg.add_line('{')
                        self._cg.indent()
                        self._cg.add_line('static uint8_t uuid[] = {')
                        self._cg.indent()

                        for b in self._cfg.metadata.trace.uuid.bytes:
                            self._cg.add_line('{},'.format(b))

                        self._cg.unindent()
                        self._cg.add_line('};')
                        self._cg.add_empty_line()
                        self._generate_align('ctx->parent.at', 8)
                        line = 'memcpy(&ctx->parent.buf[_BITS_TO_BYTES(ctx->parent.at)], uuid, 16);'
                        self._cg.add_line(line)
                        self._generate_incr_pos_bytes('ctx->parent.at', 16)
                        self._cg.unindent()
                        self._cg.add_line('}')
                        self._cg.add_empty_line()
                        continue

                    self._generate_serialize_from_action(src, '(&ctx->parent)', action)
                    self._cg.add_empty_line()

            self._cg.unindent()
            self._cg.add_lines('}')

        spc_action_index = len(ser_actions.actions)

        if spc_type is not None:
            self._cg.add_empty_line()
            self._cg.add_cc_line('stream packet context')
            self._cg.add_line('{')
            self._cg.indent()
            ser_actions.append_root_scope_type(spc_type, _PREFIX_SPC)
            tmpl_off = 'off_spc_{fname}'

            for action in itertools.islice(ser_actions.actions, spc_action_index, None):
                if type(action) is _AlignSerializationAction:
                    if action.names:
                        if len(action.names) == 1:
                            line = 'align stream packet context structure'
                        else:
                            line = 'align field "{}"'.format(action.names[-1])

                        self._cg.add_cc_line(line)

                    self._generate_align('ctx->parent.at', action.value)
                    self._cg.add_empty_line()
                elif type(action) is _SerializeSerializationAction:
                    assert(len(action.names) >= 2)
                    fmt = 'serialize field "{}"'
                    line = fmt.format(action.names[-1])
                    self._cg.add_cc_line(line)
                    field_name = action.names[-1]
                    src = _PREFIX_SPC + field_name
                    skip_int = False

                    if field_name == 'timestamp_begin':
                        ctype = self._get_type_ctype(action.type)
                        src = '({}) ts'.format(ctype)
                    elif field_name in ['timestamp_end', 'content_size',
                                        'events_discarded']:
                        skip_int = True
                    elif field_name == 'packet_size':
                        ctype = self._get_type_ctype(action.type)
                        src = '({}) ctx->parent.packet_size'.format(ctype)

                    if skip_int:
                        generate_save_offset(field_name, action)
                        self._generate_incr_pos('ctx->parent.at',
                                                action.type.size)
                    else:
                        self._generate_serialize_from_action(src, '(&ctx->parent)',
                                                      action)

                    self._cg.add_empty_line()

            self._cg.unindent()
            self._cg.add_lines('}')

        self._cg.unindent()
        tmpl = templates._FUNC_OPEN_BODY_END
        self._cg.add_lines(tmpl)

    def _generate_func_close(self, stream):
        def generate_goto_offset(name):
            tmpl = 'ctx->parent.at = ctx->off_spc_{};'.format(name)
            self._cg.add_line(tmpl)

        self._generate_func_close_proto(stream)
        tmpl = templates._FUNC_CLOSE_BODY_BEGIN
        spc_type = stream.packet_context_type
        ts_line = self._get_open_close_ts_line(stream)
        lines = tmpl.format(ts=ts_line)
        self._cg.add_lines(lines)
        self._cg.indent()
        self._cg.add_cc_line('do not close a packet that is not open')
        self._cg.add_line('if (!ctx->parent.packet_is_open) {')
        self._cg.indent()
        self._cg.add_line('ctx->parent.in_tracing_section = saved_in_tracing_section;')
        self._cg.add_line('return;')
        self._cg.unindent()
        self._cg.add_line('}')
        self._cg.add_empty_line()
        self._cg.add_cc_line('save content size')
        self._cg.add_line('ctx->parent.content_size = ctx->parent.at;')

        if spc_type is not None:
            field_name = 'timestamp_end'

            if field_name in spc_type.fields:
                t = spc_type.fields[field_name]
                ctype = self._get_type_ctype(t)
                src = '({}) ts'.format(ctype)
                self._cg.add_empty_line()
                self._generate_field_name_cc_line(field_name)
                generate_goto_offset(field_name)
                action = self._saved_serialization_actions[field_name]
                self._generate_serialize_from_action(src, '(&ctx->parent)', action)

            field_name = 'content_size'

            if 'content_size' in spc_type.fields:
                t = spc_type.fields[field_name]
                ctype = self._get_type_ctype(t)
                src = '({}) ctx->parent.content_size'.format(ctype)
                self._cg.add_empty_line()
                self._generate_field_name_cc_line(field_name)
                generate_goto_offset(field_name)
                action = self._saved_serialization_actions[field_name]
                self._generate_serialize_from_action(src, '(&ctx->parent)', action)

            field_name = 'events_discarded'

            if field_name in spc_type.fields:
                t = spc_type.fields[field_name]
                ctype = self._get_type_ctype(t)
                src = '({}) ctx->parent.events_discarded'.format(ctype)
                self._cg.add_empty_line()
                self._generate_field_name_cc_line(field_name)
                generate_goto_offset(field_name)
                action = self._saved_serialization_actions[field_name]
                self._generate_serialize_from_action(src, '(&ctx->parent)', action)

        self._cg.unindent()
        tmpl = templates._FUNC_CLOSE_BODY_END
        self._cg.add_lines(tmpl)

    def generate_c_src(self):
        self._cg.reset()
        dt = datetime.datetime.now().isoformat()
        header_filename = self.get_header_filename()
        tmpl = templates._C_SRC
        self._cg.add_lines(tmpl.format(prefix=self._cfg.prefix,
                                       header_filename=header_filename,
                                       version=barectf.__version__, date=dt))
        self._cg.add_empty_line()

        # initialization function
        self._generate_func_init()
        self._cg.add_empty_line()

        for stream in self._cfg.metadata.streams.values():
            self._generate_func_open(stream)
            self._cg.add_empty_line()
            self._generate_func_close(stream)
            self._cg.add_empty_line()
            ser_actions = _SerializationActions()

            if stream.event_header_type is not None:
                ser_actions.append_root_scope_type(stream.event_header_type,
                                                   _PREFIX_SEH)
                self._generate_func_serialize_stream_event_header(stream,
                                                                  iter(ser_actions.actions))
                self._cg.add_empty_line()

            if stream.event_context_type is not None:
                ser_action_index = len(ser_actions.actions)
                ser_actions.append_root_scope_type(stream.event_context_type,
                                                   _PREFIX_SEC)
                ser_action_iter = itertools.islice(ser_actions.actions,
                                                   ser_action_index, None)
                self._generate_func_serialize_stream_event_context(stream,
                                                                   ser_action_iter)
                self._cg.add_empty_line()

            for ev in stream.events.values():
                self._generate_func_get_event_size(stream, ev)
                self._cg.add_empty_line()
                self._generate_func_serialize_event(stream, ev, ser_actions)
                self._cg.add_empty_line()
                self._generate_func_trace(stream, ev)
                self._cg.add_empty_line()

        return self._cg.code

    def get_header_filename(self):
        return '{}.h'.format(self._cfg.prefix.rstrip('_'))

    def get_bitfield_header_filename(self):
        return '{}-bitfield.h'.format(self._cfg.prefix.rstrip('_'))
