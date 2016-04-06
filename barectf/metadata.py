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

import enum
import collections


@enum.unique
class ByteOrder(enum.Enum):
    LE = 0
    BE = 1


@enum.unique
class Encoding(enum.Enum):
    NONE = 0
    UTF8 = 1
    ASCII = 2


class Type:
    @property
    def align(self):
        return None

    @property
    def size(self):
        pass

    @property
    def is_dynamic(self):
        raise NotImplementedError()


class PropertyMapping:
    def __init__(self, object, prop):
        self._object = object
        self._prop = prop

    @property
    def object(self):
        return self._object

    @object.setter
    def object(self, value):
        self._object = value

    @property
    def prop(self):
        return self.prop

    @prop.setter
    def prop(self, value):
        self.prop = value


class Integer(Type):
    def __init__(self):
        self.set_default_size()
        self.set_default_align()
        self.set_default_signed()
        self.set_default_byte_order()
        self.set_default_base()
        self.set_default_encoding()
        self.set_default_property_mappings()

    def set_default_size(self):
        self._size = None

    def set_default_align(self):
        self._align = None

    def set_default_signed(self):
        self._signed = False

    def set_default_byte_order(self):
        self._byte_order = None

    def set_default_base(self):
        self._base = 10

    def set_default_encoding(self):
        self._encoding = Encoding.NONE

    def set_default_property_mappings(self):
        self._property_mappings = []

    @property
    def signed(self):
        return self._signed

    @signed.setter
    def signed(self, value):
        self._signed = value

    @property
    def byte_order(self):
        return self._byte_order

    @byte_order.setter
    def byte_order(self, value):
        self._byte_order = value

    @property
    def base(self):
        return self._base

    @base.setter
    def base(self, value):
        self._base = value

    @property
    def encoding(self):
        return self._encoding

    @encoding.setter
    def encoding(self, value):
        self._encoding = value

    @property
    def align(self):
        if self._align is None:
            if self._size is None:
                return
            else:
                if self._size % 8 == 0:
                    return 8
                else:
                    return 1
        else:
            return self._align

    @align.setter
    def align(self, value):
        self._align = value

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, value):
        self._size = value

    @property
    def property_mappings(self):
        return self._property_mappings

    @property
    def is_dynamic(self):
        return False


class FloatingPoint(Type):
    def __init__(self):
        self.set_default_exp_size()
        self.set_default_mant_size()
        self.set_default_align()
        self.set_default_byte_order()

    def set_default_exp_size(self):
        self._exp_size = None

    def set_default_mant_size(self):
        self._mant_size = None

    def set_default_align(self):
        self._align = 8

    def set_default_byte_order(self):
        self._byte_order = None

    @property
    def exp_size(self):
        return self._exp_size

    @exp_size.setter
    def exp_size(self, value):
        self._exp_size = value

    @property
    def mant_size(self):
        return self._mant_size

    @mant_size.setter
    def mant_size(self, value):
        self._mant_size = value

    @property
    def size(self):
        if self._exp_size is None or self._mant_size is None:
            return

        return self._exp_size + self._mant_size

    @property
    def byte_order(self):
        return self._byte_order

    @byte_order.setter
    def byte_order(self, value):
        self._byte_order = value

    @property
    def align(self):
        return self._align

    @align.setter
    def align(self, value):
        self._align = value

    @property
    def is_dynamic(self):
        return False


class Enum(Type):
    def __init__(self):
        self.set_default_value_type()
        self.set_default_members()

    def set_default_value_type(self):
        self._value_type = None

    def set_default_members(self):
        self._members = collections.OrderedDict()

    @property
    def align(self):
        return self._value_type.align

    @property
    def size(self):
        return self._value_type.size

    @property
    def value_type(self):
        return self._value_type

    @value_type.setter
    def value_type(self, value):
        self._value_type = value

    @property
    def members(self):
        return self._members

    @property
    def last_value(self):
        if not self._members:
            return

        return list(self._members.values())[-1][1]

    def value_of(self, label):
        return self._members[label]

    def label_of(self, value):
        for label, vrange in self._members.items():
            if value >= vrange[0] and value <= vrange[1]:
                return label

    def __getitem__(self, key):
        if type(key) is str:
            return self.value_of(key)
        elif type(key) is int:
            return self.label_of(key)

        raise TypeError('wrong subscript type')

    @property
    def is_dynamic(self):
        return False


class String(Type):
    def __init__(self):
        self.set_default_encoding()

    def set_default_encoding(self):
        self._encoding = Encoding.UTF8

    @property
    def align(self):
        return 8

    @property
    def encoding(self):
        return self._encoding

    @encoding.setter
    def encoding(self, value):
        self._encoding = value

    @property
    def is_dynamic(self):
        return True


class Array(Type):
    def __init__(self):
        self.set_default_element_type()
        self.set_default_length()

    def set_default_element_type(self):
        self._default_element_type = None

    def set_default_length(self):
        self._default_length = None

    @property
    def align(self):
        return self._element_type.align

    @property
    def element_type(self):
        return self._element_type

    @element_type.setter
    def element_type(self, value):
        self._element_type = value

    @property
    def length(self):
        return self._length

    @length.setter
    def length(self, value):
        self._length = value

    @property
    def is_variable_length(self):
        return type(self._length) is not int

    @property
    def is_dynamic(self):
        if self.is_variable_length:
            return True

        return self.element_type.is_dynamic


class Struct(Type):
    def __init__(self):
        self.set_default_min_align()
        self.set_default_fields()

    def set_default_min_align(self):
        self._min_align = 1

    def set_default_fields(self):
        self._fields = collections.OrderedDict()

    @property
    def min_align(self):
        return self._min_align

    @min_align.setter
    def min_align(self, value):
        self._min_align = value

    @property
    def align(self):
        align = self.min_align

        for field in self.fields.values():
            if field.align is None:
                return

            if field.align > align:
                align = field.align

        return align

    @property
    def is_dynamic(self):
        for field in self.fields.values():
            if field.is_dynamic:
                return True

        return False

    @property
    def fields(self):
        return self._fields

    def __getitem__(self, key):
        return self.fields[key]

    def __len__(self):
        return len(self._fields)


class Variant(Type):
    def __init__(self):
        self.set_default_tag()
        self.set_default_types()

    def set_default_tag(self):
        self._tag = None

    def set_default_types(self):
        self._types = collections.OrderedDict()

    @property
    def align(self):
        single_type = self.get_single_type()

        if single_type is not None:
            return single_type.align

        # if all the possible types have the same alignment, then
        # there's only one possible alignment
        align = None

        for t in self.types.values():
            if t.align is None:
                return

            if align is None:
                # first
                align = t.align
            else:
                if t.align != align:
                    return

        return align

    @property
    def size(self):
        single_type = self.get_single_type()

        if single_type is not None:
            return single_type.size

    @property
    def tag(self):
        return self._tag

    @tag.setter
    def tag(self, value):
        self._tag = value

    @property
    def types(self):
        return self._types

    def __getitem__(self, key):
        return self.types[key]

    def get_single_type(self):
        if len(self.members) == 1:
            return list(self.members.values())[0]

    @property
    def is_dynamic(self):
        single_type = self.get_single_type()

        if single_type is not None:
            return single_type.is_dynamic

        return True


class Trace:
    def __init__(self):
        self._byte_order = None
        self._packet_header_type = None
        self._uuid = None

    @property
    def uuid(self):
        return self._uuid

    @uuid.setter
    def uuid(self, value):
        self._uuid = value

    @property
    def byte_order(self):
        return self._byte_order

    @byte_order.setter
    def byte_order(self, value):
        self._byte_order = value

    @property
    def packet_header_type(self):
        return self._packet_header_type

    @packet_header_type.setter
    def packet_header_type(self, value):
        self._packet_header_type = value


class Env(collections.OrderedDict):
    pass


class Clock:
    def __init__(self):
        self.set_default_name()
        self.set_default_uuid()
        self.set_default_description()
        self.set_default_freq()
        self.set_default_error_cycles()
        self.set_default_offset_seconds()
        self.set_default_offset_cycles()
        self.set_default_absolute()
        self.set_default_return_ctype()

    def set_default_name(self):
        self._name = None

    def set_default_uuid(self):
        self._uuid = None

    def set_default_description(self):
        self._description = None

    def set_default_freq(self):
        self._freq = 1000000000

    def set_default_error_cycles(self):
        self._error_cycles = 0

    def set_default_offset_seconds(self):
        self._offset_seconds = 0

    def set_default_offset_cycles(self):
        self._offset_cycles = 0

    def set_default_absolute(self):
        self._absolute = False

    def set_default_return_ctype(self):
        self._return_ctype = 'uint32_t'

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def uuid(self):
        return self._uuid

    @uuid.setter
    def uuid(self, value):
        self._uuid = value

    @property
    def description(self):
        return self._description

    @description.setter
    def description(self, value):
        self._description = value

    @property
    def error_cycles(self):
        return self._error_cycles

    @error_cycles.setter
    def error_cycles(self, value):
        self._error_cycles = value

    @property
    def freq(self):
        return self._freq

    @freq.setter
    def freq(self, value):
        self._freq = value

    @property
    def offset_seconds(self):
        return self._offset_seconds

    @offset_seconds.setter
    def offset_seconds(self, value):
        self._offset_seconds = value

    @property
    def offset_cycles(self):
        return self._offset_cycles

    @offset_cycles.setter
    def offset_cycles(self, value):
        self._offset_cycles = value

    @property
    def absolute(self):
        return self._absolute

    @absolute.setter
    def absolute(self, value):
        self._absolute = value

    @property
    def return_ctype(self):
        return self._return_ctype

    @return_ctype.setter
    def return_ctype(self, value):
        self._return_ctype = value


LogLevel = collections.namedtuple('LogLevel', ['name', 'value'])


class Event:
    def __init__(self):
        self._id = None
        self._name = None
        self._log_level = None
        self._context_type = None
        self._payload_type = None

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        self._id = value

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def log_level(self):
        return self._log_level

    @log_level.setter
    def log_level(self, value):
        self._log_level = value

    @property
    def context_type(self):
        return self._context_type

    @context_type.setter
    def context_type(self, value):
        self._context_type = value

    @property
    def payload_type(self):
        return self._payload_type

    @payload_type.setter
    def payload_type(self, value):
        self._payload_type = value

    def __getitem__(self, key):
        if type(self.payload_type) in [Struct, Variant]:
            return self.payload_type[key]

        raise TypeError('{} is not subscriptable')


class Stream:
    def __init__(self):
        self._id = 0
        self._name = None
        self._packet_context_type = None
        self._event_header_type = None
        self._event_context_type = None
        self._events = collections.OrderedDict()

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        self._id = value

    @property
    def packet_context_type(self):
        return self._packet_context_type

    @packet_context_type.setter
    def packet_context_type(self, value):
        self._packet_context_type = value

    @property
    def event_header_type(self):
        return self._event_header_type

    @event_header_type.setter
    def event_header_type(self, value):
        self._event_header_type = value

    @property
    def event_context_type(self):
        return self._event_context_type

    @event_context_type.setter
    def event_context_type(self, value):
        self._event_context_type = value

    @property
    def events(self):
        return self._events

    def is_event_empty(self, event):
        total_fields = 0

        if self.event_header_type:
            total_fields += len(self.event_header_type)

        if self.event_context_type:
            total_fields += len(self.event_context_type)

        if event.context_type:
            total_fields += len(event.context_type)

        if event.payload_type:
            total_fields += len(event.payload_type)

        return total_fields == 0


class Metadata:
    def __init__(self):
        self._trace = None
        self._env = collections.OrderedDict()
        self._clocks = collections.OrderedDict()
        self._streams = collections.OrderedDict()
        self._default_stream_name = None

    @property
    def trace(self):
        return self._trace

    @trace.setter
    def trace(self, value):
        self._trace = value

    @property
    def env(self):
        return self._env

    @env.setter
    def env(self, value):
        self._env = value

    @property
    def clocks(self):
        return self._clocks

    @clocks.setter
    def clocks(self, value):
        self._clocks = value

    @property
    def streams(self):
        return self._streams

    @streams.setter
    def streams(self, value):
        self._streams = value

    @property
    def default_stream_name(self):
        return self._default_stream_name

    @default_stream_name.setter
    def default_stream_name(self, value):
        self._default_stream_name = value

    @property
    def default_stream(self):
        if self._default_stream_name in self._streams:
            return self._streams[self._default_stream_name]
