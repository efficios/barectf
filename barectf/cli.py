# The MIT License (MIT)
#
# Copyright (c) 2014 Philippe Proulx <philippe.proulx@efficios.com>
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
from termcolor import cprint, colored
import barectf.templates
import pytsdl.parser
import pytsdl.tsdl
import collections
import argparse
import sys
import os
import re


def _perror(msg, exit_code=1):
    cprint('error: {}'.format(msg), 'red', attrs=['bold'], file=sys.stderr)
    sys.exit(exit_code)


def _pinfo(msg):
    cprint(':: {}'.format(msg), 'blue', attrs=['bold'])


def _psuccess(msg):
    cprint('{}'.format(msg), 'green', attrs=['bold'])


def _parse_args():
    ap = argparse.ArgumentParser()

    ap.add_argument('-O', '--output', metavar='OUTPUT', action='store',
                    default=os.getcwd(),
                    help='output directory of C files')
    ap.add_argument('-p', '--prefix', metavar='PREFIX', action='store',
                    default='barectf',
                    help='custom prefix for C function and structure names')
    ap.add_argument('-s', '--static-inline', action='store_true',
                    help='generate static inline C functions')
    ap.add_argument('-c', '--manual-clock', action='store_true',
                    help='do not use a clock callback: pass clock value to tracing functions')
    ap.add_argument('metadata', metavar='METADATA', action='store',
                    help='CTF metadata input file')

    # parse args
    args = ap.parse_args()

    # validate output directory
    if not os.path.isdir(args.output):
        _perror('"{}" is not an existing directory'.format(args.output))

    # validate prefix
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', args.prefix):
        _perror('"{}" is not a valid C identifier'.format(args.prefix))

    # validate that metadata file exists
    if not os.path.isfile(args.metadata):
        _perror('"{}" is not an existing file'.format(args.metadata))

    return args


class _CBlock(list):
    pass


class _CLine(str):
    pass


class BarectfCodeGenerator:
    _CTX_AT = 'ctx->at'
    _CTX_BUF = 'ctx->buf'
    _CTX_PACKET_SIZE = 'ctx->packet_size'
    _CTX_BUF_AT = '{}[{} >> 3]'.format(_CTX_BUF, _CTX_AT)
    _CTX_BUF_AT_ADDR = '&{}'.format(_CTX_BUF_AT)
    _CTX_CALL_CLOCK_CB = 'ctx->clock_cb(ctx->clock_cb_data)'

    _BO_SUFFIXES_MAP = {
        pytsdl.tsdl.ByteOrder.BE: 'be',
        pytsdl.tsdl.ByteOrder.LE: 'le',
    }

    _TSDL_TYPE_NAMES_MAP = {
        pytsdl.tsdl.Integer: 'integer',
        pytsdl.tsdl.FloatingPoint: 'floating point',
        pytsdl.tsdl.Enum: 'enumeration',
        pytsdl.tsdl.String: 'string',
        pytsdl.tsdl.Array: 'static array',
        pytsdl.tsdl.Sequence: 'dynamic array',
        pytsdl.tsdl.Struct: 'structure',
    }

    def __init__(self):
        self._parser = pytsdl.parser.Parser()

        self._obj_size_cb = {
            pytsdl.tsdl.Struct: self._get_struct_size,
            pytsdl.tsdl.Integer: self._get_integer_size,
            pytsdl.tsdl.Enum: self._get_enum_size,
            pytsdl.tsdl.FloatingPoint: self._get_floating_point_size,
            pytsdl.tsdl.Array: self._get_array_size,
        }

        self._obj_alignment_cb = {
            pytsdl.tsdl.Struct: self._get_struct_alignment,
            pytsdl.tsdl.Integer: self._get_integer_alignment,
            pytsdl.tsdl.Enum: self._get_enum_alignment,
            pytsdl.tsdl.FloatingPoint: self._get_floating_point_alignment,
            pytsdl.tsdl.Array: self._get_array_alignment,
            pytsdl.tsdl.Sequence: self._get_sequence_alignment,
            pytsdl.tsdl.String: self._get_string_alignment,
        }

        self._obj_param_ctype_cb = {
            pytsdl.tsdl.Struct: lambda obj: 'const void*',
            pytsdl.tsdl.Integer: self._get_integer_param_ctype,
            pytsdl.tsdl.Enum: self._get_enum_param_ctype,
            pytsdl.tsdl.FloatingPoint: self._get_floating_point_param_ctype,
            pytsdl.tsdl.Array: lambda obj: 'const void*',
            pytsdl.tsdl.Sequence: lambda obj: 'const void*',
            pytsdl.tsdl.String: lambda obj: 'const char*',
        }

        self._write_field_obj_cb = {
            pytsdl.tsdl.Struct: self._write_field_struct,
            pytsdl.tsdl.Integer: self._write_field_integer,
            pytsdl.tsdl.Enum: self._write_field_enum,
            pytsdl.tsdl.FloatingPoint: self._write_field_floating_point,
            pytsdl.tsdl.Array: self._write_field_array,
            pytsdl.tsdl.Sequence: self._write_field_sequence,
            pytsdl.tsdl.String: self._write_field_string,
        }

        self._get_src_name_funcs = {
            'trace.packet.header.': self._get_tph_src_name,
            'env.': self._get_env_src_name,
            'stream.packet.context.': self._get_spc_src_name,
            'stream.event.header.': self._get_seh_src_name,
            'stream.event.context.': self._get_sec_src_name,
            'event.context.': self._get_ec_src_name,
            'event.fields.': self._get_ef_src_name,
        }

    # Finds the terminal element of a TSDL array/sequence.
    #
    #   arrayseq: array or sequence
    def _find_arrayseq_element(self, arrayseq):
        el = arrayseq.element
        t = type(arrayseq.element)

        if t is pytsdl.tsdl.Array or t is pytsdl.tsdl.Sequence:
            return self._find_arrayseq_element(el)

        return el

    # Validates an inner TSDL structure's field (constrained structure).
    #
    #   fname: field name
    #   ftype: TSDL object
    def _validate_struct_field(self, fname, ftype, inner_struct):
        if type(ftype) is pytsdl.tsdl.Sequence:
            if inner_struct:
                raise RuntimeError('field "{}" is a dynamic array (not allowed here)'.format(fname))
            else:
                element = self._find_arrayseq_element(ftype)
                self._validate_struct_field(fname, element, True)
        elif type(ftype) is pytsdl.tsdl.Array:
            # we need to check every element until we find a terminal one
            element = self._find_arrayseq_element(ftype)
            self._validate_struct_field(fname, element, True)
        elif type(ftype) is pytsdl.tsdl.Variant:
            raise RuntimeError('field "{}" contains a variant (unsupported)'.format(fname))
        elif type(ftype) is pytsdl.tsdl.String:
            if inner_struct:
                raise RuntimeError('field "{}" contains a string (not allowed here)'.format(fname))
        elif type(ftype) is pytsdl.tsdl.Struct:
            self._validate_struct(ftype, True)
        elif type(ftype) is pytsdl.tsdl.Integer:
            if self._get_obj_size(ftype) > 64:
                raise RuntimeError('integer field "{}" larger than 64-bit'.format(fname))
        elif type(ftype) is pytsdl.tsdl.FloatingPoint:
            if self._get_obj_size(ftype) > 64:
                raise RuntimeError('floating point field "{}" larger than 64-bit'.format(fname))
        elif type(ftype) is pytsdl.tsdl.Enum:
            if self._get_obj_size(ftype) > 64:
                raise RuntimeError('enum field "{}" larger than 64-bit'.format(fname))

    # Validates an inner TSDL structure (constrained).
    #
    #   struct: TSDL structure to validate
    def _validate_struct(self, struct, inner_struct):
        # just in case we call this with the wrong type
        if type(struct) is not pytsdl.tsdl.Struct:
            raise RuntimeError('expecting a struct')

        # make sure inner structures are at least byte-aligned
        if inner_struct:
            if self._get_obj_alignment(struct) < 8:
                raise RuntimeError('inner struct must be at least byte-aligned')

        # check each field
        for fname, ftype in struct.fields.items():
            self._validate_struct_field(fname, ftype, inner_struct)

    # Validates a context or fields structure.
    #
    #   struct: context/fields TSDL structure
    def _validate_context_fields(self, struct):
        if type(struct) is not pytsdl.tsdl.Struct:
            raise RuntimeError('expecting a struct')

        self._validate_struct(struct, False)

    # Validates a TSDL integer with optional constraints.
    #
    #   integer: TSDL integer to validate
    #   size:    expected size (None for any size)
    #   align:   expected alignment (None for any alignment)
    #   signed:  expected signedness (None for any signedness)
    def _validate_integer(self, integer, size=None, align=None,
                          signed=None):
        if type(integer) is not pytsdl.tsdl.Integer:
            raise RuntimeError('expected integer')

        if size is not None:
            if integer.size != size:
                raise RuntimeError('expected {}-bit integer'.format(size))

        if align is not None:
            if integer.align != align:
                raise RuntimeError('expected integer with {}-bit alignment'.format(align))

        if signed is not None:
            if integer.signed != signed:
                raise RuntimeError('expected {} integer'.format('signed' if signed else 'unsigned'))

    # Validates a packet header.
    #
    #   packet_header: packet header TSDL structure to validate
    def _validate_tph(self, packet_header):
        try:
            self._validate_struct(packet_header, True)
        except RuntimeError as e:
            _perror('packet header: {}'.format(e))

        # magic must be the first field
        if 'magic' in packet_header.fields:
            if list(packet_header.fields.keys())[0] != 'magic':
                _perror('packet header: "magic" must be the first field')
        else:
            _perror('packet header: missing "magic" field')

        # magic must be a 32-bit unsigned integer, 32-bit aligned
        try:
            self._validate_integer(packet_header['magic'], 32, 32, False)
        except RuntimeError as e:
            _perror('packet header: "magic": {}'.format(e))

        # mandatory stream_id
        if 'stream_id' not in packet_header.fields:
            _perror('packet header: missing "stream_id" field')

        # stream_id must be an unsigned integer
        try:
            self._validate_integer(packet_header['stream_id'], signed=False)
        except RuntimeError as e:
            _perror('packet header: "stream_id": {}'.format(e))

        # only magic and stream_id allowed
        if len(packet_header.fields) != 2:
            _perror('packet header: only "magic" and "stream_id" fields are allowed')

    # Converts a list of strings to a dotted representation. For
    # example, ['trace', 'packet', 'header', 'magic'] is converted to
    # 'trace.packet.header.magic'.
    #
    #   name: list of strings to convert
    def _dot_name_to_str(self, name):
        return '.'.join(name)

    # Compares two TSDL integers. Returns True if they are the same.
    #
    #   int1: first TSDL integer
    #   int2: second TSDL integer
    def _compare_integers(self, int1, int2):
        if type(int1) is not pytsdl.tsdl.Integer:
            return False

        if type(int2) is not pytsdl.tsdl.Integer:
            return False

        size = int1.size == int2.size
        align = int1.align == int2.align
        cmap = int1.map == int2.map
        base = int1.base == int2.base
        encoding = int1.encoding == int2.encoding
        signed = int1.signed == int2.signed
        comps = (size, align, cmap, base, encoding, signed)

        # True means 1 for sum()
        return sum(comps) == len(comps)

    # Validates a packet context.
    #
    #   stream: TSDL stream containing the packet context to validate
    def _validate_spc(self, stream):
        packet_context = stream.packet_context
        sid = stream.id

        try:
            self._validate_struct(packet_context, True)
        except RuntimeError as e:
            _perror('stream {}: packet context: {}'.format(sid, e))

        fields = packet_context.fields

        # if timestamp_begin exists, timestamp_end must exist
        if 'timestamp_begin' in fields or 'timestamp_end' in fields:
            if 'timestamp_begin' not in fields or 'timestamp_end' not in fields:
                _perror('stream {}: packet context: "timestamp_begin" must exist if "timestamp_end" exists'.format(sid))
            else:
                # timestamp_begin and timestamp_end must have the same integer
                # as the event header's timestamp field (should exist by now)
                timestamp = stream.event_header['timestamp']

                if not self._compare_integers(fields['timestamp_begin'], timestamp):
                    _perror('stream {}: packet context: "timestamp_begin": integer type different from event header\'s "timestamp" field'.format(sid))

                if not self._compare_integers(fields['timestamp_end'], timestamp):
                    _perror('stream {}: packet context: "timestamp_end": integer type different from event header\'s "timestamp" field'.format(sid))

        # content_size must exist and be an unsigned integer
        if 'content_size' not in fields:
            _perror('stream {}: packet context: missing "content_size" field'.format(sid))

        try:
            self._validate_integer(fields['content_size'], 32, 32, False)
        except:
            try:
                self._validate_integer(fields['content_size'], 64, 64, False)
            except:
                _perror('stream {}: packet context: "content_size": expecting unsigned 32-bit/64-bit integer'.format(sid))

        # packet_size must exist and be an unsigned integer
        if 'packet_size' not in fields:
            _perror('stream {}: packet context: missing "packet_size" field'.format(sid))

        try:
            self._validate_integer(fields['packet_size'], 32, 32, False)
        except:
            try:
                self._validate_integer(fields['packet_size'], 64, 64, False)
            except:
                _perror('stream {}: packet context: "packet_size": expecting unsigned 32-bit/64-bit integer'.format(sid))

        # if cpu_id exists, must be an unsigned integer
        if 'cpu_id' in fields:
            try:
                self._validate_integer(fields['cpu_id'], signed=False)
            except RuntimeError as e:
                _perror('stream {}: packet context: "cpu_id": {}'.format(sid, e))

    # Validates an event header.
    #
    #   stream: TSDL stream containing the event header to validate
    def _validate_seh(self, stream):
        event_header = stream.event_header
        sid = stream.id

        try:
            self._validate_struct(event_header, True)
        except RuntimeError as e:
            _perror('stream {}: event header: {}'.format(sid, e))

        fields = event_header.fields

        # id must exist and be an unsigned integer
        if 'id' not in fields:
            _perror('stream {}: event header: missing "id" field'.format(sid))

        try:
            self._validate_integer(fields['id'], signed=False)
        except RuntimeError as e:
            _perror('stream {}: "id": {}'.format(sid, format(e)))

        # timestamp must exist, be an unsigned integer and be mapped to a valid clock
        if 'timestamp' not in fields:
            _perror('stream {}: event header: missing "timestamp" field'.format(sid))

        try:
            self._validate_integer(fields['timestamp'], signed=False)
        except RuntimeError as e:
            _perror('stream {}: event header: "timestamp": {}'.format(sid, format(e)))

        if fields['timestamp'].map is None:
            _perror('stream {}: event header: "timestamp" must be mapped to a valid clock'.format(sid))

        # id must be the first field, followed by timestamp
        if list(fields.keys())[0] != 'id':
            _perror('stream {}: event header: "id" must be the first field'.format(sid))

        if list(fields.keys())[1] != 'timestamp':
            _perror('stream {}: event header: "timestamp" must be the second field'.format(sid))

        # only id and timestamp and allowed in event header
        if len(fields) != 2:
            _perror('stream {}: event header: only "id" and "timestamp" fields are allowed'.format(sid))

    # Validates a strean event context.
    #
    #   stream: TSDL stream containing the stream event context
    def _validate_sec(self, stream):
        stream_event_context = stream.event_context
        sid = stream.id

        if stream_event_context is None:
            return

        try:
            self._validate_context_fields(stream_event_context)
        except RuntimeError as e:
            _perror('stream {}: event context: {}'.format(sid, e))

    # Validates an event context.
    #
    #   stream: TSDL stream containing the TSDL event
    #   event:  TSDL event containing the context to validate
    def _validate_ec(self, stream, event):
        event_context = event.context
        sid = stream.id
        eid = event.id

        if event_context is None:
            return

        try:
            self._validate_context_fields(event_context)
        except RuntimeError as e:
            _perror('stream {}: event {}: context: {}'.format(sid, eid, e))

    # Validates an event fields.
    #
    #   stream: TSDL stream containing the TSDL event
    #   event:  TSDL event containing the fields to validate
    def _validate_ef(self, stream, event):
        event_fields = event.fields
        sid = stream.id
        eid = event.id

        try:
            self._validate_context_fields(event_fields)
        except RuntimeError as e:
            _perror('stream {}: event {}: fields: {}'.format(sid, eid, e))

    # Validates a TSDL event.
    #
    #   stream: TSDL stream containing the TSDL event
    #   event:  TSDL event to validate
    def _validate_event(self, stream, event):
        # name must be a compatible C identifier
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', event.name):
            fmt = 'stream {}: event {}: malformed event name: "{}"'
            _perror(fmt.format(stream.id, event.id, event.name))

        self._validate_ec(stream, event)
        self._validate_ef(stream, event)

    # Validates a TSDL stream.
    #
    #   stream: TSDL stream to validate
    def _validate_stream(self, stream):
        self._validate_seh(stream)
        self._validate_spc(stream)
        self._validate_sec(stream)

        # event stuff
        for event in stream.events:
            self._validate_event(stream, event)

    # Validates all TSDL scopes of the current TSDL document.
    def _validate_all_scopes(self):
        # packet header
        self._validate_tph(self._doc.trace.packet_header)

        # stream stuff
        for stream in self._doc.streams.values():
            self._validate_stream(stream)

    # Validates the trace block.
    def _validate_trace(self):
        # make sure a native byte order is specified
        if self._doc.trace.byte_order is None:
            _perror('native byte order (trace.byte_order) is not specified')

    # Validates the current TSDL document.
    def _validate_metadata(self):
        self._validate_trace()
        self._validate_all_scopes()

    # Returns an aligned number.
    #
    # 3, 4 -> 4
    # 4, 4 -> 4
    # 5, 4 -> 8
    # 6, 4 -> 8
    # 7, 4 -> 8
    # 8, 4 -> 8
    # 9, 4 -> 12
    #
    #   at:    number to align
    #   align: alignment (power of two)
    def _get_alignment(self, at, align):
        return (at + align - 1) & -align

    # Converts a tree of offset variables:
    #
    #     field
    #       a -> 0
    #       b -> 8
    #       other_struct
    #         field -> 16
    #         yeah -> 20
    #       c -> 32
    #     len -> 36
    #
    # to a flat dict:
    #
    #     field_a -> 0
    #     field_b -> 8
    #     field_other_struct_field -> 16
    #     field_other_struct_yeah -> 20
    #     field_c -> 32
    #     len -> 36
    #
    #   offvars_tree: tree of offset variables
    #   prefix:       offset variable name prefix
    #   offvars:      flattened offset variables
    def _flatten_offvars_tree(self, offvars_tree, prefix=None,
                              offvars=None):
        if offvars is None:
            offvars = collections.OrderedDict()

        for name, offset in offvars_tree.items():
            if prefix is not None:
                varname = '{}_{}'.format(prefix, name)
            else:
                varname = name

            if isinstance(offset, dict):
                self._flatten_offvars_tree(offset, varname, offvars)
            else:
                offvars[varname] = offset

        return offvars

    # Returns the size of a TSDL structure with _static size_ (must be
    # validated first).
    #
    #   struct:       TSDL structure of which to get the size
    #   offvars_tree: optional offset variables tree (output)
    #   base_offset:  base offsets for offset variables
    def _get_struct_size(self, struct,
                         offvars_tree=None,
                         base_offset=0):
        if offvars_tree is None:
            offvars_tree = collections.OrderedDict()

        offset = 0

        for fname, ftype in struct.fields.items():
            field_alignment = self._get_obj_alignment(ftype)
            offset = self._get_alignment(offset, field_alignment)

            if type(ftype) is pytsdl.tsdl.Struct:
                offvars_tree[fname] = collections.OrderedDict()
                sz = self._get_struct_size(ftype, offvars_tree[fname],
                                      base_offset + offset)
            else:
                # only integers may act as sequence lengths
                if type(ftype) is pytsdl.tsdl.Integer:
                    offvars_tree[fname] = base_offset + offset

                sz = self._get_obj_size(ftype)

            offset += sz

        return offset

    # Returns the size of a TSDL array.
    #
    #   array: TSDL array of which to get the size
    def _get_array_size(self, array):
        element = array.element

        # effective size of one element includes its alignment after its size
        size = self._get_obj_size(element)
        align = self._get_obj_alignment(element)

        return self._get_alignment(size, align) * array.length

    # Returns the size of a TSDL enumeration.
    #
    #   enum: TSDL enumeration of which to get the size
    def _get_enum_size(self, enum):
        return self._get_obj_size(enum.integer)

    # Returns the size of a TSDL floating point number.
    #
    #   floating_point: TSDL floating point number of which to get the size
    def _get_floating_point_size(self, floating_point):
        return floating_point.exp_dig + floating_point.mant_dig

    # Returns the size of a TSDL integer.
    #
    #   integer: TSDL integer of which to get the size
    def _get_integer_size(self, integer):
        return integer.size

    # Returns the size of a TSDL type.
    #
    #   obj: TSDL type of which to get the size
    def _get_obj_size(self, obj):
        return self._obj_size_cb[type(obj)](obj)

    # Returns the alignment of a TSDL structure.
    #
    #   struct: TSDL structure of which to get the alignment
    def _get_struct_alignment(self, struct):
        if struct.align is not None:
            return struct.align

        cur_align = 1

        for fname, ftype in struct.fields.items():
            cur_align = max(self._get_obj_alignment(ftype), cur_align)

        return cur_align

    # Returns the alignment of a TSDL integer.
    #
    #   integer: TSDL integer of which to get the alignment
    def _get_integer_alignment(self, integer):
        return integer.align

    # Returns the alignment of a TSDL floating point number.
    #
    #   floating_point: TSDL floating point number of which to get the
    #                   alignment
    def _get_floating_point_alignment(self, floating_point):
        return floating_point.align

    # Returns the alignment of a TSDL enumeration.
    #
    #   enum: TSDL enumeration of which to get the alignment
    def _get_enum_alignment(self, enum):
        return self._get_obj_alignment(enum.integer)

    # Returns the alignment of a TSDL string.
    #
    #   string: TSDL string of which to get the alignment
    def _get_string_alignment(self, string):
        return 8

    # Returns the alignment of a TSDL array.
    #
    #   array: TSDL array of which to get the alignment
    def _get_array_alignment(self, array):
        return self._get_obj_alignment(array.element)

    # Returns the alignment of a TSDL sequence.
    #
    #   sequence: TSDL sequence of which to get the alignment
    def _get_sequence_alignment(self, sequence):
        return self._get_obj_alignment(sequence.element)

    # Returns the alignment of a TSDL type.
    #
    #   obj: TSDL type of which to get the alignment
    def _get_obj_alignment(self, obj):
        return self._obj_alignment_cb[type(obj)](obj)

    # Converts a field name to a C parameter name.
    #
    # You should not use this function directly, but rather use one
    # of the _*_fname_to_pname() variants depending on your scope.
    #
    #   prefix: parameter name prefix
    #   fname:  field name
    def _fname_to_pname(self, prefix, fname):
        return 'param_{}_{}'.format(prefix, fname)

    # Converts an event fields field name to a C parameter name.
    #
    #   fname: field name
    def _ef_fname_to_pname(self, fname):
        return self._fname_to_pname('ef', fname)

    # Converts an event context field name to a C parameter name.
    #
    #   fname: field name
    def _ec_fname_to_pname(self, fname):
        return self._fname_to_pname('ec', fname)

    # Converts a stream event context field name to a C parameter name.
    #
    #   fname: field name
    def _sec_fname_to_pname(self, fname):
        return self._fname_to_pname('sec', fname)

    # Converts an event header field name to a C parameter name.
    #
    #   fname: field name
    def _eh_fname_to_pname(self, fname):
        return self._fname_to_pname('eh', fname)

    # Converts a stream packet context field name to a C parameter name.
    #
    #   fname: field name
    def _spc_fname_to_pname(self, fname):
        return self._fname_to_pname('spc', fname)

    # Converts a trace packet header field name to a C parameter name.
    #
    #   fname: field name
    def _tph_fname_to_pname(self, fname):
        return self._fname_to_pname('tph', fname)

    # Returns the equivalent C type of a TSDL integer.
    #
    #   integer: TSDL integer of which to get the equivalent C type
    def _get_integer_param_ctype(self, integer):
        signed = 'u' if not integer.signed else ''

        if integer.size <= 8:
            sz = '8'
        elif integer.size <= 16:
            sz = '16'
        elif integer.size <= 32:
            sz = '32'
        elif integer.size == 64:
            sz = '64'

        return '{}int{}_t'.format(signed, sz)

    # Returns the equivalent C type of a TSDL enumeration.
    #
    #   enum: TSDL enumeration of which to get the equivalent C type
    def _get_enum_param_ctype(self, enum):
        return self._get_obj_param_ctype(enum.integer)

    # Returns the equivalent C type of a TSDL floating point number.
    #
    #   fp: TSDL floating point number of which to get the equivalent C type
    def _get_floating_point_param_ctype(self, fp):
        if fp.exp_dig == 8 and fp.mant_dig == 24 and fp.align == 32:
            return 'float'
        elif fp.exp_dig == 11 and fp.mant_dig == 53 and fp.align == 64:
            return 'double'
        else:
            return 'uint64_t'

    # Returns the equivalent C type of a TSDL type.
    #
    #   obj: TSDL type of which to get the equivalent C type
    def _get_obj_param_ctype(self, obj):
        return self._obj_param_ctype_cb[type(obj)](obj)

    # Returns the check offset overflow macro call string for a given size.
    #
    #   size: size to check
    def _get_chk_offset_v(self, size):
        fmt = '{}_CHK_OFFSET_V({}, {}, {});'
        ret = fmt.format(self._prefix.upper(), self._CTX_AT,
                       self._CTX_PACKET_SIZE, size)

        return ret

    # Returns the check offset overflow macro call C line for a given size.
    #
    #   size: size to check
    def _get_chk_offset_v_cline(self, size):
        return _CLine(self._get_chk_offset_v(size))

    # Returns the offset alignment macro call string for a given alignment.
    #
    #   size: new alignment
    def _get_align_offset(self, align, at=None):
        if at is None:
            at = self._CTX_AT

        fmt = '{}_ALIGN_OFFSET({}, {});'
        ret = fmt.format(self._prefix.upper(), at, align)

        return ret

    # Returns the offset alignment macro call C line for a given alignment.
    #
    #   size: new alignment
    def _get_align_offset_cline(self, size):
        return _CLine(self._get_align_offset(size))

    # Converts a C source string with newlines to an array of C lines and
    # returns it.
    #
    #   s: C source string
    def _str_to_clines(self, s):
        lines = s.split('\n')

        return [_CLine(line) for line in lines]

    # Fills a given template with values and returns its C lines. The `prefix`
    # and `ucprefix` template variable are automatically provided using the
    # generator's context.
    #
    #   tmpl:   template
    #   kwargs: additional template variable values
    def _template_to_clines(self, tmpl, **kwargs):
        s = tmpl.format(prefix=self._prefix, ucprefix=self._prefix.upper(),
                        **kwargs)

        return self._str_to_clines(s)

    # Returns the C lines for writing a TSDL structure field.
    #
    #   fname:    field name
    #   src_name: C source pointer
    #   struct:   TSDL structure
    def _write_field_struct(self, fname, src_name, struct, scope_prefix=None):
        size = self._get_struct_size(struct)
        size_bytes = self._get_alignment(size, 8) // 8
        dst = self._CTX_BUF_AT_ADDR

        return [
            # memcpy() is safe since barectf requires inner structures
            # to be byte-aligned
            self._get_chk_offset_v_cline(size),
            _CLine('memcpy({}, {}, {});'.format(dst, src_name, size_bytes)),
            _CLine('{} += {};'.format(self._CTX_AT, size)),
        ]

    # Returns the C lines for writing a TSDL integer field.
    #
    #   fname:    field name
    #   src_name: C source integer
    #   integer:  TSDL integer
    def _write_field_integer(self, fname, src_name, integer, scope_prefix=None):
        bo = self._BO_SUFFIXES_MAP[integer.byte_order]
        t = self._get_obj_param_ctype(integer)
        length = self._get_obj_size(integer)

        return self._template_to_clines(barectf.templates.WRITE_INTEGER,
                                        sz=length, bo=bo, type=t,
                                        src_name=src_name)

    # Returns the C lines for writing a TSDL enumeration field.
    #
    #   fname:    field name
    #   src_name: C source integer
    #   enum:     TSDL enumeration
    def _write_field_enum(self, fname, src_name, enum, scope_prefix=None):
        return self._write_field_obj(fname, src_name, enum.integer,
                                     scope_prefix)

    # Returns the C lines for writing a TSDL floating point number field.
    #
    #   fname:          field name
    #   src_name:       C source pointer
    #   floating_point: TSDL floating point number
    def _write_field_floating_point(self, fname, src_name, floating_point,
                                    scope_prefix=None):
        bo = self._BO_SUFFIXES_MAP[floating_point.byte_order]
        t = self._get_obj_param_ctype(floating_point)
        length = self._get_obj_size(floating_point)

        if t == 'float':
            t = 'uint32_t'
        elif t == 'double':
            t = 'uint64_t'

        src_name_casted = '*(({}*) &{})'.format(t, src_name)

        return self._template_to_clines(barectf.templates.WRITE_INTEGER,
                                        sz=length, bo=bo, type=t,
                                        src_name=src_name_casted)

    # Returns the C lines for writing either a TSDL array field or a
    # TSDL sequence field.
    #
    #   fname:        field name
    #   src_name:     C source pointer
    #   arrayseq:     TSDL array or sequence
    #   scope_prefix: preferred scope prefix
    def _write_field_array_sequence(self, fname, src_name, arrayseq,
                                    scope_prefix):
        def length_index_varname(index):
            return 'lens_{}_{}'.format(fname, index)

        # first pass: find all lengths to multiply
        mulops = []
        done = False

        while not done:
            mulops.append(arrayseq.length)
            element = arrayseq.element
            tel = type(element)

            if tel is pytsdl.tsdl.Array or tel is pytsdl.tsdl.Sequence:
                # another array/sequence; continue
                arrayseq = element
                continue

            # found the end
            done = True

        # align the size of the repeating element (effective repeating size)
        el_size = self._get_obj_size(element)
        el_align = self._get_obj_alignment(element)
        el_size = self._get_alignment(el_size, el_align)

        # this effective size is part of the operands to multiply
        mulops.append(el_size)

        # clines
        clines = []

        # fetch and save sequence lengths
        emulops = []

        for i in range(len(mulops)):
            mulop = mulops[i]

            if type(mulop) is list:
                # offset variable to fetch
                offvar = self._get_seq_length_src_name(mulop, scope_prefix)

                if type(offvar) is int:
                    # environment constant
                    emulops.append(str(offvar))
                    continue

                # save buffer position
                line = 'ctx_at_bkup = {};'.format(self._CTX_AT)
                clines.append(_CLine(line))

                # go back to field offset
                line = '{} = {};'.format(self._CTX_AT, offvar)
                clines.append(_CLine(line))

                # read value into specific variable
                varname = length_index_varname(i)
                emulops.append(varname)
                varctype = 'uint32_t'
                fmt = '{ctype} {cname} = *(({ctype}*) ({ctxbufataddr}));'
                line = fmt.format(ctype=varctype, cname=varname,
                                  ctxbufataddr=self._CTX_BUF_AT_ADDR)
                clines.append(_CLine(line))

                # restore buffer position
                line = '{} = ctx_at_bkup;'.format(self._CTX_AT)
                clines.append(_CLine(line))
            else:
                emulops.append(str(mulop))

        # write product of sizes in bits
        mul = ' * '.join(emulops)
        sz_bits_varname = 'sz_bits_{}'.format(fname)
        sz_bytes_varname = 'sz_bytes_{}'.format(fname)
        line = 'uint32_t {} = {};'.format(sz_bits_varname, mul)
        clines.append(_CLine(line))

        # check overflow
        clines.append(self._get_chk_offset_v_cline(sz_bits_varname))

        # write product of sizes in bytes
        line = 'uint32_t {} = {};'.format(sz_bytes_varname, sz_bits_varname)
        clines.append(_CLine(line))
        line = self._get_align_offset(8, at=sz_bytes_varname)
        clines.append(_CLine(line))
        line = '{} >>= 3;'.format(sz_bytes_varname)
        clines.append(_CLine(line))

        # memcpy()
        dst = self._CTX_BUF_AT_ADDR
        line = 'memcpy({}, {}, {});'.format(dst, src_name, sz_bytes_varname)
        clines.append(_CLine(line))
        line = '{} += {};'.format(self._CTX_AT, sz_bits_varname)
        clines.append(_CLine(line))

        return clines

    # Returns the C lines for writing a TSDL array field.
    #
    #   fname:        field name
    #   src_name:     C source pointer
    #   array:        TSDL array
    #   scope_prefix: preferred scope prefix
    def _write_field_array(self, fname, src_name, array, scope_prefix=None):
        return self._write_field_array_sequence(fname, src_name, array,
                                                scope_prefix)

    # Returns the C lines for writing a TSDL sequence field.
    #
    #   fname:        field name
    #   src_name:     C source pointer
    #   sequence:     TSDL sequence
    #   scope_prefix: preferred scope prefix
    def _write_field_sequence(self, fname, src_name, sequence, scope_prefix):
        return self._write_field_array_sequence(fname, src_name, sequence,
                                                scope_prefix)

    # Returns a trace packet header C source name out of a sequence length
    # expression.
    #
    #   length: sequence length expression
    def _get_tph_src_name(self, length):
        offvar = self._get_offvar_name_from_expr(length[3:], 'tph')

        return 'ctx->{}'.format(offvar)

    # Returns an environment C source name out of a sequence length
    # expression.
    #
    #   length: sequence length expression
    def _get_env_src_name(self, length):
        if len(length) != 2:
            _perror('invalid sequence length: "{}"'.format(self._dot_name_to_str(length)))

        fname = length[1]

        if fname not in self._doc.env:
            _perror('cannot find field env.{}'.format(fname))

        env_length = self._doc.env[fname]

        if type(env_length) is not int:
            _perror('env.{} is not a constant integer'.format(fname))

        return self._doc.env[fname]

    # Returns a stream packet context C source name out of a sequence length
    # expression.
    #
    #   length: sequence length expression
    def _get_spc_src_name(self, length):
        offvar = self._get_offvar_name_from_expr(length[3:], 'spc')

        return 'ctx->{}'.format(offvar)

    # Returns a stream event header C source name out of a sequence length
    # expression.
    #
    #   length: sequence length expression
    def _get_seh_src_name(self, length):
        return self._get_offvar_name_from_expr(length[3:], 'seh')

    # Returns a stream event context C source name out of a sequence length
    # expression.
    #
    #   length: sequence length expression
    def _get_sec_src_name(self, length):
        return self._get_offvar_name_from_expr(length[3:], 'sec')

    # Returns an event context C source name out of a sequence length
    # expression.
    #
    #   length: sequence length expression
    def _get_ec_src_name(self, length):
        return self._get_offvar_name_from_expr(length[2:], 'ec')

    # Returns an event fields C source name out of a sequence length
    # expression.
    #
    #   length: sequence length expression
    def _get_ef_src_name(self, length):
        return self._get_offvar_name_from_expr(length[2:], 'ef')

    # Returns a C source name out of a sequence length expression.
    #
    #   length:       sequence length expression
    #   scope_prefix: preferred scope prefix
    def _get_seq_length_src_name(self, length, scope_prefix=None):
        length_dot = self._dot_name_to_str(length)

        for prefix, get_src_name in self._get_src_name_funcs.items():
            if length_dot.startswith(prefix):
                return get_src_name(length)

        return self._get_offvar_name_from_expr(length, scope_prefix)

    # Returns the C lines for writing a TSDL string field.
    #
    #   fname:        field name
    #   src_name:     C source pointer
    #   string:       TSDL string
    def _write_field_string(self, fname, src_name, string, scope_prefix=None):
        clines = []

        # get string length
        sz_bytes_varname = 'slen_bytes_{}'.format(fname)
        line = 'size_t {} = strlen({}) + 1;'.format(sz_bytes_varname, src_name)
        clines.append(_CLine(line))

        # check offset overflow
        sz_bits_varname = 'slen_bits_{}'.format(fname)
        line = 'size_t {} = ({} << 3);'.format(sz_bits_varname,
                                               sz_bytes_varname)
        clines.append(_CLine(line))
        cline = self._get_chk_offset_v_cline(sz_bits_varname)
        clines.append(cline)

        # memcpy()
        dst = self._CTX_BUF_AT_ADDR
        line = 'memcpy({}, {}, {});'.format(dst, src_name, sz_bytes_varname)
        clines.append(_CLine(line))

        # update bit position
        line = '{} += {};'.format(self._CTX_AT, sz_bits_varname)
        clines.append(_CLine(line))

        return clines

    # Returns the C lines for writing a TSDL type field.
    #
    #   fname:        field name
    #   src_name:     C source pointer
    #   ftype:        TSDL type
    #   scope_prefix: preferred scope prefix
    def _write_field_obj(self, fname, src_name, ftype, scope_prefix):
        return self._write_field_obj_cb[type(ftype)](fname, src_name, ftype,
                                                     scope_prefix)

    # Returns an offset variable name out of an offset name.
    #
    #   name:   offset name
    #   prefix: offset variable name prefix
    def _get_offvar_name(self, name, prefix=None):
        parts = ['off']

        if prefix is not None:
            parts.append(prefix)

        parts.append(name)

        return '_'.join(parts)

    # Returns an offset variable name out of an expression (array of
    # strings).
    #
    #   expr:   array of strings
    #   prefix: offset variable name prefix
    def _get_offvar_name_from_expr(self, expr, prefix=None):
        return self._get_offvar_name('_'.join(expr), prefix)

    # Returns the C lines for writing a TSDL field.
    #
    #   fname:         field name
    #   ftype:         TSDL field type
    #   scope_name:    scope name
    #   scope_prefix:  preferred scope prefix
    #   param_name_cb: callback to get the C parameter name out of the
    #                  field name
    def _field_to_clines(self, fname, ftype, scope_name, scope_prefix,
                         param_name_cb):
        clines = []
        pname = param_name_cb(fname)
        align = self._get_obj_alignment(ftype)

        # group comment
        fmt = '/* write {}.{} ({}) */'
        line = fmt.format(scope_name, fname,
                          self._TSDL_TYPE_NAMES_MAP[type(ftype)])
        clines.append(_CLine(line))

        # align bit index before writing to the buffer
        cline = self._get_align_offset_cline(align)
        clines.append(cline)

        # write offset variables
        if type(ftype) is pytsdl.tsdl.Struct:
            offvars_tree = collections.OrderedDict()
            self._get_struct_size(ftype, offvars_tree)
            offvars = self._flatten_offvars_tree(offvars_tree)

            # as many offset as there are child fields because a future
            # sequence could refer to any of those fields
            for lname, offset in offvars.items():
                offvar = self._get_offvar_name('_'.join([fname, lname]),
                                               scope_prefix)
                fmt = 'uint32_t {} = (uint32_t) {} + {};'
                line = fmt.format(offvar, self._CTX_AT, offset);
                clines.append(_CLine(line))
        elif type(ftype) is pytsdl.tsdl.Integer:
            # offset of this simple field is the current bit index
            offvar = self._get_offvar_name(fname, scope_prefix)
            line = 'uint32_t {} = (uint32_t) {};'.format(offvar, self._CTX_AT)
            clines.append(_CLine(line))

        clines += self._write_field_obj(fname, pname, ftype, scope_prefix)

        return clines

    # Joins C line groups and returns C lines.
    #
    #   cline_groups: C line groups to join
    def _join_cline_groups(self, cline_groups):
        if not cline_groups:
            return cline_groups

        output_clines = cline_groups[0]

        for clines in cline_groups[1:]:
            output_clines.append('')
            output_clines += clines

        return output_clines

    # Returns the C lines for writing a complete TSDL structure (top level
    # scope).
    #
    #   struct:        TSDL structure
    #   scope_name:    scope name
    #   scope_prefix:  preferred scope prefix
    #   param_name_cb: callback to get the C parameter name out of the
    #                  field name
    def _struct_to_clines(self, struct, scope_name, scope_prefix,
                          param_name_cb):
        cline_groups = []

        for fname, ftype in struct.fields.items():
            clines = self._field_to_clines(fname, ftype, scope_name,
                                           scope_prefix, param_name_cb)
            cline_groups.append(clines)

        return self._join_cline_groups(cline_groups)

    # Returns the offset variables of a TSDL structure.
    #
    #   struct: TSDL structure
    def _get_struct_size_offvars(self, struct):
        offvars_tree = collections.OrderedDict()
        size = self._get_struct_size(struct, offvars_tree)
        offvars = self._flatten_offvars_tree(offvars_tree)

        return size, offvars

    # Returns the size and offset variables of the current trace packet header.
    def _get_tph_size_offvars(self):
        return self._get_struct_size_offvars(self._doc.trace.packet_header)

    # Returns the size and offset variables of the a stream packet context.
    #
    #   stream: TSDL stream
    def _get_spc_size_offvars(self, stream):
        return self._get_struct_size_offvars(stream.packet_context)

    # Returns the C lines for the barectf context C structure entries for
    # offsets.
    #
    #   prefix:  offset variable names prefix
    #   offvars: offset variables
    def _offvars_to_ctx_clines(self, prefix, offvars):
        clines = []

        for name in offvars.keys():
            offvar = self._get_offvar_name(name, prefix)
            clines.append(_CLine('uint32_t {};'.format(offvar)))

        return clines

    # Generates a barectf context C structure.
    #
    #   stream:   TSDL stream
    #   hide_sid: True to hide the stream ID
    def _gen_barectf_ctx_struct(self, stream, hide_sid=False):
        # get offset variables for both the packet header and packet context
        tph_size, tph_offvars = self._get_tph_size_offvars()
        spc_size, spc_offvars = self._get_spc_size_offvars(stream)
        clines = self._offvars_to_ctx_clines('tph', tph_offvars)
        clines += self._offvars_to_ctx_clines('spc', spc_offvars)

        # indent C
        clines_indented = []
        for cline in clines:
            clines_indented.append(_CLine('\t' + cline))

        # clock callback
        clock_cb = '\t/* (no clock callback) */'

        if not self._manual_clock:
            ctype = self._get_clock_ctype(stream)
            fmt = '\t{} (*clock_cb)(void*);\n\tvoid* clock_cb_data;'
            clock_cb = fmt.format(ctype)

        # fill template
        sid = ''

        if not hide_sid:
            sid = stream.id

        t = barectf.templates.BARECTF_CTX
        struct = t.format(prefix=self._prefix, sid=sid,
                          ctx_fields='\n'.join(clines_indented),
                          clock_cb=clock_cb)

        return struct

    # Generates all barectf context C structures.
    def _gen_barectf_contexts_struct(self):
        hide_sid = False

        if len(self._doc.streams) == 1:
            hide_sid = True

        structs = []

        for stream in self._doc.streams.values():
            struct = self._gen_barectf_ctx_struct(stream, hide_sid)
            structs.append(struct)

        return '\n\n'.join(structs)

    # Returns the C type of the clock used by the event header of a
    # TSDL stream.
    #
    #   stream: TSDL stream containing the event header to inspect
    def _get_clock_ctype(self, stream):
        return self._get_obj_param_ctype(stream.event_header['timestamp'])

    # Generates the manual clock value C parameter for a given stream.
    #
    #   stream: TSDL stream
    def _gen_manual_clock_param(self, stream):
        return '{} param_clock'.format(self._get_clock_ctype(stream))

    # Generates the body of a barectf_open() function.
    #
    #   stream: TSDL stream
    def _gen_barectf_func_open_body(self, stream):
        clines = []

        # keep clock value (for timestamp_begin)
        if self._stream_has_timestamp_begin_end(stream):
            # get clock value ASAP
            clk_type = self._get_clock_ctype(stream)
            clk = self._gen_get_clock_value()
            line = '{} clk_value = {};'.format(clk_type, clk)
            clines.append(_CLine(line))
            clines.append(_CLine(''))

        # reset bit position to write the packet context (after packet header)
        spc_offset = self._get_stream_packet_context_offset(stream)
        fmt = '{} = {};'
        line = fmt.format(self._CTX_AT, spc_offset)
        clines.append(_CLine(line))

        # bit position at beginning of event (to reset in case we run
        # out of space)
        line = 'uint32_t ctx_at_begin = {};'.format(self._CTX_AT)
        clines.append(_CLine(line))
        clines.append(_CLine(''))

        # packet context fields
        fcline_groups = []
        scope_name = 'stream.packet.context'
        scope_prefix = 'spc'

        for fname, ftype in stream.packet_context.fields.items():
            # packet size
            if fname == 'packet_size':
                fclines = self._field_to_clines(fname, ftype, scope_name,
                                                scope_prefix,
                                                lambda x: 'ctx->packet_size')
                fcline_groups.append(fclines)

            # content size (skip)
            elif fname == 'content_size':
                fclines = self._field_to_clines(fname, ftype, scope_name,
                                                scope_prefix, lambda x: '0')
                fcline_groups.append(fclines)

            # timestamp_begin
            elif fname == 'timestamp_begin':
                fclines = self._field_to_clines(fname, ftype, scope_name,
                                                scope_prefix,
                                                lambda x: 'clk_value')
                fcline_groups.append(fclines)

            # timestamp_end (skip)
            elif fname == 'timestamp_end':
                fclines = self._field_to_clines(fname, ftype, scope_name,
                                                scope_prefix, lambda x: '0')
                fcline_groups.append(fclines)

            # anything else
            else:
                fclines = self._field_to_clines(fname, ftype, scope_name,
                                                scope_prefix,
                                                self._spc_fname_to_pname)
                fcline_groups.append(fclines)

        # return 0
        fcline_groups.append([_CLine('return 0;')])

        clines += self._join_cline_groups(fcline_groups)

        # get source
        cblock = _CBlock(clines)
        src = self._cblock_to_source(cblock)

        return src

    _SPC_KNOWN_FIELDS = [
        'content_size',
        'packet_size',
        'timestamp_begin',
        'timestamp_end',
    ]

    # Generates a barectf_open() function.
    #
    #   stream:   TSDL stream
    #   gen_body: also generate function body
    #   hide_sid: True to hide the stream ID
    def _gen_barectf_func_open(self, stream, gen_body, hide_sid=False):
        params = []

        # manual clock
        if self._manual_clock:
            clock_param = self._gen_manual_clock_param(stream)
            params.append(clock_param)

        # packet context
        for fname, ftype in stream.packet_context.fields.items():
            if fname in self._SPC_KNOWN_FIELDS:
                continue

            ptype = self._get_obj_param_ctype(ftype)
            pname = self._spc_fname_to_pname(fname)
            param = '{} {}'.format(ptype, pname)
            params.append(param)

        params_str = ''

        if params:
            params_str = ',\n\t'.join([''] + params)

        # fill template
        sid = ''

        if not hide_sid:
            sid = stream.id

        t = barectf.templates.FUNC_OPEN
        func = t.format(si=self._si_str, prefix=self._prefix, sid=sid,
                        params=params_str)

        if gen_body:
            func += '\n{\n'
            func += self._gen_barectf_func_open_body(stream)
            func += '\n}'
        else:
            func += ';'

        return func

    # Generates the body of a barectf_init() function.
    #
    #   stream: TSDL stream
    def _gen_barectf_func_init_body(self, stream):
        clines = []

        line = 'uint32_t ctx_at_bkup;'
        clines.append(_CLine(line))

        # bit position at beginning of event (to reset in case we run
        # out of space)
        line = 'uint32_t ctx_at_begin = {};'.format(self._CTX_AT)
        clines.append(_CLine(line))
        clines.append(_CLine(''))

        # set context parameters
        clines.append(_CLine("/* barectf context parameters */"))
        clines.append(_CLine('ctx->buf = buf;'))
        clines.append(_CLine('ctx->packet_size = buf_size * 8;'))
        clines.append(_CLine('{} = 0;'.format(self._CTX_AT)))

        if not self._manual_clock:
            clines.append(_CLine('ctx->clock_cb = clock_cb;'))
            clines.append(_CLine('ctx->clock_cb_data = clock_cb_data;'))

        # set context offsets
        clines.append(_CLine(''))
        clines.append(_CLine("/* barectf context offsets */"))
        ph_size, ph_offvars = self._get_tph_size_offvars()
        pc_size, pc_offvars = self._get_spc_size_offvars(stream)
        pc_alignment = self._get_obj_alignment(stream.packet_context)
        pc_offset = self._get_alignment(ph_size, pc_alignment)

        for offvar, offset in ph_offvars.items():
            offvar_field = self._get_offvar_name(offvar, 'tph')
            line = 'ctx->{} = {};'.format(offvar_field, offset)
            clines.append(_CLine(line))

        for offvar, offset in pc_offvars.items():
            offvar_field = self._get_offvar_name(offvar, 'spc')
            line = 'ctx->{} = {};'.format(offvar_field, pc_offset + offset)
            clines.append(_CLine(line))

        clines.append(_CLine(''))

        # packet header fields
        fcline_groups = []
        scope_name = 'trace.packet.header'
        scope_prefix = 'tph'

        for fname, ftype in self._doc.trace.packet_header.fields.items():
            # magic number
            if fname == 'magic':
                fclines = self._field_to_clines(fname, ftype, scope_name,
                                                scope_prefix,
                                                lambda x: '0xc1fc1fc1UL')
                fcline_groups.append(fclines)

            # stream ID
            elif fname == 'stream_id':
                fclines = self._field_to_clines(fname, ftype, scope_name,
                                                scope_prefix,
                                                lambda x: str(stream.id))
                fcline_groups.append(fclines)

        # return 0
        fcline_groups.append([_CLine('return 0;')])

        clines += self._join_cline_groups(fcline_groups)

        # get source
        cblock = _CBlock(clines)
        src = self._cblock_to_source(cblock)

        return src

    # Generates a barectf_init() function.
    #
    #   stream:   TSDL stream
    #   gen_body: also generate function body
    #   hide_sid: True to hide the stream ID
    def _gen_barectf_func_init(self, stream, gen_body, hide_sid=False):
        # fill template
        sid = ''

        if not hide_sid:
            sid = stream.id

        params = ''

        if not self._manual_clock:
            ts_ftype = stream.event_header['timestamp']
            ts_ptype = self._get_obj_param_ctype(ts_ftype)
            fmt = ',\n\t{} (*clock_cb)(void*),\n\tvoid* clock_cb_data'
            params = fmt.format(ts_ptype)

        t = barectf.templates.FUNC_INIT
        func = t.format(si=self._si_str, prefix=self._prefix, sid=sid,
                        params=params)

        if gen_body:
            func += '\n{\n'
            func += self._gen_barectf_func_init_body(stream)
            func += '\n}'
        else:
            func += ';'

        return func

    # Generates the C expression to get the clock value depending on
    # whether we're in manual clock mode or not.
    def _gen_get_clock_value(self):
        if self._manual_clock:
            return 'param_clock'
        else:
            return self._CTX_CALL_CLOCK_CB

    # Returns True if the given TSDL stream has timestamp_begin and
    # timestamp_end fields.
    #
    #   stream: TSDL stream to check
    def _stream_has_timestamp_begin_end(self, stream):
        return self._has_timestamp_begin_end[stream.id]

    # Returns the packet context offset (from the beginning of the
    # packet) of a given TSDL stream
    #
    #   stream: TSDL stream
    def _get_stream_packet_context_offset(self, stream):
        return self._packet_context_offsets[stream.id]

    # Generates the C lines to write a barectf context field, saving
    # and restoring the current bit position accordingly.
    #
    #   src_name: C source name
    #   prefix:   offset variable prefix
    #   name:     offset variable name
    #   integer:  TSDL integer to write
    def _gen_write_ctx_field_integer(self, src_name, prefix, name, integer):
        clines = []

        # save buffer position
        line = 'ctx_at_bkup = {};'.format(self._CTX_AT)
        clines.append(_CLine(line))

        # go back to field offset
        offvar = self._get_offvar_name(name, prefix)
        line = '{} = ctx->{};'.format(self._CTX_AT, offvar)
        clines.append(_CLine(line))

        # write value
        clines += self._write_field_integer(None, src_name, integer)

        # restore buffer position
        line = '{} = ctx_at_bkup;'.format(self._CTX_AT)
        clines.append(_CLine(line))

        return clines

    # Generates the body of a barectf_close() function.
    #
    #   stream: TSDL stream
    def _gen_barectf_func_close_body(self, stream):
        clines = []

        line = 'uint32_t ctx_at_bkup;'
        clines.append(_CLine(line))

        # bit position at beginning of event (to reset in case we run
        # out of space)
        line = 'uint32_t ctx_at_begin = {};'.format(self._CTX_AT)
        clines.append(_CLine(line))

        # update timestamp end if present
        if self._stream_has_timestamp_begin_end(stream):
            clines.append(_CLine(''))
            clines.append(_CLine("/* update packet context's timestamp_end */"))

            # get clock value ASAP
            clk_type = self._get_clock_ctype(stream)
            clk = self._gen_get_clock_value()
            line = '{} clk_value = {};'.format(clk_type, clk)
            clines.append(_CLine(line))

            # write timestamp_end
            timestamp_end_integer = stream.packet_context['timestamp_end']
            clines += self._gen_write_ctx_field_integer('clk_value', 'spc',
                                                        'timestamp_end',
                                                        timestamp_end_integer)

        # update content_size
        clines.append(_CLine(''))
        clines.append(_CLine("/* update packet context's content_size */"))
        content_size_integer = stream.packet_context['content_size']
        clines += self._gen_write_ctx_field_integer('ctx_at_bkup', 'spc',
                                                    'content_size',
                                                    content_size_integer)

        # return 0
        clines.append(_CLine('\n'))
        clines.append(_CLine('return 0;'))

        # get source
        cblock = _CBlock(clines)
        src = self._cblock_to_source(cblock)

        return src

    # Generates a barectf_close() function.
    #
    #   stream:   TSDL stream
    #   gen_body: also generate function body
    #   hide_sid: True to hide the stream ID
    def _gen_barectf_func_close(self, stream, gen_body, hide_sid=False):
        # fill template
        sid = ''

        if not hide_sid:
            sid = stream.id

        params = ''

        if self._manual_clock:
            clock_param = self._gen_manual_clock_param(stream)
            params = ',\n\t{}'.format(clock_param)

        t = barectf.templates.FUNC_CLOSE
        func = t.format(si=self._si_str, prefix=self._prefix, sid=sid,
                        params=params)

        if gen_body:
            func += '\n{\n'
            func += self._gen_barectf_func_close_body(stream)
            func += '\n}'
        else:
            func += ';'

        return func

    # Generates all barectf_init() function.
    #
    #   gen_body: also generate function bodies
    def _gen_barectf_funcs_init(self, gen_body):
        hide_sid = False

        if len(self._doc.streams) == 1:
            hide_sid = True

        funcs = []

        for stream in self._doc.streams.values():
            funcs.append(self._gen_barectf_func_init(stream, gen_body,
                                                     hide_sid))

        return funcs

    # Generates all barectf_open() function.
    #
    #   gen_body: also generate function bodies
    def _gen_barectf_funcs_open(self, gen_body):
        hide_sid = False

        if len(self._doc.streams) == 1:
            hide_sid = True

        funcs = []

        for stream in self._doc.streams.values():
            funcs.append(self._gen_barectf_func_open(stream, gen_body,
                                                     hide_sid))

        return funcs

    # Generates the body of a barectf_trace() function.
    #
    #   stream: TSDL stream of TSDL event to trace
    #   event:  TSDL event to trace
    def _gen_barectf_func_trace_event_body(self, stream, event):
        clines = []

        # get clock value ASAP
        clk_type = self._get_clock_ctype(stream)
        clk = self._gen_get_clock_value()
        line = '{} clk_value = {};'.format(clk_type, clk)
        clines.append(_CLine(line))
        clines.append(_CLine(''))

        # bit position backup (could be used)
        clines.append(_CLine('uint32_t ctx_at_bkup;'))

        # bit position at beginning of event (to reset in case we run
        # out of space)
        line = 'uint32_t ctx_at_begin = {};'.format(self._CTX_AT)
        clines.append(_CLine(line))
        clines.append(_CLine(''))

        # event header
        fcline_groups = []
        scope_name = 'event.header'
        scope_prefix = 'eh'

        for fname, ftype in stream.event_header.fields.items():
            # id
            if fname == 'id':
                fclines = self._field_to_clines(fname, ftype, scope_name,
                                                scope_prefix,
                                                lambda x: str(event.id))
                fcline_groups.append(fclines)

            # timestamp
            elif fname == 'timestamp':
                fclines = self._field_to_clines(fname, ftype, scope_name,
                                                scope_prefix,
                                                lambda x: 'clk_value')
                fcline_groups.append(fclines)

        # stream event context
        if stream.event_context is not None:
            fclines = self._struct_to_clines(stream.event_context,
                                             'stream.event.context', 'sec',
                                             self._sec_fname_to_pname)
            fcline_groups.append(fclines)

        # event context
        if event.context is not None:
            fclines = self._struct_to_clines(event.context,
                                             'event.context', 'ec',
                                             self._ec_fname_to_pname)
            fcline_groups.append(fclines)

        # event fields
        if event.fields is not None:
            fclines = self._struct_to_clines(event.fields,
                                             'event.fields', 'ef',
                                             self._ef_fname_to_pname)
            fcline_groups.append(fclines)

        # return 0
        fcline_groups.append([_CLine('return 0;')])

        clines += self._join_cline_groups(fcline_groups)

        # get source
        cblock = _CBlock(clines)
        src = self._cblock_to_source(cblock)

        return src

    # Generates a barectf_trace() function.
    #
    #   stream:   TSDL stream containing the TSDL event to trace
    #   event:    TSDL event to trace
    #   gen_body: also generate function body
    #   hide_sid: True to hide the stream ID
    def _gen_barectf_func_trace_event(self, stream, event, gen_body, hide_sid):
        params = []

        # manual clock
        if self._manual_clock:
            clock_param = self._gen_manual_clock_param(stream)
            params.append(clock_param)

        # stream event context params
        if stream.event_context is not None:
            for fname, ftype in stream.event_context.fields.items():
                ptype = self._get_obj_param_ctype(ftype)
                pname = self._sec_fname_to_pname(fname)
                param = '{} {}'.format(ptype, pname)
                params.append(param)

        # event context params
        if event.context is not None:
            for fname, ftype in event.context.fields.items():
                ptype = self._get_obj_param_ctype(ftype)
                pname = self._ec_fname_to_pname(fname)
                param = '{} {}'.format(ptype, pname)
                params.append(param)

        # event fields params
        if event.fields is not None:
            for fname, ftype in event.fields.fields.items():
                ptype = self._get_obj_param_ctype(ftype)
                pname = self._ef_fname_to_pname(fname)
                param = '{} {}'.format(ptype, pname)
                params.append(param)

        params_str = ''

        if params:
            params_str = ',\n\t'.join([''] + params)

        # fill template
        sid = ''

        if not hide_sid:
            sid = stream.id

        t = barectf.templates.FUNC_TRACE
        func = t.format(si=self._si_str, prefix=self._prefix, sid=sid,
                        evname=event.name, params=params_str)

        if gen_body:
            func += '\n{\n'
            func += self._gen_barectf_func_trace_event_body(stream, event)
            func += '\n}'
        else:
            func += ';'

        return func

    # Generates all barectf_trace() functions of a given TSDL stream.
    #
    #   stream:   TSDL stream containing the TSDL events to trace
    #   gen_body: also generate function body
    #   hide_sid: True to hide the stream ID
    def _gen_barectf_funcs_trace_stream(self, stream, gen_body, hide_sid):
        funcs = []

        for event in stream.events:
            funcs.append(self._gen_barectf_func_trace_event(stream, event,
                                                            gen_body, hide_sid))

        return funcs

    # Generates all barectf_trace() function.
    #
    #   gen_body: also generate function bodies
    def _gen_barectf_funcs_trace(self, gen_body):
        hide_sid = False

        if len(self._doc.streams) == 1:
            hide_sid = True

        funcs = []

        for stream in self._doc.streams.values():
            funcs += self._gen_barectf_funcs_trace_stream(stream, gen_body,
                                                          hide_sid)

        return funcs

    # Generates all barectf_close() function.
    #
    #   gen_body: also generate function bodies
    def _gen_barectf_funcs_close(self, gen_body):
        hide_sid = False

        if len(self._doc.streams) == 1:
            hide_sid = True

        funcs = []

        for stream in self._doc.streams.values():
            funcs.append(self._gen_barectf_func_close(stream, gen_body,
                                                      hide_sid))

        return funcs

    # Generate all barectf functions
    #
    #   gen_body: also generate function bodies
    def _gen_barectf_functions(self, gen_body):
        init_funcs = self._gen_barectf_funcs_init(gen_body)
        open_funcs = self._gen_barectf_funcs_open(gen_body)
        close_funcs = self._gen_barectf_funcs_close(gen_body)
        trace_funcs = self._gen_barectf_funcs_trace(gen_body)

        return init_funcs + open_funcs + close_funcs + trace_funcs

    # Generates the barectf header C source
    def _gen_barectf_header(self):
        ctx_structs = self._gen_barectf_contexts_struct()
        functions = self._gen_barectf_functions(self._static_inline)
        functions_str = '\n\n'.join(functions)
        t = barectf.templates.HEADER
        header = t.format(prefix=self._prefix, ucprefix=self._prefix.upper(),
                          barectf_ctx=ctx_structs, functions=functions_str)

        return header

    _BO_DEF_MAP = {
        pytsdl.tsdl.ByteOrder.BE: 'BIG_ENDIAN',
        pytsdl.tsdl.ByteOrder.LE: 'LITTLE_ENDIAN',
    }

    # Generates the barectf bitfield.h header.
    def _gen_barectf_bitfield_header(self):
        header = barectf.templates.BITFIELD
        header = header.replace('$prefix$', self._prefix)
        header = header.replace('$PREFIX$', self._prefix.upper())
        endian_def = self._BO_DEF_MAP[self._doc.trace.byte_order]
        header = header.replace('$ENDIAN_DEF$', endian_def)

        return header

    # Generates the main barectf C source file.
    def _gen_barectf_csrc(self):
        functions = self._gen_barectf_functions(True)
        functions_str = '\n\n'.join(functions)
        t = barectf.templates.CSRC
        csrc = t.format(prefix=self._prefix, ucprefix=self._prefix.upper(),
                        functions=functions_str)

        return csrc

    # Writes a file to the generator's output.
    #
    #   name:     file name
    #   contents: file contents
    def _write_file(self, name, contents):
        path = os.path.join(self._output, name)
        try:
            with open(path, 'w') as f:
                f.write(contents)
        except Exception as e:
            _perror('cannot write "{}": {}'.format(path, e))

    # Converts a C block to actual C source lines.
    #
    #   cblock: C block
    #   indent: initial indentation
    def _cblock_to_source_lines(self, cblock, indent=1):
        src = []
        indentstr = '\t' * indent

        for line in cblock:
            if type(line) is _CBlock:
                src += self._cblock_to_source_lines(line, indent + 1)
            else:
                src.append(indentstr + line)

        return src

    # Converts a C block to an actual C source string.
    #
    #   cblock: C block
    #   indent: initial indentation
    def _cblock_to_source(self, cblock, indent=1):
        lines = self._cblock_to_source_lines(cblock, indent)

        return '\n'.join(lines)

    # Sets the generator parameters.
    def _set_params(self):
        # streams have timestamp_begin/timestamp_end fields
        self._has_timestamp_begin_end = {}

        for stream in self._doc.streams.values():
            has = 'timestamp_begin' in stream.packet_context.fields
            self._has_timestamp_begin_end[stream.id] = has

        # packet header size with alignment
        self._packet_context_offsets = {}

        tph_size = self._get_struct_size(self._doc.trace.packet_header)

        for stream in self._doc.streams.values():
            spc_alignment = self._get_obj_alignment(stream.packet_context)
            spc_offset = self._get_alignment(tph_size, spc_alignment)
            self._packet_context_offsets[stream.id] = spc_offset

    # Generates barectf C files.
    #
    #   metadata:      metadata path
    #   output:        output directory
    #   prefix:        prefix
    #   static_inline: generate static inline functions
    #   manual_clock:  do not use a clock callback: pass clock value to
    #                  tracing functions
    def gen_barectf(self, metadata, output, prefix, static_inline,
                    manual_clock):
        self._metadata = metadata
        self._output = output
        self._prefix = prefix
        self._static_inline = static_inline
        self._manual_clock = manual_clock
        self._si_str = ''

        if static_inline:
            self._si_str = 'static inline '

        # open CTF metadata file
        _pinfo('opening CTF metadata file "{}"'.format(self._metadata))

        try:
            with open(metadata) as f:
                self._tsdl = f.read()
        except:
            _perror('cannot open/read CTF metadata file "{}"'.format(metadata))

        # parse CTF metadata
        _pinfo('parsing CTF metadata file')

        try:
            self._doc = self._parser.parse(self._tsdl)
        except pytsdl.parser.ParseError as e:
            _perror('parse error: {}'.format(e))

        # validate CTF metadata against barectf constraints
        _pinfo('validating CTF metadata file')
        self._validate_metadata()
        _psuccess('CTF metadata file is valid')

        # set parameters for this generation
        self._set_params()

        # generate header
        _pinfo('generating barectf header files')
        header = self._gen_barectf_header()
        self._write_file('{}.h'.format(self._prefix), header)
        header = self._gen_barectf_bitfield_header()
        self._write_file('{}_bitfield.h'.format(self._prefix), header)

        # generate C source file
        if not self._static_inline:
            _pinfo('generating barectf C source file')
            csrc = self._gen_barectf_csrc()
            self._write_file('{}.c'.format(self._prefix), csrc)

        _psuccess('done')


def run():
    args = _parse_args()
    generator = BarectfCodeGenerator()
    generator.gen_barectf(args.metadata, args.output, args.prefix,
                          args.static_inline, args.manual_clock)
