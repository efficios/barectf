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
        raise NotImplementedError()

    @property
    def size(self):
        raise NotImplementedError()

    @size.setter
    def size(self, value):
        self._size = value


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
        self._size = None
        self._align = None
        self._signed = False
        self._byte_order = None
        self._base = 10
        self._encoding = Encoding.NONE
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
                return None
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


class FloatingPoint(Type):
    def __init__(self):
        self._exp_size = None
        self._mant_size = None
        self._align = 8
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


class Enum(Type):
    def __init__(self):
        self._value_type = None
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


class String(Type):
    def __init__(self):
        self._encoding = Encoding.UTF8

    @property
    def size(self):
        return None

    @property
    def align(self):
        return 8

    @property
    def encoding(self):
        return self._encoding

    @encoding.setter
    def encoding(self, value):
        self._encoding = value


class Array(Type):
    def __init__(self):
        self._element_type = None
        self._length = None

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
    def is_static(self):
        return type(self._length) is int

    @property
    def size(self):
        if self.length == 0:
            return 0

        element_sz = self.element_type.size

        if element_sz is None:
            return None

        # TODO: compute static size here
        return None


class Struct(Type):
    def __init__(self):
        self._min_align = 1
        self._fields = collections.OrderedDict()

    @property
    def min_align(self):
        return self._min_align

    @min_align.setter
    def min_align(self, value):
        self._min_align = value

    @property
    def align(self):
        fields_max = max([f.align for f in self.fields.values()] + [1])

        return max(fields_max, self._min_align)

    @property
    def size(self):
        # TODO: compute static size here (if available)
        return None

    @property
    def fields(self):
        return self._fields

    def __getitem__(self, key):
        return self.fields[key]


class Variant(Type):
    def __init__(self):
        self._tag = None
        self._types = collections.OrderedDict()

    @property
    def align(self):
        return 1

    @property
    def size(self):
        if len(self.members) == 1:
            return list(self.members.values())[0].size

        return None

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
        self._name = None
        self._uuid = None
        self._description = None
        self._freq = 1000000000
        self._error_cycles = 0
        self._offset_seconds = 0
        self._offset_cycles = 0
        self._absolute = False
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


class Metadata:
    def __init__(self):
        self._trace = None
        self._env = collections.OrderedDict()
        self._clocks = collections.OrderedDict()
        self._streams = collections.OrderedDict()

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
