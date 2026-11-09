#include "uavsd/core/metadata.hpp"

#include <gtest/gtest.h>

namespace uavsd {

TEST(MetadataTest, ParsesUltralyticsNames) {
    const auto names = parseClassNames("{0: 'uav', 1: 'bird', 12: \"air plane\"}");
    ASSERT_EQ(names.size(), 3U);
    EXPECT_EQ(names.at(0), "uav");
    EXPECT_EQ(names.at(1), "bird");
    EXPECT_EQ(names.at(12), "air plane");
}

TEST(MetadataTest, IgnoresDigitsInsideNames) {
    const auto names = parseClassNames("{0: 'dji m300', 1: 'uav'}");
    ASSERT_EQ(names.size(), 2U);
    EXPECT_EQ(names.at(0), "dji m300");
    EXPECT_EQ(names.at(1), "uav");
}

TEST(MetadataTest, EmptyInputGivesEmptyMap) {
    EXPECT_TRUE(parseClassNames("").empty());
    EXPECT_TRUE(parseClassNames("{}").empty());
}

}
