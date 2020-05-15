# The MIT License (MIT)
#
# Copyright (c) 2015-2016 Philippe Proulx <pproulx@efficios.com>
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

from barectf import metadata
import collections
import datetime
import barectf
import enum
import yaml
import uuid
import copy
import re
import os


class _ConfigErrorCtx:
    def __init__(self, name, msg=None):
        self._name = name
        self._msg = msg

    @property
    def name(self):
        return self._name

    @property
    def msg(self):
        return self._msg


class ConfigError(RuntimeError):
    def __init__(self, init_ctx_name, init_ctx_msg=None):
        self._ctx = []
        self.append_ctx(init_ctx_name, init_ctx_msg)

    @property
    def ctx(self):
        return self._ctx

    def append_ctx(self, name, msg=None):
        self._ctx.append(_ConfigErrorCtx(name, msg))


class Config:
    def __init__(self, version, prefix, metadata, options):
        self.prefix = prefix
        self.version = version
        self.metadata = metadata
        self.options = options

    def _validate_metadata(self, meta):
        try:
            validator = _MetadataTypesHistologyValidator()
            validator.validate(meta)
            validator = _MetadataSpecialFieldsValidator()
            validator.validate(meta)
        except ConfigError as exc:
            exc.append_ctx('metadata')
            raise

        try:
            validator = _BarectfMetadataValidator()
            validator.validate(meta)
        except ConfigError as exc:
            exc.append_ctx('barectf metadata')
            raise

    def _augment_metadata_env(self, meta):
        version_tuple = barectf.get_version_tuple()
        base_env = {
            'domain': 'bare',
            'tracer_name': 'barectf',
            'tracer_major': version_tuple[0],
            'tracer_minor': version_tuple[1],
            'tracer_patch': version_tuple[2],
            'barectf_gen_date': str(datetime.datetime.now().isoformat()),
        }

        base_env.update(meta.env)
        meta.env = base_env

    @property
    def version(self):
        return self._version

    @version.setter
    def version(self, value):
        self._version = value

    @property
    def metadata(self):
        return self._metadata

    @metadata.setter
    def metadata(self, value):
        self._validate_metadata(value)
        self._augment_metadata_env(value)
        self._metadata = value

    @property
    def prefix(self):
        return self._prefix

    @prefix.setter
    def prefix(self, value):
        if not _is_valid_identifier(value):
            raise ConfigError('configuration',
                              'prefix must be a valid C identifier')

        self._prefix = value

    @property
    def options(self):
        return self._options

    @options.setter
    def options(self, options):
        self._options = options


class ConfigOptions:
    def __init__(self):
        self._gen_prefix_def = False
        self._gen_default_stream_def = False

    @property
    def gen_prefix_def(self):
        return self._gen_prefix_def

    @gen_prefix_def.setter
    def gen_prefix_def(self, value):
        self._gen_prefix_def = value

    @property
    def gen_default_stream_def(self):
        return self._gen_default_stream_def

    @gen_default_stream_def.setter
    def gen_default_stream_def(self, value):
        self._gen_default_stream_def = value


def _is_assoc_array_prop(node):
    return isinstance(node, dict)


def _is_array_prop(node):
    return isinstance(node, list)


def _is_int_prop(node):
    return type(node) is int


def _is_str_prop(node):
    return type(node) is str


def _is_bool_prop(node):
    return type(node) is bool


def _is_valid_alignment(align):
    return ((align & (align - 1)) == 0) and align > 0


def _byte_order_str_to_bo(bo_str):
    bo_str = bo_str.lower()

    if bo_str == 'le':
        return metadata.ByteOrder.LE
    elif bo_str == 'be':
        return metadata.ByteOrder.BE


def _encoding_str_to_encoding(encoding_str):
    encoding_str = encoding_str.lower()

    if encoding_str == 'utf-8' or encoding_str == 'utf8':
        return metadata.Encoding.UTF8
    elif encoding_str == 'ascii':
        return metadata.Encoding.ASCII
    elif encoding_str == 'none':
        return metadata.Encoding.NONE


_re_iden = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]*$')
_ctf_keywords = set([
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
])


def _is_valid_identifier(iden):
    if not _re_iden.match(iden):
        return False

    if _re_iden in _ctf_keywords:
        return False

    return True


def _get_first_unknown_prop(node, known_props):
    for prop_name in node:
        if prop_name in known_props:
            continue

        return prop_name


# This validator validates the configured metadata for barectf specific
# needs.
#
# barectf needs:
#
#   * all header/contexts are at least byte-aligned
#   * all integer and floating point number sizes to be <= 64
#   * no inner structures or arrays
class _BarectfMetadataValidator:
    def __init__(self):
        self._type_to_validate_type_func = {
            metadata.Integer: self._validate_int_type,
            metadata.FloatingPoint: self._validate_float_type,
            metadata.Enum: self._validate_enum_type,
            metadata.String: self._validate_string_type,
            metadata.Struct: self._validate_struct_type,
            metadata.Array: self._validate_array_type,
        }

    def _validate_int_type(self, t, entity_root):
        if t.size > 64:
            raise ConfigError('integer type', 'size must be lesser than or equal to 64 bits')

    def _validate_float_type(self, t, entity_root):
        if t.size > 64:
            raise ConfigError('floating point number type', 'size must be lesser than or equal to 64 bits')

    def _validate_enum_type(self, t, entity_root):
        if t.value_type.size > 64:
            raise ConfigError('enumeration type', 'integer type\'s size must be lesser than or equal to 64 bits')

    def _validate_string_type(self, t, entity_root):
        pass

    def _validate_struct_type(self, t, entity_root):
        if not entity_root:
            raise ConfigError('structure type', 'inner structure types are not supported as of this version')

        for field_name, field_type in t.fields.items():
            if entity_root and self._cur_entity is _Entity.TRACE_PACKET_HEADER:
                if field_name == 'uuid':
                    # allow
                    continue

            try:
                self._validate_type(field_type, False)
            except ConfigError as exc:
                exc.append_ctx('structure type\' field "{}"'.format(field_name))
                raise

    def _validate_array_type(self, t, entity_root):
        raise ConfigError('array type', 'not supported as of this version')

    def _validate_type(self, t, entity_root):
        self._type_to_validate_type_func[type(t)](t, entity_root)

    def _validate_entity(self, t):
        if t is None:
            return

        # make sure entity is byte-aligned
        if t.align < 8:
            raise ConfigError('root type', 'alignment must be at least byte-aligned')

        # make sure entity is a structure
        if type(t) is not metadata.Struct:
            raise ConfigError('root type', 'expecting a structure type')

        # validate types
        self._validate_type(t, True)

    def _validate_entities_and_names(self, meta):
        self._cur_entity = _Entity.TRACE_PACKET_HEADER

        try:
            self._validate_entity(meta.trace.packet_header_type)
        except ConfigError as exc:
            exc.append_ctx('trace', 'invalid packet header type')
            raise

        for stream_name, stream in meta.streams.items():
            if not _is_valid_identifier(stream_name):
                raise ConfigError('trace', 'stream name "{}" is not a valid C identifier'.format(stream_name))

            self._cur_entity = _Entity.STREAM_PACKET_CONTEXT

            try:
                self._validate_entity(stream.packet_context_type)
            except ConfigError as exc:
                exc.append_ctx('stream "{}"'.format(stream_name),
                               'invalid packet context type')
                raise

            self._cur_entity = _Entity.STREAM_EVENT_HEADER

            try:
                self._validate_entity(stream.event_header_type)
            except ConfigError as exc:
                exc.append_ctx('stream "{}"'.format(stream_name),
                               'invalid event header type')
                raise

            self._cur_entity = _Entity.STREAM_EVENT_CONTEXT

            try:
                self._validate_entity(stream.event_context_type)
            except ConfigError as exc:
                exc.append_ctx('stream "{}"'.format(stream_name),
                               'invalid event context type'.format(stream_name))
                raise

            try:
                for ev_name, ev in stream.events.items():
                    if not _is_valid_identifier(ev_name):
                        raise ConfigError('stream "{}"'.format(stream_name),
                                          'event name "{}" is not a valid C identifier'.format(ev_name))

                    self._cur_entity = _Entity.EVENT_CONTEXT

                    try:
                        self._validate_entity(ev.context_type)
                    except ConfigError as exc:
                        exc.append_ctx('event "{}"'.format(ev_name),
                                       'invalid context type')
                        raise

                    self._cur_entity = _Entity.EVENT_PAYLOAD

                    try:
                        self._validate_entity(ev.payload_type)
                    except ConfigError as exc:
                        exc.append_ctx('event "{}"'.format(ev_name),
                                       'invalid payload type')
                        raise

                    if stream.is_event_empty(ev):
                        raise ConfigError('event "{}"'.format(ev_name), 'empty')
            except ConfigError as exc:
                exc.append_ctx('stream "{}"'.format(stream_name))
                raise

    def _validate_default_stream(self, meta):
        if meta.default_stream_name:
            if meta.default_stream_name not in meta.streams.keys():
                raise ConfigError('barectf metadata', 'default stream name ("{}") does not exist'.format(meta.default_stream_name))

    def validate(self, meta):
        self._validate_entities_and_names(meta)
        self._validate_default_stream(meta)


# This validator validates special fields of trace, stream, and event
# types. For example, if checks that the "stream_id" field exists in the
# trace packet header if there's more than one stream, and much more.
class _MetadataSpecialFieldsValidator:
    def _validate_trace_packet_header_type(self, t):
        # needs "stream_id" field?
        if len(self._meta.streams) > 1:
            # yes
            if t is None:
                raise ConfigError('"packet-header-type" property',
                                  'need "stream_id" field (more than one stream), but trace packet header type is missing')

            if type(t) is not metadata.Struct:
                raise ConfigError('"packet-header-type" property',
                                  'need "stream_id" field (more than one stream), but trace packet header type is not a structure type')

            if 'stream_id' not in t.fields:
                raise ConfigError('"packet-header-type" property',
                                  'need "stream_id" field (more than one stream)')

        # validate "magic" and "stream_id" types
        if type(t) is not metadata.Struct:
            return

        for i, (field_name, field_type) in enumerate(t.fields.items()):
            if field_name == 'magic':
                if type(field_type) is not metadata.Integer:
                    raise ConfigError('"packet-header-type" property',
                                      '"magic" field must be an integer type')

                if field_type.signed or field_type.size != 32:
                    raise ConfigError('"packet-header-type" property',
                                      '"magic" field must be a 32-bit unsigned integer type')

                if i != 0:
                    raise ConfigError('"packet-header-type" property',
                                      '"magic" field must be the first trace packet header type\'s field')
            elif field_name == 'stream_id':
                if type(field_type) is not metadata.Integer:
                    raise ConfigError('"packet-header-type" property',
                                      '"stream_id" field must be an integer type')

                if field_type.signed:
                    raise ConfigError('"packet-header-type" property',
                                      '"stream_id" field must be an unsigned integer type')

                # "id" size can fit all event IDs
                if len(self._meta.streams) > (1 << field_type.size):
                    raise ConfigError('"packet-header-type" property',
                                      '"stream_id" field\' size is too small for the number of trace streams')
            elif field_name == 'uuid':
                if self._meta.trace.uuid is None:
                    raise ConfigError('"packet-header-type" property',
                                      '"uuid" field specified, but no trace UUID provided')

                if type(field_type) is not metadata.Array:
                    raise ConfigError('"packet-header-type" property',
                                      '"uuid" field must be an array')

                if field_type.length != 16:
                    raise ConfigError('"packet-header-type" property',
                                      '"uuid" field must be an array of 16 bytes')

                element_type = field_type.element_type

                if type(element_type) is not metadata.Integer:
                    raise ConfigError('"packet-header-type" property',
                                      '"uuid" field must be an array of 16 unsigned bytes')

                if element_type.size != 8:
                    raise ConfigError('"packet-header-type" property',
                                      '"uuid" field must be an array of 16 unsigned bytes')

                if element_type.signed:
                    raise ConfigError('"packet-header-type" property',
                                      '"uuid" field must be an array of 16 unsigned bytes')

                if element_type.align != 8:
                    raise ConfigError('"packet-header-type" property',
                                      '"uuid" field must be an array of 16 unsigned, byte-aligned bytes')

    def _validate_trace(self, meta):
        self._validate_trace_packet_header_type(meta.trace.packet_header_type)

    def _validate_stream_packet_context(self, stream):
        t = stream.packet_context_type

        if type(t) is None:
            raise ConfigError('stream',
                              'missing "packet-context-type" property')

        if type(t) is not metadata.Struct:
            raise ConfigError('"packet-context-type" property',
                              'expecting a structure type')

        # "timestamp_begin", if exists, is an unsigned integer type,
        # mapped to a clock
        ts_begin = None

        if 'timestamp_begin' in t.fields:
            ts_begin = t.fields['timestamp_begin']

            if type(ts_begin) is not metadata.Integer:
                raise ConfigError('"packet-context-type" property',
                                  '"timestamp_begin" field must be an integer type')

            if ts_begin.signed:
                raise ConfigError('"packet-context-type" property',
                                  '"timestamp_begin" field must be an unsigned integer type')

            if not ts_begin.property_mappings:
                raise ConfigError('"packet-context-type" property',
                                  '"timestamp_begin" field must be mapped to a clock')

        # "timestamp_end", if exists, is an unsigned integer type,
        # mapped to a clock
        ts_end = None

        if 'timestamp_end' in t.fields:
            ts_end = t.fields['timestamp_end']

            if type(ts_end) is not metadata.Integer:
                raise ConfigError('"packet-context-type" property',
                                  '"timestamp_end" field must be an integer type')

            if ts_end.signed:
                raise ConfigError('"packet-context-type" property',
                                  '"timestamp_end" field must be an unsigned integer type')

            if not ts_end.property_mappings:
                raise ConfigError('"packet-context-type" property',
                                  '"timestamp_end" field must be mapped to a clock')

        # "timestamp_begin" and "timestamp_end" exist together
        if (('timestamp_begin' in t.fields) ^ ('timestamp_end' in t.fields)):
            raise ConfigError('"timestamp_begin" and "timestamp_end" fields must be defined together in stream packet context type')

        # "timestamp_begin" and "timestamp_end" are mapped to the same clock
        if ts_begin is not None and ts_end is not None:
            if ts_begin.property_mappings[0].object.name != ts_end.property_mappings[0].object.name:
                raise ConfigError('"timestamp_begin" and "timestamp_end" fields must be mapped to the same clock object in stream packet context type')

        # "events_discarded", if exists, is an unsigned integer type
        if 'events_discarded' in t.fields:
            events_discarded = t.fields['events_discarded']

            if type(events_discarded) is not metadata.Integer:
                raise ConfigError('"packet-context-type" property',
                                  '"events_discarded" field must be an integer type')

            if events_discarded.signed:
                raise ConfigError('"packet-context-type" property',
                                  '"events_discarded" field must be an unsigned integer type')

        # "packet_size" and "content_size" must exist
        if 'packet_size' not in t.fields:
            raise ConfigError('"packet-context-type" property',
                              'missing "packet_size" field in stream packet context type')

        packet_size = t.fields['packet_size']

        # "content_size" and "content_size" must exist
        if 'content_size' not in t.fields:
            raise ConfigError('"packet-context-type" property',
                              'missing "content_size" field in stream packet context type')

        content_size = t.fields['content_size']

        # "packet_size" is an unsigned integer type
        if type(packet_size) is not metadata.Integer:
            raise ConfigError('"packet-context-type" property',
                              '"packet_size" field in stream packet context type must be an integer type')

        if packet_size.signed:
            raise ConfigError('"packet-context-type" property',
                              '"packet_size" field in stream packet context type must be an unsigned integer type')

        # "content_size" is an unsigned integer type
        if type(content_size) is not metadata.Integer:
            raise ConfigError('"packet-context-type" property',
                              '"content_size" field in stream packet context type must be an integer type')

        if content_size.signed:
            raise ConfigError('"packet-context-type" property',
                              '"content_size" field in stream packet context type must be an unsigned integer type')

        # "packet_size" size should be greater than or equal to "content_size" size
        if content_size.size > packet_size.size:
            raise ConfigError('"packet-context-type" property',
                              '"content_size" field size must be lesser than or equal to "packet_size" field size')

    def _validate_stream_event_header(self, stream):
        t = stream.event_header_type

        # needs "id" field?
        if len(stream.events) > 1:
            # yes
            if t is None:
                raise ConfigError('"event-header-type" property',
                                  'need "id" field (more than one event), but stream event header type is missing')

            if type(t) is not metadata.Struct:
                raise ConfigError('"event-header-type" property',
                                  'need "id" field (more than one event), but stream event header type is not a structure type')

            if 'id' not in t.fields:
                raise ConfigError('"event-header-type" property',
                                  'need "id" field (more than one event)')

        # validate "id" and "timestamp" types
        if type(t) is not metadata.Struct:
            return

        # "timestamp", if exists, is an unsigned integer type,
        # mapped to a clock
        if 'timestamp' in t.fields:
            ts = t.fields['timestamp']

            if type(ts) is not metadata.Integer:
                raise ConfigError('"event-header-type" property',
                                  '"timestamp" field must be an integer type')

            if ts.signed:
                raise ConfigError('"event-header-type" property',
                                  '"timestamp" field must be an unsigned integer type')

            if not ts.property_mappings:
                raise ConfigError('"event-header-type" property',
                                  '"timestamp" field must be mapped to a clock')

        if 'id' in t.fields:
            eid = t.fields['id']

            # "id" is an unsigned integer type
            if type(eid) is not metadata.Integer:
                raise ConfigError('"event-header-type" property',
                                  '"id" field must be an integer type')

            if eid.signed:
                raise ConfigError('"event-header-type" property',
                                  '"id" field must be an unsigned integer type')

            # "id" size can fit all event IDs
            if len(stream.events) > (1 << eid.size):
                raise ConfigError('"event-header-type" property',
                                  '"id" field\' size is too small for the number of stream events')

    def _validate_stream(self, stream):
        self._validate_stream_packet_context(stream)
        self._validate_stream_event_header(stream)

    def validate(self, meta):
        self._meta = meta
        self._validate_trace(meta)

        for stream in meta.streams.values():
            try:
                self._validate_stream(stream)
            except ConfigError as exc:
                exc.append_ctx('stream "{}"'.format(stream.name), 'invalid')
                raise


# Entities. Order of values is important here.
@enum.unique
class _Entity(enum.IntEnum):
    TRACE_PACKET_HEADER = 0
    STREAM_PACKET_CONTEXT = 1
    STREAM_EVENT_HEADER = 2
    STREAM_EVENT_CONTEXT = 3
    EVENT_CONTEXT = 4
    EVENT_PAYLOAD = 5


# Since type inheritance allows types to be only partially defined at
# any place in the configuration, this validator validates that actual
# trace, stream, and event types are all complete and valid. Therefore
# an invalid, but unusued type alias is accepted.
class _MetadataTypesHistologyValidator:
    def __init__(self):
        self._type_to_validate_type_histology_func = {
            metadata.Integer: self._validate_integer_histology,
            metadata.FloatingPoint: self._validate_float_histology,
            metadata.Enum: self._validate_enum_histology,
            metadata.String: self._validate_string_histology,
            metadata.Struct: self._validate_struct_histology,
            metadata.Array: self._validate_array_histology,
        }

    def _validate_integer_histology(self, t):
        # size is set
        if t.size is None:
            raise ConfigError('integer type', 'missing size')

    def _validate_float_histology(self, t):
        # exponent digits is set
        if t.exp_size is None:
            raise ConfigError('floating point number type',
                              'missing exponent size')

        # mantissa digits is set
        if t.mant_size is None:
            raise ConfigError('floating point number type',
                              'missing mantissa size')

        # exponent and mantissa sum is a multiple of 8
        if (t.exp_size + t.mant_size) % 8 != 0:
            raise ConfigError('floating point number type',
                              'mantissa and exponent sizes sum must be a multiple of 8')

    def _validate_enum_histology(self, t):
        # integer type is set
        if t.value_type is None:
            raise ConfigError('enumeration type', 'missing value type')

        # there's at least one member
        if not t.members:
            raise ConfigError('enumeration type', 'at least one member required')

        # no overlapping values and all values are valid considering
        # the value type
        ranges = []

        if t.value_type.signed:
            value_min = -(1 << t.value_type.size - 1)
            value_max = (1 << (t.value_type.size - 1)) - 1
        else:
            value_min = 0
            value_max = (1 << t.value_type.size) - 1

        for label, value in t.members.items():
            for rg in ranges:
                if value[0] <= rg[1] and rg[0] <= value[1]:
                    raise ConfigError('enumeration type\'s member "{}"',
                                      'overlaps another member'.format(label))

            name_fmt = 'enumeration type\'s member "{}"'
            msg_fmt = 'value {} is outside the value type range [{}, {}]'

            if value[0] < value_min or value[0] > value_max:
                raise ConfigError(name_fmt.format(label),
                                  msg_fmt.format(value[0], value_min, value_max))

            if value[1] < value_min or value[1] > value_max:
                raise ConfigError(name_fmt.format(label),
                                  msg_fmt.format(value[0], value_min, value_max))

            ranges.append(value)

    def _validate_string_histology(self, t):
        # always valid
        pass

    def _validate_struct_histology(self, t):
        # all fields are valid
        for field_name, field_type in t.fields.items():
            try:
                self._validate_type_histology(field_type)
            except ConfigError as exc:
                exc.append_ctx('structure type\'s field "{}"'.format(field_name))
                raise

    def _validate_array_histology(self, t):
        # length is set
        if t.length is None:
            raise ConfigError('array type', 'missing length')

        # element type is set
        if t.element_type is None:
            raise ConfigError('array type', 'missing element type')

        # element type is valid
        try:
            self._validate_type_histology(t.element_type)
        except ConfigError as exc:
            exc.append_ctx('array type', 'invalid element type')
            raise

    def _validate_type_histology(self, t):
        if t is None:
            return

        self._type_to_validate_type_histology_func[type(t)](t)

    def _validate_entity_type_histology(self, t):
        if t is None:
            return

        if type(t) is not metadata.Struct:
            raise ConfigError('root type', 'expecting a structure type')

        self._validate_type_histology(t)

    def _validate_event_types_histology(self, ev):
        ev_name = ev.name

        # validate event context type
        try:
            self._validate_entity_type_histology(ev.context_type)
        except ConfigError as exc:
            exc.append_ctx('event "{}"'.format(ev.name),
                           'invalid context type')
            raise

        # validate event payload type
        try:
            self._validate_entity_type_histology(ev.payload_type)
        except ConfigError as exc:
            exc.append_ctx('event "{}"'.format(ev.name),
                           'invalid payload type')
            raise

    def _validate_stream_types_histology(self, stream):
        stream_name = stream.name

        # validate stream packet context type
        try:
            self._validate_entity_type_histology(stream.packet_context_type)
        except ConfigError as exc:
            exc.append_ctx('stream "{}"'.format(stream_name),
                           'invalid packet context type')
            raise

        # validate stream event header type
        try:
            self._validate_entity_type_histology(stream.event_header_type)
        except ConfigError as exc:
            exc.append_ctx('stream "{}"'.format(stream_name),
                           'invalid event header type')
            raise

        # validate stream event context type
        try:
            self._validate_entity_type_histology(stream.event_context_type)
        except ConfigError as exc:
            exc.append_ctx('stream "{}"'.format(stream_name),
                           'invalid event context type')
            raise

        # validate events
        for ev in stream.events.values():
            try:
                self._validate_event_types_histology(ev)
            except ConfigError as exc:
                exc.append_ctx('stream "{}"'.format(stream_name),
                               'invalid event')
                raise

    def validate(self, meta):
        # validate trace packet header type
        try:
            self._validate_entity_type_histology(meta.trace.packet_header_type)
        except ConfigError as exc:
            exc.append_ctx('metadata\'s trace', 'invalid packet header type')
            raise

        # validate streams
        for stream in meta.streams.values():
            self._validate_stream_types_histology(stream)


class _YamlConfigParser:
    def __init__(self, include_dirs, ignore_include_not_found, dump_config):
        self._class_name_to_create_type_func = {
            'int': self._create_integer,
            'integer': self._create_integer,
            'flt': self._create_float,
            'float': self._create_float,
            'floating-point': self._create_float,
            'enum': self._create_enum,
            'enumeration': self._create_enum,
            'str': self._create_string,
            'string': self._create_string,
            'struct': self._create_struct,
            'structure': self._create_struct,
            'array': self._create_array,
        }
        self._type_to_create_type_func = {
            metadata.Integer: self._create_integer,
            metadata.FloatingPoint: self._create_float,
            metadata.Enum: self._create_enum,
            metadata.String: self._create_string,
            metadata.Struct: self._create_struct,
            metadata.Array: self._create_array,
        }
        self._include_dirs = include_dirs
        self._ignore_include_not_found = ignore_include_not_found
        self._dump_config = dump_config

    def _set_byte_order(self, metadata_node):
        if 'trace' not in metadata_node:
            raise ConfigError('metadata', 'missing "trace" property')

        trace_node = metadata_node['trace']

        if not _is_assoc_array_prop(trace_node):
            raise ConfigError('metadata\'s "trace" property',
                              'must be an associative array')

        if 'byte-order' not in trace_node:
            raise ConfigError('metadata\'s "trace" property',
                              'missing "byte-order" property')

        bo_node = trace_node['byte-order']

        if not _is_str_prop(bo_node):
            raise ConfigError('metadata\'s "trace" property',
                              '"byte-order" property must be a string ("le" or "be")')

        self._bo = _byte_order_str_to_bo(bo_node)

        if self._bo is None:
            raise ConfigError('metadata\'s "trace" property',
                              'invalid "byte-order" property: must be "le" or "be"')

    def _lookup_type_alias(self, name):
        if name in self._tas:
            return copy.deepcopy(self._tas[name])

    def _set_int_clock_prop_mapping(self, int_obj, prop_mapping_node):
        unk_prop = _get_first_unknown_prop(prop_mapping_node, ['type', 'name', 'property'])

        if unk_prop:
            raise ConfigError('integer type\'s clock property mapping',
                              'unknown property: "{}"'.format(unk_prop))

        if 'name' not in prop_mapping_node:
            raise ConfigError('integer type\'s clock property mapping',
                              'missing "name" property')

        if 'property' not in prop_mapping_node:
            raise ConfigError('integer type\'s clock property mapping',
                              'missing "property" property')

        clock_name = prop_mapping_node['name']
        prop = prop_mapping_node['property']

        if not _is_str_prop(clock_name):
            raise ConfigError('integer type\'s clock property mapping',
                              '"name" property must be a string')

        if not _is_str_prop(prop):
            raise ConfigError('integer type\'s clock property mapping',
                              '"property" property must be a string')

        if clock_name not in self._clocks:
            raise ConfigError('integer type\'s clock property mapping',
                              'invalid clock name "{}"'.format(clock_name))

        if prop != 'value':
            raise ConfigError('integer type\'s clock property mapping',
                              'invalid "property" property: "{}"'.format(prop))

        mapped_clock = self._clocks[clock_name]
        int_obj.property_mappings.append(metadata.PropertyMapping(mapped_clock, prop))

    def _get_first_unknown_type_prop(self, type_node, known_props):
        kp = known_props + ['inherit', 'class']

        if self._version >= 201:
            kp.append('$inherit')

        return _get_first_unknown_prop(type_node, kp)

    def _create_integer(self, obj, node):
        if obj is None:
            # create integer object
            obj = metadata.Integer()

        unk_prop = self._get_first_unknown_type_prop(node, [
            'size',
            'align',
            'signed',
            'byte-order',
            'base',
            'encoding',
            'property-mappings',
        ])

        if unk_prop:
            raise ConfigError('integer type',
                              'unknown property: "{}"'.format(unk_prop))

        # size
        if 'size' in node:
            size = node['size']

            if not _is_int_prop(size):
                raise ConfigError('integer type',
                                  '"size" property of integer type object must be an integer')

            if size < 1:
                raise ConfigError('integer type',
                                  'invalid integer size: {}'.format(size))

            obj.size = size

        # align
        if 'align' in node:
            align = node['align']

            if align is None:
                obj.set_default_align()
            else:
                if not _is_int_prop(align):
                    raise ConfigError('integer type',
                                      '"align" property of integer type object must be an integer')

                if not _is_valid_alignment(align):
                    raise ConfigError('integer type',
                                      'invalid alignment: {}'.format(align))

                obj.align = align

        # signed
        if 'signed' in node:
            signed = node['signed']

            if signed is None:
                obj.set_default_signed()
            else:
                if not _is_bool_prop(signed):
                    raise ConfigError('integer type',
                                      '"signed" property of integer type object must be a boolean')

                obj.signed = signed

        # byte order
        if 'byte-order' in node:
            byte_order = node['byte-order']

            if byte_order is None:
                obj.byte_order = self._bo
            else:
                if not _is_str_prop(byte_order):
                    raise ConfigError('integer type',
                                      '"byte-order" property of integer type object must be a string ("le" or "be")')

                byte_order = _byte_order_str_to_bo(byte_order)

                if byte_order is None:
                    raise ConfigError('integer type',
                                      'invalid "byte-order" property in integer type object')

                obj.byte_order = byte_order
        else:
            obj.byte_order = self._bo

        # base
        if 'base' in node:
            base = node['base']

            if base is None:
                obj.set_default_base()
            else:
                if not _is_str_prop(base):
                    raise ConfigError('integer type',
                                      '"base" property of integer type object must be a string ("bin", "oct", "dec", or "hex")')

                if base == 'bin':
                    base = 2
                elif base == 'oct':
                    base = 8
                elif base == 'dec':
                    base = 10
                elif base == 'hex':
                    base = 16
                else:
                    raise ConfigError('integer type',
                                      'unknown "base" property value: "{}" ("bin", "oct", "dec", and "hex" are accepted)'.format(base))

                obj.base = base

        # encoding
        if 'encoding' in node:
            encoding = node['encoding']

            if encoding is None:
                obj.set_default_encoding()
            else:
                if not _is_str_prop(encoding):
                    raise ConfigError('integer type',
                                      '"encoding" property of integer type object must be a string ("none", "ascii", or "utf-8")')

                encoding = _encoding_str_to_encoding(encoding)

                if encoding is None:
                    raise ConfigError('integer type',
                                      'invalid "encoding" property in integer type object')

                obj.encoding = encoding

        # property mappings
        if 'property-mappings' in node:
            prop_mappings = node['property-mappings']

            if prop_mappings is None:
                obj.set_default_property_mappings()
            else:
                if not _is_array_prop(prop_mappings):
                    raise ConfigError('integer type',
                                      '"property-mappings" property of integer type object must be an array')

                if len(prop_mappings) > 1:
                    raise ConfigError('integer type',
                                      'length of "property-mappings" array in integer type object must be 1')

                for index, prop_mapping in enumerate(prop_mappings):
                    if not _is_assoc_array_prop(prop_mapping):
                        raise ConfigError('integer type',
                                          'elements of "property-mappings" property of integer type object must be associative arrays')

                    if 'type' not in prop_mapping:
                        raise ConfigError('integer type',
                                          'missing "type" property in integer type object\'s "property-mappings" array\'s element #{}'.format(index))

                    prop_type = prop_mapping['type']

                    if not _is_str_prop(prop_type):
                        raise ConfigError('integer type',
                                          '"type" property of integer type object\'s "property-mappings" array\'s element #{} must be a string'.format(index))

                    if prop_type == 'clock':
                        self._set_int_clock_prop_mapping(obj, prop_mapping)
                    else:
                        raise ConfigError('integer type',
                                          'unknown property mapping type "{}" in integer type object\'s "property-mappings" array\'s element #{}'.format(prop_type, index))

        return obj

    def _create_float(self, obj, node):
        if obj is None:
            # create floating point number object
            obj = metadata.FloatingPoint()

        unk_prop = self._get_first_unknown_type_prop(node, [
            'size',
            'align',
            'byte-order',
        ])

        if unk_prop:
            raise ConfigError('floating point number type',
                              'unknown property: "{}"'.format(unk_prop))

        # size
        if 'size' in node:
            size = node['size']

            if not _is_assoc_array_prop(size):
                raise ConfigError('floating point number type',
                                  '"size" property must be an associative array')

            unk_prop = _get_first_unknown_prop(size, ['exp', 'mant'])

            if unk_prop:
                raise ConfigError('floating point number type\'s "size" property',
                                  'unknown property: "{}"'.format(unk_prop))

            if 'exp' in size:
                exp = size['exp']

                if not _is_int_prop(exp):
                    raise ConfigError('floating point number type\'s "size" property',
                                      '"exp" property must be an integer')

                if exp < 1:
                    raise ConfigError('floating point number type\'s "size" property',
                                      'invalid exponent size: {}')

                obj.exp_size = exp

            if 'mant' in size:
                mant = size['mant']

                if not _is_int_prop(mant):
                    raise ConfigError('floating point number type\'s "size" property',
                                      '"mant" property must be an integer')

                if mant < 1:
                    raise ConfigError('floating point number type\'s "size" property',
                                      'invalid mantissa size: {}')

                obj.mant_size = mant

        # align
        if 'align' in node:
            align = node['align']

            if align is None:
                obj.set_default_align()
            else:
                if not _is_int_prop(align):
                    raise ConfigError('floating point number type',
                                      '"align" property must be an integer')

                if not _is_valid_alignment(align):
                    raise ConfigError('floating point number type',
                                      'invalid alignment: {}'.format(align))

                obj.align = align

        # byte order
        if 'byte-order' in node:
            byte_order = node['byte-order']

            if byte_order is None:
                obj.byte_order = self._bo
            else:
                if not _is_str_prop(byte_order):
                    raise ConfigError('floating point number type',
                                      '"byte-order" property must be a string ("le" or "be")')

                byte_order = _byte_order_str_to_bo(byte_order)

                if byte_order is None:
                    raise ConfigError('floating point number type',
                                      'invalid "byte-order" property')
        else:
            obj.byte_order = self._bo

        return obj

    def _create_enum(self, obj, node):
        if obj is None:
            # create enumeration object
            obj = metadata.Enum()

        unk_prop = self._get_first_unknown_type_prop(node, [
            'value-type',
            'members',
        ])

        if unk_prop:
            raise ConfigError('enumeration type',
                              'unknown property: "{}"'.format(unk_prop))

        # value type
        if 'value-type' in node:
            value_type_node = node['value-type']

            try:
                obj.value_type = self._create_type(value_type_node)
            except ConfigError as exc:
                exc.append_ctx('enumeration type', 'cannot create integer type')
                raise

        # members
        if 'members' in node:
            members_node = node['members']

            if not _is_array_prop(members_node):
                raise ConfigError('enumeration type',
                                  '"members" property must be an array')

            cur = 0
            last_value = obj.last_value

            if last_value is None:
                cur = 0
            else:
                cur = last_value + 1

            for index, m_node in enumerate(members_node):
                if not _is_str_prop(m_node) and not _is_assoc_array_prop(m_node):
                    raise ConfigError('enumeration type',
                                      'invalid member #{}: expecting a string or an associative array'.format(index))

                if _is_str_prop(m_node):
                    label = m_node
                    value = (cur, cur)
                    cur += 1
                else:
                    unk_prop = _get_first_unknown_prop(m_node, [
                        'label',
                        'value',
                    ])

                    if unk_prop:
                        raise ConfigError('enumeration type',
                                          'unknown member object property: "{}"'.format(unk_prop))

                    if 'label' not in m_node:
                        raise ConfigError('enumeration type',
                                          'missing "label" property in member #{}'.format(index))

                    label = m_node['label']

                    if not _is_str_prop(label):
                        raise ConfigError('enumeration type',
                                          '"label" property of member #{} must be a string'.format(index))

                    if 'value' not in m_node:
                        raise ConfigError('enumeration type',
                                          'missing "value" property in member ("{}")'.format(label))

                    value = m_node['value']

                    if not _is_int_prop(value) and not _is_array_prop(value):
                        raise ConfigError('enumeration type',
                                          'invalid member ("{}"): expecting an integer or an array'.format(label))

                    if _is_int_prop(value):
                        cur = value + 1
                        value = (value, value)
                    else:
                        if len(value) != 2:
                            raise ConfigError('enumeration type',
                                              'invalid member ("{}"): range must have exactly two items'.format(label))

                        mn = value[0]
                        mx = value[1]

                        if mn > mx:
                            raise ConfigError('enumeration type',
                                              'invalid member ("{}"): invalid range ({} > {})'.format(label, mn, mx))

                        value = (mn, mx)
                        cur = mx + 1

                obj.members[label] = value

        return obj

    def _create_string(self, obj, node):
        if obj is None:
            # create string object
            obj = metadata.String()

        unk_prop = self._get_first_unknown_type_prop(node, [
            'encoding',
        ])

        if unk_prop:
            raise ConfigError('string type',
                              'unknown object property: "{}"'.format(unk_prop))

        # encoding
        if 'encoding' in node:
            encoding = node['encoding']

            if encoding is None:
                obj.set_default_encoding()
            else:
                if not _is_str_prop(encoding):
                    raise ConfigError('string type',
                                      '"encoding" property of must be a string ("none", "ascii", or "utf-8")')

                encoding = _encoding_str_to_encoding(encoding)

                if encoding is None:
                    raise ConfigError('string type',
                                      'invalid "encoding" property')

                obj.encoding = encoding

        return obj

    def _create_struct(self, obj, node):
        if obj is None:
            # create structure object
            obj = metadata.Struct()

        unk_prop = self._get_first_unknown_type_prop(node, [
            'min-align',
            'fields',
        ])

        if unk_prop:
            raise ConfigError('structure type',
                              'unknown object property: "{}"'.format(unk_prop))

        # minimum alignment
        if 'min-align' in node:
            min_align = node['min-align']

            if min_align is None:
                obj.set_default_min_align()
            else:
                if not _is_int_prop(min_align):
                    raise ConfigError('structure type',
                                      '"min-align" property must be an integer')

                if not _is_valid_alignment(min_align):
                    raise ConfigError('structure type',
                                      'invalid minimum alignment: {}'.format(min_align))

                obj.min_align = min_align

        # fields
        if 'fields' in node:
            fields = node['fields']

            if fields is None:
                obj.set_default_fields()
            else:
                if not _is_assoc_array_prop(fields):
                    raise ConfigError('structure type',
                                      '"fields" property must be an associative array')

                for field_name, field_node in fields.items():
                    if not _is_valid_identifier(field_name):
                        raise ConfigError('structure type',
                                          '"{}" is not a valid field name'.format(field_name))

                    try:
                        obj.fields[field_name] = self._create_type(field_node)
                    except ConfigError as exc:
                        exc.append_ctx('structure type',
                                       'cannot create field "{}"'.format(field_name))
                        raise

        return obj

    def _create_array(self, obj, node):
        if obj is None:
            # create array object
            obj = metadata.Array()

        unk_prop = self._get_first_unknown_type_prop(node, [
            'length',
            'element-type',
        ])

        if unk_prop:
            raise ConfigError('array type',
                              'unknown property: "{}"'.format(unk_prop))

        # length
        if 'length' in node:
            length = node['length']

            if not _is_int_prop(length):
                raise ConfigError('array type',
                                  '"length" property must be an integer')

            if type(length) is int and length < 0:
                raise ConfigError('array type',
                                  'invalid length: {}'.format(length))

            obj.length = length

        # element type
        if 'element-type' in node:
            element_type_node = node['element-type']

            try:
                obj.element_type = self._create_type(node['element-type'])
            except ConfigError as exc:
                exc.append_ctx('array type', 'cannot create element type')
                raise

        return obj

    def _create_type(self, type_node):
        if type(type_node) is str:
            t = self._lookup_type_alias(type_node)

            if t is None:
                raise ConfigError('type',
                                  'unknown type alias "{}"'.format(type_node))

            return t

        if not _is_assoc_array_prop(type_node):
            raise ConfigError('type',
                              'expecting associative arrays or string (type alias name)')

        # inherit:
        #   v2.0:  "inherit"
        #   v2.1+: "$inherit"
        inherit_node = None

        if self._version >= 200:
            if 'inherit' in type_node:
                inherit_prop = 'inherit'
                inherit_node = type_node[inherit_prop]

        if self._version >= 201:
            if '$inherit' in type_node:
                if inherit_node is not None:
                    raise ConfigError('type',
                                      'cannot specify both "inherit" and "$inherit" properties of type object: prefer "$inherit"')

                inherit_prop = '$inherit'
                inherit_node = type_node[inherit_prop]

        if inherit_node is not None and 'class' in type_node:
            raise ConfigError('type',
                              'cannot specify both "{}" and "class" properties in type object'.format(inherit_prop))

        if inherit_node is not None:
            if not _is_str_prop(inherit_node):
                raise ConfigError('type',
                                  '"{}" property of type object must be a string'.format(inherit_prop))

            base = self._lookup_type_alias(inherit_node)

            if base is None:
                raise ConfigError('type',
                                  'cannot inherit from type alias "{}": type alias does not exist at this point'.format(inherit_node))

            func = self._type_to_create_type_func[type(base)]
        else:
            if 'class' not in type_node:
                raise ConfigError('type',
                                  'does not inherit, therefore must have a "class" property')

            class_name = type_node['class']

            if type(class_name) is not str:
                raise ConfigError('type', '"class" property must be a string')

            if class_name not in self._class_name_to_create_type_func:
                raise ConfigError('type',
                                  'unknown class "{}"'.format(class_name))

            base = None
            func = self._class_name_to_create_type_func[class_name]

        return func(base, type_node)

    def _register_type_aliases(self, metadata_node):
        self._tas = dict()

        if 'type-aliases' not in metadata_node:
            return

        ta_node = metadata_node['type-aliases']

        if ta_node is None:
            return

        if not _is_assoc_array_prop(ta_node):
            raise ConfigError('metadata',
                              '"type-aliases" property must be an associative array')

        for ta_name, ta_type in ta_node.items():
            if ta_name in self._tas:
                raise ConfigError('metadata',
                                  'duplicate type alias "{}"'.format(ta_name))

            try:
                t = self._create_type(ta_type)
            except ConfigError as exc:
                exc.append_ctx('metadata',
                               'cannot create type alias "{}"'.format(ta_name))
                raise

            self._tas[ta_name] = t

    def _create_clock(self, node):
        # create clock object
        clock = metadata.Clock()

        if not _is_assoc_array_prop(node):
            raise ConfigError('metadata',
                              'clock objects must be associative arrays')

        known_props = [
            'uuid',
            'description',
            'freq',
            'error-cycles',
            'offset',
            'absolute',
            'return-ctype',
        ]

        if self._version >= 201:
            known_props.append('$return-ctype')

        unk_prop = _get_first_unknown_prop(node, known_props)

        if unk_prop:
            raise ConfigError('clock',
                              'unknown property: "{}"'.format(unk_prop))

        # UUID
        if 'uuid' in node:
            uuidp = node['uuid']

            if uuidp is None:
                clock.set_default_uuid()
            else:
                if not _is_str_prop(uuidp):
                    raise ConfigError('clock',
                                      '"uuid" property must be a string')

                try:
                    uuidp = uuid.UUID(uuidp)
                except:
                    raise ConfigError('clock', 'malformed UUID: "{}"'.format(uuidp))

                clock.uuid = uuidp

        # description
        if 'description' in node:
            desc = node['description']

            if desc is None:
                clock.set_default_description()
            else:
                if not _is_str_prop(desc):
                    raise ConfigError('clock',
                                      '"description" property must be a string')

                clock.description = desc

        # frequency
        if 'freq' in node:
            freq = node['freq']

            if freq is None:
                clock.set_default_freq()
            else:
                if not _is_int_prop(freq):
                    raise ConfigError('clock',
                                      '"freq" property must be an integer')

                if freq < 1:
                    raise ConfigError('clock',
                                      'invalid frequency: {}'.format(freq))

                clock.freq = freq

        # error cycles
        if 'error-cycles' in node:
            error_cycles = node['error-cycles']

            if error_cycles is None:
                clock.set_default_error_cycles()
            else:
                if not _is_int_prop(error_cycles):
                    raise ConfigError('clock',
                                      '"error-cycles" property must be an integer')

                if error_cycles < 0:
                    raise ConfigError('clock',
                                      'invalid error cycles: {}'.format(error_cycles))

                clock.error_cycles = error_cycles

        # offset
        if 'offset' in node:
            offset = node['offset']

            if offset is None:
                clock.set_default_offset_seconds()
                clock.set_default_offset_cycles()
            else:
                if not _is_assoc_array_prop(offset):
                    raise ConfigError('clock',
                                      '"offset" property must be an associative array')

                unk_prop = _get_first_unknown_prop(offset, ['cycles', 'seconds'])

                if unk_prop:
                    raise ConfigError('clock',
                                      'unknown offset property: "{}"'.format(unk_prop))

                # cycles
                if 'cycles' in offset:
                    offset_cycles = offset['cycles']

                    if offset_cycles is None:
                        clock.set_default_offset_cycles()
                    else:
                        if not _is_int_prop(offset_cycles):
                            raise ConfigError('clock\'s "offset" property',
                                              '"cycles" property must be an integer')

                        if offset_cycles < 0:
                            raise ConfigError('clock\'s "offset" property',
                                              'invalid cycles: {}'.format(offset_cycles))

                        clock.offset_cycles = offset_cycles

                # seconds
                if 'seconds' in offset:
                    offset_seconds = offset['seconds']

                    if offset_seconds is None:
                        clock.set_default_offset_seconds()
                    else:
                        if not _is_int_prop(offset_seconds):
                            raise ConfigError('clock\'s "offset" property',
                                              '"seconds" property must be an integer')

                        if offset_seconds < 0:
                            raise ConfigError('clock\'s "offset" property',
                                              'invalid seconds: {}'.format(offset_seconds))

                        clock.offset_seconds = offset_seconds

        # absolute
        if 'absolute' in node:
            absolute = node['absolute']

            if absolute is None:
                clock.set_default_absolute()
            else:
                if not _is_bool_prop(absolute):
                    raise ConfigError('clock',
                                      '"absolute" property must be a boolean')

                clock.absolute = absolute

        # return C type:
        #   v2.0:  "return-ctype"
        #   v2.1+: "$return-ctype"
        return_ctype_node = None

        if self._version >= 200:
            if 'return-ctype' in node:
                return_ctype_prop = 'return-ctype'
                return_ctype_node = node[return_ctype_prop]

        if self._version >= 201:
            if '$return-ctype' in node:
                if return_ctype_node is not None:
                    raise ConfigError('clock',
                                      'cannot specify both "return-ctype" and "$return-ctype" properties: prefer "$return-ctype"')

                return_ctype_prop = '$return-ctype'
                return_ctype_node = node[return_ctype_prop]

        if return_ctype_node is not None:
            if return_ctype_node is None:
                clock.set_default_return_ctype()
            else:
                if not _is_str_prop(return_ctype_node):
                    raise ConfigError('clock',
                                      '"{}" property of must be a string'.format(return_ctype_prop))

                clock.return_ctype = return_ctype_node

        return clock

    def _register_clocks(self, metadata_node):
        self._clocks = collections.OrderedDict()

        if 'clocks' not in metadata_node:
            return

        clocks_node = metadata_node['clocks']

        if clocks_node is None:
            return

        if not _is_assoc_array_prop(clocks_node):
            raise ConfigError('metadata',
                              '"clocks" property must be an associative array')

        for clock_name, clock_node in clocks_node.items():
            if not _is_valid_identifier(clock_name):
                raise ConfigError('metadata',
                                  'invalid clock name: "{}"'.format(clock_name))

            if clock_name in self._clocks:
                raise ConfigError('metadata',
                                  'duplicate clock "{}"'.format(clock_name))

            try:
                clock = self._create_clock(clock_node)
            except ConfigError as exc:
                exc.append_ctx('metadata',
                               'cannot create clock "{}"'.format(clock_name))
                raise

            clock.name = clock_name
            self._clocks[clock_name] = clock

    def _create_env(self, metadata_node):
        env = collections.OrderedDict()

        if 'env' not in metadata_node:
            return env

        env_node = metadata_node['env']

        if env_node is None:
            return env

        if not _is_assoc_array_prop(env_node):
            raise ConfigError('metadata',
                              '"env" property must be an associative array')

        for env_name, env_value in env_node.items():
            if env_name in env:
                raise ConfigError('metadata',
                                  'duplicate environment variable "{}"'.format(env_name))

            if not _is_valid_identifier(env_name):
                raise ConfigError('metadata',
                                  'invalid environment variable name: "{}"'.format(env_name))

            if not _is_int_prop(env_value) and not _is_str_prop(env_value):
                raise ConfigError('metadata',
                                  'invalid environment variable value ("{}"): expecting integer or string'.format(env_name))

            env[env_name] = env_value

        return env

    def _register_log_levels(self, metadata_node):
        self._log_levels = dict()

        # log levels:
        #   v2.0:  "log-levels"
        #   v2.1+: "$log-levels"
        log_levels_node = None

        if self._version >= 200:
            if 'log-levels' in metadata_node:
                log_levels_prop = 'log-levels'
                log_levels_node = metadata_node[log_levels_prop]

        if self._version >= 201:
            if '$log-levels' in metadata_node:
                if log_levels_node is not None:
                    raise ConfigError('metadata',
                                      'cannot specify both "log-levels" and "$log-levels" properties of metadata object: prefer "$log-levels"')

                log_levels_prop = '$log-levels'
                log_levels_node = metadata_node[log_levels_prop]

        if log_levels_node is None:
            return

        if not _is_assoc_array_prop(log_levels_node):
            raise ConfigError('metadata',
                              '"{}" property (metadata) must be an associative array'.format(log_levels_prop))

        for ll_name, ll_value in log_levels_node.items():
            if ll_name in self._log_levels:
                raise ConfigError('"{}" property"'.format(log_levels_prop),
                                  'duplicate entry "{}"'.format(ll_name))

            if not _is_int_prop(ll_value):
                raise ConfigError('"{}" property"'.format(log_levels_prop),
                                  'invalid entry ("{}"): expecting an integer'.format(ll_name))

            if ll_value < 0:
                raise ConfigError('"{}" property"'.format(log_levels_prop),
                                  'invalid entry ("{}"): value must be positive'.format(ll_name))

            self._log_levels[ll_name] = ll_value

    def _create_trace(self, metadata_node):
        # create trace object
        trace = metadata.Trace()

        if 'trace' not in metadata_node:
            raise ConfigError('metadata', 'missing "trace" property')

        trace_node = metadata_node['trace']

        if not _is_assoc_array_prop(trace_node):
            raise ConfigError('metadata',
                              '"trace" property must be an associative array')

        unk_prop = _get_first_unknown_prop(trace_node, [
            'byte-order',
            'uuid',
            'packet-header-type',
        ])

        if unk_prop:
            raise ConfigError('trace',
                              'unknown property: "{}"'.format(unk_prop))

        # set byte order (already parsed)
        trace.byte_order = self._bo

        # UUID
        if 'uuid' in trace_node and trace_node['uuid'] is not None:
            uuidp = trace_node['uuid']

            if not _is_str_prop(uuidp):
                raise ConfigError('trace',
                                  '"uuid" property must be a string')

            if uuidp == 'auto':
                uuidp = uuid.uuid1()
            else:
                try:
                    uuidp = uuid.UUID(uuidp)
                except:
                    raise ConfigError('trace',
                                      'malformed UUID: "{}"'.format(uuidp))

            trace.uuid = uuidp

        # packet header type
        if 'packet-header-type' in trace_node and trace_node['packet-header-type'] is not None:
            try:
                ph_type = self._create_type(trace_node['packet-header-type'])
            except ConfigError as exc:
                exc.append_ctx('trace',
                               'cannot create packet header type')
                raise

            trace.packet_header_type = ph_type

        return trace

    def _lookup_log_level(self, ll):
        if _is_int_prop(ll):
            return ll
        elif _is_str_prop(ll) and ll in self._log_levels:
            return self._log_levels[ll]

    def _create_event(self, event_node):
        event = metadata.Event()

        if not _is_assoc_array_prop(event_node):
            raise ConfigError('event',
                              'expecting associative array')

        unk_prop = _get_first_unknown_prop(event_node, [
            'log-level',
            'context-type',
            'payload-type',
        ])

        if unk_prop:
            raise ConfigError('event',
                              'unknown property: "{}"'.format(unk_prop))

        if 'log-level' in event_node and event_node['log-level'] is not None:
            ll_node = event_node['log-level']

            if _is_str_prop(ll_node):
                ll_value = self._lookup_log_level(event_node['log-level'])

                if ll_value is None:
                    raise ConfigError('event\'s "log-level" property',
                                      'cannot find log level "{}"'.format(ll_node))

                ll = metadata.LogLevel(event_node['log-level'], ll_value)
            elif _is_int_prop(ll_node):
                if ll_node < 0:
                    raise ConfigError('event\'s "log-level" property',
                                      'invalid value {}: value must be positive'.format(ll_node))

                ll = metadata.LogLevel(None, ll_node)
            else:
                raise ConfigError('event\'s "log-level" property',
                                  'must be either a string or an integer')

            event.log_level = ll

        if 'context-type' in event_node and event_node['context-type'] is not None:
            ctx_type_node = event_node['context-type']

            try:
                t = self._create_type(event_node['context-type'])
            except ConfigError as exc:
                exc.append_ctx('event',
                               'cannot create context type object')
                raise

            event.context_type = t

        if 'payload-type' in event_node and event_node['payload-type'] is not None:
            try:
                t = self._create_type(event_node['payload-type'])
            except ConfigError as exc:
                exc.append_ctx('event',
                               'cannot create payload type object')
                raise

            event.payload_type = t

        return event

    def _create_stream(self, stream_name, stream_node):
        stream = metadata.Stream()

        if not _is_assoc_array_prop(stream_node):
            raise ConfigError('stream objects must be associative arrays')

        known_props = [
            'packet-context-type',
            'event-header-type',
            'event-context-type',
            'events',
        ]

        if self._version >= 202:
            known_props.append('$default')

        unk_prop = _get_first_unknown_prop(stream_node, known_props)

        if unk_prop:
            add = ''

            if unk_prop == '$default':
                add = ' (use version 2.2 or greater)'

            raise ConfigError('stream',
                              'unknown property{}: "{}"'.format(add, unk_prop))

        if 'packet-context-type' in stream_node and stream_node['packet-context-type'] is not None:
            try:
                t = self._create_type(stream_node['packet-context-type'])
            except ConfigError as exc:
                exc.append_ctx('stream',
                               'cannot create packet context type object')
                raise

            stream.packet_context_type = t

        if 'event-header-type' in stream_node and stream_node['event-header-type'] is not None:
            try:
                t = self._create_type(stream_node['event-header-type'])
            except ConfigError as exc:
                exc.append_ctx('stream',
                               'cannot create event header type object')
                raise

            stream.event_header_type = t

        if 'event-context-type' in stream_node and stream_node['event-context-type'] is not None:
            try:
                t = self._create_type(stream_node['event-context-type'])
            except ConfigError as exc:
                exc.append_ctx('stream',
                               'cannot create event context type object')
                raise

            stream.event_context_type = t

        if 'events' not in stream_node:
            raise ConfigError('stream',
                              'missing "events" property')

        events = stream_node['events']

        if events is not None:
            if not _is_assoc_array_prop(events):
                raise ConfigError('stream',
                                  '"events" property must be an associative array')

            if not events:
                raise ConfigError('stream', 'at least one event is needed')

            cur_id = 0

            for ev_name, ev_node in events.items():
                try:
                    ev = self._create_event(ev_node)
                except ConfigError as exc:
                    exc.append_ctx('stream',
                                   'cannot create event "{}"'.format(ev_name))
                    raise

                ev.id = cur_id
                ev.name = ev_name
                stream.events[ev_name] = ev
                cur_id += 1

        if '$default' in stream_node and stream_node['$default'] is not None:
            default_node = stream_node['$default']

            if not _is_bool_prop(default_node):
                raise ConfigError('stream',
                                  'invalid "$default" property: expecting a boolean')

            if default_node:
                if self._meta.default_stream_name is not None and self._meta.default_stream_name != stream_name:
                    fmt = 'cannot specify more than one default stream (default stream already set to "{}")'
                    raise ConfigError('stream',
                                      fmt.format(self._meta.default_stream_name))

                self._meta.default_stream_name = stream_name

        return stream

    def _create_streams(self, metadata_node):
        streams = collections.OrderedDict()

        if 'streams' not in metadata_node:
            raise ConfigError('metadata',
                              'missing "streams" property')

        streams_node = metadata_node['streams']

        if not _is_assoc_array_prop(streams_node):
            raise ConfigError('metadata',
                              '"streams" property must be an associative array')

        if not streams_node:
            raise ConfigError('metadata\'s "streams" property',
                              'at least one stream is needed')

        cur_id = 0

        for stream_name, stream_node in streams_node.items():
            try:
                stream = self._create_stream(stream_name, stream_node)
            except ConfigError as exc:
                exc.append_ctx('metadata',
                               'cannot create stream "{}"'.format(stream_name))
                raise

            stream.id = cur_id
            stream.name = str(stream_name)
            streams[stream_name] = stream
            cur_id += 1

        return streams

    def _create_metadata(self, root):
        self._meta = metadata.Metadata()

        if 'metadata' not in root:
            raise ConfigError('configuration',
                              'missing "metadata" property')

        metadata_node = root['metadata']

        if not _is_assoc_array_prop(metadata_node):
            raise ConfigError('configuration\'s "metadata" property',
                              'must be an associative array')

        known_props = [
            'type-aliases',
            'log-levels',
            'trace',
            'env',
            'clocks',
            'streams',
        ]

        if self._version >= 201:
            known_props.append('$log-levels')

        if self._version >= 202:
            known_props.append('$default-stream')

        unk_prop = _get_first_unknown_prop(metadata_node, known_props)

        if unk_prop:
            add = ''

            if unk_prop == '$include':
                add = ' (use version 2.1 or greater)'

            if unk_prop == '$default-stream':
                add = ' (use version 2.2 or greater)'

            raise ConfigError('metadata',
                              'unknown property{}: "{}"'.format(add, unk_prop))

        if '$default-stream' in metadata_node and metadata_node['$default-stream'] is not None:
            default_stream_node = metadata_node['$default-stream']

            if not _is_str_prop(default_stream_node):
                raise ConfigError('metadata\'s "$default-stream" property',
                                  'expecting a string')

            self._meta.default_stream_name = default_stream_node

        self._set_byte_order(metadata_node)
        self._register_clocks(metadata_node)
        self._meta.clocks = self._clocks
        self._register_type_aliases(metadata_node)
        self._meta.env = self._create_env(metadata_node)
        self._meta.trace = self._create_trace(metadata_node)
        self._register_log_levels(metadata_node)
        self._meta.streams = self._create_streams(metadata_node)

        return self._meta

    def _get_version(self, root):
        if 'version' not in root:
            raise ConfigError('configuration',
                              'missing "version" property')

        version_node = root['version']

        if not _is_str_prop(version_node):
            raise ConfigError('configuration\'s "version" property',
                              'must be a string')

        version_node = version_node.strip()

        if version_node not in ['2.0', '2.1', '2.2']:
            raise ConfigError('configuration',
                              'unsupported version ({}): versions 2.0, 2.1, and 2.2 are supported'.format(version_node))

        # convert version string to comparable version integer
        parts = version_node.split('.')
        version = int(parts[0]) * 100 + int(parts[1])

        return version

    def _get_prefix(self, root):
        def_prefix = 'barectf_'

        if 'prefix' not in root:
            return def_prefix

        prefix_node = root['prefix']

        if prefix_node is None:
            return def_prefix

        if not _is_str_prop(prefix_node):
            raise ConfigError('configuration\'s "prefix" property',
                              'must be a string')

        if not _is_valid_identifier(prefix_node):
            raise ConfigError('configuration\'s "prefix" property',
                              'must be a valid C identifier')

        return prefix_node

    def _get_options(self, root):
        cfg_options = ConfigOptions()

        if 'options' not in root:
            return cfg_options

        options_node = root['options']

        if not _is_assoc_array_prop(options_node):
            raise ConfigError('configuration\'s "options" property',
                              'must be an associative array')

        known_props = [
            'gen-prefix-def',
            'gen-default-stream-def',
        ]
        unk_prop = _get_first_unknown_prop(options_node, known_props)

        if unk_prop:
            raise ConfigError('configuration\'s "options" property',
                              'unknown property: "{}"'.format(unk_prop))

        if 'gen-prefix-def' in options_node and options_node['gen-prefix-def'] is not None:
            gen_prefix_def_node = options_node['gen-prefix-def']

            if not _is_bool_prop(gen_prefix_def_node):
                raise ConfigError('configuration\'s "options" property',
                                  'invalid option "gen-prefix-def": expecting a boolean')

            cfg_options.gen_prefix_def = gen_prefix_def_node

        if 'gen-default-stream-def' in options_node and options_node['gen-default-stream-def'] is not None:
            gen_default_stream_def_node = options_node['gen-default-stream-def']

            if not _is_bool_prop(gen_default_stream_def_node):
                raise ConfigError('configuration\'s "options" property',
                                  'invalid option "gen-default-stream-def": expecting a boolean')

            cfg_options.gen_default_stream_def = gen_default_stream_def_node

        return cfg_options

    def _get_last_include_file(self):
        if self._include_stack:
            return self._include_stack[-1]

        return self._root_yaml_path

    def _load_include(self, yaml_path):
        for inc_dir in self._include_dirs:
            # current include dir + file name path
            # note: os.path.join() only takes the last arg if it's absolute
            inc_path = os.path.join(inc_dir, yaml_path)

            # real path (symbolic links resolved)
            real_path = os.path.realpath(inc_path)

            # normalized path (weird stuff removed!)
            norm_path = os.path.normpath(real_path)

            if not os.path.isfile(norm_path):
                # file does not exist: skip
                continue

            if norm_path in self._include_stack:
                base_path = self._get_last_include_file()
                raise ConfigError('in "{}"',
                                  'cannot recursively include file "{}"'.format(base_path, norm_path))

            self._include_stack.append(norm_path)

            # load raw content
            return self._yaml_ordered_load(norm_path)

        if not self._ignore_include_not_found:
            base_path = self._get_last_include_file()
            raise ConfigError('in "{}"',
                              'cannot include file "{}": file not found in include directories'.format(base_path, yaml_path))

        return None

    def _get_include_paths(self, include_node):
        if include_node is None:
            return []

        if _is_str_prop(include_node):
            return [include_node]

        if _is_array_prop(include_node):
            for include_path in include_node:
                if not _is_str_prop(include_path):
                    raise ConfigError('"$include" property',
                                      'expecting array of strings')

            return include_node

        raise ConfigError('"$include" property',
                          'expecting string or array of strings')

    def _update_node(self, base_node, overlay_node):
        for olay_key, olay_value in overlay_node.items():
            if olay_key in base_node:
                base_value = base_node[olay_key]

                if _is_assoc_array_prop(olay_value) and _is_assoc_array_prop(base_value):
                    # merge dictionaries
                    self._update_node(base_value, olay_value)
                elif _is_array_prop(olay_value) and _is_array_prop(base_value):
                    # append extension array items to base items
                    base_value += olay_value
                else:
                    # fall back to replacing
                    base_node[olay_key] = olay_value
            else:
                base_node[olay_key] = olay_value

    def _process_node_include(self, last_overlay_node, name,
                              process_base_include_cb,
                              process_children_include_cb=None):
        if not _is_assoc_array_prop(last_overlay_node):
            raise ConfigError('"$include" property',
                              '{} objects must be associative arrays'.format(name))

        # process children inclusions first
        if process_children_include_cb:
            process_children_include_cb(last_overlay_node)

        if '$include' in last_overlay_node:
            include_node = last_overlay_node['$include']
        else:
            # no includes!
            return last_overlay_node

        include_paths = self._get_include_paths(include_node)
        cur_base_path = self._get_last_include_file()
        base_node = None

        # keep the include paths and remove the include property
        include_paths = copy.deepcopy(include_paths)
        del last_overlay_node['$include']

        for include_path in include_paths:
            # load raw YAML from included file
            overlay_node = self._load_include(include_path)

            if overlay_node is None:
                # cannot find include file, but we're ignoring those
                # errors, otherwise _load_include() itself raises
                # a config error
                continue

            # recursively process includes
            try:
                overlay_node = process_base_include_cb(overlay_node)
            except ConfigError as exc:
                exc.append_ctx('in "{}"'.format(cur_base_path))
                raise

            # pop include stack now that we're done including
            del self._include_stack[-1]

            # at this point, base_node is fully resolved (does not
            # contain any include property)
            if base_node is None:
                base_node = overlay_node
            else:
                self._update_node(base_node, overlay_node)

        # finally, we update the latest base node with our last overlay
        # node
        if base_node is None:
            # nothing was included, which is possible when we're
            # ignoring include errors
            return last_overlay_node

        self._update_node(base_node, last_overlay_node)

        return base_node

    def _process_event_include(self, event_node):
        return self._process_node_include(event_node, 'event',
                                          self._process_event_include)

    def _process_stream_include(self, stream_node):
        def process_children_include(stream_node):
            if 'events' in stream_node:
                events_node = stream_node['events']

                if not _is_assoc_array_prop(events_node):
                    raise ConfigError('"$include" property',
                                      '"events" property must be an associative array')

                events_node_keys = list(events_node.keys())

                for key in events_node_keys:
                    event_node = events_node[key]

                    try:
                        events_node[key] = self._process_event_include(event_node)
                    except ConfigError as exc:
                        exc.append_ctx('"$include" property',
                                       'cannot process includes of event object "{}"'.format(key))
                        raise

        return self._process_node_include(stream_node, 'stream',
                                          self._process_stream_include,
                                          process_children_include)

    def _process_trace_include(self, trace_node):
        return self._process_node_include(trace_node, 'trace',
                                          self._process_trace_include)

    def _process_clock_include(self, clock_node):
        return self._process_node_include(clock_node, 'clock',
                                          self._process_clock_include)

    def _process_metadata_include(self, metadata_node):
        def process_children_include(metadata_node):
            if 'trace' in metadata_node:
                metadata_node['trace'] = self._process_trace_include(metadata_node['trace'])

            if 'clocks' in metadata_node:
                clocks_node = metadata_node['clocks']

                if not _is_assoc_array_prop(clocks_node):
                    raise ConfigError('"$include" property',
                                      '"clocks" property must be an associative array')

                clocks_node_keys = list(clocks_node.keys())

                for key in clocks_node_keys:
                    clock_node = clocks_node[key]

                    try:
                        clocks_node[key] = self._process_clock_include(clock_node)
                    except ConfigError as exc:
                        exc.append_ctx('"$include" property',
                                       'cannot process includes of clock object "{}"'.format(key))
                        raise

            if 'streams' in metadata_node:
                streams_node = metadata_node['streams']

                if not _is_assoc_array_prop(streams_node):
                    raise ConfigError('"$include" property',
                                      '"streams" property must be an associative array')

                streams_node_keys = list(streams_node.keys())

                for key in streams_node_keys:
                    stream_node = streams_node[key]

                    try:
                        streams_node[key] = self._process_stream_include(stream_node)
                    except ConfigError as exc:
                        exc.append_ctx('"$include" property',
                                       'cannot process includes of stream object "{}"'.format(key))
                        raise

        return self._process_node_include(metadata_node, 'metadata',
                                          self._process_metadata_include,
                                          process_children_include)

    def _process_root_includes(self, root):
        # The following config objects support includes:
        #
        #   * Metadata object
        #   * Trace object
        #   * Stream object
        #   * Event object
        #
        # We need to process the event includes first, then the stream
        # includes, then the trace includes, and finally the metadata
        # includes.
        #
        # In each object, only one of the $include and $include-replace
        # special properties is allowed.
        #
        # We keep a stack of absolute paths to included files to detect
        # recursion.
        if 'metadata' in root:
            root['metadata'] = self._process_metadata_include(root['metadata'])

        return root

    def _yaml_ordered_dump(self, node, **kwds):
        class ODumper(yaml.Dumper):
            pass

        def dict_representer(dumper, node):
            return dumper.represent_mapping(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                                            node.items())

        ODumper.add_representer(collections.OrderedDict, dict_representer)

        return yaml.dump(node, Dumper=ODumper, **kwds)

    def _yaml_ordered_load(self, yaml_path):
        class OLoader(yaml.Loader):
            pass

        def construct_mapping(loader, node):
            loader.flatten_mapping(node)

            return collections.OrderedDict(loader.construct_pairs(node))

        OLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                                construct_mapping)

        # YAML -> Python
        try:
            with open(yaml_path, 'r') as f:
                node = yaml.load(f, OLoader)
        except (OSError, IOError) as e:
            raise ConfigError('configuration',
                              'cannot open file "{}"'.format(yaml_path))
        except ConfigError as exc:
            exc.append_ctx('configuration',
                           'unknown error while trying to load file "{}"'.format(yaml_path))
            raise

        # loaded node must be an associate array
        if not _is_assoc_array_prop(node):
            raise ConfigError('configuration',
                              'root of YAML file "{}" must be an associative array'.format(yaml_path))

        return node

    def _reset(self):
        self._version = None
        self._include_stack = []

    def parse(self, yaml_path):
        self._reset()
        self._root_yaml_path = yaml_path

        try:
            root = self._yaml_ordered_load(yaml_path)
        except ConfigError as exc:
            exc.append_ctx('configuration',
                           'cannot parse YAML file "{}"'.format(yaml_path))
            raise

        if not _is_assoc_array_prop(root):
            raise ConfigError('configuration',
                              'must be an associative array')

        # get the config version
        self._version = self._get_version(root)

        known_props = [
            'version',
            'prefix',
            'metadata',
        ]

        if self._version >= 202:
            known_props.append('options')

        unk_prop = _get_first_unknown_prop(root, known_props)

        if unk_prop:
            add = ''

            if unk_prop == 'options':
                add = ' (use version 2.2 or greater)'

            raise ConfigError('configuration',
                              'unknown property{}: "{}"'.format(add, unk_prop))

        # process includes if supported
        if self._version >= 201:
            root = self._process_root_includes(root)

        # dump config if required
        if self._dump_config:
            print(self._yaml_ordered_dump(root, indent=2,
                                          default_flow_style=False))

        # get prefix and metadata
        prefix = self._get_prefix(root)
        meta = self._create_metadata(root)
        opts = self._get_options(root)

        return Config(self._version, prefix, meta, opts)


def from_yaml_file(path, include_dirs, ignore_include_not_found, dump_config):
    try:
        parser = _YamlConfigParser(include_dirs, ignore_include_not_found,
                                   dump_config)
        cfg = parser.parse(path)

        return cfg
    except ConfigError as exc:
        exc.append_ctx('configuration',
                       'cannot create configuration from YAML file "{}"'.format(path))
        raise
