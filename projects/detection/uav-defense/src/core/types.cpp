#include "uavsd/core/types.hpp"

#include <algorithm>

namespace uavsd {

double intersectionOverUnion(const BoundingBox& a, const BoundingBox& b) {
    const double left = std::max(a.x, b.x);
    const double top = std::max(a.y, b.y);
    const double right = std::min(a.x + a.width, b.x + b.width);
    const double bottom = std::min(a.y + a.height, b.y + b.height);
    const double intersection = std::max(0.0, right - left) * std::max(0.0, bottom - top);
    const double unionArea = a.area() + b.area() - intersection;
    return unionArea > 0.0 ? intersection / unionArea : 0.0;
}

}
