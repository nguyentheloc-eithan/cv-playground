#include "uavsd/engines/registry.hpp"

#include <algorithm>

#include <gtest/gtest.h>

namespace uavsd {

namespace {

class FakeEngine final : public DetectionEngine {
public:
    [[nodiscard]] std::string_view name() const override { return "fake"; }
    void load(const std::filesystem::path&) override {}
    void warmup() override {}
    [[nodiscard]] std::vector<Detection> detect(const cv::Mat&, std::int64_t frameIndex,
                                                double timestamp) override {
        return {Detection{0, "uav", 1.0F, {0.0, 0.0, 1.0, 1.0}, frameIndex, timestamp}};
    }
    void close() override {}
};

}

TEST(RegistryTest, YoloIsRegisteredByDefault) {
    const auto names = registeredEngines();
    EXPECT_NE(std::find(names.begin(), names.end(), "yolo"), names.end());
}

TEST(RegistryTest, CustomEngineCanBeRegisteredAndCreated) {
    registerEngine("fake", [](const EngineConfig&) { return std::make_unique<FakeEngine>(); });
    EngineConfig config;
    config.engine = "fake";
    auto engine = createEngine(config);
    ASSERT_NE(engine, nullptr);
    EXPECT_EQ(engine->name(), "fake");
    const auto detections = engine->detect(cv::Mat(), 7, 0.7);
    ASSERT_EQ(detections.size(), 1U);
    EXPECT_EQ(detections[0].frameIndex, 7);
}

TEST(RegistryTest, UnknownEngineThrows) {
    EngineConfig config;
    config.engine = "missing";
    EXPECT_THROW(static_cast<void>(createEngine(config)), std::invalid_argument);
}

}
