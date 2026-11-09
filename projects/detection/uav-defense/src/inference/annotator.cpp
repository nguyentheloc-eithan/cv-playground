#include "uavsd/inference/annotator.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>

#include <opencv2/imgproc.hpp>

namespace uavsd {

void drawDetections(cv::Mat& image, const std::vector<Detection>& detections) {
    const cv::Scalar boxColor(0, 200, 255);
    const cv::Scalar textColor(0, 0, 0);
    for (const Detection& detection : detections) {
        const cv::Rect rect(static_cast<int>(std::lround(detection.bbox.x)),
                            static_cast<int>(std::lround(detection.bbox.y)),
                            static_cast<int>(std::lround(detection.bbox.width)),
                            static_cast<int>(std::lround(detection.bbox.height)));
        cv::rectangle(image, rect, boxColor, 2);

        char label[64];
        std::snprintf(label, sizeof(label), "%s %.2f", detection.className.c_str(),
                      static_cast<double>(detection.confidence));
        int baseline = 0;
        const cv::Size textSize = cv::getTextSize(label, cv::FONT_HERSHEY_SIMPLEX, 0.5, 1, &baseline);
        const int top = std::max(rect.y - textSize.height - baseline - 4, 0);
        cv::rectangle(image,
                      cv::Rect(rect.x, top, textSize.width + 6, textSize.height + baseline + 4),
                      boxColor, cv::FILLED);
        cv::putText(image, label, cv::Point(rect.x + 3, top + textSize.height + 2),
                    cv::FONT_HERSHEY_SIMPLEX, 0.5, textColor, 1, cv::LINE_AA);
    }
}

}
