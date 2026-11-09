#include "uavsd/config/engine_config.hpp"

#include <fstream>

#include <gtest/gtest.h>

namespace uavsd {

namespace {

std::filesystem::path writeConfig(const std::string& name, const std::string& content) {
    const auto path = std::filesystem::temp_directory_path() / name;
    std::ofstream(path) << content;
    return path;
}

}

TEST(EngineConfigTest, LoadsAllFields) {
    const auto path = writeConfig("uavsd_engine_full.yaml", R"(
engine: yolo
weights: models/exports/model.onnx
imgsz: 1280
conf_threshold: 0.3
iou_threshold: 0.6
device: cuda:1
output_format: end2end
class_names:
  0: uav
  1: bird
)");
    const EngineConfig config = loadEngineConfig(path);
    EXPECT_EQ(config.engine, "yolo");
    EXPECT_EQ(config.weights, "models/exports/model.onnx");
    EXPECT_EQ(config.imgsz, 1280);
    EXPECT_FLOAT_EQ(config.confThreshold, 0.3F);
    EXPECT_DOUBLE_EQ(config.iouThreshold, 0.6);
    EXPECT_EQ(config.device, "cuda:1");
    EXPECT_EQ(config.outputFormat, YoloOutputFormat::EndToEnd);
    EXPECT_EQ(config.classNames.at(1), "bird");
    std::filesystem::remove(path);
}

TEST(EngineConfigTest, MissingWeightsIsAnError) {
    const auto path = writeConfig("uavsd_engine_noweights.yaml", "engine: yolo\n");
    EXPECT_THROW(static_cast<void>(loadEngineConfig(path)), std::invalid_argument);
    std::filesystem::remove(path);
}

TEST(EngineConfigTest, UnknownOutputFormatIsAnError) {
    const auto path =
        writeConfig("uavsd_engine_badformat.yaml", "weights: m.onnx\noutput_format: fancy\n");
    EXPECT_THROW(static_cast<void>(loadEngineConfig(path)), std::invalid_argument);
    std::filesystem::remove(path);
}

}
