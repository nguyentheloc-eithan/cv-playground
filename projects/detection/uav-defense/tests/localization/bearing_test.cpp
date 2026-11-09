#include "uavsd/localization/bearing.hpp"

#include <cmath>
#include <numbers>

#include <gtest/gtest.h>

namespace uavsd {

namespace {

const CameraIntrinsics kCamera{1000.0, 1000.0, 960.0, 540.0};

}

TEST(BearingTest, PrincipalPointIsStraightAhead) {
    const Bearing bearing = pixelToBearing(kCamera, 960.0, 540.0);
    EXPECT_DOUBLE_EQ(bearing.azimuthRad, 0.0);
    EXPECT_DOUBLE_EQ(bearing.elevationRad, 0.0);
}

TEST(BearingTest, OffsetOfOneFocalLengthIsFortyFiveDegrees) {
    EXPECT_NEAR(pixelToBearing(kCamera, 1960.0, 540.0).azimuthRad, std::numbers::pi / 4.0, 1e-12);
    EXPECT_NEAR(pixelToBearing(kCamera, 960.0, -460.0).elevationRad, std::numbers::pi / 4.0,
                1e-12);
    EXPECT_LT(pixelToBearing(kCamera, 960.0, 1000.0).elevationRad, 0.0);
}

TEST(BearingTest, RejectsInvalidIntrinsics) {
    EXPECT_THROW(static_cast<void>(pixelToBearing(CameraIntrinsics{}, 0.0, 0.0)),
                 std::invalid_argument);
}

TEST(RangeTest, KnownWidthRangeWithUncertainty) {
    const auto range = rangeFromKnownWidth(1000.0, 0.5, 10.0, 0.05, 1.0);
    ASSERT_TRUE(range.has_value());
    EXPECT_DOUBLE_EQ(range->meters, 50.0);
    EXPECT_NEAR(range->sigmaMeters, 50.0 * std::hypot(0.1, 0.1), 1e-12);
}

TEST(RangeTest, InvalidInputsGiveNoEstimate) {
    EXPECT_FALSE(rangeFromKnownWidth(1000.0, 0.5, 0.0, 0.0, 0.0).has_value());
}

}
