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
