# The MIT License (MIT)
#
# Copyright (c) 2014-2020 Philippe Proulx <pproulx@efficios.com>
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

import barectf.tsdl182gen as barectf_tsdl182gen
import barectf.templates as barectf_templates
import barectf.template as barectf_template
import barectf.codegen as barectf_codegen
import barectf.config as barectf_config
import barectf.version as barectf_version
import itertools
import datetime
import copy


class _GeneratedFile:
    def __init__(self, name, contents):
        self._name = name
        self._contents = contents

    @property
    def name(self):
        return self._name

    @property
    def contents(self):
        return self._contents


class CodeGenerator:
    def __init__(self, configuration):
        self._config = configuration
        self._file_name_prefix = configuration.options.code_generation_options.file_name_prefix
        self._ccode_gen = _CCodeGenerator(configuration)
        self._c_headers = None
        self._c_sources = None
        self._metadata_stream = None

    @property
    def _barectf_header_name(self):
        return f'{self._file_name_prefix}.h'

    def generate_c_headers(self):
        if self._c_headers is None:
            bitfield_header_name = f'{self._file_name_prefix}-bitfield.h'
            self._c_headers = [
                _GeneratedFile(self._barectf_header_name,
                               self._ccode_gen.generate_header(bitfield_header_name)),
                _GeneratedFile(bitfield_header_name,
                               self._ccode_gen.generate_bitfield_header()),
            ]

        return self._c_headers

    def generate_c_sources(self):
        if self._c_sources is None:
            self._c_sources = [
                _GeneratedFile(f'{self._file_name_prefix}.c',
                               self._ccode_gen.generate_c_src(self._barectf_header_name))
            ]

        return self._c_sources

    def generate_metadata_stream(self):
        if self._metadata_stream is None:
            self._metadata_stream = _GeneratedFile('metadata',
                                                   barectf_tsdl182gen._from_config(self._config))

        return self._metadata_stream


def _align(v, align):
    return (v + (align - 1)) & -align


class _SerializationAction:
    def __init__(self, offset_in_byte, ft, names):
        assert(offset_in_byte >= 0 and offset_in_byte < 8)
        self._offset_in_byte = offset_in_byte
        self._ft = ft
        self._names = copy.deepcopy(names)

    @property
    def offset_in_byte(self):
        return self._offset_in_byte

    @property
    def ft(self):
        return self._ft

    @property
    def names(self):
        return self._names


class _AlignSerializationAction(_SerializationAction):
    def __init__(self, offset_in_byte, ft, names, value):
        super().__init__(offset_in_byte, ft, names)
        self._value = value

    @property
    def value(self):
        return self._value


class _SerializeSerializationAction(_SerializationAction):
    pass


class _SerializationActions:
    def __init__(self):
        self.reset()

    def reset(self):
        self._last_alignment = None
        self._last_bit_array_size = None
        self._actions = []
        self._names = []
        self._offset_in_byte = 0

    def append_root_scope_ft(self, ft, name):
        if ft is None:
            return

        assert(type(ft) is barectf_config.StructureFieldType)
        self._names = [name]
        self._append_ft(ft)

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

    def _append_ft(self, ft):
        if isinstance(ft, (barectf_config.StringFieldType, barectf_config._ArrayFieldType)):
            assert(type(ft) is barectf_config.StringFieldType or self._names[-1] == 'uuid')
            do_align = self._must_align(8)
            self._last_alignment = 8
            self._last_bit_array_size = 8
            self._try_append_align_action(8, do_align, ft)
            self._append_serialize_action(ft)
        else:
            do_align = self._must_align(ft.alignment)
            self._last_alignment = ft.alignment

            if type(ft) is barectf_config.StructureFieldType:
                self._last_bit_array_size = ft.alignment
            else:
                self._last_bit_array_size = ft.size

            self._try_append_align_action(ft.alignment, do_align, ft)

            if type(ft) is barectf_config.StructureFieldType:
                for member_name, member in ft.members.items():
                    self._names.append(member_name)
                    self._append_ft(member.field_type)
                    del self._names[-1]
            else:
                self._append_serialize_action(ft)

    def _try_append_align_action(self, alignment, do_align, ft=None):
        offset_in_byte = self._offset_in_byte
        self._offset_in_byte = _align(self._offset_in_byte, alignment) % 8

        if do_align and alignment > 1:
            self._actions.append(_AlignSerializationAction(offset_in_byte, ft, self._names,
                                                           alignment))

    def _append_serialize_action(self, ft):
        assert(type(ft) is not barectf_config.StructureFieldType)
        offset_in_byte = self._offset_in_byte

        if isinstance(ft, barectf_config._BitArrayFieldType):
            self._offset_in_byte += ft.size
            self._offset_in_byte %= 8

        self._actions.append(_SerializeSerializationAction(offset_in_byte, ft, self._names))


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


class _CCodeGenerator:
    def __init__(self, cfg):
        self._cfg = cfg
        code_gen_opts = cfg.options.code_generation_options
        self._iden_prefix = code_gen_opts.identifier_prefix
        self._cg = barectf_codegen._CodeGenerator('\t')
        self._saved_serialization_actions = {}

    def _create_template(self, name: str) -> barectf_template._Template:
        return barectf_template._Template(name, cfg=self._cfg)

    def _create_file_template(self, name: str) -> barectf_template._Template:
        return barectf_template._Template(name, True, self._cfg)

    @property
    def _trace_type(self):
        return self._cfg.trace.type

    def _clk_type_c_type(self, clk_type):
        return self._cfg.options.code_generation_options.clock_type_c_types[clk_type]

    def _generate_ctx_parent(self):
        tmpl = barectf_templates._CTX_PARENT
        self._cg.add_lines(tmpl.format(prefix=self._iden_prefix))

    def _generate_ctx(self, stream_type):
        tmpl = barectf_templates._CTX_BEGIN
        self._cg.add_lines(tmpl.format(prefix=self._iden_prefix, sname=stream_type.name))
        self._cg.indent()
        pkt_header_ft = self._trace_type._pkt_header_ft

        if pkt_header_ft is not None:
            for member_name in pkt_header_ft.members:
                self._cg.add_lines(f'uint32_t off_tph_{member_name};')

        for member_name in stream_type._pkt_ctx_ft.members:
            self._cg.add_lines(f'uint32_t off_spc_{member_name};')

        if stream_type.default_clock_type is not None:
            self._cg.add_line(f'{self._clk_type_c_type(stream_type.default_clock_type)} cur_last_event_ts;')

        self._cg.unindent()
        tmpl = barectf_templates._CTX_END
        self._cg.add_lines(tmpl)

    def _generate_ctxs(self):
        for stream_type in self._trace_type.stream_types:
            self._generate_ctx(stream_type)

    def _generate_clock_cb(self, clk_type):
        tmpl = barectf_templates._CLOCK_CB
        self._cg.add_lines(tmpl.format(return_ctype=self._clk_type_c_type(clk_type),
                                       cname=clk_type.name))

    def _generate_clock_cbs(self):
        clk_names = set()

        for stream_type in self._trace_type.stream_types:
            def_clk_type = stream_type.default_clock_type

            if def_clk_type is not None and def_clk_type not in clk_names:
                self._generate_clock_cb(def_clk_type)
                clk_names.add(def_clk_type)

    def _generate_platform_callbacks(self):
        tmpl = barectf_templates._PLATFORM_CALLBACKS_BEGIN
        self._cg.add_lines(tmpl.format(prefix=self._iden_prefix))
        self._cg.indent()
        self._generate_clock_cbs()
        self._cg.unindent()
        tmpl = barectf_templates._PLATFORM_CALLBACKS_END
        self._cg.add_lines(tmpl)

    def generate_bitfield_header(self):
        self._cg.reset()
        tmpl = barectf_templates._BITFIELD
        tmpl = tmpl.replace('$prefix$', self._iden_prefix)
        tmpl = tmpl.replace('$PREFIX$', self._iden_prefix.upper())

        if self._trace_type.default_byte_order == barectf_config.ByteOrder.BIG_ENDIAN:
            endian_def = 'BIG_ENDIAN'
        else:
            endian_def = 'LITTLE_ENDIAN'

        tmpl = tmpl.replace('$ENDIAN_DEF$', endian_def)
        self._cg.add_lines(tmpl)

        return self._cg.code

    def _generate_func_init_proto(self):
        tmpl = barectf_templates._FUNC_INIT_PROTO
        self._cg.add_lines(tmpl.format(prefix=self._iden_prefix))

    def _get_ft_c_type(self, ft):
        if isinstance(ft, barectf_config._IntegerFieldType):
            sign_prefix = 'u' if isinstance(ft, barectf_config.UnsignedIntegerFieldType) else ''

            if ft.size <= 8:
                sz = 8
            elif ft.size <= 16:
                sz = 16
            elif ft.size <= 32:
                sz = 32
            else:
                assert ft.size == 64
                sz = 64

            return f'{sign_prefix}int{sz}_t'
        elif type(ft) is barectf_config.RealFieldType:
            if ft.size == 32 and ft.alignment == 32:
                return 'float'
            elif ft.size == 64 and ft.alignment == 64:
                return 'double'
            else:
                return 'uint64_t'
        else:
            assert type(ft) is barectf_config.StringFieldType
            return 'const char *'

    def _generate_ft_c_type(self, ft):
        c_type = self._get_ft_c_type(ft)
        self._cg.append_to_last_line(c_type)

    def _generate_proto_param(self, ft, name):
        self._generate_ft_c_type(ft)
        self._cg.append_to_last_line(' ')
        self._cg.append_to_last_line(name)

    def _generate_proto_params(self, ft, name_prefix, exclude_set=None):
        if exclude_set is None:
            exclude_set = set()

        self._cg.indent()

        for member_name, member in ft.members.items():
            if member_name in exclude_set:
                continue

            self._cg.append_to_last_line(',')
            self._cg.add_line('')
            self._generate_proto_param(member.field_type, name_prefix + member_name)

        self._cg.unindent()

    def _generate_func_open_proto(self, stream_type):
        tmpl = barectf_templates._FUNC_OPEN_PROTO_BEGIN
        self._cg.add_lines(tmpl.format(prefix=self._iden_prefix, sname=stream_type.name))

        if self._trace_type._pkt_header_ft is not None:
            self._generate_proto_params(self._trace_type._pkt_header_ft, _PREFIX_TPH,
                                        {'magic', 'stream_id', 'uuid'})

        exclude_set = {
            'timestamp_begin',
            'timestamp_end',
            'packet_size',
            'content_size',
            'events_discarded',
        }
        self._generate_proto_params(stream_type._pkt_ctx_ft, _PREFIX_SPC, exclude_set)
        tmpl = barectf_templates._FUNC_OPEN_PROTO_END
        self._cg.add_lines(tmpl)

    def _generate_func_close_proto(self, stream_type):
        tmpl = barectf_templates._FUNC_CLOSE_PROTO
        self._cg.add_lines(tmpl.format(prefix=self._iden_prefix, sname=stream_type.name))

    def _generate_func_trace_proto_params(self, stream_type, ev_type):
        if stream_type._ev_header_ft is not None:
            self._generate_proto_params(stream_type._ev_header_ft, _PREFIX_SEH, {'id', 'timestamp'})

        if stream_type.event_common_context_field_type is not None:
            self._generate_proto_params(stream_type.event_common_context_field_type, _PREFIX_SEC)

        if ev_type.specific_context_field_type is not None:
            self._generate_proto_params(ev_type.specific_context_field_type, _PREFIX_EC)

        if ev_type.payload_field_type is not None:
            self._generate_proto_params(ev_type.payload_field_type, _PREFIX_EP)

    def _generate_func_trace_proto(self, stream_type, ev_type):
        tmpl = barectf_templates._FUNC_TRACE_PROTO_BEGIN
        self._cg.add_lines(tmpl.format(prefix=self._iden_prefix, sname=stream_type.name,
                                       evname=ev_type.name))
        self._generate_func_trace_proto_params(stream_type, ev_type)
        tmpl = barectf_templates._FUNC_TRACE_PROTO_END
        self._cg.add_lines(tmpl)

    def _punctuate_proto(self):
        self._cg.append_to_last_line(';')

    def generate_header(self, bitfield_header_name):
        self._cg.reset()
        dt = datetime.datetime.now().isoformat()
        prefix_def = ''
        def_stream_type_name_def = ''
        cg_opts = self._cfg.options.code_generation_options
        header_opts = cg_opts.header_options

        if header_opts.identifier_prefix_definition:
            prefix_def = f'#define _BARECTF_PREFIX {self._iden_prefix}'

        def_stream_type = cg_opts.default_stream_type

        if header_opts.default_stream_type_name_definition and def_stream_type is not None:
            def_stream_type_name_def = f'#define _BARECTF_DEFAULT_STREAM {def_stream_type.name}'

        def_stream_type_trace_defs = ''

        if def_stream_type is not None:
            lines = []

            for ev_type in def_stream_type.event_types:
                tmpl = barectf_templates._DEFINE_DEFAULT_STREAM_TRACE
                define = tmpl.format(prefix=self._iden_prefix, sname=def_stream_type.name,
                                     evname=ev_type.name)
                lines.append(define)

            def_stream_type_trace_defs = '\n'.join(lines)

        tmpl = barectf_templates._HEADER_BEGIN
        self._cg.add_lines(tmpl.format(prefix=self._iden_prefix,
                                       ucprefix=self._iden_prefix.upper(),
                                       bitfield_header_filename=bitfield_header_name,
                                       version=barectf_version.__version__, date=dt,
                                       prefix_def=prefix_def,
                                       default_stream_def=def_stream_type_name_def,
                                       default_stream_trace_defs=def_stream_type_trace_defs))
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

        for stream_type in self._trace_type.stream_types:
            self._generate_func_open_proto(stream_type)
            self._punctuate_proto()
            self._cg.add_empty_line()
            self._generate_func_close_proto(stream_type)
            self._punctuate_proto()
            self._cg.add_empty_line()

            for ev_type in stream_type.event_types:
                self._generate_func_trace_proto(stream_type, ev_type)
                self._punctuate_proto()
                self._cg.add_empty_line()

        tmpl = barectf_templates._HEADER_END
        self._cg.add_lines(tmpl.format(ucprefix=self._iden_prefix.upper()))
        return self._cg.code

    def _get_call_event_param_list_from_struct_ft(self, ft, prefix, exclude_set=None):
        if exclude_set is None:
            exclude_set = set()

        lst = ''

        for member_name in ft.members:
            if member_name in exclude_set:
                continue

            lst += f', {prefix}{member_name}'

        return lst

    def _get_call_event_param_list(self, stream_type, ev_type):
        lst = ''

        if stream_type._ev_header_ft is not None:
            lst += self._get_call_event_param_list_from_struct_ft(stream_type._ev_header_ft,
                                                                  _PREFIX_SEH, {'id', 'timestamp'})

        if stream_type.event_common_context_field_type is not None:
            lst += self._get_call_event_param_list_from_struct_ft(stream_type.event_common_context_field_type,
                                                                  _PREFIX_SEC)

        if ev_type.specific_context_field_type is not None:
            lst += self._get_call_event_param_list_from_struct_ft(ev_type.specific_context_field_type,
                                                                  _PREFIX_EC)

        if ev_type.payload_field_type is not None:
            lst += self._get_call_event_param_list_from_struct_ft(ev_type.payload_field_type,
                                                                  _PREFIX_EP)

        return lst

    def _generate_align(self, at, align):
        self._cg.add_line(f'_ALIGN({at}, {align});')

    def _generate_incr_pos(self, var, value):
        self._cg.add_line(f'{var} += {value};')

    def _generate_incr_pos_bytes(self, var, value):
        self._generate_incr_pos(var, f'_BYTES_TO_BITS({value})')

    def _generate_func_get_event_size_proto(self, stream_type, ev_type):
        tmpl = barectf_templates._FUNC_GET_EVENT_SIZE_PROTO_BEGIN
        self._cg.add_lines(tmpl.format(prefix=self._iden_prefix, sname=stream_type.name,
                                       evname=ev_type.name))
        self._generate_func_trace_proto_params(stream_type, ev_type)
        tmpl = barectf_templates._FUNC_GET_EVENT_SIZE_PROTO_END
        self._cg.add_lines(tmpl)

    def _generate_func_get_event_size(self, stream_type, ev_type):
        self._generate_func_get_event_size_proto(stream_type, ev_type)
        tmpl = barectf_templates._FUNC_GET_EVENT_SIZE_BODY_BEGIN
        lines = tmpl.format(prefix=self._iden_prefix)
        self._cg.add_lines(lines)
        self._cg.add_empty_line()
        self._cg.indent()
        ser_actions = _SerializationActions()
        ser_actions.append_root_scope_ft(stream_type._ev_header_ft, _PREFIX_SEH)
        ser_actions.append_root_scope_ft(stream_type.event_common_context_field_type, _PREFIX_SEC)
        ser_actions.append_root_scope_ft(ev_type.specific_context_field_type, _PREFIX_EC)
        ser_actions.append_root_scope_ft(ev_type.payload_field_type, _PREFIX_EP)

        for action in ser_actions.actions:
            if type(action) is _AlignSerializationAction:
                if action.names:
                    if len(action.names) == 1:
                        line = f'align {_PREFIX_TO_NAME[action.names[0]]} structure'
                    else:
                        line = f'align field `{action.names[-1]}` ({_PREFIX_TO_NAME[action.names[0]]})'

                    self._cg.add_cc_line(line)

                self._generate_align('at', action.value)
                self._cg.add_empty_line()
            else:
                assert type(action) is _SerializeSerializationAction
                assert(len(action.names) >= 2)
                line = f'add size of field `{action.names[-1]}` ({_PREFIX_TO_NAME[action.names[0]]})'
                self._cg.add_cc_line(line)

                if type(action.ft) is barectf_config.StringFieldType:
                    param = ''.join(action.names)
                    self._generate_incr_pos_bytes('at', f'strlen({param}) + 1')
                else:
                    self._generate_incr_pos('at', action.ft.size)

                self._cg.add_empty_line()

        self._cg.unindent()
        tmpl = barectf_templates._FUNC_GET_EVENT_SIZE_BODY_END
        self._cg.add_lines(tmpl)

    def _generate_func_serialize_event_proto(self, stream_type, ev_type):
        tmpl = barectf_templates._FUNC_SERIALIZE_EVENT_PROTO_BEGIN
        self._cg.add_lines(tmpl.format(prefix=self._iden_prefix, sname=stream_type.name,
                                       evname=ev_type.name))
        self._generate_func_trace_proto_params(stream_type, ev_type)
        tmpl = barectf_templates._FUNC_SERIALIZE_EVENT_PROTO_END
        self._cg.add_lines(tmpl)

    def _generate_serialize_from_action(self, var, ctx, action):
        def gen_bitfield_write(c_type, var, ctx, action):
            ptr = f'&{ctx}->buf[_BITS_TO_BYTES({ctx}->at)]'
            start = action.offset_in_byte
            suffix = 'le' if action.ft.byte_order is barectf_config.ByteOrder.LITTLE_ENDIAN else 'be'
            func = f'{self._iden_prefix}bt_bitfield_write_{suffix}'
            call = f'{func}({ptr}, uint8_t, {start}, {action.ft.size}, {c_type}, ({c_type}) {var});'
            self._cg.add_line(call)

        def gen_serialize_int(var, ctx, action):
            c_type = self._get_ft_c_type(action.ft)
            gen_bitfield_write(c_type, var, ctx, action)
            self._generate_incr_pos(f'{ctx}->at', action.ft.size)

        def gen_serialize_real(var, ctx, action):
            c_type = self._get_ft_c_type(action.ft)
            flt_dbl = False

            if c_type == 'float' or c_type == 'double':
                flt_dbl = True

                if c_type == 'float':
                    union_name = 'f2u'
                    int_c_type = 'uint32_t'
                else:
                    assert c_type == 'double'
                    union_name = 'd2u'
                    int_c_type = 'uint64_t'

                # union for reading the bytes of the floating point number
                self._cg.add_empty_line()
                self._cg.add_line('{')
                self._cg.indent()
                self._cg.add_line(f'union {union_name} {union_name};')
                self._cg.add_empty_line()
                self._cg.add_line(f'{union_name}.f = {var};')
                bf_var = f'{union_name}.u'
            else:
                bf_var = f'({c_type}) {var}'
                int_c_type = c_type

            gen_bitfield_write(int_c_type, bf_var, ctx, action)

            if flt_dbl:
                self._cg.unindent()
                self._cg.add_line('}')
                self._cg.add_empty_line()

            self._generate_incr_pos(f'{ctx}->at', action.ft.size)

        def gen_serialize_string(var, ctx, action):
            self._cg.add_lines(f'_write_cstring({ctx}, {var});')

        if isinstance(action.ft, barectf_config._IntegerFieldType):
            return gen_serialize_int(var, ctx, action)
        elif type(action.ft) is barectf_config.RealFieldType:
            return gen_serialize_real(var, ctx, action)
        else:
            assert type(action.ft) is barectf_config.StringFieldType
            return gen_serialize_string(var, ctx, action)

    def _generate_serialize_statements_from_actions(self, prefix, action_iter, spec_src=None):
        for action in action_iter:
            if type(action) is _AlignSerializationAction:
                if action.names:
                    if len(action.names) == 1:
                        line = f'align {_PREFIX_TO_NAME[action.names[0]]} structure'
                    else:
                        line = f'align field `{action.names[-1]}` ({_PREFIX_TO_NAME[action.names[0]]})'

                    self._cg.add_cc_line(line)

                self._generate_align('ctx->at', action.value)
                self._cg.add_empty_line()
            else:
                assert type(action) is _SerializeSerializationAction
                assert(len(action.names) >= 2)
                member_name = action.names[-1]
                line = f'serialize field `{member_name}` ({_PREFIX_TO_NAME[action.names[0]]})'
                self._cg.add_cc_line(line)
                src = prefix + member_name

                if spec_src is not None and member_name in spec_src:
                    src = spec_src[member_name]

                self._generate_serialize_from_action(src, 'ctx', action)
                self._cg.add_empty_line()

    def _generate_func_serialize_event(self, stream_type, ev_type, orig_ser_actions):
        self._generate_func_serialize_event_proto(stream_type, ev_type)
        tmpl = barectf_templates._FUNC_SERIALIZE_EVENT_BODY_BEGIN
        lines = tmpl.format(prefix=self._iden_prefix)
        self._cg.add_lines(lines)
        self._cg.indent()
        self._cg.add_empty_line()

        if stream_type._ev_header_ft is not None:
            params = self._get_call_event_param_list_from_struct_ft(stream_type._ev_header_ft,
                                                                    _PREFIX_SEH,
                                                                    {'timestamp', 'id'})
            self._cg.add_cc_line('stream event header')
            line = f'_serialize_stream_event_header_{stream_type.name}(ctx, {ev_type.id}{params});'
            self._cg.add_line(line)
            self._cg.add_empty_line()

        if stream_type.event_common_context_field_type is not None:
            params = self._get_call_event_param_list_from_struct_ft(stream_type.event_common_context_field_type,
                                                                    _PREFIX_SEC)
            self._cg.add_cc_line('stream event context')
            line = f'_serialize_stream_event_context_{stream_type.name}(ctx{params});'
            self._cg.add_line(line)
            self._cg.add_empty_line()

        if ev_type.specific_context_field_type is not None or ev_type.payload_field_type is not None:
            ser_actions = copy.deepcopy(orig_ser_actions)

        if ev_type.specific_context_field_type is not None:
            ser_action_index = len(ser_actions.actions)
            ser_actions.append_root_scope_ft(ev_type.specific_context_field_type, _PREFIX_EC)
            ser_action_iter = itertools.islice(ser_actions.actions, ser_action_index, None)
            self._generate_serialize_statements_from_actions(_PREFIX_EC, ser_action_iter)

        if ev_type.payload_field_type is not None:
            ser_action_index = len(ser_actions.actions)
            ser_actions.append_root_scope_ft(ev_type.payload_field_type, _PREFIX_EP)
            ser_action_iter = itertools.islice(ser_actions.actions, ser_action_index, None)
            self._generate_serialize_statements_from_actions(_PREFIX_EP, ser_action_iter)

        self._cg.unindent()
        tmpl = barectf_templates._FUNC_SERIALIZE_EVENT_BODY_END
        self._cg.add_lines(tmpl)

    def _generate_func_serialize_event_header_proto(self, stream_type):
        tmpl = barectf_templates._FUNC_SERIALIZE_STREAM_EVENT_HEADER_PROTO_BEGIN
        self._cg.add_lines(tmpl.format(prefix=self._iden_prefix, sname=stream_type.name))

        if stream_type._ev_header_ft is not None:
            self._generate_proto_params(stream_type._ev_header_ft, _PREFIX_SEH,
                                        {'id', 'timestamp'})

        tmpl = barectf_templates._FUNC_SERIALIZE_STREAM_EVENT_HEADER_PROTO_END
        self._cg.add_lines(tmpl)

    def _generate_func_serialize_event_common_context_proto(self, stream_type):
        tmpl = barectf_templates._FUNC_SERIALIZE_STREAM_EVENT_CONTEXT_PROTO_BEGIN
        self._cg.add_lines(tmpl.format(prefix=self._iden_prefix, sname=stream_type.name))

        if stream_type.event_common_context_field_type is not None:
            self._generate_proto_params(stream_type.event_common_context_field_type, _PREFIX_SEC)

        tmpl = barectf_templates._FUNC_SERIALIZE_STREAM_EVENT_CONTEXT_PROTO_END
        self._cg.add_lines(tmpl)

    def _generate_func_serialize_event_header(self, stream_type, ser_action_iter):
        self._generate_func_serialize_event_header_proto(stream_type)
        tmpl = barectf_templates._FUNC_SERIALIZE_STREAM_EVENT_HEADER_BODY_BEGIN
        lines = tmpl.format(prefix=self._iden_prefix, sname=stream_type.name)
        self._cg.add_lines(lines)
        self._cg.indent()

        if stream_type.default_clock_type is not None:
            line = f'struct {self._iden_prefix}{stream_type.name}_ctx *s_ctx = FROM_VOID_PTR(struct {self._iden_prefix}{stream_type.name}_ctx, vctx);'
            self._cg.add_line(line)
            line = f'const {self._clk_type_c_type(stream_type.default_clock_type)} ts = s_ctx->cur_last_event_ts;'
            self._cg.add_line(line)

        self._cg.add_empty_line()

        if stream_type._ev_header_ft is not None:
            spec_src = {}
            member_name = 'id'
            member = stream_type._ev_header_ft.members.get(member_name)

            if member is not None:
                spec_src[member_name] = f'({self._get_ft_c_type(member.field_type)}) event_id'

            member_name = 'timestamp'
            member = stream_type._ev_header_ft.members.get(member_name)

            if member is not None:
                spec_src[member_name] = f'({self._get_ft_c_type(member.field_type)}) ts'

            self._generate_serialize_statements_from_actions(_PREFIX_SEH, ser_action_iter,
                                                             spec_src)

        self._cg.unindent()
        tmpl = barectf_templates._FUNC_SERIALIZE_STREAM_EVENT_HEADER_BODY_END
        self._cg.add_lines(tmpl)

    def _generate_func_serialize_event_common_context(self, stream_type, ser_action_iter):
        self._generate_func_serialize_event_common_context_proto(stream_type)
        tmpl = barectf_templates._FUNC_SERIALIZE_STREAM_EVENT_CONTEXT_BODY_BEGIN
        lines = tmpl.format(prefix=self._iden_prefix)
        self._cg.add_lines(lines)
        self._cg.indent()

        if stream_type.event_common_context_field_type is not None:
            self._generate_serialize_statements_from_actions(_PREFIX_SEC, ser_action_iter)

        self._cg.unindent()
        tmpl = barectf_templates._FUNC_SERIALIZE_STREAM_EVENT_CONTEXT_BODY_END
        self._cg.add_lines(tmpl)

    def _generate_func_trace(self, stream_type, ev_type):
        self._generate_func_trace_proto(stream_type, ev_type)
        params = self._get_call_event_param_list(stream_type, ev_type)
        def_clk_type = stream_type.default_clock_type

        if def_clk_type is not None:
            save_ts_line = f'ctx->cur_last_event_ts = ctx->parent.cbs.{def_clk_type.name}_clock_get_value(ctx->parent.data);'
        else:
            save_ts_line = '/* (no clock) */'

        tmpl = barectf_templates._FUNC_TRACE_BODY
        self._cg.add_lines(tmpl.format(sname=stream_type.name, evname=ev_type.name, params=params,
                                       save_ts=save_ts_line))

    def _generate_func_init(self):
        self._generate_func_init_proto()
        tmpl = barectf_templates._FUNC_INIT_BODY
        self._cg.add_lines(tmpl.format(prefix=self._iden_prefix))

    def _generate_member_name_cc_line(self, member_name):
        self._cg.add_cc_line(f'`{member_name}` field')

    def _save_serialization_action(self, name, action):
        self._saved_serialization_actions[name] = action

    def _get_open_close_ts_line(self, stream_type):
        def_clk_type = stream_type.default_clock_type

        if def_clk_type is None:
            return ''

        c_type = self._clk_type_c_type(def_clk_type)
        return f'\tconst {c_type} ts = ctx->parent.use_cur_last_event_ts ? ctx->cur_last_event_ts : ctx->parent.cbs.{def_clk_type.name}_clock_get_value(ctx->parent.data);'

    def _generate_func_open(self, stream_type):
        def generate_save_offset(name, action):
            self._cg.add_line(f'ctx->off_spc_{name} = ctx->parent.at;')
            self._save_serialization_action(name, action)

        self._generate_func_open_proto(stream_type)
        tmpl = barectf_templates._FUNC_OPEN_BODY_BEGIN
        pkt_ctx_ft = stream_type._pkt_ctx_ft
        ts_line = self._get_open_close_ts_line(stream_type)
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
        pkt_header_ft = self._trace_type._pkt_header_ft
        ser_actions = _SerializationActions()

        if pkt_header_ft is not None:
            self._cg.add_empty_line()
            self._cg.add_cc_line('trace packet header')
            self._cg.add_line('{')
            self._cg.indent()
            ser_actions.append_root_scope_ft(pkt_header_ft, _PREFIX_TPH)

            for action in ser_actions.actions:
                if type(action) is _AlignSerializationAction:
                    if action.names:
                        if len(action.names) == 1:
                            line = 'align trace packet header structure'
                        else:
                            line = f'align field `{action.names[-1]}`'

                        self._cg.add_cc_line(line)

                    self._generate_align('ctx->parent.at', action.value)
                    self._cg.add_empty_line()
                else:
                    assert type(action) is _SerializeSerializationAction
                    assert(len(action.names) >= 2)
                    member_name = action.names[-1]
                    line = f'serialize field `{member_name}`'
                    self._cg.add_cc_line(line)
                    src = _PREFIX_TPH + member_name

                    if member_name == 'magic':
                        src = '0xc1fc1fc1UL'
                    elif member_name == 'stream_id':
                        src = f'({self._get_ft_c_type(action.ft)}) {stream_type.id}'
                    elif member_name == 'uuid':
                        self._cg.add_line('{')
                        self._cg.indent()
                        self._cg.add_line('static uint8_t uuid[] = {')
                        self._cg.indent()

                        for b in self._trace_type.uuid.bytes:
                            self._cg.add_line(f'{b},')

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
        self._cg.add_empty_line()
        self._cg.add_cc_line('stream packet context')
        self._cg.add_line('{')
        self._cg.indent()
        ser_actions.append_root_scope_ft(pkt_ctx_ft, _PREFIX_SPC)

        for action in itertools.islice(ser_actions.actions, spc_action_index, None):
            if type(action) is _AlignSerializationAction:
                if action.names:
                    if len(action.names) == 1:
                        line = 'align stream packet context structure'
                    else:
                        line = f'align field `{action.names[-1]}`'

                    self._cg.add_cc_line(line)

                self._generate_align('ctx->parent.at', action.value)
                self._cg.add_empty_line()
            else:
                assert type(action) is _SerializeSerializationAction
                assert(len(action.names) >= 2)
                member_name = action.names[-1]
                line = f'serialize field `{member_name}`'
                self._cg.add_cc_line(line)
                src = _PREFIX_SPC + member_name
                skip_int = False

                if member_name == 'timestamp_begin':
                    src = f'({self._get_ft_c_type(action.ft)}) ts'
                elif member_name in {'timestamp_end', 'content_size', 'events_discarded'}:
                    skip_int = True
                elif member_name == 'packet_size':
                    src = f'({self._get_ft_c_type(action.ft)}) ctx->parent.packet_size'

                if skip_int:
                    generate_save_offset(member_name, action)
                    self._generate_incr_pos('ctx->parent.at', action.ft.size)
                else:
                    self._generate_serialize_from_action(src, '(&ctx->parent)', action)

                self._cg.add_empty_line()

        self._cg.unindent()
        self._cg.add_lines('}')
        self._cg.unindent()
        tmpl = barectf_templates._FUNC_OPEN_BODY_END
        self._cg.add_lines(tmpl)

    def _generate_func_close(self, stream_type):
        def generate_goto_offset(name):
            self._cg.add_line(f'ctx->parent.at = ctx->off_spc_{name};')

        self._generate_func_close_proto(stream_type)
        tmpl = barectf_templates._FUNC_CLOSE_BODY_BEGIN
        pkt_ctx_ft = stream_type._pkt_ctx_ft
        ts_line = self._get_open_close_ts_line(stream_type)
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
        member_name = 'timestamp_end'
        member = pkt_ctx_ft.members.get(member_name)

        if member is not None:
            self._cg.add_empty_line()
            self._generate_member_name_cc_line(member_name)
            generate_goto_offset(member_name)
            action = self._saved_serialization_actions[member_name]
            c_type = self._get_ft_c_type(member.field_type)
            self._generate_serialize_from_action(f'({c_type}) ts', '(&ctx->parent)', action)

        member_name = 'content_size'
        member = pkt_ctx_ft.members.get(member_name)

        if member is not None:
            self._cg.add_empty_line()
            self._generate_member_name_cc_line(member_name)
            generate_goto_offset(member_name)
            action = self._saved_serialization_actions[member_name]
            c_type = self._get_ft_c_type(member.field_type)
            self._generate_serialize_from_action(f'({c_type}) ctx->parent.content_size',
                                                 '(&ctx->parent)', action)

        member_name = 'events_discarded'
        member = pkt_ctx_ft.members.get(member_name)

        if member is not None:
            self._cg.add_empty_line()
            self._generate_member_name_cc_line(member_name)
            generate_goto_offset(member_name)
            action = self._saved_serialization_actions[member_name]
            c_type = self._get_ft_c_type(member.field_type)
            self._generate_serialize_from_action(f'({c_type}) ctx->parent.events_discarded',
                                                 '(&ctx->parent)', action)

        self._cg.unindent()
        tmpl = barectf_templates._FUNC_CLOSE_BODY_END
        self._cg.add_lines(tmpl)

    def generate_c_src(self, header_name):
        self._cg.reset()
        dt = datetime.datetime.now().isoformat()
        tmpl = barectf_templates._C_SRC
        self._cg.add_lines(tmpl.format(prefix=self._iden_prefix, header_filename=header_name,
                                       version=barectf_version.__version__, date=dt))
        self._cg.add_empty_line()

        # initialization function
        self._generate_func_init()
        self._cg.add_empty_line()

        for stream_type in self._trace_type.stream_types:
            self._generate_func_open(stream_type)
            self._cg.add_empty_line()
            self._generate_func_close(stream_type)
            self._cg.add_empty_line()
            ser_actions = _SerializationActions()

            if stream_type._ev_header_ft is not None:
                ser_actions.append_root_scope_ft(stream_type._ev_header_ft, _PREFIX_SEH)
                self._generate_func_serialize_event_header(stream_type, iter(ser_actions.actions))
                self._cg.add_empty_line()

            if stream_type.event_common_context_field_type is not None:
                ser_action_index = len(ser_actions.actions)
                ser_actions.append_root_scope_ft(stream_type.event_common_context_field_type,
                                                 _PREFIX_SEC)
                ser_action_iter = itertools.islice(ser_actions.actions, ser_action_index, None)
                self._generate_func_serialize_event_common_context(stream_type, ser_action_iter)
                self._cg.add_empty_line()

            for ev_type in stream_type.event_types:
                self._generate_func_get_event_size(stream_type, ev_type)
                self._cg.add_empty_line()
                self._generate_func_serialize_event(stream_type, ev_type, ser_actions)
                self._cg.add_empty_line()
                self._generate_func_trace(stream_type, ev_type)
                self._cg.add_empty_line()

        return self._cg.code
