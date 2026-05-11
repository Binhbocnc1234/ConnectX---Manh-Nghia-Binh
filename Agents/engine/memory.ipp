#include "core.ipp"

namespace {

struct TTEntry {
    std::uint64_t key;
    int depth;
    int value;
    int flag;
    int best_move;
};

struct PairHash {
    std::size_t operator()(const std::pair<std::uint64_t, std::uint64_t>& p) const noexcept {
        std::uint64_t x = p.first;
        std::uint64_t y = p.second;
        std::uint64_t h = x ^ (y + 0x9e3779b97f4a7c15ULL + (x << 6) + (x >> 2));
        return static_cast<std::size_t>(h);
    }
};

std::unordered_map<int, std::vector<TTEntry>> tt;
std::unordered_map<int, std::array<int, 2>> killer_moves;
std::unordered_map<std::pair<std::uint64_t, std::uint64_t>, int, PairHash> opening_book;
bool opening_book_loaded = false;
std::string engine_base_dir;

std::array<std::uint64_t, 49> Z_ME{};
std::array<std::uint64_t, 49> Z_OPP{};
bool zobrist_ready = false;

std::uint64_t mirror_board(std::uint64_t bb) {
    std::uint64_t m = 0;
    m |= (bb & 0x7FULL) << 42;
    m |= (bb & (0x7FULL << 7)) << 28;
    m |= (bb & (0x7FULL << 14)) << 14;
    m |= (bb & (0x7FULL << 21));
    m |= (bb & (0x7FULL << 28)) >> 14;
    m |= (bb & (0x7FULL << 35)) >> 28;
    m |= (bb & (0x7FULL << 42)) >> 42;
    return m;
}

std::uint64_t splitmix64(std::uint64_t x) {
    x = (x + 0x9E3779B97F4A7C15ULL) & 0xFFFFFFFFFFFFFFFFULL;
    std::uint64_t z = x;
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL) & 0xFFFFFFFFFFFFFFFFULL;
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EBULL) & 0xFFFFFFFFFFFFFFFFULL;
    return (z ^ (z >> 31)) & 0xFFFFFFFFFFFFFFFFULL;
}

void ensure_zobrist() {
    if (zobrist_ready) return;
    std::uint64_t x = 0xC0FFEEULL & 0xFFFFFFFFFFFFFFFFULL;
    for (int i = 0; i < 49; ++i) {
        x = splitmix64(x);
        Z_ME[i] = x;
        x = splitmix64(x);
        Z_OPP[i] = x;
    }
    zobrist_ready = true;
}

std::uint64_t zobrist_hash(std::uint64_t me, std::uint64_t opp) {
    ensure_zobrist();
    std::uint64_t h = 0;
    std::uint64_t bb = me;
    while (bb) {
        std::uint64_t lsb = bb & (~bb + 1ULL);
        int idx = static_cast<int>(std::countr_zero(lsb));
        h ^= Z_ME[idx];
        bb ^= lsb;
    }
    bb = opp;
    while (bb) {
        std::uint64_t lsb = bb & (~bb + 1ULL);
        int idx = static_cast<int>(std::countr_zero(lsb));
        h ^= Z_OPP[idx];
        bb ^= lsb;
    }
    return h & 0xFFFFFFFFFFFFFFFFULL;
}

std::pair<std::uint64_t, bool> canonical_tt_key(std::uint64_t me, std::uint64_t opp) {
    std::uint64_t key = zobrist_hash(me, opp);
    std::uint64_t m_me = mirror_board(me);
    std::uint64_t m_opp = mirror_board(opp);
    std::uint64_t m_key = zobrist_hash(m_me, m_opp);
    if ((m_key < key) || (m_key == key && std::make_pair(m_me, m_opp) < std::make_pair(me, opp))) {
        return {m_key, true};
    }
    return {key, false};
}

struct TTProbeResult {
    bool has_value;
    int value;
    int alpha;
    int beta;
    int best_hint;
};

TTProbeResult tt_probe(std::uint64_t key64, int depth, int alpha, int beta) {
    int idx = static_cast<int>(key64 & TT_BUCKET_MASK);
    auto it = tt.find(idx);
    if (it == tt.end()) return {false, 0, alpha, beta, -1};

    int best_hint = -1;
    int best_hint_depth = -1;

    for (const auto& e : it->second) {
        if (e.key != key64) continue;
        if (e.best_move != -1 && e.depth > best_hint_depth) {
            best_hint = e.best_move;
            best_hint_depth = e.depth;
        }
        if (e.depth < depth) continue;

        if (e.flag == TT_EXACT) return {true, e.value, alpha, beta, e.best_move};
        if (e.flag == TT_LOWER) {
            if (e.value > alpha) alpha = e.value;
        } else if (e.flag == TT_UPPER) {
            if (e.value < beta) beta = e.value;
        }
        if (alpha >= beta) return {true, e.value, alpha, beta, e.best_move};
    }

    return {false, 0, alpha, beta, best_hint};
}

void tt_store(std::uint64_t key64, int depth, int value, int flag, int best_move) {
    int idx = static_cast<int>(key64 & TT_BUCKET_MASK);
    TTEntry entry{key64, depth, value, flag, best_move};
    auto& bucket = tt[idx];

    for (auto& e : bucket) {
        if (e.key == key64) {
            if (depth >= e.depth) e = entry;
            return;
        }
    }

    if (static_cast<int>(bucket.size()) < TT_BUCKET_SIZE) {
        bucket.push_back(entry);
        return;
    }

    int victim_i = 0;
    int victim_depth = bucket[0].depth;
    for (int i = 1; i < static_cast<int>(bucket.size()); ++i) {
        if (bucket[i].depth < victim_depth) {
            victim_depth = bucket[i].depth;
            victim_i = i;
        }
    }
    bucket[victim_i] = entry;
}

std::uint64_t read_u64_le(const char* ptr) {
    std::uint64_t v = 0;
    for (int i = 0; i < 8; ++i) {
        v |= (static_cast<std::uint64_t>(static_cast<unsigned char>(ptr[i])) << (8 * i));
    }
    return v;
}

void load_opening_book() {
    if (opening_book_loaded) return;
    opening_book_loaded = true;
    opening_book.clear();

    std::filesystem::path current_dir = engine_base_dir.empty()
        ? std::filesystem::current_path()
        : std::filesystem::path(engine_base_dir);

    std::filesystem::path book_path = current_dir / "opening_book.bin";

    if (std::filesystem::exists(book_path)) {
        int count = 0;
        try {
            std::ifstream in(book_path, std::ios::binary);
            if (!in) {
                throw std::runtime_error("cannot open file");
            }

            char magic[4] = {0, 0, 0, 0};
            in.read(magic, 4);
            if (in.gcount() != 4 || std::string(magic, 4) != "BK01") {
                std::cout << "[FastAgent] Warning: " << book_path.string()
                          << " is not in expected BK01 binary format." << std::endl;
                return;
            }

            std::vector<char> raw_data((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
            constexpr int entry_size = 17;
            int num_entries = static_cast<int>(raw_data.size() / entry_size);

            for (int i = 0; i < num_entries; ++i) {
                if (i == num_entries / 4) {
                    std::cout << "[FastAgent] Loading... 25%" << std::endl;
                } else if (i == num_entries / 2) {
                    std::cout << "[FastAgent] Loading... 50%" << std::endl;
                } else if (i == (num_entries * 3) / 4) {
                    std::cout << "[FastAgent] Loading... 75%" << std::endl;
                }

                const char* p = raw_data.data() + i * entry_size;
                std::uint64_t me = read_u64_le(p);
                std::uint64_t opp = read_u64_le(p + 8);
                int move = static_cast<unsigned char>(p[16]);

                opening_book[{me, opp}] = move;

                std::uint64_t m_me = mirror_board(me);
                std::uint64_t m_opp = mirror_board(opp);
                if (std::make_pair(m_me, m_opp) != std::make_pair(me, opp)) {
                    opening_book[{m_me, m_opp}] = 6 - move;
                }

                count += 1;
            }

            std::cout << "[FastAgent] Loading... 100%" << std::endl;
            std::cout << "[FastAgent Loaded " << count << " positions (" << opening_book.size()
                      << " entries with mirror) from " << book_path.string() << " (Binary)." << std::endl;
        } catch (const std::exception& e) {
            std::cout << "[FastAgent] Error loading binary book: " << e.what() << std::endl;
        }
    } else {
        std::filesystem::path old_path = current_dir / "small_book_pruned.jsonl";
        if (std::filesystem::exists(old_path)) {
            std::cout << "[FastAgent] Warning: binary book not found, please re-export using export_book_pruned.cpp for faster loading." << std::endl;
        } else {
            std::cout << "[FastAgent] Warning: No opening book found at " << book_path.string() << std::endl;
        }
    }
}

} // namespace
