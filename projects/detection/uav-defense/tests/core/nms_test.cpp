#include "uavsd/core/nms.hpp"

#include <gtest/gtest.h>

namespace uavsd {

TEST(NmsTest, SuppressesOverlappingBoxesOfSameClass) {
    const std::vector<ScoredBox> boxes{
        {{0.0, 0.0, 10.0, 10.0}, 0, 0.6F},
        {{1.0, 1.0, 10.0, 10.0}, 0, 0.9F},
        {{50.0, 50.0, 10.0, 10.0}, 0, 0.5F},
    };
    const auto kept = nonMaxSuppression(boxes, 0.5);
    ASSERT_EQ(kept.size(), 2U);
    EXPECT_EQ(kept[0], 1U);
    EXPECT_EQ(kept[1], 2U);
}

TEST(NmsTest, KeepsOverlappingBoxesOfDifferentClasses) {
    const std::vector<ScoredBox> boxes{
        {{0.0, 0.0, 10.0, 10.0}, 0, 0.9F},
        {{0.0, 0.0, 10.0, 10.0}, 1, 0.8F},
    };
    EXPECT_EQ(nonMaxSuppression(boxes, 0.5).size(), 2U);
}

TEST(NmsTest, EmptyInput) { EXPECT_TRUE(nonMaxSuppression({}, 0.5).empty()); }

}
