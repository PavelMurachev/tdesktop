#define main IndividualReactiveProbeEntry
#include "rpl_loading.cpp"
#undef main
#include <fstream>

// Owned-only has an independent observable model. Existing market behavior is
// additionally compared against baseline traces, including error-response order.
std::string check_sequence(const std::string &word, bool market) {
    Fixture fixture;
    current = &fixture;
    auto controller = std::make_unique<Window::SessionController>(&fixture);
    RunPickerLoad(controller.get(), market);
    if (fixture.craftRequests != 1 || fixture.resaleRequests != (market ? 1 : 0)) {
        throw std::runtime_error("endpoint requests differ from mode; word=" + word);
    }
    char craftReply = 0, marketReply = 0;
    bool destroyed = false, expectedOpen = false;
    auto observations = std::string();
    for (const auto event : word) {
        const auto countBefore = fixture.rendered.size();
        switch (event) {
        case 'C':
        case 'E':
            if (!craftReply) craftReply = event;
            fixture.craft.fire(event == 'C'
                ? Data::CraftGiftsDescriptor{42, 1}
                : Data::CraftGiftsDescriptor{});
            break;
        case 'M':
        case 'F':
            if (!marketReply) marketReply = event;
            fixture.resale.fire(event == 'M'
                ? Data::ResaleGiftsDescriptor{42, 2}
                : Data::ResaleGiftsDescriptor{});
            break;
        case 'D':
            destroyed = true;
            controller.reset();
            break;
        default:
            throw std::runtime_error("unknown sequence event");
        }
        if (!destroyed && !expectedOpen && !market) {
            expectedOpen = (craftReply != 0);
        }
        if (fixture.rendered.size() > 1
            || (destroyed && fixture.rendered.size() != countBefore)
            || (!market && fixture.rendered.size() != (expectedOpen ? 1U : 0U))) {
            throw std::runtime_error("unexpected picker count; word=" + word + "; event=" + event);
        }
        if (fixture.resaleRequests != (market ? 1 : 0)) {
            throw std::runtime_error("mode triggered unexpected resale request; word=" + word);
        }
        observations += std::to_string(fixture.rendered.size()) + ':';
        if (!fixture.rendered.empty()) {
            observations += std::to_string(fixture.rendered[0].first) + ','
                + std::to_string(fixture.rendered[0].second);
        }
        observations += ';';
    }
    return observations;
}
int run_sequences(bool market, std::ostream &trace) {
    constexpr auto alphabet = "CEMFD";
    constexpr int alphabetSize = 5;
    constexpr int maxLength = 5;
    int checked = 0, wordsOfLength = 1;
    for (int length = 0; length <= maxLength; ++length) {
        for (int number = 0; number != wordsOfLength; ++number) {
            auto remaining = number;
            auto word = std::string(length, alphabet[0]);
            for (auto &letter : word) {
                letter = alphabet[remaining % alphabetSize];
                remaining /= alphabetSize;
            }
            trace << (market ? "market|" : "owned|") << word << '|'
                  << check_sequence(word, market) << '\n';
            ++checked;
        }
        wordsOfLength *= alphabetSize;
    }
    return checked;
}
int main(int argc, char **argv) {
    QCoreApplication application(argc, argv);
    const auto legacyOnly = argc == 2 && std::string(argv[1]) == "legacy";
    if (argc > 2 || (argc == 2 && !legacyOnly)) return 2;
    std::cout << "QtCore runtime: " << qVersion() << std::endl;
    std::ofstream trace("sequence-observations.txt");
    if (!trace) return 3;
    int total = 0;
    try {
        if (!legacyOnly) {
            const auto count = run_sequences(false, trace);
            total += count;
            std::cout << "PASS: owned-only event sequences: " << count << std::endl;
        }
        const auto count = run_sequences(true, trace);
        total += count;
        std::cout << "PASS: existing-market event sequences: " << count << std::endl;
    } catch (const std::exception &error) {
        std::cerr << "FAIL: " << error.what() << std::endl;
        return 1;
    }
    std::cout << "SEQUENCES: " << total << " checked; max_length=5; alphabet=CEMFD" << std::endl;
    return 0;
}
