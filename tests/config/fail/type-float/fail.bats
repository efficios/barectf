#!/usr/bin/env bats

load ../../../common
load ../../common

@test 'unknown property in float type object makes barectf fail' {
  barectf_assert_file_exists unknown-prop.yaml
  barectf_config_check_fail
}

@test 'no "size" property in float type object makes barectf fail' {
  barectf_assert_file_exists size-no.yaml
  barectf_config_check_fail
}

@test 'wrong "size" property type in float type object makes barectf fail' {
  barectf_assert_file_exists size-invalid-type.yaml
  barectf_config_check_fail
}

@test 'unknown property in float type object "size" property makes barectf fail' {
  barectf_assert_file_exists size-unknown-prop.yaml
  barectf_config_check_fail
}

@test 'no "exp" property in float type object "size" property makes barectf fail' {
  barectf_assert_file_exists size-exp-no.yaml
  barectf_config_check_fail
}

@test 'no "mant" property in float type object "size" property makes barectf fail' {
  barectf_assert_file_exists size-mant-no.yaml
  barectf_config_check_fail
}

@test 'sum of "mant" and "exp" properties of float type size object not a multiple of 32 property makes barectf fail' {
  barectf_assert_file_exists size-exp-mant-wrong-sum.yaml
  barectf_config_check_fail
}

@test 'wrong "align" property type in float type object makes barectf fail' {
  barectf_assert_file_exists align-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "align" property (0) in float type object makes barectf fail' {
  barectf_assert_file_exists align-0.yaml
  barectf_config_check_fail
}

@test 'invalid "align" property (3) in float type object makes barectf fail' {
  barectf_assert_file_exists align-3.yaml
  barectf_config_check_fail
}

@test 'wrong "byte-order" property type in float type object makes barectf fail' {
  barectf_assert_file_exists bo-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "byte-order" property in float type object makes barectf fail' {
  barectf_assert_file_exists bo-invalid.yaml
  barectf_config_check_fail
}
