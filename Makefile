# We use a branch of Speckle (https://github.com/ccelio/Speckle) to cross
# compile the binaries for SPEC2017. These can be compiled locally on a machine
# with the Spec installation, and the overlay directories
# ($SPECKLE_DIR/build/overlay) can be moved EC2

# Default to the submodule
SPECKLE_DIR ?= speckle
#Default to ref input size for SPEC17
INPUT ?= ref
CROSS_COMPILE ?= riscv64-unknown-linux-gnu-
TMA_COUNTERS_DIR ?= $(CURDIR)/../../tests/tmatests

#TODO: Provide runscripts for fp{speed, rate}
spec17_suites = intrate intspeed
spec17_rootfs_dirs = $(patsubst %, spec17-%, $(spec17-suites))

# Cross-compile tma_reader so gen_binaries.sh picks it up automatically
# Counter definitions come from tma_counters.h (single source of truth)
$(SPECKLE_DIR)/tma_reader: $(SPECKLE_DIR)/tma_reader.c $(TMA_COUNTERS_DIR)/tma_counters.h
	$(CROSS_COMPILE)gcc -O2 -static -I$(TMA_COUNTERS_DIR) -o $@ $<

$(SPECKLE_DIR)/build/overlay/%/$(INPUT): $(SPECKLE_DIR)/tma_reader
	cd $(SPECKLE_DIR) && ./gen_binaries.sh --compile --suite $* --input $(INPUT)

spec17-%: $(SPECKLE_DIR)/build/overlay/%/$(INPUT);
	echo $^

clean:
	rm -rf $(SPECKLE_DIR)/build $(SPECKLE_DIR)/tma_reader

.PHONY: $(spec17_overlays) $(spec17_rootfs_dirs) clean
.PRECIOUS: $(SPECKLE_DIR)/build/overlay/%/$(INPUT)
