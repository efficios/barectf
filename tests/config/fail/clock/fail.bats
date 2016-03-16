#!/usr/bin/env bats

load ../../../common
load ../../common

@test 'unknown property in clock object makes barectf fail' {
  barectf_assert_file_exists unknown-prop.yaml
  barectf_config_check_fail
}

@test 'wrong "freq" property type in clock object makes barectf fail' {
  barectf_assert_file_exists freq-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "freq" property (0) in clock object makes barectf fail' {
  barectf_assert_file_exists freq-0.yaml
  barectf_config_check_fail
}

@test 'invalid "freq" property (negative) in clock object makes barectf fail' {
  barectf_assert_file_exists freq-neg.yaml
  barectf_config_check_fail
}

@test 'wrong "description" property type in clock object makes barectf fail' {
  barectf_assert_file_exists description-invalid-type.yaml
  barectf_config_check_fail
}

@test 'wrong "uuid" property type in clock object makes barectf fail' {
  barectf_assert_file_exists uuid-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "uuid" property in clock object makes barectf fail' {
  barectf_assert_file_exists uuid-invalid.yaml
  barectf_config_check_fail
}

@test 'wrong "error-cycles" property type in clock object makes barectf fail' {
  barectf_assert_file_exists ec-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "error-cycles" property in clock object makes barectf fail' {
  barectf_assert_file_exists ec-invalid.yaml
  barectf_config_check_fail
}

@test 'wrong "offset" property type in clock object makes barectf fail' {
  barectf_assert_file_exists offset-invalid-type.yaml
  barectf_config_check_fail
}

@test 'wrong "absolute" property type in clock object makes barectf fail' {
  barectf_assert_file_exists absolute-invalid-type.yaml
  barectf_config_check_fail
}

@test 'unknown property in clock offset object makes barectf fail' {
  barectf_assert_file_exists offset-unknown-prop.yaml
  barectf_config_check_fail
}

@test 'wrong "seconds" property type in clock offset object makes barectf fail' {
  barectf_assert_file_exists offset-seconds-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "seconds" property in clock offset object makes barectf fail' {
  barectf_assert_file_exists offset-seconds-neg.yaml
  barectf_config_check_fail
}

@test 'wrong "cycles" property type in clock offset object makes barectf fail' {
  barectf_assert_file_exists offset-cycles-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "cycles" property in clock offset object makes barectf fail' {
  barectf_assert_file_exists offset-cycles-neg.yaml
  barectf_config_check_fail
}

@test 'wrong "$return-ctype" property type in clock object makes barectf fail' {
  barectf_assert_file_exists rct-invalid-type.yaml
  barectf_config_check_fail
}
