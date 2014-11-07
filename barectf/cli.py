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


def gen_barectf(output, prefix, static_inline, manual_clock):
    _pinfo(output)
    _pinfo(prefix)
    _pinfo(static_inline)
    _pinfo(manual_clock)


def run():
    args = _parse_args()
    gen_barectf(args.output, args.prefix, args.static_inline,
                args.manual_clock)
