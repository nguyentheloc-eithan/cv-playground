include(GoogleTest)

add_executable(uavsd_core_tests
  core/letterbox_test.cpp
  core/metadata_test.cpp
  core/nms_test.cpp
  core/yolo_decode_test.cpp
  localization/bearing_test.cpp
)
target_link_libraries(uavsd_core_tests PRIVATE uavsd::core GTest::gtest_main)
gtest_discover_tests(uavsd_core_tests DISCOVERY_MODE PRE_TEST)

add_executable(uavsd_runtime_tests
  runtime/engine_config_test.cpp
  runtime/frame_source_test.cpp
  runtime/registry_test.cpp
)
target_link_libraries(uavsd_runtime_tests PRIVATE uavsd::runtime GTest::gtest_main)
gtest_discover_tests(uavsd_runtime_tests DISCOVERY_MODE PRE_TEST DISCOVERY_TIMEOUT 60)
