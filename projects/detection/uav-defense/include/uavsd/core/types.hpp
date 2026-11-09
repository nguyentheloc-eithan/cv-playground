#pragma once

#include <cstdint>
#include <string>

namespace uavsd {

struct BoundingBox {
    double x = 0.0;
    double y = 0.0;
    double width = 0.0;
    double height = 0.0;

    [[nodiscard]] double area() const { return width * height; }
    [[nodiscard]] double centerX() const { return x + width / 2.0; }
    [[nodiscard]] double centerY() const { return y + height / 2.0; }
};

struct Detection {
    int classId = 0;
    std::string className;
    float confidence = 0.0F;
    BoundingBox bbox;
    std::int64_t frameIndex = 0;
    double timestamp = 0.0;
};

[[nodiscard]] double intersectionOverUnion(const BoundingBox& a, const BoundingBox& b);

}
