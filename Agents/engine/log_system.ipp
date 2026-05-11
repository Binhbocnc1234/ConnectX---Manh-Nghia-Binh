#include "core.ipp"

namespace {

std::string format_int_list(const std::vector<int>& values) {
    std::ostringstream oss;
    oss << "[";
    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i > 0) oss << ", ";
        oss << values[i];
    }
    oss << "]";
    return oss.str();
}

void log_move(int /*move*/, const TimePoint& /*start_time*/) {
}

} // namespace
