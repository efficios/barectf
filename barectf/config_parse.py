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

import barectf.config_parse_common as barectf_config_parse_common
from barectf.config_parse_common import _ConfigurationParseError
from barectf.config_parse_common import _MapNode
import barectf.config_parse_v2 as barectf_config_parse_v2
import barectf.config_parse_v3 as barectf_config_parse_v3
import barectf.config as barectf_config
import collections
from barectf.typing import Count, VersionNumber
from typing import Optional, List, TextIO
import typing


# Creates and returns a barectf 3 YAML configuration file parser to
# parse the file-like object `file`.
#
# `file` can be a barectf 2 or 3 configuration file.
def _create_v3_parser(file: TextIO, with_pkg_include_dir: bool, include_dirs: Optional[List[str]],
                      ignore_include_not_found: bool) -> barectf_config_parse_v3._Parser:
    try:
        root_node = barectf_config_parse_common._yaml_load(file)

        if type(root_node) is barectf_config_parse_common._ConfigNodeV3:
            # barectf 3 configuration file
            return barectf_config_parse_v3._Parser(file,
                                                   typing.cast(barectf_config_parse_common._ConfigNodeV3,
                                                               root_node),
                                                   with_pkg_include_dir, include_dirs,
                                                   ignore_include_not_found)
        elif type(root_node) is collections.OrderedDict:
            # barectf 2 configuration file
            v2_parser = barectf_config_parse_v2._Parser(file, typing.cast(_MapNode, root_node),
                                                        with_pkg_include_dir, include_dirs,
                                                        ignore_include_not_found)
            return barectf_config_parse_v3._Parser(file, v2_parser.config_node,
                                                   with_pkg_include_dir, include_dirs,
                                                   ignore_include_not_found)
        else:
            raise _ConfigurationParseError('Configuration',
                                           f'Root (configuration) node is not an object (it\'s a `{type(root_node)}`)')
    except _ConfigurationParseError as exc:
        barectf_config_parse_common._append_error_ctx(exc, 'Configuration',
                                                      'Cannot create configuration from YAML file')

        # satisfy static type checker (never reached)
        raise


def _from_file(file: TextIO, with_pkg_include_dir: bool, include_dirs: Optional[List[str]],
               ignore_include_not_found: bool) -> barectf_config.Configuration:
    return _create_v3_parser(file, with_pkg_include_dir, include_dirs, ignore_include_not_found).config


def _effective_config_file(file: TextIO, with_pkg_include_dir: bool,
                           include_dirs: Optional[List[str]], ignore_include_not_found: bool,
                           indent_space_count: Count) -> str:
    config_node = _create_v3_parser(file, with_pkg_include_dir, include_dirs,
                                    ignore_include_not_found).root_node
    return barectf_config_parse_common._yaml_dump(config_node, indent=indent_space_count,
                                                  default_flow_style=False, explicit_start=True,
                                                  explicit_end=True)


def _config_file_major_version(file: TextIO) -> VersionNumber:
    try:
        root_node = barectf_config_parse_common._yaml_load(file)

        if type(root_node) is barectf_config_parse_common._ConfigNodeV3:
            # barectf 3 configuration file
            return VersionNumber(3)
        else:
            # barectf 2 configuration file
            assert type(root_node) is collections.OrderedDict
            return VersionNumber(2)
    except _ConfigurationParseError as exc:
        barectf_config_parse_common._append_error_ctx(exc, 'Configuration', 'Cannot load YAML file')

        # satisfy static type checker (never reached)
        raise
