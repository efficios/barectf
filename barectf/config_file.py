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

import barectf.config_parse as barectf_config_parse
import barectf.config as barectf_config
from barectf.typing import Count, VersionNumber
from typing import Optional, List, TextIO


def effective_configuration_file(file: TextIO, with_package_inclusion_directory: bool = True,
                                 inclusion_directories: Optional[List[str]] = None,
                                 ignore_inclusion_not_found: bool = False,
                                 indent_space_count: Count = Count(2)) -> str:
    if inclusion_directories is None:
        inclusion_directories = []

    return barectf_config_parse._effective_config_file(file, with_package_inclusion_directory,
                                                       inclusion_directories,
                                                       ignore_inclusion_not_found,
                                                       indent_space_count)


def configuration_from_file(file: TextIO, with_package_inclusion_directory: bool = True,
                            inclusion_directories: Optional[List[str]] = None,
                            ignore_inclusion_not_found: bool = False) -> barectf_config.Configuration:
    if inclusion_directories is None:
        inclusion_directories = []

    return barectf_config_parse._from_file(file, with_package_inclusion_directory,
                                           inclusion_directories, ignore_inclusion_not_found)


def configuration_file_major_version(file: TextIO) -> VersionNumber:
    return barectf_config_parse._config_file_major_version(file)
