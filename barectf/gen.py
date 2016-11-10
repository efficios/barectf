# The MIT License (MIT)
#
# Copyright (c) 2014-2016 Philippe Proulx <pproulx@efficios.com>
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
import argparse
import datetime
import barectf
import sys
import os
import re


def _align(v, align):
    return (v + (align - 1)) & -align


class _StaticAlignSizeAutomatonByteOffset:
    def __init__(self):
        self._byte_offset = 0
        self._type_to_update_byte_offset_func = {
            metadata.Integer: self._write_static_size,
            metadata.FloatingPoint: self._write_static_size,
            metadata.Enum: self._write_static_size,
            metadata.String: self._write_string_size,
        }

    @property
    def byte_offset(self):
        return self._byte_offset

    @byte_offset.setter
    def byte_offset(self, value):
        self._byte_offset = value

    def _wrap_byte_offset(self):
        self._byte_offset %= 8

    def align(self, align):
        # align byte offset
        self._byte_offset = _align(self._byte_offset, align)

        # wrap on current byte
        self._wrap_byte_offset()

    def write_type(self, t):
        self._type_to_update_byte_offset_func[type(t)](t)

    def _write_string_size(self, t):
        self.reset()

    def _write_static_size(self, t):
        # increment byte offset
        self._byte_offset += t.size

        # wrap on current byte
        self._wrap_byte_offset()

    def reset(self):
        # reset byte offset
        self._byte_offset = 0

    def set_unknown(self):
        self._byte_offset = None


class _StaticAlignSizeAutomatonPreSize:
    def __init__(self):
        self.reset(1)

    def reset(self, initial_align):
        self._max_align = initial_align
        self._size = 0

    def add_type(self, t):
        if t.align > self._max_align:
            # type alignment is greater than the maximum alignment we
            # got so far since the last reset, so we don't know how many
            # padding bits are needed between this type and the previous
            # one, hence the static size is set to the type's size
            # (since we're aligned) and our new alignment is saved
            self._max_align = t.align

            if type(t) is metadata.Struct:
                self._size = 0
            else:
                self._size = t.size

            return False
        else:
            # type alignment is lesser than or equal to the maximum
            # alignment we got so far, so we just align the static size
            # and add the type's size
            self._size = _align(self._size, t.align)

            if type(t) is not metadata.Struct:
                self._size += t.size

            return True

    @property
    def size(self):
        return self._size


_PREFIX_TPH = 'tph_'
_PREFIX_SPC = 'spc_'
_PREFIX_SEH = 'seh_'
_PREFIX_SEC = 'sec_'
_PREFIX_EC = 'ec_'
_PREFIX_EP = 'ep_'


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
        self._saved_byte_offsets = {}
        self._sasa = _StaticAlignSizeAutomatonByteOffset()

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
        self._sasa.align(align)

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

    def _generate_func_get_event_size_from_entity(self, prefix, t):
        self._cg.add_line('{')
        self._cg.indent()
        statically_aligned = self._pre_size_sasa.add_type(t)

        if not statically_aligned:
            # increment current position if needed
            if self._last_basic_types_size > 0:
                self._generate_incr_pos('at', self._last_basic_types_size)
                self._last_basic_types_size = 0

            self._cg.add_cc_line('align structure')
            self._generate_align_type('at', t)

        for field_name, field_type in t.fields.items():
            self._cg.add_empty_line()
            self._generate_field_name_cc_line(field_name)

            if type(field_type) is metadata.String:
                # increment current position if needed
                if self._last_basic_types_size > 0:
                    self._generate_incr_pos('at', self._last_basic_types_size)
                    self._last_basic_types_size = 0

                param = prefix + field_name
                self._generate_incr_pos_bytes('at',
                                              'strlen({}) + 1'.format(param))
                self._pre_size_sasa.reset(8)
            else:
                statically_aligned = self._pre_size_sasa.add_type(field_type)

                if not statically_aligned:
                    # increment current position if needed
                    if self._last_basic_types_size > 0:
                        self._generate_incr_pos('at', self._last_basic_types_size)

                    # realign dynamically
                    self._cg.add_cc_line('align for field')
                    self._generate_align_type('at', field_type)

                fmt = 'field size: {} (partial total so far: {})'
                self._cg.add_cc_line(fmt.format(field_type.size, self._pre_size_sasa.size))
                self._last_basic_types_size = self._pre_size_sasa.size

        self._cg.unindent()
        self._cg.add_line('}')
        self._cg.add_empty_line()

    def _generate_func_get_event_size(self, stream, event):
        self._reset_per_func_state()
        self._generate_func_get_event_size_proto(stream, event)
        tmpl = templates._FUNC_GET_EVENT_SIZE_BODY_BEGIN
        lines = tmpl.format(prefix=self._cfg.prefix)
        self._cg.add_lines(lines)
        self._cg.add_empty_line()
        self._cg.indent()
        func = self._generate_func_get_event_size_from_entity
        self._pre_size_sasa = _StaticAlignSizeAutomatonPreSize()
        self._cg.add_cc_line('byte-align entity')
        self._generate_align('at', 8)
        self._cg.add_empty_line()
        self._pre_size_sasa.reset(8)
        self._last_basic_types_size = 0

        if stream.event_header_type is not None:
            self._cg.add_cc_line('stream event header')
            func(_PREFIX_SEH, stream.event_header_type)

        if stream.event_context_type is not None:
            self._cg.add_cc_line('stream event context')
            func(_PREFIX_SEC, stream.event_context_type)

        if event.context_type is not None:
            self._cg.add_cc_line('event context')
            func(_PREFIX_EC, event.context_type)

        if event.payload_type is not None:
            self._cg.add_cc_line('event payload')
            func(_PREFIX_EP, event.payload_type)

        # increment current position if needed
        if self._last_basic_types_size > 0:
            self._generate_incr_pos('at', self._last_basic_types_size)
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

    def _generate_bitfield_write(self, ctype, var, ctx, t):
        ptr = '&{ctx}->buf[_BITS_TO_BYTES({ctx}->at)]'.format(ctx=ctx)
        start = self._sasa.byte_offset
        suffix = 'le' if t.byte_order is metadata.ByteOrder.LE else 'be'
        func = '{}bt_bitfield_write_{}'.format(self._cfg.prefix, suffix)
        call_fmt = '{func}({ptr}, uint8_t, {start}, {size}, {ctype}, ({ctype}) {var});'
        call = call_fmt.format(func=func, ptr=ptr, start=start, size=t.size,
                               ctype=ctype, var=var)
        self._cg.add_line(call)

    def _generate_serialize_int(self, var, ctx, t):
        ctype = self._get_int_ctype(t)
        self._generate_bitfield_write(ctype, var, ctx, t)
        self._generate_incr_pos('{}->at'.format(ctx), t.size)

    def _generate_serialize_float(self, var, ctx, t):
        ctype = self._get_type_ctype(t)
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

        self._generate_bitfield_write(int_ctype, bf_var, ctx, t)

        if flt_dbl:
            self._cg.unindent()
            self._cg.add_line('}')
            self._cg.add_empty_line()

        self._generate_incr_pos('{}->at'.format(ctx), t.size)

    def _generate_serialize_enum(self, var, ctx, t):
        self._generate_serialize_type(var, ctx, t.value_type)

    def _generate_serialize_string(self, var, ctx, t):
        tmpl = '_write_cstring({}, {});'.format(ctx, var)
        self._cg.add_lines(tmpl)

    def _generate_serialize_type(self, var, ctx, t):
        self._type_to_generate_serialize_func[type(t)](var, ctx, t)
        self._sasa.write_type(t)

    def _generate_func_serialize_event_from_entity(self, prefix, t,
                                                   spec_src=None):
        self._cg.add_line('{')
        self._cg.indent()
        self._cg.add_cc_line('align structure')
        self._sasa.reset()
        self._generate_align_type('ctx->at', t)

        for field_name, field_type in t.fields.items():
            src = prefix + field_name

            if spec_src is not None:
                if field_name in spec_src:
                    src = spec_src[field_name]

            self._cg.add_empty_line()
            self._generate_field_name_cc_line(field_name)
            self._generate_align_type('ctx->at', field_type)
            self._generate_serialize_type(src, 'ctx', field_type)

        self._cg.unindent()
        self._cg.add_line('}')
        self._cg.add_empty_line()

    def _generate_func_serialize_event(self, stream, event):
        self._reset_per_func_state()
        self._generate_func_serialize_event_proto(stream, event)
        tmpl = templates._FUNC_SERIALIZE_EVENT_BODY_BEGIN
        lines = tmpl.format(prefix=self._cfg.prefix)
        self._cg.add_lines(lines)
        self._cg.indent()

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

        if event.context_type is not None:
            self._cg.add_cc_line('event context')
            self._generate_func_serialize_event_from_entity(_PREFIX_EC,
                                                            event.context_type)

        if event.payload_type is not None:
            self._cg.add_cc_line('event payload')
            self._generate_func_serialize_event_from_entity(_PREFIX_EP,
                                                            event.payload_type)

        self._cg.unindent()
        tmpl = templates._FUNC_SERIALIZE_EVENT_BODY_END
        self._cg.add_lines(tmpl)

    def _generate_func_serialize_stream_event_header_proto(self, stream):
        tmpl = templates._FUNC_SERIALIZE_STREAM_EVENT_HEADER_PROTO_BEGIN
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

    def _generate_func_serialize_stream_event_header(self, stream):
        self._reset_per_func_state()
        self._generate_func_serialize_stream_event_header_proto(stream)
        tmpl = templates._FUNC_SERIALIZE_STREAM_EVENT_HEADER_BODY_BEGIN
        lines = tmpl.format(prefix=self._cfg.prefix)
        self._cg.add_lines(lines)
        self._cg.indent()

        if stream.event_header_type is not None:
            if 'timestamp' in stream.event_header_type.fields:
                timestamp = stream.event_header_type.fields['timestamp']
                ts_ctype = self._get_int_ctype(timestamp)
                clock = timestamp.property_mappings[0].object
                clock_name = clock.name
                clock_ctype = clock.return_ctype
                tmpl = '{} ts = ctx->cbs.{}_clock_get_value(ctx->data);'
                self._cg.add_line(tmpl.format(clock_ctype, clock_name))

        self._cg.add_empty_line()
        func = self._generate_func_serialize_event_from_entity

        if stream.event_header_type is not None:
            spec_src = {}

            if 'id' in stream.event_header_type.fields:
                id_t = stream.event_header_type.fields['id']
                id_t_ctype = self._get_int_ctype(id_t)
                spec_src['id'] = '({}) event_id'.format(id_t_ctype)

            if 'timestamp' in stream.event_header_type.fields:
                spec_src['timestamp'] = '({}) ts'.format(ts_ctype)

            func(_PREFIX_SEH, stream.event_header_type, spec_src)

        self._cg.unindent()
        tmpl = templates._FUNC_SERIALIZE_STREAM_EVENT_HEADER_BODY_END
        self._cg.add_lines(tmpl)

    def _generate_func_serialize_stream_event_context(self, stream):
        self._reset_per_func_state()
        self._generate_func_serialize_stream_event_context_proto(stream)
        tmpl = templates._FUNC_SERIALIZE_STREAM_EVENT_CONTEXT_BODY_BEGIN
        lines = tmpl.format(prefix=self._cfg.prefix)
        self._cg.add_lines(lines)
        self._cg.indent()
        func = self._generate_func_serialize_event_from_entity

        if stream.event_context_type is not None:
            func(_PREFIX_SEC, stream.event_context_type)

        self._cg.unindent()
        tmpl = templates._FUNC_SERIALIZE_STREAM_EVENT_CONTEXT_BODY_END
        self._cg.add_lines(tmpl)

    def _generate_func_trace(self, stream, event):
        self._reset_per_func_state()
        self._generate_func_trace_proto(stream, event)
        params = self._get_call_event_param_list(stream, event)
        tmpl = templates._FUNC_TRACE_BODY
        self._cg.add_lines(tmpl.format(sname=stream.name, evname=event.name,
                                       params=params))

    def _generate_func_init(self):
        self._reset_per_func_state()
        self._generate_func_init_proto()
        tmpl = templates._FUNC_INIT_BODY
        self._cg.add_lines(tmpl.format(prefix=self._cfg.prefix))

    def _generate_field_name_cc_line(self, field_name):
        self._cg.add_cc_line('"{}" field'.format(field_name))

    def _save_byte_offset(self, name):
        self._saved_byte_offsets[name] = self._sasa.byte_offset

    def _restore_byte_offset(self, name):
        self._sasa.byte_offset = self._saved_byte_offsets[name]

    def _reset_per_func_state(self):
        pass

    def _generate_func_open(self, stream):
        def generate_save_offset(name):
            tmpl = 'ctx->off_spc_{} = ctx->parent.at;'.format(name)
            self._cg.add_line(tmpl)
            self._save_byte_offset(name)

        self._reset_per_func_state()
        self._generate_func_open_proto(stream)
        tmpl = templates._FUNC_OPEN_BODY_BEGIN
        self._cg.add_lines(tmpl)
        self._cg.indent()
        tph_type = self._cfg.metadata.trace.packet_header_type
        spc_type = stream.packet_context_type

        if spc_type is not None and 'timestamp_begin' in spc_type.fields:
            field = spc_type.fields['timestamp_begin']
            tmpl = '{} ts = ctx->parent.cbs.{}_clock_get_value(ctx->parent.data);'
            clock = field.property_mappings[0].object
            clock_ctype = clock.return_ctype
            clock_name = clock.name
            self._cg.add_line(tmpl.format(clock_ctype, clock_name))
            self._cg.add_empty_line()

        self._cg.add_cc_line('do not open a packet that is already open')
        self._cg.add_line('if (ctx->parent.packet_is_open) {')
        self._cg.indent()
        self._cg.add_line('return;')
        self._cg.unindent()
        self._cg.add_line('}')
        self._cg.add_empty_line()
        self._cg.add_line('ctx->parent.at = 0;')

        if tph_type is not None:
            self._cg.add_empty_line()
            self._cg.add_cc_line('trace packet header')
            self._cg.add_line('{')
            self._cg.indent()
            self._cg.add_cc_line('align structure')
            self._sasa.reset()
            self._generate_align_type('ctx->parent.at', tph_type)

            for field_name, field_type in tph_type.fields.items():
                src = _PREFIX_TPH + field_name

                if field_name == 'magic':
                    src = '0xc1fc1fc1UL'
                elif field_name == 'stream_id':
                    stream_id_ctype = self._get_int_ctype(field_type)
                    src = '({}) {}'.format(stream_id_ctype, stream.id)
                elif field_name == 'uuid':
                    self._cg.add_empty_line()
                    self._generate_field_name_cc_line(field_name)
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
                    self._sasa.reset()
                    continue

                self._cg.add_empty_line()
                self._generate_field_name_cc_line(field_name)
                self._generate_align_type('ctx->parent.at', field_type)
                self._generate_serialize_type(src, '(&ctx->parent)', field_type)

            self._cg.unindent()
            self._cg.add_lines('}')

        if spc_type is not None:
            self._cg.add_empty_line()
            self._cg.add_cc_line('stream packet context')
            self._cg.add_line('{')
            self._cg.indent()
            self._cg.add_cc_line('align structure')
            self._sasa.reset()
            self._generate_align_type('ctx->parent.at', spc_type)
            tmpl_off = 'off_spc_{fname}'

            for field_name, field_type in spc_type.fields.items():
                src = _PREFIX_SPC + field_name
                skip_int = False
                self._cg.add_empty_line()
                self._generate_field_name_cc_line(field_name)

                if field_name == 'timestamp_begin':
                    ctype = self._get_type_ctype(field_type)
                    src = '({}) ts'.format(ctype)
                elif field_name in ['timestamp_end', 'content_size',
                                    'events_discarded']:
                    skip_int = True
                elif field_name == 'packet_size':
                    ctype = self._get_type_ctype(field_type)
                    src = '({}) ctx->parent.packet_size'.format(ctype)

                self._generate_align_type('ctx->parent.at', field_type)

                if skip_int:
                    generate_save_offset(field_name)
                    self._generate_incr_pos('ctx->parent.at', field_type.size)
                    self._sasa.write_type(field_type)
                else:
                    self._generate_serialize_type(src, '(&ctx->parent)',
                                                  field_type)

            self._cg.unindent()
            self._cg.add_lines('}')

        self._cg.unindent()
        tmpl = templates._FUNC_OPEN_BODY_END
        self._cg.add_lines(tmpl)

    def _generate_func_close(self, stream):
        def generate_goto_offset(name):
            tmpl = 'ctx->parent.at = ctx->off_spc_{};'.format(name)
            self._cg.add_line(tmpl)

        self._reset_per_func_state()
        self._generate_func_close_proto(stream)
        tmpl = templates._FUNC_CLOSE_BODY_BEGIN
        self._cg.add_lines(tmpl)
        self._cg.indent()
        spc_type = stream.packet_context_type

        if spc_type is not None:
            if 'timestamp_end' in spc_type.fields:
                tmpl = '{} ts = ctx->parent.cbs.{}_clock_get_value(ctx->parent.data);'
                field = spc_type.fields['timestamp_end']
                clock = field.property_mappings[0].object
                clock_ctype = clock.return_ctype
                clock_name = clock.name
                self._cg.add_line(tmpl.format(clock_ctype, clock_name))
                self._cg.add_empty_line()

        self._cg.add_cc_line('do not close a packet that is not open')
        self._cg.add_line('if (!ctx->parent.packet_is_open) {')
        self._cg.indent()
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
                self._restore_byte_offset(field_name)
                self._generate_serialize_type(src, '(&ctx->parent)', t)

            field_name = 'content_size'

            if 'content_size' in spc_type.fields:
                t = spc_type.fields[field_name]
                ctype = self._get_type_ctype(t)
                src = '({}) ctx->parent.content_size'.format(ctype)
                self._cg.add_empty_line()
                self._generate_field_name_cc_line(field_name)
                generate_goto_offset(field_name)
                self._restore_byte_offset(field_name)
                self._generate_serialize_type(src, '(&ctx->parent)', t)

            field_name = 'events_discarded'

            if field_name in spc_type.fields:
                t = spc_type.fields[field_name]
                ctype = self._get_type_ctype(t)
                src = '({}) ctx->parent.events_discarded'.format(ctype)
                self._cg.add_empty_line()
                self._generate_field_name_cc_line(field_name)
                generate_goto_offset(field_name)
                self._restore_byte_offset(field_name)
                self._generate_serialize_type(src, '(&ctx->parent)', t)

        self._cg.unindent()
        tmpl = templates._FUNC_CLOSE_BODY_END
        self._cg.add_lines(tmpl)
        self._sasa.reset()

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

            if stream.event_header_type is not None:
                self._generate_func_serialize_stream_event_header(stream)
                self._cg.add_empty_line()

            if stream.event_context_type is not None:
                self._generate_func_serialize_stream_event_context(stream)
                self._cg.add_empty_line()

            for ev in stream.events.values():
                self._generate_func_get_event_size(stream, ev)
                self._cg.add_empty_line()
                self._generate_func_serialize_event(stream, ev)
                self._cg.add_empty_line()
                self._generate_func_trace(stream, ev)
                self._cg.add_empty_line()

        return self._cg.code

    def get_header_filename(self):
        return '{}.h'.format(self._cfg.prefix.rstrip('_'))

    def get_bitfield_header_filename(self):
        return '{}-bitfield.h'.format(self._cfg.prefix.rstrip('_'))
