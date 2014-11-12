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
    _CTX_BUF_SIZE = 'ctx->buf_size'
    _CTX_BUF_AT = '{}[{} >> 3]'.format(_CTX_BUF, _CTX_AT)
    _CTX_BUF_AT_ADDR = '&{}'.format(_CTX_BUF_AT)
    _CTX_CALL_CLOCK_CB = 'ctx->clock_cb(ctx->clock_cb_data)'

    _bo_suffixes_map = {
        pytsdl.tsdl.ByteOrder.BE: 'be',
        pytsdl.tsdl.ByteOrder.LE: 'le',
    }

    _tsdl_type_names_map = {
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

    # TODO: prettify this function
    def _validate_struct(self, struct):
        # just in case we call this with the wrong type
        if type(struct) is not pytsdl.tsdl.Struct:
            raise RuntimeError('expecting a struct')

        # make sure inner structures are at least byte-aligned
        if self._get_obj_alignment(struct) < 8:
            raise RuntimeError('inner struct must be at least byte-aligned')

        # check each field
        for fname, ftype in struct.fields.items():
            if type(ftype) is pytsdl.tsdl.Sequence:
                raise RuntimeError('field "{}" is a dynamic array (not allowed here)'.format(fname))
            elif type(ftype) is pytsdl.tsdl.Array:
                # we need to check every element until we find a terminal one
                element = ftype.element

                while True:
                    if type(element) is pytsdl.tsdl.Sequence:
                        raise RuntimeError('field "{}" contains a dynamic array (not allowed here)'.format(fname))
                    elif type(element) is pytsdl.tsdl.Variant:
                        raise RuntimeError('field "{}" contains a variant (unsupported)'.format(fname))
                    elif type(element) is pytsdl.tsdl.String:
                        raise RuntimeError('field "{}" contains a string (not allowed here)'.format(fname))
                    elif type(element) is pytsdl.tsdl.Struct:
                        _validate_struct(element)
                    elif type(element) is pytsdl.tsdl.Integer:
                        if self._get_obj_size(element) > 64:
                            raise RuntimeError('integer field "{}" larger than 64-bit'.format(fname))
                    elif type(element) is pytsdl.tsdl.FloatingPoint:
                        if self._get_obj_size(element) > 64:
                            raise RuntimeError('floating point field "{}" larger than 64-bit'.format(fname))
                    elif type(element) is pytsdl.tsdl.Enum:
                        if self._get_obj_size(element) > 64:
                            raise RuntimeError('enum field "{}" larger than 64-bit'.format(fname))

                    if type(element) is pytsdl.tsdl.Array:
                        # still an array, continue
                        element = element.element
                    else:
                        # found the terminal element
                        break
            elif type(ftype) is pytsdl.tsdl.Variant:
                raise RuntimeError('field "{}" is a variant (unsupported)'.format(fname))
            elif type(ftype) is pytsdl.tsdl.String:
                raise RuntimeError('field "{}" is a string (not allowed here)'.format(fname))
            elif type(ftype) is pytsdl.tsdl.Struct:
                self._validate_struct(ftype)
            elif type(ftype) is pytsdl.tsdl.Integer:
                if self._get_obj_size(ftype) > 64:
                    raise RuntimeError('integer field "{}" larger than 64-bit'.format(fname))
            elif type(ftype) is pytsdl.tsdl.FloatingPoint:
                if self._get_obj_size(ftype) > 64:
                    raise RuntimeError('floating point field "{}" larger than 64-bit'.format(fname))
            elif type(ftype) is pytsdl.tsdl.Enum:
                if self._get_obj_size(ftype) > 64:
                    raise RuntimeError('enum field "{}" larger than 64-bit'.format(fname))

    def _validate_context_fields(self, struct):
        if type(struct) is not pytsdl.tsdl.Struct:
            raise RuntimeError('expecting a struct')

        for fname, ftype in struct.fields.items():
            if type(ftype) is pytsdl.tsdl.Variant:
                raise RuntimeError('field "{}" is a variant (unsupported)'.format(fname))
            elif type(ftype) is pytsdl.tsdl.Struct:
                # validate inner structure against barectf constraints
                self._validate_struct(ftype)

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

    def _validate_packet_header(self, packet_header):
        try:
            self._validate_struct(packet_header)
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

    def _dot_name_to_str(self, name):
        return '.'.join(name)

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

    def _validate_packet_context(self, stream):
        packet_context = stream.packet_context
        sid = stream.id

        try:
            self._validate_struct(packet_context)
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

    def _validate_event_header(self, stream):
        event_header = stream.event_header
        sid = stream.id

        try:
            self._validate_struct(event_header)
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

    def _validate_stream_event_context(self, stream):
        stream_event_context = stream.event_context
        sid = stream.id

        if stream_event_context is None:
            return

        try:
            self._validate_context_fields(stream_event_context)
        except RuntimeError as e:
            _perror('stream {}: event context: {}'.format(sid, e))

    def _validate_event_context(self, stream, event):
        event_context = event.context
        sid = stream.id
        eid = event.id

        if event_context is None:
            return

        try:
            self._validate_context_fields(event_context)
        except RuntimeError as e:
            _perror('stream {}: event {}: context: {}'.format(sid, eid, e))

    def _validate_event_fields(self, stream, event):
        event_fields = event.fields
        sid = stream.id
        eid = event.id

        try:
            self._validate_context_fields(event_fields)
        except RuntimeError as e:
            _perror('stream {}: event {}: fields: {}'.format(sid, eid, e))

    def _validate_event(self, stream, event):
        # name must be a compatible C identifier
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', event.name):
            _perror('stream {}: event {}: malformed name'.format(stream.id,
                                                                 event.id))

        self._validate_event_context(stream, event)
        self._validate_event_fields(stream, event)

    def _validate_stream(self, stream):
        self._validate_event_header(stream)
        self._validate_packet_context(stream)
        self._validate_stream_event_context(stream)

        # event stuff
        for event in stream.events:
            self._validate_event(stream, event)

    def _validate_all_scopes(self):
        # packet header
        self._validate_packet_header(self._doc.trace.packet_header)

        # stream stuff
        for stream in self._doc.streams.values():
            self._validate_stream(stream)


    def _validate_metadata(self):
        self._validate_all_scopes()

    # 3, 4 -> 4
    # 4, 4 -> 4
    # 5, 4 -> 8
    # 6, 4 -> 8
    # 7, 4 -> 8
    # 8, 4 -> 8
    # 9, 4 -> 12
    def _get_alignment(self, at, align):
        return (at + align - 1) & -align

    # this converts a tree of offset variables:
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

    # returns the size of a struct with _static size_
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

    def _get_array_size(self, array):
        element = array.element

        # effective size of one element includes its alignment after its size
        size = self._get_obj_size(element)
        align = self._get_obj_alignment(element)

        return self._get_alignment(size, align) * array.length

    def _get_enum_size(self, enum):
        return self._get_obj_size(enum.integer)

    def _get_floating_point_size(self, floating_point):
        return floating_point.exp_dig + floating_point.mant_dig

    def _get_integer_size(self, integer):
        return integer.size

    def _get_obj_size(self, obj):
        return self._obj_size_cb[type(obj)](obj)

    def _get_struct_alignment(self, struct):
        if struct.align is not None:
            return struct.align

        cur_align = 1

        for fname, ftype in struct.fields.items():
            cur_align = max(self._get_obj_alignment(ftype), cur_align)

        return cur_align

    def _get_integer_alignment(self, integer):
        return integer.align

    def _get_floating_point_alignment(self, floating_point):
        return floating_point.align

    def _get_enum_alignment(self, enum):
        return self._get_obj_alignment(enum.integer)

    def _get_string_alignment(self, string):
        return 8

    def _get_array_alignment(self, array):
        return self._get_obj_alignment(array.element)

    def _get_sequence_alignment(self, sequence):
        return self._get_obj_alignment(sequence.element)

    def _get_obj_alignment(self, obj):
        return self._obj_alignment_cb[type(obj)](obj)

    def _fname_to_pname(self, prefix, name):
        return 'param_{}_{}'.format(prefix, name)

    def _ef_fname_to_pname(self, name):
        return self._fname_to_pname('ef', name)

    def _ec_fname_to_pname(self, name):
        return self._fname_to_pname('ec', name)

    def _sec_fname_to_pname(self, name):
        return self._fname_to_pname('sec', name)

    def _eh_fname_to_pname(self, name):
        return self._fname_to_pname('eh', name)

    def _spc_fname_to_pname(self, name):
        return self._fname_to_pname('spc', name)

    def _tph_fname_to_pname(self, name):
        return self._fname_to_pname('tph', name)

    def _get_integer_param_ctype(self, integer):
        signed = 'u' if not integer.signed else ''

        if integer.size == 8:
            sz = '8'
        elif integer.size == 16:
            sz = '16'
        elif integer.size == 32:
            sz = '32'
        elif integer.size == 64:
            sz = '64'
        else:
            # if the integer is signed and of uncommon size, the sign bit is
            # at a custom position anyway so we use a 64-bit unsigned
            signed = 'u'

            if integer.signed:
                sz = '64'
            else:
                if integer.size < 16:
                    sz = '8'
                elif integer.size < 32:
                    sz = '16'
                elif integer.size < 64:
                    sz = '32'
                else:
                    sz = '64'

        return '{}int{}_t'.format(signed, sz)

    def _get_enum_param_ctype(self, enum):
        return self._get_obj_param_ctype(enum.integer)

    def _get_floating_point_param_ctype(self, fp):
        if fp.exp_dig == 8 and fp.mant_dig == 24 and fp.align == 32:
            return 'float'
        elif fp.exp_dig == 11 and fp.mant_dig == 53 and fp.align == 64:
            return 'double'
        else:
            return 'uint64_t'

    def _get_obj_param_ctype(self, obj):
        return self._obj_param_ctype_cb[type(obj)](obj)

    def _get_chk_offset_v(self, size):
        fmt = '{}_CHK_OFFSET_V({}, {}, {});'
        ret = fmt.format(self._prefix.upper(), self._CTX_AT,
                       self._CTX_BUF_SIZE, size)

        return ret

    def _get_chk_offset_v_cline(self, size):
        return _CLine(self._get_chk_offset_v(size))

    def _get_align_offset(self, align):
        fmt = '{}_ALIGN_OFFSET({}, {});'
        ret = fmt.format(self._prefix.upper(), self._CTX_AT, align)

        return ret

    def _get_align_offset_cline(self, size):
        return _CLine(self._get_align_offset(size))

    def _str_to_clines(self, s):
        lines = s.split('\n')

        return [_CLine(line) for line in lines]

    def _template_to_clines(self, tmpl, **kwargs):
        s = tmpl.format(prefix=self._prefix, ucprefix=self._prefix.upper(),
                        **kwargs)

        return self._str_to_clines(s)

    def _write_field_struct(self, fname, src_name, struct, scope_prefix):
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

    def _write_field_integer(self, fname, src_name, integer, scope_prefix=None):
        bo = self._bo_suffixes_map[integer.byte_order]
        t = self._get_obj_param_ctype(integer)
        length = self._get_obj_size(integer)

        return self._template_to_clines(barectf.templates.WRITE_INTEGER,
                                        sz=length, bo=bo, type=t,
                                        src_name=src_name)

    def _write_field_enum(self, fname, src_name, enum, scope_prefix=None):
        return self._write_field_obj(fname, src_name, enum.integer)

    def _write_field_floating_point(self, fname, src_name, floating_point,
                                    scope_prefix=None):
        bo = self._bo_suffixes_map[floating_point.byte_order]
        t = self._get_obj_param_ctype(floating_point)
        length = self._get_obj_size(floating_point)

        return self._template_to_clines(barectf.templates.WRITE_INTEGER,
                                        sz=length, bo=bo, type=t,
                                        src_name=src_name)

    def _write_field_array(self, fname, src_name, array, scope_prefix=None):
        clines = []

        # array index variable declaration
        iv = 'ia_{}'.format(fname)
        clines.append(_CLine('uint32_t {};'.format(iv)))

        # for loop using array's static length
        line = 'for ({iv} = 0; {iv} < {l}; ++{iv}) {{'.format(iv=iv,
                                                              l=array.length)
        clines.append(_CLine(line))

        # for loop statements
        for_block = _CBlock()

        # align bit index before writing to the buffer
        element_align = self._get_obj_alignment(array.element)
        cline = self._get_align_offset_cline(element_align)
        for_block.append(cline)

        # write element to the buffer
        for_block += self._write_field_obj(fname, src_name, array.element,
                                           scope_prefix)
        clines.append(for_block)

        # for loop end
        clines.append(_CLine('}'))

        return clines

    def _get_tph_src_name(self, length):
        offvar = self._get_offvar_name_from_expr(length[3:], 'tph')

        return 'ctx->{}'.format(offvar)

    def _get_env_src_name(self, length):
        if len(length) != 2:
            _perror('invalid sequence length: "{}"'.format(self._dot_name_to_str(length)))

        fname = length[1]

        if fname not in self._doc.env:
            _perror('cannot find field env.{}'.format(fname))

        return str(self._doc.env[fname])

    def _get_spc_src_name(self, length):
        offvar = self._get_offvar_name_from_expr(length[3:], 'spc')

        return 'ctx->{}'.format(offvar)

    def _get_seh_src_name(self, length):
        return self._get_offvar_name_from_expr(length[3:], 'seh')

    def _get_sec_src_name(self, length):
        return self._get_offvar_name_from_expr(length[3:], 'sec')

    def _get_ec_src_name(self, length):
        return self._get_offvar_name_from_expr(length[2:], 'ec')

    def _get_ef_src_name(self, length):
        return self._get_offvar_name_from_expr(length[2:], 'ef')

    def _seq_length_to_src_name(self, length, scope_prefix=None):
        length_dot = self._dot_name_to_str(length)

        for prefix, get_src_name in self._get_src_name_funcs.items():
            if length_dot.startswith(prefix):
                return get_src_name(length)

        return self._get_offvar_name_from_expr(length, scope_prefix)

    def _write_field_sequence(self, fname, src_name, sequence, scope_prefix):
        clines = []

        # sequence index variable declaration
        iv = 'is_{}'.format(fname)
        clines.append(_CLine('uint32_t {};'.format(iv)))

        # sequence length offset variable
        length_offvar = self._seq_length_to_src_name(sequence.length,
                                                     scope_prefix)

        # for loop using sequence's static length
        line = 'for ({iv} = 0; {iv} < {l}; ++{iv}) {{'.format(iv=iv,
                                                              l=length_offvar)
        clines.append(_CLine(line))

        # for loop statements
        for_block = _CBlock()

        # align bit index before writing to the buffer
        element_align = self._get_obj_alignment(sequence.element)
        cline = self._get_align_offset_cline(element_align)
        for_block.append(cline)

        # write element to the buffer
        for_block += self._write_field_obj(fname, src_name, sequence.element,
                                           scope_prefix)
        clines.append(for_block)

        # for loop end
        clines.append(_CLine('}'))

        return clines

    def _write_field_string(self, fname, src_name, string, scope_prefix=None):
        clines = []

        # string index variable declaration
        iv = 'is_{}'.format(fname)
        clines.append(_CLine('uint32_t {};'.format(iv)))

        # for loop; loop until the end of the source string is reached
        fmt = "for ({iv} = 0; {src}[{iv}] != '\\0'; ++{iv}, {ctxat} += 8) {{"
        line = fmt.format(iv=iv, src=src_name, ctxat=self._CTX_AT)
        clines.append(_CLine(line))

        # for loop statements
        for_block = _CBlock()

        # check offset overflow
        for_block.append(self._get_chk_offset_v_cline(8))

        # write byte to the buffer
        fmt = '{dst} = {src}[{iv}];'
        line = fmt.format(dst=self._CTX_BUF_AT, iv=iv, src=src_name)
        for_block.append(_CLine(line))

        # append for loop
        clines.append(for_block)
        clines.append(_CLine('}'))

        # write NULL character to the buffer
        clines.append(_CLine("{} = '\\0';".format(self._CTX_BUF_AT)))
        clines.append(_CLine('{} += 8;'.format(self._CTX_AT)))

        return clines

    def _write_field_obj(self, fname, src_name, ftype, scope_prefix):
        return self._write_field_obj_cb[type(ftype)](fname, src_name, ftype,
                                                     scope_prefix)

    def _get_offvar_name(self, name, prefix=None):
        parts = ['off']

        if prefix is not None:
            parts.append(prefix)

        parts.append(name)

        return '_'.join(parts)

    def _get_offvar_name_from_expr(self, expr, prefix=None):
        return self._get_offvar_name('_'.join(expr), prefix)

    def _field_to_clines(self, fname, ftype, scope_name, scope_prefix,
                         param_name_cb):
        clines = []
        pname = param_name_cb(fname)
        align = self._get_obj_alignment(ftype)

        # group comment
        fmt = '/* write {}.{} ({}) */'
        line = fmt.format(scope_name, fname,
                          self._tsdl_type_names_map[type(ftype)])
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
                fmt = 'uint32_t {} = {} + {};'
                line = fmt.format(offvar, self._CTX_AT, offset);
                clines.append(_CLine(line))
        elif type(ftype) is pytsdl.tsdl.Integer:
            # offset of this simple field is the current bit index
            offvar = self._get_offvar_name(fname, scope_prefix)
            line = 'uint32_t {} = {};'.format(offvar, self._CTX_AT)
            clines.append(_CLine(line))

        clines += self._write_field_obj(fname, pname, ftype, scope_prefix)

        return clines

    def _join_cline_groups(self, cline_groups):
        if not cline_groups:
            return cline_groups

        output_clines = cline_groups[0]

        for clines in cline_groups[1:]:
            output_clines.append('')
            output_clines += clines

        return output_clines

    def _struct_to_clines(self, struct, scope_name, scope_prefix,
                          param_name_cb):
        cline_groups = []

        for fname, ftype in struct.fields.items():
            clines = self._field_to_clines(fname, ftype, scope_name,
                                           scope_prefix, param_name_cb)
            cline_groups.append(clines)

        return self._join_cline_groups(cline_groups)

    def _get_struct_size_offvars(self, struct):
        offvars_tree = collections.OrderedDict()
        size = self._get_struct_size(struct, offvars_tree)
        offvars = self._flatten_offvars_tree(offvars_tree)

        return size, offvars

    def _get_ph_size_offvars(self):
        return self._get_struct_size_offvars(self._doc.trace.packet_header)

    def _get_pc_size_offvars(self, stream):
        return self._get_struct_size_offvars(stream.packet_context)

    def _offvars_to_ctx_clines(self, prefix, offvars):
        clines = []

        for name in offvars.keys():
            offvar = self._get_offvar_name(name, prefix)
            clines.append(_CLine('uint32_t {};'.format(offvar)))

        return clines

    def _gen_barectf_ctx_struct(self, stream, hide_sid=False):
        # get offset variables for both the packet header and packet context
        ph_size, ph_offvars = self._get_ph_size_offvars()
        pc_size, pc_offvars = self._get_pc_size_offvars(stream)
        clines = self._offvars_to_ctx_clines('tph', ph_offvars)
        clines += self._offvars_to_ctx_clines('spc', pc_offvars)

        # indent C
        clines_indented = []
        for cline in clines:
            clines_indented.append(_CLine('\t' + cline))

        # clock callback
        clock_cb = '\t/* (no clock callback) */'

        if not self._manual_clock:
            ctype = self._get_clock_type(stream)
            fmt = '\t{} (*clock_cb)(void*),\n\tvoid* clock_cb_data;'
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

    def _gen_barectf_contexts_struct(self):
        hide_sid = False

        if len(self._doc.streams) == 1:
            hide_sid = True

        structs = []

        for stream in self._doc.streams.values():
            struct = self._gen_barectf_ctx_struct(stream, hide_sid)
            structs.append(struct)

        return '\n\n'.join(structs)

    _packet_context_known_fields = [
        'content_size',
        'packet_size',
        'timestamp_begin',
        'timestamp_end',
    ]

    def _get_clock_type(self, stream):
        return self._get_obj_param_ctype(stream.event_header['timestamp'])

    def _gen_manual_clock_param(self, stream):
        return '{} param_clock'.format(self._get_clock_type(stream))

    def _gen_barectf_func_open_body(self, stream):
        clines = []

        # keep clock value (for timestamp_begin)
        if self._stream_has_timestamp_begin_end(stream):
            # get clock value ASAP
            clk_type = self._get_clock_type(stream)
            clk = self._gen_get_clock_value()
            line = '{} clk_value = {};'.format(clk_type, clk)
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
                                                lambda x: 'ctx->buffer_size')
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

    def _gen_barectf_func_open(self, stream, gen_body, hide_sid=False):
        params = []

        # manual clock
        if self._manual_clock:
            clock_param = self._gen_manual_clock_param(stream)
            params.append(clock_param)

        # packet context
        for fname, ftype in stream.packet_context.fields.items():
            if fname in self._packet_context_known_fields:
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

    def _gen_barectf_func_init_body(self, stream):
        clines = []

        line = 'uint32_t ctx_at_bkup;'
        clines.append(_CLine(line))

        # set context parameters
        clines.append(_CLine(''))
        clines.append(_CLine("/* barectf context parameters */"))
        clines.append(_CLine('ctx->buf = buf;'))
        clines.append(_CLine('ctx->buf_size = buf_size * 8;'))
        clines.append(_CLine('{} = 0;'.format(self._CTX_AT)))

        if not self._manual_clock:
            clines.append(_CLine('ctx->clock_cb = clock_cb;'))
            clines.append(_CLine('ctx->clock_cb_data = clock_cb_data;'))

        # set context offsets
        clines.append(_CLine(''))
        clines.append(_CLine("/* barectf context offsets */"))
        ph_size, ph_offvars = self._get_ph_size_offvars()
        pc_size, pc_offvars = self._get_pc_size_offvars(stream)
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

    def _gen_get_clock_value(self):
        if self._manual_clock:
            return 'param_clock'
        else:
            return self._CTX_CALL_CLOCK_CB

    def _stream_has_timestamp_begin_end(self, stream):
        return self._has_timestamp_begin_end[stream.id]

    def _gen_write_ctx_field_integer(self, src_name, prefix, name, obj):
        clines = []

        # save buffer position
        line = 'ctx_at_bkup = {};'.format(self._CTX_AT)
        clines.append(_CLine(line))

        # go back to field offset
        offvar = self._get_offvar_name(name, prefix)
        line = '{} = ctx->{};'.format(self._CTX_AT, offvar)
        clines.append(_CLine(line))

        # write value
        clines += self._write_field_integer(None, src_name, obj)

        # restore buffer position
        line = '{} = ctx_at_bkup;'.format(self._CTX_AT)
        clines.append(_CLine(line))

        return clines

    def _gen_barectf_func_close_body(self, stream):
        clines = []

        line = 'uint32_t ctx_at_bkup;'
        clines.append(_CLine(line))

        # update timestamp end if present
        if self._stream_has_timestamp_begin_end(stream):
            clines.append(_CLine(''))
            clines.append(_CLine("/* update packet context's timestamp_end */"))

            # get clock value ASAP
            clk_type = self._get_clock_type(stream)
            clk = self._gen_get_clock_value()
            line = '{} clk_value = {};'.format(clk_type, clk)
            clines.append(_CLine(line))

            # write timestamp_end
            timestamp_end_integer = stream.packet_context['timestamp_end']
            clines += self._gen_write_ctx_field_integer('clk_value', 'pc',
                                                        'timestamp_end',
                                                        timestamp_end_integer)

        # update content_size
        clines.append(_CLine(''))
        clines.append(_CLine("/* update packet context's content_size */"))
        content_size_integer = stream.packet_context['content_size']
        clines += self._gen_write_ctx_field_integer('ctx_at_bkup', 'pc',
                                                    'content_size',
                                                    content_size_integer)

        # get source
        cblock = _CBlock(clines)
        src = self._cblock_to_source(cblock)

        return src

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

    def _gen_barectf_funcs_init(self, gen_body):
        hide_sid = False

        if len(self._doc.streams) == 1:
            hide_sid = True

        funcs = []

        for stream in self._doc.streams.values():
            funcs.append(self._gen_barectf_func_init(stream, gen_body,
                                                     hide_sid))

        return funcs

    def _gen_barectf_funcs_open(self, gen_body):
        hide_sid = False

        if len(self._doc.streams) == 1:
            hide_sid = True

        funcs = []

        for stream in self._doc.streams.values():
            funcs.append(self._gen_barectf_func_open(stream, gen_body,
                                                     hide_sid))

        return funcs

    def _gen_barectf_func_trace_event_body(self, stream, event):
        clines = []

        # get clock value ASAP
        clk_type = self._get_clock_type(stream)
        clk = self._gen_get_clock_value()
        line = '{} clk_value = {};'.format(clk_type, clk)
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

    def _gen_barectf_funcs_trace_stream(self, stream, gen_body, hide_sid):
        funcs = []

        for event in stream.events:
            funcs.append(self._gen_barectf_func_trace_event(stream, event,
                                                            gen_body, hide_sid))

        return funcs

    def _gen_barectf_funcs_trace(self, gen_body):
        hide_sid = False

        if len(self._doc.streams) == 1:
            hide_sid = True

        funcs = []

        for stream in self._doc.streams.values():
            funcs += self._gen_barectf_funcs_trace_stream(stream, gen_body,
                                                          hide_sid)

        return funcs

    def _gen_barectf_funcs_close(self, gen_body):
        hide_sid = False

        if len(self._doc.streams) == 1:
            hide_sid = True

        funcs = []

        for stream in self._doc.streams.values():
            funcs.append(self._gen_barectf_func_close(stream, gen_body,
                                                      hide_sid))

        return funcs

    def _gen_barectf_header(self):
        ctx_structs = self._gen_barectf_contexts_struct()
        init_funcs = self._gen_barectf_funcs_init(self._static_inline)
        open_funcs = self._gen_barectf_funcs_open(self._static_inline)
        close_funcs = self._gen_barectf_funcs_close(self._static_inline)
        trace_funcs = self._gen_barectf_funcs_trace(self._static_inline)
        functions = init_funcs + open_funcs + close_funcs + trace_funcs
        functions_str = '\n\n'.join(functions)
        t = barectf.templates.HEADER
        header = t.format(prefix=self._prefix, ucprefix=self._prefix.upper(),
                          barectf_ctx=ctx_structs, functions=functions_str)

        return header

    def _cblock_to_source_lines(self, cblock, indent=1):
        src = []
        indentstr = '\t' * indent

        for line in cblock:
            if type(line) is _CBlock:
                src += self._cblock_to_source_lines(line, indent + 1)
            else:
                src.append(indentstr + line)

        return src

    def _cblock_to_source(self, cblock, indent=1):
        lines = self._cblock_to_source_lines(cblock, indent)

        return '\n'.join(lines)

    def _set_params(self):
        self._has_timestamp_begin_end = {}

        for stream in self._doc.streams.values():
            has = 'timestamp_begin' in stream.packet_context.fields
            self._has_timestamp_begin_end[stream.id] = has

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
        self._gen_barectf_header()

        # generate C source file
        if not self._static_inline:
            _pinfo('generating barectf translation unit')
            pass

        _psuccess('done')


def run():
    args = _parse_args()
    generator = BarectfCodeGenerator()
    generator.gen_barectf(args.metadata, args.output, args.prefix,
                          args.static_inline, args.manual_clock)
