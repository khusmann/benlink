all : audiorx_demo

audiorx_demo : audiorx_demo.o libsbc/sbc.o libsbc/bits.o libsbc/wave.o
	cc -o audiorx_demo audiorx_demo.o libsbc/sbc.o libsbc/bits.o libsbc/wave.o -lbluetooth

.PHONY: all