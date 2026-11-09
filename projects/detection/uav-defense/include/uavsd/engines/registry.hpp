#pragma once

#include <functional>
#include <memory>
#include <string>
#include <vector>

#include "uavsd/config/engine_config.hpp"
#include "uavsd/engines/detection_engine.hpp"

namespace uavsd {

using EngineFactory = std::function<std::unique_ptr<DetectionEngine>(const EngineConfig&)>;

void registerEngine(const std::string& name, EngineFactory factory);

[[nodiscard]] std::vector<std::string> registeredEngines();

[[nodiscard]] std::unique_ptr<DetectionEngine> createEngine(const EngineConfig& config);

}
