all : audiorx_demo audiotx_demo

audiorx_demo : audiorx_demo.o libsbc/sbc.o libsbc/bits.o libsbc/wave.o
	$(CC) -o $@ $^ -lbluetooth

audiotx_demo : audiotx_demo.o libsbc/sbc.o libsbc/bits.o libsbc/wave.o
	$(CC) -o $@ $^ -lbluetooth

.PHONY: all
