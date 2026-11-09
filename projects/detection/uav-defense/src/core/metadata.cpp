#include "uavsd/core/metadata.hpp"

#include <cctype>
#include <cstddef>

namespace uavsd {

std::map<int, std::string> parseClassNames(std::string_view text) {
    std::map<int, std::string> names;
    std::size_t pos = 0;
    while (pos < text.size()) {
        while (pos < text.size() && std::isdigit(static_cast<unsigned char>(text[pos])) == 0) {
            if (text[pos] == '\'' || text[pos] == '"') {
                const std::size_t close = text.find(text[pos], pos + 1);
                pos = close == std::string_view::npos ? text.size() : close + 1;
                continue;
            }
            ++pos;
        }
        if (pos >= text.size()) {
            break;
        }
        int id = 0;
        while (pos < text.size() && std::isdigit(static_cast<unsigned char>(text[pos])) != 0) {
            id = id * 10 + (text[pos] - '0');
            ++pos;
        }
        const std::size_t colon = text.find(':', pos);
        if (colon == std::string_view::npos) {
            break;
        }
        const std::size_t open = text.find_first_of("'\"", colon + 1);
        if (open == std::string_view::npos) {
            break;
        }
        const std::size_t close = text.find(text[open], open + 1);
        if (close == std::string_view::npos) {
            break;
        }
        names[id] = std::string(text.substr(open + 1, close - open - 1));
        pos = close + 1;
    }
    return names;
}

}  // namespace uavsd
