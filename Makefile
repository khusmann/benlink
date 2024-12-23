.PHONY: docs

all: docs

docs:
	pdoc ./src/benlink -o docs --logo /logo.svg
	cp logo.svg docs/logo.svg

preview-docs:
	python3 -m http.server --directory docs
