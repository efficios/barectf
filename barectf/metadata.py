# The MIT License (MIT)
#
# Copyright (c) 2015-2020 Philippe Proulx <pproulx@efficios.com>
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
import barectf
import datetime


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
        return False


class PropertyMapping:
    def __init__(self, object, prop):
        self._object = object
        self._prop = prop

    @property
    def object(self):
        return self._object

    @property
    def prop(self):
        return self.prop


class Integer(Type):
    def __init__(self, size, byte_order, align=None, signed=False,
                 base=10, encoding=Encoding.NONE, property_mappings=None):
        self._size = size
        self._byte_order = byte_order

        if align is None:
            if size % 8 == 0:
                self._align = 8
            else:
                self._align = 1
        else:
            self._align = align

        self._signed = signed
        self._base = base
        self._encoding = encoding

        if property_mappings is None:
            self._property_mappings = []
        else:
            self._property_mappings = property_mappings

    @property
    def signed(self):
        return self._signed

    @property
    def byte_order(self):
        return self._byte_order

    @property
    def base(self):
        return self._base

    @property
    def encoding(self):
        return self._encoding

    @property
    def align(self):
        return self._align

    @property
    def size(self):
        return self._size

    @property
    def property_mappings(self):
        return self._property_mappings


class FloatingPoint(Type):
    def __init__(self, exp_size, mant_size, byte_order, align=8):
        self._exp_size = exp_size
        self._mant_size = mant_size
        self._byte_order = byte_order
        self._align = align

    @property
    def exp_size(self):
        return self._exp_size

    @property
    def mant_size(self):
        return self._mant_size

    @property
    def size(self):
        return self._exp_size + self._mant_size

    @property
    def byte_order(self):
        return self._byte_order

    @property
    def align(self):
        return self._align


class Enum(Type):
    def __init__(self, value_type, members=None):
        self._value_type = value_type

        if members is None:
            self._members = collections.OrderedDict()
        else:
            self._members = members

    @property
    def align(self):
        return self._value_type.align

    @property
    def size(self):
        return self._value_type.size

    @property
    def value_type(self):
        return self._value_type

    @property
    def members(self):
        return self._members

    @property
    def last_value(self):
        if len(self._members) == 0:
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

        raise TypeError('Wrong subscript type')


class String(Type):
    def __init__(self, encoding=Encoding.UTF8):
        self._encoding = encoding.UTF8

    @property
    def align(self):
        return 8

    @property
    def encoding(self):
        return self._encoding

    @property
    def is_dynamic(self):
        return True


class Array(Type):
    def __init__(self, element_type, length):
        self._element_type = element_type
        self._length = length

    @property
    def align(self):
        return self._element_type.align

    @property
    def element_type(self):
        return self._element_type

    @property
    def length(self):
        return self._length


class Struct(Type):
    def __init__(self, min_align=1, fields=None):
        self._min_align = min_align

        if fields is None:
            self._fields = collections.OrderedDict()
        else:
            self._fields = fields

        self._align = self.min_align

        for field in self.fields.values():
            if field.align is None:
                continue

            if field.align > self._align:
                self._align = field.align

    @property
    def min_align(self):
        return self._min_align

    @property
    def align(self):
        return self._align

    @property
    def fields(self):
        return self._fields

    def __getitem__(self, key):
        return self.fields[key]

    def __len__(self):
        return len(self._fields)


class Trace:
    def __init__(self, byte_order, uuid=None, packet_header_type=None):
        self._byte_order = byte_order
        self._uuid = uuid
        self._packet_header_type = packet_header_type

    @property
    def uuid(self):
        return self._uuid

    @property
    def byte_order(self):
        return self._byte_order

    @property
    def packet_header_type(self):
        return self._packet_header_type


class Clock:
    def __init__(self, name, uuid=None, description=None, freq=int(1e9),
                 error_cycles=0, offset_seconds=0, offset_cycles=0,
                 absolute=False, return_ctype='uint32_t'):
        self._name = name
        self._uuid = uuid
        self._description = description
        self._freq = freq
        self._error_cycles = error_cycles
        self._offset_seconds = offset_seconds
        self._offset_cycles = offset_cycles
        self._absolute = absolute
        self._return_ctype = return_ctype

    @property
    def name(self):
        return self._name

    @property
    def uuid(self):
        return self._uuid

    @property
    def description(self):
        return self._description

    @property
    def error_cycles(self):
        return self._error_cycles

    @property
    def freq(self):
        return self._freq

    @property
    def offset_seconds(self):
        return self._offset_seconds

    @property
    def offset_cycles(self):
        return self._offset_cycles

    @property
    def absolute(self):
        return self._absolute

    @property
    def return_ctype(self):
        return self._return_ctype


LogLevel = collections.namedtuple('LogLevel', ['name', 'value'])


class Event:
    def __init__(self, id, name, log_level=None, payload_type=None,
                 context_type=None):
        self._id = id
        self._name = name
        self._payload_type = payload_type
        self._log_level = log_level
        self._context_type = context_type

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
    def context_type(self):
        return self._context_type

    @property
    def payload_type(self):
        return self._payload_type

    def __getitem__(self, key):
        if self.payload_type is None:
            raise KeyError(key)

        return self.payload_type[key]


class Stream:
    def __init__(self, id, name=None, packet_context_type=None,
                 event_header_type=None, event_context_type=None,
                 events=None):
        self._id = id
        self._name = name
        self._packet_context_type = packet_context_type
        self._event_header_type = event_header_type
        self._event_context_type = event_context_type

        if events is None:
            self._events = collections.OrderedDict()
        else:
            self._events = events

    @property
    def name(self):
        return self._name

    @property
    def id(self):
        return self._id

    @property
    def packet_context_type(self):
        return self._packet_context_type

    @property
    def event_header_type(self):
        return self._event_header_type

    @property
    def event_context_type(self):
        return self._event_context_type

    @property
    def events(self):
        return self._events


class Metadata:
    def __init__(self, trace, env=None, clocks=None, streams=None,
                 default_stream_name=None):
        self._trace = trace
        version_tuple = barectf.get_version_tuple()
        self._env = collections.OrderedDict([
            ('domain', 'bare'),
            ('tracer_name', 'barectf'),
            ('tracer_major', version_tuple[0]),
            ('tracer_minor', version_tuple[1]),
            ('tracer_patch', version_tuple[2]),
            ('barectf_gen_date', str(datetime.datetime.now().isoformat())),
        ])

        if env is not None:
            self._env.update(env)

        if clocks is None:
            self._clocks = collections.OrderedDict()
        else:
            self._clocks = clocks

        if streams is None:
            self._streams = collections.OrderedDict()
        else:
            self._streams = streams

        self._default_stream_name = default_stream_name

    @property
    def trace(self):
        return self._trace

    @property
    def env(self):
        return self._env

    @property
    def clocks(self):
        return self._clocks

    @property
    def streams(self):
        return self._streams

    @property
    def default_stream_name(self):
        return self._default_stream_name

    @property
    def default_stream(self):
        if self._default_stream_name in self._streams:
            return self._streams[self._default_stream_name]
