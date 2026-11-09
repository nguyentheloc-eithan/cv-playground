#include "uavsd/core/yolo_decode.hpp"

#include <array>

#include <gtest/gtest.h>

namespace uavsd {

namespace {

LetterboxInfo identityLetterbox() { return computeLetterbox(640, 640, 640); }

}

TEST(YoloDecodeTest, ResolvesFormatFromShape) {
    const std::array<std::int64_t, 3> endToEnd{1, 300, 6};
    const std::array<std::int64_t, 3> raw{1, 5, 8400};
    EXPECT_EQ(resolveYoloOutputFormat(YoloOutputFormat::Auto, endToEnd),
              YoloOutputFormat::EndToEnd);
    EXPECT_EQ(resolveYoloOutputFormat(YoloOutputFormat::Auto, raw), YoloOutputFormat::Raw);
    EXPECT_EQ(resolveYoloOutputFormat(YoloOutputFormat::Raw, endToEnd), YoloOutputFormat::Raw);
}

TEST(YoloDecodeTest, EndToEndFiltersByConfidence) {
    const std::array<float, 12> data{
        10.0F, 20.0F, 30.0F, 60.0F, 0.9F, 0.0F,
        0.0F,  0.0F,  5.0F,  5.0F,  0.1F, 0.0F,
    };
    const auto boxes = decodeYoloEndToEnd(data, 2, 0.25F, identityLetterbox());
    ASSERT_EQ(boxes.size(), 1U);
    EXPECT_DOUBLE_EQ(boxes[0].box.x, 10.0);
    EXPECT_DOUBLE_EQ(boxes[0].box.y, 20.0);
    EXPECT_DOUBLE_EQ(boxes[0].box.width, 20.0);
    EXPECT_DOUBLE_EQ(boxes[0].box.height, 40.0);
    EXPECT_EQ(boxes[0].classId, 0);
    EXPECT_FLOAT_EQ(boxes[0].score, 0.9F);
}

TEST(YoloDecodeTest, RawDecodesCentersAndAppliesNms) {
    const std::int64_t channels = 6;
    const std::int64_t anchors = 3;
    const std::array<float, 18> data{
        100.0F, 101.0F, 400.0F,
        100.0F, 101.0F, 400.0F,
        20.0F,  20.0F,  10.0F,
        20.0F,  20.0F,  10.0F,
        0.8F,   0.7F,   0.05F,
        0.1F,   0.2F,   0.6F,
    };
    const auto boxes = decodeYoloRaw(data, channels, anchors, 0.25F, 0.5, identityLetterbox());
    ASSERT_EQ(boxes.size(), 2U);
    EXPECT_EQ(boxes[0].classId, 0);
    EXPECT_FLOAT_EQ(boxes[0].score, 0.8F);
    EXPECT_DOUBLE_EQ(boxes[0].box.x, 90.0);
    EXPECT_DOUBLE_EQ(boxes[0].box.width, 20.0);
    EXPECT_EQ(boxes[1].classId, 1);
    EXPECT_DOUBLE_EQ(boxes[1].box.x, 395.0);
}

TEST(YoloDecodeTest, RejectsShortBuffers) {
    const std::array<float, 5> data{};
    EXPECT_THROW(static_cast<void>(decodeYoloEndToEnd(data, 1, 0.25F, identityLetterbox())),
                 std::invalid_argument);
    EXPECT_THROW(static_cast<void>(decodeYoloRaw(data, 5, 2, 0.25F, 0.5, identityLetterbox())),
                 std::invalid_argument);
}

}
