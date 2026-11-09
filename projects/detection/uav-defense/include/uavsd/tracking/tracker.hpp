#pragma once

#include <vector>

#include "uavsd/core/types.hpp"
#include "uavsd/tracking/track.hpp"

namespace uavsd {

class Tracker {
public:
    virtual ~Tracker() = default;

    virtual std::vector<Track> update(const std::vector<Detection>& detections,
                                      double timestamp) = 0;

    virtual void reset() = 0;
};

}
