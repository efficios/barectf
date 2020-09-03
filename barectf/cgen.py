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

import barectf.template as barectf_template
import barectf.config as barectf_config
import collections
import copy


# A tuple containing serialization and size computation function
# templates for a given operation.
_OpTemplates = collections.namedtuple('_OpTemplates', ['serialize', 'size'])


# Base class of any operation within source code.
#
# Any operation has:
#
# * An offset at which to start to write within the current byte.
#
# * A field type.
#
# * A list of names which, when joined with `_`, form the generic C
#   source variable name.
#
# * Serialization and size computation templates to generate the
#   operation's source code for those functions.
class _Op:
    def __init__(self, offset_in_byte, ft, names, templates):
        assert(offset_in_byte >= 0 and offset_in_byte < 8)
        self._offset_in_byte = offset_in_byte
        self._ft = ft
        self._names = copy.copy(names)
        self._templates = templates

    @property
    def offset_in_byte(self):
        return self._offset_in_byte

    @property
    def ft(self):
        return self._ft

    @property
    def names(self):
        return self._names

    @property
    def top_name(self):
        return self._names[-1]

    def _render_template(self, templ, **kwargs):
        return templ.render(op=self, root_ft_prefixes=_RootFtPrefixes,
                            root_ft_prefix_names=_ROOT_FT_PREFIX_NAMES, **kwargs)

    def serialize_str(self, **kwargs):
        return self._render_template(self._templates.serialize, **kwargs)

    def size_str(self, **kwargs):
        return self._render_template(self._templates.size, **kwargs)


# An "align" operation.
class _AlignOp(_Op):
    def __init__(self, offset_in_byte, ft, names, templates, value):
        super().__init__(offset_in_byte, ft, names, templates)
        self._value = value

    @property
    def value(self):
        return self._value


# A "write" operation.
class _WriteOp(_Op):
    pass


# A builder of a chain of operations.
#
# Such a builder is closely connected to a `_CodeGen` object using it to
# find generic templates.
#
# Call append_root_ft() to make an operation builder append operations
# to itself for each member, recursively, of the structure field type.
#
# Get an operation builder's operations with its `ops` property.
class _OpsBuilder:
    def __init__(self, cg):
        self._last_alignment = None
        self._last_bit_array_size = None
        self._ops = []
        self._names = []
        self._offset_in_byte = 0
        self._cg = cg

    @property
    def ops(self):
        return self._ops

    # Creates and appends the operations for the members, recursively,
    # of the root structure field type `ft` named `name`.
    #
    # `spec_serialize_write_templates` is a mapping of first level
    # member names to specialized serialization "write" templates.
    def append_root_ft(self, ft, name, spec_serialize_write_templates=None):
        if ft is None:
            return

        if spec_serialize_write_templates is None:
            spec_serialize_write_templates = {}

        assert type(ft) is barectf_config.StructureFieldType
        assert len(self._names) == 0
        self._append_ft(ft, name, spec_serialize_write_templates)

    # Creates and appends the operations of a given field type `ft`
    # named `name`.
    #
    # See append_root_ft() for `spec_serialize_write_templates`.
    def _append_ft(self, ft, name, spec_serialize_write_templates):
        def top_name():
            return self._names[-1]

        # Appends a "write" operation for the field type `ft`.
        #
        # This function considers `spec_serialize_write_templates` to
        # override generic templates.
        def append_write_op(ft):
            assert type(ft) is not barectf_config.StructureFieldType
            offset_in_byte = self._offset_in_byte

            if isinstance(ft, barectf_config._BitArrayFieldType):
                self._offset_in_byte += ft.size
                self._offset_in_byte %= 8

            serialize_write_templ = None

            if len(self._names) == 2:
                serialize_write_templ = spec_serialize_write_templates.get(top_name())

            if serialize_write_templ is None:
                if isinstance(ft, barectf_config._IntegerFieldType):
                    serialize_write_templ = self._cg._serialize_write_int_statements_templ
                elif type(ft) is barectf_config.RealFieldType:
                    serialize_write_templ = self._cg._serialize_write_real_statements_templ
                else:
                    assert type(ft) is barectf_config.StringFieldType
                    serialize_write_templ = self._cg._serialize_write_string_statements_templ

            size_write_templ = None

            if isinstance(ft, barectf_config._BitArrayFieldType):
                size_write_templ = self._cg._size_write_bit_array_statements_templ
            elif type(ft) is barectf_config.StringFieldType:
                size_write_templ = self._cg._size_write_string_statements_templ

            self._ops.append(_WriteOp(offset_in_byte, ft, self._names,
                                      _OpTemplates(serialize_write_templ, size_write_templ)))

        # Creates and appends an "align" operation for the field type
        # `ft` if needed.
        #
        # This function updates the builder's state.
        def try_append_align_op(alignment, do_align, ft):
            def align(v, alignment):
                return (v + (alignment - 1)) & -alignment

            offset_in_byte = self._offset_in_byte
            self._offset_in_byte = align(self._offset_in_byte, alignment) % 8

            if do_align and alignment > 1:
                self._ops.append(_AlignOp(offset_in_byte, ft, self._names,
                                          _OpTemplates(self._cg._serialize_align_statements_templ,
                                                       self._cg._size_align_statements_templ),
                                          alignment))

        # Returns whether or not, considering the alignment requirement
        # `align_req` and the builder's current state, we must create
        # and append an "align" operation.
        def must_align(align_req):
            return self._last_alignment != align_req or self._last_bit_array_size % align_req != 0

        # push field type's name to the builder's name stack initially
        self._names.append(name)

        if isinstance(ft, (barectf_config.StringFieldType, barectf_config._ArrayFieldType)):
            assert type(ft) is barectf_config.StringFieldType or top_name() == 'uuid'

            # strings and arrays are always byte-aligned
            do_align = must_align(8)
            self._last_alignment = 8
            self._last_bit_array_size = 8
            try_append_align_op(8, do_align, ft)
            append_write_op(ft)
        else:
            do_align = must_align(ft.alignment)
            self._last_alignment = ft.alignment

            if type(ft) is barectf_config.StructureFieldType:
                self._last_bit_array_size = ft.alignment
            else:
                self._last_bit_array_size = ft.size

            try_append_align_op(ft.alignment, do_align, ft)

            if type(ft) is barectf_config.StructureFieldType:
                for member_name, member in ft.members.items():
                    self._append_ft(member.field_type, member_name, spec_serialize_write_templates)
            else:
                append_write_op(ft)

        # exiting for this field type: pop its name
        del self._names[-1]


# The operations for an event.
#
# The available operations are:
#
# * Specific context operations.
# * Payload operations.
class _EventOps:
    def __init__(self, spec_ctx_ops, payload_ops):
        self._spec_ctx_ops = copy.copy(spec_ctx_ops)
        self._payload_ops = copy.copy(payload_ops)

    @property
    def spec_ctx_ops(self):
        return self._spec_ctx_ops

    @property
    def payload_ops(self):
        return self._payload_ops


# The operations for a stream.
#
# The available operations are:
#
# * Packet header operations.
# * Packet context operations.
# * Event header operations.
# * Event common context operations.
# * Event operations (`_EventOps`).
class _StreamOps:
    def __init__(self, pkt_header_ops, pkt_ctx_ops, ev_header_ops,
                 ev_common_ctx_ops, ev_ops):
        self._pkt_header_ops = copy.copy(pkt_header_ops)
        self._pkt_ctx_ops = copy.copy(pkt_ctx_ops)
        self._ev_header_ops = copy.copy(ev_header_ops)
        self._ev_common_ctx_ops = copy.copy(ev_common_ctx_ops)
        self._ev_ops = copy.copy(ev_ops)

    @property
    def pkt_header_ops(self):
        return self._pkt_header_ops

    @property
    def pkt_ctx_ops(self):
        return self._pkt_ctx_ops

    @property
    def ev_header_ops(self):
        return self._ev_header_ops

    @property
    def ev_common_ctx_ops(self):
        return self._ev_common_ctx_ops

    @property
    def ev_ops(self):
        return self._ev_ops


# The C variable name prefixes for the six kinds of root field types.
class _RootFtPrefixes:
    PH = 'ph'
    PC = 'pc'
    EH = 'eh'
    ECC = 'ecc'
    SC = 'sc'
    P = 'p'


# The human-readable names of the `_RootFtPrefixes` members.
_ROOT_FT_PREFIX_NAMES = {
    _RootFtPrefixes.PH: 'packet header',
    _RootFtPrefixes.PC: 'packet context',
    _RootFtPrefixes.EH: 'event header',
    _RootFtPrefixes.ECC: 'event common context',
    _RootFtPrefixes.SC: 'specific context',
    _RootFtPrefixes.P: 'payload',
}


# A named function parameter for a given field type.
_FtParam = collections.namedtuple('_FtParam', ['ft', 'name'])


# A C code generator.
#
# Such a code generator can generate:
#
# * The bitfield header (gen_bitfield_header()).
# * The public header (gen_header()).
# * The source code (gen_src()).
class _CodeGen:
    def __init__(self, cfg):
        self._cfg = cfg
        self._iden_prefix = cfg.options.code_generation_options.identifier_prefix
        self._saved_serialization_ops = {}
        self._templ_filters = {
            'ft_c_type': self._ft_c_type,
            'open_func_params_str': self._open_func_params_str,
            'trace_func_params_str': self._trace_func_params_str,
            'serialize_ev_common_ctx_func_params_str': self._serialize_ev_common_ctx_func_params_str,
        }
        self._func_proto_params_templ = self._create_template('func-proto-params.j2')
        self._serialize_align_statements_templ = self._create_template('serialize-align-statements.j2')
        self._serialize_write_int_statements_templ = self._create_template('serialize-write-int-statements.j2')
        self._serialize_write_real_statements_templ = self._create_template('serialize-write-real-statements.j2')
        self._serialize_write_string_statements_templ = self._create_template('serialize-write-string-statements.j2')
        self._serialize_write_magic_statements_templ = self._create_template('serialize-write-magic-statements.j2')
        self._serialize_write_uuid_statements_templ = self._create_template('serialize-write-uuid-statements.j2')
        self._serialize_write_stream_type_id_statements_templ = self._create_template('serialize-write-stream-type-id-statements.j2')
        self._serialize_write_time_statements_templ = self._create_template('serialize-write-time-statements.j2')
        self._serialize_write_packet_size_statements_templ = self._create_template('serialize-write-packet-size-statements.j2')
        self._serialize_write_skip_save_statements_templ = self._create_template('serialize-write-skip-save-statements.j2')
        self._serialize_write_ev_type_id_statements_templ = self._create_template('serialize-write-ev-type-id-statements.j2')
        self._size_align_statements_templ = self._create_template('size-align-statements.j2')
        self._size_write_bit_array_statements_templ = self._create_template('size-write-bit-array-statements.j2')
        self._size_write_string_statements_templ = self._create_template('size-write-string-statements.j2')

    # Creates and returns a template named `name` which is a file
    # template if `is_file_template` is `True`.
    #
    # `name` is the file name, including the `.j2` extension, within the
    # `c` directory.
    #
    # Such a template has the filters custom filters
    # `self._templ_filters`.
    def _create_template_base(self, name: str, is_file_template: bool):
        return barectf_template._Template(f'c/{name}', is_file_template, self._cfg,
                                          self._templ_filters)

    # Creates and returns a non-file template named `name`.
    #
    # See _create_template_base() for `name`.
    def _create_template(self, name: str) -> barectf_template._Template:
        return self._create_template_base(name, False)

    # Creates and returns a file template named `name`.
    #
    # See _create_template_base() for `name`.
    def _create_file_template(self, name: str) -> barectf_template._Template:
        return self._create_template_base(name, True)

    # Trace type of this code generator's barectf configuration.
    @property
    def _trace_type(self):
        return self._cfg.trace.type

    # Returns the C type for the field type `ft`, returning a `const` C
    # type if `is_const` is `True`.
    def _ft_c_type(self, ft, is_const=False):
        const_beg_str = 'const '

        if isinstance(ft, barectf_config._IntegerFieldType):
            sign_prefix = 'u' if isinstance(ft, barectf_config.UnsignedIntegerFieldType) else ''

            if ft.size <= 8:
                sz = 8
            elif ft.size <= 16:
                sz = 16
            elif ft.size <= 32:
                sz = 32
            else:
                assert ft.size <= 64
                sz = 64

            return f'{const_beg_str if is_const else ""}{sign_prefix}int{sz}_t'
        elif type(ft) is barectf_config.RealFieldType:
            if ft.size == 32 and ft.alignment == 32:
                c_type = 'float'
            elif ft.size == 64 and ft.alignment == 64:
                c_type = 'double'
            else:
                c_type = 'uint64_t'

            return f'{const_beg_str if is_const else ""}{c_type}'
        else:
            assert type(ft) is barectf_config.StringFieldType
            return f'const char *{" const" if is_const else ""}'

    # Returns the function prototype parameters for the members of the
    # root structure field type `root_ft`.
    #
    # Each parameter has the prefix `name_prefix` followed with `_`.
    #
    # Members of which the name is in `exclude_set` are excluded.
    def _proto_params_str(self, root_ft, name_prefix, const_params, exclude_set=None):
        if root_ft is None:
            return

        if exclude_set is None:
            exclude_set = set()

        params = []

        for member_name, member in root_ft.members.items():
            if member_name in exclude_set:
                continue

            params.append(_FtParam(member.field_type, member_name))

        return self._func_proto_params_templ.render(params=params, prefix=name_prefix,
                                                    const_params=const_params)

    # Returns the packet opening function prototype parameters for the
    # stream type `stream_type`.
    def _open_func_params_str(self, stream_type, const_params):
        parts = []
        parts.append(self._proto_params_str(self._trace_type._pkt_header_ft, _RootFtPrefixes.PH,
                                            const_params, {'magic', 'stream_id', 'uuid'}))

        exclude_set = {
            'timestamp_begin',
            'timestamp_end',
            'packet_size',
            'content_size',
            'events_discarded',
        }
        parts.append(self._proto_params_str(stream_type._pkt_ctx_ft, _RootFtPrefixes.PC,
                                            const_params, exclude_set))
        return ''.join(parts)

    # Returns the tracing function prototype parameters for the stream
    # and event types `stream_ev_types`.
    def _trace_func_params_str(self, stream_ev_types, const_params):
        stream_type = stream_ev_types[0]
        ev_type = stream_ev_types[1]
        parts = []

        if stream_type._ev_header_ft is not None:
            parts.append(self._proto_params_str(stream_type._ev_header_ft, _RootFtPrefixes.EH,
                                                const_params, {'id', 'timestamp'}))

        if stream_type.event_common_context_field_type is not None:
            parts.append(self._proto_params_str(stream_type.event_common_context_field_type,
                                                _RootFtPrefixes.ECC, const_params))

        if ev_type.specific_context_field_type is not None:
            parts.append(self._proto_params_str(ev_type.specific_context_field_type,
                                                _RootFtPrefixes.SC, const_params))

        if ev_type.payload_field_type is not None:
            parts.append(self._proto_params_str(ev_type.payload_field_type, _RootFtPrefixes.P,
                                                const_params))

        return ''.join(parts)

    # Returns the event header serialization function prototype
    # parameters for the stream type `stream_type`.
    def _serialize_ev_common_ctx_func_params_str(self, stream_type, const_params):
        return self._proto_params_str(stream_type.event_common_context_field_type,
                                      _RootFtPrefixes.ECC, const_params);

    # Generates the bitfield header file contents.
    def gen_bitfield_header(self):
        return self._create_file_template('bitfield.h.j2').render()

    # Generates the public header file contents.
    def gen_header(self):
        return self._create_file_template('barectf.h.j2').render(root_ft_prefixes=_RootFtPrefixes)

    # Generates the source code file contents.
    def gen_src(self, header_file_name, bitfield_header_file_name):
        # Creates and returns the operations for all the stream and for
        # all their events.
        def create_stream_ops():
            stream_ser_ops = {}

            for stream_type in self._trace_type.stream_types:
                pkt_header_ser_ops = []
                builder = _OpsBuilder(self)
                pkt_header_ft = self._trace_type._pkt_header_ft

                # packet header serialization operations
                if pkt_header_ft is not None:
                    spec_serialize_write_templates = {
                        'magic': self._serialize_write_magic_statements_templ,
                        'uuid': self._serialize_write_uuid_statements_templ,
                        'stream_id': self._serialize_write_stream_type_id_statements_templ,
                    }
                    builder.append_root_ft(pkt_header_ft, _RootFtPrefixes.PH,
                                           spec_serialize_write_templates)
                    pkt_header_ser_ops = copy.copy(builder.ops)

                # packet context serialization operations
                first_op_index = len(builder.ops)
                spec_serialize_write_templates = {
                    'timestamp_begin': self._serialize_write_time_statements_templ,
                    'packet_size': self._serialize_write_packet_size_statements_templ,
                    'timestamp_end': self._serialize_write_skip_save_statements_templ,
                    'events_discarded': self._serialize_write_skip_save_statements_templ,
                    'content_size': self._serialize_write_skip_save_statements_templ,
                }
                builder.append_root_ft(stream_type._pkt_ctx_ft, _RootFtPrefixes.PC,
                                       spec_serialize_write_templates)
                pkt_ctx_ser_ops = copy.copy(builder.ops[first_op_index:])

                # event header serialization operations
                builder = _OpsBuilder(self)
                ev_header_ser_ops = []

                if stream_type._ev_header_ft is not None:
                    spec_serialize_write_templates = {
                        'timestamp': self._serialize_write_time_statements_templ,
                        'id': self._serialize_write_ev_type_id_statements_templ,
                    }
                    builder.append_root_ft(stream_type._ev_header_ft, _RootFtPrefixes.EH,
                                           spec_serialize_write_templates)
                    ev_header_ser_ops = copy.copy(builder.ops)

                # event common context serialization operations
                ev_common_ctx_ser_ops = []

                if stream_type.event_common_context_field_type is not None:
                    first_op_index = len(builder.ops)
                    builder.append_root_ft(stream_type.event_common_context_field_type,
                                           _RootFtPrefixes.ECC)
                    ev_common_ctx_ser_ops = copy.copy(builder.ops[first_op_index:])

                # serialization operations specific to each event type
                ev_ser_ops = {}

                for ev_type in stream_type.event_types:
                    ev_builder = copy.copy(builder)

                    # specific context serialization operations
                    spec_ctx_ser_ops = []

                    if ev_type.specific_context_field_type is not None:
                        first_op_index = len(ev_builder.ops)
                        ev_builder.append_root_ft(ev_type.specific_context_field_type,
                                                  _RootFtPrefixes.SC)
                        spec_ctx_ser_ops = copy.copy(ev_builder.ops[first_op_index:])

                    # payload serialization operations
                    payload_ser_ops = []

                    if ev_type.payload_field_type is not None:
                        first_op_index = len(ev_builder.ops)
                        ev_builder.append_root_ft(ev_type.payload_field_type, _RootFtPrefixes.P)
                        payload_ser_ops = copy.copy(ev_builder.ops[first_op_index:])

                    ev_ser_ops[ev_type] = _EventOps(spec_ctx_ser_ops, payload_ser_ops)

                stream_ser_ops[stream_type] = _StreamOps(pkt_header_ser_ops, pkt_ctx_ser_ops,
                                                         ev_header_ser_ops, ev_common_ctx_ser_ops,
                                                         ev_ser_ops)

            return stream_ser_ops

        # Returns the "write" operation for the packet context member
        # named `member_name` within the stream type `stream_type`.
        def stream_op_pkt_ctx_op(stream_type, member_name):
            for op in stream_ops[stream_type].pkt_ctx_ops:
                if op.top_name == member_name and type(op) is _WriteOp:
                    return op

        stream_ops = create_stream_ops()
        return self._create_file_template('barectf.c.j2').render(header_file_name=header_file_name,
                                                                 bitfield_header_file_name=bitfield_header_file_name,
                                                                 root_ft_prefixes=_RootFtPrefixes,
                                                                 root_ft_prefix_names=_ROOT_FT_PREFIX_NAMES,
                                                                 stream_ops=stream_ops,
                                                                 stream_op_pkt_ctx_op=stream_op_pkt_ctx_op)
