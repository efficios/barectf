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

import termcolor
import os.path
import barectf
import barectf.config_parse_common as barectf_config_parse_common
import barectf.argpar as barectf_argpar
from typing import Any, List, Iterable, NoReturn
import typing
from barectf.typing import Index, Count
import sys
import os


# Colors and prints the error message `msg` and exits with status code
# 1.
def _print_error(msg: str) -> NoReturn:
    termcolor.cprint('Error: ', 'red', end='', file=sys.stderr)
    termcolor.cprint(msg, 'red', attrs=['bold'], file=sys.stderr)
    sys.exit(1)


# Pretty-prints the barectf configuration error `exc` and exits with
# status code 1.
def _print_config_error(exc: barectf._ConfigurationParseError) -> NoReturn:
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
def _print_unknown_exc(exc: Exception) -> NoReturn:
    import traceback

    traceback.print_exc()
    _print_error(f'Unknown exception: {exc}')


# Finds and returns all the option items in `items` having the long name
# `long_name`.
def _find_opt_items(items: Iterable[barectf_argpar._Item],
                    long_name: str) -> List[barectf_argpar._OptItem]:
    ret_items: List[barectf_argpar._OptItem] = []

    for item in items:
        if type(item) is barectf_argpar._OptItem:
            item = typing.cast(barectf_argpar._OptItem, item)

            if item.descr.long_name == long_name:
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
def _opt_item_val(items: Iterable[barectf_argpar._Item], long_name: str,
                  default: Any = None) -> Any:
    opt_items = _find_opt_items(items, long_name)

    if len(opt_items) == 0:
        return default

    opt_item = opt_items[-1]

    if opt_item.descr.has_arg:
        return opt_item.arg_text

    return True


class _CliError(Exception):
    pass


def _cfg_file_path_from_parse_res(parse_res: barectf_argpar._ParseRes) -> str:
    cfg_file_path = None

    for item in parse_res.items:
        if type(item) is barectf_argpar._NonOptItem:
            if cfg_file_path is not None:
                raise _CliError('Multiple configuration file paths provided')

            cfg_file_path = typing.cast(barectf_argpar._NonOptItem, item).text

    if cfg_file_path is None:
        raise _CliError('Missing configuration file path')

    if not os.path.isfile(cfg_file_path):
        raise _CliError(f'`{cfg_file_path}` is not an existing, regular file')

    return cfg_file_path


# Returns a `_CfgCmdCfg` object from the command-line parsing results
# `parse_res`.
def _cfg_cmd_cfg_from_parse_res(parse_res: barectf_argpar._ParseRes) -> '_CfgCmdCfg':
    # check configuration file path
    cfg_file_path = _cfg_file_path_from_parse_res(parse_res)

    # inclusion directories (`--include-dir` option needs an argument)
    inclusion_dirs = typing.cast(List[str],
                                 [item.arg_text for item in _find_opt_items(parse_res.items, 'include-dir')])

    for dir in inclusion_dirs:
        if not os.path.isdir(dir):
            raise _CliError(f'`{dir}` is not an existing directory')

    inclusion_dirs.append(os.getcwd())

    # other options
    ignore_inclusion_file_not_found = _opt_item_val(parse_res.items, 'ignore-include-not-found',
                                                    False)

    return _CfgCmdCfg(cfg_file_path, inclusion_dirs, ignore_inclusion_file_not_found)


def _print_gen_cmd_usage():
    print('''Usage: barectf generate [--code-dir=DIR] [--headers-dir=DIR]
                        [--metadata-dir=DIR] [--prefix=PREFIX]
                        [--include-dir=DIR]... [--ignore-include-not-found]
                        CONFIG-FILE-PATH
       barectf generate --help

Generate the C source and CTF metadata stream files of a tracer from the
configuration file CONFIG-FILE-PATH.

Options:
  -c DIR, --code-dir=DIR        Write C source files to DIR instead of the CWD
  -H DIR, --headers-dir=DIR     Write C header files to DIR instead of the CWD
  -h, --help                    Show this help and quit
  --ignore-include-not-found    Continue to process the configuration file when
                                included files are not found
  -I DIR, --include-dir=DIR     Add DIR to the list of directories to be
                                searched for inclusion files
  -m DIR, --metadata-dir=DIR    Write the metadata stream file to DIR instead of
                                the CWD
  -p PREFIX, --prefix=PREFIX    Set the configuration prefix to PREFIX''')


# Returns a source and metadata stream file generating command object
# from the specific command-line arguments `orig_args`.
def _gen_cmd_cfg_from_args(orig_args: barectf_argpar.OrigArgs) -> '_GenCmd':
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

    # get common configuration file command CLI configuration
    cfg_cmd_cfg = _cfg_cmd_cfg_from_parse_res(res)

    # directories
    c_source_dir = _opt_item_val(res.items, 'code-dir', os.getcwd())
    c_header_dir = _opt_item_val(res.items, 'headers-dir', os.getcwd())
    metadata_stream_dir = _opt_item_val(res.items, 'metadata-dir', os.getcwd())

    for dir in [c_source_dir, c_header_dir, metadata_stream_dir]:
        if not os.path.isdir(dir):
            raise _CliError(f'`{dir}` is not an existing directory')

    # other options
    dump_config = _opt_item_val(res.items, 'dump-config', False)
    v2_prefix = _opt_item_val(res.items, 'prefix')

    return _GenCmd(_GenCmdCfg(cfg_cmd_cfg.cfg_file_path, c_source_dir, c_header_dir,
                              metadata_stream_dir, cfg_cmd_cfg.inclusion_dirs,
                              cfg_cmd_cfg.ignore_inclusion_file_not_found, dump_config, v2_prefix))


def _show_effective_cfg_cmd_usage():
    print('''Usage: barectf show-effective-configuration [--include-dir=DIR]...
                                            [--ignore-include-not-found]
                                            [--indent-spaces=COUNT] CONFIG-FILE-PATH
       barectf show-effective-configuration --help

Print the effective configuration file for a the configuration file
CONFIG-FILE-PATH.

Options:
  -h, --help                    Show this help and quit
  --ignore-include-not-found    Continue to process the configuration file when
                                included files are not found
  -I DIR, --include-dir=DIR     Add DIR to the list of directories to be
                                searched for inclusion files
  --indent-spaces=COUNT         Use COUNT spaces at a time to indent YAML lines
                                instead of 2''')


# Returns an effective configuration showing command object from the
# specific command-line arguments `orig_args`.
def _show_effective_cfg_cfg_from_args(orig_args: barectf_argpar.OrigArgs) -> '_ShowEffectiveCfgCmd':
    # parse original arguments
    opt_descrs = [
        barectf_argpar.OptDescr('h', 'help'),
        barectf_argpar.OptDescr('I', 'include-dir', True),
        barectf_argpar.OptDescr(long_name='indent-spaces', has_arg=True),
        barectf_argpar.OptDescr(long_name='ignore-include-not-found'),
    ]
    res = barectf_argpar.parse(orig_args, opt_descrs)
    assert len(res.ingested_orig_args) == len(orig_args)

    # command help?
    if len(_find_opt_items(res.items, 'help')) > 0:
        _show_effective_cfg_cmd_usage()
        sys.exit()

    # get common configuration command CLI configuration
    cfg_cmd_cfg = _cfg_cmd_cfg_from_parse_res(res)

    # other options
    indent_space_count = _opt_item_val(res.items, 'indent-spaces', 2)

    try:
        indent_space_count = int(indent_space_count)
    except (ValueError, TypeError):
        raise _CliError(f'Invalid `--indent-spaces` option argument: `{indent_space_count}`')

    if indent_space_count < 1 or indent_space_count > 8:
        raise _CliError(f'Invalid `--indent-spaces` option argument (`{indent_space_count}`): expecting a value in [1, 8]')

    return _ShowEffectiveCfgCmd(_ShowEffectiveCfgCmdCfg(cfg_cmd_cfg.cfg_file_path,
                                                        cfg_cmd_cfg.inclusion_dirs,
                                                        cfg_cmd_cfg.ignore_inclusion_file_not_found,
                                                        Count(indent_space_count)))


def _show_cfg_version_cmd_usage():
    print('''Usage: barectf show-configuration-version CONFIG-FILE-PATH
       barectf show-configuration-version --help

Print the major version (2 or 3) of the configuration file CONFIG-FILE-PATH.

Options:
  -h, --help    Show this help and quit''')


# Returns a configuration version showing command object from the
# specific command-line arguments `orig_args`.
def _show_cfg_version_cfg_from_args(orig_args: barectf_argpar.OrigArgs) -> '_ShowCfgVersionCmd':
    # parse original arguments
    opt_descrs = [
        barectf_argpar.OptDescr('h', 'help'),
    ]
    res = barectf_argpar.parse(orig_args, opt_descrs)
    assert len(res.ingested_orig_args) == len(orig_args)

    # command help?
    if len(_find_opt_items(res.items, 'help')) > 0:
        _show_cfg_version_cmd_usage()
        sys.exit()

    # check configuration file path
    cfg_file_path = _cfg_file_path_from_parse_res(res)

    return _ShowCfgVersionCmd(_ShowCfgVersionCmdCfg(cfg_file_path))


def _print_general_usage():
    print('''Usage: barectf COMMAND COMMAND-ARGS
       barectf --help
       barectf --version

General options:
  -h, --help       Show this help and quit
  -V, --version    Show version and quit

Available commands:
  gen:
  generate:
    Generate the C source and CTF metadata stream files of a tracer from a
    configuration file.

  show-effective-configuration:
  show-effective-config:
  show-effective-cfg:
    Print the effective configuration file for a given configuration file and
    inclusion directories.

  show-configuration-version:
  show-config-version:
  show-cfg-version
    Print the major version of a given configuration file.

Run `barectf COMMAND --help` to show the help of COMMAND.''')


# Returns a command object from the command-line arguments `orig_args`.
#
# All the `orig_args` elements are considered.
def _cmd_from_args(orig_args: barectf_argpar.OrigArgs) -> '_Cmd':
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
    res = barectf_argpar.parse(orig_args, general_opt_descrs, False)

    # find command name, collecting preceding (common) option items
    cmd_from_args_funcs = {
        'generate': _gen_cmd_cfg_from_args,
        'gen': _gen_cmd_cfg_from_args,
        'show-effective-configuration': _show_effective_cfg_cfg_from_args,
        'show-effective-config': _show_effective_cfg_cfg_from_args,
        'show-effective-cfg': _show_effective_cfg_cfg_from_args,
        'show-configuration-version': _show_cfg_version_cfg_from_args,
        'show-config-version': _show_cfg_version_cfg_from_args,
        'show-cfg-version': _show_cfg_version_cfg_from_args,
    }
    general_opt_items: List[barectf_argpar._OptItem] = []
    cmd_first_orig_arg_index = None
    cmd_from_args_func = None

    for item in res.items:
        if type(item) is barectf_argpar._NonOptItem:
            item = typing.cast(barectf_argpar._NonOptItem, item)
            cmd_from_args_func = cmd_from_args_funcs.get(item.text)

            if cmd_from_args_func is None:
                cmd_first_orig_arg_index = item.orig_arg_index
            else:
                cmd_first_orig_arg_index = Index(item.orig_arg_index + 1)

            break
        else:
            assert type(item) is barectf_argpar._OptItem
            general_opt_items.append(typing.cast(barectf_argpar._OptItem, item))

    # general help?
    if len(_find_opt_items(general_opt_items, 'help')) > 0:
        _print_general_usage()
        sys.exit()

    # version?
    if len(_find_opt_items(general_opt_items, 'version')) > 0:
        print(f'barectf {barectf.__version__}')
        sys.exit()

    # create command object
    cmd_orig_args = orig_args[cmd_first_orig_arg_index:]

    if cmd_from_args_func is None:
        # default `generate` command
        return _gen_cmd_cfg_from_args(cmd_orig_args)
    else:
        return cmd_from_args_func(cmd_orig_args)


class _CmdCfg:
    pass


class _CfgCmdCfg(_CmdCfg):
    def __init__(self, cfg_file_path: str, inclusion_dirs: List[str],
                 ignore_inclusion_file_not_found: bool):
        self._cfg_file_path = cfg_file_path
        self._inclusion_dirs = inclusion_dirs
        self._ignore_inclusion_file_not_found = ignore_inclusion_file_not_found

    @property
    def cfg_file_path(self) -> str:
        return self._cfg_file_path

    @property
    def inclusion_dirs(self) -> List[str]:
        return self._inclusion_dirs

    @property
    def ignore_inclusion_file_not_found(self) -> bool:
        return self._ignore_inclusion_file_not_found


class _Cmd:
    def __init__(self, cfg: _CmdCfg):
        self._cfg = cfg

    @property
    def cfg(self) -> _CmdCfg:
        return self._cfg

    def exec(self):
        raise NotImplementedError


class _GenCmdCfg(_CfgCmdCfg):
    def __init__(self, cfg_file_path: str, c_source_dir: str, c_header_dir: str,
                 metadata_stream_dir: str, inclusion_dirs: List[str],
                 ignore_inclusion_file_not_found: bool, dump_config: bool, v2_prefix: str):
        super().__init__(cfg_file_path, inclusion_dirs, ignore_inclusion_file_not_found)
        self._c_source_dir = c_source_dir
        self._c_header_dir = c_header_dir
        self._metadata_stream_dir = metadata_stream_dir
        self._dump_config = dump_config
        self._v2_prefix = v2_prefix

    @property
    def c_source_dir(self) -> str:
        return self._c_source_dir

    @property
    def c_header_dir(self) -> str:
        return self._c_header_dir

    @property
    def metadata_stream_dir(self) -> str:
        return self._metadata_stream_dir

    @property
    def dump_config(self) -> bool:
        return self._dump_config

    @property
    def v2_prefix(self) -> str:
        return self._v2_prefix


# Source and metadata stream file generating command.
class _GenCmd(_Cmd):
    def exec(self):
        # create configuration
        try:
            with open(self.cfg.cfg_file_path) as f:
                if self.cfg.dump_config:
                    # print effective configuration file
                    print(barectf.effective_configuration_file(f, True, self.cfg.inclusion_dirs,
                                                               self.cfg.ignore_inclusion_file_not_found))

                    # barectf.configuration_from_file() reads the file again
                    # below: rewind.
                    f.seek(0)

                config = barectf.configuration_from_file(f, True, self.cfg.inclusion_dirs,
                                                         self.cfg.ignore_inclusion_file_not_found)
        except barectf._ConfigurationParseError as exc:
            _print_config_error(exc)
        except Exception as exc:
            _print_unknown_exc(exc)

        if self.cfg.v2_prefix is not None:
            # Override prefixes.
            #
            # For historical reasons, the `--prefix` option applies the
            # barectf 2 configuration prefix rules. Therefore, get the
            # equivalent barectf 3 prefixes first.
            v3_prefixes = barectf_config_parse_common._v3_prefixes_from_v2_prefix(self.cfg.v2_prefix)
            cg_opts = config.options.code_generation_options
            cg_opts = barectf.ConfigurationCodeGenerationOptions(v3_prefixes.identifier,
                                                                 v3_prefixes.file_name,
                                                                 cg_opts.default_data_stream_type,
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
            write_file(self.cfg.metadata_stream_dir, code_gen.generate_metadata_stream())

            # generate and write C header files
            write_files(self.cfg.c_header_dir, code_gen.generate_c_headers())

            # generate and write C source files
            write_files(self.cfg.c_source_dir, code_gen.generate_c_sources())
        except Exception as exc:
            # We know `config` is valid, therefore the code generator cannot
            # fail for a reason known to barectf.
            _print_unknown_exc(exc)


class _ShowEffectiveCfgCmdCfg(_CfgCmdCfg):
    def __init__(self, cfg_file_path: str, inclusion_dirs: List[str],
                 ignore_inclusion_file_not_found: bool, indent_space_count: Count):
        super().__init__(cfg_file_path, inclusion_dirs, ignore_inclusion_file_not_found)
        self._indent_space_count = indent_space_count

    @property
    def indent_space_count(self) -> Count:
        return self._indent_space_count


# Effective configuration showing command.
class _ShowEffectiveCfgCmd(_Cmd):
    def exec(self):
        try:
            with open(self.cfg.cfg_file_path) as f:
                print(barectf.effective_configuration_file(f, True, self.cfg.inclusion_dirs,
                                                           self.cfg.ignore_inclusion_file_not_found,
                                                           self.cfg.indent_space_count))
        except barectf._ConfigurationParseError as exc:
            _print_config_error(exc)
        except Exception as exc:
            _print_unknown_exc(exc)


class _ShowCfgVersionCmdCfg(_CmdCfg):
    def __init__(self, cfg_file_path: str):
        self._cfg_file_path = cfg_file_path

    @property
    def cfg_file_path(self) -> str:
        return self._cfg_file_path


class _ShowCfgVersionCmd(_Cmd):
    def exec(self):
        try:
            with open(self.cfg.cfg_file_path) as f:
                print(barectf.configuration_file_major_version(f))
        except barectf._ConfigurationParseError as exc:
            _print_config_error(exc)
        except Exception as exc:
            _print_unknown_exc(exc)


def _run():
    # create command from arguments
    try:
        cmd = _cmd_from_args(sys.argv[1:])
    except barectf_argpar._Error as exc:
        _print_error(f'Command-line: For argument `{exc.orig_arg}`: {exc.msg}')
    except _CliError as exc:
        _print_error(f'Command-line: {exc}')

    # execute command
    cmd.exec()
