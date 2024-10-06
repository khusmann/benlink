# Directories
INPUT_DIR := input
OUTPUT_DIR := logs

# Find all .zip files in the input directory
ZIP_FILES := $(shell find $(INPUT_DIR) -type f -name '*.zip')

# Replace input/ with output/ for the output files
OUTPUT_FILES := $(ZIP_FILES:$(INPUT_DIR)/%.zip=$(OUTPUT_DIR)/%.log)

# Default target
all: $(OUTPUT_FILES)

# Rule to process each .zip file
$(OUTPUT_DIR)/%.log: $(INPUT_DIR)/%.zip
	@mkdir -p $(dir $@)
	@echo "Processing $< -> $@"
	@./parse_bugreport.sh $< > $@