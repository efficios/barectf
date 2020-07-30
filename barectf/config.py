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
import collections.abc
import collections
import datetime
import enum


@enum.unique
class ByteOrder(enum.Enum):
    LITTLE_ENDIAN = 'le'
    BIG_ENDIAN = 'be'


class _FieldType:
    @property
    def alignment(self):
        raise NotImplementedError


class _BitArrayFieldType(_FieldType):
    def __init__(self, size, byte_order=None, alignment=1):
        self._size = size
        self._byte_order = byte_order
        self._alignment = alignment

    @property
    def size(self):
        return self._size

    @property
    def byte_order(self):
        return self._byte_order

    @property
    def alignment(self):
        return self._alignment


class DisplayBase(enum.Enum):
    BINARY = 2
    OCTAL = 8
    DECIMAL = 10
    HEXADECIMAL = 16


class _IntegerFieldType(_BitArrayFieldType):
    def __init__(self, size, byte_order=None, alignment=None,
                 preferred_display_base=DisplayBase.DECIMAL):
        effective_alignment = 1

        if alignment is None and size % 8 == 0:
            effective_alignment = 8

        super().__init__(size, byte_order, effective_alignment)
        self._preferred_display_base = preferred_display_base

    @property
    def preferred_display_base(self):
        return self._preferred_display_base


class UnsignedIntegerFieldType(_IntegerFieldType):
    def __init__(self, *args):
        super().__init__(*args)
        self._mapped_clk_type_name = None


class SignedIntegerFieldType(_IntegerFieldType):
    pass


class EnumerationFieldTypeMappingRange:
    def __init__(self, lower, upper):
        self._lower = lower
        self._upper = upper

    @property
    def lower(self):
        return self._lower

    @property
    def upper(self):
        return self._upper

    def __eq__(self, other):
        if type(other) is not type(self):
            return False

        return (self._lower, self._upper) == (other._lower, other._upper)

    def __hash__(self):
        return hash((self._lower, self._upper))

    def contains(self, value):
        return self._lower <= value <= self._upper


class EnumerationFieldTypeMapping:
    def __init__(self, ranges):
        self._ranges = frozenset(ranges)

    @property
    def ranges(self):
        return self._ranges

    def ranges_contain_value(self, value):
        return any([rg.contains(value) for rg in self._ranges])


class EnumerationFieldTypeMappings(collections.abc.Mapping):
    def __init__(self, mappings):
        self._mappings = {label: mapping for label, mapping in mappings.items()}

    def __getitem__(self, key):
        return self._mappings[key]

    def __iter__(self):
        return iter(self._mappings)

    def __len__(self):
        return len(self._mappings)


class _EnumerationFieldType(_IntegerFieldType):
    def __init__(self, size, byte_order=None, alignment=None,
                 preferred_display_base=DisplayBase.DECIMAL, mappings=None):
        super().__init__(size, byte_order, alignment, preferred_display_base)
        self._mappings = EnumerationFieldTypeMappings({})

        if mappings is not None:
            self._mappings = EnumerationFieldTypeMappings(mappings)

    @property
    def mappings(self):
        return self._mappings

    def labels_for_value(self, value):
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
    def alignment(self):
        return 8


class _ArrayFieldType(_FieldType):
    def __init__(self, element_field_type):
        self._element_field_type = element_field_type

    @property
    def element_field_type(self):
        return self._element_field_type

    @property
    def alignment(self):
        return self._element_field_type.alignment


class StaticArrayFieldType(_ArrayFieldType):
    def __init__(self, length, element_field_type):
        super().__init__(element_field_type)
        self._length = length

    @property
    def length(self):
        return self._length


class StructureFieldTypeMember:
    def __init__(self, field_type):
        self._field_type = field_type

    @property
    def field_type(self):
        return self._field_type


class StructureFieldTypeMembers(collections.abc.Mapping):
    def __init__(self, members):
        self._members = collections.OrderedDict()

        for name, member in members.items():
            assert type(member) is StructureFieldTypeMember
            self._members[name] = member

    def __getitem__(self, key):
        return self._members[key]

    def __iter__(self):
        return iter(self._members)

    def __len__(self):
        return len(self._members)


class StructureFieldType(_FieldType):
    def __init__(self, minimum_alignment=1, members=None):
        self._minimum_alignment = minimum_alignment
        self._members = StructureFieldTypeMembers({})

        if members is not None:
            self._members = StructureFieldTypeMembers(members)

        self._set_alignment()

    def _set_alignment(self):
        self._alignment = self._minimum_alignment

        for member in self._members.values():
            if member.field_type.alignment > self._alignment:
                self._alignment = member.field_type.alignment

    @property
    def minimum_alignment(self):
        return self._minimum_alignment

    @property
    def alignment(self):
        return self._alignment

    @property
    def members(self):
        return self._members


class _UniqueByName:
    def __eq__(self, other):
        if type(other) is not type(self):
            return False

        return self._name == other._name

    def __lt__(self, other):
        assert type(self) is type(other)
        return self._name < other._name

    def __hash__(self):
        return hash(self._name)


class EventType(_UniqueByName):
    def __init__(self, name, log_level=None, specific_context_field_type=None,
                 payload_field_type=None):
        self._id = None
        self._name = name
        self._log_level = log_level
        self._specific_context_field_type = specific_context_field_type
        self._payload_field_type = payload_field_type

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def log_level(self):
        return self._log_level

    @property
    def specific_context_field_type(self):
        return self._specific_context_field_type

    @property
    def payload_field_type(self):
        return self._payload_field_type


class ClockTypeOffset:
    def __init__(self, seconds=0, cycles=0):
        self._seconds = seconds
        self._cycles = cycles

    @property
    def seconds(self):
        return self._seconds

    @property
    def cycles(self):
        return self._cycles


class ClockType(_UniqueByName):
    def __init__(self, name, frequency=int(1e9), uuid=None, description=None, precision=0,
                 offset=None, origin_is_unix_epoch=False):
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
    def name(self):
        return self._name

    @property
    def frequency(self):
        return self._frequency

    @property
    def uuid(self):
        return self._uuid

    @property
    def description(self):
        return self._description

    @property
    def precision(self):
        return self._precision

    @property
    def offset(self):
        return self._offset

    @property
    def origin_is_unix_epoch(self):
        return self._origin_is_unix_epoch


DEFAULT_FIELD_TYPE = 'default'


class StreamTypePacketFeatures:
    def __init__(self, total_size_field_type=DEFAULT_FIELD_TYPE,
                 content_size_field_type=DEFAULT_FIELD_TYPE, beginning_time_field_type=None,
                 end_time_field_type=None, discarded_events_counter_field_type=None):
        def get_ft(user_ft):
            if user_ft == DEFAULT_FIELD_TYPE:
                return UnsignedIntegerFieldType(64)

            return user_ft

        self._total_size_field_type = get_ft(total_size_field_type)
        self._content_size_field_type = get_ft(content_size_field_type)
        self._beginning_time_field_type = get_ft(beginning_time_field_type)
        self._end_time_field_type = get_ft(end_time_field_type)
        self._discarded_events_counter_field_type = get_ft(discarded_events_counter_field_type)

    @property
    def total_size_field_type(self):
        return self._total_size_field_type

    @property
    def content_size_field_type(self):
        return self._content_size_field_type

    @property
    def beginning_time_field_type(self):
        return self._beginning_time_field_type

    @property
    def end_time_field_type(self):
        return self._end_time_field_type

    @property
    def discarded_events_counter_field_type(self):
        return self._discarded_events_counter_field_type


class StreamTypeEventFeatures:
    def __init__(self, type_id_field_type=DEFAULT_FIELD_TYPE, time_field_type=None):
        def get_ft(user_field_type):
            if user_field_type == DEFAULT_FIELD_TYPE:
                return UnsignedIntegerFieldType(64)

            return user_field_type

        self._type_id_field_type = get_ft(type_id_field_type)
        self._time_field_type = get_ft(time_field_type)

    @property
    def type_id_field_type(self):
        return self._type_id_field_type

    @property
    def time_field_type(self):
        return self._time_field_type


class StreamTypeFeatures:
    def __init__(self, packet_features=None, event_features=None):
        self._packet_features = StreamTypePacketFeatures()

        if packet_features is not None:
            self._packet_features = packet_features

        self._event_features = StreamTypeEventFeatures()

        if event_features is not None:
            self._event_features = event_features

    @property
    def packet_features(self):
        return self._packet_features

    @property
    def event_features(self):
        return self._event_features


class StreamType(_UniqueByName):
    def __init__(self, name, event_types, default_clock_type=None, features=None,
                 packet_context_field_type_extra_members=None,
                 event_common_context_field_type=None):
        self._id = None
        self._name = name
        self._default_clock_type = default_clock_type
        self._event_common_context_field_type = event_common_context_field_type
        self._event_types = frozenset(event_types)

        # assign unique IDs
        for index, ev_type in enumerate(sorted(self._event_types, key=lambda evt: evt.name)):
            assert ev_type._id is None
            ev_type._id = index

        self._set_features(features)
        self._packet_context_field_type_extra_members = StructureFieldTypeMembers({})

        if packet_context_field_type_extra_members is not None:
            self._packet_context_field_type_extra_members = StructureFieldTypeMembers(packet_context_field_type_extra_members)

        self._set_pkt_ctx_ft()
        self._set_ev_header_ft()

    def _set_features(self, features):
        if features is not None:
            self._features = features
            return

        ev_time_ft = None
        pkt_beginning_time_ft = None
        pkt_end_time_ft = None

        if self._default_clock_type is not None:
            # Automatic time field types because the stream type has a
            # default clock type.
            ev_time_ft = DEFAULT_FIELD_TYPE
            pkt_beginning_time_ft = DEFAULT_FIELD_TYPE
            pkt_end_time_ft = DEFAULT_FIELD_TYPE

        self._features = StreamTypeFeatures(StreamTypePacketFeatures(beginning_time_field_type=pkt_beginning_time_ft,
                                                                     end_time_field_type=pkt_end_time_ft),
                                            StreamTypeEventFeatures(time_field_type=ev_time_ft))

    def _set_ft_mapped_clk_type_name(self, ft):
        if ft is None:
            return

        if self._default_clock_type is not None:
            assert isinstance(ft, UnsignedIntegerFieldType)
            ft._mapped_clk_type_name = self._default_clock_type.name

    def _set_pkt_ctx_ft(self):
        def add_member_if_exists(name, ft, set_mapped_clk_type_name=False):
            nonlocal members

            if ft is not None:
                if set_mapped_clk_type_name:
                    self._set_ft_mapped_clk_type_name(ft)

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
                             self._features.packet_features.beginning_time_field_type, True)
        add_member_if_exists('timestamp_end', self._features.packet_features.end_time_field_type,
                             True)
        add_member_if_exists('events_discarded',
                             self._features.packet_features.discarded_events_counter_field_type)

        if self._packet_context_field_type_extra_members is not None:
            for name, field_type in self._packet_context_field_type_extra_members.items():
                assert name not in members
                members[name] = field_type

        self._pkt_ctx_ft = StructureFieldType(8, members)

    def _set_ev_header_ft(self):
        members = collections.OrderedDict()

        if self._features.event_features.type_id_field_type is not None:
            members['id'] = StructureFieldTypeMember(self._features.event_features.type_id_field_type)

        if self._features.event_features.time_field_type is not None:
            ft = self._features.event_features.time_field_type
            self._set_ft_mapped_clk_type_name(ft)
            members['timestamp'] = StructureFieldTypeMember(ft)

        self._ev_header_ft = StructureFieldType(8, members)

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def default_clock_type(self):
        return self._default_clock_type

    @property
    def features(self):
        return self._features

    @property
    def packet_context_field_type_extra_members(self):
        return self._packet_context_field_type_extra_members

    @property
    def event_common_context_field_type(self):
        return self._event_common_context_field_type

    @property
    def event_types(self):
        return self._event_types


class TraceTypeFeatures:
    def __init__(self, magic_field_type=DEFAULT_FIELD_TYPE, uuid_field_type=None,
                 stream_type_id_field_type=DEFAULT_FIELD_TYPE):
        def get_field_type(user_field_type, default_field_type):
            if user_field_type == DEFAULT_FIELD_TYPE:
                return default_field_type

            return user_field_type

        self._magic_field_type = get_field_type(magic_field_type, UnsignedIntegerFieldType(32))
        self._uuid_field_type = get_field_type(uuid_field_type,
                                               StaticArrayFieldType(16, UnsignedIntegerFieldType(8)))
        self._stream_type_id_field_type = get_field_type(stream_type_id_field_type,
                                                         UnsignedIntegerFieldType(64))

    @property
    def magic_field_type(self):
        return self._magic_field_type

    @property
    def uuid_field_type(self):
        return self._uuid_field_type

    @property
    def stream_type_id_field_type(self):
        return self._stream_type_id_field_type


class TraceType:
    def __init__(self, stream_types, default_byte_order, uuid=None, features=None):
        self._default_byte_order = default_byte_order
        self._stream_types = frozenset(stream_types)

        # assign unique IDs
        for index, stream_type in enumerate(sorted(self._stream_types, key=lambda st: st.name)):
            assert stream_type._id is None
            stream_type._id = index

        self._uuid = uuid
        self._set_features(features)
        self._set_pkt_header_ft()
        self._set_fts_effective_byte_order()

    def _set_features(self, features):
        if features is not None:
            self._features = features
            return

        # automatic UUID field type because the trace type has a UUID
        uuid_ft = None if self._uuid is None else DEFAULT_FIELD_TYPE
        self._features = TraceTypeFeatures(uuid_field_type=uuid_ft)

    def _set_pkt_header_ft(self):
        def add_member_if_exists(name, field_type):
            nonlocal members

            if field_type is not None:
                members[name] = StructureFieldTypeMember(field_type)

        members = collections.OrderedDict()
        add_member_if_exists('magic', self._features.magic_field_type)
        add_member_if_exists('uuid', self._features.uuid_field_type)
        add_member_if_exists('stream_id', self._features.stream_type_id_field_type)
        self._pkt_header_ft = StructureFieldType(8, members)

    def _set_fts_effective_byte_order(self):
        def set_ft_effective_byte_order(ft):
            if ft is None:
                return

            if isinstance(ft, _BitArrayFieldType):
                if ft._byte_order is None:
                    assert self._default_byte_order is not None
                    ft._byte_order = self._default_byte_order
            elif isinstance(ft, StaticArrayFieldType):
                set_ft_effective_byte_order(ft.element_field_type)
            elif isinstance(ft, StructureFieldType):
                for member in ft.members.values():
                    set_ft_effective_byte_order(member.field_type)

        # packet header field type
        set_ft_effective_byte_order(self._pkt_header_ft)

        # stream type field types
        for stream_type in self._stream_types:
            set_ft_effective_byte_order(stream_type._pkt_ctx_ft)
            set_ft_effective_byte_order(stream_type._ev_header_ft)
            set_ft_effective_byte_order(stream_type._event_common_context_field_type)

            # event type field types
            for ev_type in stream_type.event_types:
                set_ft_effective_byte_order(ev_type._specific_context_field_type)
                set_ft_effective_byte_order(ev_type._payload_field_type)

    @property
    def default_byte_order(self):
        return self._default_byte_order

    @property
    def uuid(self):
        return self._uuid

    @property
    def stream_types(self):
        return self._stream_types

    def stream_type(self, name):
        for cand_stream_type in self._stream_types:
            if cand_stream_type.name == name:
                return cand_stream_type

    @property
    def features(self):
        return self._features


class TraceEnvironment(collections.abc.Mapping):
    def __init__(self, environment):
        self._env = {name: value for name, value in environment.items()}

    def __getitem__(self, key):
        return self._env[key]

    def __iter__(self):
        return iter(self._env)

    def __len__(self):
        return len(self._env)


class Trace:
    def __init__(self, type, environment=None):
        self._type = type
        self._set_env(environment)

    def _set_env(self, environment):
        init_env = collections.OrderedDict([
            ('domain', 'bare'),
            ('tracer_name', 'barectf'),
            ('tracer_major', barectf_version.__major_version__),
            ('tracer_minor', barectf_version.__minor_version__),
            ('tracer_patch', barectf_version.__patch_version__),
            ('barectf_gen_date', str(datetime.datetime.now().isoformat())),
        ])

        if environment is None:
            environment = {}

        init_env.update(environment)
        self._env = TraceEnvironment(init_env)

    @property
    def type(self):
        return self._type

    @property
    def environment(self):
        return self._env


class ClockTypeCTypes(collections.abc.Mapping):
    def __init__(self, c_types):
        self._c_types = {clk_type: c_type for clk_type, c_type in c_types.items()}

    def __getitem__(self, key):
        return self._c_types[key]

    def __iter__(self):
        return iter(self._c_types)

    def __len__(self):
        return len(self._c_types)


class ConfigurationCodeGenerationHeaderOptions:
    def __init__(self, identifier_prefix_definition=False,
                 default_stream_type_name_definition=False):
        self._identifier_prefix_definition = identifier_prefix_definition
        self._default_stream_type_name_definition = default_stream_type_name_definition

    @property
    def identifier_prefix_definition(self):
        return self._identifier_prefix_definition

    @property
    def default_stream_type_name_definition(self):
        return self._default_stream_type_name_definition


class ConfigurationCodeGenerationOptions:
    def __init__(self, identifier_prefix='barectf_', file_name_prefix='barectf',
                 default_stream_type=None, header_options=None, clock_type_c_types=None):
        self._identifier_prefix = identifier_prefix
        self._file_name_prefix = file_name_prefix
        self._default_stream_type = default_stream_type

        self._header_options = ConfigurationCodeGenerationHeaderOptions()

        if header_options is not None:
            self._header_options = header_options

        self._clock_type_c_types = ClockTypeCTypes({})

        if clock_type_c_types is not None:
            self._clock_type_c_types = ClockTypeCTypes(clock_type_c_types)

    @property
    def identifier_prefix(self):
        return self._identifier_prefix

    @property
    def file_name_prefix(self):
        return self._file_name_prefix

    @property
    def default_stream_type(self):
        return self._default_stream_type

    @property
    def header_options(self):
        return self._header_options

    @property
    def clock_type_c_types(self):
        return self._clock_type_c_types


class ConfigurationOptions:
    def __init__(self, code_generation_options=None):
        self._code_generation_options = ConfigurationCodeGenerationOptions()

        if code_generation_options is not None:
            self._code_generation_options = code_generation_options

    @property
    def code_generation_options(self):
        return self._code_generation_options


class Configuration:
    def __init__(self, trace, options=None):
        self._trace = trace
        self._options = ConfigurationOptions()

        if options is not None:
            self._options = options

        clk_type_c_types = self._options.code_generation_options.clock_type_c_types

        for stream_type in trace.type.stream_types:
            def_clk_type = stream_type.default_clock_type

            if def_clk_type is None:
                continue

            if def_clk_type not in clk_type_c_types:
                clk_type_c_types._c_types[def_clk_type] = 'uint32_t'

    @property
    def trace(self):
        return self._trace

    @property
    def options(self):
        return self._options
