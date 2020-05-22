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
from barectf import config
import pkg_resources
import collections
import jsonschema
import datetime
import barectf
import os.path
import enum
import yaml
import uuid
import copy
import re
import os


class _ConfigParseErrorCtx:
    def __init__(self, name, msg=None):
        self._name = name
        self._msg = msg

    @property
    def name(self):
        return self._name

    @property
    def msg(self):
        return self._msg


class ConfigParseError(RuntimeError):
    def __init__(self, init_ctx_name, init_ctx_msg=None):
        self._ctx = []
        self.append_ctx(init_ctx_name, init_ctx_msg)

    @property
    def ctx(self):
        return self._ctx

    def append_ctx(self, name, msg=None):
        self._ctx.append(_ConfigParseErrorCtx(name, msg))


def _opt_to_public(obj):
    if obj is None:
        return

    return obj.to_public()


class _PseudoObj:
    def __init__(self):
        self._public = None

    def to_public(self):
        if self._public is None:
            self._public = self._to_public()

        return self._public

    def _to_public(self):
        raise NotImplementedError


class _PropertyMapping(_PseudoObj):
    def __init__(self):
        super().__init__()
        self.object = None
        self.prop = None

    def _to_public(self):
        return metadata.PropertyMapping(self.object.to_public(), self.prop)


class _Integer(_PseudoObj):
    def __init__(self):
        super().__init__()
        self.size = None
        self.byte_order = None
        self.align = None
        self.signed = False
        self.base = 10
        self.encoding = metadata.Encoding.NONE
        self.property_mappings = []

    @property
    def real_align(self):
        if self.align is None:
            if self.size % 8 == 0:
                return 8
            else:
                return 1
        else:
            return self.align

    def _to_public(self):
        prop_mappings = [pm.to_public() for pm in self.property_mappings]
        return metadata.Integer(self.size, self.byte_order, self.align,
                                self.signed, self.base, self.encoding,
                                prop_mappings)


class _FloatingPoint(_PseudoObj):
    def __init__(self):
        super().__init__()
        self.exp_size = None
        self.mant_size = None
        self.byte_order = None
        self.align = 8

    @property
    def real_align(self):
        return self.align

    def _to_public(self):
        return metadata.FloatingPoint(self.exp_size, self.mant_size,
                                      self.byte_order, self.align)


class _Enum(_PseudoObj):
    def __init__(self):
        super().__init__()
        self.value_type = None
        self.members = collections.OrderedDict()

    @property
    def real_align(self):
        return self.value_type.real_align

    def _to_public(self):
        return metadata.Enum(self.value_type.to_public(), self.members)


class _String(_PseudoObj):
    def __init__(self):
        super().__init__()
        self.encoding = metadata.Encoding.UTF8

    @property
    def real_align(self):
        return 8

    def _to_public(self):
        return metadata.String(self.encoding)


class _Array(_PseudoObj):
    def __init__(self):
        super().__init__()
        self.element_type = None
        self.length = None

    @property
    def real_align(self):
        return self.element_type.real_align

    def _to_public(self):
        return metadata.Array(self.element_type.to_public(), self.length)


class _Struct(_PseudoObj):
    def __init__(self):
        super().__init__()
        self.min_align = 1
        self.fields = collections.OrderedDict()

    @property
    def real_align(self):
        align = self.min_align

        for pseudo_field in self.fields.values():
            if pseudo_field.real_align > align:
                align = pseudo_field.real_align

        return align

    def _to_public(self):
        fields = []

        for name, pseudo_field in self.fields.items():
            fields.append((name, pseudo_field.to_public()))

        return metadata.Struct(self.min_align, collections.OrderedDict(fields))


class _Trace(_PseudoObj):
    def __init__(self):
        super().__init__()
        self.byte_order = None
        self.uuid = None
        self.packet_header_type = None

    def _to_public(self):
        return metadata.Trace(self.byte_order, self.uuid,
                              _opt_to_public(self.packet_header_type))


class _Clock(_PseudoObj):
    def __init__(self):
        super().__init__()
        self.name = None
        self.uuid = None
        self.description = None
        self.freq = int(1e9)
        self.error_cycles = 0
        self.offset_seconds = 0
        self.offset_cycles = 0
        self.absolute = False
        self.return_ctype = 'uint32_t'

    def _to_public(self):
        return metadata.Clock(self.name, self.uuid, self.description, self.freq,
                              self.error_cycles, self.offset_seconds,
                              self.offset_cycles, self.absolute,
                              self.return_ctype)


class _Event(_PseudoObj):
    def __init__(self):
        super().__init__()
        self.id = None
        self.name = None
        self.log_level = None
        self.payload_type = None
        self.context_type = None

    def _to_public(self):
        return metadata.Event(self.id, self.name, self.log_level,
                              _opt_to_public(self.payload_type),
                              _opt_to_public(self.context_type))


class _Stream(_PseudoObj):
    def __init__(self):
        super().__init__()
        self.id = None
        self.name = None
        self.packet_context_type = None
        self.event_header_type = None
        self.event_context_type = None
        self.events = collections.OrderedDict()

    def is_event_empty(self, event):
        total_fields = 0

        if self.event_header_type is not None:
            total_fields += len(self.event_header_type.fields)

        if self.event_context_type is not None:
            total_fields += len(self.event_context_type.fields)

        if event.context_type is not None:
            total_fields += len(event.context_type.fields)

        if event.payload_type is not None:
            total_fields += len(event.payload_type.fields)

        return total_fields == 0

    def _to_public(self):
        events = []

        for name, pseudo_ev in self.events.items():
            events.append((name, pseudo_ev.to_public()))

        return metadata.Stream(self.id, self.name,
                               _opt_to_public(self.packet_context_type),
                               _opt_to_public(self.event_header_type),
                               _opt_to_public(self.event_context_type),
                               collections.OrderedDict(events))


class _Metadata(_PseudoObj):
    def __init__(self):
        super().__init__()
        self.trace = None
        self.env = None
        self.clocks = None
        self.streams = None
        self.default_stream_name = None

    def _to_public(self):
        clocks = []

        for name, pseudo_clock in self.clocks.items():
            clocks.append((name, pseudo_clock.to_public()))

        streams = []

        for name, pseudo_stream in self.streams.items():
            streams.append((name, pseudo_stream.to_public()))

        return metadata.Metadata(self.trace.to_public(), self.env,
                                 collections.OrderedDict(clocks),
                                 collections.OrderedDict(streams),
                                 self.default_stream_name)


# This JSON schema reference resolver only serves to detect when it
# needs to resolve a remote URI.
#
# This must never happen in barectf because all our schemas are local;
# it would mean a programming or schema error.
class _RefResolver(jsonschema.RefResolver):
    def resolve_remote(self, uri):
        # this must never happen: all our schemas are local
        raise RuntimeError('Missing local schema with URI "{}"'.format(uri))


# Schema validator which considers all the schemas found in the barectf
# package's `schemas` directory.
#
# The only public method is validate() which accepts an instance to
# validate as well as a schema short ID.
class _SchemaValidator:
    def __init__(self):
        subdirs = ['config', os.path.join('2', 'config')]
        schemas_dir = pkg_resources.resource_filename(__name__, 'schemas')
        self._store = {}

        for subdir in subdirs:
            dir = os.path.join(schemas_dir, subdir)

            for file_name in os.listdir(dir):
                if not file_name.endswith('.yaml'):
                    continue

                with open(os.path.join(dir, file_name)) as f:
                    schema = yaml.load(f, Loader=yaml.SafeLoader)

                assert '$id' in schema
                schema_id = schema['$id']
                assert schema_id not in self._store
                self._store[schema_id] = schema

    @staticmethod
    def _dict_from_ordered_dict(o_dict):
        dct = {}

        for k, v in o_dict.items():
            new_v = v

            if type(v) is collections.OrderedDict:
                new_v = _SchemaValidator._dict_from_ordered_dict(v)

            dct[k] = new_v

        return dct

    def _validate(self, instance, schema_short_id):
        # retrieve full schema ID from short ID
        schema_id = 'https://barectf.org/schemas/{}.json'.format(schema_short_id)
        assert schema_id in self._store

        # retrieve full schema
        schema = self._store[schema_id]

        # Create a reference resolver for this schema using this
        # validator's schema store.
        resolver = _RefResolver(base_uri=schema_id, referrer=schema,
                                store=self._store)

        # create a JSON schema validator using this reference resolver
        validator = jsonschema.Draft7Validator(schema, resolver=resolver)

        # Validate the instance, converting its
        # `collections.OrderedDict` objects to `dict` objects so as to
        # make any error message easier to read (because
        # validator.validate() below uses str() for error messages, and
        # collections.OrderedDict.__str__() is bulky).
        validator.validate(self._dict_from_ordered_dict(instance))

    # Validates `instance` using the schema having the short ID
    # `schema_short_id`.
    #
    # A schema short ID is the part between `schemas/` and `.json` in
    # its URI.
    #
    # Raises a `ConfigParseError` object, hiding any `jsonschema`
    # exception, on validation failure.
    def validate(self, instance, schema_short_id):
        try:
            self._validate(instance, schema_short_id)
        except jsonschema.ValidationError as exc:
            # convert to barectf `ConfigParseError` exception
            contexts = ['Configuration object']
            contexts += ['"{}" property'.format(p) for p in exc.absolute_path]
            schema_ctx = ''

            if len(exc.context) > 0:
                msgs = '; '.join([e.message for e in exc.context])
                schema_ctx = ': {}'.format(msgs)

            new_exc = ConfigParseError(contexts.pop(),
                                       '{}{} (from schema "{}")'.format(exc.message,
                                                                        schema_ctx,
                                                                        schema_short_id))

            for ctx in reversed(contexts):
                new_exc.append_ctx(ctx)

            raise new_exc


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


def _validate_identifier(iden, ctx_obj_name, prop):
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
        fmt = 'Invalid {} (not a valid identifier): "{}"'
        raise ConfigParseError(ctx_obj_name, fmt.format(prop, iden))


def _validate_alignment(align, ctx_obj_name):
    assert align >= 1

    if (align & (align - 1)) != 0:
        raise ConfigParseError(ctx_obj_name,
                               'Invalid alignment: {}'.format(align))


def _append_error_ctx(exc, obj_name, msg=None):
    exc.append_ctx(obj_name, msg)
    raise


# Entities.
#
# Order of values is important here.
@enum.unique
class _Entity(enum.IntEnum):
    TRACE_PACKET_HEADER = 0
    STREAM_PACKET_CONTEXT = 1
    STREAM_EVENT_HEADER = 2
    STREAM_EVENT_CONTEXT = 3
    EVENT_CONTEXT = 4
    EVENT_PAYLOAD = 5


# This validator validates the configured metadata for barectf specific
# needs.
#
# barectf needs:
#
# * All header/contexts are at least byte-aligned.
# * No nested structures or arrays.
class _BarectfMetadataValidator:
    def __init__(self):
        self._type_to_validate_type_func = {
            _Struct: self._validate_struct_type,
            _Array: self._validate_array_type,
        }

    def _validate_struct_type(self, t, entity_root):
        if not entity_root:
            raise ConfigParseError('Structure type',
                                   'Inner structure types are not supported as of this version')

        for field_name, field_type in t.fields.items():
            if entity_root and self._cur_entity is _Entity.TRACE_PACKET_HEADER:
                if field_name == 'uuid':
                    # allow
                    continue

            try:
                self._validate_type(field_type, False)
            except ConfigParseError as exc:
                _append_error_ctx(exc, 'Structure type\'s field "{}"'.format(field_name))

    def _validate_array_type(self, t, entity_root):
        raise ConfigParseError('Array type', 'Not supported as of this version')

    def _validate_type(self, t, entity_root):
        func = self._type_to_validate_type_func.get(type(t))

        if func is not None:
            func(t, entity_root)

    def _validate_entity(self, t):
        if t is None:
            return

        # make sure entity is byte-aligned
        if t.real_align < 8:
            raise ConfigParseError('Root type',
                                   'Alignment must be at least 8')

        assert type(t) is _Struct

        # validate types
        self._validate_type(t, True)

    def _validate_entities_and_names(self, meta):
        self._cur_entity = _Entity.TRACE_PACKET_HEADER

        try:
            self._validate_entity(meta.trace.packet_header_type)
        except ConfigParseError as exc:
            _append_error_ctx(exc, 'Trace', 'Invalid packet header type')

        for stream_name, stream in meta.streams.items():
            _validate_identifier(stream_name, 'Trace', 'stream name')
            self._cur_entity = _Entity.STREAM_PACKET_CONTEXT

            try:
                self._validate_entity(stream.packet_context_type)
            except ConfigParseError as exc:
                _append_error_ctx(exc, 'Stream "{}"'.format(stream_name),
                                  'Invalid packet context type')

            self._cur_entity = _Entity.STREAM_EVENT_HEADER

            try:
                self._validate_entity(stream.event_header_type)
            except ConfigParseError as exc:
                _append_error_ctx(exc, 'Stream "{}"'.format(stream_name),
                                  'Invalid event header type')

            self._cur_entity = _Entity.STREAM_EVENT_CONTEXT

            try:
                self._validate_entity(stream.event_context_type)
            except ConfigParseError as exc:
                _append_error_ctx(exc, 'Stream "{}"'.format(stream_name),
                                  'Invalid event context type'.format(stream_name))

            try:
                for ev_name, ev in stream.events.items():
                    _validate_identifier(ev_name,
                                         'Stream "{}"'.format(stream_name),
                                         'event name')

                    self._cur_entity = _Entity.EVENT_CONTEXT

                    try:
                        self._validate_entity(ev.context_type)
                    except ConfigParseError as exc:
                        _append_error_ctx(exc, 'Event "{}"'.format(ev_name),
                                          'Invalid context type')

                    self._cur_entity = _Entity.EVENT_PAYLOAD

                    try:
                        self._validate_entity(ev.payload_type)
                    except ConfigParseError as exc:
                        _append_error_ctx(exc, 'Event "{}"'.format(ev_name),
                                          'Invalid payload type')

                    if stream.is_event_empty(ev):
                        raise ConfigParseError('Event "{}"'.format(ev_name), 'Empty')
            except ConfigParseError as exc:
                _append_error_ctx(exc, 'Stream "{}"'.format(stream_name))

    def _validate_default_stream(self, meta):
        if meta.default_stream_name:
            if meta.default_stream_name not in meta.streams.keys():
                fmt = 'Default stream name ("{}") does not exist'
                raise ConfigParseError('barectf metadata',
                                       fmt.format(meta.default_stream_name))

    def validate(self, meta):
        self._validate_entities_and_names(meta)
        self._validate_default_stream(meta)


# This validator validates special fields of trace, stream, and event
# types.
#
# For example, it checks that the "stream_id" field exists in the trace
# packet header if there's more than one stream, and much more.
class _MetadataSpecialFieldsValidator:
    def _validate_trace_packet_header_type(self, t):
        # needs "stream_id" field?
        if len(self._meta.streams) > 1:
            # yes
            if t is None:
                raise ConfigParseError('"packet-header-type" property',
                                       'Need "stream_id" field (more than one stream), but trace packet header type is missing')

            if type(t) is not _Struct:
                raise ConfigParseError('"packet-header-type" property',
                                       'Need "stream_id" field (more than one stream), but trace packet header type is not a structure type')

            if 'stream_id' not in t.fields:
                raise ConfigParseError('"packet-header-type" property',
                                       'Need "stream_id" field (more than one stream)')

        # validate "magic" and "stream_id" types
        if type(t) is not _Struct:
            return

        for i, (field_name, field_type) in enumerate(t.fields.items()):
            if field_name == 'magic':
                if type(field_type) is not _Integer:
                    raise ConfigParseError('"packet-header-type" property',
                                           '"magic" field must be an integer type')

                if field_type.signed or field_type.size != 32:
                    raise ConfigParseError('"packet-header-type" property',
                                           '"magic" field must be a 32-bit unsigned integer type')

                if i != 0:
                    raise ConfigParseError('"packet-header-type" property',
                                           '"magic" field must be the first trace packet header type\'s field')
            elif field_name == 'stream_id':
                if type(field_type) is not _Integer:
                    raise ConfigParseError('"packet-header-type" property',
                                           '"stream_id" field must be an integer type')

                if field_type.signed:
                    raise ConfigParseError('"packet-header-type" property',
                                           '"stream_id" field must be an unsigned integer type')

                # "id" size can fit all event IDs
                if len(self._meta.streams) > (1 << field_type.size):
                    raise ConfigParseError('"packet-header-type" property',
                                           '"stream_id" field\' size is too small for the number of trace streams')
            elif field_name == 'uuid':
                if self._meta.trace.uuid is None:
                    raise ConfigParseError('"packet-header-type" property',
                                           '"uuid" field specified, but no trace UUID provided')

                if type(field_type) is not _Array:
                    raise ConfigParseError('"packet-header-type" property',
                                           '"uuid" field must be an array')

                if field_type.length != 16:
                    raise ConfigParseError('"packet-header-type" property',
                                           '"uuid" field must be an array of 16 bytes')

                element_type = field_type.element_type

                if type(element_type) is not _Integer:
                    raise ConfigParseError('"packet-header-type" property',
                                           '"uuid" field must be an array of 16 unsigned bytes')

                if element_type.size != 8:
                    raise ConfigParseError('"packet-header-type" property',
                                           '"uuid" field must be an array of 16 unsigned bytes')

                if element_type.signed:
                    raise ConfigParseError('"packet-header-type" property',
                                           '"uuid" field must be an array of 16 unsigned bytes')

                if element_type.real_align != 8:
                    raise ConfigParseError('"packet-header-type" property',
                                           '"uuid" field must be an array of 16 unsigned, byte-aligned bytes')

    def _validate_trace(self, meta):
        self._validate_trace_packet_header_type(meta.trace.packet_header_type)

    def _validate_stream_packet_context(self, stream):
        t = stream.packet_context_type

        if type(t) is None:
            raise ConfigParseError('Stream',
                                   'Missing "packet-context-type" property')

        if type(t) is not _Struct:
            raise ConfigParseError('"packet-context-type" property',
                                   'Expecting a structure type')

        # "timestamp_begin", if exists, is an unsigned integer type,
        # mapped to a clock
        ts_begin = None

        if 'timestamp_begin' in t.fields:
            ts_begin = t.fields['timestamp_begin']

            if type(ts_begin) is not _Integer:
                raise ConfigParseError('"packet-context-type" property',
                                       '"timestamp_begin" field must be an integer type')

            if ts_begin.signed:
                raise ConfigParseError('"packet-context-type" property',
                                       '"timestamp_begin" field must be an unsigned integer type')

            if not ts_begin.property_mappings:
                raise ConfigParseError('"packet-context-type" property',
                                       '"timestamp_begin" field must be mapped to a clock')

        # "timestamp_end", if exists, is an unsigned integer type,
        # mapped to a clock
        ts_end = None

        if 'timestamp_end' in t.fields:
            ts_end = t.fields['timestamp_end']

            if type(ts_end) is not _Integer:
                raise ConfigParseError('"packet-context-type" property',
                                       '"timestamp_end" field must be an integer type')

            if ts_end.signed:
                raise ConfigParseError('"packet-context-type" property',
                                       '"timestamp_end" field must be an unsigned integer type')

            if not ts_end.property_mappings:
                raise ConfigParseError('"packet-context-type" property',
                                       '"timestamp_end" field must be mapped to a clock')

        # "timestamp_begin" and "timestamp_end" exist together
        if (('timestamp_begin' in t.fields) ^ ('timestamp_end' in t.fields)):
            raise ConfigParseError('"timestamp_begin" and "timestamp_end" fields must be defined together in stream packet context type')

        # "timestamp_begin" and "timestamp_end" are mapped to the same clock
        if ts_begin is not None and ts_end is not None:
            if ts_begin.property_mappings[0].object.name != ts_end.property_mappings[0].object.name:
                raise ConfigParseError('"timestamp_begin" and "timestamp_end" fields must be mapped to the same clock object in stream packet context type')

        # "events_discarded", if exists, is an unsigned integer type
        if 'events_discarded' in t.fields:
            events_discarded = t.fields['events_discarded']

            if type(events_discarded) is not _Integer:
                raise ConfigParseError('"packet-context-type" property',
                                       '"events_discarded" field must be an integer type')

            if events_discarded.signed:
                raise ConfigParseError('"packet-context-type" property',
                                       '"events_discarded" field must be an unsigned integer type')

        # "packet_size" and "content_size" must exist
        if 'packet_size' not in t.fields:
            raise ConfigParseError('"packet-context-type" property',
                                   'Missing "packet_size" field in stream packet context type')

        packet_size = t.fields['packet_size']

        # "content_size" and "content_size" must exist
        if 'content_size' not in t.fields:
            raise ConfigParseError('"packet-context-type" property',
                                   'Missing "content_size" field in stream packet context type')

        content_size = t.fields['content_size']

        # "packet_size" is an unsigned integer type
        if type(packet_size) is not _Integer:
            raise ConfigParseError('"packet-context-type" property',
                                   '"packet_size" field in stream packet context type must be an integer type')

        if packet_size.signed:
            raise ConfigParseError('"packet-context-type" property',
                                   '"packet_size" field in stream packet context type must be an unsigned integer type')

        # "content_size" is an unsigned integer type
        if type(content_size) is not _Integer:
            raise ConfigParseError('"packet-context-type" property',
                                   '"content_size" field in stream packet context type must be an integer type')

        if content_size.signed:
            raise ConfigParseError('"packet-context-type" property',
                                   '"content_size" field in stream packet context type must be an unsigned integer type')

        # "packet_size" size should be greater than or equal to "content_size" size
        if content_size.size > packet_size.size:
            raise ConfigParseError('"packet-context-type" property',
                                   '"content_size" field size must be lesser than or equal to "packet_size" field size')

    def _validate_stream_event_header(self, stream):
        t = stream.event_header_type

        # needs "id" field?
        if len(stream.events) > 1:
            # yes
            if t is None:
                raise ConfigParseError('"event-header-type" property',
                                       'Need "id" field (more than one event), but stream event header type is missing')

            if type(t) is not _Struct:
                raise ConfigParseError('"event-header-type" property',
                                       'Need "id" field (more than one event), but stream event header type is not a structure type')

            if 'id' not in t.fields:
                raise ConfigParseError('"event-header-type" property',
                                       'Need "id" field (more than one event)')

        # validate "id" and "timestamp" types
        if type(t) is not _Struct:
            return

        # "timestamp", if exists, is an unsigned integer type,
        # mapped to a clock
        if 'timestamp' in t.fields:
            ts = t.fields['timestamp']

            if type(ts) is not _Integer:
                raise ConfigParseError('"event-header-type" property',
                                       '"timestamp" field must be an integer type')

            if ts.signed:
                raise ConfigParseError('"event-header-type" property',
                                       '"timestamp" field must be an unsigned integer type')

            if not ts.property_mappings:
                raise ConfigParseError('"event-header-type" property',
                                       '"timestamp" field must be mapped to a clock')

        if 'id' in t.fields:
            eid = t.fields['id']

            # "id" is an unsigned integer type
            if type(eid) is not _Integer:
                raise ConfigParseError('"event-header-type" property',
                                       '"id" field must be an integer type')

            if eid.signed:
                raise ConfigParseError('"event-header-type" property',
                                       '"id" field must be an unsigned integer type')

            # "id" size can fit all event IDs
            if len(stream.events) > (1 << eid.size):
                raise ConfigParseError('"event-header-type" property',
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
            except ConfigParseError as exc:
                _append_error_ctx(exc, 'Stream "{}"'.format(stream.name), 'Invalid')


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
        self._include_dirs = include_dirs
        self._ignore_include_not_found = ignore_include_not_found
        self._dump_config = dump_config
        self._schema_validator = _SchemaValidator()

    def _set_byte_order(self, metadata_node):
        self._bo = _byte_order_str_to_bo(metadata_node['trace']['byte-order'])
        assert self._bo is not None

    def _set_int_clock_prop_mapping(self, int_obj, prop_mapping_node):
        clock_name = prop_mapping_node['name']
        clock = self._clocks.get(clock_name)

        if clock is None:
            raise ConfigParseError('Integer type\'s clock property mapping',
                                   'Invalid clock name "{}"'.format(clock_name))

        prop_mapping = _PropertyMapping()
        prop_mapping.object = clock
        prop_mapping.prop = 'value'
        int_obj.property_mappings.append(prop_mapping)

    def _create_integer(self, node):
        obj = _Integer()

        # size
        obj.size = node['size']

        # align
        align_node = node.get('align')

        if align_node is not None:
            _validate_alignment(align_node, 'Integer type')
            obj.align = align_node

        # signed
        signed_node = node.get('signed')

        if signed_node is not None:
            obj.signed = signed_node

        # byte order
        obj.byte_order = self._bo
        bo_node = node.get('byte-order')

        if bo_node is not None:
            obj.byte_order = _byte_order_str_to_bo(bo_node)

        # base
        base_node = node.get('base')

        if base_node is not None:
            if base_node == 'bin':
                obj.base = 2
            elif base_node == 'oct':
                obj.base = 8
            elif base_node == 'dec':
                obj.base = 10
            else:
                assert base_node == 'hex'
                obj.base = 16

        # encoding
        encoding_node = node.get('encoding')

        if encoding_node is not None:
            obj.encoding = _encoding_str_to_encoding(encoding_node)

        # property mappings
        pm_node = node.get('property-mappings')

        if pm_node is not None:
            assert len(pm_node) == 1
            self._set_int_clock_prop_mapping(obj, pm_node[0])

        return obj

    def _create_float(self, node):
        obj = _FloatingPoint()

        # size
        size_node = node['size']
        obj.exp_size = size_node['exp']
        obj.mant_size = size_node['mant']

        # align
        align_node = node.get('align')

        if align_node is not None:
            _validate_alignment(align_node, 'Floating point number type')
            obj.align = align_node

        # byte order
        obj.byte_order = self._bo
        bo_node = node.get('byte-order')

        if bo_node is not None:
            obj.byte_order = _byte_order_str_to_bo(bo_node)

        return obj

    def _create_enum(self, node):
        obj = _Enum()

        # value type
        try:
            obj.value_type = self._create_type(node['value-type'])
        except ConfigParseError as exc:
            _append_error_ctx(exc, 'Enumeration type',
                              'Cannot create integer type')

        # members
        members_node = node.get('members')

        if members_node is not None:
            if obj.value_type.signed:
                value_min = -(1 << obj.value_type.size - 1)
                value_max = (1 << (obj.value_type.size - 1)) - 1
            else:
                value_min = 0
                value_max = (1 << obj.value_type.size) - 1

            cur = 0

            for m_node in members_node:
                if type(m_node) is str:
                    label = m_node
                    value = (cur, cur)
                    cur += 1
                else:
                    assert type(m_node) is collections.OrderedDict
                    label = m_node['label']
                    value = m_node['value']

                    if type(value) is int:
                        cur = value + 1
                        value = (value, value)
                    else:
                        assert type(value) is list
                        assert len(value) == 2
                        mn = value[0]
                        mx = value[1]

                        if mn > mx:
                            raise ConfigParseError('Enumeration type',
                                                   'Invalid member ("{}"): invalid range ({} > {})'.format(label, mn, mx))

                        value = (mn, mx)
                        cur = mx + 1

                name_fmt = 'Enumeration type\'s member "{}"'
                msg_fmt = 'Value {} is outside the value type range [{}, {}]'

                if value[0] < value_min or value[0] > value_max:
                    raise ConfigParseError(name_fmt.format(label),
                                           msg_fmt.format(value[0],
                                                          value_min,
                                                          value_max))

                if value[1] < value_min or value[1] > value_max:
                    raise ConfigParseError(name_fmt.format(label),
                                           msg_fmt.format(value[0],
                                                          value_min,
                                                          value_max))

                obj.members[label] = value

        return obj

    def _create_string(self, node):
        obj = _String()

        # encoding
        encoding_node = node.get('encoding')

        if encoding_node is not None:
            obj.encoding = _encoding_str_to_encoding(encoding_node)

        return obj

    def _create_struct(self, node):
        obj = _Struct()

        # minimum alignment
        min_align_node = node.get('min-align')

        if min_align_node is not None:
            _validate_alignment(min_align_node, 'Structure type')
            obj.min_align = min_align_node

        # fields
        fields_node = node.get('fields')

        if fields_node is not None:
            for field_name, field_node in fields_node.items():
                _validate_identifier(field_name, 'Structure type', 'field name')

                try:
                    obj.fields[field_name] = self._create_type(field_node)
                except ConfigParseError as exc:
                    _append_error_ctx(exc, 'Structure type',
                                      'Cannot create field "{}"'.format(field_name))

        return obj

    def _create_array(self, node):
        obj = _Array()

        # length
        obj.length = node['length']

        # element type
        try:
            obj.element_type = self._create_type(node['element-type'])
        except ConfigParseError as exc:
            _append_error_ctx(exc, 'Array type', 'Cannot create element type')

        return obj

    def _create_type(self, type_node):
        return self._class_name_to_create_type_func[type_node['class']](type_node)

    def _create_clock(self, node):
        # create clock object
        clock = _Clock()

        # UUID
        uuid_node = node.get('uuid')

        if uuid_node is not None:
            try:
                clock.uuid = uuid.UUID(uuid_node)
            except:
                raise ConfigParseError('Clock', 'Malformed UUID: "{}"'.format(uuid_node))

        # description
        descr_node = node.get('description')

        if descr_node is not None:
            clock.description = descr_node

        # frequency
        freq_node = node.get('freq')

        if freq_node is not None:
            clock.freq = freq_node

        # error cycles
        error_cycles_node = node.get('error-cycles')

        if error_cycles_node is not None:
            clock.error_cycles = error_cycles_node

        # offset
        offset_node = node.get('offset')

        if offset_node is not None:
            # cycles
            offset_cycles_node = offset_node.get('cycles')

            if offset_cycles_node is not None:
                clock.offset_cycles = offset_cycles_node

            # seconds
            offset_seconds_node = offset_node.get('seconds')

            if offset_seconds_node is not None:
                clock.offset_seconds = offset_seconds_node

        # absolute
        absolute_node = node.get('absolute')

        if absolute_node is not None:
            clock.absolute = absolute_node

        return_ctype_node = node.get('$return-ctype')

        if return_ctype_node is None:
            return_ctype_node = node.get('return-ctype')

        if return_ctype_node is not None:
            clock.return_ctype = return_ctype_node

        return clock

    def _register_clocks(self, metadata_node):
        self._clocks = collections.OrderedDict()
        clocks_node = metadata_node.get('clocks')

        if clocks_node is None:
            return

        for clock_name, clock_node in clocks_node.items():
            _validate_identifier(clock_name, 'Metadata', 'clock name')
            assert clock_name not in self._clocks

            try:
                clock = self._create_clock(clock_node)
            except ConfigParseError as exc:
                _append_error_ctx(exc, 'Metadata',
                                  'Cannot create clock "{}"'.format(clock_name))

            clock.name = clock_name
            self._clocks[clock_name] = clock

    def _create_env(self, metadata_node):
        env_node = metadata_node.get('env')

        if env_node is None:
            return collections.OrderedDict()

        for env_name, env_value in env_node.items():
            _validate_identifier(env_name, 'Metadata',
                                 'environment variable name')

        return copy.deepcopy(env_node)

    def _create_trace(self, metadata_node):
        # create trace object
        trace = _Trace()

        trace_node = metadata_node['trace']

        # set byte order (already parsed)
        trace.byte_order = self._bo

        # UUID
        uuid_node = trace_node.get('uuid')

        if uuid_node is not None:
            if uuid_node == 'auto':
                trace.uuid = uuid.uuid1()
            else:
                try:
                    trace.uuid = uuid.UUID(uuid_node)
                except:
                    raise ConfigParseError('Trace',
                                           'Malformed UUID: "{}"'.format(uuid_node))

        # packet header type
        pht_node = trace_node.get('packet-header-type')

        if pht_node is not None:
            try:
                trace.packet_header_type = self._create_type(pht_node)
            except ConfigParseError as exc:
                _append_error_ctx(exc, 'Trace',
                                  'Cannot create packet header type')

        return trace

    def _create_event(self, event_node):
        # create event object
        event = _Event()

        log_level_node = event_node.get('log-level')

        if log_level_node is not None:
            assert type(log_level_node) is int
            event.log_level = metadata.LogLevel(None, log_level_node)

        ct_node = event_node.get('context-type')

        if ct_node is not None:
            try:
                event.context_type = self._create_type(ct_node)
            except ConfigParseError as exc:
                _append_error_ctx(exc, 'Event',
                                  'Cannot create context type object')

        pt_node = event_node.get('payload-type')

        if pt_node is not None:
            try:
                event.payload_type = self._create_type(pt_node)
            except ConfigParseError as exc:
                _append_error_ctx(exc, 'Event',
                                  'Cannot create payload type object')

        return event

    def _create_stream(self, stream_name, stream_node):
        # create stream object
        stream = _Stream()

        pct_node = stream_node.get('packet-context-type')

        if pct_node is not None:
            try:
                stream.packet_context_type = self._create_type(pct_node)
            except ConfigParseError as exc:
                _append_error_ctx(exc, 'Stream',
                                  'Cannot create packet context type object')

        eht_node = stream_node.get('event-header-type')

        if eht_node is not None:
            try:
                stream.event_header_type = self._create_type(eht_node)
            except ConfigParseError as exc:
                _append_error_ctx(exc, 'Stream',
                                  'Cannot create event header type object')

        ect_node = stream_node.get('event-context-type')

        if ect_node is not None:
            try:
                stream.event_context_type = self._create_type(ect_node)
            except ConfigParseError as exc:
                _append_error_ctx(exc, 'Stream',
                                  'Cannot create event context type object')

        events_node = stream_node['events']
        cur_id = 0

        for ev_name, ev_node in events_node.items():
            try:
                ev = self._create_event(ev_node)
            except ConfigParseError as exc:
                _append_error_ctx(exc, 'Stream',
                                  'Cannot create event "{}"'.format(ev_name))

            ev.id = cur_id
            ev.name = ev_name
            stream.events[ev_name] = ev
            cur_id += 1

        default_node = stream_node.get('$default')

        if default_node is not None:
            if self._meta.default_stream_name is not None and self._meta.default_stream_name != stream_name:
                fmt = 'Cannot specify more than one default stream (default stream already set to "{}")'
                raise ConfigParseError('Stream',
                                       fmt.format(self._meta.default_stream_name))

            self._meta.default_stream_name = stream_name

        return stream

    def _create_streams(self, metadata_node):
        streams = collections.OrderedDict()
        streams_node = metadata_node['streams']
        cur_id = 0

        for stream_name, stream_node in streams_node.items():
            try:
                stream = self._create_stream(stream_name, stream_node)
            except ConfigParseError as exc:
                _append_error_ctx(exc, 'Metadata',
                                  'Cannot create stream "{}"'.format(stream_name))

            stream.id = cur_id
            stream.name = stream_name
            streams[stream_name] = stream
            cur_id += 1

        return streams

    def _create_metadata(self, root):
        self._meta = _Metadata()
        metadata_node = root['metadata']

        if '$default-stream' in metadata_node and metadata_node['$default-stream'] is not None:
            default_stream_node = metadata_node['$default-stream']
            self._meta.default_stream_name = default_stream_node

        self._set_byte_order(metadata_node)
        self._register_clocks(metadata_node)
        self._meta.clocks = self._clocks
        self._meta.env = self._create_env(metadata_node)
        self._meta.trace = self._create_trace(metadata_node)
        self._meta.streams = self._create_streams(metadata_node)

        # validate metadata
        try:
            _MetadataSpecialFieldsValidator().validate(self._meta)
        except ConfigParseError as exc:
            _append_error_ctx(exc, 'Metadata')

        try:
            _BarectfMetadataValidator().validate(self._meta)
        except ConfigParseError as exc:
            _append_error_ctx(exc, 'barectf metadata')

        return self._meta

    def _get_prefix(self, config_node):
        prefix = config_node.get('prefix', 'barectf_')
        _validate_identifier(prefix, '"prefix" property', 'prefix')
        return prefix

    def _get_options(self, config_node):
        gen_prefix_def = False
        gen_default_stream_def = False
        options_node = config_node.get('options')

        if options_node is not None:
            gen_prefix_def = options_node.get('gen-prefix-def',
                                              gen_prefix_def)
            gen_default_stream_def = options_node.get('gen-default-stream-def',
                                                      gen_default_stream_def)

        return config.ConfigOptions(gen_prefix_def, gen_default_stream_def)

    def _get_last_include_file(self):
        if self._include_stack:
            return self._include_stack[-1]

        return self._root_yaml_path

    def _load_include(self, yaml_path):
        for inc_dir in self._include_dirs:
            # Current inclusion dir + file name path.
            #
            # Note: os.path.join() only takes the last argument if it's
            # absolute.
            inc_path = os.path.join(inc_dir, yaml_path)

            # real path (symbolic links resolved)
            real_path = os.path.realpath(inc_path)

            # normalized path (weird stuff removed!)
            norm_path = os.path.normpath(real_path)

            if not os.path.isfile(norm_path):
                # file doesn't exist: skip
                continue

            if norm_path in self._include_stack:
                base_path = self._get_last_include_file()
                raise ConfigParseError('In "{}"',
                                       'Cannot recursively include file "{}"'.format(base_path,
                                                                                     norm_path))

            self._include_stack.append(norm_path)

            # load raw content
            return self._yaml_ordered_load(norm_path)

        if not self._ignore_include_not_found:
            base_path = self._get_last_include_file()
            raise ConfigParseError('In "{}"',
                                   'Cannot include file "{}": file not found in include directories'.format(base_path,
                                                                                                            yaml_path))

    def _get_include_paths(self, include_node):
        if include_node is None:
            # none
            return []

        if type(include_node) is str:
            # wrap as array
            return [include_node]

        # already an array
        assert type(include_node) is list
        return include_node

    def _update_node(self, base_node, overlay_node):
        for olay_key, olay_value in overlay_node.items():
            if olay_key in base_node:
                base_value = base_node[olay_key]

                if type(olay_value) is collections.OrderedDict and type(base_value) is collections.OrderedDict:
                    # merge dictionaries
                    self._update_node(base_value, olay_value)
                elif type(olay_value) is list and type(base_value) is list:
                    # append extension array items to base items
                    base_value += olay_value
                else:
                    # fall back to replacing
                    base_node[olay_key] = olay_value
            else:
                base_node[olay_key] = olay_value

    def _process_node_include(self, last_overlay_node,
                              process_base_include_cb,
                              process_children_include_cb=None):
        # process children inclusions first
        if process_children_include_cb is not None:
            process_children_include_cb(last_overlay_node)

        incl_prop_name = '$include'

        if incl_prop_name in last_overlay_node:
            include_node = last_overlay_node[incl_prop_name]
        else:
            # no inclusions!
            return last_overlay_node

        include_paths = self._get_include_paths(include_node)
        cur_base_path = self._get_last_include_file()
        base_node = None

        # keep the inclusion paths and remove the `$include` property
        include_paths = copy.deepcopy(include_paths)
        del last_overlay_node[incl_prop_name]

        for include_path in include_paths:
            # load raw YAML from included file
            overlay_node = self._load_include(include_path)

            if overlay_node is None:
                # Cannot find inclusion file, but we're ignoring those
                # errors, otherwise _load_include() itself raises a
                # config error.
                continue

            # recursively process inclusions
            try:
                overlay_node = process_base_include_cb(overlay_node)
            except ConfigParseError as exc:
                _append_error_ctx(exc, 'In "{}"'.format(cur_base_path))

            # pop inclusion stack now that we're done including
            del self._include_stack[-1]

            # At this point, `base_node` is fully resolved (does not
            # contain any `$include` property).
            if base_node is None:
                base_node = overlay_node
            else:
                self._update_node(base_node, overlay_node)

        # Finally, update the latest base node with our last overlay
        # node.
        if base_node is None:
            # Nothing was included, which is possible when we're
            # ignoring inclusion errors.
            return last_overlay_node

        self._update_node(base_node, last_overlay_node)
        return base_node

    def _process_event_include(self, event_node):
        # Make sure the event object is valid for the inclusion
        # processing stage.
        self._schema_validator.validate(event_node,
                                        '2/config/event-pre-include')

        # process inclusions
        return self._process_node_include(event_node,
                                          self._process_event_include)

    def _process_stream_include(self, stream_node):
        def process_children_include(stream_node):
            if 'events' in stream_node:
                events_node = stream_node['events']

                for key in list(events_node):
                    events_node[key] = self._process_event_include(events_node[key])

        # Make sure the stream object is valid for the inclusion
        # processing stage.
        self._schema_validator.validate(stream_node,
                                        '2/config/stream-pre-include')

        # process inclusions
        return self._process_node_include(stream_node,
                                          self._process_stream_include,
                                          process_children_include)

    def _process_trace_include(self, trace_node):
        # Make sure the trace object is valid for the inclusion
        # processing stage.
        self._schema_validator.validate(trace_node,
                                        '2/config/trace-pre-include')

        # process inclusions
        return self._process_node_include(trace_node,
                                          self._process_trace_include)

    def _process_clock_include(self, clock_node):
        # Make sure the clock object is valid for the inclusion
        # processing stage.
        self._schema_validator.validate(clock_node,
                                        '2/config/clock-pre-include')

        # process inclusions
        return self._process_node_include(clock_node,
                                          self._process_clock_include)

    def _process_metadata_include(self, metadata_node):
        def process_children_include(metadata_node):
            if 'trace' in metadata_node:
                metadata_node['trace'] = self._process_trace_include(metadata_node['trace'])

            if 'clocks' in metadata_node:
                clocks_node = metadata_node['clocks']

                for key in list(clocks_node):
                    clocks_node[key] = self._process_clock_include(clocks_node[key])

            if 'streams' in metadata_node:
                streams_node = metadata_node['streams']

                for key in list(streams_node):
                    streams_node[key] = self._process_stream_include(streams_node[key])

        # Make sure the metadata object is valid for the inclusion
        # processing stage.
        self._schema_validator.validate(metadata_node,
                                        '2/config/metadata-pre-include')

        # process inclusions
        return self._process_node_include(metadata_node,
                                          self._process_metadata_include,
                                          process_children_include)

    def _process_config_includes(self, config_node):
        # Process inclusions in this order:
        #
        # 1. Clock object, event objects, and trace objects (the order
        #    between those is not important).
        #
        # 2. Stream objects.
        #
        # 3. Metadata object.
        #
        # This is because:
        #
        # * A metadata object can include clock objects, a trace object,
        #   stream objects, and event objects (indirectly).
        #
        # * A stream object can include event objects.
        #
        # We keep a stack of absolute paths to included files
        # (`self._include_stack`) to detect recursion.
        #
        # First, make sure the configuration object itself is valid for
        # the inclusion processing stage.
        self._schema_validator.validate(config_node,
                                        '2/config/config-pre-include')

        # Process metadata object inclusions.
        #
        # self._process_metadata_include() returns a new (or the same)
        # metadata object without any `$include` property in it,
        # recursively.
        config_node['metadata'] = self._process_metadata_include(config_node['metadata'])

        return config_node

    def _expand_field_type_aliases(self, metadata_node, type_aliases_node):
        def resolve_field_type_aliases(parent_node, key, from_descr,
                                       alias_set=None):
            if key not in parent_node:
                return

            # This set holds all the aliases we need to expand,
            # recursively. This is used to detect cycles.
            if alias_set is None:
                alias_set = set()

            node = parent_node[key]

            if node is None:
                return

            if type(node) is str:
                alias = node

                if alias not in resolved_aliases:
                    # Only check for a field type alias cycle when we
                    # didn't resolve the alias yet, as a given node can
                    # refer to the same field type alias more than once.
                    if alias in alias_set:
                        fmt = 'Cycle detected during the "{}" type alias resolution'
                        raise ConfigParseError(from_descr, fmt.format(alias))

                    # try to load field type alias node named `alias`
                    if alias not in type_aliases_node:
                        raise ConfigParseError(from_descr,
                                               'Type alias "{}" does not exist'.format(alias))

                    # resolve it
                    alias_set.add(alias)
                    resolve_field_type_aliases(type_aliases_node, alias,
                                               from_descr, alias_set)
                    resolved_aliases.add(alias)

                parent_node[key] = copy.deepcopy(type_aliases_node[node])
                return

            # traverse, resolving field type aliases as needed
            for pkey in ['$inherit', 'inherit', 'value-type', 'element-type']:
                resolve_field_type_aliases(node, pkey, from_descr, alias_set)

            # structure field type fields
            pkey = 'fields'

            if pkey in node:
                assert type(node[pkey]) is collections.OrderedDict

                for field_name in node[pkey]:
                    resolve_field_type_aliases(node[pkey], field_name,
                                               from_descr, alias_set)

        def resolve_field_type_aliases_from(parent_node, key, parent_node_type_name,
                                            parent_node_name=None):
            from_descr = '"{}" property of {}'.format(key,
                                                      parent_node_type_name)

            if parent_node_name is not None:
                from_descr += ' "{}"'.format(parent_node_name)

            resolve_field_type_aliases(parent_node, key, from_descr)

        # set of resolved field type aliases
        resolved_aliases = set()

        # expand field type aliases within trace, streams, and events now
        resolve_field_type_aliases_from(metadata_node['trace'],
                                        'packet-header-type', 'trace')

        for stream_name, stream in metadata_node['streams'].items():
            resolve_field_type_aliases_from(stream, 'packet-context-type',
                                            'stream', stream_name)
            resolve_field_type_aliases_from(stream, 'event-header-type',
                                            'stream', stream_name)
            resolve_field_type_aliases_from(stream, 'event-context-type',
                                            'stream', stream_name)

            try:
                for event_name, event in stream['events'].items():
                    resolve_field_type_aliases_from(event, 'context-type', 'event',
                                                    event_name)
                    resolve_field_type_aliases_from(event, 'payload-type', 'event',
                                                    event_name)
            except ConfigParseError as exc:
                _append_error_ctx(exc, 'Stream "{}"'.format(stream_name))

        # we don't need the `type-aliases` node anymore
        del metadata_node['type-aliases']

    def _expand_field_type_inheritance(self, metadata_node):
        def apply_inheritance(parent_node, key):
            if key not in parent_node:
                return

            node = parent_node[key]

            if node is None:
                return

            # process children first
            for pkey in ['$inherit', 'inherit', 'value-type', 'element-type']:
                apply_inheritance(node, pkey)

            # structure field type fields
            pkey = 'fields'

            if pkey in node:
                assert type(node[pkey]) is collections.OrderedDict

                for field_name, field_type in node[pkey].items():
                    apply_inheritance(node[pkey], field_name)

            # apply inheritance of this node
            if 'inherit' in node:
                # barectf 2.1: `inherit` property was renamed to `$inherit`
                assert '$inherit' not in node
                node['$inherit'] = node['inherit']
                del node['inherit']

            inherit_key = '$inherit'

            if inherit_key in node:
                assert type(node[inherit_key]) is collections.OrderedDict

                # apply inheritance below
                apply_inheritance(node, inherit_key)

                # `node` is an overlay on the `$inherit` node
                base_node = node[inherit_key]
                del node[inherit_key]
                self._update_node(base_node, node)

                # set updated base node as this node
                parent_node[key] = base_node

        apply_inheritance(metadata_node['trace'], 'packet-header-type')

        for stream in metadata_node['streams'].values():
            apply_inheritance(stream, 'packet-context-type')
            apply_inheritance(stream, 'event-header-type')
            apply_inheritance(stream, 'event-context-type')

            for event in stream['events'].values():
                apply_inheritance(event, 'context-type')
                apply_inheritance(event, 'payload-type')

    def _expand_field_types(self, metadata_node):
        type_aliases_node = metadata_node.get('type-aliases')

        if type_aliases_node is None:
            # If there's no `type-aliases` node, then there's no field
            # type aliases and therefore no possible inheritance.
            return

        # first, expand field type aliases
        self._expand_field_type_aliases(metadata_node, type_aliases_node)

        # next, apply inheritance to create effective field types
        self._expand_field_type_inheritance(metadata_node)

    def _expand_log_levels(self, metadata_node):
        if 'log-levels' in metadata_node:
            # barectf 2.1: `log-levels` property was renamed to `$log-levels`
            assert '$log-levels' not in node
            node['$log-levels'] = node['log-levels']
            del node['log-levels']

        log_levels_key = '$log-levels'
        log_levels_node = metadata_node.get(log_levels_key)

        if log_levels_node is None:
            # no log level aliases
            return

        # not needed anymore
        del metadata_node[log_levels_key]

        for stream_name, stream in metadata_node['streams'].items():
            try:
                for event_name, event in stream['events'].items():
                    prop_name = 'log-level'
                    ll_node = event.get(prop_name)

                    if ll_node is None:
                        continue

                    if type(ll_node) is str:
                        if ll_node not in log_levels_node:
                            raise ConfigParseError('Event "{}"'.format(event_name),
                                                   'Log level "{}" does not exist'.format(ll_node))

                        event[prop_name] = log_levels_node[ll_node]
            except ConfigParseError as exc:
                _append_error_ctx(exc, 'Stream "{}"'.format(stream_name))

    def _yaml_ordered_dump(self, node, **kwds):
        class ODumper(yaml.Dumper):
            pass

        def dict_representer(dumper, node):
            return dumper.represent_mapping(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                                            node.items())

        ODumper.add_representer(collections.OrderedDict, dict_representer)

        # Python -> YAML
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
            raise ConfigParseError('Configuration',
                                   'Cannot open file "{}"'.format(yaml_path))
        except ConfigParseError as exc:
            _append_error_ctx(exc, 'Configuration',
                                   'Unknown error while trying to load file "{}"'.format(yaml_path))

        # loaded node must be an associate array
        if type(node) is not collections.OrderedDict:
            raise ConfigParseError('Configuration',
                                   'Root of YAML file "{}" must be an associative array'.format(yaml_path))

        return node

    def _reset(self):
        self._version = None
        self._include_stack = []

    def parse(self, yaml_path):
        self._reset()
        self._root_yaml_path = yaml_path

        # load the configuration object as is from the root YAML file
        try:
            config_node = self._yaml_ordered_load(yaml_path)
        except ConfigParseError as exc:
            _append_error_ctx(exc, 'Configuration',
                                   'Cannot parse YAML file "{}"'.format(yaml_path))

        # Make sure the configuration object is minimally valid, that
        # is, it contains a valid `version` property.
        #
        # This step does not validate the whole configuration object
        # yet because we don't have an effective configuration object;
        # we still need to:
        #
        # * Process inclusions.
        # * Expand field types (inheritance and aliases).
        self._schema_validator.validate(config_node, 'config/config-min')

        # Process configuration object inclusions.
        #
        # self._process_config_includes() returns a new (or the same)
        # configuration object without any `$include` property in it,
        # recursively.
        config_node = self._process_config_includes(config_node)

        # Make sure that the current configuration object is valid
        # considering field types are not expanded yet.
        self._schema_validator.validate(config_node,
                                        '2/config/config-pre-field-type-expansion')

        # Expand field types.
        #
        # This process:
        #
        # 1. Replaces field type aliases with "effective" field
        #    types, recursively.
        #
        #    After this step, the `type-aliases` property of the
        #    `metadata` node is gone.
        #
        # 2. Applies inheritance following the `$inherit`/`inherit`
        #    properties.
        #
        #    After this step, field type objects do not contain
        #    `$inherit` or `inherit` properties.
        #
        # This is done blindly, in that the process _doesn't_ validate
        # field type objects at this point.
        self._expand_field_types(config_node['metadata'])

        # Make sure that the current configuration object is valid
        # considering log levels are not expanded yet.
        self._schema_validator.validate(config_node,
                                        '2/config/config-pre-log-level-expansion')

        # Expand log levels, that is, replace log level strings with
        # their equivalent numeric values.
        self._expand_log_levels(config_node['metadata'])

        # validate the whole, effective configuration object
        self._schema_validator.validate(config_node, '2/config/config')

        # dump config if required
        if self._dump_config:
            print(self._yaml_ordered_dump(config_node, indent=2,
                                          default_flow_style=False))

        # get prefix, options, and metadata pseudo-object
        prefix = self._get_prefix(config_node)
        opts = self._get_options(config_node)
        pseudo_meta = self._create_metadata(config_node)

        # create public configuration
        return config.Config(pseudo_meta.to_public(), prefix, opts)


def _from_file(path, include_dirs, ignore_include_not_found, dump_config):
    try:
        parser = _YamlConfigParser(include_dirs, ignore_include_not_found,
                                   dump_config)
        return parser.parse(path)
    except ConfigParseError as exc:
        _append_error_ctx(exc, 'Configuration',
                               'Cannot create configuration from YAML file "{}"'.format(path))
