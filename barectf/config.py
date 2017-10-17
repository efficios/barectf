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


class ConfigError(RuntimeError):
    def __init__(self, msg, prev=None):
        super().__init__(msg)
        self._prev = prev

    @property
    def prev(self):
        return self._prev


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
            validator = _MetadataDynamicTypesValidator()
            validator.validate(meta)
            validator = _MetadataSpecialFieldsValidator()
            validator.validate(meta)
        except Exception as e:
            raise ConfigError('metadata error', e)

        try:
            validator = _BarectfMetadataValidator()
            validator.validate(meta)
        except Exception as e:
            raise ConfigError('barectf metadata error', e)

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
            raise ConfigError('configuration prefix must be a valid C identifier')

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
#   * no inner structures, arrays, or variants
class _BarectfMetadataValidator:
    def __init__(self):
        self._type_to_validate_type_func = {
            metadata.Integer: self._validate_int_type,
            metadata.FloatingPoint: self._validate_float_type,
            metadata.Enum: self._validate_enum_type,
            metadata.String: self._validate_string_type,
            metadata.Struct: self._validate_struct_type,
            metadata.Array: self._validate_array_type,
            metadata.Variant: self._validate_variant_type,
        }

    def _validate_int_type(self, t, entity_root):
        if t.size > 64:
            raise ConfigError('integer type\'s size must be lesser than or equal to 64 bits')

    def _validate_float_type(self, t, entity_root):
        if t.size > 64:
            raise ConfigError('floating point number type\'s size must be lesser than or equal to 64 bits')

    def _validate_enum_type(self, t, entity_root):
        if t.value_type.size > 64:
            raise ConfigError('enumeration type\'s integer type\'s size must be lesser than or equal to 64 bits')

    def _validate_string_type(self, t, entity_root):
        pass

    def _validate_struct_type(self, t, entity_root):
        if not entity_root:
            raise ConfigError('inner structure types are not supported as of this version')

        for field_name, field_type in t.fields.items():
            if entity_root and self._cur_entity is _Entity.TRACE_PACKET_HEADER:
                if field_name == 'uuid':
                    # allow
                    continue

            try:
                self._validate_type(field_type, False)
            except Exception as e:
                raise ConfigError('in structure type\'s field "{}"'.format(field_name), e)

    def _validate_array_type(self, t, entity_root):
        raise ConfigError('array types are not supported as of this version')

    def _validate_variant_type(self, t, entity_root):
        raise ConfigError('variant types are not supported as of this version')

    def _validate_type(self, t, entity_root):
        self._type_to_validate_type_func[type(t)](t, entity_root)

    def _validate_entity(self, t):
        if t is None:
            return

        # make sure entity is byte-aligned
        if t.align < 8:
            raise ConfigError('type\'s alignment must be at least byte-aligned')

        # make sure entity is a structure
        if type(t) is not metadata.Struct:
            raise ConfigError('expecting a structure type')

        # validate types
        self._validate_type(t, True)

    def _validate_entities_and_names(self, meta):
        self._cur_entity = _Entity.TRACE_PACKET_HEADER

        try:
            self._validate_entity(meta.trace.packet_header_type)
        except Exception as e:
            raise ConfigError('invalid trace packet header type', e)

        for stream_name, stream in meta.streams.items():
            if not _is_valid_identifier(stream_name):
                raise ConfigError('stream name "{}" is not a valid C identifier'.format(stream_name))

            self._cur_entity = _Entity.STREAM_PACKET_CONTEXT

            try:
                self._validate_entity(stream.packet_context_type)
            except Exception as e:
                raise ConfigError('invalid packet context type in stream "{}"'.format(stream_name), e)

            self._cur_entity = _Entity.STREAM_EVENT_HEADER

            try:
                self._validate_entity(stream.event_header_type)
            except Exception as e:
                raise ConfigError('invalid event header type in stream "{}"'.format(stream_name), e)

            self._cur_entity = _Entity.STREAM_EVENT_CONTEXT

            try:
                self._validate_entity(stream.event_context_type)
            except Exception as e:
                raise ConfigError('invalid event context type in stream "{}"'.format(stream_name), e)

            try:
                for ev_name, ev in stream.events.items():
                    if not _is_valid_identifier(ev_name):
                        raise ConfigError('event name "{}" is not a valid C identifier'.format(ev_name))

                    self._cur_entity = _Entity.EVENT_CONTEXT

                    try:
                        self._validate_entity(ev.context_type)
                    except Exception as e:
                        raise ConfigError('invalid context type in event "{}"'.format(ev_name), e)

                    self._cur_entity = _Entity.EVENT_PAYLOAD

                    try:
                        self._validate_entity(ev.payload_type)
                    except Exception as e:
                        raise ConfigError('invalid payload type in event "{}"'.format(ev_name), e)

                    if stream.is_event_empty(ev):
                        raise ConfigError('event "{}" is empty'.format(ev_name))
            except Exception as e:
                raise ConfigError('invalid stream "{}"'.format(stream_name), e)

    def _validate_default_stream(self, meta):
        if meta.default_stream_name:
            if meta.default_stream_name not in meta.streams.keys():
                raise ConfigError('default stream name ("{}") does not exist'.format(meta.default_stream_name))

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
                raise ConfigError('need "stream_id" field in trace packet header type (more than one stream), but trace packet header type is missing')

            if type(t) is not metadata.Struct:
                raise ConfigError('need "stream_id" field in trace packet header type (more than one stream), but trace packet header type is not a structure type')

            if 'stream_id' not in t.fields:
                raise ConfigError('need "stream_id" field in trace packet header type (more than one stream)')

        # validate "magic" and "stream_id" types
        if type(t) is not metadata.Struct:
            return

        for i, (field_name, field_type) in enumerate(t.fields.items()):
            if field_name == 'magic':
                if type(field_type) is not metadata.Integer:
                    raise ConfigError('"magic" field in trace packet header type must be an integer type')

                if field_type.signed or field_type.size != 32:
                    raise ConfigError('"magic" field in trace packet header type must be a 32-bit unsigned integer type')

                if i != 0:
                    raise ConfigError('"magic" field must be the first trace packet header type\'s field')
            elif field_name == 'stream_id':
                if type(field_type) is not metadata.Integer:
                    raise ConfigError('"stream_id" field in trace packet header type must be an integer type')

                if field_type.signed:
                    raise ConfigError('"stream_id" field in trace packet header type must be an unsigned integer type')

                # "id" size can fit all event IDs
                if len(self._meta.streams) > (1 << field_type.size):
                    raise ConfigError('"stream_id" field\' size in trace packet header type is too small for the number of trace streams')
            elif field_name == 'uuid':
                if self._meta.trace.uuid is None:
                    raise ConfigError('"uuid" field in trace packet header type specified, but no trace UUID provided')

                if type(field_type) is not metadata.Array:
                    raise ConfigError('"uuid" field in trace packet header type must be an array')

                if field_type.length != 16:
                    raise ConfigError('"uuid" field in trace packet header type must be an array of 16 bytes')

                element_type = field_type.element_type

                if type(element_type) is not metadata.Integer:
                    raise ConfigError('"uuid" field in trace packet header type must be an array of 16 unsigned bytes')

                if element_type.size != 8:
                    raise ConfigError('"uuid" field in trace packet header type must be an array of 16 unsigned bytes')

                if element_type.signed:
                    raise ConfigError('"uuid" field in trace packet header type must be an array of 16 unsigned bytes')

                if element_type.align != 8:
                    raise ConfigError('"uuid" field in trace packet header type must be an array of 16 unsigned, byte-aligned bytes')

    def _validate_trace(self, meta):
        self._validate_trace_packet_header_type(meta.trace.packet_header_type)

    def _validate_stream_packet_context(self, stream):
        t = stream.packet_context_type

        if type(t) is None:
            raise ConfigError('missing "packet-context-type" property in stream object')

        if type(t) is not metadata.Struct:
            raise ConfigError('"packet-context-type": expecting a structure type')

        # "timestamp_begin", if exists, is an unsigned integer type,
        # mapped to a clock
        ts_begin = None

        if 'timestamp_begin' in t.fields:
            ts_begin = t.fields['timestamp_begin']

            if type(ts_begin) is not metadata.Integer:
                raise ConfigError('"timestamp_begin" field in stream packet context type must be an integer type')

            if ts_begin.signed:
                raise ConfigError('"timestamp_begin" field in stream packet context type must be an unsigned integer type')

            if not ts_begin.property_mappings:
                raise ConfigError('"timestamp_begin" field in stream packet context type must be mapped to a clock')

        # "timestamp_end", if exists, is an unsigned integer type,
        # mapped to a clock
        ts_end = None

        if 'timestamp_end' in t.fields:
            ts_end = t.fields['timestamp_end']

            if type(ts_end) is not metadata.Integer:
                raise ConfigError('"timestamp_end" field in stream packet context type must be an integer type')

            if ts_end.signed:
                raise ConfigError('"timestamp_end" field in stream packet context type must be an unsigned integer type')

            if not ts_end.property_mappings:
                raise ConfigError('"timestamp_end" field in stream packet context type must be mapped to a clock')

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
                raise ConfigError('"events_discarded" field in stream packet context type must be an integer type')

            if events_discarded.signed:
                raise ConfigError('"events_discarded" field in stream packet context type must be an unsigned integer type')

        # "packet_size" and "content_size" must exist
        if 'packet_size' not in t.fields:
            raise ConfigError('missing "packet_size" field in stream packet context type')

        packet_size = t.fields['packet_size']

        # "content_size" and "content_size" must exist
        if 'content_size' not in t.fields:
            raise ConfigError('missing "content_size" field in stream packet context type')

        content_size = t.fields['content_size']

        # "packet_size" is an unsigned integer type
        if type(packet_size) is not metadata.Integer:
            raise ConfigError('"packet_size" field in stream packet context type must be an integer type')

        if packet_size.signed:
            raise ConfigError('"packet_size" field in stream packet context type must be an unsigned integer type')

        # "content_size" is an unsigned integer type
        if type(content_size) is not metadata.Integer:
            raise ConfigError('"content_size" field in stream packet context type must be an integer type')

        if content_size.signed:
            raise ConfigError('"content_size" field in stream packet context type must be an unsigned integer type')

        # "packet_size" size should be greater than or equal to "content_size" size
        if content_size.size > packet_size.size:
            raise ConfigError('"content_size" field size must be lesser than or equal to "packet_size" field size')

    def _validate_stream_event_header(self, stream):
        t = stream.event_header_type

        # needs "id" field?
        if len(stream.events) > 1:
            # yes
            if t is None:
                raise ConfigError('need "id" field in stream event header type (more than one event), but stream event header type is missing')

            if type(t) is not metadata.Struct:
                raise ConfigError('need "id" field in stream event header type (more than one event), but stream event header type is not a structure type')

            if 'id' not in t.fields:
                raise ConfigError('need "id" field in stream event header type (more than one event)')

        # validate "id" and "timestamp" types
        if type(t) is not metadata.Struct:
            return

        # "timestamp", if exists, is an unsigned integer type,
        # mapped to a clock
        if 'timestamp' in t.fields:
            ts = t.fields['timestamp']

            if type(ts) is not metadata.Integer:
                raise ConfigError('"timestamp" field in stream event header type must be an integer type')

            if ts.signed:
                raise ConfigError('"timestamp" field in stream event header type must be an unsigned integer type')

            if not ts.property_mappings:
                raise ConfigError('"timestamp" field in stream event header type must be mapped to a clock')

        if 'id' in t.fields:
            eid = t.fields['id']

            # "id" is an unsigned integer type
            if type(eid) is not metadata.Integer:
                raise ConfigError('"id" field in stream event header type must be an integer type')

            if eid.signed:
                raise ConfigError('"id" field in stream event header type must be an unsigned integer type')

            # "id" size can fit all event IDs
            if len(stream.events) > (1 << eid.size):
                raise ConfigError('"id" field\' size in stream event header type is too small for the number of stream events')

    def _validate_stream(self, stream):
        self._validate_stream_packet_context(stream)
        self._validate_stream_event_header(stream)

    def validate(self, meta):
        self._meta = meta
        self._validate_trace(meta)

        for stream in meta.streams.values():
            try:
                self._validate_stream(stream)
            except Exception as e:
                raise ConfigError('invalid stream "{}"'.format(stream.name), e)


class _MetadataDynamicTypesValidatorStackEntry:
    def __init__(self, base_t):
        self._base_t = base_t
        self._index = 0

    @property
    def index(self):
        return self._index

    @index.setter
    def index(self, value):
        self._index = value

    @property
    def base_t(self):
        return self._base_t

    @base_t.setter
    def base_t(self, value):
        self._base_t = value


# Entities. Order of values is important here.
@enum.unique
class _Entity(enum.IntEnum):
    TRACE_PACKET_HEADER = 0
    STREAM_PACKET_CONTEXT = 1
    STREAM_EVENT_HEADER = 2
    STREAM_EVENT_CONTEXT = 3
    EVENT_CONTEXT = 4
    EVENT_PAYLOAD = 5


# This validator validates dynamic metadata types, that is, it ensures
# variable-length array lengths and variant tags actually point to
# something that exists. It also checks that variable-length array
# lengths point to integer types and variant tags to enumeration types.
class _MetadataDynamicTypesValidator:
    def __init__(self):
        self._type_to_visit_type_func = {
            metadata.Integer: None,
            metadata.FloatingPoint: None,
            metadata.Enum: None,
            metadata.String: None,
            metadata.Struct: self._visit_struct_type,
            metadata.Array: self._visit_array_type,
            metadata.Variant: self._visit_variant_type,
        }

        self._cur_trace = None
        self._cur_stream = None
        self._cur_event = None

    def _lookup_path_from_base(self, path, parts, base, start_index,
                               base_is_current, from_t):
        index = start_index
        cur_t = base
        found_path = []

        while index < len(parts):
            part = parts[index]
            next_t = None

            if type(cur_t) is metadata.Struct:
                enumerated_items = enumerate(cur_t.fields.items())

                # lookup each field
                for i, (field_name, field_type) in enumerated_items:
                    if field_name == part:
                        next_t = field_type
                        found_path.append((i, field_type))

                if next_t is None:
                    raise ConfigError('invalid path "{}": cannot find field "{}" in structure type'.format(path, part))
            elif type(cur_t) is metadata.Variant:
                enumerated_items = enumerate(cur_t.types.items())

                # lookup each type
                for i, (type_name, type_type) in enumerated_items:
                    if type_name == part:
                        next_t = type_type
                        found_path.append((i, type_type))

                if next_t is None:
                    raise ConfigError('invalid path "{}": cannot find type "{}" in variant type'.format(path, part))
            else:
                raise ConfigError('invalid path "{}": requesting "{}" in a non-variant, non-structure type'.format(path, part))

            cur_t = next_t
            index += 1

        # make sure that the pointed type is not the pointing type
        if from_t is cur_t:
            raise ConfigError('invalid path "{}": pointing to self'.format(path))

        # if we're here, we found the type; however, it could be located
        # _after_ the variant/VLA looking for it, if the pointing
        # and pointed types are in the same entity, so compare the
        # current stack entries indexes to our index path in that case
        if not base_is_current:
            return cur_t

        for index, entry in enumerate(self._stack):
            if index == len(found_path):
                # end of index path; valid so far
                break

            if found_path[index][0] > entry.index:
                raise ConfigError('invalid path "{}": pointed type is after pointing type'.format(path))

        # also make sure that both pointed and pointing types share
        # a common structure ancestor
        for index, entry in enumerate(self._stack):
            if index == len(found_path):
                break

            if entry.base_t is not found_path[index][1]:
                # found common ancestor
                if type(entry.base_t) is metadata.Variant:
                    raise ConfigError('invalid path "{}": type cannot be reached because pointed and pointing types are in the same variant type'.format(path))

        return cur_t

    def _lookup_path_from_top(self, path, parts):
        if len(parts) != 1:
            raise ConfigError('invalid path "{}": multipart relative path not supported'.format(path))

        find_name = parts[0]
        index = len(self._stack) - 1
        got_struct = False

        # check stack entries in reversed order
        for entry in reversed(self._stack):
            # structure base type
            if type(entry.base_t) is metadata.Struct:
                got_struct = True
                enumerated_items = enumerate(entry.base_t.fields.items())

                # lookup each field, until the current visiting index is met
                for i, (field_name, field_type) in enumerated_items:
                    if i == entry.index:
                        break

                    if field_name == find_name:
                        return field_type

            # variant base type
            elif type(entry.base_t) is metadata.Variant:
                enumerated_items = enumerate(entry.base_t.types.items())

                # lookup each type, until the current visiting index is met
                for i, (type_name, type_type) in enumerated_items:
                    if i == entry.index:
                        break

                    if type_name == find_name:
                        if not got_struct:
                            raise ConfigError('invalid path "{}": type cannot be reached because pointed and pointing types are in the same variant type'.format(path))

                        return type_type

        # nothing returned here: cannot find type
        raise ConfigError('invalid path "{}": cannot find type in current context'.format(path))

    def _lookup_path(self, path, from_t):
        parts = path.lower().split('.')
        base = None
        base_is_current = False

        if len(parts) >= 3:
            if parts[0] == 'trace':
                if parts[1] == 'packet' and parts[2] == 'header':
                    # make sure packet header exists
                    if self._cur_trace.packet_header_type is None:
                        raise ConfigError('invalid path "{}": no defined trace packet header type'.format(path))

                    base = self._cur_trace.packet_header_type

                    if self._cur_entity == _Entity.TRACE_PACKET_HEADER:
                        base_is_current = True
                else:
                    raise ConfigError('invalid path "{}": unknown names after "trace"'.format(path))
            elif parts[0] == 'stream':
                if parts[1] == 'packet' and parts[2] == 'context':
                    if self._cur_entity < _Entity.STREAM_PACKET_CONTEXT:
                        raise ConfigError('invalid path "{}": cannot access stream packet context here'.format(path))

                    if self._cur_stream.packet_context_type is None:
                        raise ConfigError('invalid path "{}": no defined stream packet context type'.format(path))

                    base = self._cur_stream.packet_context_type

                    if self._cur_entity == _Entity.STREAM_PACKET_CONTEXT:
                        base_is_current = True
                elif parts[1] == 'event':
                    if parts[2] == 'header':
                        if self._cur_entity < _Entity.STREAM_EVENT_HEADER:
                            raise ConfigError('invalid path "{}": cannot access stream event header here'.format(path))

                        if self._cur_stream.event_header_type is None:
                            raise ConfigError('invalid path "{}": no defined stream event header type'.format(path))

                        base = self._cur_stream.event_header_type

                        if self._cur_entity == _Entity.STREAM_EVENT_HEADER:
                            base_is_current = True
                    elif parts[2] == 'context':
                        if self._cur_entity < _Entity.STREAM_EVENT_CONTEXT:
                            raise ConfigError('invalid path "{}": cannot access stream event context here'.format(path))

                        if self._cur_stream.event_context_type is None:
                            raise ConfigError('invalid path "{}": no defined stream event context type'.format(path))

                        base = self._cur_stream.event_context_type

                        if self._cur_entity == _Entity.STREAM_EVENT_CONTEXT:
                            base_is_current = True
                    else:
                        raise ConfigError('invalid path "{}": unknown names after "stream.event"'.format(path))
                else:
                    raise ConfigError('invalid path "{}": unknown names after "stream"'.format(path))

            if base is not None:
                start_index = 3

        if len(parts) >= 2 and base is None:
            if parts[0] == 'event':
                if parts[1] == 'context':
                    if self._cur_entity < _Entity.EVENT_CONTEXT:
                        raise ConfigError('invalid path "{}": cannot access event context here'.format(path))

                    if self._cur_event.context_type is None:
                        raise ConfigError('invalid path "{}": no defined event context type'.format(path))

                    base = self._cur_event.context_type

                    if self._cur_entity == _Entity.EVENT_CONTEXT:
                        base_is_current = True
                elif parts[1] == 'payload' or parts[1] == 'fields':
                    if self._cur_entity < _Entity.EVENT_PAYLOAD:
                        raise ConfigError('invalid path "{}": cannot access event payload here'.format(path))

                    if self._cur_event.payload_type is None:
                        raise ConfigError('invalid path "{}": no defined event payload type'.format(path))

                    base = self._cur_event.payload_type

                    if self._cur_entity == _Entity.EVENT_PAYLOAD:
                        base_is_current = True
                else:
                    raise ConfigError('invalid path "{}": unknown names after "event"'.format(path))

            if base is not None:
                start_index = 2

        if base is not None:
            return self._lookup_path_from_base(path, parts, base, start_index,
                                               base_is_current, from_t)
        else:
            return self._lookup_path_from_top(path, parts)

    def _stack_reset(self):
        self._stack = []

    def _stack_push(self, base_t):
        entry = _MetadataDynamicTypesValidatorStackEntry(base_t)
        self._stack.append(entry)

    def _stack_pop(self):
        self._stack.pop()

    def _stack_incr_index(self):
        self._stack[-1].index += 1

    def _visit_struct_type(self, t):
        self._stack_push(t)

        for field_name, field_type in t.fields.items():
            try:
                self._visit_type(field_type)
            except Exception as e:
                raise ConfigError('in structure type\'s field "{}"'.format(field_name), e)

            self._stack_incr_index()

        self._stack_pop()

    def _visit_array_type(self, t):
        if t.is_variable_length:
            # find length type
            try:
                length_type = self._lookup_path(t.length, t)
            except Exception as e:
                raise ConfigError('invalid array type\'s length', e)

            # make sure length type an unsigned integer
            if type(length_type) is not metadata.Integer:
                raise ConfigError('array type\'s length does not point to an integer type')

            if length_type.signed:
                raise ConfigError('array type\'s length does not point to an unsigned integer type')

        self._visit_type(t.element_type)

    def _visit_variant_type(self, t):
        # find tag type
        try:
            tag_type = self._lookup_path(t.tag, t)
        except Exception as e:
            raise ConfigError('invalid variant type\'s tag', e)

        # make sure tag type is an enumeration
        if type(tag_type) is not metadata.Enum:
            raise ConfigError('variant type\'s tag does not point to an enumeration type')

        # verify that each variant type's type exists as an enumeration member
        for tag_name in t.types.keys():
            if tag_name not in tag_type.members:
                raise ConfigError('cannot find variant type\'s type "{}" in pointed tag type'.format(tag_name))

        self._stack_push(t)

        for type_name, type_type in t.types.items():
            try:
                self._visit_type(type_type)
            except Exception as e:
                raise ConfigError('in variant type\'s type "{}"'.format(type_name), e)

            self._stack_incr_index()

        self._stack_pop()

    def _visit_type(self, t):
        if t is None:
            return

        if type(t) in self._type_to_visit_type_func:
            func = self._type_to_visit_type_func[type(t)]

            if func is not None:
                func(t)

    def _visit_event(self, ev):
        ev_name = ev.name

        # set current event
        self._cur_event = ev

        # visit event context type
        self._stack_reset()
        self._cur_entity = _Entity.EVENT_CONTEXT

        try:
            self._visit_type(ev.context_type)
        except Exception as e:
            raise ConfigError('invalid context type in event "{}"'.format(ev_name), e)

        # visit event payload type
        self._stack_reset()
        self._cur_entity = _Entity.EVENT_PAYLOAD

        try:
            self._visit_type(ev.payload_type)
        except Exception as e:
            raise ConfigError('invalid payload type in event "{}"'.format(ev_name), e)

    def _visit_stream(self, stream):
        stream_name = stream.name

        # set current stream
        self._cur_stream = stream

        # reset current event
        self._cur_event = None

        # visit stream packet context type
        self._stack_reset()
        self._cur_entity = _Entity.STREAM_PACKET_CONTEXT

        try:
            self._visit_type(stream.packet_context_type)
        except Exception as e:
            raise ConfigError('invalid packet context type in stream "{}"'.format(stream_name), e)

        # visit stream event header type
        self._stack_reset()
        self._cur_entity = _Entity.STREAM_EVENT_HEADER

        try:
            self._visit_type(stream.event_header_type)
        except Exception as e:
            raise ConfigError('invalid event header type in stream "{}"'.format(stream_name), e)

        # visit stream event context type
        self._stack_reset()
        self._cur_entity = _Entity.STREAM_EVENT_CONTEXT

        try:
            self._visit_type(stream.event_context_type)
        except Exception as e:
            raise ConfigError('invalid event context type in stream "{}"'.format(stream_name), e)

        # visit events
        for ev in stream.events.values():
            try:
                self._visit_event(ev)
            except Exception as e:
                raise ConfigError('invalid stream "{}"'.format(stream_name))

    def validate(self, meta):
        # set current trace
        self._cur_trace = meta.trace

        # visit trace packet header type
        self._stack_reset()
        self._cur_entity = _Entity.TRACE_PACKET_HEADER

        try:
            self._visit_type(meta.trace.packet_header_type)
        except Exception as e:
            raise ConfigError('invalid packet header type in trace', e)

        # visit streams
        for stream in meta.streams.values():
            self._visit_stream(stream)


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
            metadata.Variant: self._validate_variant_histology,
        }

    def _validate_integer_histology(self, t):
        # size is set
        if t.size is None:
            raise ConfigError('missing integer type\'s size')

    def _validate_float_histology(self, t):
        # exponent digits is set
        if t.exp_size is None:
            raise ConfigError('missing floating point number type\'s exponent size')

        # mantissa digits is set
        if t.mant_size is None:
            raise ConfigError('missing floating point number type\'s mantissa size')

        # exponent and mantissa sum is a multiple of 8
        if (t.exp_size + t.mant_size) % 8 != 0:
            raise ConfigError('floating point number type\'s mantissa and exponent sizes sum must be a multiple of 8')

    def _validate_enum_histology(self, t):
        # integer type is set
        if t.value_type is None:
            raise ConfigError('missing enumeration type\'s value type')

        # there's at least one member
        if not t.members:
            raise ConfigError('enumeration type needs at least one member')

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
                    raise ConfigError('enumeration type\'s member "{}" overlaps another member'.format(label))

            fmt = 'enumeration type\'s member "{}": value {} is outside the value type range [{}, {}]'

            if value[0] < value_min or value[0] > value_max:
                raise ConfigError(fmt.format(label, value[0], value_min, value_max))

            if value[1] < value_min or value[1] > value_max:
                raise ConfigError(fmt.format(label, value[1], value_min, value_max))

            ranges.append(value)

    def _validate_string_histology(self, t):
        # always valid
        pass

    def _validate_struct_histology(self, t):
        # all fields are valid
        for field_name, field_type in t.fields.items():
            try:
                self._validate_type_histology(field_type)
            except Exception as e:
                raise ConfigError('invalid structure type\'s field "{}"'.format(field_name), e)

    def _validate_array_histology(self, t):
        # length is set
        if t.length is None:
            raise ConfigError('missing array type\'s length')

        # element type is set
        if t.element_type is None:
            raise ConfigError('missing array type\'s element type')

        # element type is valid
        try:
            self._validate_type_histology(t.element_type)
        except Exception as e:
            raise ConfigError('invalid array type\'s element type', e)

    def _validate_variant_histology(self, t):
        # tag is set
        if t.tag is None:
            raise ConfigError('missing variant type\'s tag')

        # there's at least one type
        if not t.types:
            raise ConfigError('variant type needs at least one type')

        # all types are valid
        for type_name, type_t in t.types.items():
            try:
                self._validate_type_histology(type_t)
            except Exception as e:
                raise ConfigError('invalid variant type\'s type "{}"'.format(type_name), e)

    def _validate_type_histology(self, t):
        if t is None:
            return

        self._type_to_validate_type_histology_func[type(t)](t)

    def _validate_entity_type_histology(self, t):
        if t is None:
            return

        if type(t) is not metadata.Struct:
            raise ConfigError('expecting a structure type')

        self._validate_type_histology(t)

    def _validate_event_types_histology(self, ev):
        ev_name = ev.name

        # validate event context type
        try:
            self._validate_entity_type_histology(ev.context_type)
        except Exception as e:
            raise ConfigError('invalid event context type for event "{}"'.format(ev_name), e)

        # validate event payload type
        try:
            self._validate_entity_type_histology(ev.payload_type)
        except Exception as e:
            raise ConfigError('invalid event payload type for event "{}"'.format(ev_name), e)

    def _validate_stream_types_histology(self, stream):
        stream_name = stream.name

        # validate stream packet context type
        try:
            self._validate_entity_type_histology(stream.packet_context_type)
        except Exception as e:
            raise ConfigError('invalid stream packet context type for stream "{}"'.format(stream_name), e)

        # validate stream event header type
        try:
            self._validate_entity_type_histology(stream.event_header_type)
        except Exception as e:
            raise ConfigError('invalid stream event header type for stream "{}"'.format(stream_name), e)

        # validate stream event context type
        try:
            self._validate_entity_type_histology(stream.event_context_type)
        except Exception as e:
            raise ConfigError('invalid stream event context type for stream "{}"'.format(stream_name), e)

        # validate events
        for ev in stream.events.values():
            try:
                self._validate_event_types_histology(ev)
            except Exception as e:
                raise ConfigError('invalid event in stream "{}"'.format(stream_name), e)

    def validate(self, meta):
        # validate trace packet header type
        try:
            self._validate_entity_type_histology(meta.trace.packet_header_type)
        except Exception as e:
            raise ConfigError('invalid trace packet header type', e)

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
            'var': self._create_variant,
            'variant': self._create_variant,
        }
        self._type_to_create_type_func = {
            metadata.Integer: self._create_integer,
            metadata.FloatingPoint: self._create_float,
            metadata.Enum: self._create_enum,
            metadata.String: self._create_string,
            metadata.Struct: self._create_struct,
            metadata.Array: self._create_array,
            metadata.Variant: self._create_variant,
        }
        self._include_dirs = include_dirs
        self._ignore_include_not_found = ignore_include_not_found
        self._dump_config = dump_config

    def _set_byte_order(self, metadata_node):
        if 'trace' not in metadata_node:
            raise ConfigError('missing "trace" property (metadata)')

        trace_node = metadata_node['trace']

        if not _is_assoc_array_prop(trace_node):
            raise ConfigError('"trace" property (metadata) must be an associative array')

        if 'byte-order' not in trace_node:
            raise ConfigError('missing "byte-order" property (trace)')

        bo_node = trace_node['byte-order']

        if not _is_str_prop(bo_node):
            raise ConfigError('"byte-order" property of trace object must be a string ("le" or "be")')

        self._bo = _byte_order_str_to_bo(bo_node)

        if self._bo is None:
            raise ConfigError('invalid "byte-order" property (trace): must be "le" or "be"')

    def _lookup_type_alias(self, name):
        if name in self._tas:
            return copy.deepcopy(self._tas[name])

    def _set_int_clock_prop_mapping(self, int_obj, prop_mapping_node):
        unk_prop = _get_first_unknown_prop(prop_mapping_node, ['type', 'name', 'property'])

        if unk_prop:
            raise ConfigError('unknown property in integer type object\'s clock property mapping: "{}"'.format(unk_prop))

        if 'name' not in prop_mapping_node:
            raise ConfigError('missing "name" property in integer type object\'s clock property mapping')

        if 'property' not in prop_mapping_node:
            raise ConfigError('missing "property" property in integer type object\'s clock property mapping')

        clock_name = prop_mapping_node['name']
        prop = prop_mapping_node['property']

        if not _is_str_prop(clock_name):
            raise ConfigError('"name" property of integer type object\'s clock property mapping must be a string')

        if not _is_str_prop(prop):
            raise ConfigError('"property" property of integer type object\'s clock property mapping must be a string')

        if clock_name not in self._clocks:
            raise ConfigError('invalid clock name "{}" in integer type object\'s clock property mapping'.format(clock_name))

        if prop != 'value':
            raise ConfigError('invalid "property" property in integer type object\'s clock property mapping: "{}"'.format(prop))

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
            raise ConfigError('unknown integer type object property: "{}"'.format(unk_prop))

        # size
        if 'size' in node:
            size = node['size']

            if not _is_int_prop(size):
                raise ConfigError('"size" property of integer type object must be an integer')

            if size < 1:
                raise ConfigError('invalid integer size: {}'.format(size))

            obj.size = size

        # align
        if 'align' in node:
            align = node['align']

            if align is None:
                obj.set_default_align()
            else:
                if not _is_int_prop(align):
                    raise ConfigError('"align" property of integer type object must be an integer')

                if not _is_valid_alignment(align):
                    raise ConfigError('invalid alignment: {}'.format(align))

                obj.align = align

        # signed
        if 'signed' in node:
            signed = node['signed']

            if signed is None:
                obj.set_default_signed()
            else:
                if not _is_bool_prop(signed):
                    raise ConfigError('"signed" property of integer type object must be a boolean')

                obj.signed = signed

        # byte order
        if 'byte-order' in node:
            byte_order = node['byte-order']

            if byte_order is None:
                obj.byte_order = self._bo
            else:
                if not _is_str_prop(byte_order):
                    raise ConfigError('"byte-order" property of integer type object must be a string ("le" or "be")')

                byte_order = _byte_order_str_to_bo(byte_order)

                if byte_order is None:
                    raise ConfigError('invalid "byte-order" property in integer type object')

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
                    raise ConfigError('"base" property of integer type object must be a string ("bin", "oct", "dec", or "hex")')

                if base == 'bin':
                    base = 2
                elif base == 'oct':
                    base = 8
                elif base == 'dec':
                    base = 10
                elif base == 'hex':
                    base = 16
                else:
                    raise ConfigError('unknown "base" property value: "{}" ("bin", "oct", "dec", and "hex" are accepted)'.format(base))

                obj.base = base

        # encoding
        if 'encoding' in node:
            encoding = node['encoding']

            if encoding is None:
                obj.set_default_encoding()
            else:
                if not _is_str_prop(encoding):
                    raise ConfigError('"encoding" property of integer type object must be a string ("none", "ascii", or "utf-8")')

                encoding = _encoding_str_to_encoding(encoding)

                if encoding is None:
                    raise ConfigError('invalid "encoding" property in integer type object')

                obj.encoding = encoding

        # property mappings
        if 'property-mappings' in node:
            prop_mappings = node['property-mappings']

            if prop_mappings is None:
                obj.set_default_property_mappings()
            else:
                if not _is_array_prop(prop_mappings):
                    raise ConfigError('"property-mappings" property of integer type object must be an array')

                if len(prop_mappings) > 1:
                    raise ConfigError('length of "property-mappings" array in integer type object must be 1')

                for index, prop_mapping in enumerate(prop_mappings):
                    if not _is_assoc_array_prop(prop_mapping):
                        raise ConfigError('elements of "property-mappings" property of integer type object must be associative arrays')

                    if 'type' not in prop_mapping:
                        raise ConfigError('missing "type" property in integer type object\'s "property-mappings" array\'s element #{}'.format(index))

                    prop_type = prop_mapping['type']

                    if not _is_str_prop(prop_type):
                        raise ConfigError('"type" property of integer type object\'s "property-mappings" array\'s element #{} must be a string'.format(index))

                    if prop_type == 'clock':
                        self._set_int_clock_prop_mapping(obj, prop_mapping)
                    else:
                        raise ConfigError('unknown property mapping type "{}" in integer type object\'s "property-mappings" array\'s element #{}'.format(prop_type, index))

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
            raise ConfigError('unknown floating point number type object property: "{}"'.format(unk_prop))

        # size
        if 'size' in node:
            size = node['size']

            if not _is_assoc_array_prop(size):
                raise ConfigError('"size" property of floating point number type object must be an associative array')

            unk_prop = _get_first_unknown_prop(size, ['exp', 'mant'])

            if unk_prop:
                raise ConfigError('unknown floating point number type object\'s "size" property: "{}"'.format(unk_prop))

            if 'exp' in size:
                exp = size['exp']

                if not _is_int_prop(exp):
                    raise ConfigError('"exp" property of floating point number type object\'s "size" property must be an integer')

                if exp < 1:
                    raise ConfigError('invalid floating point number exponent size: {}')

                obj.exp_size = exp

            if 'mant' in size:
                mant = size['mant']

                if not _is_int_prop(mant):
                    raise ConfigError('"mant" property of floating point number type object\'s "size" property must be an integer')

                if mant < 1:
                    raise ConfigError('invalid floating point number mantissa size: {}')

                obj.mant_size = mant

        # align
        if 'align' in node:
            align = node['align']

            if align is None:
                obj.set_default_align()
            else:
                if not _is_int_prop(align):
                    raise ConfigError('"align" property of floating point number type object must be an integer')

                if not _is_valid_alignment(align):
                    raise ConfigError('invalid alignment: {}'.format(align))

                obj.align = align

        # byte order
        if 'byte-order' in node:
            byte_order = node['byte-order']

            if byte_order is None:
                obj.byte_order = self._bo
            else:
                if not _is_str_prop(byte_order):
                    raise ConfigError('"byte-order" property of floating point number type object must be a string ("le" or "be")')

                byte_order = _byte_order_str_to_bo(byte_order)

                if byte_order is None:
                    raise ConfigError('invalid "byte-order" property in floating point number type object')
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
            raise ConfigError('unknown enumeration type object property: "{}"'.format(unk_prop))

        # value type
        if 'value-type' in node:
            value_type_node = node['value-type']

            try:
                obj.value_type = self._create_type(value_type_node)
            except Exception as e:
                raise ConfigError('cannot create enumeration type\'s integer type', e)

        # members
        if 'members' in node:
            members_node = node['members']

            if not _is_array_prop(members_node):
                raise ConfigError('"members" property of enumeration type object must be an array')

            cur = 0
            last_value = obj.last_value

            if last_value is None:
                cur = 0
            else:
                cur = last_value + 1

            for index, m_node in enumerate(members_node):
                if not _is_str_prop(m_node) and not _is_assoc_array_prop(m_node):
                    raise ConfigError('invalid enumeration member #{}: expecting a string or an associative array'.format(index))

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
                        raise ConfigError('unknown enumeration type member object property: "{}"'.format(unk_prop))

                    if 'label' not in m_node:
                        raise ConfigError('missing "label" property in enumeration member #{}'.format(index))

                    label = m_node['label']

                    if not _is_str_prop(label):
                        raise ConfigError('"label" property of enumeration member #{} must be a string'.format(index))

                    if 'value' not in m_node:
                        raise ConfigError('missing "value" property in enumeration member ("{}")'.format(label))

                    value = m_node['value']

                    if not _is_int_prop(value) and not _is_array_prop(value):
                        raise ConfigError('invalid enumeration member ("{}"): expecting an integer or an array'.format(label))

                    if _is_int_prop(value):
                        cur = value + 1
                        value = (value, value)
                    else:
                        if len(value) != 2:
                            raise ConfigError('invalid enumeration member ("{}"): range must have exactly two items'.format(label))

                        mn = value[0]
                        mx = value[1]

                        if mn > mx:
                            raise ConfigError('invalid enumeration member ("{}"): invalid range ({} > {})'.format(label, mn, mx))

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
            raise ConfigError('unknown string type object property: "{}"'.format(unk_prop))

        # encoding
        if 'encoding' in node:
            encoding = node['encoding']

            if encoding is None:
                obj.set_default_encoding()
            else:
                if not _is_str_prop(encoding):
                    raise ConfigError('"encoding" property of string type object must be a string ("none", "ascii", or "utf-8")')

                encoding = _encoding_str_to_encoding(encoding)

                if encoding is None:
                    raise ConfigError('invalid "encoding" property in string type object')

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
            raise ConfigError('unknown string type object property: "{}"'.format(unk_prop))

        # minimum alignment
        if 'min-align' in node:
            min_align = node['min-align']

            if min_align is None:
                obj.set_default_min_align()
            else:
                if not _is_int_prop(min_align):
                    raise ConfigError('"min-align" property of structure type object must be an integer')

                if not _is_valid_alignment(min_align):
                    raise ConfigError('invalid minimum alignment: {}'.format(min_align))

                obj.min_align = min_align

        # fields
        if 'fields' in node:
            fields = node['fields']

            if fields is None:
                obj.set_default_fields()
            else:
                if not _is_assoc_array_prop(fields):
                    raise ConfigError('"fields" property of structure type object must be an associative array')

                for field_name, field_node in fields.items():
                    if not _is_valid_identifier(field_name):
                        raise ConfigError('"{}" is not a valid field name for structure type'.format(field_name))

                    try:
                        obj.fields[field_name] = self._create_type(field_node)
                    except Exception as e:
                        raise ConfigError('cannot create structure type\'s field "{}"'.format(field_name), e)

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
            raise ConfigError('unknown array type object property: "{}"'.format(unk_prop))

        # length
        if 'length' in node:
            length = node['length']

            if not _is_int_prop(length) and not _is_str_prop(length):
                raise ConfigError('"length" property of array type object must be an integer or a string')

            if type(length) is int and length < 0:
                raise ConfigError('invalid static array length: {}'.format(length))

            obj.length = length

        # element type
        if 'element-type' in node:
            element_type_node = node['element-type']

            try:
                obj.element_type = self._create_type(node['element-type'])
            except Exception as e:
                raise ConfigError('cannot create array type\'s element type', e)

        return obj

    def _create_variant(self, obj, node):
        if obj is None:
            # create variant object
            obj = metadata.Variant()

        unk_prop = self._get_first_unknown_type_prop(node, [
            'tag',
            'types',
        ])

        if unk_prop:
            raise ConfigError('unknown variant type object property: "{}"'.format(unk_prop))

        # tag
        if 'tag' in node:
            tag = node['tag']

            if not _is_str_prop(tag):
                raise ConfigError('"tag" property of variant type object must be a string')

            # do not validate variant tag for the moment; will be done in a
            # second phase
            obj.tag = tag

        # element type
        if 'types' in node:
            types = node['types']

            if not _is_assoc_array_prop(types):
                raise ConfigError('"types" property of variant type object must be an associative array')

            # do not validate type names for the moment; will be done in a
            # second phase
            for type_name, type_node in types.items():
                if not _is_valid_identifier(type_name):
                    raise ConfigError('"{}" is not a valid type name for variant type'.format(type_name))

                try:
                    obj.types[type_name] = self._create_type(type_node)
                except Exception as e:
                    raise ConfigError('cannot create variant type\'s type "{}"'.format(type_name), e)

        return obj

    def _create_type(self, type_node):
        if type(type_node) is str:
            t = self._lookup_type_alias(type_node)

            if t is None:
                raise ConfigError('unknown type alias "{}"'.format(type_node))

            return t

        if not _is_assoc_array_prop(type_node):
            raise ConfigError('type objects must be associative arrays or strings (type alias name)')

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
                    raise ConfigError('cannot specify both "inherit" and "$inherit" properties of type object: prefer "$inherit"')

                inherit_prop = '$inherit'
                inherit_node = type_node[inherit_prop]

        if inherit_node is not None and 'class' in type_node:
            raise ConfigError('cannot specify both "{}" and "class" properties in type object'.format(inherit_prop))

        if inherit_node is not None:
            if not _is_str_prop(inherit_node):
                raise ConfigError('"{}" property of type object must be a string'.format(inherit_prop))

            base = self._lookup_type_alias(inherit_node)

            if base is None:
                raise ConfigError('cannot inherit from type alias "{}": type alias does not exist at this point'.format(inherit_node))

            func = self._type_to_create_type_func[type(base)]
        else:
            if 'class' not in type_node:
                raise ConfigError('type objects which do not inherit must have a "class" property')

            class_name = type_node['class']

            if type(class_name) is not str:
                raise ConfigError('type objects\' "class" property must be a string')

            if class_name not in self._class_name_to_create_type_func:
                raise ConfigError('unknown type class "{}"'.format(class_name))

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
            raise ConfigError('"type-aliases" property (metadata) must be an associative array')

        for ta_name, ta_type in ta_node.items():
            if ta_name in self._tas:
                raise ConfigError('duplicate type alias "{}"'.format(ta_name))

            try:
                t = self._create_type(ta_type)
            except Exception as e:
                raise ConfigError('cannot create type alias "{}"'.format(ta_name), e)

            self._tas[ta_name] = t

    def _create_clock(self, node):
        # create clock object
        clock = metadata.Clock()

        if not _is_assoc_array_prop(node):
            raise ConfigError('clock objects must be associative arrays')

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
            raise ConfigError('unknown clock object property: "{}"'.format(unk_prop))

        # UUID
        if 'uuid' in node:
            uuidp = node['uuid']

            if uuidp is None:
                clock.set_default_uuid()
            else:
                if not _is_str_prop(uuidp):
                    raise ConfigError('"uuid" property of clock object must be a string')

                try:
                    uuidp = uuid.UUID(uuidp)
                except:
                    raise ConfigError('malformed UUID (clock object): "{}"'.format(uuidp))

                clock.uuid = uuidp

        # description
        if 'description' in node:
            desc = node['description']

            if desc is None:
                clock.set_default_description()
            else:
                if not _is_str_prop(desc):
                    raise ConfigError('"description" property of clock object must be a string')

                clock.description = desc

        # frequency
        if 'freq' in node:
            freq = node['freq']

            if freq is None:
                clock.set_default_freq()
            else:
                if not _is_int_prop(freq):
                    raise ConfigError('"freq" property of clock object must be an integer')

                if freq < 1:
                    raise ConfigError('invalid clock frequency: {}'.format(freq))

                clock.freq = freq

        # error cycles
        if 'error-cycles' in node:
            error_cycles = node['error-cycles']

            if error_cycles is None:
                clock.set_default_error_cycles()
            else:
                if not _is_int_prop(error_cycles):
                    raise ConfigError('"error-cycles" property of clock object must be an integer')

                if error_cycles < 0:
                    raise ConfigError('invalid clock error cycles: {}'.format(error_cycles))

                clock.error_cycles = error_cycles

        # offset
        if 'offset' in node:
            offset = node['offset']

            if offset is None:
                clock.set_default_offset_seconds()
                clock.set_default_offset_cycles()
            else:
                if not _is_assoc_array_prop(offset):
                    raise ConfigError('"offset" property of clock object must be an associative array')

                unk_prop = _get_first_unknown_prop(offset, ['cycles', 'seconds'])

                if unk_prop:
                    raise ConfigError('unknown clock object\'s offset property: "{}"'.format(unk_prop))

                # cycles
                if 'cycles' in offset:
                    offset_cycles = offset['cycles']

                    if offset_cycles is None:
                        clock.set_default_offset_cycles()
                    else:
                        if not _is_int_prop(offset_cycles):
                            raise ConfigError('"cycles" property of clock object\'s offset property must be an integer')

                        if offset_cycles < 0:
                            raise ConfigError('invalid clock offset cycles: {}'.format(offset_cycles))

                        clock.offset_cycles = offset_cycles

                # seconds
                if 'seconds' in offset:
                    offset_seconds = offset['seconds']

                    if offset_seconds is None:
                        clock.set_default_offset_seconds()
                    else:
                        if not _is_int_prop(offset_seconds):
                            raise ConfigError('"seconds" property of clock object\'s offset property must be an integer')

                        if offset_seconds < 0:
                            raise ConfigError('invalid clock offset seconds: {}'.format(offset_seconds))

                        clock.offset_seconds = offset_seconds

        # absolute
        if 'absolute' in node:
            absolute = node['absolute']

            if absolute is None:
                clock.set_default_absolute()
            else:
                if not _is_bool_prop(absolute):
                    raise ConfigError('"absolute" property of clock object must be a boolean')

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
                    raise ConfigError('cannot specify both "return-ctype" and "$return-ctype" properties of clock object: prefer "$return-ctype"')

                return_ctype_prop = '$return-ctype'
                return_ctype_node = node[return_ctype_prop]

        if return_ctype_node is not None:
            if return_ctype_node is None:
                clock.set_default_return_ctype()
            else:
                if not _is_str_prop(return_ctype_node):
                    raise ConfigError('"{}" property of clock object must be a string'.format(return_ctype_prop))

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
            raise ConfigError('"clocks" property (metadata) must be an associative array')

        for clock_name, clock_node in clocks_node.items():
            if not _is_valid_identifier(clock_name):
                raise ConfigError('invalid clock name: "{}"'.format(clock_name))

            if clock_name in self._clocks:
                raise ConfigError('duplicate clock "{}"'.format(clock_name))

            try:
                clock = self._create_clock(clock_node)
            except Exception as e:
                raise ConfigError('cannot create clock "{}"'.format(clock_name), e)

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
            raise ConfigError('"env" property (metadata) must be an associative array')

        for env_name, env_value in env_node.items():
            if env_name in env:
                raise ConfigError('duplicate environment variable "{}"'.format(env_name))

            if not _is_valid_identifier(env_name):
                raise ConfigError('invalid environment variable name: "{}"'.format(env_name))

            if not _is_int_prop(env_value) and not _is_str_prop(env_value):
                raise ConfigError('invalid environment variable value ("{}"): expecting integer or string'.format(env_name))

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
                    raise ConfigError('cannot specify both "log-levels" and "$log-levels" properties of metadata object: prefer "$log-levels"')

                log_levels_prop = '$log-levels'
                log_levels_node = metadata_node[log_levels_prop]

        if log_levels_node is None:
            return

        if not _is_assoc_array_prop(log_levels_node):
            raise ConfigError('"{}" property (metadata) must be an associative array'.format(log_levels_prop))

        for ll_name, ll_value in log_levels_node.items():
            if ll_name in self._log_levels:
                raise ConfigError('duplicate log level entry "{}"'.format(ll_name))

            if not _is_int_prop(ll_value):
                raise ConfigError('invalid log level entry ("{}"): expecting an integer'.format(ll_name))

            if ll_value < 0:
                raise ConfigError('invalid log level entry ("{}"): log level value must be positive'.format(ll_name))

            self._log_levels[ll_name] = ll_value

    def _create_trace(self, metadata_node):
        # create trace object
        trace = metadata.Trace()

        if 'trace' not in metadata_node:
            raise ConfigError('missing "trace" property (metadata)')

        trace_node = metadata_node['trace']

        if not _is_assoc_array_prop(trace_node):
            raise ConfigError('"trace" property (metadata) must be an associative array')

        unk_prop = _get_first_unknown_prop(trace_node, [
            'byte-order',
            'uuid',
            'packet-header-type',
        ])

        if unk_prop:
            raise ConfigError('unknown trace object property: "{}"'.format(unk_prop))

        # set byte order (already parsed)
        trace.byte_order = self._bo

        # UUID
        if 'uuid' in trace_node and trace_node['uuid'] is not None:
            uuidp = trace_node['uuid']

            if not _is_str_prop(uuidp):
                raise ConfigError('"uuid" property of trace object must be a string')

            if uuidp == 'auto':
                uuidp = uuid.uuid1()
            else:
                try:
                    uuidp = uuid.UUID(uuidp)
                except:
                    raise ConfigError('malformed UUID (trace object): "{}"'.format(uuidp))

            trace.uuid = uuidp

        # packet header type
        if 'packet-header-type' in trace_node and trace_node['packet-header-type'] is not None:
            try:
                ph_type = self._create_type(trace_node['packet-header-type'])
            except Exception as e:
                raise ConfigError('cannot create packet header type (trace)', e)

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
            raise ConfigError('event objects must be associative arrays')

        unk_prop = _get_first_unknown_prop(event_node, [
            'log-level',
            'context-type',
            'payload-type',
        ])

        if unk_prop:
            raise ConfigError('unknown event object property: "{}"'.format(unk_prop))

        if 'log-level' in event_node and event_node['log-level'] is not None:
            ll_node = event_node['log-level']

            if _is_str_prop(ll_node):
                ll_value = self._lookup_log_level(event_node['log-level'])

                if ll_value is None:
                    raise ConfigError('cannot find log level "{}"'.format(ll_node))

                ll = metadata.LogLevel(event_node['log-level'], ll_value)
            elif _is_int_prop(ll_node):
                if ll_node < 0:
                    raise ConfigError('invalid log level value {}: value must be positive'.format(ll_node))

                ll = metadata.LogLevel(None, ll_node)
            else:
                raise ConfigError('"log-level" property must be either a string or an integer')

            event.log_level = ll

        if 'context-type' in event_node and event_node['context-type'] is not None:
            ctx_type_node = event_node['context-type']

            try:
                t = self._create_type(event_node['context-type'])
            except Exception as e:
                raise ConfigError('cannot create event\'s context type object', e)

            event.context_type = t

        if 'payload-type' in event_node and event_node['payload-type'] is not None:
            try:
                t = self._create_type(event_node['payload-type'])
            except Exception as e:
                raise ConfigError('cannot create event\'s payload type object', e)

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

            raise ConfigError('unknown stream object property{}: "{}"'.format(add, unk_prop))

        if 'packet-context-type' in stream_node and stream_node['packet-context-type'] is not None:
            try:
                t = self._create_type(stream_node['packet-context-type'])
            except Exception as e:
                raise ConfigError('cannot create stream\'s packet context type object', e)

            stream.packet_context_type = t

        if 'event-header-type' in stream_node and stream_node['event-header-type'] is not None:
            try:
                t = self._create_type(stream_node['event-header-type'])
            except Exception as e:
                raise ConfigError('cannot create stream\'s event header type object', e)

            stream.event_header_type = t

        if 'event-context-type' in stream_node and stream_node['event-context-type'] is not None:
            try:
                t = self._create_type(stream_node['event-context-type'])
            except Exception as e:
                raise ConfigError('cannot create stream\'s event context type object', e)

            stream.event_context_type = t

        if 'events' not in stream_node:
            raise ConfigError('missing "events" property in stream object')

        events = stream_node['events']

        if events is not None:
            if not _is_assoc_array_prop(events):
                raise ConfigError('"events" property of stream object must be an associative array')

            if not events:
                raise ConfigError('at least one event is needed within a stream object')

            cur_id = 0

            for ev_name, ev_node in events.items():
                try:
                    ev = self._create_event(ev_node)
                except Exception as e:
                    raise ConfigError('cannot create event "{}"'.format(ev_name), e)

                ev.id = cur_id
                ev.name = ev_name
                stream.events[ev_name] = ev
                cur_id += 1

        if '$default' in stream_node and stream_node['$default'] is not None:
            default_node = stream_node['$default']

            if not _is_bool_prop(default_node):
                raise ConfigError('invalid "$default" property in stream object: expecting a boolean')

            if default_node:
                if self._meta.default_stream_name is not None and self._meta.default_stream_name != stream_name:
                    fmt = 'cannot specify more than one default stream (default stream already set to "{}")'
                    raise ConfigError(fmt.format(self._meta.default_stream_name))

                self._meta.default_stream_name = stream_name

        return stream

    def _create_streams(self, metadata_node):
        streams = collections.OrderedDict()

        if 'streams' not in metadata_node:
            raise ConfigError('missing "streams" property (metadata)')

        streams_node = metadata_node['streams']

        if not _is_assoc_array_prop(streams_node):
            raise ConfigError('"streams" property (metadata) must be an associative array')

        if not streams_node:
            raise ConfigError('at least one stream is needed (metadata)')

        cur_id = 0

        for stream_name, stream_node in streams_node.items():
            try:
                stream = self._create_stream(stream_name, stream_node)
            except Exception as e:
                raise ConfigError('cannot create stream "{}"'.format(stream_name), e)

            stream.id = cur_id
            stream.name = str(stream_name)
            streams[stream_name] = stream
            cur_id += 1

        return streams

    def _create_metadata(self, root):
        self._meta = metadata.Metadata()

        if 'metadata' not in root:
            raise ConfigError('missing "metadata" property (configuration)')

        metadata_node = root['metadata']

        if not _is_assoc_array_prop(metadata_node):
            raise ConfigError('"metadata" property (configuration) must be an associative array')

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

            raise ConfigError('unknown metadata property{}: "{}"'.format(add, unk_prop))

        if '$default-stream' in metadata_node and metadata_node['$default-stream'] is not None:
            default_stream_node = metadata_node['$default-stream']

            if not _is_str_prop(default_stream_node):
                raise ConfigError('invalid "$default-stream" property (metadata): expecting a string')

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
            raise ConfigError('missing "version" property (configuration)')

        version_node = root['version']

        if not _is_str_prop(version_node):
            raise ConfigError('"version" property (configuration) must be a string')

        version_node = version_node.strip()

        if version_node not in ['2.0', '2.1', '2.2']:
            raise ConfigError('unsupported version ({}): versions 2.0, 2.1, and 2.2 are supported'.format(version_node))

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
            raise ConfigError('"prefix" property (configuration) must be a string')

        if not _is_valid_identifier(prefix_node):
            raise ConfigError('"prefix" property (configuration) must be a valid C identifier')

        return prefix_node

    def _get_options(self, root):
        cfg_options = ConfigOptions()

        if 'options' not in root:
            return cfg_options

        options_node = root['options']

        if not _is_assoc_array_prop(options_node):
            raise ConfigError('"options" property (configuration) must be an associative array')

        known_props = [
            'gen-prefix-def',
            'gen-default-stream-def',
        ]
        unk_prop = _get_first_unknown_prop(options_node, known_props)

        if unk_prop:
            raise ConfigError('unknown configuration option property: "{}"'.format(unk_prop))

        if 'gen-prefix-def' in options_node and options_node['gen-prefix-def'] is not None:
            gen_prefix_def_node = options_node['gen-prefix-def']

            if not _is_bool_prop(gen_prefix_def_node):
                raise ConfigError('invalid configuration option "gen-prefix-def": expecting a boolean')

            cfg_options.gen_prefix_def = gen_prefix_def_node

        if 'gen-default-stream-def' in options_node and options_node['gen-default-stream-def'] is not None:
            gen_default_stream_def_node = options_node['gen-default-stream-def']

            if not _is_bool_prop(gen_default_stream_def_node):
                raise ConfigError('invalid configuration option "gen-default-stream-def": expecting a boolean')

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
                raise ConfigError('in "{}": cannot recursively include file "{}"'.format(base_path, norm_path))

            self._include_stack.append(norm_path)

            # load raw content
            return self._yaml_ordered_load(norm_path)

        if not self._ignore_include_not_found:
            base_path = self._get_last_include_file()
            raise ConfigError('in "{}": cannot include file "{}": file not found in include directories'.format(base_path, yaml_path))

        return None

    def _get_include_paths(self, include_node):
        if include_node is None:
            return []

        if _is_str_prop(include_node):
            return [include_node]

        if _is_array_prop(include_node):
            for include_path in include_node:
                if not _is_str_prop(include_path):
                    raise ConfigError('invalid include property: expecting array of strings')

            return include_node

        raise ConfigError('invalid include property: expecting string or array of strings')

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
            raise ConfigError('{} objects must be associative arrays'.format(name))

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
            except Exception as e:
                raise ConfigError('in "{}"'.format(cur_base_path), e)

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
                    raise ConfigError('"events" property must be an associative array')

                events_node_keys = list(events_node.keys())

                for key in events_node_keys:
                    event_node = events_node[key]

                    try:
                        events_node[key] = self._process_event_include(event_node)
                    except Exception as e:
                        raise ConfigError('cannot process includes of event object "{}"'.format(key), e)

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
                    raise ConfigError('"clocks" property (metadata) must be an associative array')

                clocks_node_keys = list(clocks_node.keys())

                for key in clocks_node_keys:
                    clock_node = clocks_node[key]

                    try:
                        clocks_node[key] = self._process_clock_include(clock_node)
                    except Exception as e:
                        raise ConfigError('cannot process includes of clock object "{}"'.format(key), e)

            if 'streams' in metadata_node:
                streams_node = metadata_node['streams']

                if not _is_assoc_array_prop(streams_node):
                    raise ConfigError('"streams" property (metadata) must be an associative array')

                streams_node_keys = list(streams_node.keys())

                for key in streams_node_keys:
                    stream_node = streams_node[key]

                    try:
                        streams_node[key] = self._process_stream_include(stream_node)
                    except Exception as e:
                        raise ConfigError('cannot process includes of stream object "{}"'.format(key), e)

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
            raise ConfigError('cannot open file "{}"'.format(yaml_path))
        except Exception as e:
            raise ConfigError('unknown error while trying to load file "{}"'.format(yaml_path), e)

        # loaded node must be an associate array
        if not _is_assoc_array_prop(node):
            raise ConfigError('root of YAML file "{}" must be an associative array'.format(yaml_path))

        return node

    def _reset(self):
        self._version = None
        self._include_stack = []

    def parse(self, yaml_path):
        self._reset()
        self._root_yaml_path = yaml_path

        try:
            root = self._yaml_ordered_load(yaml_path)
        except Exception as e:
            raise ConfigError('cannot parse YAML file "{}"'.format(yaml_path), e)

        if not _is_assoc_array_prop(root):
            raise ConfigError('configuration must be an associative array')

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

            raise ConfigError('unknown configuration property{}: "{}"'.format(add, unk_prop))

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
    except Exception as e:
        raise ConfigError('cannot create configuration from YAML file "{}"'.format(path), e)
