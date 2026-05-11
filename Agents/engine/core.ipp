#pragma once

#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <exception>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

// Game constants and search/scoring constants are kept identical to Python logic.
constexpr int ROWS = 6;
constexpr int COLUMNS = 7;
constexpr int INAROW = 4;

constexpr int INF = 1000000;
constexpr int NNF = -1000000;
constexpr int MATE_SCORE = 100000;

constexpr int TT_BUCKETS = 1 << 23;
constexpr int TT_BUCKET_MASK = TT_BUCKETS - 1;
constexpr int TT_BUCKET_SIZE = 4;

constexpr int TT_EXACT = 0;
constexpr int TT_LOWER = 1;
constexpr int TT_UPPER = 2;

const std::array<int, 7> MOVE_ORDER = {3, 2, 4, 1, 5, 0, 6};

using Clock = std::chrono::steady_clock;
using TimePoint = Clock::time_point;

struct TimeoutError : public std::exception {
    const char* what() const noexcept override { return "timeout"; }
};

// Shared monotonic clock helper used for timeout checks and runtime logging.
inline double now_seconds() {
    auto now = Clock::now().time_since_epoch();
    return std::chrono::duration<double>(now).count();
}

int ipow(int base, int exp) {
    int result = 1;
    for (int i = 0; i < exp; ++i) result *= base;
    return result;
}

} // namespace
