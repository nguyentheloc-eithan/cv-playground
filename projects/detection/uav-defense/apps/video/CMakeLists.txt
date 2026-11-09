add_executable(uavsd_video main.cpp)
target_link_libraries(uavsd_video PRIVATE uavsd::runtime)
uavsd_set_warnings(uavsd_video)
