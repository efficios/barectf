#!/usr/bin/env bash

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

if [ -z ${CC+x} ]; then
  # default to gcc
  export CC=gcc
fi

for d in ${test_dirs[@]}; do
  pushd $d
  $bats_bin $@ .
  popd

  if [ $? -ne 0 ]; then
    # latch error, but continue other tests
    rc=1
  fi
done

exit $rc
