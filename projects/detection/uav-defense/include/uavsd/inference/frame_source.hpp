#pragma once

#include <chrono>
#include <cstdint>
#include <opencv2/core/mat.hpp>
#include <opencv2/videoio.hpp>
#include <string>

namespace uavsd {

struct Frame {
    cv::Mat image;
    std::int64_t index = 0;
    double timestamp = 0.0;
};

class FrameSource {
public:
    explicit FrameSource(const std::string& uri);

    [[nodiscard]] bool read(Frame& frame);

    [[nodiscard]] bool isLive() const { return live_; }
    [[nodiscard]] double fps() const;
    [[nodiscard]] cv::Size frameSize() const;

private:
    cv::VideoCapture capture_;
    bool live_ = false;
    std::int64_t nextIndex_ = 0;
    std::chrono::steady_clock::time_point start_;
};

}  // namespace uavsd
