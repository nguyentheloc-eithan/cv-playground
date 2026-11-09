#include "uavsd/config/engine_config.hpp"

#include <yaml-cpp/yaml.h>

#include <stdexcept>

namespace uavsd {

namespace {

YoloOutputFormat parseOutputFormat(const std::string& value) {
    if (value == "auto") {
        return YoloOutputFormat::Auto;
    }
    if (value == "end2end") {
        return YoloOutputFormat::EndToEnd;
    }
    if (value == "raw") {
        return YoloOutputFormat::Raw;
    }
    throw std::invalid_argument("unknown output_format: " + value);
}

}  // namespace

EngineConfig loadEngineConfig(const std::filesystem::path& path) {
    const YAML::Node root = YAML::LoadFile(path.string());
    EngineConfig config;

    if (const auto node = root["engine"]) {
        config.engine = node.as<std::string>();
    }
    if (const auto node = root["weights"]) {
        config.weights = node.as<std::string>();
    }
    if (const auto node = root["imgsz"]) {
        config.imgsz = node.as<int>();
    }
    if (const auto node = root["conf_threshold"]) {
        config.confThreshold = node.as<float>();
    }
    if (const auto node = root["iou_threshold"]) {
        config.iouThreshold = node.as<double>();
    }
    if (const auto node = root["device"]) {
        config.device = node.as<std::string>();
    }
    if (const auto node = root["output_format"]) {
        config.outputFormat = parseOutputFormat(node.as<std::string>());
    }
    if (const auto node = root["class_names"]) {
        for (const auto& entry : node) {
            config.classNames[entry.first.as<int>()] = entry.second.as<std::string>();
        }
    }

    if (config.weights.empty()) {
        throw std::invalid_argument("engine config is missing 'weights'");
    }
    if (config.imgsz <= 0) {
        throw std::invalid_argument("imgsz must be positive");
    }
    return config;
}

}  // namespace uavsd
