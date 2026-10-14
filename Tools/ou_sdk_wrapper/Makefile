# Zero-dependency build for the ou_sdk wrapper.
#
# The rest of this repo's host tools are pure-stdlib Python, so a CMake-only
# build would be the one thing you cannot run without extra packages. Use this
# when CMake is not installed; prefer CMakeLists.txt otherwise (it also emits
# the CMake package config a C++ consumer may want).
#
#   make OU_SDK_ROOT=/path/to/ou-sdk-0.4.1
#   make OU_SDK_ROOT=/path/to/ou-sdk-0.4.1 selftest
#
OU_SDK_ROOT ?=
BUILD ?= build
CXX ?= c++
CXXFLAGS ?= -std=c++20 -O2 -fPIC -Wall -Wextra

SDK_INC := $(OU_SDK_ROOT)/include
SDK_LIB := $(abspath $(OU_SDK_ROOT)/lib)
BUILD_ABS := $(abspath $(BUILD))

LIB := $(BUILD)/libou_link_wrap.so
PROBE := $(BUILD)/ou_link_probe

.PHONY: all check selftest clean

all: $(LIB) $(PROBE)

check:
	@test -n "$(OU_SDK_ROOT)" || { \
	  echo "OU_SDK_ROOT is not set: make OU_SDK_ROOT=/path/to/ou-sdk-0.4.1"; exit 1; }
	@test -f "$(SDK_INC)/ou/crypto.hpp" || { \
	  echo "no $(SDK_INC)/ou/crypto.hpp -- that is not an ou_sdk headers tree"; exit 1; }

$(BUILD):
	@mkdir -p $(BUILD)

$(LIB): src/sealed_link.cpp src/ou_link_c.cpp include/ou_wrap/sealed_link.hpp include/ou_wrap/ou_link.h | check $(BUILD)
	$(CXX) $(CXXFLAGS) -Iinclude -I$(SDK_INC) -shared -o $@ \
	  src/sealed_link.cpp src/ou_link_c.cpp \
	  -L$(SDK_LIB) -lou_crypto \
	  -Wl,-rpath,$(SDK_LIB) -Wl,-rpath,'$$ORIGIN'

$(PROBE): example/ou_link_probe.cpp $(LIB) | check $(BUILD)
	$(CXX) $(CXXFLAGS) -Iinclude -I$(SDK_INC) -o $@ example/ou_link_probe.cpp \
	  -L$(BUILD_ABS) -lou_link_wrap \
	  -L$(SDK_LIB) -lou_crypto \
	  -Wl,-rpath,$(BUILD_ABS) -Wl,-rpath,$(SDK_LIB)

selftest: all
	$(PROBE) --selftest

clean:
	rm -rf $(BUILD)
