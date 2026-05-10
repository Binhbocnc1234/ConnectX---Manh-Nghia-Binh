// engine.cpp - ConnectX C++ Engine
// Giao tiep voi Python qua stdin/stdout:
//   Python -> C++: "<me_hex> <opp_hex> <deadline_ms>\n"
//   C++    -> Python: "<best_col>\n"
//
// Compile: g++ -O3 -o engine.exe engine.cpp
//          g++ -O3 -static -o engine engine.cpp  (Linux Kaggle)

#include <iostream>
#include <fstream>
#include <unordered_map>
#include <chrono>
#include <cstring>
#include <vector>
#include <algorithm>

using u64 = unsigned long long;

// ===================================================================
// Constants & Board Layout
// Column c uses bits [c*7 .. c*7+5], bit c*7+6 is sentinel (always 0)
// Row 0 = bottom, Row 5 = top
// ===================================================================
static const int BW  = 7;  // board width
static const int BH  = 6;  // board height
static const int BH1 = 7;  // BH + 1 (bits per column incl. sentinel)

static u64 BOTTOM_ROW    = 0;
static u64 COLUMN_HEADERS= 0;
static u64 VALID_CELLS   = 0;

static const int MOVE_ORDER[7] = {3, 2, 4, 1, 5, 0, 6};
static const int MATE_SCORE    = 100000;
static const int INF_VAL       = 1000000;
static const int NNF           = -INF_VAL;

void init_constants() {
    for (int c = 0; c < BW; c++) BOTTOM_ROW |= (1ULL << (c * BH1));
    COLUMN_HEADERS = BOTTOM_ROW << BH;
    VALID_CELLS    = COLUMN_HEADERS - BOTTOM_ROW;
}

// ===================================================================
// Time management
// ===================================================================
static u64 g_deadline_ms = 0;

u64 now_ms() {
    using namespace std::chrono;
    return duration_cast<milliseconds>(system_clock::now().time_since_epoch()).count();
}
bool time_up() { return now_ms() >= g_deadline_ms; }

// ===================================================================
// Bitboard utilities
// ===================================================================
u64 mirror_board(u64 bb) {
    u64 m = 0;
    m |= (bb & (0x7FULL <<  0)) << 42;
    m |= (bb & (0x7FULL <<  7)) << 28;
    m |= (bb & (0x7FULL << 14)) << 14;
    m |= (bb & (0x7FULL << 21));
    m |= (bb & (0x7FULL << 28)) >> 14;
    m |= (bb & (0x7FULL << 35)) >> 28;
    m |= (bb & (0x7FULL << 42)) >> 42;
    return m;
}

bool is_win(u64 b) {
    u64 p;
    p = b & (b >> 1);  if (p & (p >>  2)) return true;  // vertical
    p = b & (b >> 7);  if (p & (p >> 14)) return true;  // horizontal
    p = b & (b >> 6);  if (p & (p >> 12)) return true;  // diagonal /
    p = b & (b >> 8);  if (p & (p >> 16)) return true;  // diagonal backslash
    return false;
}

u64 find_threats(u64 b) {
    u64 threats = 0;
    // Vertical: only XXX_ pattern
    u64 pairs = b & (b << 1);
    u64 triple = pairs & (pairs << 1);
    threats |= triple << 1;
    // Horizontal + 2 diagonals
    for (int s : {7, 6, 8}) {
        pairs  = b & (b << s);
        triple = pairs & (pairs << s);
        threats |= (b >> s) & (pairs << s);
        threats |= (b << s) & (pairs >> (2 * s));
        threats |= triple << s;
        threats |= triple >> (3 * s);
    }
    return threats & VALID_CELLS;
}

u64 make_move(u64 me, u64 opp, int col) {
    u64 col_mask = 0x3FULL << (col * BH1);
    u64 occ      = (me | opp) & col_mask;
    if (occ & (1ULL << (col * BH1 + BH - 1))) return 0; // column full
    return (occ + (1ULL << (col * BH1))) & col_mask;
}

// ===================================================================
// Zobrist Hashing
// ===================================================================
static u64 Z_ME[49], Z_OPP[49];

u64 splitmix64(u64 x) {
    x += 0x9E3779B97F4A7C15ULL;
    x  = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ULL;
    x  = (x ^ (x >> 27)) * 0x94D049BB133111EBULL;
    return x ^ (x >> 31);
}

void init_zobrist() {
    u64 x = 0xC0FFEEULL;
    for (int i = 0; i < 49; i++) {
        x = splitmix64(x); Z_ME[i]  = x;
        x = splitmix64(x); Z_OPP[i] = x;
    }
}

u64 zobrist_hash(u64 me, u64 opp) {
    u64 h = 0, bb;
    for (bb = me;  bb; bb &= bb-1) h ^= Z_ME [__builtin_ctzll(bb)];
    for (bb = opp; bb; bb &= bb-1) h ^= Z_OPP[__builtin_ctzll(bb)];
    return h;
}

struct CKey { u64 key; bool flip; };
CKey canonical_key(u64 me, u64 opp) {
    u64 key   = zobrist_hash(me, opp);
    u64 m_me  = mirror_board(me);
    u64 m_opp = mirror_board(opp);
    u64 m_key = zobrist_hash(m_me, m_opp);
    if (m_key < key || (m_key == key && (m_me < me || (m_me == me && m_opp < opp))))
        return {m_key, true};
    return {key, false};
}

// ===================================================================
// Transposition Table
// ===================================================================
static const int TT_SIZE = 1 << 23;
static const int TT_MASK = TT_SIZE - 1;
enum { TT_EXACT=0, TT_LOWER=1, TT_UPPER=2 };

struct TTEntry { u64 key; int depth, value, flag, best_move; };
static TTEntry TT[TT_SIZE];

void tt_store(u64 key, int depth, int value, int flag, int bm) {
    TTEntry& e = TT[key & TT_MASK];
    if (e.key == 0 || e.key == key || depth >= e.depth)
        e = {key, depth, value, flag, bm};
}

struct TTRes { bool hit; int value, alpha, beta, best_move; };
TTRes tt_probe(u64 key, int depth, int alpha, int beta) {
    TTEntry& e = TT[key & TT_MASK];
    int bm = (e.key == key) ? e.best_move : -1;
    if (e.key == key && e.depth >= depth) {
        if      (e.flag == TT_EXACT) return {true,  e.value, alpha, beta, bm};
        else if (e.flag == TT_LOWER) alpha = std::max(alpha, e.value);
        else if (e.flag == TT_UPPER) beta  = std::min(beta,  e.value);
        if (alpha >= beta) return {true, e.value, alpha, beta, bm};
    }
    return {false, 0, alpha, beta, bm};
}

// ===================================================================
// Killer Moves
// ===================================================================
static int killers[64][2];
void record_killer(int depth, int col) {
    if (killers[depth][0] != col) { killers[depth][1] = killers[depth][0]; killers[depth][0] = col; }
}

// ===================================================================
// Heuristic (pre-computed window masks)
// ===================================================================
static std::vector<u64> window_masks;

void init_window_masks() {
    auto add_window = [&](int positions[4]) {
        u64 mask = 0;
        for (int i = 0; i < 4; i++) mask |= 1ULL << positions[i];
        window_masks.push_back(mask);
    };
    int pos[4];
    for (int row = 0; row < BH; row++)
        for (int col = 0; col <= BW-4; col++) {
            for (int k=0;k<4;k++) pos[k]=(col+k)*BH1+row; add_window(pos);
        }
    for (int row = 0; row <= BH-4; row++)
        for (int col = 0; col < BW; col++) {
            for (int k=0;k<4;k++) pos[k]=col*BH1+row+k; add_window(pos);
        }
    for (int row = 0; row <= BH-4; row++)
        for (int col = 0; col <= BW-4; col++) {
            for (int k=0;k<4;k++) pos[k]=(col+k)*BH1+row+k; add_window(pos);
        }
    for (int row = 3; row < BH; row++)
        for (int col = 0; col <= BW-4; col++) {
            for (int k=0;k<4;k++) pos[k]=(col+k)*BH1+row-k; add_window(pos);
        }
}

int get_heuristic_bb(u64 me, u64 opp) {
    int nm[5]={}, no[5]={};
    for (u64 mask : window_masks) {
        if (mask & opp) { if (!(mask & me)) no[__builtin_popcountll(mask & opp)]++; }
        else            { nm[__builtin_popcountll(mask & me)]++; }
    }
    int ply = __builtin_popcountll(me | opp);
    if (no[4] >= 1) return -(MATE_SCORE - ply);
    if (nm[4] >= 1) return  (MATE_SCORE - ply - 1);
    int score = 0;
    static const int W[] = {0, 1, 4, 16};
    for (int i=1;i<=3;i++) score += W[i]*nm[i] - W[i]*2*no[i];
    return score;
}

// ===================================================================
// Opening Book
// ===================================================================
static std::unordered_map<u64, int> book;
u64 bk(u64 me, u64 opp) { return me * 0x9E3779B97F4A7C15ULL ^ opp; }

void load_book(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f.is_open()) { std::cerr << "[Book] Not found: " << path << "\n"; return; }
    char magic[4]; f.read(magic, 4);
    if (std::string(magic,4) != "BK01") { std::cerr << "[Book] Bad magic\n"; return; }
    int cnt = 0;
    while (true) {
        u64 me, opp; uint8_t mv;
        f.read((char*)&me, 8); f.read((char*)&opp, 8); f.read((char*)&mv, 1);
        if (f.eof()) break;
        book[bk(me, opp)] = mv;
        u64 mm = mirror_board(me), mo = mirror_board(opp);
        if (mm != me || mo != opp) book[bk(mm, mo)] = 6 - mv;
        cnt++;
    }
    std::cerr << "[Book] Loaded " << cnt << " pos (" << book.size() << " with mirror)\n";
}

// ===================================================================
// PVS
// ===================================================================
int pvs(u64 me, u64 opp, int depth, int alpha, int beta) {
    if (is_win(opp)) { return -(MATE_SCORE - (int)__builtin_popcountll(me|opp)); }
    if (depth == 0 || time_up()) return get_heuristic_bb(me, opp);

    int a0 = alpha, b0 = beta;
    auto ck = canonical_key(me, opp);
    auto pr = tt_probe(ck.key, depth, alpha, beta);
    alpha = pr.alpha; beta = pr.beta;
    if (pr.hit) return pr.value;

    int tt_best = pr.best_move;
    if (tt_best != -1 && ck.flip) tt_best = 6 - tt_best;

    // Build ordered move list
    int ordered[7]; int n=0; bool seen[7]={};
    auto push = [&](int c){ if(c>=0&&c<7&&!seen[c]){ordered[n++]=c;seen[c]=true;} };
    push(tt_best);
    push(killers[depth][0]); push(killers[depth][1]);
    for (int c : MOVE_ORDER) push(c);

    // Safe moves
    u64 occ  = me | opp;
    u64 play = (occ + BOTTOM_ROW) & VALID_CELLS;
    u64 my_th = find_threats(me) & ~opp;
    if (my_th & play) { return MATE_SCORE - (int)__builtin_popcountll(occ) - 1; }
    u64 op_th  = find_threats(opp) & ~me;
    u64 op_win = op_th & play;
    u64 safe   = play & ~(op_th >> 1);
    if (op_win) {
        if (op_win & (op_win-1))        return -(MATE_SCORE - (int)__builtin_popcountll(occ) - 2);
        if (!(op_win & safe))           return -(MATE_SCORE - (int)__builtin_popcountll(occ) - 2);
        safe = op_win;
    } else if (!safe)                   return -(MATE_SCORE - (int)__builtin_popcountll(occ) - 2);

    int value = NNF, best_move = -1; bool first = true;
    for (int i = 0; i < n; i++) {
        int col = ordered[i];
        u64 cm = 0x3FULL << (col * BH1), occ_c = occ & cm;
        if (occ_c & (1ULL << (col*BH1+BH-1))) continue;
        u64 np = (occ_c + (1ULL<<(col*BH1))) & cm;
        if (!(np & safe)) continue;

        int res;
        if (first) { res = -pvs(opp, me|np, depth-1, -beta, -alpha); first=false; }
        else {
            res = -pvs(opp, me|np, depth-1, -alpha-1, -alpha);
            if (alpha < res && res < beta)
                res = -pvs(opp, me|np, depth-1, -beta, -res);
        }
        if (res > value) { value = res; best_move = col; }
        alpha = std::max(alpha, value);
        if (alpha >= beta) { record_killer(depth, col); break; }
    }
    if (value == NNF) return 0;

    int sm = (best_move != -1 && ck.flip) ? 6 - best_move : best_move;
    int flag = (value <= a0) ? TT_UPPER : (value >= b0) ? TT_LOWER : TT_EXACT;
    tt_store(ck.key, depth, value, flag, sm);
    return value;
}

// ===================================================================
// Root search with iterative deepening
// ===================================================================
int search_root(u64 me, u64 opp) {
    // Opening book
    auto it = book.find(bk(me, opp));
    if (it != book.end()) { std::cerr << "[Book Hit] col=" << it->second << "\n"; return it->second; }

    // Instant win
    for (int c : MOVE_ORDER) { u64 np=make_move(me,opp,c); if(np && is_win(me|np)) return c; }

    // Valid moves
    std::vector<int> valid;
    for (int c : MOVE_ORDER) if (make_move(me,opp,c)) valid.push_back(c);
    if (valid.empty()) return 3;

    int best = valid[0];
    for (int depth = 1; depth <= 30; depth += 2) {
        if (time_up()) break;
        int sc = NNF, mv = best;
        std::vector<int> moves = {best};
        for (int m : valid) if (m != best) moves.push_back(m);

        for (int col : moves) {
            if (time_up()) goto done;
            u64 np = make_move(me, opp, col);
            if (!np) continue;
            if (is_win(me | np)) return col;
            int s;
            if (col == moves[0]) { s = -pvs(opp, me|np, depth, NNF, INF_VAL); }
            else {
                s = (sc == NNF) ? -pvs(opp,me|np,depth,NNF,INF_VAL)
                                : -pvs(opp,me|np,depth,-sc-1,-sc);
                if (sc < s) s = -pvs(opp, me|np, depth, NNF, INF_VAL);
            }
            if (s > sc) { sc = s; mv = col; }
        }
        best = mv;
        std::cerr << "[ID] d=" << depth << " mv=" << best << " sc=" << sc << "\n";
        if (sc >= MATE_SCORE - 42) break;
    }
    done:
    return best;
}

// ===================================================================
// Main loop
// ===================================================================
int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    init_constants();
    init_zobrist();
    memset(TT, 0, sizeof(TT));
    memset(killers, -1, sizeof(killers));
    init_window_masks();

    // Try to load opening book from several paths
    for (auto& p : std::vector<std::string>{"opening_book.bin","Agents/opening_book.bin","../opening_book.bin"}) {
        std::ifstream t(p, std::ios::binary);
        if (t.is_open()) { load_book(p); break; }
    }
    std::cerr << "[Engine] Ready\n";

    std::string me_hex, opp_hex;
    u64 deadline_ms;
    while (std::cin >> me_hex >> opp_hex >> deadline_ms) {
        u64 me  = std::stoull(me_hex,  nullptr, 16);
        u64 opp = std::stoull(opp_hex, nullptr, 16);
        g_deadline_ms = deadline_ms;
        std::cout << search_root(me, opp) << "\n";
        std::cout.flush();
    }
    return 0;
}
