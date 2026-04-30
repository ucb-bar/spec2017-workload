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

# Cross-compile tma_inject.o (ctor/dtor pair sourced from
# tests/tmatests/tma_inject.c). SPEC's runcpu links it into every speed
# benchmark via EXTRA_LIBS (see speckle/riscv.cfg). Flags must match SPEC's
# riscv.cfg (rv64imafdc / lp64d) so the .o is ABI-compatible with the rest.
$(SPECKLE_DIR)/tma_inject.o: $(TMA_COUNTERS_DIR)/tma_inject.c $(TMA_COUNTERS_DIR)/tma_counters.h
	$(CROSS_COMPILE)gcc -O2 -c -march=rv64imafdc -mabi=lp64d \
	    -I$(TMA_COUNTERS_DIR) -o $@ $<

$(SPECKLE_DIR)/build/overlay/%/$(INPUT): $(SPECKLE_DIR)/tma_inject.o
	cd $(SPECKLE_DIR) && TMA_INJECT_OBJ=$(abspath $(SPECKLE_DIR)/tma_inject.o) \
	    ./gen_binaries.sh --compile --suite $* --input $(INPUT)

spec17-%: $(SPECKLE_DIR)/build/overlay/%/$(INPUT);
	echo $^

clean:
	rm -rf $(SPECKLE_DIR)/build $(SPECKLE_DIR)/tma_inject.o

.PHONY: $(spec17_overlays) $(spec17_rootfs_dirs) clean
.PRECIOUS: $(SPECKLE_DIR)/build/overlay/%/$(INPUT)
