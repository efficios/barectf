# The MIT License (MIT)
#
# Copyright (c) 2015-2020 Philippe Proulx <pproulx@efficios.com>
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

import barectf.config as barectf_config
import barectf.template as barectf_template
import jinja2
from typing import List, Optional
import typing


def _filt_bo_str(bo: barectf_config.ByteOrder) -> str:
    return {
        barectf_config.ByteOrder.LITTLE_ENDIAN: 'le',
        barectf_config.ByteOrder.BIG_ENDIAN: 'be',
    }[bo]


def _filt_disp_base_int(disp_base: barectf_config.DisplayBase) -> int:
    return {
        barectf_config.DisplayBase.BINARY: 2,
        barectf_config.DisplayBase.OCTAL: 8,
        barectf_config.DisplayBase.DECIMAL: 10,
        barectf_config.DisplayBase.HEXADECIMAL: 16,
    }[disp_base]


def _filt_int_ft_str(ft: barectf_config._FieldType) -> str:
    return _INT_FT_TEMPL.render(ft=ft,
                                is_signed=isinstance(ft, barectf_config.SignedIntegerFieldType))


def _gen_enum_ft(ft: barectf_config._FieldType) -> str:
    return _ENUM_FT_TEMPL.render(ft=ft)


def _gen_real_ft(ft: barectf_config._FieldType) -> str:
    return _REAL_FT_TEMPL.render(ft=ft)


def _gen_str_ft(ft: barectf_config._FieldType) -> str:
    return _STR_FT_TEMPL.render(ft=ft)


def _ft_chain(ft: barectf_config._FieldType) -> List[barectf_config._FieldType]:
    chain: List[barectf_config._FieldType] = []

    while isinstance(ft, barectf_config.StaticArrayFieldType):
        chain.append(ft)
        ft = ft.element_field_type

    chain.append(ft)
    return chain


def _gen_struct_ft(ft: barectf_config._FieldType) -> str:
    return _STRUCT_FT_TEMPL.render(ft=ft, ft_chain=_ft_chain)


_FT_CLS_TO_GEN_FT_FUNC = {
    barectf_config.UnsignedIntegerFieldType: _filt_int_ft_str,
    barectf_config.SignedIntegerFieldType: _filt_int_ft_str,
    barectf_config.UnsignedEnumerationFieldType: _gen_enum_ft,
    barectf_config.SignedEnumerationFieldType: _gen_enum_ft,
    barectf_config.RealFieldType: _gen_real_ft,
    barectf_config.StringFieldType: _gen_str_ft,
    barectf_config.StructureFieldType: _gen_struct_ft,
}


def _filt_ft_str(ft: barectf_config._FieldType) -> str:
    return _FT_CLS_TO_GEN_FT_FUNC[type(ft)](ft)


_TEMPL_FILTERS = {
    'bo_str': _filt_bo_str,
    'disp_base_int': _filt_disp_base_int,
    'int_ft_str': _filt_int_ft_str,
    'ft_str': _filt_ft_str,
}


def _create_template(name: str, is_file_template: bool = False,
                     cfg: Optional[barectf_config.Configuration] = None) -> barectf_template._Template:
    return barectf_template._Template(name, is_file_template, cfg,
                                      typing.cast(barectf_template._Filters, _TEMPL_FILTERS))


_ENUM_FT_TEMPL = _create_template('metadata-enum-ft.j2')
_INT_FT_TEMPL = _create_template('metadata-int-ft.j2')
_REAL_FT_TEMPL = _create_template('metadata-real-ft.j2')
_STR_FT_TEMPL = _create_template('metadata-str-ft.j2')
_STRUCT_FT_TEMPL = _create_template('metadata-struct-ft.j2')


def _from_config(cfg: barectf_config.Configuration) -> str:
    return _create_template('metadata.j2', True, cfg).render()
