CC ?= cc
CFLAGS ?= -std=c11 -O2
CPPFLAGS ?= -Iinclude
LDFLAGS ?=
LDLIBS ?= -lm

SRC := $(wildcard src/*.c)
BIN_DIR := bin
TARGET := $(BIN_DIR)/app

.PHONY: all clean run ui

all: $(TARGET)

$(TARGET): $(SRC) | $(BIN_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $(SRC) $(LDFLAGS) $(LDLIBS)

$(BIN_DIR):
	mkdir -p $(BIN_DIR)

run: $(TARGET)
	./$(TARGET)

ui:
	.venv/bin/python -m streamlit run dashboard.py

clean:
	rm -f $(TARGET)
