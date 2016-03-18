# The MIT License (MIT)
#
# Copyright (c) 2014-2016 Philippe Proulx <pproulx@efficios.com>
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

from pkg_resources import resource_filename
from termcolor import cprint, colored
import barectf.tsdl182gen
import barectf.config
import barectf.gen
import argparse
import os.path
import barectf
import sys
import os
import re


def _perror(msg):
    cprint('Error: ', 'red', end='', file=sys.stderr)
    cprint(msg, 'red', attrs=['bold'], file=sys.stderr)
    sys.exit(1)


def _pconfig_error(e):
    lines = []

    while True:
        if e is None:
            break

        lines.append(str(e))

        if not hasattr(e, 'prev'):
            break

        e = e.prev

    if len(lines) == 1:
        _perror(lines[0])

    cprint('Error:', 'red', file=sys.stderr)

    for i, line in enumerate(lines):
        suf = ':' if i < len(lines) - 1 else ''
        cprint('  ' + line + suf, 'red', attrs=['bold'], file=sys.stderr)

    sys.exit(1)


def _psuccess(msg):
    cprint('{}'.format(msg), 'green', attrs=['bold'])


def _parse_args():
    ap = argparse.ArgumentParser()

    ap.add_argument('-c', '--code-dir', metavar='DIR', action='store',
                    default=os.getcwd(),
                    help='output directory of C source file')
    ap.add_argument('--dump-config', action='store_true',
                    help='also dump the effective YAML configuration file used for generation')
    ap.add_argument('-H', '--headers-dir', metavar='DIR', action='store',
                    default=os.getcwd(),
                    help='output directory of C header files')
    ap.add_argument('-I', '--include-dir', metavar='DIR', action='append',
                    default=[],
                    help='add directory DIR to the list of directories to be searched for include files')
    ap.add_argument('--ignore-include-not-found', action='store_true',
                    help='continue to process the configuration file when included files are not found')
    ap.add_argument('-m', '--metadata-dir', metavar='DIR', action='store',
                    default=os.getcwd(),
                    help='output directory of CTF metadata')
    ap.add_argument('-p', '--prefix', metavar='PREFIX', action='store',
                    help='override configuration\'s prefix')
    ap.add_argument('-V', '--version', action='version',
                    version='%(prog)s {}'.format(barectf.__version__))
    ap.add_argument('config', metavar='CONFIG', action='store',
                    help='barectf YAML configuration file')

    # parse args
    args = ap.parse_args()

    # validate output directories
    for d in [args.code_dir, args.headers_dir, args.metadata_dir] + args.include_dir:
        if not os.path.isdir(d):
            _perror('"{}" is not an existing directory'.format(d))

    # validate that configuration file exists
    if not os.path.isfile(args.config):
        _perror('"{}" is not an existing, regular file'.format(args.config))

    # append current working directory and provided include directory
    args.include_dir += [os.getcwd(), resource_filename(__name__, 'include')]

    return args


def _write_file(d, name, content):
    with open(os.path.join(d, name), 'w') as f:
        f.write(content)


def run():
    # parse arguments
    args = _parse_args()

    # create configuration
    try:
        config = barectf.config.from_yaml_file(args.config, args.include_dir,
                                               args.ignore_include_not_found,
                                               args.dump_config)
    except barectf.config.ConfigError as e:
        _pconfig_error(e)
    except Exception as e:
        _perror('unknown exception: {}'.format(e))

    # replace prefix if needed
    if args.prefix:
        try:
            config.prefix = args.prefix
        except barectf.config.ConfigError as e:
            _pconfig_error(e)

    # generate metadata
    metadata = barectf.tsdl182gen.from_metadata(config.metadata)

    try:
        _write_file(args.metadata_dir, 'metadata', metadata)
    except Exception as e:
        _perror('cannot write metadata file: {}'.format(e))

    # create generator
    generator = barectf.gen.CCodeGenerator(config)

    # generate C headers
    header = generator.generate_header()
    bitfield_header = generator.generate_bitfield_header()

    try:
        _write_file(args.headers_dir, generator.get_header_filename(), header)
        _write_file(args.headers_dir, generator.get_bitfield_header_filename(),
                    bitfield_header)
    except Exception as e:
        _perror('cannot write header files: {}'.format(e))

    # generate C source
    c_src = generator.generate_c_src()

    try:
        _write_file(args.code_dir, '{}.c'.format(config.prefix.rstrip('_')),
                    c_src)
    except Exception as e:
        _perror('cannot write C source file: {}'.format(e))
