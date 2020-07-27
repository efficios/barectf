# The MIT License (MIT)
#
# Copyright (c) 2014-2020 Philippe Proulx <pproulx@efficios.com>
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

import pkg_resources
import termcolor
import argparse
import os.path
import barectf
import barectf.config_parse_common as barectf_config_parse_common
import sys
import os


# Colors and prints the error message `msg` and exits with status code
# 1.
def _print_error(msg):
    termcolor.cprint('Error: ', 'red', end='', file=sys.stderr)
    termcolor.cprint(msg, 'red', attrs=['bold'], file=sys.stderr)
    sys.exit(1)


# Pretty-prints the barectf configuration error `exc` and exits with
# status code 1.
def _print_config_error(exc):
    # reverse: most precise message comes last
    for ctx in reversed(exc.context):
        msg = ''

        if ctx.message is not None:
            msg = f' {ctx.message}'

        color = 'red'
        termcolor.cprint(f'{ctx.name}', color, attrs=['bold'], file=sys.stderr, end='')
        termcolor.cprint(':', color, file=sys.stderr, end='')
        termcolor.cprint(msg, color, file=sys.stderr)

    sys.exit(1)


# Pretty-prints the unknown exception `exc`.
def _print_unknown_exc(exc):
    import traceback

    traceback.print_exc()
    _print_error(f'Unknown exception: {exc}')


def _parse_args():
    ap = argparse.ArgumentParser()

    ap.add_argument('-c', '--code-dir', metavar='DIR', action='store', default=os.getcwd(),
                    help='output directory of C source file')
    ap.add_argument('--dump-config', action='store_true',
                    help='also dump the effective YAML configuration file used for generation')
    ap.add_argument('-H', '--headers-dir', metavar='DIR', action='store', default=os.getcwd(),
                    help='output directory of C header files')
    ap.add_argument('-I', '--include-dir', metavar='DIR', action='append', default=[],
                    help='add directory DIR to the list of directories to be searched for include files')
    ap.add_argument('--ignore-include-not-found', action='store_true',
                    help='continue to process the configuration file when included files are not found')
    ap.add_argument('-m', '--metadata-dir', metavar='DIR', action='store', default=os.getcwd(),
                    help='output directory of CTF metadata')
    ap.add_argument('-p', '--prefix', metavar='PREFIX', action='store',
                    help='override configuration\'s prefixes')
    ap.add_argument('-V', '--version', action='version',
                    version='%(prog)s {}'.format(barectf.__version__))
    ap.add_argument('config', metavar='CONFIG', action='store',
                    help='barectf YAML configuration file')

    # parse args
    args = ap.parse_args()

    # validate output directories
    for dir in [args.code_dir, args.headers_dir, args.metadata_dir] + args.include_dir:
        if not os.path.isdir(dir):
            _print_error(f'`{dir}` is not an existing directory')

    # validate that configuration file exists
    if not os.path.isfile(args.config):
        _print_error(f'`{args.config}` is not an existing, regular file')

    # Load configuration file to get its major version in order to
    # append the correct implicit inclusion directory.
    try:
        with open(args.config) as f:
            config_major_version = barectf.configuration_file_major_version(f)
    except barectf._ConfigurationParseError as exc:
        _print_config_error(exc)
    except Exception as exc:
        _print_unknown_exc(exc)

    # append current working directory and implicit inclusion directory
    args.include_dir += [
        os.getcwd(),
        pkg_resources.resource_filename(__name__, f'include/{config_major_version}')
    ]

    return args


def run():
    # parse arguments
    args = _parse_args()

    # create configuration
    try:
        with open(args.config) as f:
            if args.dump_config:
                # print effective configuration file
                print(barectf.effective_configuration_file(f, args.include_dir,
                                                           args.ignore_include_not_found))

                # barectf.configuration_from_file() reads the file again
                # below: rewind.
                f.seek(0)

            config = barectf.configuration_from_file(f, args.include_dir,
                                                     args.ignore_include_not_found)
    except barectf._ConfigurationParseError as exc:
        _print_config_error(exc)
    except Exception as exc:
        _print_unknown_exc(exc)

    if args.prefix:
        # Override prefixes.
        #
        # For historical reasons, the `--prefix` option applies the
        # barectf 2 configuration prefix rules. Therefore, get the
        # equivalent barectf 3 prefixes first.
        v3_prefixes = barectf_config_parse_common._v3_prefixes_from_v2_prefix(args.prefix)
        cg_opts = config.options.code_generation_options
        cg_opts = barectf.ConfigurationCodeGenerationOptions(v3_prefixes.identifier,
                                                             v3_prefixes.file_name,
                                                             cg_opts.default_stream_type,
                                                             cg_opts.header_options,
                                                             cg_opts.clock_type_c_types)
        config = barectf.Configuration(config.trace, barectf.ConfigurationOptions(cg_opts))

    # create a barectf code generator
    code_gen = barectf.CodeGenerator(config)

    def write_file(dir, file):
        with open(os.path.join(dir, file.name), 'w') as f:
            f.write(file.contents)

    def write_files(dir, files):
        for file in files:
            write_file(dir, file)

    try:
        # generate and write metadata stream file
        write_file(args.metadata_dir, code_gen.generate_metadata_stream())

        # generate and write C header files
        write_files(args.headers_dir, code_gen.generate_c_headers())

        # generate and write C source files
        write_files(args.code_dir, code_gen.generate_c_sources())
    except Exception as exc:
        # We know `config` is valid, therefore the code generator cannot
        # fail for a reason known to barectf.
        _print_unknown_exc(exc)
