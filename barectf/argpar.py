# The MIT License (MIT)
#
# Copyright (c) 2020 Philippe Proulx <pproulx@efficios.com>
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

import re
import typing
from typing import Optional, List, Iterable
from barectf.typing import Index, _OptStr


__all__ = ['OptDescr', '_OptItem', '_NonOptItem', '_Error', 'parse', 'OrigArgs']


# types
OrigArgs = List[str]


# Option descriptor.
class OptDescr:
    # Builds an option descriptor having the short name `short_name`
    # (without the leading `-`) and/or the long name `long_name`
    # (without the leading `--`).
    #
    # If `has_arg` is `True`, then it is expected that such an option
    # has an argument.
    def __init__(self, short_name: _OptStr = None, long_name: _OptStr = None,
                 has_arg: bool = False):
        assert short_name is not None or long_name is not None
        self._short_name = short_name
        self._long_name = long_name
        self._has_arg = has_arg

    @property
    def short_name(self) -> _OptStr:
        return self._short_name

    @property
    def long_name(self) -> _OptStr:
        return self._long_name

    @property
    def has_arg(self) -> Optional[bool]:
        return self._has_arg


class _Item:
    pass


# Parsed option argument item.
class _OptItem(_Item):
    def __init__(self, descr: OptDescr, arg_text: _OptStr = None):
        self._descr = descr
        self._arg_text = arg_text

    @property
    def descr(self) -> OptDescr:
        return self._descr

    @property
    def arg_text(self) -> _OptStr:
        return self._arg_text


# Parsed non-option argument item.
class _NonOptItem(_Item):
    def __init__(self, text: str, orig_arg_index: Index, non_opt_index: Index):
        self._text = text
        self._orig_arg_index = orig_arg_index
        self._non_opt_index = non_opt_index

    @property
    def text(self) -> str:
        return self._text

    @property
    def orig_arg_index(self) -> Index:
        return self._orig_arg_index

    @property
    def non_opt_index(self) -> Index:
        return self._non_opt_index


# Results of parse().
class _ParseRes:
    def __init__(self, items: List[_Item], ingested_orig_args: OrigArgs,
                 remaining_orig_args: OrigArgs):
        self._items = items
        self._ingested_orig_args = ingested_orig_args
        self._remaining_orig_args = remaining_orig_args

    @property
    def items(self) -> List[_Item]:
        return self._items

    @property
    def ingested_orig_args(self) -> OrigArgs:
        return self._ingested_orig_args

    @property
    def remaining_orig_args(self) -> OrigArgs:
        return self._remaining_orig_args


# Parsing error.
class _Error(Exception):
    def __init__(self, orig_arg_index: Index, orig_arg: str, msg: str):
        super().__init__(msg)
        self._orig_arg_index = orig_arg_index
        self._orig_arg = orig_arg
        self._msg = msg

    @property
    def orig_arg_index(self) -> Index:
        return self._orig_arg_index

    @property
    def orig_arg(self) -> str:
        return self._orig_arg

    @property
    def msg(self) -> str:
        return self._msg


# Results of parse_short_opts() and parse_long_opt(); internal.
class _OptParseRes(typing.NamedTuple):
    items: List[_Item]
    orig_arg_index_incr: int


# Parses the original arguments `orig_args` (list of strings),
# considering the option descriptors `opt_descrs` (set of `OptDescr`
# objects), and returns a corresponding `_ParseRes` object.
#
# This function considers ALL the elements of `orig_args`, including the
# first one, so that you would typically pass `sys.argv[1:]` to exclude
# the program/script name.
#
# This argument parser supports:
#
# * Short options without an argument, possibly tied together:
#
#       -f -auf -n
#
# * Short options with arguments:
#
#       -b 45 -f/mein/file -xyzhello
#
# * Long options without an argument:
#
#       --five-guys --burger-king --pizza-hut --subway
#
# * Long options with arguments:
#
#       --security enable --time=18.56
#
# * Non-option arguments (anything else).
#
# This function does NOT accept `--` as an original argument; while it
# means "end of options" for many command-line tools, this function is
# all about keeping the order of the arguments, so it doesn't mean much
# to put them at the end. This has the side effect that a non-option
# argument cannot have the form of an option, for example if you need to
# pass the exact relative path `--lentil-soup`. In that case, you would
# need to pass `./--lentil-soup`.
#
# This function accepts duplicate options (the resulting list of items
# contains one entry for each instance).
#
# On success, this function returns a `_ParseRes` object which contains
# a list of items as its `items` property. Each item is either an
# option item or a non-option item.
#
# The returned list contains the items in the same order that the
# original arguments `orig_args` were parsed, including non-option
# arguments. This means, for example, that for
#
#     --hello --meow=23 /path/to/file -b
#
# the function creates a list of four items: two options, one
# non-option, and one option.
#
# In the returned object, `ingested_orig_args` is the list of ingested
# original arguments to produce the resulting items, while `remaining_orig_args`
# is the list of remaining original arguments (not parsed because an
# unknown option was found and `fail_on_unknown_opt` was `False`).
#
# For example, with
#
#     --great --white contact nuance --shark nuclear
#
# if `--shark` is not described within `opt_descrs` and
# `fail_on_unknown_opt` is `False`, then `ingested_orig_args` contains
# `--great`, `--white`, `contact`, and `nuance` (two options, two
# non-options), whereas `remaining_orig_args` contains `--shark` and
# `nuclear`.
#
# This makes it possible to know where a command name is, for example.
# With those arguments:
#
#     --verbose --stuff=23 do-something --specific-opt -f -b
#
# and the option descriptors for `--verbose` and `--stuff` only, the
# function returns the `--verbose` and `--stuff` option items, the
# `do-something` non-option item, three ingested original arguments, and
# three remaining original arguments. This means you can start the next
# argument parsing stage, with option descriptors depending on the
# command name, with the remaining original arguments.
#
# Note that `len(ingested_orig_args)` is NOT always equal to the number
# of returned items, as
#
#     --hello -fdw
#
# for example contains two ingested original arguments, but four
# resulting option items.
#
# On failure, this function raises an `_Error` object.
def parse(orig_args: OrigArgs, opt_descrs: Iterable[OptDescr],
          fail_on_unknown_opt: bool = True) -> _ParseRes:
    # Finds and returns an option description amongst `opt_descrs`
    # having the short option name `short_name` OR the long option name
    # `long_name` (not both).
    def find_opt_descr(short_name: _OptStr = None,
                       long_name: _OptStr = None) -> Optional[OptDescr]:
        for opt_descr in opt_descrs:
            if short_name is not None and short_name == opt_descr.short_name:
                return opt_descr

            if long_name is not None and long_name == opt_descr.long_name:
                return opt_descr

        return None

    # Parses a short option original argument, returning an
    # `_OptParseRes` object.
    #
    # `orig_arg` can contain more than one short options, for example:
    #
    #     -xzv
    #
    # Moreover, `orig_arg` can contain the argument of a short option,
    # for example:
    #
    #     -xzvflol.mp3
    #
    # (`lol.mp3` is the argument of short option `-f`).
    #
    # If this function expects an argument for the last short option of
    # `orig_arg`, then it must be `next_orig_arg`, for example:
    #
    #     -xzvf lol.mp3
    #
    # If any of the short options of `orig_arg` is unknown, then this
    # function raises an error if `fail_on_unknown_opt` is `True`, or
    # returns `None` otherwise.
    def parse_short_opts() -> Optional[_OptParseRes]:
        short_opts = orig_arg[1:]
        items: List[_Item] = []
        done = False
        index = 0
        orig_arg_index_incr = 1

        while not done:
            short_opt = short_opts[index]
            opt_descr = find_opt_descr(short_name=short_opt)

            if opt_descr is None:
                # unknown option
                if fail_on_unknown_opt:
                    raise _Error(orig_arg_index, orig_arg, f'Unknown short option `-{short_opt}`')

                # discard collected arguments
                return None

            opt_arg = None

            if opt_descr.has_arg:
                if index == len(short_opts) - 1:
                    # last short option: use the next original argument
                    if next_orig_arg is None:
                        raise _Error(orig_arg_index, orig_arg,
                                     f'Expecting an argument for short option `-{short_opt}`')

                    opt_arg = next_orig_arg
                    orig_arg_index_incr += 1
                else:
                    # use remaining original argument's text
                    opt_arg = short_opts[index + 1:]

                done = True

            items.append(_OptItem(opt_descr, opt_arg))
            index += 1

            if index == len(short_opts):
                done = True

        return _OptParseRes(items, orig_arg_index_incr)

    # Parses a long option original argument, returning an
    # `_OptParseRes` object.
    #
    # `orig_arg` can contain a single long option, for example:
    #
    #     --header-dir
    #
    # Moreover, `orig_arg` can contain the long option's argument, for
    # example:
    #
    #     --header-dir=/path/to/dir
    #
    # If this function expects an argument for the long option, then it
    # must be `next_orig_arg`, for example:
    #
    #     --header-dir /path/to/dir
    #
    # If the long option is unknown, then this function raises an error
    # if `fail_on_unknown_opt` is `True`, or returns `None` otherwise.
    def parse_long_opt() -> Optional[_OptParseRes]:
        long_opt = orig_arg[2:]
        m = re.match(r'--([^=]+)=(.*)', orig_arg)

        if m:
            # `--long-opt=arg` form: isolate option name
            long_opt = m.group(1)

        opt_descr = find_opt_descr(long_name=long_opt)

        if opt_descr is None:
            # unknown option
            if fail_on_unknown_opt:
                raise _Error(orig_arg_index, orig_arg, f'Unknown long option `--{long_opt}`')

            # discard
            return None

        orig_arg_index_incr = 1

        if opt_descr.has_arg:
            if m:
                item = _OptItem(opt_descr, m.group(2))
            else:
                if next_orig_arg is None:
                    raise _Error(orig_arg_index, orig_arg,
                                 f'Expecting an argument for long option `--{long_opt}`')

                item = _OptItem(opt_descr, next_orig_arg)
                orig_arg_index_incr += 1
        else:
            # no option argument
            item = _OptItem(opt_descr, None)

        return _OptParseRes([item], orig_arg_index_incr)

    # parse original arguments
    items: List[_Item] = []
    orig_arg_index = Index(0)
    non_opt_index = Index(0)

    while orig_arg_index < len(orig_args):
        orig_arg = orig_args[orig_arg_index]

        # keep next original argument, if any
        next_orig_arg = None

        if orig_arg_index < len(orig_args) - 1:
            next_orig_arg = orig_args[orig_arg_index + 1]

        if orig_arg.startswith('-') and len(orig_arg) >= 2:
            # option
            if orig_arg[1] == '-':
                if orig_arg == '--':
                    raise _Error(orig_arg_index, orig_arg, 'Invalid `--` argument')

                # long option
                res = parse_long_opt()
            else:
                # short option(s)
                res = parse_short_opts()

            if res is None:
                # unknown option
                assert not fail_on_unknown_opt
                return _ParseRes(items, orig_args[:orig_arg_index], orig_args[orig_arg_index:])

            items += res.items
            orig_arg_index = Index(orig_arg_index + res.orig_arg_index_incr)
        else:
            # non-option
            items.append(_NonOptItem(orig_arg, orig_arg_index, non_opt_index))
            non_opt_index = Index(non_opt_index + 1)
            orig_arg_index = Index(orig_arg_index + 1)

    return _ParseRes(items, orig_args, [])
