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

import os
import os.path
import barectf
import subprocess


def test_everything(request, tmpdir):
    yaml_path = os.path.join(os.path.dirname(request.fspath), 'configs',
                             'pass', 'everything', 'config.yaml')
    yaml_dir = os.path.dirname(yaml_path)

    with open(yaml_path) as f:
        cfg = barectf.configuration_from_file(f, inclusion_directories=[yaml_dir])

    cg = barectf.CodeGenerator(cfg)
    files = cg.generate_c_headers()
    files += cg.generate_c_sources()

    for file in files:
        with open(os.path.join(tmpdir, file.name), 'w') as f:
            f.write(file.contents)

    cc = os.environ.get('CC', 'cc')
    o_file = 'obj.o'
    subprocess.check_call([cc, '-c', '-o', o_file, files[-1].name], cwd=tmpdir)
    nm = os.environ.get('NM', 'nm')
    syms = subprocess.check_output([nm, o_file], cwd=tmpdir, universal_newlines=True)
    syms_to_check = [
        'bctf_init',
        'bctf_my_other_stream_close_packet',
        'bctf_my_other_stream_open_packet',
        'bctf_my_other_stream_trace_context_no_payload',
        'bctf_my_other_stream_trace_evev',
        'bctf_my_other_stream_trace_my_event',
        'bctf_my_other_stream_trace_no_context_no_payload',
        'bctf_my_other_stream_trace_oh_henry_event',
        'bctf_my_other_stream_trace_this_event',
        'bctf_my_stream_close_packet',
        'bctf_my_stream_open_packet',
        'bctf_my_stream_trace_my_event',
        'bctf_packet_buf',
        'bctf_packet_buf_addr',
        'bctf_packet_buf_size',
        'bctf_packet_events_discarded',
        'bctf_discarded_event_records_count',
        'bctf_packet_is_empty',
        'bctf_packet_is_full',
        'bctf_packet_is_open',
        'bctf_packet_set_buf',
        'bctf_packet_size',
    ]

    for sym in syms_to_check:
        assert sym in syms
