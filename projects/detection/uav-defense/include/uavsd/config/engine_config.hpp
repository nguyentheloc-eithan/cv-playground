#pragma once

#include <filesystem>
#include <map>
#include <string>

#include "uavsd/core/yolo_decode.hpp"

namespace uavsd {

struct EngineConfig {
    std::string engine = "yolo";
    std::filesystem::path weights;
    int imgsz = 640;
    float confThreshold = 0.25F;
    double iouThreshold = 0.7;
    std::string device = "cpu";
    YoloOutputFormat outputFormat = YoloOutputFormat::Auto;
    std::map<int, std::string> classNames;
};

[[nodiscard]] EngineConfig loadEngineConfig(const std::filesystem::path& path);

}
