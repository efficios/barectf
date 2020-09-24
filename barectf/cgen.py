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
from typing import List, Optional, Mapping, Callable, Any, Set, Tuple
import typing
from barectf.typing import Count, Alignment


# A tuple containing serialization and size computation function
# templates for a given operation.
_OpTemplates = collections.namedtuple('_OpTemplates', ['serialize', 'size'])


# Abstract base class of any operation within source code.
#
# Any operation has:
#
# * A field type.
#
# * A list of names which, when joined with `_`, form the generic
#   C source variable name.
#
# * A level: how deep this operation is within the operation tree.
#
# * Serialization and size computation templates to generate the
#   operation's source code for those functions.
class _Op:
    def __init__(self, ft: barectf_config._FieldType, names: List[str], level: Count,
                 templates: _OpTemplates):
        self._ft = ft
        self._names = copy.copy(names)
        self._level = level
        self._templates = templates

    @property
    def ft(self) -> barectf_config._FieldType:
        return self._ft

    @property
    def names(self) -> List[str]:
        return self._names

    @property
    def level(self) -> Count:
        return self._level

    @property
    def top_name(self) -> str:
        return self._names[-1]

    def _render_template(self, templ: barectf_template._Template, **kwargs) -> str:
        return templ.render(op=self, root_ft_prefixes=_RootFtPrefixes,
                            root_ft_prefix_names=_ROOT_FT_PREFIX_NAMES, **kwargs)

    def serialize_str(self, **kwargs) -> str:
        return self._render_template(self._templates.serialize, **kwargs)

    def size_str(self, **kwargs) -> str:
        return self._render_template(self._templates.size, **kwargs)


# Compound operation.
#
# A compound operation contains a list of suboperations (leaf or
# compound).
#
# Get the suboperations of a compound operation with its `subops`
# property.
#
# The templates of a compound operation handles its suboperations.
class _CompoundOp(_Op):
    def __init__(self, ft: barectf_config._FieldType, names: List[str], level: Count,
                 templates: _OpTemplates, subops: List[Any] = None):
        super().__init__(ft, names, level, templates)
        self._subops = subops

    @property
    def subops(self):
        return self._subops


# Leaf operation (abstract class).
class _LeafOp(_Op):
    pass


# An "align" operation.
class _AlignOp(_LeafOp):
    def __init__(self, ft: barectf_config._FieldType, names: List[str], level: Count,
                 templates: _OpTemplates, value: Alignment):
        super().__init__(ft, names, level, templates)
        self._value = value

    @property
    def value(self) -> Alignment:
        return self._value


# A "write" operation.
class _WriteOp(_LeafOp):
    def __init__(self, ft: barectf_config._FieldType, names: List[str], level: Count,
                 templates: _OpTemplates, offset_in_byte: Optional[Count]):
        super().__init__(ft, names, level, templates)
        assert offset_in_byte is None or (offset_in_byte >= 0 and offset_in_byte < 8)
        self._offset_in_byte = offset_in_byte

    @property
    def offset_in_byte(self) -> Optional[Count]:
        return self._offset_in_byte


_SpecSerializeWriteTemplates = Mapping[str, barectf_template._Template]


# An operation builder.
#
# Such a builder is closely connected to a `_CodeGen` object using it to
# find generic templates.
#
# Call build_for_root_ft() to make an operation builder create a
# compound operation for a given root structure field type, recursively,
# and return it.
class _OpBuilder:
    def __init__(self, cg: '_CodeGen'):
        self._names: List[str] = []
        self._level = Count(0)
        self._offset_in_byte: Optional[Count] = None
        self._cg = cg

    # Whether or not we're within an array operation.
    @property
    def _in_array(self):
        return self._level > 0

    # Creates and returns an operation for the root structure field type
    # `ft` named `name`.
    #
    # `spec_serialize_write_templates` is a mapping of first level
    # member names to specialized serialization "write" templates.
    def build_for_root_ft(self, ft: barectf_config.StructureFieldType, name: str,
                          spec_serialize_write_templates: Optional[_SpecSerializeWriteTemplates] = None) -> _CompoundOp:
        assert ft is not None

        if spec_serialize_write_templates is None:
            spec_serialize_write_templates = {}

        assert type(ft) is barectf_config.StructureFieldType
        assert len(self._names) == 0
        assert self._level == 0
        ops = self._build_for_ft(ft, name, spec_serialize_write_templates)
        assert len(ops) == 1
        assert type(ops[0]) is _CompoundOp
        return typing.cast(_CompoundOp, ops[0])

    # Creates and returns the operation(s) for a given field type `ft`
    # named `name`.
    #
    # See build_for_root_ft() for `spec_serialize_write_templates`.
    def _build_for_ft(self, ft: barectf_config._FieldType, name: str,
                      spec_serialize_write_templates: _SpecSerializeWriteTemplates) -> List[_Op]:
        def top_name() -> str:
            return self._names[-1]

        # Creates and returns a "write" operation for the field type
        # `ft`.
        #
        # This function considers `spec_serialize_write_templates` to
        # override generic templates.
        def create_write_op(ft: barectf_config._FieldType) -> _WriteOp:
            assert type(ft) is not barectf_config.StructureFieldType
            offset_in_byte = self._offset_in_byte

            if isinstance(ft, barectf_config._BitArrayFieldType) and self._offset_in_byte is not None:
                self._offset_in_byte = Count((self._offset_in_byte + ft.size) % 8)

            serialize_write_templ: Optional[barectf_template._Template] = None

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

            return _WriteOp(ft, self._names, self._level,
                            _OpTemplates(serialize_write_templ, size_write_templ), offset_in_byte)

        # Creates and returns an "align" operation for the field type
        # `ft` if needed.
        #
        # This function updates the builder's state.
        def try_create_align_op(alignment: Alignment, ft: barectf_config._FieldType) -> Optional[_AlignOp]:
            def align(v: Count, alignment: Alignment) -> Count:
                return Count((v + (alignment - 1)) & -alignment)

            if self._offset_in_byte is None and alignment % 8 == 0:
                self._offset_in_byte = Count(0)
            else:
                if self._in_array:
                    self._offset_in_byte = None
                elif self._offset_in_byte is not None:
                    self._offset_in_byte = Count(align(self._offset_in_byte, alignment) % 8)

            if alignment > 1:
                return _AlignOp(ft, self._names, self._level,
                                _OpTemplates(self._cg._serialize_align_statements_templ,
                                             self._cg._size_align_statements_templ),
                                alignment)

            return None

        # Returns whether or not `ft` is a compound field type.
        def ft_is_compound(ft: barectf_config._FieldType) -> bool:
            return isinstance(ft, (barectf_config.StructureFieldType, barectf_config.StaticArrayFieldType))

        # push field type's name to the builder's name stack initially
        self._names.append(name)

        # operations to return
        ops: List[_Op] = []

        if type(ft) is barectf_config.StringFieldType or self._names == [_RootFtPrefixes.PH, 'uuid']:
            # strings and UUID array are always byte-aligned
            op = try_create_align_op(Alignment(8), ft)

            if op is not None:
                ops.append(op)

            ops.append(create_write_op(ft))
        else:
            if ft_is_compound(ft):
                self._offset_in_byte = None

            init_align_op = try_create_align_op(ft.alignment, ft)
            subops: List[_Op] = []

            if type(ft) is barectf_config.StructureFieldType:
                ft = typing.cast(barectf_config.StructureFieldType, ft)

                if init_align_op is not None:
                    # Append structure field's alignment as a
                    # suboperation.
                    #
                    # This is not strictly needed (could be appended to
                    # `ops`), but the properties of `_DsOps` and
                    # `_ErOps` offer a single (structure field type)
                    # operation.
                    subops.append(init_align_op)

                # append suboperations for each member
                for member_name, member in ft.members.items():
                    subops += self._build_for_ft(member.field_type, member_name,
                                                 spec_serialize_write_templates)

                # create structure field's compound operation
                ops.append(_CompoundOp(ft, self._names, self._level,
                                       _OpTemplates(self._cg._serialize_write_struct_statements_templ,
                                                    self._cg._size_write_struct_statements_templ),
                                       subops))
            elif isinstance(ft, barectf_config._ArrayFieldType):
                ft = typing.cast(barectf_config._ArrayFieldType, ft)
                assert ft.alignment == 1 or init_align_op is not None

                if init_align_op is not None:
                    ops.append(init_align_op)

                # append element's suboperations
                self._level = Count(self._level + 1)
                subops += self._build_for_ft(ft.element_field_type,
                                             f'[{_loop_var_name(Count(self._level - 1))}]',
                                             spec_serialize_write_templates)
                self._level = Count(self._level - 1)

                # select the right templates
                if type(ft) is barectf_config.StaticArrayFieldType:
                    templates = _OpTemplates(self._cg._serialize_write_static_array_statements_templ,
                                             self._cg._size_write_static_array_statements_templ)
                else:
                    assert type(ft) is barectf_config.DynamicArrayFieldType
                    templates = _OpTemplates(self._cg._serialize_write_dynamic_array_statements_templ,
                                             self._cg._size_write_dynamic_array_statements_templ)

                # create array field's compound operation
                ops.append(_CompoundOp(ft, self._names, self._level, templates, subops))
            else:
                # leaf field: align + write
                if init_align_op is not None:
                    ops.append(init_align_op)

                ops.append(create_write_op(ft))

        # exiting for this field type: pop its name
        del self._names[-1]

        return ops


_OptCompoundOp = Optional[_CompoundOp]


# The operations for an event record.
#
# The available operations are:
#
# * Specific context operation.
# * Payload operation.
class _ErOps:
    def __init__(self, spec_ctx_op: _OptCompoundOp, payload_op: _OptCompoundOp):
        self._spec_ctx_op = spec_ctx_op
        self._payload_op = payload_op

    @property
    def spec_ctx_op(self) -> _OptCompoundOp:
        return self._spec_ctx_op

    @property
    def payload_op(self) -> _OptCompoundOp:
        return self._payload_op


_ErOpsMap = Mapping[barectf_config.EventRecordType, _ErOps]


# The operations for a data stream.
#
# The available operations are:
#
# * Packet header operation.
# * Packet context operation.
# * Event record header operation.
# * Event record common context operation.
# * Event record operations (`_ErOps`).
class _DsOps:
    def __init__(self, pkt_header_op: _OptCompoundOp, pkt_ctx_op: _CompoundOp,
                 er_header_op: _OptCompoundOp, er_common_ctx_op: _OptCompoundOp, er_ops: _ErOpsMap):
        self._pkt_header_op = pkt_header_op
        self._pkt_ctx_op = pkt_ctx_op
        self._er_header_op = er_header_op
        self._er_common_ctx_op = er_common_ctx_op
        self._er_ops = er_ops

    @property
    def pkt_header_op(self) -> _OptCompoundOp:
        return self._pkt_header_op

    @property
    def pkt_ctx_op(self) -> _CompoundOp:
        return self._pkt_ctx_op

    @property
    def er_header_op(self) -> _OptCompoundOp:
        return self._er_header_op

    @property
    def er_common_ctx_op(self) -> _OptCompoundOp:
        return self._er_common_ctx_op

    @property
    def er_ops(self) -> _ErOpsMap:
        return self._er_ops


# The C variable name prefixes for the six kinds of root field types.
class _RootFtPrefixes:
    PH = 'ph'
    PC = 'pc'
    ERH = 'h'
    ERCC = 'cc'
    ERSC = 'sc'
    ERP = 'p'


# The human-readable names of the `_RootFtPrefixes` members.
_ROOT_FT_PREFIX_NAMES = {
    _RootFtPrefixes.PH: 'packet header',
    _RootFtPrefixes.PC: 'packet context',
    _RootFtPrefixes.ERH: 'header',
    _RootFtPrefixes.ERCC: 'common context',
    _RootFtPrefixes.ERSC: 'specific context',
    _RootFtPrefixes.ERP: 'payload',
}


# A named function parameter for a given field type.
_FtParam = collections.namedtuple('_FtParam', ['ft', 'name'])


# C type abstract base class.
class _CType:
    def __init__(self, is_const: bool):
        self._is_const = is_const

    @property
    def is_const(self) -> bool:
        return self._is_const


# Arithmetic C type.
class _ArithCType(_CType):
    def __init__(self, name: str, is_const: bool):
        super().__init__(is_const)
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def __str__(self) -> str:
        return f'{"const " if self._is_const else ""}{self._name}'


# Pointer C type.
class _PointerCType(_CType):
    def __init__(self, pointed_c_type: _CType, is_const: bool):
        super().__init__(is_const)
        self._pointed_c_type = pointed_c_type

    @property
    def pointed_c_type(self) -> _CType:
        return self._pointed_c_type

    def __str__(self) -> str:
        s = str(self._pointed_c_type)

        if not s.endswith('*'):
            s += ' '

        s += '*'

        if self._is_const:
            s += ' const'

        return s


# Returns the name of a loop variable given a nesting level `level`.
def _loop_var_name(level: Count) -> str:
    if level < 3:
        return 'ijk'[level]

    return f'k{level - 2}'


# A C code generator.
#
# Such a code generator can generate:
#
# * The bitfield header (gen_bitfield_header()).
# * The public header (gen_header()).
# * The source code (gen_src()).
class _CodeGen:
    def __init__(self, cfg: barectf_config.Configuration):
        self._cfg = cfg
        self._iden_prefix = cfg.options.code_generation_options.identifier_prefix
        self._templ_filters: Mapping[str, Callable[..., Any]] = {
            'ft_c_type': self._ft_c_type,
            'open_func_params_str': self._open_func_params_str,
            'trace_func_params_str': self._trace_func_params_str,
            'serialize_er_common_ctx_func_params_str': self._serialize_er_common_ctx_func_params_str,
            'loop_var_name': _loop_var_name,
            'op_src_var_name': self._op_src_var_name,
        }
        self._func_proto_params_templ = self._create_template('func-proto-params.j2')
        self._serialize_align_statements_templ = self._create_template('serialize-align-statements.j2')
        self._serialize_write_int_statements_templ = self._create_template('serialize-write-int-statements.j2')
        self._serialize_write_real_statements_templ = self._create_template('serialize-write-real-statements.j2')
        self._serialize_write_string_statements_templ = self._create_template('serialize-write-string-statements.j2')
        self._serialize_write_struct_statements_templ = self._create_template('serialize-write-struct-statements.j2')
        self._serialize_write_static_array_statements_templ = self._create_template('serialize-write-static-array-statements.j2')
        self._serialize_write_dynamic_array_statements_templ = self._create_template('serialize-write-dynamic-array-statements.j2')
        self._serialize_write_magic_statements_templ = self._create_template('serialize-write-magic-statements.j2')
        self._serialize_write_uuid_statements_templ = self._create_template('serialize-write-uuid-statements.j2')
        self._serialize_write_dst_id_statements_templ = self._create_template('serialize-write-dst-id-statements.j2')
        self._serialize_write_timestamp_statements_templ = self._create_template('serialize-write-timestamp-statements.j2')
        self._serialize_write_packet_size_statements_templ = self._create_template('serialize-write-packet-size-statements.j2')
        self._serialize_write_skip_save_statements_templ = self._create_template('serialize-write-skip-save-statements.j2')
        self._serialize_write_ert_id_statements_templ = self._create_template('serialize-write-ert-id-statements.j2')
        self._size_align_statements_templ = self._create_template('size-align-statements.j2')
        self._size_write_bit_array_statements_templ = self._create_template('size-write-bit-array-statements.j2')
        self._size_write_string_statements_templ = self._create_template('size-write-string-statements.j2')
        self._size_write_struct_statements_templ = self._create_template('size-write-struct-statements.j2')
        self._size_write_static_array_statements_templ = self._create_template('size-write-static-array-statements.j2')
        self._size_write_dynamic_array_statements_templ = self._create_template('size-write-dynamic-array-statements.j2')

    # Creates and returns a template named `name` which is a file
    # template if `is_file_template` is `True`.
    #
    # `name` is the file name, including the `.j2` extension, within the
    # `c` directory.
    #
    # Such a template has the filters custom filters
    # `self._templ_filters`.
    def _create_template_base(self, name: str,
                              is_file_template: bool) -> barectf_template._Template:
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
    def _trace_type(self) -> barectf_config.TraceType:
        return self._cfg.trace.type

    # Returns the name of a source variable for the operation `op`.
    def _op_src_var_name(self, op: _LeafOp) -> str:
        s = ''

        for index, name in enumerate(op.names):
            if index > 0 and not name.startswith('['):
                s += '_'

            s += name

        return s

    # Returns the C type for the field type `ft`, making it `const` if
    # `is_const` is `True`.
    def _ft_c_type(self, ft: barectf_config._FieldType, is_const: bool = False):
        if isinstance(ft, barectf_config._IntegerFieldType):
            ft = typing.cast(barectf_config._IntegerFieldType, ft)
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

            return _ArithCType(f'{sign_prefix}int{sz}_t', is_const)
        elif type(ft) is barectf_config.RealFieldType:
            ft = typing.cast(barectf_config.RealFieldType, ft)

            if ft.size == 32 and ft.alignment == 32:
                s = 'float'
            elif ft.size == 64 and ft.alignment == 64:
                s = 'double'
            else:
                s = 'uint64_t'

            return _ArithCType(s, is_const)
        elif type(ft) is barectf_config.StringFieldType:
            return _PointerCType(_ArithCType('char', True), is_const)
        else:
            assert isinstance(ft, barectf_config._ArrayFieldType)
            ft = typing.cast(barectf_config._ArrayFieldType, ft)
            return _PointerCType(self._ft_c_type(ft.element_field_type, True), is_const)

    # Returns the function prototype parameters for the members of the
    # root structure field type `root_ft`.
    #
    # Each parameter has the prefix `name_prefix` followed with `_`.
    #
    # Members of which the name is in `exclude_set` are excluded.
    def _proto_params_str(self, root_ft: Optional[barectf_config.StructureFieldType],
                          name_prefix: str, const_params: bool,
                          exclude_set: Optional[Set[str]] = None, only_dyn: bool = False) -> str:
        if root_ft is None:
            return ''

        if exclude_set is None:
            exclude_set = set()

        params = []

        for member_name, member in root_ft.members.items():
            if member_name in exclude_set:
                continue

            is_dyn = member.field_type.size_is_dynamic

            if isinstance(member.field_type, barectf_config.UnsignedIntegerFieldType):
                ft = typing.cast(barectf_config.UnsignedIntegerFieldType, member.field_type)
                is_dyn = is_dyn or ft._is_len

            if only_dyn and not is_dyn:
                continue

            params.append(_FtParam(member.field_type, member_name))

        return self._func_proto_params_templ.render(params=params, prefix=name_prefix,
                                                    const_params=const_params)

    # Returns the packet opening function prototype parameters for the
    # data stream type `dst`.
    def _open_func_params_str(self, dst: barectf_config.DataStreamType, const_params: bool) -> str:
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
        parts.append(self._proto_params_str(dst._pkt_ctx_ft, _RootFtPrefixes.PC, const_params,
                                            exclude_set))
        return ''.join(parts)

    # Returns the tracing function prototype parameters for the data
    # stream and event record types `ds_er_types`.
    def _trace_func_params_str(self, ds_er_types: Tuple[barectf_config.DataStreamType,
                                                        barectf_config.EventRecordType],
                               const_params: bool, only_dyn: bool = False):
        dst = ds_er_types[0]
        ert = ds_er_types[1]
        parts = []

        if dst._er_header_ft is not None:
            parts.append(self._proto_params_str(dst._er_header_ft, _RootFtPrefixes.ERH,
                                                const_params, {'id', 'timestamp'},
                                                only_dyn=only_dyn))

        if dst.event_record_common_context_field_type is not None:
            parts.append(self._proto_params_str(dst.event_record_common_context_field_type,
                                                _RootFtPrefixes.ERCC, const_params,
                                                only_dyn=only_dyn))

        if ert.specific_context_field_type is not None:
            parts.append(self._proto_params_str(ert.specific_context_field_type,
                                                _RootFtPrefixes.ERSC, const_params,
                                                only_dyn=only_dyn))

        if ert.payload_field_type is not None:
            parts.append(self._proto_params_str(ert.payload_field_type, _RootFtPrefixes.ERP,
                                                const_params, only_dyn=only_dyn))

        return ''.join(parts)

    # Returns the event record common context serialization function
    # prototype parameters for the data stream type `dst`.
    def _serialize_er_common_ctx_func_params_str(self, dst: barectf_config.DataStreamType,
                                                 const_params: bool) -> str:
        return self._proto_params_str(dst.event_record_common_context_field_type,
                                      _RootFtPrefixes.ERCC, const_params)

    # Generates the bitfield header file contents.
    def gen_bitfield_header(self) -> str:
        return self._create_file_template('bitfield.h.j2').render()

    # Generates the public header file contents.
    def gen_header(self) -> str:
        return self._create_file_template('barectf.h.j2').render(root_ft_prefixes=_RootFtPrefixes)

    # Generates the source code file contents.
    def gen_src(self, header_file_name: str, bitfield_header_file_name: str) -> str:
        # Creates and returns the operations for all the data stream and
        # for all their event records.
        def create_ds_ops() -> Mapping[barectf_config.DataStreamType, _DsOps]:
            ds_ops = {}

            for dst in self._trace_type.data_stream_types:
                pkt_header_op = None
                builder = _OpBuilder(self)
                pkt_header_ft = self._trace_type._pkt_header_ft

                # packet header operations
                if pkt_header_ft is not None:
                    spec_serialize_write_templates = {
                        'magic': self._serialize_write_magic_statements_templ,
                        'uuid': self._serialize_write_uuid_statements_templ,
                        'stream_id': self._serialize_write_dst_id_statements_templ,
                    }
                    pkt_header_op = builder.build_for_root_ft(pkt_header_ft,
                                                                  _RootFtPrefixes.PH,
                                                                  spec_serialize_write_templates)

                # packet context operation
                spec_serialize_write_templates = {
                    'timestamp_begin': self._serialize_write_timestamp_statements_templ,
                    'packet_size': self._serialize_write_packet_size_statements_templ,
                    'timestamp_end': self._serialize_write_skip_save_statements_templ,
                    'events_discarded': self._serialize_write_skip_save_statements_templ,
                    'content_size': self._serialize_write_skip_save_statements_templ,
                }
                pkt_ctx_op = builder.build_for_root_ft(dst._pkt_ctx_ft, _RootFtPrefixes.PC,
                                                       spec_serialize_write_templates)

                # event record header operation
                builder = _OpBuilder(self)
                er_header_op = None

                if dst._er_header_ft is not None:
                    spec_serialize_write_templates = {
                        'timestamp': self._serialize_write_timestamp_statements_templ,
                        'id': self._serialize_write_ert_id_statements_templ,
                    }
                    er_header_op = builder.build_for_root_ft(dst._er_header_ft, _RootFtPrefixes.ERH,
                                                             spec_serialize_write_templates)

                # event record common context operation
                er_common_ctx_op = None

                if dst.event_record_common_context_field_type is not None:
                    er_common_ctx_op = builder.build_for_root_ft(dst.event_record_common_context_field_type,
                                                                 _RootFtPrefixes.ERCC)

                # operations specific to each event record type
                er_ops = {}

                for ert in dst.event_record_types:
                    ev_builder = copy.copy(builder)

                    # specific context operation
                    spec_ctx_op = None

                    if ert.specific_context_field_type is not None:
                        spec_ctx_op = ev_builder.build_for_root_ft(ert.specific_context_field_type,
                                                                   _RootFtPrefixes.ERSC)

                    # payload operation
                    payload_op = None

                    if ert.payload_field_type is not None:
                        payload_op = ev_builder.build_for_root_ft(ert.payload_field_type,
                                                                  _RootFtPrefixes.ERP)

                    er_ops[ert] = _ErOps(spec_ctx_op, payload_op)

                ds_ops[dst] = _DsOps(pkt_header_op, pkt_ctx_op, er_header_op, er_common_ctx_op,
                                     er_ops)

            return ds_ops

        # Returns the "write" operation for the packet context member
        # named `member_name` within the data stream type `dst`.
        def ds_op_pkt_ctx_op(dst: barectf_config.DataStreamType, member_name: str) -> _Op:
            ret_op = None

            for op in ds_ops[dst].pkt_ctx_op.subops:
                if op.top_name == member_name and type(op) is _WriteOp:
                    ret_op = op
                    break

            assert ret_op is not None
            return typing.cast(_Op, ret_op)

        ds_ops = create_ds_ops()
        return self._create_file_template('barectf.c.j2').render(header_file_name=header_file_name,
                                                                 bitfield_header_file_name=bitfield_header_file_name,
                                                                 root_ft_prefixes=_RootFtPrefixes,
                                                                 root_ft_prefix_names=_ROOT_FT_PREFIX_NAMES,
                                                                 ds_ops=ds_ops,
                                                                 ds_op_pkt_ctx_op=ds_op_pkt_ctx_op)
