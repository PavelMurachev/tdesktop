#include <QtCore/QCoreApplication>
#include <QtCore/QEventLoop>
#include <QtCore/QTimer>

#include <iostream>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "base/assertion.h"
#include "base/weak_ptr.h"
#include <crl/common/crl_common_on_main_guarded.h>
#include <rpl/event_stream.h>
#include <rpl/range.h>

// Real pinned rpl/base/crl and QtCore. Data, transport and UI below are adapters.
namespace base::assertion {
void log(const char *message, const char *file, int line) {
    std::cerr << "Assertion: " << message << " at " << file << ':' << line << '\n';
}
}
namespace Data {
struct CraftGiftsDescriptor { uint64 giftId = 0; int count = 0; };
struct ResaleGiftsDescriptor { uint64 giftId = 0; int count = 0; };
struct ResaleFilter { bool forCraft = false; };
}
struct Session {};
struct LoadingState {
    Data::CraftGiftsDescriptor craft;
    Data::ResaleGiftsDescriptor resale;
    rpl::lifetime craftLifetime;
    rpl::lifetime resaleLifetime;
};
struct Fixture {
    Session session;
    int craftRequests = 0, resaleRequests = 0;
    Session *requestedSession = nullptr;
    uint64 requestedGiftId = 0;
    bool forCraft = false;
    rpl::event_stream<Data::CraftGiftsDescriptor> craft;
    rpl::event_stream<Data::ResaleGiftsDescriptor> resale;
    std::optional<Data::CraftGiftsDescriptor> inlineCraft;
    std::optional<Data::ResaleGiftsDescriptor> inlineResale;
    std::weak_ptr<LoadingState> state;
    std::vector<std::pair<uint64, int>> rendered;
    Fn<void()> onShow;
    ~Fixture() {
        craft.fire_done();
        resale.fire_done();
        // Test cleanup only: retention assertions run before this destructor.
        if (const auto retained = state.lock()) {
            retained->craftLifetime.destroy();
            retained->resaleLifetime.destroy();
        }
    }
};
Fixture *current = nullptr;
namespace Window {
struct SessionController : base::has_weak_ptr {
    Fixture *fixture = nullptr;
    explicit SessionController(Fixture *value) : fixture(value) {}
    Session &session() { return fixture->session; }
    void show(Fn<void()> make) {
        make();
        if (fixture->onShow) fixture->onShow();
    }
};
}
Fn<void()> Box(Fn<void()> make) { return make; }
namespace Data {
rpl::producer<CraftGiftsDescriptor> CraftGiftsSlice(Session *session, uint64 giftId) {
    ++current->craftRequests;
    current->requestedSession = session;
    current->requestedGiftId = giftId;
    if (current->inlineCraft) return rpl::single(CraftGiftsDescriptor(*current->inlineCraft));
    return current->craft.events();
}
rpl::producer<ResaleGiftsDescriptor> ResaleGiftsSlice(Session *, uint64, ResaleFilter filter) {
    ++current->resaleRequests;
    current->forCraft = filter.forCraft;
    if (current->inlineResale) return rpl::single(ResaleGiftsDescriptor(*current->inlineResale));
    return current->resale.events();
}
}

void RunPickerLoad(not_null<Window::SessionController*> controller,
                   [[maybe_unused]] bool allowResale, uint64 giftId = 42) {
    const auto session = &controller->session();
    const auto state = std::make_shared<LoadingState>();
    auto fixture = controller->fixture;
    fixture->state = state;
    const auto make = [=] {
        fixture->rendered.emplace_back(state->craft.giftId, state->resale.count);
    };
    // @PRODUCTION_LOADING@
}

void require(bool value, const char *reason) {
    if (!value) throw std::runtime_error(reason);
}
void no_response() {
    Fixture fixture;
    current = &fixture;
    Window::SessionController controller(&fixture);
    RunPickerLoad(&controller, false);
    require(fixture.craftRequests == 1 && fixture.resaleRequests == 0,
        "owned-only load requested resale");
    require(fixture.rendered.empty(), "picker opened before any response");
    require(!fixture.state.expired(), "pending request lost its state");
    fixture.craft.fire_done();
    require(fixture.state.expired(), "completion without value retained adapter state");
}
void owned_reply() {
    Fixture fixture;
    current = &fixture;
    Window::SessionController controller(&fixture);
    RunPickerLoad(&controller, false);
    fixture.craft.fire({42, 3});
    require(fixture.rendered.size() == 1 && fixture.rendered[0].first == 42,
        "owned response did not open its picker");
    require(fixture.resaleRequests == 0, "owned reply caused a resale request");
    require(fixture.state.expired(), "self-destroying subscription retained state after rendering");
}
void empty_error_descriptor() {
    Fixture fixture;
    current = &fixture;
    Window::SessionController controller(&fixture);
    RunPickerLoad(&controller, false);
    fixture.craft.fire({}); // Actual CraftGiftsSlice emits {} on RPC failure.
    require(fixture.rendered.size() == 1 && fixture.rendered[0].first == 0,
        "empty error descriptor left owned-only load waiting for resale");
    require(fixture.resaleRequests == 0, "error fallback requested the market");
}
void deleted_controller() {
    Fixture fixture;
    current = &fixture;
    auto controller = std::make_unique<Window::SessionController>(&fixture);
    RunPickerLoad(controller.get(), false);
    controller.reset();
    QEventLoop loop;
    QTimer::singleShot(0, [&] { fixture.craft.fire({42, 1}); });
    QTimer::singleShot(10, &loop, &QEventLoop::quit);
    loop.exec();
    require(fixture.rendered.empty(), "queued response touched deleted base controller");
    require(fixture.state.expired(), "late reply retained state after guard rejection");
}
void duplicate_reply() {
    Fixture fixture;
    current = &fixture;
    Window::SessionController controller(&fixture);
    RunPickerLoad(&controller, false);
    fixture.craft.fire({42, 1});
    fixture.craft.fire({42, 2});
    require(fixture.rendered.size() == 1, "terminated rpl subscription reopened picker");
}
void craft_first() {
    Fixture fixture;
    current = &fixture;
    Window::SessionController controller(&fixture);
    RunPickerLoad(&controller, true);
    fixture.craft.fire({42, 1});
    require(fixture.rendered.empty(), "existing market picker opened before resale");
    fixture.resale.fire({42, 2});
    require(fixture.rendered.size() == 1 && fixture.rendered[0].second == 2,
        "craft-first order failed");
    require(fixture.resaleRequests == 1 && fixture.forCraft, "resale filter changed");
}
void market_first() {
    Fixture fixture;
    current = &fixture;
    Window::SessionController controller(&fixture);
    RunPickerLoad(&controller, true);
    fixture.resale.fire({42, 2});
    require(fixture.rendered.empty(), "existing picker opened before craft response");
    fixture.craft.fire({42, 1});
    require(fixture.rendered.size() == 1 && fixture.rendered[0].second == 2,
        "market-first order failed");
}
void empty_market() {
    Fixture fixture;
    current = &fixture;
    Window::SessionController controller(&fixture);
    RunPickerLoad(&controller, true);
    fixture.resale.fire({42, 0});
    fixture.craft.fire({42, 1});
    require(fixture.rendered.size() == 1 && fixture.rendered[0].second == 0,
        "empty market blocked existing picker");
}
void inline_owned() {
    Fixture fixture;
    current = &fixture;
    fixture.inlineCraft = Data::CraftGiftsDescriptor{42, 1};
    Window::SessionController controller(&fixture);
    RunPickerLoad(&controller, false);
    require(fixture.rendered.size() == 1 && fixture.resaleRequests == 0,
        "inline one-shot owned source failed");
    require(fixture.state.expired(), "inline source retained completed adapter state");
}
void inline_market() {
    Fixture fixture;
    current = &fixture;
    fixture.inlineCraft = Data::CraftGiftsDescriptor{42, 1};
    fixture.inlineResale = Data::ResaleGiftsDescriptor{42, 2};
    Window::SessionController controller(&fixture);
    RunPickerLoad(&controller, true);
    require(fixture.rendered.size() == 1 && fixture.rendered[0].second == 2,
        "two inline one-shot sources failed");
    require(fixture.state.expired(), "inline market source retained state");
}
void reentrant_reply() {
    Fixture fixture;
    current = &fixture;
    bool injected = false;
    fixture.onShow = [&] {
        if (!std::exchange(injected, true)) fixture.craft.fire({42, 2});
    };
    Window::SessionController controller(&fixture);
    RunPickerLoad(&controller, false);
    fixture.craft.fire({42, 1});
    require(injected && fixture.rendered.size() == 1,
        "nested emit during UI adapter reopened picker");
}
void separate_sessions() {
    Fixture first, second;
    Window::SessionController a(&first), b(&second);
    current = &first;
    RunPickerLoad(&a, false, 42);
    current = &second;
    RunPickerLoad(&b, false, 43);
    second.craft.fire({43, 1});
    first.craft.fire({42, 1});
    require(first.requestedSession == &first.session && second.requestedSession == &second.session,
        "source binding crossed sessions");
    require(first.requestedGiftId == 42 && second.requestedGiftId == 43,
        "request gift IDs crossed sessions");
    require(first.rendered.size() == 1 && second.rendered.size() == 1
            && first.rendered[0].first == 42 && second.rendered[0].first == 43,
        "interleaved replies opened the wrong controller");
}
void legacy_completion_without_value() {
    Fixture fixture;
    current = &fixture;
    Window::SessionController controller(&fixture);
    RunPickerLoad(&controller, true);
    fixture.craft.fire_done();
    fixture.resale.fire_done();
    require(fixture.rendered.empty(), "completed streams without values opened picker");
    require(fixture.state.expired(), "completed legacy streams retained adapter state");
}
int main(int argc, char **argv) {
    QCoreApplication application(argc, argv);
    std::cout << "QtCore runtime: " << qVersion() << std::endl;
    auto tests = std::vector<std::pair<const char *, Fn<void()>>>{
        {"owned pending and completion", no_response},
        {"owned response and lifetime release", owned_reply},
        {"empty error descriptor", empty_error_descriptor},
        {"queued reply after controller destruction", deleted_controller},
        {"duplicate reply ignored", duplicate_reply},
        {"existing market craft first", craft_first},
        {"existing market resale first", market_first},
        {"existing market empty list", empty_market},
        {"inline owned producer", inline_owned},
        {"inline market producers", inline_market},
        {"nested emit during rendering", reentrant_reply},
        {"interleaved session replies", separate_sessions},
        {"legacy completion without values", legacy_completion_without_value},
    };
    if (argc == 2) {
        auto selected = decltype(tests)();
        for (const auto &test : tests) if (test.first == std::string(argv[1])) selected.push_back(test);
        if (selected.empty()) return 2;
        tests = std::move(selected);
    } else if (argc != 1) {
        return 2;
    }
    int failed = 0;
    for (const auto &[name, test] : tests) {
        try {
            test();
            std::cout << "PASS: " << name << std::endl;
        } catch (const std::exception &error) {
            ++failed;
            std::cout << "FAIL: " << name << ": " << error.what() << std::endl;
        }
    }
    std::cout << "SUMMARY: " << tests.size() - failed << '/' << tests.size()
              << " passed; real rpl/base/crl/QtCore, test data/transport/UI." << std::endl;
    return failed ? 1 : 0;
}
