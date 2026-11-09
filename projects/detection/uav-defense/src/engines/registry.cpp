#include "uavsd/engines/registry.hpp"

#include <map>
#include <mutex>
#include <stdexcept>

#include "uavsd/engines/yolo_onnx_engine.hpp"

namespace uavsd {

namespace {

struct Registry {
    Registry() {
        factories["yolo"] = [](const EngineConfig& config) {
            return std::make_unique<YoloOnnxEngine>(config);
        };
    }

    std::mutex mutex;
    std::map<std::string, EngineFactory> factories;
};

Registry& registry() {
    static Registry instance;
    return instance;
}

}

void registerEngine(const std::string& name, EngineFactory factory) {
    auto& r = registry();
    std::lock_guard lock(r.mutex);
    r.factories[name] = std::move(factory);
}

std::vector<std::string> registeredEngines() {
    auto& r = registry();
    std::lock_guard lock(r.mutex);
    std::vector<std::string> names;
    for (const auto& [name, factory] : r.factories) {
        names.push_back(name);
    }
    return names;
}

std::unique_ptr<DetectionEngine> createEngine(const EngineConfig& config) {
    auto& r = registry();
    std::lock_guard lock(r.mutex);
    const auto it = r.factories.find(config.engine);
    if (it == r.factories.end()) {
        throw std::invalid_argument("unknown detection engine: " + config.engine);
    }
    return it->second(config);
}

}
