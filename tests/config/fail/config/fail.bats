#!/usr/bin/env bats

load ../../../common
load ../../common

@test 'unknown property in config object makes barectf fail' {
  barectf_assert_file_exists unknown-prop.yaml
  barectf_config_check_fail
}

@test 'no "version" property in config object makes barectf fail' {
  barectf_assert_file_exists version-no.yaml
  barectf_config_check_fail
}

@test 'wrong "version" property type in config object makes barectf fail' {
  barectf_assert_file_exists version-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "version" property (1.9) in config object makes barectf fail' {
  barectf_assert_file_exists version-invalid-19.yaml
  barectf_config_check_fail
}

@test 'invalid "version" property (2.3) in config object makes barectf fail' {
  barectf_assert_file_exists version-invalid-23.yaml
  barectf_config_check_fail
}

@test 'wrong "prefix" property type in config object makes barectf fail' {
  barectf_assert_file_exists prefix-invalid-type.yaml
  barectf_config_check_fail
}

@test 'no valid C identifier in "prefix" property type in config object makes barectf fail' {
  barectf_assert_file_exists prefix-invalid-identifier.yaml
  barectf_config_check_fail
}

@test 'no "metadata" property in config object makes barectf fail' {
  barectf_assert_file_exists metadata-no.yaml
  barectf_config_check_fail
}

@test 'wrong "metadata" property type in config object makes barectf fail' {
  barectf_assert_file_exists metadata-invalid-type.yaml
  barectf_config_check_fail
}

@test 'wrong "options" property type in config object makes barectf fail' {
  barectf_assert_file_exists options-invalid-type.yaml
  barectf_config_check_fail
}

@test 'wrong "gen-prefix-def" property type in config options object makes barectf fail' {
  barectf_assert_file_exists options-gen-prefix-def-invalid-type.yaml
  barectf_config_check_fail
}

@test 'wrong "gen-default-stream-def" property type in config options object makes barectf fail' {
  barectf_assert_file_exists options-gen-default-stream-def-invalid-type.yaml
  barectf_config_check_fail
}
