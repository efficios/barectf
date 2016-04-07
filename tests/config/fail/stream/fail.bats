#!/usr/bin/env bats

load ../../../common
load ../../common

@test 'unknown property in stream object makes barectf fail' {
  barectf_assert_file_exists unknown-prop.yaml
  barectf_config_check_fail
}

@test 'no "packet-context-type" property in stream object makes barectf fail' {
  barectf_assert_file_exists pct-no.yaml
  barectf_config_check_fail
}

@test 'wrong "packet-context-type" property type in stream object makes barectf fail' {
  barectf_assert_file_exists pct-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "packet-context-type" property field type (not a structure) in stream object makes barectf fail' {
  barectf_assert_file_exists pct-not-struct.yaml
  barectf_config_check_fail
}

@test 'invalid "timestamp_begin" field type (not an integer) in packet context type makes barectf fail' {
  barectf_assert_file_exists pct-tb-not-int.yaml
  barectf_config_check_fail
}

@test 'invalid "timestamp_begin" field type (signed) in packet context type makes barectf fail' {
  barectf_assert_file_exists pct-tb-wrong-signed.yaml
  barectf_config_check_fail
}

@test 'invalid "timestamp_begin" field type (not mapped to a clock) in packet context type makes barectf fail' {
  barectf_assert_file_exists pct-tb-wrong-pm.yaml
  barectf_config_check_fail
}

@test 'no "timestamp_begin" field with an existing "timestamp_end" field in packet context type makes barectf fail' {
  barectf_assert_file_exists pct-te-yes-tb-no.yaml
  barectf_config_check_fail
}

@test 'invalid "timestamp_end" field type (not an integer) in packet context type makes barectf fail' {
  barectf_assert_file_exists pct-te-not-int.yaml
  barectf_config_check_fail
}

@test 'invalid "timestamp_end" field type (signed) in packet context type makes barectf fail' {
  barectf_assert_file_exists pct-te-wrong-signed.yaml
  barectf_config_check_fail
}

@test 'invalid "timestamp_end" field type (not mapped to a clock) in packet context type makes barectf fail' {
  barectf_assert_file_exists pct-te-wrong-pm.yaml
  barectf_config_check_fail
}

@test 'no "timestamp_end" field with an existing "timestamp_begin" field in packet context type makes barectf fail' {
  barectf_assert_file_exists pct-tb-yes-te-no.yaml
  barectf_config_check_fail
}

@test '"timestamp_begin" field and "timestamp_end" field are not mapped to the same clock in packet context type makes barectf fail' {
  barectf_assert_file_exists pct-tb-te-different-clocks.yaml
  barectf_config_check_fail
}

@test 'invalid "packet_size" field type (not an integer) in packet context type makes barectf fail' {
  barectf_assert_file_exists pct-ps-not-int.yaml
  barectf_config_check_fail
}

@test 'invalid "packet_size" field type (signed) in packet context type makes barectf fail' {
  barectf_assert_file_exists pct-ps-wrong-signed.yaml
  barectf_config_check_fail
}

@test 'no "packet_size" field with an existing "content_size" field in packet context type makes barectf fail' {
  barectf_assert_file_exists pct-cs-yes-ps-no.yaml
  barectf_config_check_fail
}

@test 'invalid "content_size" field type (not an integer) in packet context type makes barectf fail' {
  barectf_assert_file_exists pct-cs-not-int.yaml
  barectf_config_check_fail
}

@test 'invalid "content_size" field type (signed) in packet context type makes barectf fail' {
  barectf_assert_file_exists pct-cs-wrong-signed.yaml
  barectf_config_check_fail
}

@test 'no "content_size" field with an existing "packet_size" field in packet context type makes barectf fail' {
  barectf_assert_file_exists pct-ps-yes-cs-no.yaml
  barectf_config_check_fail
}

@test '"content_size" field size greater than "packet_size" field size in packet context type makes barectf fail' {
  barectf_assert_file_exists pct-cs-gt-ps.yaml
  barectf_config_check_fail
}

@test 'invalid "events_discarded" field type (not an integer) in packet context type makes barectf fail' {
  barectf_assert_file_exists pct-ed-not-int.yaml
  barectf_config_check_fail
}

@test 'invalid "events_discarded" field type (signed) in packet context type makes barectf fail' {
  barectf_assert_file_exists pct-ed-wrong-signed.yaml
  barectf_config_check_fail
}

@test 'wrong "event-header-type" property type in stream object makes barectf fail' {
  barectf_assert_file_exists eht-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "event-header-type" property field type (not a structure) in stream object makes barectf fail' {
  barectf_assert_file_exists eht-not-struct.yaml
  barectf_config_check_fail
}

@test 'invalid "timestamp" field type (not an integer) in event header type makes barectf fail' {
  barectf_assert_file_exists eht-timestamp-not-int.yaml
  barectf_config_check_fail
}

@test 'invalid "timestamp" field type (signed) in event header type makes barectf fail' {
  barectf_assert_file_exists eht-timestamp-wrong-signed.yaml
  barectf_config_check_fail
}

@test 'invalid "timestamp" field type (not mapped to a clock) in event header type makes barectf fail' {
  barectf_assert_file_exists eht-timestamp-wrong-pm.yaml
  barectf_config_check_fail
}

@test 'invalid "id" field type (not an integer) in event header type makes barectf fail' {
  barectf_assert_file_exists eht-id-not-int.yaml
  barectf_config_check_fail
}

@test 'invalid "id" field type (signed) in event header type makes barectf fail' {
  barectf_assert_file_exists eht-id-wrong-signed.yaml
  barectf_config_check_fail
}

@test 'no event header type with multiple events in stream object makes barectf fail' {
  barectf_assert_file_exists eht-id-no-multiple-events.yaml
  barectf_config_check_fail
}

@test '"id" field type size too small for the number of stream events in event header type makes barectf fail' {
  barectf_assert_file_exists eht-id-too-small.yaml
  barectf_config_check_fail
}

@test 'wrong "event-context-type" property type in stream object makes barectf fail' {
  barectf_assert_file_exists ect-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "event-context-type" property field type (not a structure) in stream object makes barectf fail' {
  barectf_assert_file_exists ect-not-struct.yaml
  barectf_config_check_fail
}

@test 'no "events" property in stream object makes barectf fail' {
  barectf_assert_file_exists events-no.yaml
  barectf_config_check_fail
}

@test 'wrong "events" property type in stream object makes barectf fail' {
  barectf_assert_file_exists events-invalid-type.yaml
  barectf_config_check_fail
}

@test 'empty "events" property in stream object makes barectf fail' {
  barectf_assert_file_exists events-empty.yaml
  barectf_config_check_fail
}

@test 'invalid "events" key (invalid C identifier) in metadata object makes barectf fail' {
  barectf_assert_file_exists events-key-invalid-identifier.yaml
  barectf_config_check_fail
}

@test 'wrong "$default" property type in stream object makes barectf fail' {
  barectf_assert_file_exists default-invalid-type.yaml
  barectf_config_check_fail
}
