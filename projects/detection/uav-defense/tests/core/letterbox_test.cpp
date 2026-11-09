#include "uavsd/core/letterbox.hpp"

#include <gtest/gtest.h>

namespace uavsd {

TEST(LetterboxTest, WideFrameIsPaddedVertically) {
    const LetterboxInfo info = computeLetterbox(1920, 1080, 640);
    EXPECT_DOUBLE_EQ(info.scale, 640.0 / 1920.0);
    EXPECT_DOUBLE_EQ(info.padX, 0.0);
    EXPECT_DOUBLE_EQ(info.padY, 140.0);
}

TEST(LetterboxTest, UnletterboxRestoresSourceCoordinates) {
    const LetterboxInfo info = computeLetterbox(1920, 1080, 640);
    const BoundingBox box = unletterbox(info, 100.0, 240.0, 120.0, 250.0);
    EXPECT_NEAR(box.x, 300.0, 1e-9);
    EXPECT_NEAR(box.y, 300.0, 1e-9);
    EXPECT_NEAR(box.width, 60.0, 1e-9);
    EXPECT_NEAR(box.height, 30.0, 1e-9);
}

TEST(LetterboxTest, UnletterboxClampsToFrame) {
    const LetterboxInfo info = computeLetterbox(1920, 1080, 640);
    const BoundingBox box = unletterbox(info, -10.0, 100.0, 700.0, 150.0);
    EXPECT_DOUBLE_EQ(box.x, 0.0);
    EXPECT_DOUBLE_EQ(box.y, 0.0);
    EXPECT_DOUBLE_EQ(box.width, 1920.0);
    EXPECT_DOUBLE_EQ(box.height, 30.0);
}

TEST(LetterboxTest, RejectsInvalidDimensions) {
    EXPECT_THROW(static_cast<void>(computeLetterbox(0, 1080, 640)), std::invalid_argument);
}

TEST(IouTest, IdenticalAndDisjointBoxes) {
    const BoundingBox a{0.0, 0.0, 10.0, 10.0};
    EXPECT_DOUBLE_EQ(intersectionOverUnion(a, a), 1.0);
    EXPECT_DOUBLE_EQ(intersectionOverUnion(a, BoundingBox{20.0, 20.0, 5.0, 5.0}), 0.0);
    EXPECT_NEAR(intersectionOverUnion(a, BoundingBox{5.0, 0.0, 10.0, 10.0}), 50.0 / 150.0, 1e-12);
}

}
