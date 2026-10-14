cmake_minimum_required(VERSION 3.16)
project(ou_sdk_wrapper LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "" FORCE)
endif()

# ---------------------------------------------------------------------------
# Locate the ou_sdk 0.4.1 artifact (headers + prebuilt shared libs).
#
#   cmake -S . -B build -DOU_SDK_ROOT=/path/to/ou-sdk-0.4.1
#
# Extract it from the Harbor tarballs first; see README.md.
# ---------------------------------------------------------------------------
set(OU_SDK_ROOT "$ENV{OU_SDK_ROOT}" CACHE PATH "ou_sdk 0.4.1 root (contains include/ and lib/)")

if(NOT OU_SDK_ROOT)
  message(FATAL_ERROR
    "OU_SDK_ROOT is not set.\n"
    "  cmake -S . -B build -DOU_SDK_ROOT=/path/to/ou-sdk-0.4.1\n"
    "The directory must contain include/ou/crypto.hpp and lib/libou_crypto.so.")
endif()
if(NOT EXISTS "${OU_SDK_ROOT}/include/ou/crypto.hpp")
  message(FATAL_ERROR
    "OU_SDK_ROOT=${OU_SDK_ROOT} does not look like an ou_sdk headers tree "
    "(missing include/ou/crypto.hpp).")
endif()

# ---------------------------------------------------------------------------
# The wrapper: ou_sdk's crypto core + the sealed-stream layer it does not ship.
# ---------------------------------------------------------------------------
add_library(ou_link_wrap SHARED
  src/sealed_link.cpp
  src/ou_link_c.cpp)
add_library(ou::link_wrap ALIAS ou_link_wrap)

# ou_wrap/sealed_link.hpp includes <ou/crypto.hpp>, so the SDK include tree is
# part of this target's public interface.
target_include_directories(ou_link_wrap
  PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/include" "${OU_SDK_ROOT}/include")

target_link_directories(ou_link_wrap PRIVATE "${OU_SDK_ROOT}/lib")
target_link_libraries(ou_link_wrap PRIVATE ou_crypto)

set_target_properties(ou_link_wrap PROPERTIES
  BUILD_RPATH "${OU_SDK_ROOT}/lib"
  INSTALL_RPATH "${OU_SDK_ROOT}/lib")

# ---------------------------------------------------------------------------
# Interop probe: seal/open one frame from the command line, so the wrapper can
# be diffed byte-for-byte against an independent implementation
# (Tools/ou_crypto.py) without any hardware.
# ---------------------------------------------------------------------------
add_executable(ou_link_probe example/ou_link_probe.cpp)
# The probe also diffs against ou_sdk's own ShellCrypto::seal, so it links the
# SDK directly rather than only through the wrapper.
target_link_directories(ou_link_probe PRIVATE "${OU_SDK_ROOT}/lib")
target_link_libraries(ou_link_probe PRIVATE ou_link_wrap ou_crypto)
set_target_properties(ou_link_probe PROPERTIES
  BUILD_RPATH "${OU_SDK_ROOT}/lib;${CMAKE_BINARY_DIR}")
