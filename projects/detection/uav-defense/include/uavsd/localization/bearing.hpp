#pragma once

#include <optional>

namespace uavsd {

struct CameraIntrinsics {
    double fx = 0.0;
    double fy = 0.0;
    double cx = 0.0;
    double cy = 0.0;
};

struct Bearing {
    double azimuthRad = 0.0;
    double elevationRad = 0.0;
};

struct RangeEstimate {
    double meters = 0.0;
    double sigmaMeters = 0.0;
};

[[nodiscard]] Bearing pixelToBearing(const CameraIntrinsics& intrinsics, double u, double v);

[[nodiscard]] std::optional<RangeEstimate> rangeFromKnownWidth(double fx, double realWidthMeters,
                                                               double pixelWidth,
                                                               double realWidthSigmaMeters,
                                                               double pixelWidthSigma);

}
