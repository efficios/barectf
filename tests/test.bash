#!/usr/bin/env bash

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

test_dirs=(
  "config/fail/clock"
  "config/fail/config"
  "config/fail/event"
  "config/fail/include"
  "config/fail/metadata"
  "config/fail/stream"
  "config/fail/trace"
  "config/fail/type"
  "config/fail/type-enum"
  "config/fail/type-float"
  "config/fail/type-int"
  "config/fail/type-string"
  "config/fail/type-struct"
  "config/fail/yaml"
  "config/pass/everything"
)
bats_bin="$(pwd)/bats/bin/bats"
rc=0

if [ -z "${CC+x}" ]; then
  # default to gcc
  export CC=gcc
fi

for d in "${test_dirs[@]}"; do
  pushd "$d" >/dev/null
  $bats_bin "${@}" .
  if [ $? -ne 0 ]; then
    # latch error, but continue other tests
    rc=1
  fi
  popd >/dev/null
done

exit $rc
