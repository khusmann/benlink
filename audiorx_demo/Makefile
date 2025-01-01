all : audiorx_demo

audiorx_demo : audiorx_demo.o \
			   sbc/wave.o \
			   sbc/decoder-sbc.o \
			   sbc/decoder-private.o \
			   sbc/dequant.o \
			   sbc/framing.c \
			   sbc/bitstream-decode.o \
			   sbc/alloc.o \
			   sbc/bitalloc.o \
			   sbc/bitalloc-sbc.o \
			   sbc/synthesis-sbc.o \
			   sbc/synthesis-8-generated.o \
			   sbc/synthesis-dct8.o
	$(CC) -o $@ $^ -lbluetooth -O0

.PHONY: all
