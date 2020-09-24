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

import barectf.config_parse_common as barectf_config_parse_common
from barectf.config_parse_common import _ConfigurationParseError
from barectf.config_parse_common import _append_error_ctx
from barectf.config_parse_common import _MapNode
import barectf.config as barectf_config
from barectf.config import _OptStructFt
import collections
import uuid
from barectf.typing import Count, Alignment, VersionNumber
from typing import Optional, List, Dict, Any, TextIO, Set, Iterable, Callable, Tuple, Type
import typing


# A barectf 3 YAML configuration parser.
#
# When you build such a parser, it parses the configuration node `node`
# (already loaded from the file having the path `path`) and creates a
# corresponding `barectf.Configuration` object which you can get with
# the `config` property.
#
# See the comments of _parse() for more implementation details about the
# parsing stages and general strategy.
class _Parser(barectf_config_parse_common._Parser):
    # Builds a barectf 3 YAML configuration parser and parses the root
    # configuration node `node` (already loaded from the file-like
    # object `root_file`).
    def __init__(self, root_file: TextIO, node: barectf_config_parse_common._ConfigNodeV3,
                 with_pkg_include_dir: bool, inclusion_dirs: Optional[List[str]],
                 ignore_include_not_found: bool):
        super().__init__(root_file, node, with_pkg_include_dir, inclusion_dirs,
                         ignore_include_not_found, VersionNumber(3))
        self._ft_cls_name_to_create_method: Dict[str, Callable[[_MapNode],
                                                               List[barectf_config._FieldType]]] = {
            'unsigned-integer': self._create_int_ft,
            'signed-integer': self._create_int_ft,
            'unsigned-enumeration': self._create_enum_ft,
            'signed-enumeration': self._create_enum_ft,
            'real': self._create_real_ft,
            'string': self._create_string_ft,
            'static-array': self._create_static_array_ft,
            'dynamic-array': self._create_dynamic_array_ft,
            'structure': self._create_struct_ft,
        }
        self._parse()

    # Validates the alignment `alignment`, raising a
    # `_ConfigurationParseError` exception using `ctx_obj_name` if it's
    # invalid.
    @staticmethod
    def _validate_alignment(alignment: Alignment, ctx_obj_name: str):
        assert alignment >= 1

        # check for power of two
        if (alignment & (alignment - 1)) != 0:
            raise _ConfigurationParseError(ctx_obj_name,
                                           f'Invalid alignment (not a power of two): {alignment}')

    # Validates the TSDL identifier `iden`, raising a
    # `_ConfigurationParseError` exception using `ctx_obj_name` and
    # `prop` to format the message if it's invalid.
    @staticmethod
    def _validate_iden(iden: str, ctx_obj_name: str, prop: str):
        assert type(iden) is str
        ctf_keywords = {
            'align',
            'callsite',
            'clock',
            'enum',
            'env',
            'event',
            'floating_point',
            'integer',
            'stream',
            'string',
            'struct',
            'trace',
            'typealias',
            'typedef',
            'variant',
        }

        if iden in ctf_keywords:
            msg = f'Invalid {prop} (not a valid identifier): `{iden}`'
            raise _ConfigurationParseError(ctx_obj_name, msg)

    @staticmethod
    def _alignment_prop(ft_node: _MapNode, prop_name: str) -> Alignment:
        alignment = ft_node.get(prop_name)

        if alignment is not None:
            _Parser._validate_alignment(alignment, '`prop_name` property')

        return Alignment(alignment)

    @property
    def _trace_type_node(self) -> _MapNode:
        return self.config_node['trace']['type']

    @staticmethod
    def _byte_order_from_node(node: str) -> barectf_config.ByteOrder:
        return {
            'big-endian': barectf_config.ByteOrder.BIG_ENDIAN,
            'little-endian': barectf_config.ByteOrder.LITTLE_ENDIAN,
        }[node]

    # Creates a bit array field type having the type `ft_type` from the
    # bit array field type node `ft_node`, passing the additional
    # `*args` to ft_type.__init__().
    def _create_common_bit_array_ft(self, ft_node: _MapNode,
                                    ft_type: Type[barectf_config._BitArrayFieldType],
                                    default_alignment: Optional[Alignment],
                                    *args) -> barectf_config._BitArrayFieldType:
        alignment = self._alignment_prop(ft_node, 'alignment')

        if alignment is None:
            alignment = default_alignment

        return ft_type(ft_node['size'], alignment, *args)

    # Creates an integer field type having the type `ft_type` from the
    # integer field type node `ft_node`, passing the additional `*args`
    # to ft_type.__init__().
    def _create_common_int_ft(self, ft_node: _MapNode,
                              ft_type: Type[barectf_config._IntegerFieldType], *args) -> barectf_config._IntegerFieldType:
        preferred_display_base = {
            'binary': barectf_config.DisplayBase.BINARY,
            'octal': barectf_config.DisplayBase.OCTAL,
            'decimal': barectf_config.DisplayBase.DECIMAL,
            'hexadecimal': barectf_config.DisplayBase.HEXADECIMAL,
        }[ft_node.get('preferred-display-base', 'decimal')]
        return typing.cast(barectf_config._IntegerFieldType,
                           self._create_common_bit_array_ft(ft_node, ft_type, None,
                                                            preferred_display_base, *args))

    # Creates an integer field type from the unsigned/signed integer
    # field type node `ft_node`.
    def _create_int_ft(self, ft_node: _MapNode) -> List[barectf_config._FieldType]:
        ft_type = {
            'unsigned-integer': barectf_config.UnsignedIntegerFieldType,
            'signed-integer': barectf_config.SignedIntegerFieldType,
        }[ft_node['class']]
        return [self._create_common_int_ft(ft_node, ft_type)]

    # Creates an enumeration field type from the unsigned/signed
    # enumeration field type node `ft_node`.
    def _create_enum_ft(self, ft_node: _MapNode) -> List[barectf_config._FieldType]:
        ft_type = {
            'unsigned-enumeration': barectf_config.UnsignedEnumerationFieldType,
            'signed-enumeration': barectf_config.SignedEnumerationFieldType,
        }[ft_node['class']]
        mappings = collections.OrderedDict()

        for label, mapping_node in ft_node['mappings'].items():
            ranges = set()

            for range_node in mapping_node:
                if type(range_node) is list:
                    ranges.add(barectf_config.EnumerationFieldTypeMappingRange(range_node[0],
                                                                               range_node[1]))
                else:
                    assert type(range_node) is int
                    ranges.add(barectf_config.EnumerationFieldTypeMappingRange(range_node,
                                                                               range_node))

            mappings[label] = barectf_config.EnumerationFieldTypeMapping(ranges)

        return [typing.cast(barectf_config._EnumerationFieldType,
                            self._create_common_int_ft(ft_node, ft_type,
                                                       barectf_config.EnumerationFieldTypeMappings(mappings)))]

    # Creates a real field type from the real field type node `ft_node`.
    def _create_real_ft(self, ft_node: _MapNode) -> List[barectf_config._FieldType]:
        return [typing.cast(barectf_config.RealFieldType,
                            self._create_common_bit_array_ft(ft_node, barectf_config.RealFieldType,
                                                             Alignment(8)))]

    # Creates a string field type from the string field type node
    # `ft_node`.
    def _create_string_ft(self, ft_node: _MapNode) -> List[barectf_config._FieldType]:
        return [barectf_config.StringFieldType()]

    def _create_array_ft(self, ft_type, ft_node: _MapNode, **kwargs) -> barectf_config._ArrayFieldType:
        prop_name = 'element-field-type'

        try:
            element_fts = self._create_fts(ft_node[prop_name])
        except _ConfigurationParseError as exc:
            _append_error_ctx(exc, f'`{prop_name}` property')

        if len(element_fts) != 1 or isinstance(element_fts[0], (barectf_config.StructureFieldType,
                                                                barectf_config.DynamicArrayFieldType)):
            raise _ConfigurationParseError(f'`{prop_name}` property',
                                           'Nested structure and dynamic array field types are not supported')

        return ft_type(element_field_type=element_fts[0], **kwargs)

    # Creates a static array field type from the static array field type
    # node `ft_node`.
    def _create_static_array_ft(self, ft_node: _MapNode) -> List[barectf_config._FieldType]:
        return [typing.cast(barectf_config.StaticArrayFieldType,
                            self._create_array_ft(barectf_config.StaticArrayFieldType, ft_node,
                                                  length=ft_node['length']))]

    # Creates a dynamic array field type from the dynamic array field
    # type node `ft_node`.
    def _create_dynamic_array_ft(self, ft_node: _MapNode) -> List[barectf_config._FieldType]:
        # create length unsigned integer field type
        len_ft = barectf_config.UnsignedIntegerFieldType(32, alignment=Alignment(8))
        return [
            len_ft,
            typing.cast(barectf_config.DynamicArrayFieldType,
                        self._create_array_ft(barectf_config.DynamicArrayFieldType, ft_node,
                                              length_field_type=len_ft))
        ]

    # Creates structure field type members from the structure field type
    # members node `members_node`.
    #
    # `prop_name` is the name of the property of which `members_node` is
    # the value.
    def _create_struct_ft_members(self, members_node: List[_MapNode], prop_name: str):
        members = collections.OrderedDict()
        member_names: Set[str] = set()

        for member_node in members_node:
            member_name, member_node = list(member_node.items())[0]

            if member_name in member_names:
                raise _ConfigurationParseError(f'`{prop_name}` property',
                                               f'Duplicate member `{member_name}`')

            self._validate_iden(member_name, f'`{prop_name}` property',
                                'structure field type member name')
            member_names.add(member_name)
            ft_prop_name = 'field-type'
            ft_node = member_node[ft_prop_name]

            try:
                if ft_node['class'] in ['structure']:
                    raise _ConfigurationParseError(f'`{ft_prop_name}` property',
                                                   'Nested structure field types are not supported')

                try:
                    member_fts = self._create_fts(ft_node)
                except _ConfigurationParseError as exc:
                    _append_error_ctx(exc, f'`{ft_prop_name}` property')
            except _ConfigurationParseError as exc:
                _append_error_ctx(exc, f'Structure field type member `{member_name}`')

            if len(member_fts) == 2:
                # The only case where this happens is a dynamic array
                # field type node which generates an unsigned integer
                # field type for the length and the dynamic array field
                # type itself.
                assert type(member_fts[1]) is barectf_config.DynamicArrayFieldType
                members[f'__{member_name}_len'] = barectf_config.StructureFieldTypeMember(member_fts[0])
            else:
                assert len(member_fts) == 1

            members[member_name] = barectf_config.StructureFieldTypeMember(member_fts[-1])

        return barectf_config.StructureFieldTypeMembers(members)

    # Creates a structure field type from the structure field type node
    # `ft_node`.
    def _create_struct_ft(self, ft_node: _MapNode) -> List[barectf_config._FieldType]:
        minimum_alignment = self._alignment_prop(ft_node, 'minimum-alignment')

        if minimum_alignment is None:
            minimum_alignment = 1

        members = None
        prop_name = 'members'
        members_node = ft_node.get(prop_name)

        if members_node is not None:
            members = self._create_struct_ft_members(members_node, prop_name)

        return [barectf_config.StructureFieldType(minimum_alignment, members)]

    # Creates field types from the field type node `ft_node`.
    def _create_fts(self, ft_node: _MapNode) -> List[barectf_config._FieldType]:
        return self._ft_cls_name_to_create_method[ft_node['class']](ft_node)

    # Creates field types from the field type node `parent_node[key]`
    # if it exists.
    def _try_create_fts(self, parent_node: _MapNode, key: str) -> Optional[List[barectf_config._FieldType]]:
        if key not in parent_node:
            return None

        try:
            return self._create_fts(parent_node[key])
        except _ConfigurationParseError as exc:
            _append_error_ctx(exc, f'`{key}` property')

            # satisfy static type checker (never reached)
            raise

    # Like _try_create_fts(), but casts the result's type (first and
    # only element) to `barectf_config.StructureFieldType` to satisfy
    # static type checkers.
    def _try_create_struct_ft(self, parent_node: _MapNode, key: str) -> _OptStructFt:
        fts = self._try_create_fts(parent_node, key)

        if fts is None:
            return None

        return typing.cast(barectf_config.StructureFieldType, fts[0])

    # Returns the total number of members in the structure field type
    # node `ft_node` if it exists, otherwise 0.
    @staticmethod
    def _total_struct_ft_node_members(ft_node: Optional[_MapNode]) -> Count:
        if ft_node is None:
            return Count(0)

        members_node = ft_node.get('members')

        if members_node is None:
            return Count(0)

        return Count(len(members_node))

    # Creates an event record type from the event record type node
    # `ert_node` named `name`.
    #
    # `ert_member_count` is the total number of structure field type
    # members within the event record type so far (from the common part
    # in its data stream type). For example, if the data stream type has
    # an event record header field type with `id` and `timestamp`
    # members, then `ert_member_count` is 2.
    def _create_ert(self, name: str, ert_node: _MapNode,
                        ert_member_count: Count) -> barectf_config.EventRecordType:
        try:
            self._validate_iden(name, '`name` property', 'event record type name')

            # make sure the event record type is not empty
            spec_ctx_ft_prop_name = 'specific-context-field-type'
            payload_ft_prop_name = 'payload-field-type'
            ert_member_count = Count(ert_member_count + self._total_struct_ft_node_members(ert_node.get(spec_ctx_ft_prop_name)))
            ert_member_count = Count(ert_member_count + self._total_struct_ft_node_members(ert_node.get(payload_ft_prop_name)))

            if ert_member_count == 0:
                raise _ConfigurationParseError('Event record type',
                                               'Event record type is empty (no members).')

            # create event record type
            return barectf_config.EventRecordType(name, ert_node.get('log-level'),
                                                  self._try_create_struct_ft(ert_node,
                                                                       spec_ctx_ft_prop_name),
                                                  self._try_create_struct_ft(ert_node,
                                                                       payload_ft_prop_name))
        except _ConfigurationParseError as exc:
            _append_error_ctx(exc, f'Event record type `{name}`')

            # satisfy static type checker (never reached)
            raise

    # Returns the effective feature field type for the field type
    # node `parent_node[key]`, if any.
    #
    # Returns:
    #
    # If `parent_node[key]` is `False`:
    #     `None`.
    #
    # If `parent_node[key]` is `True`:
    #     `barectf_config.DEFAULT_FIELD_TYPE`.
    #
    # If `parent_node[key]` doesn't exist:
    #     `none` (parameter).
    #
    # Otherwise:
    #     A created field type.
    def _feature_ft(self, parent_node: _MapNode, key: str, none: Any = None) -> Any:
        if key not in parent_node:
            # missing: default feature field type
            return none

        ft_node = parent_node[key]
        assert ft_node is not None

        if ft_node is True:
            # default feature field type
            return barectf_config.DEFAULT_FIELD_TYPE

        if ft_node is False:
            # disabled feature
            return None

        assert type(ft_node) is collections.OrderedDict
        return self._create_fts(ft_node)[0]

    def _create_dst(self, name: str, dst_node: _MapNode) -> barectf_config.DataStreamType:
        try:
            # validate data stream type's name
            self._validate_iden(name, '`name` property', 'data stream type name')

            # get default clock type, if any
            def_clk_type = None
            prop_name = '$default-clock-type-name'
            def_clk_type_name = dst_node.get(prop_name)

            if def_clk_type_name is not None:
                try:
                    def_clk_type = self._clk_type(def_clk_type_name, prop_name)
                except _ConfigurationParseError as exc:
                    _append_error_ctx(exc, f'`{prop_name}` property')

            # create feature field types
            pkt_total_size_ft = barectf_config.DEFAULT_FIELD_TYPE
            pkt_content_size_ft = barectf_config.DEFAULT_FIELD_TYPE
            pkt_beginning_ts_ft = None
            pkt_end_ts_ft = None
            pkt_disc_er_counter_snap_ft = barectf_config.DEFAULT_FIELD_TYPE
            ert_id_ft = barectf_config.DEFAULT_FIELD_TYPE
            ert_ts_ft = None

            if def_clk_type is not None:
                # The data stream type has a default clock type.
                # Initialize the packet beginning timestamp, packet end
                # timestamp, and event record timestamp field types to
                # default field types.
                #
                # This means your data stream type node only needs a
                # default clock type name to enable those features
                # automatically. Those features do not add any parameter
                # to the event tracing functions.
                pkt_beginning_ts_ft = barectf_config.DEFAULT_FIELD_TYPE
                pkt_end_ts_ft = barectf_config.DEFAULT_FIELD_TYPE
                ert_ts_ft = barectf_config.DEFAULT_FIELD_TYPE

            features_node = dst_node.get('$features')

            if features_node is not None:
                # create packet feature field types
                pkt_node = features_node.get('packet')

                if pkt_node is not None:
                    pkt_total_size_ft = self._feature_ft(pkt_node, 'total-size-field-type',
                                                         pkt_total_size_ft)
                    pkt_content_size_ft = self._feature_ft(pkt_node, 'content-size-field-type',
                                                           pkt_content_size_ft)
                    pkt_beginning_ts_ft = self._feature_ft(pkt_node,
                                                           'beginning-timestamp-field-type',
                                                           pkt_beginning_ts_ft)
                    pkt_end_ts_ft = self._feature_ft(pkt_node, 'end-timestamp-field-type',
                                                     pkt_end_ts_ft)
                    pkt_disc_er_counter_snap_ft = self._feature_ft(pkt_node,
                                                                   'discarded-event-records-counter-snapshot-field-type',
                                                                   pkt_disc_er_counter_snap_ft)

                # create event record feature field types
                er_node = features_node.get('event-record')
                type_id_ft_prop_name = 'type-id-field-type'

                if er_node is not None:
                    ert_id_ft = self._feature_ft(er_node, type_id_ft_prop_name, ert_id_ft)
                    ert_ts_ft = self._feature_ft(er_node, 'timestamp-field-type', ert_ts_ft)

            erts_prop_name = 'event-record-types'
            ert_count = len(dst_node[erts_prop_name])

            try:
                if ert_id_ft is None and ert_count > 1:
                    raise _ConfigurationParseError(f'`{type_id_ft_prop_name}` property',
                                                   'Event record type ID field type feature is required because data stream type has more than one event record type')

                if isinstance(ert_id_ft, barectf_config._IntegerFieldType):
                    ert_id_int_ft = typing.cast(barectf_config._IntegerFieldType, ert_id_ft)

                    if ert_count > (1 << ert_id_int_ft.size):
                        raise _ConfigurationParseError(f'`{type_id_ft_prop_name}` property',
                                                       f'Field type\'s size ({ert_id_int_ft.size} bits) is too small to accomodate {ert_count} event record types')
            except _ConfigurationParseError as exc:
                exc._append_ctx('`event-record` property')
                _append_error_ctx(exc, '`$features` property')

            pkt_features = barectf_config.DataStreamTypePacketFeatures(pkt_total_size_ft,
                                                                       pkt_content_size_ft,
                                                                       pkt_beginning_ts_ft,
                                                                       pkt_end_ts_ft,
                                                                       pkt_disc_er_counter_snap_ft)
            er_features = barectf_config.DataStreamTypeEventRecordFeatures(ert_id_ft, ert_ts_ft)
            features = barectf_config.DataStreamTypeFeatures(pkt_features, er_features)

            # create packet context (structure) field type extra members
            pkt_ctx_ft_extra_members = None
            prop_name = 'packet-context-field-type-extra-members'
            pkt_ctx_ft_extra_members_node = dst_node.get(prop_name)

            if pkt_ctx_ft_extra_members_node is not None:
                pkt_ctx_ft_extra_members = self._create_struct_ft_members(pkt_ctx_ft_extra_members_node,
                                                                          prop_name)

                # check for illegal packet context field type member names
                reserved_member_names = {
                    'packet_size',
                    'content_size',
                    'timestamp_begin',
                    'timestamp_end',
                    'events_discarded',
                    'packet_seq_num',
                }

                for member_name in pkt_ctx_ft_extra_members:
                    if member_name in reserved_member_names:
                        raise _ConfigurationParseError(f'`{prop_name}` property',
                                                       f'Packet context field type member name `{member_name}` is reserved.')

            # create event record types
            er_header_common_ctx_member_count = Count(0)

            if er_features.type_id_field_type is not None:
                er_header_common_ctx_member_count = Count(er_header_common_ctx_member_count + 1)

            if er_features.timestamp_field_type is not None:
                er_header_common_ctx_member_count = Count(er_header_common_ctx_member_count + 1)

            er_common_ctx_ft_prop_name = 'event-record-common-context-field-type'
            er_common_ctx_ft_node = dst_node.get(er_common_ctx_ft_prop_name)
            er_header_common_ctx_member_count = Count(er_header_common_ctx_member_count + self._total_struct_ft_node_members(er_common_ctx_ft_node))
            erts = set()

            for ert_name, ert_node in dst_node[erts_prop_name].items():
                erts.add(self._create_ert(ert_name, ert_node, er_header_common_ctx_member_count))

            # create data stream type
            return barectf_config.DataStreamType(name, erts, def_clk_type, features,
                                                 pkt_ctx_ft_extra_members,
                                                 self._try_create_struct_ft(dst_node,
                                                                            er_common_ctx_ft_prop_name))
        except _ConfigurationParseError as exc:
            _append_error_ctx(exc, f'Data data stream type `{name}`')

            # satisfy static type checker (never reached)
            raise

    def _clk_type(self, name: str, prop_name: str) -> barectf_config.ClockType:
        clk_type = self._clk_types.get(name)

        if clk_type is None:
            raise _ConfigurationParseError(f'`{prop_name}` property',
                                           f'Clock type `{name}` does not exist')

        return clk_type

    def _create_clk_type(self, name: str, clk_type_node: _MapNode) -> barectf_config.ClockType:
        self._validate_iden(name, '`name` property', 'clock type name')
        clk_type_uuid = None
        uuid_node = clk_type_node.get('uuid')

        if uuid_node is not None:
            clk_type_uuid = uuid.UUID(uuid_node)

        offset_seconds = 0
        offset_cycles = Count(0)
        offset_node = clk_type_node.get('offset')

        if offset_node is not None:
            offset_seconds = offset_node.get('seconds', 0)
            offset_cycles = offset_node.get('cycles', Count(0))

        return barectf_config.ClockType(name, clk_type_node.get('frequency', int(1e9)),
                                        clk_type_uuid, clk_type_node.get('description'),
                                        clk_type_node.get('precision', 0),
                                        barectf_config.ClockTypeOffset(offset_seconds, offset_cycles),
                                        clk_type_node.get('origin-is-unix-epoch', False))

    def _create_clk_types(self):
        self._clk_types = {}

        for clk_type_name, clk_type_node in self._trace_type_node.get('clock-types', {}).items():
            self._clk_types[clk_type_name] = self._create_clk_type(clk_type_name, clk_type_node)

    def _create_trace_type(self):
        try:
            # create clock types (_create_dst() needs them)
            self._create_clk_types()

            # get UUID
            trace_type_uuid = None
            uuid_node = self._trace_type_node.get('uuid')

            if uuid_node is not None:
                if uuid_node == 'auto':
                    trace_type_uuid = uuid.uuid1()
                else:
                    trace_type_uuid = uuid.UUID(uuid_node)

            # create feature field types
            magic_ft = barectf_config.DEFAULT_FIELD_TYPE
            uuid_ft = None
            dst_id_ft = barectf_config.DEFAULT_FIELD_TYPE

            if trace_type_uuid is not None:
                # Trace type has a UUID: initialize UUID field type to
                # a default field type.
                uuid_ft = barectf_config.DEFAULT_FIELD_TYPE

            features_node = self._trace_type_node.get('$features')
            dst_id_ft_prop_name = 'data-stream-type-id-field-type'

            if features_node is not None:
                magic_ft = self._feature_ft(features_node, 'magic-field-type',
                                            magic_ft)
                uuid_ft = self._feature_ft(features_node, 'uuid-field-type', uuid_ft)
                dst_id_ft = self._feature_ft(features_node, dst_id_ft_prop_name, dst_id_ft)

            dsts_prop_name = 'data-stream-types'
            dst_count = len(self._trace_type_node[dsts_prop_name])

            try:
                if dst_id_ft is None and dst_count > 1:
                    raise _ConfigurationParseError(f'`{dst_id_ft_prop_name}` property',
                                                   'Data stream type ID field type feature is required because trace type has more than one data stream type')

                if isinstance(dst_id_ft, barectf_config._FieldType) and dst_count > (1 << dst_id_ft.size):
                    raise _ConfigurationParseError(f'`{dst_id_ft_prop_name}` property',
                                                   f'Field type\'s size ({dst_id_ft.size} bits) is too small to accomodate {dst_count} data stream types')
            except _ConfigurationParseError as exc:
                _append_error_ctx(exc, '`$features` property')

            features = barectf_config.TraceTypeFeatures(magic_ft, uuid_ft, dst_id_ft)

            # create data stream types
            dsts = set()

            for dst_name, dst_node in self._trace_type_node[dsts_prop_name].items():
                dsts.add(self._create_dst(dst_name, dst_node))

            # create trace type
            return barectf_config.TraceType(self._native_byte_order, dsts, trace_type_uuid,
                                            features)
        except _ConfigurationParseError as exc:
            _append_error_ctx(exc, 'Trace type')

    def _create_trace(self):
        try:
            trace_type = self._create_trace_type()
            trace_node = self.config_node['trace']
            env = None
            env_node = trace_node.get('environment')

            if env_node is not None:
                # validate each environment variable name
                for name in env_node:
                    self._validate_iden(name, '`environment` property',
                                        'environment variable name')

                # the node already has the expected structure
                env = barectf_config.TraceEnvironment(env_node)

            return barectf_config.Trace(trace_type, env)

        except _ConfigurationParseError as exc:
            _append_error_ctx(exc, 'Trace')

    def _create_config(self):
        # create trace first
        trace = self._create_trace()

        # find default data stream type, if any
        def_dst = None

        for dst_name, dst_node in self._trace_type_node['data-stream-types'].items():
            prop_name = '$is-default'
            is_default = dst_node.get(prop_name)

            if is_default is True:
                if def_dst is not None:
                    exc = _ConfigurationParseError(f'`{prop_name}` property',
                                                   f'Duplicate default data stream type (`{def_dst.name}`)')
                    exc._append_ctx(f'Data stream type `{dst_name}`')
                    _append_error_ctx(exc, 'Trace type')

                def_dst = trace.type.data_stream_type(dst_name)

        # create clock type C type mapping
        clk_types_node = self._trace_type_node.get('clock-types')
        clk_type_c_types = None

        if clk_types_node is not None:
            clk_type_c_types = collections.OrderedDict()

            for dst in trace.type.data_stream_types:
                if dst.default_clock_type is None:
                    continue

                clk_type_node = clk_types_node[dst.default_clock_type.name]
                c_type = clk_type_node.get('$c-type')

                if c_type is not None:
                    clk_type_c_types[dst.default_clock_type] = c_type

        # create options
        iden_prefix_def = False
        def_dst_name_def = False
        opts_node = self.config_node.get('options')
        iden_prefix = 'barectf_'
        file_name_prefix = 'barectf'

        if opts_node is not None:
            code_gen_opts_node = opts_node.get('code-generation')

            if code_gen_opts_node is not None:
                prefix_node = code_gen_opts_node.get('prefix', 'barectf')

                if type(prefix_node) is str:
                    # automatic prefixes
                    iden_prefix = f'{prefix_node}_'
                    file_name_prefix = prefix_node
                else:
                    iden_prefix = prefix_node['identifier']
                    file_name_prefix = prefix_node['file-name']

                header_opts = code_gen_opts_node.get('header')

                if header_opts is not None:
                    iden_prefix_def = header_opts.get('identifier-prefix-definition', False)
                    def_dst_name_def = header_opts.get('default-data-stream-type-name-definition',
                                                       False)

        header_opts = barectf_config.ConfigurationCodeGenerationHeaderOptions(iden_prefix_def,
                                                                              def_dst_name_def)
        cg_opts = barectf_config.ConfigurationCodeGenerationOptions(iden_prefix, file_name_prefix,
                                                                    def_dst, header_opts,
                                                                    clk_type_c_types)
        opts = barectf_config.ConfigurationOptions(cg_opts)

        # create configuration
        self._config = barectf_config.Configuration(trace, opts)

    # Expands the field type aliases found in the trace type node.
    #
    # This method modifies the trace type node.
    #
    # When this method returns:
    #
    # * Any field type alias is replaced with its full field type
    #   node equivalent.
    #
    # * The `$field-type-aliases` property of the trace type node is
    #   removed.
    def _expand_ft_aliases(self):
        def resolve_ft_alias_from(parent_node: _MapNode, key: str):
            if key not in parent_node:
                return

            if type(parent_node[key]) not in [collections.OrderedDict, str]:
                return

            self._resolve_ft_alias_from(ft_aliases_node, parent_node, key)

        ft_aliases_node = self._trace_type_node['$field-type-aliases']

        # Expand field type aliases within trace, data stream, and event
        # record type nodes.
        features_prop_name = '$features'

        try:
            features_node = self._trace_type_node.get(features_prop_name)

            if features_node is not None:
                try:
                    resolve_ft_alias_from(features_node, 'magic-field-type')
                    resolve_ft_alias_from(features_node, 'uuid-field-type')
                    resolve_ft_alias_from(features_node, 'data-stream-type-id-field-type')
                except _ConfigurationParseError as exc:
                    _append_error_ctx(exc, f'`{features_prop_name}` property')
        except _ConfigurationParseError as exc:
            _append_error_ctx(exc, 'Trace type')

        for dst_name, dst_node in self._trace_type_node['data-stream-types'].items():
            try:
                features_node = dst_node.get(features_prop_name)

                if features_node is not None:
                    try:
                        pkt_prop_name = 'packet'
                        pkt_node = features_node.get(pkt_prop_name)

                        if pkt_node is not None:
                            try:
                                resolve_ft_alias_from(pkt_node, 'total-size-field-type')
                                resolve_ft_alias_from(pkt_node, 'content-size-field-type')
                                resolve_ft_alias_from(pkt_node, 'beginning-timestamp-field-type')
                                resolve_ft_alias_from(pkt_node, 'end-timestamp-field-type')
                                resolve_ft_alias_from(pkt_node,
                                                      'discarded-event-records-counter-snapshot-field-type')
                            except _ConfigurationParseError as exc:
                                _append_error_ctx(exc, f'`{pkt_prop_name}` property')

                        er_prop_name = 'event-record'
                        er_node = features_node.get(er_prop_name)

                        if er_node is not None:
                            try:
                                resolve_ft_alias_from(er_node, 'type-id-field-type')
                                resolve_ft_alias_from(er_node, 'timestamp-field-type')
                            except _ConfigurationParseError as exc:
                                _append_error_ctx(exc, f'`{er_prop_name}` property')
                    except _ConfigurationParseError as exc:
                        _append_error_ctx(exc, f'`{features_prop_name}` property')

                pkt_ctx_ft_extra_members_prop_name = 'packet-context-field-type-extra-members'
                pkt_ctx_ft_extra_members_node = dst_node.get(pkt_ctx_ft_extra_members_prop_name)

                if pkt_ctx_ft_extra_members_node is not None:
                    try:
                        for member_node in pkt_ctx_ft_extra_members_node:
                            member_node = list(member_node.values())[0]
                            resolve_ft_alias_from(member_node, 'field-type')
                    except _ConfigurationParseError as exc:
                        _append_error_ctx(exc, f'`{pkt_ctx_ft_extra_members_prop_name}` property')

                resolve_ft_alias_from(dst_node, 'event-record-common-context-field-type')

                for ert_name, ert_node in dst_node['event-record-types'].items():
                    try:
                        resolve_ft_alias_from(ert_node, 'specific-context-field-type')
                        resolve_ft_alias_from(ert_node, 'payload-field-type')
                    except _ConfigurationParseError as exc:
                        _append_error_ctx(exc, f'Event record type `{ert_name}`')
            except _ConfigurationParseError as exc:
                _append_error_ctx(exc, f'Data stream type `{dst_name}`')

        # remove the (now unneeded) `$field-type-aliases` property
        del self._trace_type_node['$field-type-aliases']

    # Applies field type inheritance to all field type nodes found in
    # the trace type node.
    #
    # This method modifies the trace type node.
    #
    # When this method returns, no field type node has an `$inherit`
    # property.
    def _apply_fts_inheritance(self):
        def apply_ft_inheritance(parent_node: _MapNode, key: str):
            if key not in parent_node:
                return

            if type(parent_node[key]) is not collections.OrderedDict:
                return

            self._apply_ft_inheritance(parent_node, key)

        features_prop_name = '$features'
        features_node = self._trace_type_node.get(features_prop_name)

        if features_node is not None:
            apply_ft_inheritance(features_node, 'magic-field-type')
            apply_ft_inheritance(features_node, 'uuid-field-type')
            apply_ft_inheritance(features_node, 'data-stream-type-id-field-type')

        for dst_node in self._trace_type_node['data-stream-types'].values():
            features_node = dst_node.get(features_prop_name)

            if features_node is not None:
                pkt_node = features_node.get('packet')

                if pkt_node is not None:
                    apply_ft_inheritance(pkt_node, 'total-size-field-type')
                    apply_ft_inheritance(pkt_node, 'content-size-field-type')
                    apply_ft_inheritance(pkt_node, 'beginning-timestamp-field-type')
                    apply_ft_inheritance(pkt_node, 'end-timestamp-field-type')
                    apply_ft_inheritance(pkt_node,
                                         'discarded-event-records-counter-snapshot-field-type')

                er_node = features_node.get('event-record')

                if er_node is not None:
                    apply_ft_inheritance(er_node, 'type-id-field-type')
                    apply_ft_inheritance(er_node, 'timestamp-field-type')

            pkt_ctx_ft_extra_members_node = dst_node.get('packet-context-field-type-extra-members')

            if pkt_ctx_ft_extra_members_node is not None:
                for member_node in pkt_ctx_ft_extra_members_node:
                    member_node = list(member_node.values())[0]
                    apply_ft_inheritance(member_node, 'field-type')

            apply_ft_inheritance(dst_node, 'event-record-common-context-field-type')

            for ert_node in dst_node['event-record-types'].values():
                apply_ft_inheritance(ert_node, 'specific-context-field-type')
                apply_ft_inheritance(ert_node, 'payload-field-type')

    # Normalizes structure field type member nodes.
    #
    # A structure field type member node can look like this:
    #
    #     - msg: custom-string
    #
    # which is the equivalent of this:
    #
    #     - msg:
    #         field-type: custom-string
    #
    # This method normalizes form 1 to use form 2.
    def _normalize_struct_ft_member_nodes(self):
        def normalize_members_node(members_node: List[_MapNode]):
            ft_prop_name = 'field-type'

            for member_node in members_node:
                member_name, val_node = list(member_node.items())[0]

                if type(val_node) is str:
                    member_node[member_name] = collections.OrderedDict({
                        ft_prop_name: val_node
                    })

                normalize_struct_ft_member_nodes(member_node[member_name], ft_prop_name)

        def normalize_struct_ft_member_nodes(parent_node: _MapNode, key: str):
            if type(parent_node) is not collections.OrderedDict:
                return

            ft_node = parent_node.get(key)

            if type(ft_node) is not collections.OrderedDict:
                return

            ft_node = typing.cast(collections.OrderedDict, ft_node)
            members_nodes = ft_node.get('members')

            if members_nodes is not None:
                normalize_members_node(members_nodes)

        prop_name = '$field-type-aliases'
        ft_aliases_node = self._trace_type_node.get(prop_name)

        if ft_aliases_node is not None:
            for alias in ft_aliases_node:
                normalize_struct_ft_member_nodes(ft_aliases_node, alias)

        features_prop_name = '$features'
        features_node = self._trace_type_node.get(features_prop_name)

        if features_node is not None:
            normalize_struct_ft_member_nodes(features_node, 'magic-field-type')
            normalize_struct_ft_member_nodes(features_node, 'uuid-field-type')
            normalize_struct_ft_member_nodes(features_node, 'data-stream-type-id-field-type')

        for dst_node in self._trace_type_node['data-stream-types'].values():
            features_node = dst_node.get(features_prop_name)

            if features_node is not None:
                pkt_node = features_node.get('packet')

                if pkt_node is not None:
                    normalize_struct_ft_member_nodes(pkt_node, 'total-size-field-type')
                    normalize_struct_ft_member_nodes(pkt_node, 'content-size-field-type')
                    normalize_struct_ft_member_nodes(pkt_node, 'beginning-timestamp-field-type')
                    normalize_struct_ft_member_nodes(pkt_node, 'end-timestamp-field-type')
                    normalize_struct_ft_member_nodes(pkt_node,
                                                     'discarded-event-records-counter-snapshot-field-type')

                er_node = features_node.get('event-record')

                if er_node is not None:
                    normalize_struct_ft_member_nodes(er_node, 'type-id-field-type')
                    normalize_struct_ft_member_nodes(er_node, 'timestamp-field-type')

            pkt_ctx_ft_extra_members_node = dst_node.get('packet-context-field-type-extra-members')

            if pkt_ctx_ft_extra_members_node is not None:
                normalize_members_node(pkt_ctx_ft_extra_members_node)

            normalize_struct_ft_member_nodes(dst_node, 'event-record-common-context-field-type')

            for ert_node in dst_node['event-record-types'].values():
                normalize_struct_ft_member_nodes(ert_node, 'specific-context-field-type')
                normalize_struct_ft_member_nodes(ert_node, 'payload-field-type')

    # Calls _expand_ft_aliases() and _apply_fts_inheritance() if the
    # trace type node has a `$field-type-aliases` property.
    def _expand_fts(self):
        # Make sure that the current configuration node is valid
        # considering field types are not expanded yet.
        self._schema_validator.validate(self.config_node,
                                        'config/3/config-pre-field-type-expansion')

        prop_name = '$field-type-aliases'
        ft_aliases_node = self._trace_type_node.get(prop_name)

        if ft_aliases_node is None:
            # If there's no `'$field-type-aliases'` node, then there's
            # no field type aliases and therefore no possible
            # inheritance.
            if prop_name in self._trace_type_node:
                del self._trace_type_node[prop_name]

            return

        # normalize structure field type member nodes
        self._normalize_struct_ft_member_nodes()

        # first, expand field type aliases
        self._expand_ft_aliases()

        # next, apply inheritance to create effective field type nodes
        self._apply_fts_inheritance()

    # Substitute the event record type node log level aliases with their
    # numeric equivalents.
    #
    # Removes the `$log-level-aliases` property of the trace type node.
    def _sub_log_level_aliases(self):
        # Make sure that the current configuration node is valid
        # considering log level aliases are not substituted yet.
        self._schema_validator.validate(self.config_node,
                                        'config/3/config-pre-log-level-alias-sub')

        log_level_aliases_prop_name = '$log-level-aliases'
        log_level_aliases_node = self._trace_type_node.get(log_level_aliases_prop_name)

        if log_level_aliases_prop_name in self._trace_type_node:
            del self._trace_type_node[log_level_aliases_prop_name]

        if log_level_aliases_node is None:
            # no log level aliases
            return

        # substitute log level aliases
        for dst_name, dst_node in self._trace_type_node['data-stream-types'].items():
            try:
                for ert_name, ert_node in dst_node['event-record-types'].items():
                    try:
                        prop_name = 'log-level'
                        ll_node = ert_node.get(prop_name)

                        if ll_node is None:
                            continue

                        if type(ll_node) is str:
                            if ll_node not in log_level_aliases_node:
                                raise _ConfigurationParseError(f'`{prop_name}` property',
                                                               f'Log level alias `{ll_node}` does not exist')

                            ert_node[prop_name] = log_level_aliases_node[ll_node]
                    except _ConfigurationParseError as exc:
                        _append_error_ctx(exc, f'Event record type `{ert_name}`')
            except _ConfigurationParseError as exc:
                _append_error_ctx(exc, f'Data stream type `{dst_name}`')

    # Generator of parent node and key pairs for all the nodes,
    # recursively, of `node`.
    #
    # It is safe to delete a yielded node during the iteration.
    @staticmethod
    def _props(node: Any) -> Iterable[Tuple[Any, str]]:
        if type(node) is collections.OrderedDict:
            for key in list(node):
                yield from _Parser._props(node[key])
                yield node, key
        elif type(node) is list:
            for item_node in node:
                yield from _Parser._props(item_node)

    def _trace_type_props(self) -> Iterable[Tuple[Any, str]]:
        yield from _Parser._props(self.config_node['trace']['type'])

    # Normalize the properties of the configuration node.
    #
    # This method, for each property of the trace type node:
    #
    # 1. Removes it if it's `None` (means default).
    #
    # 2. Chooses a specific `class` property value.
    #
    # 3. Chooses a specific `byte-order`/`native-byte-order` property
    #    value.
    #
    # 4. Chooses a specific `preferred-display-base` property value.
    #
    # This method also applies 1. to the trace node's `environment`
    # property.
    def _normalize_props(self):
        def normalize_byte_order_prop(parent_node: _MapNode, key: str):
            node = parent_node[key]

            if node in ['be', 'big']:
                parent_node[key] = 'big-endian'
            elif node in ['le', 'little']:
                parent_node[key] = 'little-endian'

        trace_node = self.config_node['trace']
        normalize_byte_order_prop(self._trace_type_node, 'native-byte-order')

        for parent_node, key in self._trace_type_props():
            node = parent_node[key]

            if node is None:
                # a `None` property is equivalent to not having it
                del parent_node[key]
                continue

            if key == 'class' and type(node) is str:
                # field type class aliases
                if node in ['uint', 'unsigned-int']:
                    parent_node[key] = 'unsigned-integer'
                elif node in ['sint', 'signed-int']:
                    parent_node[key] = 'signed-integer'
                elif node in ['uenum', 'unsigned-enum']:
                    parent_node[key] = 'unsigned-enumeration'
                elif node in ['senum', 'signed-enum']:
                    parent_node[key] = 'signed-enumeration'
                elif node == 'str':
                    parent_node[key] = 'string'
                elif node == 'struct':
                    parent_node[key] = 'structure'
            elif key == 'preferred-display-base' and type(node) is str:
                # display base aliases
                if node == 'bin':
                    parent_node[key] = 'binary'
                elif node == 'oct':
                    parent_node[key] = 'octal'
                elif node == 'dec':
                    parent_node[key] = 'decimal'
                elif node == 'hex':
                    parent_node[key] = 'hexadecimal'

        prop_name = 'environment'

        if prop_name in trace_node:
            node = trace_node[prop_name]

            if node is None:
                del trace_node[prop_name]

    # Sets the parser's native byte order.
    def _set_native_byte_order(self):
        self._native_byte_order_node = self._trace_type_node['native-byte-order']
        self._native_byte_order = self._byte_order_from_node(self._native_byte_order_node)

    # Processes the inclusions of the event record type node
    # `ert_node`, returning the effective node.
    def _process_ert_node_include(self, ert_node: _MapNode) -> _MapNode:
        # Make sure the event record type node is valid for the
        # inclusion processing stage.
        self._schema_validator.validate(ert_node, 'config/3/ert-pre-include')

        # process inclusions
        return self._process_node_include(ert_node, self._process_ert_node_include)

    # Processes the inclusions of the data stream type node `dst_node`,
    # returning the effective node.
    def _process_dst_node_include(self, dst_node: _MapNode) -> _MapNode:
        def process_children_include(dst_node: _MapNode):
            prop_name = 'event-record-types'

            if prop_name in dst_node:
                erts_node = dst_node[prop_name]

                for key in list(erts_node):
                    erts_node[key] = self._process_ert_node_include(erts_node[key])

        # Make sure the data stream type node is valid for the inclusion
        # processing stage.
        self._schema_validator.validate(dst_node, 'config/3/dst-pre-include')

        # process inclusions
        return self._process_node_include(dst_node, self._process_dst_node_include,
                                          process_children_include)

    # Processes the inclusions of the clock type node `clk_type_node`,
    # returning the effective node.
    def _process_clk_type_node_include(self, clk_type_node: _MapNode) -> _MapNode:
        # Make sure the clock type node is valid for the inclusion
        # processing stage.
        self._schema_validator.validate(clk_type_node, 'config/3/clock-type-pre-include')

        # process inclusions
        return self._process_node_include(clk_type_node, self._process_clk_type_node_include)

    # Processes the inclusions of the trace type node `trace_type_node`,
    # returning the effective node.
    def _process_trace_type_node_include(self, trace_type_node: _MapNode) -> _MapNode:
        def process_children_include(trace_type_node: _MapNode):
            prop_name = 'clock-types'

            if prop_name in trace_type_node:
                clk_types_node = trace_type_node[prop_name]

                for key in list(clk_types_node):
                    clk_types_node[key] = self._process_clk_type_node_include(clk_types_node[key])

            prop_name = 'data-stream-types'

            if prop_name in trace_type_node:
                dsts_node = trace_type_node[prop_name]

                for key in list(dsts_node):
                    dsts_node[key] = self._process_dst_node_include(dsts_node[key])

        # Make sure the trace type node is valid for the inclusion
        # processing stage.
        self._schema_validator.validate(trace_type_node, 'config/3/trace-type-pre-include')

        # process inclusions
        return self._process_node_include(trace_type_node, self._process_trace_type_node_include,
                                          process_children_include)

    # Processes the inclusions of the trace node `trace_node`, returning
    # the effective node.
    def _process_trace_node_include(self, trace_node: _MapNode) -> _MapNode:
        def process_children_include(trace_node: _MapNode):
            prop_name = 'type'
            trace_node[prop_name] = self._process_trace_type_node_include(trace_node[prop_name])

        # Make sure the trace node is valid for the inclusion processing
        # stage.
        self._schema_validator.validate(trace_node, 'config/3/trace-pre-include')

        # process inclusions
        return self._process_node_include(trace_node, self._process_trace_node_include,
                                          process_children_include)

    # Processes the inclusions of the configuration node, modifying it
    # during the process.
    def _process_config_includes(self):
        # Process inclusions in this order:
        #
        # 1. Clock type node and event record type nodes (the order
        #    between those is not important).
        #
        # 2. Data stream type nodes.
        #
        # 3. Trace type node.
        #
        # 4. Trace node.
        #
        # This is because:
        #
        # * A trace node can include a trace type node, clock type
        #   nodes, data stream type nodes, and event record type nodes.
        #
        # * A trace type node can include clock type nodes, data stream
        #   type nodes, and event record type nodes.
        #
        # * A data stream type node can include event record type nodes.
        #
        # First, make sure the configuration node itself is valid for
        # the inclusion processing stage.
        self._schema_validator.validate(self.config_node, 'config/3/config-pre-include')

        # Process trace node inclusions.
        #
        # self._process_trace_node_include() returns a new (or the same)
        # trace node without any `$include` property in it, recursively.
        self.config_node['trace'] = self._process_trace_node_include(self.config_node['trace'])

    def _parse(self):
        # process configuration node inclusions
        self._process_config_includes()

        # Expand field type nodes.
        #
        # This process:
        #
        # 1. Replaces field type aliases with "effective" field type
        #    nodes, recursively.
        #
        #    After this step, the `$field-type-aliases` property of the
        #    trace type node is gone.
        #
        # 2. Applies inheritance, following the `$inherit` properties.
        #
        #    After this step, field type nodes do not contain `$inherit`
        #    properties.
        #
        # This is done blindly, in that the process _doesn't_ validate
        # field type nodes at this point.
        self._expand_fts()

        # Substitute log level aliases.
        #
        # This process:
        #
        # 1. Replaces log level aliases in event record type nodes with
        #    their numeric equivalents as found in the
        #    `$log-level-aliases` property of the trace type node.
        #
        # 2. Removes the `$log-level-aliases` property from the trace
        #    type node.
        self._sub_log_level_aliases()

        # At this point, the configuration node must be valid as an
        # effective configuration node.
        self._schema_validator.validate(self.config_node, 'config/3/config')

        # Normalize properties.
        #
        # This process removes `None` properties and chooses specific
        # enumerators when aliases exist (for example, `big-endian`
        # instead of `be`).
        #
        # The goal of this is that, if the user then gets this parser's
        # `config_node` property, it has a normal and very readable
        # form.
        #
        # It also makes _create_config() easier to implement because it
        # doesn't need to check for `None` nodes or enumerator aliases.
        self._normalize_props()

        # Set the native byte order.
        self._set_native_byte_order()

        # Create a barectf configuration object from the configuration
        # node.
        self._create_config()

    @property
    def config(self) -> barectf_config.Configuration:
        return self._config

    @property
    def config_node(self) -> _MapNode:
        return typing.cast(barectf_config_parse_common._ConfigNodeV3, self._root_node).config_node
