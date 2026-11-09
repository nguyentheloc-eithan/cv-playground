cmake_minimum_required(VERSION 3.22)

project(uavs_defense VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

option(UAVSD_BUILD_TESTS "Build unit tests" ON)
option(UAVSD_BUILD_APPS "Build applications" ON)
option(UAVSD_WARNINGS_AS_ERRORS "Treat compiler warnings as errors" OFF)

list(APPEND CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/cmake)
include(Dependencies)

function(uavsd_set_warnings target)
  if(MSVC)
    target_compile_options(${target} PRIVATE /W4)
    if(UAVSD_WARNINGS_AS_ERRORS)
      target_compile_options(${target} PRIVATE /WX)
    endif()
  else()
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Wshadow -Wconversion)
    if(UAVSD_WARNINGS_AS_ERRORS)
      target_compile_options(${target} PRIVATE -Werror)
    endif()
  endif()
endfunction()

add_library(uavsd_core
  src/core/letterbox.cpp
  src/core/metadata.cpp
  src/core/nms.cpp
  src/core/types.cpp
  src/core/yolo_decode.cpp
  src/localization/bearing.cpp
)
add_library(uavsd::core ALIAS uavsd_core)
target_include_directories(uavsd_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
uavsd_set_warnings(uavsd_core)

add_library(uavsd_runtime
  src/config/engine_config.cpp
  src/engines/registry.cpp
  src/engines/yolo_onnx_engine.cpp
  src/inference/annotator.cpp
  src/inference/frame_source.cpp
)
add_library(uavsd::runtime ALIAS uavsd_runtime)
target_link_libraries(uavsd_runtime
  PUBLIC uavsd::core ${OpenCV_LIBS}
  PRIVATE uavsd::onnxruntime uavsd::yaml
)
target_include_directories(uavsd_runtime PUBLIC ${OpenCV_INCLUDE_DIRS})
uavsd_set_warnings(uavsd_runtime)

if(UAVSD_BUILD_APPS)
  add_subdirectory(apps/video)
endif()

if(UAVSD_BUILD_TESTS)
  enable_testing()
  add_subdirectory(tests)
endif()
