#include "uavsd/inference/frame_source.hpp"

#include <filesystem>

#include <gtest/gtest.h>

namespace uavsd {

TEST(FrameSourceTest, ReadsFramesWithIndicesAndTimestamps) {
    const auto path = std::filesystem::temp_directory_path() / "uavsd_frame_source_test.avi";
    {
        cv::VideoWriter writer(path.string(), cv::VideoWriter::fourcc('M', 'J', 'P', 'G'), 10.0,
                               cv::Size(64, 48));
        ASSERT_TRUE(writer.isOpened());
        for (int i = 0; i < 5; ++i) {
            writer.write(cv::Mat(48, 64, CV_8UC3, cv::Scalar::all(i * 40)));
        }
    }

    FrameSource source(path.string());
    EXPECT_FALSE(source.isLive());

    Frame frame;
    int count = 0;
    while (source.read(frame)) {
        EXPECT_EQ(frame.index, count);
        EXPECT_NEAR(frame.timestamp, count / 10.0, 1e-6);
        EXPECT_EQ(frame.image.cols, 64);
        ++count;
    }
    EXPECT_EQ(count, 5);
    std::filesystem::remove(path);
}

TEST(FrameSourceTest, MissingFileThrows) {
    EXPECT_THROW(FrameSource("does/not/exist.mp4"), std::runtime_error);
}

}
