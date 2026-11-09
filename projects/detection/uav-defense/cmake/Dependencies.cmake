find_package(OpenCV REQUIRED COMPONENTS core imgproc imgcodecs videoio highgui)

find_package(yaml-cpp CONFIG REQUIRED)
add_library(uavsd::yaml INTERFACE IMPORTED)
if(TARGET yaml-cpp::yaml-cpp)
  target_link_libraries(uavsd::yaml INTERFACE yaml-cpp::yaml-cpp)
else()
  target_link_libraries(uavsd::yaml INTERFACE yaml-cpp)
endif()

set(ONNXRUNTIME_ROOT "" CACHE PATH "ONNX Runtime install prefix")

find_package(onnxruntime CONFIG QUIET HINTS ${ONNXRUNTIME_ROOT})
add_library(uavsd::onnxruntime INTERFACE IMPORTED)
if(TARGET onnxruntime::onnxruntime)
  target_link_libraries(uavsd::onnxruntime INTERFACE onnxruntime::onnxruntime)
else()
  find_path(ONNXRUNTIME_INCLUDE_DIR
    NAMES onnxruntime_cxx_api.h
    HINTS ${ONNXRUNTIME_ROOT}
    PATH_SUFFIXES include include/onnxruntime include/onnxruntime/core/session
  )
  find_library(ONNXRUNTIME_LIBRARY
    NAMES onnxruntime
    HINTS ${ONNXRUNTIME_ROOT}
    PATH_SUFFIXES lib lib64
  )
  if(NOT ONNXRUNTIME_INCLUDE_DIR OR NOT ONNXRUNTIME_LIBRARY)
    message(FATAL_ERROR "ONNX Runtime not found. Set -DONNXRUNTIME_ROOT=<install prefix>.")
  endif()
  target_include_directories(uavsd::onnxruntime INTERFACE ${ONNXRUNTIME_INCLUDE_DIR})
  target_link_libraries(uavsd::onnxruntime INTERFACE ${ONNXRUNTIME_LIBRARY})
endif()

if(UAVSD_BUILD_TESTS)
  include(FetchContent)
  FetchContent_Declare(googletest
    URL https://github.com/google/googletest/releases/download/v1.15.2/googletest-1.15.2.tar.gz
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
  )
  set(INSTALL_GTEST OFF CACHE BOOL "" FORCE)
  set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
  FetchContent_MakeAvailable(googletest)
endif()
