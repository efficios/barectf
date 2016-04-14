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

# source
SRC = barectf

# config
ASCIIDOC_CONF = asciidoc.conf
XSL_FILES = \
	manpage.xsl \
	manpage-callouts.xsl \
	manpage-bold-literal.xsl \
	manpage-links.xsl
XSL_SRC_FILES = $(addprefix xsl/,$(XSL_FILES))

# tools
ASCIIDOC ?= asciidoc
XMLTO ?= xmlto
ADOC = $(ASCIIDOC) -f $(ASCIIDOC_CONF) -d manpage \
	-a barectf_version=$(shell grep '^__version__' ../../barectf/__init__.py | grep -Po '\d+\.\d+\.\d+(?:-\w+)?')
ADOC_DOCBOOK = $(ADOC) -b docbook
XTO = $(XMLTO) -m $(firstword $(XSL_SRC_FILES)) man

# recipes
.PHONY: all

all: $(SRC).1

$(SRC).1.xml: $(SRC).1.txt $(ASCIIDOC_CONF)
	$(ADOC_DOCBOOK) -o $@ $<

$(SRC).1: $(SRC).1.xml $(XSL_SRC_FILES)
	$(XTO) $<

.PHONY: clean

clean:
	rm -f $(SRC).1 $(SRC).1.xml
