#include "uavsd/localization/bearing.hpp"

#include <cmath>
#include <stdexcept>

namespace uavsd {

Bearing pixelToBearing(const CameraIntrinsics& intrinsics, double u, double v) {
    if (intrinsics.fx <= 0.0 || intrinsics.fy <= 0.0) {
        throw std::invalid_argument("focal lengths must be positive");
    }
    const double x = (u - intrinsics.cx) / intrinsics.fx;
    const double y = (intrinsics.cy - v) / intrinsics.fy;
    return Bearing{std::atan(x), std::atan2(y, std::sqrt(1.0 + x * x))};
}

std::optional<RangeEstimate> rangeFromKnownWidth(double fx, double realWidthMeters,
                                                 double pixelWidth, double realWidthSigmaMeters,
                                                 double pixelWidthSigma) {
    if (fx <= 0.0 || realWidthMeters <= 0.0 || pixelWidth <= 0.0) {
        return std::nullopt;
    }
    const double meters = fx * realWidthMeters / pixelWidth;
    const double relativeSigma = std::hypot(realWidthSigmaMeters / realWidthMeters,
                                            pixelWidthSigma / pixelWidth);
    return RangeEstimate{meters, meters * relativeSigma};
}

}
