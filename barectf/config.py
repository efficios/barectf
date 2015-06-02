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

from barectf import metadata
import collections
import datetime
import barectf
import enum
import yaml
import uuid
import copy
import re


class ConfigError(RuntimeError):
    def __init__(self, msg, prev=None):
        super().__init__(msg)
        self._prev = prev

    @property
    def prev(self):
        return self._prev


class Config:
    def __init__(self, version, prefix, metadata):
        self.prefix = prefix
        self.version = version
        self.metadata = metadata

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
        env = meta.env

        env['domain'] = 'bare'
        env['tracer_name'] = 'barectf'
        version_tuple = barectf.get_version_tuple()
        env['tracer_major'] = version_tuple[0]
        env['tracer_minor'] = version_tuple[1]
        env['tracer_patch'] = version_tuple[2]
        env['barectf_gen_date'] = str(datetime.datetime.now().isoformat())

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
        if not is_valid_identifier(value):
            raise ConfigError('prefix must be a valid C identifier')

        self._prefix = value


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


def is_valid_identifier(iden):
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


def _get_first_unknown_type_prop(type_node, known_props):
    kp = known_props + ['inherit', 'class']

    return _get_first_unknown_prop(type_node, kp)


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
            if not is_valid_identifier(stream_name):
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
                    if not is_valid_identifier(ev_name):
                        raise ConfigError('event name "{}" is not a valid C identifier'.format(ev_name))

                    self._cur_entity = _Entity.EVENT_CONTEXT

                    try:
                        self._validate_entity(ev.context_type)
                    except Exception as e:
                        raise ConfigError('invalid context type in event "{}"'.format(ev_name), e)

                    self._cur_entity = _Entity.EVENT_PAYLOAD

                    if ev.payload_type is None:
                        raise ConfigError('missing payload type in event "{}"'.format(ev_name), e)

                    try:
                        self._validate_entity(ev.payload_type)
                    except Exception as e:
                        raise ConfigError('invalid payload type in event "{}"'.format(ev_name), e)

                    if not ev.payload_type.fields:
                        raise ConfigError('empty payload type in event "{}"'.format(ev_name), e)
            except Exception as e:
                raise ConfigError('invalid stream "{}"'.format(stream_name), e)

    def validate(self, meta):
        self._validate_entities_and_names(meta)


# This validator validates special fields of trace, stream, and event
# types. For example, if checks that the "stream_id" field exists in the
# trace packet header if there's more than one stream, and much more.
class _MetadataSpecialFieldsValidator:
    def _validate_trace_packet_header_type(self, t):
        # needs "stream_id" field?
        if len(self._meta.streams) > 1:
            # yes
            if t is None:
                raise ConfigError('need "stream_id" field in trace packet header type, but trace packet header type is missing')

            if type(t) is not metadata.Struct:
                raise ConfigError('need "stream_id" field in trace packet header type, but trace packet header type is not a structure type')

            if 'stream_id' not in t.fields:
                raise ConfigError('need "stream_id" field in trace packet header type')

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
            elif field_name == 'uuid':
                if self._meta.trace.uuid is None:
                    raise ConfigError('"uuid" field in trace packet header type specified, but no trace UUID provided')

                if type(field_type) is not metadata.Array:
                    raise ConfigError('"uuid" field in trace packet header type must be an array')

                if field_type.length != 16:
                    raise ConfigError('"uuid" field in trace packet header type must be an array of 16 bytes')

                element_type = field_type.element_type

                if type(element_type) is not metadata.Integer:
                    raise ConfigError('"uuid" field in trace packet header type must be an array of 16 bytes')

                if element_type.size != 8:
                    raise ConfigError('"uuid" field in trace packet header type must be an array of 16 bytes')

                if element_type.align != 8:
                    raise ConfigError('"uuid" field in trace packet header type must be an array of 16 byte-aligned bytes')

    def _validate_trace(self, meta):
        self._validate_trace_packet_header_type(meta.trace.packet_header_type)

    def _validate_stream_packet_context(self, stream):
        t = stream.packet_context_type

        if type(t) is None:
            return

        if type(t) is not metadata.Struct:
            return

        # "timestamp_begin", if exists, is an unsigned integer type,
        # mapped to a clock
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

    def _validate_stream_event_header(self, stream):
        t = stream.event_header_type

        # needs "id" field?
        if len(stream.events) > 1:
            # yes
            if t is None:
                raise ConfigError('need "id" field in stream event header type, but stream event header type is missing')

            if type(t) is not metadata.Struct:
                raise ConfigError('need "id" field in stream event header type, but stream event header type is not a structure type')

            if 'id' not in t.fields:
                raise ConfigError('need "id" field in stream event header type')

        # validate "id" and "timestamp" types
        if type(t) is not metadata.Struct:
            return

        # "timestamp", if exists, is an unsigned integer type,
        # mapped to a clock
        if 'timestamp' in t.fields:
            ts = t.fields['timestamp']

            if type(ts) is not metadata.Integer:
                raise ConfigError('"ts" field in stream event header type must be an integer type')

            if ts.signed:
                raise ConfigError('"ts" field in stream event header type must be an unsigned integer type')

            if not ts.property_mappings:
                raise ConfigError('"ts" field in stream event header type must be mapped to a clock')

        # "id" is an unsigned integer type
        if 'id' in t.fields:
            eid = t.fields['id']

            if type(eid) is not metadata.Integer:
                raise ConfigError('"id" field in stream event header type must be an integer type')

            if eid.signed:
                raise ConfigError('"id" field in stream event header type must be an unsigned integer type')

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
        if not t.is_static:
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
# trace, stream, and event types are all complete and valid.
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
            raise ConfigError('missing enumeration type\'s integer type')

        # there's at least one member
        if not t.members:
            raise ConfigError('enumeration type needs at least one member')

        # no overlapping values
        ranges = []

        for label, value in t.members.items():
            for rg in ranges:
                if value[0] <= rg[1] and rg[0] <= value[1]:
                    raise ConfigError('enumeration type\'s member "{}" overlaps another member'.format(label))

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

        # entity cannot be an array
        if type(t) is metadata.Array:
            raise ConfigError('cannot use an array here')

        self._validate_type_histology(t)

    def _validate_event_types_histology(self, ev):
        ev_name = ev.name

        # validate event context type
        try:
            self._validate_entity_type_histology(ev.context_type)
        except Exception as e:
            raise ConfigError('invalid event context type for event "{}"'.format(ev_name), e)

        # validate event payload type
        if ev.payload_type is None:
            raise ConfigError('event payload type must exist in event "{}"'.format(ev_name))

        # TODO: also check arrays, sequences, and variants
        if type(ev.payload_type) is metadata.Struct:
            if not ev.payload_type.fields:
                raise ConfigError('event payload type must have at least one field for event "{}"'.format(ev_name))

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
    def __init__(self):
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

    def _set_byte_order(self, metadata_node):
        if 'trace' not in metadata_node:
            raise ConfigError('missing "trace" property (metadata)')

        trace_node = metadata_node['trace']

        if not _is_assoc_array_prop(trace_node):
            raise ConfigError('"trace" property (metadata) must be an associative array')

        if 'byte-order' not in trace_node:
            raise ConfigError('missing "byte-order" property (trace)')

        self._bo = _byte_order_str_to_bo(trace_node['byte-order'])

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

    def _create_integer(self, obj, node):
        if obj is None:
            # create integer object
            obj = metadata.Integer()

        unk_prop = _get_first_unknown_type_prop(node, [
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

            if not _is_int_prop(align):
                raise ConfigError('"align" property of integer type object must be an integer')

            if not _is_valid_alignment(align):
                raise ConfigError('invalid alignment: {}'.format(align))

            obj.align = align

        # signed
        if 'signed' in node:
            signed = node['signed']

            if not _is_bool_prop(signed):
                raise ConfigError('"signed" property of integer type object must be a boolean')

            obj.signed = signed

        # byte order
        if 'byte-order' in node:
            byte_order = node['byte-order']

            if not _is_str_prop(byte_order):
                raise ConfigError('"byte-order" property of integer type object must be a string ("le" or "be")')

            byte_order = _byte_order_str_to_bo(byte_order)

            if byte_order is None:
                raise ConfigError('invalid "byte-order" property in integer type object')
        else:
            byte_order = self._bo

        obj.byte_order = byte_order

        # base
        if 'base' in node:
            base = node['base']

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

            obj.base = base

        # encoding
        if 'encoding' in node:
            encoding = node['encoding']

            if not _is_str_prop(encoding):
                raise ConfigError('"encoding" property of integer type object must be a string ("none", "ascii", or "utf-8")')

            encoding = _encoding_str_to_encoding(encoding)

            if encoding is None:
                raise ConfigError('invalid "encoding" property in integer type object')

            obj.encoding = encoding

        # property mappings
        if 'property-mappings' in node:
            prop_mappings = node['property-mappings']

            if not _is_array_prop(prop_mappings):
                raise ConfigError('"property-mappings" property of integer type object must be an array')

            if len(prop_mappings) > 1:
                raise ConfigError('length of "property-mappings" array in integer type object must be 1')

            del obj.property_mappings[:]

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

        unk_prop = _get_first_unknown_type_prop(node, [
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

            unk_prop = _get_first_unknown_prop(node, ['exp', 'mant'])

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

            if not _is_int_prop(align):
                raise ConfigError('"align" property of floating point number type object must be an integer')

            if not _is_valid_alignment(align):
                raise ConfigError('invalid alignment: {}'.format(align))

            obj.align = align

        # byte order
        if 'byte-order' in node:
            byte_order = node['byte-order']

            if not _is_str_prop(byte_order):
                raise ConfigError('"byte-order" property of floating point number type object must be a string ("le" or "be")')

            byte_order = _byte_order_str_to_bo(byte_order)

            if byte_order is None:
                raise ConfigError('invalid "byte-order" property in floating point number type object')
        else:
            byte_order = self._bo

        obj.byte_order = byte_order

        return obj

    def _create_enum(self, obj, node):
        if obj is None:
            # create enumeration object
            obj = metadata.Enum()

        unk_prop = _get_first_unknown_type_prop(node, [
            'value-type',
            'members',
        ])

        if unk_prop:
            raise ConfigError('unknown enumeration type object property: "{}"'.format(unk_prop))

        # value type
        if 'value-type' in node:
            try:
                obj.value_type = self._create_type(node['value-type'])
            except Exception as e:
                raise ConfigError('cannot create enumeration type\'s integer type', e)

        # members
        if 'members' in node:
            members_node = node['members']

            if not _is_array_prop(members_node):
                raise ConfigError('"members" property of enumeration type object must be an array')

            cur = 0

            for index, m_node in enumerate(members_node):
                if not _is_str_prop(m_node) and not _is_assoc_array_prop(m_node):
                    raise ConfigError('invalid enumeration member #{}: expecting a string or an associative array'.format(index))

                if _is_str_prop(m_node):
                    label = m_node
                    value = (cur, cur)
                    cur += 1
                else:
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

        unk_prop = _get_first_unknown_type_prop(node, [
            'encoding',
        ])

        if unk_prop:
            raise ConfigError('unknown string type object property: "{}"'.format(unk_prop))

        # encoding
        if 'encoding' in node:
            encoding = node['encoding']

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

        unk_prop = _get_first_unknown_type_prop(node, [
            'min-align',
            'fields',
        ])

        if unk_prop:
            raise ConfigError('unknown string type object property: "{}"'.format(unk_prop))

        # minimum alignment
        if 'min-align' in node:
            min_align = node['min-align']

            if not _is_int_prop(min_align):
                raise ConfigError('"min-align" property of structure type object must be an integer')

            if not _is_valid_alignment(min_align):
                raise ConfigError('invalid minimum alignment: {}'.format(min_align))

            obj.min_align = min_align

        # fields
        if 'fields' in node:
            fields = node['fields']

            if not _is_assoc_array_prop(fields):
                raise ConfigError('"fields" property of structure type object must be an associative array')

            for field_name, field_node in fields.items():
                if not is_valid_identifier(field_name):
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

        unk_prop = _get_first_unknown_type_prop(node, [
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
            try:
                obj.element_type = self._create_type(node['element-type'])
            except Exception as e:
                raise ConfigError('cannot create array type\'s element type', e)

        return obj

    def _create_variant(self, obj, node):
        if obj is None:
            # create variant object
            obj = metadata.Variant()

        unk_prop = _get_first_unknown_type_prop(node, [
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
                if not is_valid_identifier(type_name):
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
            raise ConfigError('type objects must be associative arrays')

        if 'inherit' in type_node and 'class' in type_node:
            raise ConfigError('cannot specify both "inherit" and "class" properties in type object')

        if 'inherit' in type_node:
            inherit = type_node['inherit']

            if not _is_str_prop(inherit):
                raise ConfigError('"inherit" property of type object must be a string')

            base = self._lookup_type_alias(inherit)

            if base is None:
                raise ConfigError('cannot inherit from type alias "{}": type alias does not exist'.format(inherit))

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

        unk_prop = _get_first_unknown_prop(node, [
            'uuid',
            'description',
            'freq',
            'error-cycles',
            'offset',
            'absolute',
            'return-ctype',
        ])

        if unk_prop:
            raise ConfigError('unknown clock object property: "{}"'.format(unk_prop))

        # UUID
        if 'uuid' in node:
            uuidp = node['uuid']

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

            if not _is_str_prop(desc):
                raise ConfigError('"description" property of clock object must be a string')

            clock.description = desc

        # frequency
        if 'freq' in node:
            freq = node['freq']

            if not _is_int_prop(freq):
                raise ConfigError('"freq" property of clock object must be an integer')

            if freq < 1:
                raise ConfigError('invalid clock frequency: {}'.format(freq))

            clock.freq = freq

        # error cycles
        if 'error-cycles' in node:
            error_cycles = node['error-cycles']

            if not _is_int_prop(error_cycles):
                raise ConfigError('"error-cycles" property of clock object must be an integer')

            if error_cycles < 0:
                raise ConfigError('invalid clock error cycles: {}'.format(error_cycles))

            clock.error_cycles = error_cycles

        # offset
        if 'offset' in node:
            offset = node['offset']

            if not _is_assoc_array_prop(offset):
                raise ConfigError('"offset" property of clock object must be an associative array')

            unk_prop = _get_first_unknown_prop(offset, ['cycles', 'seconds'])

            if unk_prop:
                raise ConfigError('unknown clock object\'s offset property: "{}"'.format(unk_prop))

            # cycles
            if 'cycles' in offset:
                offset_cycles = offset['cycles']

                if not _is_int_prop(offset_cycles):
                    raise ConfigError('"cycles" property of clock object\'s offset property must be an integer')

                if offset_cycles < 0:
                    raise ConfigError('invalid clock offset cycles: {}'.format(offset_cycles))

                clock.offset_cycles = offset_cycles

            # seconds
            if 'seconds' in offset:
                offset_seconds = offset['seconds']

                if not _is_int_prop(offset_seconds):
                    raise ConfigError('"seconds" property of clock object\'s offset property must be an integer')

                if offset_seconds < 0:
                    raise ConfigError('invalid clock offset seconds: {}'.format(offset_seconds))

                clock.offset_seconds = offset_seconds

        # absolute
        if 'absolute' in node:
            absolute = node['absolute']

            if not _is_bool_prop(absolute):
                raise ConfigError('"absolute" property of clock object must be a boolean')

            clock.absolute = absolute

        # return C type
        if 'return-ctype' in node:
            ctype = node['return-ctype']

            if not _is_str_prop(ctype):
                raise ConfigError('"return-ctype" property of clock object must be a string')

            clock.return_ctype = ctype

        return clock

    def _register_clocks(self, metadata_node):
        self._clocks = collections.OrderedDict()

        if 'clocks' not in metadata_node:
            return

        clocks_node = metadata_node['clocks']

        if not _is_assoc_array_prop(clocks_node):
            raise ConfigError('"clocks" property (metadata) must be an associative array')

        for clock_name, clock_node in clocks_node.items():
            if not is_valid_identifier(clock_name):
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

        if not _is_assoc_array_prop(env_node):
            raise ConfigError('"env" property (metadata) must be an associative array')

        for env_name, env_value in env_node.items():
            if env_name in env:
                raise ConfigError('duplicate environment variable "{}"'.format(env_name))

            if not is_valid_identifier(env_name):
                raise ConfigError('invalid environment variable name: "{}"'.format(env_name))

            if not _is_int_prop(env_value) and not _is_str_prop(env_value):
                raise ConfigError('invalid environment variable value ("{}"): expecting integer or string'.format(env_name))

            env[env_name] = env_value

        return env

    def _register_log_levels(self, metadata_node):
        self._log_levels = dict()

        if 'log-levels' not in metadata_node:
            return

        log_levels_node = metadata_node['log-levels']

        if not _is_assoc_array_prop(log_levels_node):
            raise ConfigError('"log-levels" property (metadata) must be an associative array')

        for ll_name, ll_value in log_levels_node.items():
            if ll_name in self._log_levels:
                raise ConfigError('duplicate log level entry "{}"'.format(ll_name))

            if not _is_int_prop(ll_value):
                raise ConfigError('invalid log level entry ("{}"): expecting an integer'.format(ll_name))

            self._log_levels[ll_name] = ll_value

    def _create_trace(self, metadata_node):
        # create trace object
        trace = metadata.Trace()
        trace_node = metadata_node['trace']
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
        if 'uuid' in trace_node:
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
        if 'packet-header-type' in trace_node:
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
        unk_prop = _get_first_unknown_prop(event_node, [
            'log-level',
            'context-type',
            'payload-type',
        ])

        if unk_prop:
            raise ConfigError('unknown event object property: "{}"'.format(unk_prop))

        if not _is_assoc_array_prop(event_node):
            raise ConfigError('event objects must be associative arrays')

        if 'log-level' in event_node:
            ll = self._lookup_log_level(event_node['log-level'])

            if ll is None:
                raise ConfigError('invalid "log-level" property')

            event.log_level = ll

        if 'context-type' in event_node:
            try:
                t = self._create_type(event_node['context-type'])
            except Exception as e:
                raise ConfigError('cannot create event\'s context type object', e)

            event.context_type = t

        if 'payload-type' not in event_node:
            raise ConfigError('missing "payload-type" property in event object')

        try:
            t = self._create_type(event_node['payload-type'])
        except Exception as e:
            raise ConfigError('cannot create event\'s payload type object', e)

        event.payload_type = t

        return event

    def _create_stream(self, stream_node):
        stream = metadata.Stream()
        unk_prop = _get_first_unknown_prop(stream_node, [
            'packet-context-type',
            'event-header-type',
            'event-context-type',
            'events',
        ])

        if unk_prop:
            raise ConfigError('unknown stream object property: "{}"'.format(unk_prop))

        if not _is_assoc_array_prop(stream_node):
            raise ConfigError('stream objects must be associative arrays')

        if 'packet-context-type' in stream_node:
            try:
                t = self._create_type(stream_node['packet-context-type'])
            except Exception as e:
                raise ConfigError('cannot create stream\'s packet context type object', e)

            stream.packet_context_type = t

        if 'event-header-type' in stream_node:
            try:
                t = self._create_type(stream_node['event-header-type'])
            except Exception as e:
                raise ConfigError('cannot create stream\'s event header type object', e)

            stream.event_header_type = t

        if 'event-context-type' in stream_node:
            try:
                t = self._create_type(stream_node['event-context-type'])
            except Exception as e:
                raise ConfigError('cannot create stream\'s event context type object', e)

            stream.event_context_type = t

        if 'events' not in stream_node:
            raise ConfigError('missing "events" property in stream object')

        events = stream_node['events']

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
                stream = self._create_stream(stream_node)
            except Exception as e:
                raise ConfigError('cannot create stream "{}"'.format(stream_name), e)

            stream.id = cur_id
            stream.name = str(stream_name)
            streams[stream_name] = stream
            cur_id += 1

        return streams

    def _create_metadata(self, root):
        meta = metadata.Metadata()

        if 'metadata' not in root:
            raise ConfigError('missing "metadata" property (root)')

        metadata_node = root['metadata']
        unk_prop = _get_first_unknown_prop(metadata_node, [
            'type-aliases',
            'log-levels',
            'trace',
            'env',
            'clocks',
            'streams',
        ])

        if unk_prop:
            raise ConfigError('unknown metadata property: "{}"'.format(unk_prop))

        if not _is_assoc_array_prop(metadata_node):
            raise ConfigError('"metadata" property (root) must be an associative array')

        self._set_byte_order(metadata_node)
        self._register_clocks(metadata_node)
        meta.clocks = self._clocks
        self._register_type_aliases(metadata_node)
        meta.env = self._create_env(metadata_node)
        meta.trace = self._create_trace(metadata_node)
        self._register_log_levels(metadata_node)
        meta.streams = self._create_streams(metadata_node)

        return meta

    def _get_version(self, root):
        if 'version' not in root:
            raise ConfigError('missing "version" property (root)')

        version_node = root['version']

        if not _is_str_prop(version_node):
            raise ConfigError('"version" property (root) must be a string')

        if version_node != '2.0':
            raise ConfigError('unsupported version: {}'.format(version_node))

        return version_node

    def _get_prefix(self, root):
        if 'prefix' not in root:
            return 'barectf_'

        prefix_node = root['prefix']

        if not _is_str_prop(prefix_node):
            raise ConfigError('"prefix" property (root) must be a string')

        if not is_valid_identifier(prefix_node):
            raise ConfigError('"prefix" property (root) must be a valid C identifier')

        return prefix_node

    def _yaml_ordered_load(self, stream):
        class OLoader(yaml.Loader):
            pass

        def construct_mapping(loader, node):
            loader.flatten_mapping(node)

            return collections.OrderedDict(loader.construct_pairs(node))

        OLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                                construct_mapping)

        return yaml.load(stream, OLoader)

    def parse(self, yml):
        try:
            root = self._yaml_ordered_load(yml)
        except Exception as e:
            raise ConfigError('cannot parse YAML input', e)

        if not _is_assoc_array_prop(root):
            raise ConfigError('root must be an associative array')

        self._version = self._get_version(root)
        meta = self._create_metadata(root)
        prefix = self._get_prefix(root)

        return Config(self._version, prefix, meta)


def from_yaml(yml):
    parser = _YamlConfigParser()
    cfg = parser.parse(yml)

    return cfg


def from_yaml_file(path):
    try:
        with open(path) as f:
            return from_yaml(f.read())
    except Exception as e:
        raise ConfigError('cannot create configuration from YAML file'.format(e), e)
