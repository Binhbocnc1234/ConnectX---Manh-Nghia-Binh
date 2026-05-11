extern "C" {

void opening_book_opt_set_base_dir(const char* path) {
    if (path == nullptr) {
        engine_base_dir.clear();
        return;
    }
    engine_base_dir = path;
}

int opening_book_opt_agent(
    const int* board,
    int board_size,
    int mark,
    int step,
    int columns,
    int timeout_has_value,
    double timeout_value,
    int overage_has_value,
    double overage_value
) {
    double base_timeout = timeout_has_value ? timeout_value : 2.0;
    return opening_book_opt_agent_impl(
        board,
        board_size,
        mark,
        step,
        columns,
        base_timeout,
        overage_has_value != 0,
        overage_value
    );
}

}
