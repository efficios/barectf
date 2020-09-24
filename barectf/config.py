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

import barectf.version as barectf_version
from typing import Optional, Any, FrozenSet, Mapping, Iterator, Set, Union, Callable
import typing
from barectf.typing import Count, Alignment, _OptStr, Id
import collections.abc
import collections
import datetime
import enum
import uuid as uuidp


@enum.unique
class ByteOrder(enum.Enum):
    LITTLE_ENDIAN = 'le'
    BIG_ENDIAN = 'be'


class _FieldType:
    @property
    def alignment(self) -> Alignment:
        raise NotImplementedError

    @property
    def size_is_dynamic(self):
        return False


class _BitArrayFieldType(_FieldType):
    def __init__(self, size: Count, alignment: Alignment = Alignment(1)):
        self._size = size
        self._alignment = alignment

    @property
    def size(self) -> Count:
        return self._size

    @property
    def alignment(self) -> Alignment:
        return self._alignment


class DisplayBase(enum.Enum):
    BINARY = 2
    OCTAL = 8
    DECIMAL = 10
    HEXADECIMAL = 16


class _IntegerFieldType(_BitArrayFieldType):
    def __init__(self, size: Count, alignment: Optional[Alignment] = None,
                 preferred_display_base: DisplayBase = DisplayBase.DECIMAL):
        if alignment is None:
            alignment = Alignment(8 if size % 8 == 0 else 1)

        super().__init__(size, alignment)
        self._preferred_display_base = preferred_display_base

    @property
    def preferred_display_base(self) -> DisplayBase:
        return self._preferred_display_base


class UnsignedIntegerFieldType(_IntegerFieldType):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mapped_clk_type_name = None
        self._is_len = False


class SignedIntegerFieldType(_IntegerFieldType):
    pass


class EnumerationFieldTypeMappingRange:
    def __init__(self, lower: int, upper: int):
        self._lower = lower
        self._upper = upper

    @property
    def lower(self) -> int:
        return self._lower

    @property
    def upper(self) -> int:
        return self._upper

    def __eq__(self, other: Any) -> bool:
        if type(other) is not type(self):
            return False

        return (self._lower, self._upper) == (other._lower, other._upper)

    def __hash__(self) -> int:
        return hash((self._lower, self._upper))

    def contains(self, value: int) -> bool:
        return self._lower <= value <= self._upper


class EnumerationFieldTypeMapping:
    def __init__(self, ranges: Set[EnumerationFieldTypeMappingRange]):
        self._ranges = frozenset(ranges)

    @property
    def ranges(self) -> FrozenSet[EnumerationFieldTypeMappingRange]:
        return self._ranges

    def ranges_contain_value(self, value: int) -> bool:
        return any([rg.contains(value) for rg in self._ranges])


_EnumFtMappings = Mapping[str, EnumerationFieldTypeMapping]


class EnumerationFieldTypeMappings(collections.abc.Mapping):
    def __init__(self, mappings: _EnumFtMappings):
        self._mappings = {label: mapping for label, mapping in mappings.items()}

    def __getitem__(self, key: str) -> EnumerationFieldTypeMapping:
        return self._mappings[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._mappings)

    def __len__(self) -> int:
        return len(self._mappings)


class _EnumerationFieldType(_IntegerFieldType):
    def __init__(self, size: Count, alignment: Optional[Alignment] = None,
                 preferred_display_base: DisplayBase = DisplayBase.DECIMAL,
                 mappings: Optional[_EnumFtMappings] = None):
        super().__init__(size, alignment, preferred_display_base)
        self._mappings = EnumerationFieldTypeMappings({})

        if mappings is not None:
            self._mappings = EnumerationFieldTypeMappings(mappings)

    @property
    def mappings(self) -> EnumerationFieldTypeMappings:
        return self._mappings

    def labels_for_value(self, value: int) -> Set[str]:
        labels = set()

        for label, mapping in self._mappings.items():
            if mapping.ranges_contain_value(value):
                labels.add(label)

        return labels


class UnsignedEnumerationFieldType(_EnumerationFieldType, UnsignedIntegerFieldType):
    pass


class SignedEnumerationFieldType(_EnumerationFieldType, SignedIntegerFieldType):
    pass


class RealFieldType(_BitArrayFieldType):
    pass


class StringFieldType(_FieldType):
    @property
    def alignment(self) -> Alignment:
        return Alignment(8)

    @property
    def size_is_dynamic(self):
        return True


class _ArrayFieldType(_FieldType):
    def __init__(self, element_field_type: _FieldType):
        self._element_field_type = element_field_type

    @property
    def element_field_type(self) -> _FieldType:
        return self._element_field_type

    @property
    def alignment(self) -> Alignment:
        return self._element_field_type.alignment

    @property
    def size_is_dynamic(self):
        return self._element_field_type.size_is_dynamic


class StaticArrayFieldType(_ArrayFieldType):
    def __init__(self, length: Count, element_field_type: _FieldType):
        super().__init__(element_field_type)
        self._length = length

    @property
    def length(self) -> Count:
        return self._length


class DynamicArrayFieldType(_ArrayFieldType):
    def __init__(self, length_field_type: UnsignedIntegerFieldType, element_field_type: _FieldType):
        super().__init__(element_field_type)
        self._length_field_type = length_field_type
        self._length_ft_member_name: Optional[str] = None

    @property
    def length_field_type(self):
        return self._length_field_type

    @property
    def size_is_dynamic(self):
        return True


class StructureFieldTypeMember:
    def __init__(self, field_type: _FieldType):
        self._field_type = field_type

    @property
    def field_type(self) -> _FieldType:
        return self._field_type


_StructFtMembers = Mapping[str, StructureFieldTypeMember]


class StructureFieldTypeMembers(collections.abc.Mapping):
    def __init__(self, members: _StructFtMembers):
        self._members = collections.OrderedDict()

        for name, member in members.items():
            assert type(member) is StructureFieldTypeMember
            self._members[name] = member

    def __getitem__(self, key: str) -> StructureFieldTypeMember:
        return self._members[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._members)

    def __len__(self) -> int:
        return len(self._members)


class StructureFieldType(_FieldType):
    def __init__(self, minimum_alignment: Alignment = Alignment(1),
                 members: Optional[_StructFtMembers] = None):
        self._minimum_alignment = minimum_alignment
        self._members = StructureFieldTypeMembers({})

        if members is not None:
            self._members = StructureFieldTypeMembers(members)

        self._set_alignment()
        self._set_dyn_array_ft_length_ft_member_names()

    def _set_alignment(self):
        self._alignment: Alignment = self._minimum_alignment

        for member in self._members.values():
            if member.field_type.alignment > self._alignment:
                self._alignment = member.field_type.alignment

    def _set_dyn_array_ft_length_ft_member_names(self):
        for member in self._members.values():
            if type(member.field_type) is DynamicArrayFieldType:
                # Find length field type member name within the same
                # structure field type members.
                for len_name, len_member in self._members.items():
                    if member.field_type.length_field_type is len_member.field_type:
                        member.field_type._length_ft_member_name = len_name
                        len_member.field_type._is_len = True
                        break

            if member.field_type.alignment > self._alignment:
                self._alignment = member.field_type.alignment

    @property
    def minimum_alignment(self) -> Alignment:
        return self._minimum_alignment

    @property
    def alignment(self) -> Alignment:
        return self._alignment

    @property
    def size_is_dynamic(self):
        return any([member.field_type.size_is_dynamic for member in self.members.values()])

    @property
    def members(self) -> StructureFieldTypeMembers:
        return self._members


class _UniqueByName:
    _name: str

    def __eq__(self, other: Any) -> bool:
        if type(other) is not type(self):
            return False

        return self._name == other._name

    def __lt__(self, other: '_UniqueByName'):
        assert type(self) is type(other)
        return self._name < other._name

    def __hash__(self) -> int:
        return hash(self._name)


_OptFt = Optional[_FieldType]
_OptStructFt = Optional[StructureFieldType]
LogLevel = typing.NewType('LogLevel', int)


class EventRecordType(_UniqueByName):
    def __init__(self, name: str, log_level: Optional[LogLevel] = None,
                 specific_context_field_type: _OptStructFt = None, payload_field_type: _OptStructFt = None):
        self._id: Optional[Id] = None
        self._name = name
        self._log_level = log_level
        self._specific_context_field_type = specific_context_field_type
        self._payload_field_type = payload_field_type

    @property
    def id(self) -> Optional[Id]:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def log_level(self) -> Optional[LogLevel]:
        return self._log_level

    @property
    def specific_context_field_type(self) -> _OptStructFt:
        return self._specific_context_field_type

    @property
    def payload_field_type(self) -> _OptStructFt:
        return self._payload_field_type


class ClockTypeOffset:
    def __init__(self, seconds: int = 0, cycles: Count = Count(0)):
        self._seconds = seconds
        self._cycles = cycles

    @property
    def seconds(self) -> int:
        return self._seconds

    @property
    def cycles(self) -> Count:
        return self._cycles


_OptUuid = Optional[uuidp.UUID]


class ClockType(_UniqueByName):
    def __init__(self, name: str, frequency: Count = Count(int(1e9)), uuid: _OptUuid = None,
                 description: _OptStr = None, precision: Count = Count(0),
                 offset: Optional[ClockTypeOffset] = None, origin_is_unix_epoch: bool = False):
        self._name = name
        self._frequency = frequency
        self._uuid = uuid
        self._description = description
        self._precision = precision
        self._offset = ClockTypeOffset()

        if offset is not None:
            self._offset = offset

        self._origin_is_unix_epoch = origin_is_unix_epoch

    @property
    def name(self) -> str:
        return self._name

    @property
    def frequency(self) -> Count:
        return self._frequency

    @property
    def uuid(self) -> _OptUuid:
        return self._uuid

    @property
    def description(self) -> _OptStr:
        return self._description

    @property
    def precision(self) -> Count:
        return self._precision

    @property
    def offset(self) -> ClockTypeOffset:
        return self._offset

    @property
    def origin_is_unix_epoch(self) -> bool:
        return self._origin_is_unix_epoch


DEFAULT_FIELD_TYPE = 'default'
_DefaultableUIntFt = Union[str, UnsignedIntegerFieldType]
_OptDefaultableUIntFt = Optional[_DefaultableUIntFt]
_OptUIntFt = Optional[UnsignedIntegerFieldType]


class DataStreamTypePacketFeatures:
    def __init__(self, total_size_field_type: _DefaultableUIntFt = DEFAULT_FIELD_TYPE,
                 content_size_field_type: _DefaultableUIntFt = DEFAULT_FIELD_TYPE,
                 beginning_timestamp_field_type: _OptDefaultableUIntFt = None,
                 end_timestamp_field_type: _OptDefaultableUIntFt = None,
                 discarded_event_records_snapshot_counter_field_type: _OptDefaultableUIntFt = DEFAULT_FIELD_TYPE):
        def get_ft(user_ft: _OptDefaultableUIntFt) -> _OptUIntFt:
            if user_ft == DEFAULT_FIELD_TYPE:
                return UnsignedIntegerFieldType(64)

            return typing.cast(_OptUIntFt, user_ft)

        self._total_size_field_type = get_ft(total_size_field_type)
        self._content_size_field_type = get_ft(content_size_field_type)
        self._beginning_timestamp_field_type = get_ft(beginning_timestamp_field_type)
        self._end_timestamp_field_type = get_ft(end_timestamp_field_type)
        self._discarded_event_records_snapshot_counter_field_type = get_ft(discarded_event_records_snapshot_counter_field_type)

    @property
    def total_size_field_type(self) -> _OptUIntFt:
        return self._total_size_field_type

    @property
    def content_size_field_type(self) -> _OptUIntFt:
        return self._content_size_field_type

    @property
    def beginning_timestamp_field_type(self) -> _OptUIntFt:
        return self._beginning_timestamp_field_type

    @property
    def end_timestamp_field_type(self) -> _OptUIntFt:
        return self._end_timestamp_field_type

    @property
    def discarded_event_records_snapshot_counter_field_type(self) -> _OptUIntFt:
        return self._discarded_event_records_snapshot_counter_field_type


class DataStreamTypeEventRecordFeatures:
    def __init__(self, type_id_field_type: _OptDefaultableUIntFt = DEFAULT_FIELD_TYPE,
                 timestamp_field_type: _OptDefaultableUIntFt = None):
        def get_ft(user_ft: _OptDefaultableUIntFt) -> _OptUIntFt:
            if user_ft == DEFAULT_FIELD_TYPE:
                return UnsignedIntegerFieldType(64)

            return typing.cast(_OptUIntFt, user_ft)

        self._type_id_field_type = get_ft(type_id_field_type)
        self._timestamp_field_type = get_ft(timestamp_field_type)

    @property
    def type_id_field_type(self) -> _OptUIntFt:
        return self._type_id_field_type

    @property
    def timestamp_field_type(self) -> _OptUIntFt:
        return self._timestamp_field_type


class DataStreamTypeFeatures:
    def __init__(self, packet_features: Optional[DataStreamTypePacketFeatures] = None,
                 event_record_features: Optional[DataStreamTypeEventRecordFeatures] = None):
        if packet_features is None:
            self._packet_features = DataStreamTypePacketFeatures()
        else:
            self._packet_features = packet_features

        if event_record_features is None:
            self._event_record_features = DataStreamTypeEventRecordFeatures()
        else:
            self._event_record_features = event_record_features

    @property
    def packet_features(self) -> DataStreamTypePacketFeatures:
        return self._packet_features

    @property
    def event_record_features(self) -> DataStreamTypeEventRecordFeatures:
        return self._event_record_features


class DataStreamType(_UniqueByName):
    def __init__(self, name: str, event_record_types: Set[EventRecordType],
                 default_clock_type: Optional[ClockType] = None,
                 features: Optional[DataStreamTypeFeatures] = None,
                 packet_context_field_type_extra_members: Optional[_StructFtMembers] = None,
                 event_record_common_context_field_type: _OptStructFt = None):
        self._id: Optional[Id] = None
        self._name = name
        self._default_clock_type = default_clock_type
        self._event_record_common_context_field_type = event_record_common_context_field_type
        self._event_record_types = frozenset(event_record_types)

        # assign unique IDs
        for index, ert in enumerate(sorted(self._event_record_types, key=lambda evt: evt.name)):
            assert ert._id is None
            ert._id = Id(index)

        self._set_features(features)
        self._packet_context_field_type_extra_members = StructureFieldTypeMembers({})

        if packet_context_field_type_extra_members is not None:
            self._packet_context_field_type_extra_members = StructureFieldTypeMembers(packet_context_field_type_extra_members)

        self._set_pkt_ctx_ft()
        self._set_er_header_ft()

    def _set_features(self, features: Optional[DataStreamTypeFeatures]):
        if features is not None:
            self._features = features
            return None

        er_ts_ft = None
        pkt_beginning_ts_ft = None
        pkt_end_ts_ft = None

        if self._default_clock_type is not None:
            # Automatic timestamp field types because the data stream
            # type has a default clock type.
            er_ts_ft = DEFAULT_FIELD_TYPE
            pkt_beginning_ts_ft = DEFAULT_FIELD_TYPE
            pkt_end_ts_ft = DEFAULT_FIELD_TYPE

        self._features = DataStreamTypeFeatures(DataStreamTypePacketFeatures(beginning_timestamp_field_type=pkt_beginning_ts_ft,
                                                                             end_timestamp_field_type=pkt_end_ts_ft),
                                                DataStreamTypeEventRecordFeatures(timestamp_field_type=er_ts_ft))

    def _set_ft_mapped_clk_type_name(self, ft: Optional[UnsignedIntegerFieldType]):
        if ft is None:
            return

        if self._default_clock_type is not None:
            assert isinstance(ft, UnsignedIntegerFieldType)
            ft._mapped_clk_type_name = self._default_clock_type.name

    def _set_pkt_ctx_ft(self):
        members = None

        def add_member_if_exists(name: str, ft: _FieldType, set_mapped_clk_type_name: bool = False):
            nonlocal members

            if ft is not None:
                if set_mapped_clk_type_name:
                    self._set_ft_mapped_clk_type_name(typing.cast(UnsignedIntegerFieldType, ft))

                members[name] = StructureFieldTypeMember(ft)

        members = collections.OrderedDict([
            (
                'packet_size',
                StructureFieldTypeMember(self._features.packet_features.total_size_field_type)
            ),
            (
                'content_size',
                StructureFieldTypeMember(self._features.packet_features.content_size_field_type)
            )
        ])

        add_member_if_exists('timestamp_begin',
                             self._features.packet_features.beginning_timestamp_field_type, True)
        add_member_if_exists('timestamp_end', self._features.packet_features.end_timestamp_field_type,
                             True)
        add_member_if_exists('events_discarded',
                             self._features.packet_features.discarded_event_records_snapshot_counter_field_type)

        if self._packet_context_field_type_extra_members is not None:
            for name, field_type in self._packet_context_field_type_extra_members.items():
                assert name not in members
                members[name] = field_type

        self._pkt_ctx_ft = StructureFieldType(8, members)

    def _set_er_header_ft(self):
        members = collections.OrderedDict()

        if self._features.event_record_features.type_id_field_type is not None:
            members['id'] = StructureFieldTypeMember(self._features.event_record_features.type_id_field_type)

        if self._features.event_record_features.timestamp_field_type is not None:
            ft = self._features.event_record_features.timestamp_field_type
            self._set_ft_mapped_clk_type_name(ft)
            members['timestamp'] = StructureFieldTypeMember(ft)

        self._er_header_ft = StructureFieldType(8, members)

    @property
    def id(self) -> Optional[Id]:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def default_clock_type(self) -> Optional[ClockType]:
        return self._default_clock_type

    @property
    def features(self) -> DataStreamTypeFeatures:
        return self._features

    @property
    def packet_context_field_type_extra_members(self) -> StructureFieldTypeMembers:
        return self._packet_context_field_type_extra_members

    @property
    def event_record_common_context_field_type(self) -> _OptStructFt:
        return self._event_record_common_context_field_type

    @property
    def event_record_types(self) -> FrozenSet[EventRecordType]:
        return self._event_record_types


_OptUuidFt = Optional[Union[str, StaticArrayFieldType]]


class TraceTypeFeatures:
    def __init__(self, magic_field_type: _OptDefaultableUIntFt = DEFAULT_FIELD_TYPE,
                 uuid_field_type: _OptUuidFt = None,
                 data_stream_type_id_field_type: _OptDefaultableUIntFt = DEFAULT_FIELD_TYPE):
        def get_field_type(user_ft: Optional[Union[str, _FieldType]],
                           create_default_ft: Callable[[], _FieldType]) -> _OptFt:
            if user_ft == DEFAULT_FIELD_TYPE:
                return create_default_ft()

            return typing.cast(_OptFt, user_ft)

        def create_default_magic_ft():
            return UnsignedIntegerFieldType(32)

        def create_default_uuid_ft():
            return StaticArrayFieldType(Count(16), UnsignedIntegerFieldType(8))

        def create_default_dst_id_ft():
            return UnsignedIntegerFieldType(64)

        self._magic_field_type = typing.cast(_OptUIntFt, get_field_type(magic_field_type, create_default_magic_ft))
        self._uuid_field_type = typing.cast(Optional[StaticArrayFieldType],
                                            get_field_type(uuid_field_type, create_default_uuid_ft))
        self._data_stream_type_id_field_type = typing.cast(_OptUIntFt,
                                                           get_field_type(data_stream_type_id_field_type,
                                                                          create_default_dst_id_ft))

    @property
    def magic_field_type(self) -> _OptUIntFt:
        return self._magic_field_type

    @property
    def uuid_field_type(self) -> Optional[StaticArrayFieldType]:
        return self._uuid_field_type

    @property
    def data_stream_type_id_field_type(self) -> _OptUIntFt:
        return self._data_stream_type_id_field_type


class TraceType:
    def __init__(self, native_byte_order: ByteOrder, data_stream_types: Set[DataStreamType],
                 uuid: _OptUuid = None, features: Optional[TraceTypeFeatures] = None):
        self._native_byte_order = native_byte_order
        self._data_stream_types = frozenset(data_stream_types)

        # assign unique IDs
        for index, dst in enumerate(sorted(self._data_stream_types, key=lambda st: st.name)):
            assert dst._id is None
            dst._id = Id(index)

        self._uuid = uuid
        self._set_features(features)
        self._set_pkt_header_ft()

    def _set_features(self, features: Optional[TraceTypeFeatures]):
        if features is not None:
            self._features = features
            return

        # automatic UUID field type because the trace type has a UUID
        uuid_ft = None if self._uuid is None else DEFAULT_FIELD_TYPE
        self._features = TraceTypeFeatures(uuid_field_type=uuid_ft)

    def _set_pkt_header_ft(self):
        members = collections.OrderedDict()

        def add_member_if_exists(name: str, ft: _OptFt):
            nonlocal members

            if ft is not None:
                members[name] = StructureFieldTypeMember(ft)

        add_member_if_exists('magic', self._features.magic_field_type)
        add_member_if_exists('uuid', self._features.uuid_field_type)
        add_member_if_exists('stream_id', self._features.data_stream_type_id_field_type)
        self._pkt_header_ft = StructureFieldType(8, members)

    @property
    def native_byte_order(self) -> ByteOrder:
        return self._native_byte_order

    @property
    def uuid(self) -> _OptUuid:
        return self._uuid

    @property
    def data_stream_types(self) -> FrozenSet[DataStreamType]:
        return self._data_stream_types

    def data_stream_type(self, name: str) -> Optional[DataStreamType]:
        for cand_dst in self._data_stream_types:
            if cand_dst.name == name:
                return cand_dst

        return None

    @property
    def features(self) -> TraceTypeFeatures:
        return self._features

    @property
    def clock_types(self) -> Set[ClockType]:
        clk_types = set()

        for dst in self._data_stream_types:
            if dst.default_clock_type is not None:
                clk_types.add(dst.default_clock_type)

        return clk_types


_EnvEntry = Union[str, int]
_EnvEntries = Mapping[str, _EnvEntry]


class TraceEnvironment(collections.abc.Mapping):
    def __init__(self, environment: _EnvEntries):
        self._env = {name: value for name, value in environment.items()}

    def __getitem__(self, key: str) -> _EnvEntry:
        return self._env[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._env)

    def __len__(self) -> int:
        return len(self._env)


class Trace:
    def __init__(self, type: TraceType, environment: Optional[_EnvEntries] = None):
        self._type = type
        self._set_env(environment)

    def _set_env(self, environment: Optional[_EnvEntries]):
        init_env = collections.OrderedDict([
            ('domain', 'bare'),
            ('tracer_name', 'barectf'),
            ('tracer_major', barectf_version.__major_version__),
            ('tracer_minor', barectf_version.__minor_version__),
            ('tracer_patch', barectf_version.__patch_version__),
            ('tracer_pre', barectf_version.__pre_version__),
            ('barectf_gen_date', str(datetime.datetime.now().isoformat())),
        ])

        if environment is None:
            environment = {}

        init_env.update(environment)
        self._env = TraceEnvironment(typing.cast(_EnvEntries, init_env))

    @property
    def type(self) -> TraceType:
        return self._type

    @property
    def environment(self) -> TraceEnvironment:
        return self._env


_ClkTypeCTypes = Mapping[ClockType, str]


class ClockTypeCTypes(collections.abc.Mapping):
    def __init__(self, c_types: _ClkTypeCTypes):
        self._c_types = {clk_type: c_type for clk_type, c_type in c_types.items()}

    def __getitem__(self, key: ClockType) -> str:
        return self._c_types[key]

    def __iter__(self) -> Iterator[ClockType]:
        return iter(self._c_types)

    def __len__(self) -> int:
        return len(self._c_types)


class ConfigurationCodeGenerationHeaderOptions:
    def __init__(self, identifier_prefix_definition: bool = False,
                 default_data_stream_type_name_definition: bool = False):
        self._identifier_prefix_definition = identifier_prefix_definition
        self._default_data_stream_type_name_definition = default_data_stream_type_name_definition

    @property
    def identifier_prefix_definition(self) -> bool:
        return self._identifier_prefix_definition

    @property
    def default_data_stream_type_name_definition(self) -> bool:
        return self._default_data_stream_type_name_definition


class ConfigurationCodeGenerationOptions:
    def __init__(self, identifier_prefix: str = 'barectf_', file_name_prefix: str = 'barectf',
                 default_data_stream_type: Optional[DataStreamType] = None,
                 header_options: Optional[ConfigurationCodeGenerationHeaderOptions] = None,
                 clock_type_c_types: Optional[_ClkTypeCTypes] = None):
        self._identifier_prefix = identifier_prefix
        self._file_name_prefix = file_name_prefix
        self._default_data_stream_type = default_data_stream_type

        self._header_options = ConfigurationCodeGenerationHeaderOptions()

        if header_options is not None:
            self._header_options = header_options

        self._clock_type_c_types = ClockTypeCTypes({})

        if clock_type_c_types is not None:
            self._clock_type_c_types = ClockTypeCTypes(clock_type_c_types)

    @property
    def identifier_prefix(self) -> str:
        return self._identifier_prefix

    @property
    def file_name_prefix(self) -> str:
        return self._file_name_prefix

    @property
    def default_data_stream_type(self) -> Optional[DataStreamType]:
        return self._default_data_stream_type

    @property
    def header_options(self) -> ConfigurationCodeGenerationHeaderOptions:
        return self._header_options

    @property
    def clock_type_c_types(self) -> ClockTypeCTypes:
        return self._clock_type_c_types


class ConfigurationOptions:
    def __init__(self,
                 code_generation_options: Optional[ConfigurationCodeGenerationOptions] = None):
        self._code_generation_options = ConfigurationCodeGenerationOptions()

        if code_generation_options is not None:
            self._code_generation_options = code_generation_options

    @property
    def code_generation_options(self) -> ConfigurationCodeGenerationOptions:
        return self._code_generation_options


class Configuration:
    def __init__(self, trace: Trace, options: Optional[ConfigurationOptions] = None):
        self._trace = trace
        self._options = ConfigurationOptions()

        if options is not None:
            self._options = options

        clk_type_c_types = self._options.code_generation_options.clock_type_c_types

        for dst in trace.type.data_stream_types:
            def_clk_type = dst.default_clock_type

            if def_clk_type is None:
                continue

            if def_clk_type not in clk_type_c_types:
                clk_type_c_types._c_types[def_clk_type] = 'uint32_t'

    @property
    def trace(self) -> Trace:
        return self._trace

    @property
    def options(self) -> ConfigurationOptions:
        return self._options
