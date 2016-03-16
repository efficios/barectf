barectf_config_check_fail() {
  if [ $status -eq 0 ]; then
    echo "Fail: exit code is 0" 1>&2
    return 1
  fi

  pushd "$BATS_TEST_DIRNAME"
  local find_output="$(find -iname '*.c' -o -iname '*.h' -o -iname metadata)"
  popd

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
