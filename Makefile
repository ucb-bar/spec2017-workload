# We use a branch of Speckle (https://github.com/ccelio/Speckle) to cross
# compile the binaries for SPEC2017. These can be compiled locally on a machine
# with the Spec installation, and the overlay directories
# ($SPECKLE_DIR/build/overlay) can be moved EC2

# Default to the submodule
SPECKLE_DIR ?= speckle
#Default to ref input size for SPEC17
INPUT ?= ref

#TODO: Provide runscripts for fp{speed, rate}
spec17_suites = intrate intspeed
spec17_rootfs_dirs = $(patsubst %, spec17-%, $(spec17-suites))

$(SPECKLE_DIR)/build/overlay/%/$(INPUT):
	cd $(SPECKLE_DIR) && ./gen_binaries.sh --compile --suite $* --input $(INPUT)

spec17-%: $(SPECKLE_DIR)/build/overlay/%/$(INPUT);
	echo $^

clean:
	rm -rf $(SPECKLE_DIR)/build

.PHONY: $(spec17_overlays) $(spec17_rootfs_dirs) clean
.PRECIOUS: $(SPECKLE_DIR)/build/overlay/%/$(INPUT)
