#include "uavsd/inference/frame_source.hpp"

#include <algorithm>
#include <cctype>
#include <stdexcept>

namespace uavsd {

namespace {

bool isDeviceIndex(const std::string& uri) {
    return !uri.empty() && std::all_of(uri.begin(), uri.end(), [](unsigned char c) {
        return std::isdigit(c) != 0;
    });
}

}

FrameSource::FrameSource(const std::string& uri) {
    if (isDeviceIndex(uri)) {
        capture_.open(std::stoi(uri));
        live_ = true;
    } else {
        capture_.open(uri);
        live_ = uri.find("://") != std::string::npos;
    }
    if (!capture_.isOpened()) {
        throw std::runtime_error("cannot open frame source: " + uri);
    }
    start_ = std::chrono::steady_clock::now();
}

bool FrameSource::read(Frame& frame) {
    if (!capture_.read(frame.image) || frame.image.empty()) {
        return false;
    }
    frame.index = nextIndex_++;
    if (live_) {
        frame.timestamp =
            std::chrono::duration<double>(std::chrono::steady_clock::now() - start_).count();
    } else if (const double rate = fps(); rate > 0.0) {
        frame.timestamp = static_cast<double>(frame.index) / rate;
    } else {
        frame.timestamp = capture_.get(cv::CAP_PROP_POS_MSEC) / 1000.0;
    }
    return true;
}

double FrameSource::fps() const { return capture_.get(cv::CAP_PROP_FPS); }

cv::Size FrameSource::frameSize() const {
    return {static_cast<int>(capture_.get(cv::CAP_PROP_FRAME_WIDTH)),
            static_cast<int>(capture_.get(cv::CAP_PROP_FRAME_HEIGHT))};
}

}
