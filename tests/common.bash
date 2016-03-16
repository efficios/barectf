barectf_assert_file_exists() {
  pushd "$BATS_TEST_DIRNAME"

  if [ ! -f "$1" ]; then
    echo "FATAL: "$1" does not exist" 1>&2
    return 1
  fi

  run barectf "$1"
  local rc=$?
  popd
  return $rc
}
