#pragma once

#include <map>
#include <string>
#include <string_view>

namespace uavsd {

[[nodiscard]] std::map<int, std::string> parseClassNames(std::string_view text);

}
