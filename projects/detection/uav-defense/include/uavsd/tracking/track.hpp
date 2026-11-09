#pragma once

#include <cstdint>
#include <optional>
#include <string>

#include "uavsd/core/types.hpp"
#include "uavsd/localization/bearing.hpp"

namespace uavsd {

enum class TrackState { Tentative, Confirmed, Lost, Removed };

struct Vec2 {
    double x = 0.0;
    double y = 0.0;
};

struct Track {
    std::int64_t trackId = 0;
    std::string className;
    float confidence = 0.0F;
    BoundingBox bbox;
    Vec2 centerPx;
    Vec2 velocityPx;
    std::optional<Bearing> bearing;
    std::optional<RangeEstimate> range;
    double firstSeen = 0.0;
    double lastSeen = 0.0;
    int hits = 0;
    int misses = 0;
    TrackState state = TrackState::Tentative;
};

}  // namespace uavsd
