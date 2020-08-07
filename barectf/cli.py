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
import barectf.argpar as barectf_argpar
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


# Finds and returns all the option items in `items` having the long name
# `long_name`.
def _find_opt_items(items, long_name):
    ret_items = []

    for item in items:
        if type(item) is barectf_argpar._OptItem and item.descr.long_name == long_name:
            ret_items.append(item)

    return ret_items


# Returns:
#
# For an option item without an argument:
#     `True`.
#
# For an option item with an argument:
#     Its argument.
#
# Uses the last option item having the long name `long_name` found in
# `items`.
#
# Returns `default` if there's no such option item.
def _opt_item_val(items, long_name, default=None):
    opt_items = _find_opt_items(items, long_name)

    if len(opt_items) == 0:
        return default

    opt_item = opt_items[-1]

    if opt_item.descr.has_arg:
        return opt_item.arg_text

    return True


class _CliCfg:
    pass


class _CliGenCmdCfg(_CliCfg):
    def __init__(self, config_file_path, c_source_dir, c_header_dir, metadata_stream_dir,
                 inclusion_dirs, ignore_inclusion_not_found, dump_config, v2_prefix):
        self._config_file_path = config_file_path
        self._c_source_dir = c_source_dir
        self._c_header_dir = c_header_dir
        self._metadata_stream_dir = metadata_stream_dir
        self._inclusion_dirs = inclusion_dirs
        self._ignore_inclusion_not_found = ignore_inclusion_not_found
        self._dump_config = dump_config
        self._v2_prefix = v2_prefix

    @property
    def config_file_path(self):
        return self._config_file_path

    @property
    def c_source_dir(self):
        return self._c_source_dir

    @property
    def c_header_dir(self):
        return self._c_header_dir

    @property
    def metadata_stream_dir(self):
        return self._metadata_stream_dir

    @property
    def inclusion_dirs(self):
        return self._inclusion_dirs

    @property
    def ignore_inclusion_not_found(self):
        return self._ignore_inclusion_not_found

    @property
    def dump_config(self):
        return self._dump_config

    @property
    def v2_prefix(self):
        return self._v2_prefix


def _print_gen_cmd_usage():
    print('''Usage: barectf generate [--code-dir=DIR] [--headers-dir=DIR]
                        [--metadata-dir=DIR] [--prefix=PREFIX]
                        [--include-dir=DIR]... [--ignore-include-not-found]
                        [--dump-config] CONFIG-FILE-PATH

Options:
  -c DIR, --code-dir=DIR        Write C source files to DIR
  --dump-config                 Print the effective configuration file
  -H DIR, --headers-dir=DIR     Write C header files to DIR
  --ignore-include-not-found    Continue to process the configuration file when
                                included files are not found
  -I DIR, --include-dir=DIR     Add DIR to the list of directories to be
                                searched for inclusion files
  -m DIR, --metadata-dir=DIR    Write the metadata stream file to DIR
  -p PREFIX, --prefix=PREFIX    Set the configuration prefix to PREFIX''')


class _CliError(Exception):
    pass


def _cli_gen_cfg_from_args(orig_args):
    # parse original arguments
    opt_descrs = [
        barectf_argpar.OptDescr('h', 'help'),
        barectf_argpar.OptDescr('c', 'code-dir', True),
        barectf_argpar.OptDescr('H', 'headers-dir', True),
        barectf_argpar.OptDescr('I', 'include-dir', True),
        barectf_argpar.OptDescr('m', 'metadata-dir', True),
        barectf_argpar.OptDescr('p', 'prefix', True),
        barectf_argpar.OptDescr(long_name='dump-config'),
        barectf_argpar.OptDescr(long_name='ignore-include-not-found'),
    ]
    res = barectf_argpar.parse(orig_args, opt_descrs)
    assert len(res.ingested_orig_args) == len(orig_args)

    # command help?
    if len(_find_opt_items(res.items, 'help')) > 0:
        _print_gen_cmd_usage()
        sys.exit()

    # check configuration file path
    config_file_path = None

    for item in res.items:
        if type(item) is barectf_argpar._NonOptItem:
            if config_file_path is not None:
                raise _CliError('Multiple configuration file paths provided')

            config_file_path = item.text

    if config_file_path is None:
        raise _CliError('Missing configuration file path')

    if not os.path.isfile(config_file_path):
        raise _CliError(f'`{config_file_path}` is not an existing, regular file')

    # directories
    c_source_dir = _opt_item_val(res.items, 'code-dir', os.getcwd())
    c_header_dir = _opt_item_val(res.items, 'headers-dir', os.getcwd())
    metadata_stream_dir = _opt_item_val(res.items, 'metadata-dir', os.getcwd())
    inclusion_dirs = [item.arg_text for item in _find_opt_items(res.items, 'include-dir')]

    for dir in [c_source_dir, c_header_dir, metadata_stream_dir] + inclusion_dirs:
        if not os.path.isdir(dir):
            raise _CliError(f'`{dir}` is not an existing directory')

    inclusion_dirs.append(os.getcwd())

    # other options
    ignore_inclusion_not_found = _opt_item_val(res.items, 'ignore-include-not-found', False)
    dump_config = _opt_item_val(res.items, 'dump-config', False)
    v2_prefix = _opt_item_val(res.items, 'prefix')

    return _CliGenCmdCfg(config_file_path, c_source_dir, c_header_dir, metadata_stream_dir,
                         inclusion_dirs, ignore_inclusion_not_found, dump_config, v2_prefix)


def _print_general_usage():
    print('''Usage: barectf COMMAND COMMAND-ARGS
       barectf --help
       barectf --version

General options:
  -h, --help       Show this help and quit
  -V, --version    Show version and quit

Available commands:
  gen, generate    Generate the C source and CTF metadata files of a tracer
                   from a configuration file

Run `barectf COMMAND --help` to show the help of COMMAND.''')


def _cli_cfg_from_args():
    # We use our `argpar` module here instead of Python's `argparse`
    # because we need to support the two following use cases:
    #
    #     $ barectf config.yaml
    #     $ barectf generate config.yaml
    #
    # In other words, the default command is `generate` (for backward
    # compatibility reasons). The argument parser must not consider
    # `config.yaml` as being a command name.
    general_opt_descrs = [
        barectf_argpar.OptDescr('V', 'version'),
        barectf_argpar.OptDescr('h', 'help'),
    ]
    orig_args = sys.argv[1:]
    res = barectf_argpar.parse(orig_args, general_opt_descrs, False)

    # find command name, collecting preceding (common) option items
    general_opt_items = []
    cmd_first_orig_arg_index = None
    cmd_name = None

    for item in res.items:
        if type(item) is barectf_argpar._NonOptItem:
            if item.text in ['gen', 'generate']:
                cmd_name = 'generate'
                cmd_first_orig_arg_index = item.orig_arg_index + 1
            else:
                cmd_first_orig_arg_index = item.orig_arg_index

            break
        else:
            assert type(item) is barectf_argpar._OptItem
            general_opt_items.append(item)

    # general help?
    if len(_find_opt_items(general_opt_items, 'help')) > 0:
        _print_general_usage()
        sys.exit()

    # version?
    if len(_find_opt_items(general_opt_items, 'version')) > 0:
        print(f'barectf {barectf.__version__}')
        sys.exit()

    # execute command
    cmd_orig_args = orig_args[cmd_first_orig_arg_index:]

    if cmd_name is None:
        # default `generate` command
        return _cli_gen_cfg_from_args(cmd_orig_args)
    else:
        assert cmd_name == 'generate'
        return _cli_gen_cfg_from_args(cmd_orig_args)


def _run():
    # parse arguments
    try:
        cli_cfg = _cli_cfg_from_args()
    except barectf_argpar._Error as exc:
        _print_error(f'Command-line: For argument `{exc.orig_arg}`: {exc.msg}')
    except _CliError as exc:
        _print_error(f'Command-line: {exc}')

    assert type(cli_cfg) is _CliGenCmdCfg

    # create configuration
    try:
        with open(cli_cfg.config_file_path) as f:
            if cli_cfg.dump_config:
                # print effective configuration file
                print(barectf.effective_configuration_file(f, True, cli_cfg.inclusion_dirs,
                                                           cli_cfg.ignore_inclusion_not_found))

                # barectf.configuration_from_file() reads the file again
                # below: rewind.
                f.seek(0)

            config = barectf.configuration_from_file(f, True, cli_cfg.inclusion_dirs,
                                                     cli_cfg.ignore_inclusion_not_found)
    except barectf._ConfigurationParseError as exc:
        _print_config_error(exc)
    except Exception as exc:
        _print_unknown_exc(exc)

    if cli_cfg.v2_prefix is not None:
        # Override prefixes.
        #
        # For historical reasons, the `--prefix` option applies the
        # barectf 2 configuration prefix rules. Therefore, get the
        # equivalent barectf 3 prefixes first.
        v3_prefixes = barectf_config_parse_common._v3_prefixes_from_v2_prefix(cli_cfg.v2_prefix)
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
        write_file(cli_cfg.metadata_stream_dir, code_gen.generate_metadata_stream())

        # generate and write C header files
        write_files(cli_cfg.c_header_dir, code_gen.generate_c_headers())

        # generate and write C source files
        write_files(cli_cfg.c_source_dir, code_gen.generate_c_sources())
    except Exception as exc:
        # We know `config` is valid, therefore the code generator cannot
        # fail for a reason known to barectf.
        _print_unknown_exc(exc)
