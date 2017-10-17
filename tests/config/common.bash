# The MIT License (MIT)
#
# Copyright (c) 2016 Philippe Proulx <pproulx@efficios.com>
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

barectf_assert_file_exists() {
  if [ ! -f "$1" ]; then
    echo "FATAL: "$1" does not exist" 1>&2
    return 1
  fi

  if ! which barectf > /dev/null; then
    echo "FATAL: cannot find barectf tool" 1>&2
    return 1
  fi
}

barectf_config_check_success() {
  pushd "$BATS_TEST_DIRNAME" >/dev/null

  if ! barectf_assert_file_exists "$1"; then
    popd >/dev/null
    return 1
  fi

  run barectf "$1"
  popd >/dev/null

  if [ "$status" -ne 0 ]; then
    echo "Fail: exit code is $status" 1>&2
    return 1
  fi
}

barectf_config_check_fail() {
  pushd "$BATS_TEST_DIRNAME" >/dev/null

  if ! barectf_assert_file_exists "$1"; then
    popd >/dev/null
    return 1
  fi

  run barectf "$1"

  if [ "$status" -eq 0 ]; then
    echo "Fail: exit code is 0" 1>&2
    popd >/dev/null
    return 1
  fi

  local find_output="$(find -iname '*.c' -o -iname '*.h' -o -iname metadata)"
  popd >/dev/null

  if [ -n "$find_output" ]; then
    echo "Fail: barectf generated files" 1>&2
    return 1
  fi
}

setup() {
  :
}

teardown() {
  rm -f *ctf.c *ctf.h *ctf.o *ctf-bitfield.h metadata
}
