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


# The context of a configuration parsing error.
#
# Such a context object has a name and, optionally, a message.
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


# Appends the context having the object name `obj_name` and the
# (optional) message `msg` to the `_ConfigParseError` exception `exc`
# and then raises `exc` again.
def _append_error_ctx(exc, obj_name, msg=None):
    exc.append_ctx(obj_name, msg)
    raise


# A configuration parsing error.
#
# Such an error object contains a list of contexts (`ctx` property).
#
# The first context of this list is the most specific context, while the
# last is the more general.
#
# Use append_ctx() to append a context to an existing configuration
# parsing error when you catch it before raising it again. You can use
# _append_error_ctx() to do exactly this in a single call.
class _ConfigParseError(RuntimeError):
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


# Pseudo object base class.
#
# A concrete pseudo object contains the same data as its public version,
# but it's mutable.
#
# The to_public() method converts the pseudo object to an equivalent
# public, immutable object, caching the result so as to always return
# the same Python object.
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
        raise RuntimeError('Missing local schema with URI `{}`'.format(uri))


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
        # collections.OrderedDict.__str__() returns a somewhat bulky
        # representation).
        validator.validate(self._dict_from_ordered_dict(instance))

    # Validates `instance` using the schema having the short ID
    # `schema_short_id`.
    #
    # A schema short ID is the part between `schemas/` and `.json` in
    # its URI.
    #
    # Raises a `_ConfigParseError` object, hiding any `jsonschema`
    # exception, on validation failure.
    def validate(self, instance, schema_short_id):
        try:
            self._validate(instance, schema_short_id)
        except jsonschema.ValidationError as exc:
            # convert to barectf `_ConfigParseError` exception
            contexts = ['Configuration object']

            # Each element of the instance's absolute path is either an
            # integer (array element's index) or a string (object
            # property's name).
            for elem in exc.absolute_path:
                if type(elem) is int:
                    ctx = 'Element {}'.format(elem)
                else:
                    ctx = '`{}` property'.format(elem)

                contexts.append(ctx)

            schema_ctx = ''

            if len(exc.context) > 0:
                # According to the documentation of
                # jsonschema.ValidationError.context(),
                # the method returns a
                #
                # > list of errors from the subschemas
                #
                # This contains additional information about the
                # validation failure which can help the user figure out
                # what's wrong exactly.
                #
                # Join each message with `; ` and append this to our
                # configuration parsing error's message.
                msgs = '; '.join([e.message for e in exc.context])
                schema_ctx = ': {}'.format(msgs)

            new_exc = _ConfigParseError(contexts.pop(),
                                        '{}{} (from schema `{}`)'.format(exc.message,
                                                                         schema_ctx,
                                                                         schema_short_id))

            for ctx in reversed(contexts):
                new_exc.append_ctx(ctx)

            raise new_exc


# Converts the byte order string `bo_str` to a `metadata.ByteOrder`
# enumerator.
def _byte_order_str_to_bo(bo_str):
    bo_str = bo_str.lower()

    if bo_str == 'le':
        return metadata.ByteOrder.LE
    elif bo_str == 'be':
        return metadata.ByteOrder.BE


# Converts the encoding string `encoding_str` to a `metadata.Encoding`
# enumerator.
def _encoding_str_to_encoding(encoding_str):
    encoding_str = encoding_str.lower()

    if encoding_str == 'utf-8' or encoding_str == 'utf8':
        return metadata.Encoding.UTF8
    elif encoding_str == 'ascii':
        return metadata.Encoding.ASCII
    elif encoding_str == 'none':
        return metadata.Encoding.NONE


# Validates the TSDL identifier `iden`, raising a `_ConfigParseError`
# exception using `ctx_obj_name` and `prop` to format the message if
# it's invalid.
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
        fmt = 'Invalid {} (not a valid identifier): `{}`'
        raise _ConfigParseError(ctx_obj_name, fmt.format(prop, iden))


# Validates the alignment `align`, raising a `_ConfigParseError`
# exception using `ctx_obj_name` if it's invalid.
def _validate_alignment(align, ctx_obj_name):
    assert align >= 1

    if (align & (align - 1)) != 0:
        raise _ConfigParseError(ctx_obj_name,
                                'Invalid alignment (not a power of two): {}'.format(align))


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


# A validator which validates the configured metadata for barectf
# specific needs.
#
# barectf needs:
#
# * The alignments of all header/context field types are at least 8.
#
# * There are no nested structure or array field types, except the
#   packet header field type's `uuid` field
#
class _BarectfMetadataValidator:
    def __init__(self):
        self._type_to_validate_type_func = {
            _Struct: self._validate_struct_type,
            _Array: self._validate_array_type,
        }

    def _validate_struct_type(self, t, entity_root):
        if not entity_root:
            raise _ConfigParseError('Structure field type',
                                    'Inner structure field types are not supported as of this version')

        for field_name, field_type in t.fields.items():
            if entity_root and self._cur_entity is _Entity.TRACE_PACKET_HEADER:
                if field_name == 'uuid':
                    # allow
                    continue

            try:
                self._validate_type(field_type, False)
            except _ConfigParseError as exc:
                _append_error_ctx(exc,
                                  'Structure field type\'s field `{}`'.format(field_name))

    def _validate_array_type(self, t, entity_root):
        raise _ConfigParseError('Array field type',
                                'Not supported as of this version')

    def _validate_type(self, t, entity_root):
        func = self._type_to_validate_type_func.get(type(t))

        if func is not None:
            func(t, entity_root)

    def _validate_entity(self, t):
        if t is None:
            return

        # make sure root field type has a real alignment of at least 8
        if t.real_align < 8:
            raise _ConfigParseError('Root field type',
                                    'Effective alignment must be at least 8 (got {})'.format(t.real_align))

        assert type(t) is _Struct

        # validate field types
        self._validate_type(t, True)

    def _validate_event_entities_and_names(self, stream, ev):
        try:
            _validate_identifier(ev.name, 'Event type', 'event type name')

            self._cur_entity = _Entity.EVENT_CONTEXT

            try:
                self._validate_entity(ev.context_type)
            except _ConfigParseError as exc:
                _append_error_ctx(exc, 'Event type',
                                  'Invalid context field type')

            self._cur_entity = _Entity.EVENT_PAYLOAD

            try:
                self._validate_entity(ev.payload_type)
            except _ConfigParseError as exc:
                _append_error_ctx(exc, 'Event type',
                                  'Invalid payload field type')

            if stream.is_event_empty(ev):
                raise _ConfigParseError('Event type', 'Empty')
        except _ConfigParseError as exc:
            _append_error_ctx(exc, 'Event type `{}`'.format(ev.name))

    def _validate_stream_entities_and_names(self, stream):
        try:
            _validate_identifier(stream.name, 'Stream type', 'stream type name')
            self._cur_entity = _Entity.STREAM_PACKET_CONTEXT

            try:
                self._validate_entity(stream.packet_context_type)
            except _ConfigParseError as exc:
                _append_error_ctx(exc, 'Stream type',
                                  'Invalid packet context field type')

            self._cur_entity = _Entity.STREAM_EVENT_HEADER

            try:
                self._validate_entity(stream.event_header_type)
            except _ConfigParseError as exc:
                _append_error_ctx(exc, 'Stream type',
                                  'Invalid event header field type')

            self._cur_entity = _Entity.STREAM_EVENT_CONTEXT

            try:
                self._validate_entity(stream.event_context_type)
            except _ConfigParseError as exc:
                _append_error_ctx(exc, 'Stream type',
                                  'Invalid event context field type')

            for ev in stream.events.values():
                self._validate_event_entities_and_names(stream, ev)
        except _ConfigParseError as exc:
            _append_error_ctx(exc, 'Stream type `{}`'.format(stream.name))

    def _validate_entities_and_names(self, meta):
        self._cur_entity = _Entity.TRACE_PACKET_HEADER

        try:
            self._validate_entity(meta.trace.packet_header_type)
        except _ConfigParseError as exc:
            _append_error_ctx(exc, 'Trace type',
                              'Invalid packet header field type')

        for stream in meta.streams.values():
            self._validate_stream_entities_and_names(stream)

    def _validate_default_stream(self, meta):
        if meta.default_stream_name is not None:
            if meta.default_stream_name not in meta.streams.keys():
                fmt = 'Default stream type name (`{}`) does not name an existing stream type'
                raise _ConfigParseError('Metadata',
                                        fmt.format(meta.default_stream_name))

    def validate(self, meta):
        try:
            self._validate_entities_and_names(meta)
            self._validate_default_stream(meta)
        except _ConfigParseError as exc:
            _append_error_ctx(exc, 'barectf metadata')


# A validator which validates special fields of trace, stream, and event
# types.
class _MetadataSpecialFieldsValidator:
    # Validates the packet header field type `t`.
    def _validate_trace_packet_header_type(self, t):
        ctx_obj_name = '`packet-header-type` property'

        # If there's more than one stream type, then the `stream_id`
        # (stream type ID) field is required.
        if len(self._meta.streams) > 1:
            if t is None:
                raise _ConfigParseError('Trace type',
                                        '`stream_id` field is required (because there\'s more than one stream type), but packet header field type is missing')

            if 'stream_id' not in t.fields:
                raise _ConfigParseError(ctx_obj_name,
                                        '`stream_id` field is required (because there\'s more than one stream type)')

        if t is None:
            return

        # The `magic` field type must be the first one.
        #
        # The `stream_id` field type's size (bits) must be large enough
        # to accomodate any stream type ID.
        for i, (field_name, field_type) in enumerate(t.fields.items()):
            if field_name == 'magic':
                if i != 0:
                    raise _ConfigParseError(ctx_obj_name,
                                            '`magic` field must be the first packet header field type\'s field')
            elif field_name == 'stream_id':
                if len(self._meta.streams) > (1 << field_type.size):
                    raise _ConfigParseError(ctx_obj_name,
                                            '`stream_id` field\'s size is too small to accomodate {} stream types'.format(len(self._meta.streams)))

    # Validates the trace type of the metadata object `meta`.
    def _validate_trace(self, meta):
        self._validate_trace_packet_header_type(meta.trace.packet_header_type)

    # Validates the packet context field type of the stream type
    # `stream`.
    def _validate_stream_packet_context(self, stream):
        ctx_obj_name = '`packet-context-type` property'
        t = stream.packet_context_type
        assert t is not None

        # The `timestamp_begin` and `timestamp_end` field types must be
        # mapped to the `value` property of the same clock.
        ts_begin = t.fields.get('timestamp_begin')
        ts_end = t.fields.get('timestamp_end')

        if ts_begin is not None and ts_end is not None:
            if ts_begin.property_mappings[0].object.name != ts_end.property_mappings[0].object.name:
                raise _ConfigParseError(ctx_obj_name,
                                        '`timestamp_begin` and `timestamp_end` fields must be mapped to the same clock value')

        # The `packet_size` field type's size must be greater than or
        # equal to the `content_size` field type's size.
        if t.fields['content_size'].size > t.fields['packet_size'].size:
            raise _ConfigParseError(ctx_obj_name,
                                    '`content_size` field\'s size must be less than or equal to `packet_size` field\'s size')

    # Validates the event header field type of the stream type `stream`.
    def _validate_stream_event_header(self, stream):
        ctx_obj_name = '`event-header-type` property'
        t = stream.event_header_type

        # If there's more than one event type, then the `id` (event type
        # ID) field is required.
        if len(stream.events) > 1:
            if t is None:
                raise _ConfigParseError('Stream type',
                                        '`id` field is required (because there\'s more than one event type), but event header field type is missing')

            if 'id' not in t.fields:
                raise _ConfigParseError(ctx_obj_name,
                                        '`id` field is required (because there\'s more than one event type)')

        if t is None:
            return

        # The `id` field type's size (bits) must be large enough to
        # accomodate any event type ID.
        eid = t.fields.get('id')

        if eid is not None:
            if len(stream.events) > (1 << eid.size):
                raise _ConfigParseError(ctx_obj_name,
                                        '`id` field\'s size is too small to accomodate {} event types'.format(len(stream.events)))

    # Validates the stream type `stream`.
    def _validate_stream(self, stream):
        self._validate_stream_packet_context(stream)
        self._validate_stream_event_header(stream)

    # Validates the trace and stream types of the metadata object
    # `meta`.
    def validate(self, meta):
        self._meta = meta

        try:
            try:
                self._validate_trace(meta)
            except _ConfigParseError as exc:
                _append_error_ctx(exc, 'Trace type')

            for stream in meta.streams.values():
                try:
                    self._validate_stream(stream)
                except _ConfigParseError as exc:
                    _append_error_ctx(exc, 'Stream type `{}`'.format(stream.name))
        except _ConfigParseError as exc:
            _append_error_ctx(exc, 'Metadata')


# A barectf YAML configuration parser.
#
# When you build such a parser, it parses the configuration file and
# creates a corresponding `config.Config` object which you can get with
# the `config` property.
#
# See the comments of _parse() for more implementation details about the
# parsing stages and general strategy.
class _YamlConfigParser:
    # Builds a barectf YAML configuration parser and parses the
    # configuration file having the path `path`.
    #
    # The parser considers the inclusion directories `include_dirs`,
    # ignores nonexistent inclusion files if `ignore_include_not_found`
    # is `True`, and dumps the effective configuration (as YAML) if
    # `dump_config` is `True`.
    #
    # Raises `_ConfigParseError` on parsing error.
    def __init__(self, path, include_dirs, ignore_include_not_found,
                 dump_config):
        self._root_path = path
        self._class_name_to_create_field_type_func = {
            'int': self._create_integer_field_type,
            'integer': self._create_integer_field_type,
            'flt': self._create_float_field_type,
            'float': self._create_float_field_type,
            'floating-point': self._create_float_field_type,
            'enum': self._create_enum_field_type,
            'enumeration': self._create_enum_field_type,
            'str': self._create_string_field_type,
            'string': self._create_string_field_type,
            'struct': self._create_struct_field_type,
            'structure': self._create_struct_field_type,
            'array': self._create_array_field_type,
        }
        self._include_dirs = include_dirs
        self._ignore_include_not_found = ignore_include_not_found
        self._dump_config = dump_config
        self._schema_validator = _SchemaValidator()
        self._parse()

    # Sets the default byte order as found in the `metadata_node` node.
    def _set_byte_order(self, metadata_node):
        self._bo = _byte_order_str_to_bo(metadata_node['trace']['byte-order'])
        assert self._bo is not None

    # Sets the clock value property mapping of the pseudo integer field
    # type object `int_obj` as found in the `prop_mapping_node` node.
    def _set_int_clock_prop_mapping(self, int_obj, prop_mapping_node):
        clock_name = prop_mapping_node['name']
        clock = self._clocks.get(clock_name)

        if clock is None:
            exc = _ConfigParseError('`property-mappings` property',
                                    'Clock type `{}` does not exist'.format(clock_name))
            exc.append_ctx('Integer field type')
            raise exc

        prop_mapping = _PropertyMapping()
        prop_mapping.object = clock
        prop_mapping.prop = 'value'
        int_obj.property_mappings.append(prop_mapping)

    # Creates a pseudo integer field type from the node `node` and
    # returns it.
    def _create_integer_field_type(self, node):
        obj = _Integer()
        obj.size = node['size']
        align_node = node.get('align')

        if align_node is not None:
            _validate_alignment(align_node, 'Integer field type')
            obj.align = align_node

        signed_node = node.get('signed')

        if signed_node is not None:
            obj.signed = signed_node

        obj.byte_order = self._bo
        bo_node = node.get('byte-order')

        if bo_node is not None:
            obj.byte_order = _byte_order_str_to_bo(bo_node)

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

        encoding_node = node.get('encoding')

        if encoding_node is not None:
            obj.encoding = _encoding_str_to_encoding(encoding_node)

        pm_node = node.get('property-mappings')

        if pm_node is not None:
            assert len(pm_node) == 1
            self._set_int_clock_prop_mapping(obj, pm_node[0])

        return obj

    # Creates a pseudo floating point number field type from the node
    # `node` and returns it.
    def _create_float_field_type(self, node):
        obj = _FloatingPoint()
        size_node = node['size']
        obj.exp_size = size_node['exp']
        obj.mant_size = size_node['mant']
        align_node = node.get('align')

        if align_node is not None:
            _validate_alignment(align_node, 'Floating point number field type')
            obj.align = align_node

        obj.byte_order = self._bo
        bo_node = node.get('byte-order')

        if bo_node is not None:
            obj.byte_order = _byte_order_str_to_bo(bo_node)

        return obj

    # Creates a pseudo enumeration field type from the node `node` and
    # returns it.
    def _create_enum_field_type(self, node):
        ctx_obj_name = 'Enumeration field type'
        obj = _Enum()

        # value (integer) field type
        try:
            obj.value_type = self._create_type(node['value-type'])
        except _ConfigParseError as exc:
            _append_error_ctx(exc, ctx_obj_name,
                              'Cannot create value (integer) field type')

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
                            exc = _ConfigParseError(ctx_obj_name)
                            exc.append_ctx('Member `{}`'.format(label),
                                           'Invalid integral range ({} > {})'.format(label, mn, mx))
                            raise exc

                        value = (mn, mx)
                        cur = mx + 1

                # Make sure that all the integral values of the range
                # fits the enumeration field type's integer value field
                # type depending on its size (bits).
                member_obj_name = 'Member `{}`'.format(label)
                msg_fmt = 'Value {} is outside the value type range [{}, {}]'
                msg = msg_fmt.format(value[0], value_min, value_max)

                try:
                    if value[0] < value_min or value[0] > value_max:
                        raise _ConfigParseError(member_obj_name, msg)

                    if value[1] < value_min or value[1] > value_max:
                        raise _ConfigParseError(member_obj_name, msg)
                except _ConfigParseError as exc:
                    _append_error_ctx(exc, ctx_obj_name)

                obj.members[label] = value

        return obj

    # Creates a pseudo string field type from the node `node` and
    # returns it.
    def _create_string_field_type(self, node):
        obj = _String()
        encoding_node = node.get('encoding')

        if encoding_node is not None:
            obj.encoding = _encoding_str_to_encoding(encoding_node)

        return obj

    # Creates a pseudo structure field type from the node `node` and
    # returns it.
    def _create_struct_field_type(self, node):
        ctx_obj_name = 'Structure field type'
        obj = _Struct()
        min_align_node = node.get('min-align')

        if min_align_node is not None:
            _validate_alignment(min_align_node, ctx_obj_name)
            obj.min_align = min_align_node

        fields_node = node.get('fields')

        if fields_node is not None:
            for field_name, field_node in fields_node.items():
                _validate_identifier(field_name, ctx_obj_name, 'field name')

                try:
                    obj.fields[field_name] = self._create_type(field_node)
                except _ConfigParseError as exc:
                    _append_error_ctx(exc, ctx_obj_name,
                                      'Cannot create field `{}`'.format(field_name))

        return obj

    # Creates a pseudo array field type from the node `node` and returns
    # it.
    def _create_array_field_type(self, node):
        obj = _Array()
        obj.length = node['length']

        try:
            obj.element_type = self._create_type(node['element-type'])
        except _ConfigParseError as exc:
            _append_error_ctx(exc, 'Array field type',
                              'Cannot create element field type')

        return obj

    # Creates a pseudo field type from the node `node` and returns it.
    #
    # This method checks the `class` property of `node` to determine
    # which function of `self._class_name_to_create_field_type_func` to
    # call to create the corresponding pseudo field type.
    def _create_type(self, type_node):
        return self._class_name_to_create_field_type_func[type_node['class']](type_node)

    # Creates a pseudo clock type from the node `node` and returns it.
    def _create_clock(self, node):
        clock = _Clock()
        uuid_node = node.get('uuid')

        if uuid_node is not None:
            try:
                clock.uuid = uuid.UUID(uuid_node)
            except:
                raise _ConfigParseError('Clock type',
                                        'Malformed UUID `{}`'.format(uuid_node))

        descr_node = node.get('description')

        if descr_node is not None:
            clock.description = descr_node

        freq_node = node.get('freq')

        if freq_node is not None:
            clock.freq = freq_node

        error_cycles_node = node.get('error-cycles')

        if error_cycles_node is not None:
            clock.error_cycles = error_cycles_node

        offset_node = node.get('offset')

        if offset_node is not None:
            offset_cycles_node = offset_node.get('cycles')

            if offset_cycles_node is not None:
                clock.offset_cycles = offset_cycles_node

            offset_seconds_node = offset_node.get('seconds')

            if offset_seconds_node is not None:
                clock.offset_seconds = offset_seconds_node

        absolute_node = node.get('absolute')

        if absolute_node is not None:
            clock.absolute = absolute_node

        return_ctype_node = node.get('$return-ctype')

        if return_ctype_node is None:
            # barectf 2.1: `return-ctype` property was renamed to
            # `$return-ctype`
            return_ctype_node = node.get('return-ctype')

        if return_ctype_node is not None:
            clock.return_ctype = return_ctype_node

        return clock

    # Registers all the clock types of the metadata node
    # `metadata_node`, creating pseudo clock types during the process,
    # within this parser.
    #
    # The pseudo clock types in `self._clocks` are then accessible when
    # creating a pseudo integer field type (see
    # _create_integer_field_type() and _set_int_clock_prop_mapping()).
    def _register_clocks(self, metadata_node):
        self._clocks = collections.OrderedDict()
        clocks_node = metadata_node.get('clocks')

        if clocks_node is None:
            return

        for clock_name, clock_node in clocks_node.items():
            _validate_identifier(clock_name, 'Metadata', 'clock type name')
            assert clock_name not in self._clocks

            try:
                clock = self._create_clock(clock_node)
            except _ConfigParseError as exc:
                _append_error_ctx(exc, 'Metadata',
                                  'Cannot create clock type `{}`'.format(clock_name))

            clock.name = clock_name
            self._clocks[clock_name] = clock

    # Creates an environment object (`collections.OrderedDict`) from the
    # metadata node `metadata_node` and returns it.
    def _create_env(self, metadata_node):
        env_node = metadata_node.get('env')

        if env_node is None:
            return collections.OrderedDict()

        for env_name, env_value in env_node.items():
            _validate_identifier(env_name, 'Metadata',
                                 'environment variable name')

        return copy.deepcopy(env_node)

    # Creates a pseudo trace type from the metadata node `metadata_node`
    # and returns it.
    def _create_trace(self, metadata_node):
        ctx_obj_name = 'Trace type'
        trace = _Trace()
        trace_node = metadata_node['trace']
        trace.byte_order = self._bo
        uuid_node = trace_node.get('uuid')

        if uuid_node is not None:
            # The `uuid` property of the trace type node can be `auto`
            # to make barectf generate a UUID.
            if uuid_node == 'auto':
                trace.uuid = uuid.uuid1()
            else:
                try:
                    trace.uuid = uuid.UUID(uuid_node)
                except:
                    raise _ConfigParseError(ctx_obj_name,
                                            'Malformed UUID `{}`'.format(uuid_node))

        pht_node = trace_node.get('packet-header-type')

        if pht_node is not None:
            try:
                trace.packet_header_type = self._create_type(pht_node)
            except _ConfigParseError as exc:
                _append_error_ctx(exc, ctx_obj_name,
                                  'Cannot create packet header field type')

        return trace

    # Creates a pseudo event type from the event node `event_node` and
    # returns it.
    def _create_event(self, event_node):
        ctx_obj_name = 'Event type'
        event = _Event()
        log_level_node = event_node.get('log-level')

        if log_level_node is not None:
            assert type(log_level_node) is int
            event.log_level = metadata.LogLevel(None, log_level_node)

        ct_node = event_node.get('context-type')

        if ct_node is not None:
            try:
                event.context_type = self._create_type(ct_node)
            except _ConfigParseError as exc:
                _append_error_ctx(exc, ctx_obj_name,
                                  'Cannot create context field type')

        pt_node = event_node.get('payload-type')

        if pt_node is not None:
            try:
                event.payload_type = self._create_type(pt_node)
            except _ConfigParseError as exc:
                _append_error_ctx(exc, ctx_obj_name,
                                  'Cannot create payload field type')

        return event

    # Creates a pseudo stream type named `stream_name` from the stream
    # node `stream_node` and returns it.
    def _create_stream(self, stream_name, stream_node):
        ctx_obj_name = 'Stream type'
        stream = _Stream()
        pct_node = stream_node.get('packet-context-type')

        if pct_node is not None:
            try:
                stream.packet_context_type = self._create_type(pct_node)
            except _ConfigParseError as exc:
                _append_error_ctx(exc, ctx_obj_name,
                                  'Cannot create packet context field type')

        eht_node = stream_node.get('event-header-type')

        if eht_node is not None:
            try:
                stream.event_header_type = self._create_type(eht_node)
            except _ConfigParseError as exc:
                _append_error_ctx(exc, ctx_obj_name,
                                  'Cannot create event header field type')

        ect_node = stream_node.get('event-context-type')

        if ect_node is not None:
            try:
                stream.event_context_type = self._create_type(ect_node)
            except _ConfigParseError as exc:
                _append_error_ctx(exc, ctx_obj_name,
                                  'Cannot create event context field type')

        events_node = stream_node['events']
        cur_id = 0

        for ev_name, ev_node in events_node.items():
            try:
                ev = self._create_event(ev_node)
            except _ConfigParseError as exc:
                _append_error_ctx(exc, ctx_obj_name,
                                  'Cannot create event type `{}`'.format(ev_name))

            ev.id = cur_id
            ev.name = ev_name
            stream.events[ev_name] = ev
            cur_id += 1

        default_node = stream_node.get('$default')

        if default_node is not None:
            if self._meta.default_stream_name is not None and self._meta.default_stream_name != stream_name:
                fmt = 'Cannot specify more than one default stream type (default stream type already set to `{}`)'
                raise _ConfigParseError('Stream type',
                                        fmt.format(self._meta.default_stream_name))

            self._meta.default_stream_name = stream_name

        return stream

    # Creates a `collections.OrderedDict` object where keys are stream
    # type names and values are pseudo stream types from the metadata
    # node `metadata_node` and returns it.
    def _create_streams(self, metadata_node):
        streams = collections.OrderedDict()
        streams_node = metadata_node['streams']
        cur_id = 0

        for stream_name, stream_node in streams_node.items():
            try:
                stream = self._create_stream(stream_name, stream_node)
            except _ConfigParseError as exc:
                _append_error_ctx(exc, 'Metadata',
                                  'Cannot create stream type `{}`'.format(stream_name))

            stream.id = cur_id
            stream.name = stream_name
            streams[stream_name] = stream
            cur_id += 1

        return streams

    # Creates a pseudo metadata object from the configuration node
    # `root` and returns it.
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

        # validate the pseudo metadata object
        _MetadataSpecialFieldsValidator().validate(self._meta)
        _BarectfMetadataValidator().validate(self._meta)

        return self._meta

    # Gets and validates the tracing prefix as found in the
    # configuration node `config_node` and returns it.
    def _get_prefix(self, config_node):
        prefix = config_node.get('prefix', 'barectf_')
        _validate_identifier(prefix, '`prefix` property', 'prefix')
        return prefix

    # Gets the options as found in the configuration node `config_node`
    # and returns a corresponding `config.ConfigOptions` object.
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

    # Returns the last included file name from the parser's inclusion
    # file name stack.
    def _get_last_include_file(self):
        if self._include_stack:
            return self._include_stack[-1]

        return self._root_path

    # Loads the inclusion file having the path `yaml_path` and returns
    # its content as a `collections.OrderedDict` object.
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
                raise _ConfigParseError('File `{}`'.format(base_path),
                                        'Cannot recursively include file `{}`'.format(norm_path))

            self._include_stack.append(norm_path)

            # load raw content
            return self._yaml_ordered_load(norm_path)

        if not self._ignore_include_not_found:
            base_path = self._get_last_include_file()
            raise _ConfigParseError('File `{}`'.format(base_path),
                                    'Cannot include file `{}`: file not found in inclusion directories'.format(yaml_path))
    # Returns a list of all the inclusion file paths as found in the
    # inclusion node `include_node`.
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

    # Updates the node `base_node` with an overlay node `overlay_node`.
    #
    # Both the inclusion and field type inheritance features use this
    # update mechanism.
    def _update_node(self, base_node, overlay_node):
        for olay_key, olay_value in overlay_node.items():
            if olay_key in base_node:
                base_value = base_node[olay_key]

                if type(olay_value) is collections.OrderedDict and type(base_value) is collections.OrderedDict:
                    # merge both objects
                    self._update_node(base_value, olay_value)
                elif type(olay_value) is list and type(base_value) is list:
                    # append extension array items to base items
                    base_value += olay_value
                else:
                    # fall back to replacing base property
                    base_node[olay_key] = olay_value
            else:
                # set base property from overlay property
                base_node[olay_key] = olay_value

    # Processes inclusions using `last_overlay_node` as the last overlay
    # node to use to "patch" the node.
    #
    # If `last_overlay_node` contains an `$include` property, then this
    # method patches the current base node (initially empty) in order
    # using the content of the inclusion files (recursively).
    #
    # At the end, this method removes the `$include` of
    # `last_overlay_node` and then patches the current base node with
    # its other properties before returning the result (always a deep
    # copy).
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
            except _ConfigParseError as exc:
                _append_error_ctx(exc, 'File `{}`'.format(cur_base_path))

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

    # Process the inclusions of the event type node `event_node`,
    # returning the effective node.
    def _process_event_include(self, event_node):
        # Make sure the event type node is valid for the inclusion
        # processing stage.
        self._schema_validator.validate(event_node,
                                        '2/config/event-pre-include')

        # process inclusions
        return self._process_node_include(event_node,
                                          self._process_event_include)

    # Process the inclusions of the stream type node `stream_node`,
    # returning the effective node.
    def _process_stream_include(self, stream_node):
        def process_children_include(stream_node):
            if 'events' in stream_node:
                events_node = stream_node['events']

                for key in list(events_node):
                    events_node[key] = self._process_event_include(events_node[key])

        # Make sure the stream type node is valid for the inclusion
        # processing stage.
        self._schema_validator.validate(stream_node,
                                        '2/config/stream-pre-include')

        # process inclusions
        return self._process_node_include(stream_node,
                                          self._process_stream_include,
                                          process_children_include)

    # Process the inclusions of the trace type node `trace_node`,
    # returning the effective node.
    def _process_trace_include(self, trace_node):
        # Make sure the trace type node is valid for the inclusion
        # processing stage.
        self._schema_validator.validate(trace_node,
                                        '2/config/trace-pre-include')

        # process inclusions
        return self._process_node_include(trace_node,
                                          self._process_trace_include)

    # Process the inclusions of the clock type node `clock_node`,
    # returning the effective node.
    def _process_clock_include(self, clock_node):
        # Make sure the clock type node is valid for the inclusion
        # processing stage.
        self._schema_validator.validate(clock_node,
                                        '2/config/clock-pre-include')

        # process inclusions
        return self._process_node_include(clock_node,
                                          self._process_clock_include)

    # Process the inclusions of the metadata node `metadata_node`,
    # returning the effective node.
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

        # Make sure the metadata node is valid for the inclusion
        # processing stage.
        self._schema_validator.validate(metadata_node,
                                        '2/config/metadata-pre-include')

        # process inclusions
        return self._process_node_include(metadata_node,
                                          self._process_metadata_include,
                                          process_children_include)

    # Process the inclusions of the configuration node `config_node`,
    # returning the effective node.
    def _process_config_includes(self, config_node):
        # Process inclusions in this order:
        #
        # 1. Clock type node, event type nodes, and trace type nodes
        #    (the order between those is not important).
        #
        # 2. Stream type nodes.
        #
        # 3. Metadata node.
        #
        # This is because:
        #
        # * A metadata node can include clock type nodes, a trace type
        #   node, stream type nodes, and event type nodes (indirectly).
        #
        # * A stream type node can include event type nodes.
        #
        # We keep a stack of absolute paths to included files
        # (`self._include_stack`) to detect recursion.
        #
        # First, make sure the configuration object itself is valid for
        # the inclusion processing stage.
        self._schema_validator.validate(config_node,
                                        '2/config/config-pre-include')

        # Process metadata node inclusions.
        #
        # self._process_metadata_include() returns a new (or the same)
        # metadata node without any `$include` property in it,
        # recursively.
        config_node['metadata'] = self._process_metadata_include(config_node['metadata'])

        return config_node

    # Expands the field type aliases found in the metadata node
    # `metadata_node` using the aliases of the `type_aliases_node` node.
    #
    # This method modifies `metadata_node`.
    #
    # When this method returns:
    #
    # * Any field type alias is replaced with its full field type
    #   equivalent.
    #
    # * The `type-aliases` property of `metadata_node` is removed.
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
                        fmt = 'Cycle detected during the `{}` field type alias resolution'
                        raise _ConfigParseError(from_descr, fmt.format(alias))

                    # try to load field type alias node named `alias`
                    if alias not in type_aliases_node:
                        raise _ConfigParseError(from_descr,
                                                'Field type alias `{}` does not exist'.format(alias))

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

        def resolve_field_type_aliases_from(parent_node, key):
            resolve_field_type_aliases(parent_node, key,
                                       '`{}` property'.format(key))

        # set of resolved field type aliases
        resolved_aliases = set()

        # Expand field type aliases within trace, stream, and event
        # types now.
        try:
            resolve_field_type_aliases_from(metadata_node['trace'],
                                            'packet-header-type')
        except _ConfigParseError as exc:
            _append_error_ctx(exc, 'Trace type')

        for stream_name, stream in metadata_node['streams'].items():
            try:
                resolve_field_type_aliases_from(stream, 'packet-context-type')
                resolve_field_type_aliases_from(stream, 'event-header-type')
                resolve_field_type_aliases_from(stream, 'event-context-type')

                for event_name, event in stream['events'].items():
                    try:
                        resolve_field_type_aliases_from(event, 'context-type')
                        resolve_field_type_aliases_from(event, 'payload-type')
                    except _ConfigParseError as exc:
                        _append_error_ctx(exc,
                                          'Event type `{}`'.format(event_name))
            except _ConfigParseError as exc:
                _append_error_ctx(exc, 'Stream type `{}`'.format(stream_name))

        # remove the (now unneeded) `type-aliases` node
        del metadata_node['type-aliases']

    # Applies field type inheritance to all field types found in
    # `metadata_node`.
    #
    # This method modifies `metadata_node`.
    #
    # When this method returns, no field type node has an `$inherit` or
    # `inherit` property.
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

    # Calls _expand_field_type_aliases() and
    # _expand_field_type_inheritance() if the metadata node
    # `metadata_node` has a `type-aliases` property.
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

    # Replaces the textual log levels in event type nodes of the
    # metadata node `metadata_node` with their numeric equivalent (as
    # found in the `$log-levels` or `log-levels` node of
    # `metadata_node`).
    #
    # This method modifies `metadata_node`.
    #
    # When this method returns, the `$log-levels` or `log-level`
    # property of `metadata_node` is removed.
    def _expand_log_levels(self, metadata_node):
        if 'log-levels' in metadata_node:
            # barectf 2.1: `log-levels` property was renamed to
            # `$log-levels`
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
                            exc = _ConfigParseError('`log-level` property',
                                                    'Log level alias `{}` does not exist'.format(ll_node))
                            exc.append_ctx('Event type `{}`'.format(event_name))
                            raise exc

                        event[prop_name] = log_levels_node[ll_node]
            except _ConfigParseError as exc:
                _append_error_ctx(exc, 'Stream type `{}`'.format(stream_name))

    # Dumps the node `node` as YAML, passing `kwds` to yaml.dump().
    def _yaml_ordered_dump(self, node, **kwds):
        class ODumper(yaml.Dumper):
            pass

        def dict_representer(dumper, node):
            return dumper.represent_mapping(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                                            node.items())

        ODumper.add_representer(collections.OrderedDict, dict_representer)

        # Python -> YAML
        return yaml.dump(node, Dumper=ODumper, **kwds)

    # Loads the content of the YAML file having the path `yaml_path` as
    # a Python object.
    #
    # All YAML maps are loaded as `collections.OrderedDict` objects.
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
        except (OSError, IOError) as exc:
            raise _ConfigParseError('File `{}`'.format(yaml_path),
                                    'Cannot open file: {}'.format(exc))

        assert type(node) is collections.OrderedDict
        return node

    def _parse(self):
        self._version = None
        self._include_stack = []

        # load the configuration object as is from the root YAML file
        try:
            config_node = self._yaml_ordered_load(self._root_path)
        except _ConfigParseError as exc:
            _append_error_ctx(exc, 'Configuration',
                              'Cannot parse YAML file `{}`'.format(self._root_path))

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
        # 2. Applies inheritance, following the `$inherit`/`inherit`
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
        self._config = config.Config(pseudo_meta.to_public(), prefix, opts)

    @property
    def config(self):
        return self._config


def _from_file(path, include_dirs, ignore_include_not_found, dump_config):
    try:
        return _YamlConfigParser(path, include_dirs, ignore_include_not_found,
                                 dump_config).config
    except _ConfigParseError as exc:
        _append_error_ctx(exc, 'Configuration',
                          'Cannot create configuration from YAML file `{}`'.format(path))
