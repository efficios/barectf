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
import argparse
import pytsdl.tsdl
import pytsdl.parser
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

    for name, ftype in struct.fields.items():
        if type(ftype) is pytsdl.tsdl.Sequence:
            raise RuntimeError('field "{}" is a dynamic array'.format(name))
        elif type(ftype) is pytsdl.tsdl.Array:
            end = False
            element = ftype.element

            while not end:
                if type(element) is pytsdl.tsdl.Sequence:
                    raise RuntimeError('field "{}" contains a dynamic array'.format(name))
                elif type(element) is pytsdl.tsdl.Variant:
                    raise RuntimeError('field "{}" contains a variant (unsupported)'.format(name))
                elif type(element) is pytsdl.tsdl.String:
                    raise RuntimeError('field "{}" contains a string'.format(name))
                elif type(element) is pytsdl.tsdl.Struct:
                    _validate_struct(element)

                if type(element) is pytsdl.tsdl.Array:
                    element = element.element
                else:
                    end = True
        elif type(ftype) is pytsdl.tsdl.Variant:
            raise RuntimeError('field "{}" is a variant (unsupported)'.format(name))
        elif type(ftype) is pytsdl.tsdl.String:
            raise RuntimeError('field "{}" is a string'.format(name))
        elif type(ftype) is pytsdl.tsdl.Struct:
            _validate_struct(ftype)


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


def _validate_clock(doc, name):
    msg = '"{}" does not name an existing clock'.format(_dot_name_to_str(name))

    if len(name) != 3:
        raise RuntimeError(msg)

    if name[0] != 'clock' or name[2] != 'value':
        raise RuntimeError()

    if name[1] not in doc.clocks:
        raise RuntimeError(msg)


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

    if fields['timestamp'].map is None:
        _perror('stream {}: "timestamp": integer must be mapped to an existing clock'.format(sid))

    try:
        _validate_clock(doc, fields['timestamp'].map)
    except RuntimeError as e:
        _perror('stream {}: "timestamp": integer must be mapped to an existing clock'.format(sid))


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

    _pinfo(metadata)
    _pinfo(output)
    _pinfo(prefix)
    _pinfo(static_inline)
    _pinfo(manual_clock)


def run():
    args = _parse_args()
    gen_barectf(args.metadata, args.output, args.prefix, args.static_inline,
                args.manual_clock)
