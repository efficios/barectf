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
import pytsdl.parser
import pytsdl.tsdl
import collections
import argparse
import sys
import os
import re


def _perror(msg, exit_code=1):
    cprint('Error: {}'.format(msg), 'red', attrs=['bold'], file=sys.stderr)
    sys.exit(exit_code)


def _pinfo(msg):
    cprint(':: {}'.format(msg), 'blue', attrs=['bold'], file=sys.stderr)


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


def _validate_struct(struct):
    if type(struct) is not pytsdl.tsdl.Struct:
        raise RuntimeError('expecting a struct')

    if _get_obj_alignment(struct) < 8:
        raise RuntimeError('inner struct must be at least byte-aligned')

    for name, ftype in struct.fields.items():
        if type(ftype) is pytsdl.tsdl.Sequence:
            raise RuntimeError('field "{}" is a dynamic array (not allowed here)'.format(name))
        elif type(ftype) is pytsdl.tsdl.Array:
            end = False
            element = ftype.element

            while not end:
                if type(element) is pytsdl.tsdl.Sequence:
                    raise RuntimeError('field "{}" contains a dynamic array (not allowed here)'.format(name))
                elif type(element) is pytsdl.tsdl.Variant:
                    raise RuntimeError('field "{}" contains a variant (unsupported)'.format(name))
                elif type(element) is pytsdl.tsdl.String:
                    raise RuntimeError('field "{}" contains a string (not allowed here)'.format(name))
                elif type(element) is pytsdl.tsdl.Struct:
                    _validate_struct(element)
                elif type(element) is pytsdl.tsdl.Integer:
                    if _get_integer_size(element) > 64:
                        raise RuntimeError('integer field "{}" larger than 64-bit'.format(name))
                elif type(element) is pytsdl.tsdl.FloatingPoint:
                    if _get_floating_point_size(element) > 64:
                        raise RuntimeError('floating point field "{}" larger than 64-bit'.format(name))
                elif type(element) is pytsdl.tsdl.Enum:
                    if _get_enum_size(element) > 64:
                        raise RuntimeError('enum field "{}" larger than 64-bit'.format(name))

                if type(element) is pytsdl.tsdl.Array:
                    element = element.element
                else:
                    end = True
        elif type(ftype) is pytsdl.tsdl.Variant:
            raise RuntimeError('field "{}" is a variant (unsupported)'.format(name))
        elif type(ftype) is pytsdl.tsdl.String:
            raise RuntimeError('field "{}" is a string (not allowed here)'.format(name))
        elif type(ftype) is pytsdl.tsdl.Struct:
            _validate_struct(ftype)
        elif type(ftype) is pytsdl.tsdl.Integer:
            if _get_integer_size(ftype) > 64:
                raise RuntimeError('integer field "{}" larger than 64-bit'.format(name))
        elif type(ftype) is pytsdl.tsdl.FloatingPoint:
            if _get_floating_point_size(ftype) > 64:
                raise RuntimeError('floating point field "{}" larger than 64-bit'.format(name))
        elif type(ftype) is pytsdl.tsdl.Enum:
            if _get_enum_size(ftype) > 64:
                raise RuntimeError('enum field "{}" larger than 64-bit'.format(name))


def _validate_context_field(struct):
    if type(struct) is not pytsdl.tsdl.Struct:
        raise RuntimeError('expecting a struct')

    for name, ftype in struct.fields.items():
        if type(ftype) is pytsdl.tsdl.Variant:
            raise RuntimeError('field "{}" is a variant (unsupported)'.format(name))
        elif type(ftype) is pytsdl.tsdl.Struct:
            _validate_struct(ftype)


def _validate_integer(integer, size=None, align=None, signed=None):
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


def _validate_packet_header(packet_header):
    try:
        _validate_struct(packet_header)
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
        _validate_integer(packet_header['magic'], 32, 32, False)
    except RuntimeError as e:
        _perror('packet header: "magic": {}'.format(e))

    # mandatory stream_id
    if 'stream_id' not in packet_header.fields:
        _perror('packet header: missing "stream_id" field')

    # stream_id must be an unsigned integer
    try:
        _validate_integer(packet_header['stream_id'], signed=False)
    except RuntimeError as e:
        _perror('packet header: "stream_id": {}'.format(e))


def _dot_name_to_str(name):
    return '.'.join(name)


def _compare_integers(int1, int2):
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

    return sum(comps) == len(comps)


def _validate_packet_context(doc, stream):
    packet_context = stream.packet_context
    sid = stream.id

    try:
        _validate_struct(packet_context)
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

            if not _compare_integers(fields['timestamp_begin'], timestamp):
                _perror('stream {}: packet context: "timestamp_begin": integer type different from event header\'s "timestamp" field'.format(sid))

            if not _compare_integers(fields['timestamp_end'], timestamp):
                _perror('stream {}: packet context: "timestamp_end": integer type different from event header\'s "timestamp" field'.format(sid))

    # content_size must exist and be an unsigned integer
    if 'content_size' not in fields:
        _perror('stream {}: packet context: missing "content_size" field'.format(sid))

    try:
        _validate_integer(fields['content_size'], 32, 32, False)
    except:
        try:
            _validate_integer(fields['content_size'], 64, 64, False)
        except:
            _perror('stream {}: packet context: "content_size": expecting unsigned 32-bit/64-bit integer'.format(sid))

    # packet_size must exist and be an unsigned integer
    if 'packet_size' not in fields:
        _perror('stream {}: packet context: missing "packet_size" field'.format(sid))

    try:
        _validate_integer(fields['packet_size'], 32, 32, False)
    except:
        try:
            _validate_integer(fields['packet_size'], 64, 64, False)
        except:
            _perror('stream {}: packet context: "packet_size": expecting unsigned 32-bit/64-bit integer'.format(sid))

    # if cpu_id exists, must be an unsigned integer
    if 'cpu_id' in fields:
        try:
            _validate_integer(fields['cpu_id'], signed=False)
        except RuntimeError as e:
            _perror('stream {}: packet context: "cpu_id": {}'.format(sid, e))


def _validate_event_header(doc, stream):
    event_header = stream.event_header
    sid = stream.id

    try:
        _validate_struct(event_header)
    except RuntimeError as e:
        _perror('stream {}: event header: {}'.format(sid, e))

    fields = event_header.fields

    # id must exist and be an unsigned integer
    if 'id' not in fields:
        _perror('stream {}: event header: missing "id" field'.format(sid))

    try:
        _validate_integer(fields['id'], signed=False)
    except RuntimeError as e:
        _perror('stream {}: "id": {}'.format(sid, format(e)))


    # timestamp must exist, be an unsigned integer and be mapped to a valid clock
    if 'timestamp' not in fields:
        _perror('stream {}: event header: missing "timestamp" field'.format(sid))

    try:
        _validate_integer(fields['timestamp'], signed=False)
    except RuntimeError as e:
        _perror('stream {}: "timestamp": {}'.format(sid, format(e)))


def _validate_stream_event_context(doc, stream):
    stream_event_context = stream.event_context
    sid = stream.id

    if stream_event_context is None:
        return

    try:
        _validate_context_field(stream_event_context)
    except RuntimeError as e:
        _perror('stream {}: event context: {}'.format(sid, e))


def _validate_headers_contexts(doc):
    # packet header
    _validate_packet_header(doc.trace.packet_header)

    # stream stuff
    for stream_id, stream in doc.streams.items():
        _validate_event_header(doc, stream)
        _validate_packet_context(doc, stream)
        _validate_stream_event_context(doc, stream)


def _validate_metadata(doc):
    _validate_headers_contexts(doc)


def _get_alignment(at, align):
    return (at + align - 1) & -align


def _offset_vars_tree_to_vars(offset_vars_tree, prefix='',
                              offset_vars=collections.OrderedDict()):
    for name, offset in offset_vars_tree.items():
        varname = '{}_{}'.format(prefix, name)

        if isinstance(offset, dict):
            _offset_vars_tree_to_vars(offset, varname, offset_vars)
        else:
            offset_vars[varname] = offset

    return offset_vars


def _get_struct_size(struct, offset_vars_tree=collections.OrderedDict(),
                     base_offset=0):
    offset = 0

    for fname, ftype in struct.fields.items():
        field_alignment = _get_obj_alignment(ftype)
        offset = _get_alignment(offset, field_alignment)

        if type(ftype) is pytsdl.tsdl.Struct:
            offset_vars_tree[fname] = collections.OrderedDict()
            sz = _get_struct_size(ftype, offset_vars_tree[fname],
                                  base_offset + offset)
        else:
            offset_vars_tree[fname] = base_offset + offset
            sz = _get_obj_size(ftype)

        offset += sz

    return offset


def _get_array_size(array):
    element = array.element

    # effective size of one element includes its alignment after its size
    size = _get_obj_size(element)
    align = _get_obj_alignment(element)

    return _get_alignment(size, align) * array.length


def _get_enum_size(enum):
    return _get_obj_size(enum.integer)


def _get_floating_point_size(floating_point):
    return floating_point.exp_dig + floating_point.mant_dig


def _get_integer_size(integer):
    return integer.size


_obj_size_cb = {
    pytsdl.tsdl.Integer: _get_integer_size,
    pytsdl.tsdl.Enum: _get_enum_size,
    pytsdl.tsdl.FloatingPoint: _get_floating_point_size,
    pytsdl.tsdl.Array: _get_array_size,
}


def _get_obj_size(obj):
    return _obj_size_cb[type(obj)](obj)


def _get_struct_alignment(struct):
    if struct.align is not None:
        return struct.align

    cur_align = 1

    for fname, ftype in struct.fields.items():
        cur_align = max(_get_obj_alignment(ftype), cur_align)

    return cur_align


def _get_integer_alignment(integer):
    return integer.align


def _get_floating_point_alignment(floating_point):
    return floating_point.align


def _get_enum_alignment(enum):
    return _get_obj_alignment(enum.integer)


def _get_string_alignment(string):
    return 8

def _get_array_alignment(array):
    return _get_obj_alignment(array.element)


def _get_sequence_alignment(sequence):
    return _get_obj_alignment(sequence.element)


_obj_alignment_cb = {
    pytsdl.tsdl.Struct: _get_struct_alignment,
    pytsdl.tsdl.Integer: _get_integer_alignment,
    pytsdl.tsdl.Enum: _get_enum_alignment,
    pytsdl.tsdl.FloatingPoint: _get_floating_point_alignment,
    pytsdl.tsdl.Array: _get_array_alignment,
    pytsdl.tsdl.Sequence: _get_sequence_alignment,
    pytsdl.tsdl.String: _get_string_alignment,
}


def _get_obj_alignment(obj):
    return _obj_alignment_cb[type(obj)](obj)


class _CBlock(list):
    pass


class _CLine(str):
    pass


_CTX_AT = 'ctx->at'
_CTX_BUF = 'ctx->buf'
_CTX_BUF_AT = '{}[{} >> 3]'.format(_CTX_BUF, _CTX_AT)
_CTX_BUF_AT_ADDR = '&{}'.format(_CTX_BUF_AT)
_ALIGN_OFFSET = 'ALIGN_OFFSET'


def _field_name_to_param_name(fname):
    return '_param_{}'.format(fname)


def _get_integer_param_type(integer):
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


def _get_enum_param_type(enum):
    return _get_obj_param_type(enum.integer)


def _get_floating_point_param_type(fp):
    if fp.exp_dig == 8 and fp.mant_dig == 24 and fp.align == 32:
        return 'float'
    elif fp.exp_dig == 11 and fp.mant_dig == 53 and fp.align == 64:
        return 'double'
    else:
        return 'uint64_t'


_obj_param_type_cb = {
    pytsdl.tsdl.Struct: lambda obj: 'const void*',
    pytsdl.tsdl.Integer: _get_integer_param_type,
    pytsdl.tsdl.Enum: _get_enum_param_type,
    pytsdl.tsdl.FloatingPoint: _get_floating_point_param_type,
    pytsdl.tsdl.Array: lambda obj: 'const void*',
    pytsdl.tsdl.Sequence: lambda obj: 'const void*',
    pytsdl.tsdl.String: lambda obj: 'const char*',
}


def _get_obj_param_type(obj):
    return _obj_param_type_cb[type(obj)](obj)


def _write_field_struct(doc, fname, struct):
    size = _get_struct_size(struct)
    size_bytes = _get_alignment(size, 8) // 8

    dst = _CTX_BUF_AT_ADDR
    src = _field_name_to_param_name(fname)

    return [
        # memcpy() is safe since barectf requires inner structures
        # to be byte-aligned
        _CLine('memcpy({}, {}, {});'.format(dst, src, size_bytes)),
        _CLine('{} += {};'.format(_CTX_AT, size)),
    ]


_bo_suffixes_map = {
    pytsdl.tsdl.ByteOrder.BE: 'be',
    pytsdl.tsdl.ByteOrder.LE: 'le',
}


def _write_field_integer(doc, fname, integer):
    bo = _bo_suffixes_map[integer.byte_order]
    ptr = _CTX_BUF
    t = _get_obj_param_type(integer)
    start = _CTX_AT
    length = _get_obj_size(integer)
    value = _field_name_to_param_name(fname)
    fmt = 'barectf_bitfield_write_{}({}, {}, {}, {}, {});'

    return [
        _CLine(fmt.format(bo, ptr, t, start, length, value)),
        _CLine('{} += {};'.format(_CTX_AT, length))
    ]


def _write_field_enum(doc, fname, enum):
    return _write_field_obj(doc, fname, enum.integer)


def _write_field_floating_point(doc, fname, floating_point):
    bo = _bo_suffixes_map[floating_point.byte_order]
    ptr = _CTX_BUF
    t = _get_obj_param_type(floating_point)
    start = _CTX_AT
    length = _get_obj_size(floating_point)
    value = _field_name_to_param_name(fname)
    fmt = 'barectf_bitfield_write_{}({}, {}, {}, {}, {});'

    return [
        _CLine(fmt.format(bo, ptr, t, start, length, value)),
        _CLine('{} += {};'.format(_CTX_AT, length))
    ]


def _write_field_array(doc, fname, array):
    lines = []
    iv = 'ia_{}'.format(fname)
    lines.append(_CLine('uint32_t {};'.format(iv)))
    line = 'for ({iv} = 0; {iv} < {l}; ++{iv}) {{'.format(iv=iv, l=array.length)
    lines.append(_CLine(line))
    for_block = _CBlock()
    element_align = _get_obj_alignment(array.element)
    line = '{}({}, {});'.format(_ALIGN_OFFSET, _CTX_AT, element_align)
    for_block.append(_CLine(line))
    for_block += _write_field_obj(doc, fname, array.element)
    lines.append(for_block)
    lines.append(_CLine('}'))

    return lines


def _write_field_sequence(doc, fname, sequence):
    return [
        _CLine('would write sequence here;'),
    ]


def _write_field_string(doc, fname, string):
    lines = []
    src = _field_name_to_param_name(fname)
    iv = 'is_{}'.format(fname)
    lines.append(_CLine('uint32_t {};'.format(iv)))
    fmt = "for ({iv} = 0; {src}[{iv}] != '\\0'; ++{iv}, {ctxat} += 8) {{"
    lines.append(_CLine(fmt.format(iv=iv, src=src, ctxat=_CTX_AT)))
    for_block = _CBlock()
    line = '{} = {}[{}]'.format(_CTX_BUF_AT, src, iv)
    for_block.append(_CLine(line))
    lines.append(for_block)
    lines.append(_CLine('}'))
    lines.append(_CLine("{} = '\\0';".format(_CTX_BUF_AT)))
    lines.append(_CLine('{} += 8;'.format(_CTX_AT)))

    return lines


_write_field_obj_cb = {
    pytsdl.tsdl.Struct: _write_field_struct,
    pytsdl.tsdl.Integer: _write_field_integer,
    pytsdl.tsdl.Enum: _write_field_enum,
    pytsdl.tsdl.FloatingPoint: _write_field_floating_point,
    pytsdl.tsdl.Array: _write_field_array,
    pytsdl.tsdl.Sequence: _write_field_sequence,
    pytsdl.tsdl.String: _write_field_string,
}


def _write_field_obj(doc, fname, ftype):
    return _write_field_obj_cb[type(ftype)](doc, fname, ftype)


def _struct_to_c_lines(doc, struct):
    lines = []

    for fname, ftype in struct.fields.items():
        pname = _field_name_to_param_name(fname)
        align = _get_obj_alignment(ftype)
        line = '{}({}, {});'.format(_ALIGN_OFFSET, _CTX_AT, align)
        lines.append(line)

        # offset variables
        if type(ftype) is pytsdl.tsdl.Struct:
            offset_vars_tree = collections.OrderedDict()
            _get_struct_size(ftype, offset_vars_tree)
            offset_vars = _offset_vars_tree_to_vars(offset_vars_tree)

            for lname, offset in offset_vars.items():
                line = 'uint32_t off_{}_{}'.format(fname, lname, _CTX_AT);
                lines.append(_CLine(line))
        else:
            line = 'uint32_t off_{} = {};'.format(fname, _CTX_AT)
            lines.append(_CLine(line))

        lines += _write_field_obj(doc, fname, ftype)

    return lines


def gen_barectf(metadata, output, prefix, static_inline, manual_clock):
    # open CTF metadata file
    try:
        with open(metadata) as f:
            tsdl = f.read()
    except:
        _perror('cannot open/read CTF metadata file "{}"'.format(metadata))

    # parse CTF metadata
    parser = pytsdl.parser.Parser()

    try:
        doc = parser.parse(tsdl)
    except pytsdl.parser.ParseError as e:
        _perror('parse error: {}'.format(e))

    # validate CTF metadata against barectf constraints
    _validate_metadata(doc)

    import json

    lines = _struct_to_c_lines(doc, doc.streams[0].get_event(0).fields)

    print(json.dumps(lines, indent=4))


def run():
    args = _parse_args()
    gen_barectf(args.metadata, args.output, args.prefix, args.static_inline,
                args.manual_clock)
