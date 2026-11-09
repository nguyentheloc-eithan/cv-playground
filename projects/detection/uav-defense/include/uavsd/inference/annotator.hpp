#pragma once

#include <vector>

#include <opencv2/core/mat.hpp>

#include "uavsd/core/types.hpp"

namespace uavsd {

void drawDetections(cv::Mat& image, const std::vector<Detection>& detections);

}
