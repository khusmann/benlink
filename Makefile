.PHONY: docs proto

all: docs

proto:
	cd src && python -m grpc_tools.protoc -I. \
		--python_out=. --pyi_out=. --grpc_python_out=. \
		benlink/firmware/_benshikj.proto

docs:
	pdoc ./src/benlink \
		'!benlink.firmware._benshikj_pb2' \
		'!benlink.firmware._benshikj_pb2_grpc' \
		-o docs --logo /logo.svg
	cp ./assets/logo-transparent.svg docs/logo.svg

preview-docs:
	python3 -m http.server --directory docs
