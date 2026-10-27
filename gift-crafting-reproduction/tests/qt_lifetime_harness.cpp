#include <QtWidgets/QApplication>
#include <QtWidgets/QDialog>
#include <QtCore/QEventLoop>
#include <QtCore/QTimer>
#include <QtCore/QPointer>

#include <algorithm>
#include <functional>
#include <iostream>
#include <memory>
#include <optional>
#include <stdexcept>
#include <utility>
#include <vector>

#include "base/assertion.h"
#include "base/weak_ptr.h"
#include "base/weak_qptr.h"
#include <crl/common/crl_common_on_main_guarded.h>
#include <crl/qt/crl_qt_guards.h>

// Actual Qt, GSL, base weak pointers and crl::guard. Session/data/UI adapters
// below are test doubles. This is not a complete Telegram application build.
namespace base::assertion {
void log(const char *message, const char *file, int line) {
    std::cerr << "Assertion: " << message << " at " << file << ':' << line << '\n';
}
}
namespace Data {
struct UniqueGift {
    QString giftAddress;
    uint64 initialGiftId = 42;
    TimeId canCraftAt = 0;
    QString slug;
};
using SavedStarGiftId = int;
struct GiftUpdate {
    enum class Action { Upgraded, Delete };
    SavedStarGiftId id = 0;
    QString slug;
    Action action = Action::Delete;
};
struct GiftUpgradeResult {
    struct Info { std::shared_ptr<UniqueGift> unique; } info;
};
}
struct GiftForCraft {
    std::shared_ptr<Data::UniqueGift> unique;
    Data::SavedStarGiftId manageId = 0;
};
struct InformBox { QString text; QString title; };
InformBox MakeInformBox(InformBox value) { return value; }
struct Show {
    int notices = 0;
    void show(InformBox) { ++notices; }
};
namespace tr {
struct Marked {};
constexpr Marked marked;
QString lng_gift_craft_address_error(Marked) { return u"address"_q; }
QString lng_gift_craft_unavailable() { return u"unavailable"_q; }
}
namespace base::unixtime { TimeId now() { return 1000; } }
void ShowCraftLaterError(std::shared_ptr<Show> show, TimeId) { ++show->notices; }
struct MTPUpdates { std::shared_ptr<Data::GiftUpgradeResult> gift; };
struct SessionData {
    int invalidations = 0;
    std::vector<Data::GiftUpdate> changes;
    void nextForUpgradeGiftInvalidate(int) { ++invalidations; }
    void notifyGiftUpdate(Data::GiftUpdate value) { changes.push_back(std::move(value)); }
};
struct Api {
    int applied = 0;
    void applyUpdates(const MTPUpdates &) { ++applied; }
};
struct Session {
    Api apiValue;
    SessionData dataValue;
    Api &api() { return apiValue; }
    SessionData &data() { return dataValue; }
    int user() const { return 1; }
};
namespace Main { using Session = ::Session; }
namespace Window {
struct SessionController : base::has_weak_ptr {
    std::shared_ptr<Session> value = std::make_shared<Session>();
    Session &session() { return *value; }
};
}
class GenericBox : public QDialog {
public:
    std::shared_ptr<Show> show = std::make_shared<Show>();
    std::shared_ptr<Show> uiShow() const { return show; }
    void closeBox() { close(); deleteLater(); }

};
struct Preview { std::vector<GiftForCraft> gifts; bool autoStart = false; };
struct Picker {
    Fn<void(GiftForCraft)> chosen;
    bool firstSlot = false;
    bool allowResale = true;
};
struct Fixture {
    std::vector<Preview> previews;
    std::optional<Picker> picker;
};
Fixture *current = nullptr;
void ShowGiftCraftBox(not_null<Window::SessionController*> controller,
                     std::vector<GiftForCraft> gifts, bool autoStart) {
    (void)controller->session();
    current->previews.push_back({std::move(gifts), autoStart});
}
void ShowSelectGiftBox(not_null<Window::SessionController*>, uint64,
                      Fn<void(GiftForCraft)> chosen, std::vector<GiftForCraft>,
                      Fn<void()>, bool firstSlot, bool allowResale = true) {
    current->picker = Picker{std::move(chosen), firstSlot, allowResale};
}
std::shared_ptr<Data::GiftUpgradeResult> FindUniqueGift(Session *, const MTPUpdates &value) {
    return value.gift;
}

// @PRODUCTION_FRAGMENTS@

void require(bool condition, const char *reason) {
    if (!condition) throw std::runtime_error(reason);
}
std::shared_ptr<Data::UniqueGift> gift(bool exported = false) {
    auto result = std::make_shared<Data::UniqueGift>();
    result->slug = exported ? u"exported"_q : u"ordinary"_q;
    if (exported) result->giftAddress = u"fixture-address"_q;
    return result;
}
void drainDeletes() { QCoreApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete); }
void real_qobject_guard() {
    auto object = std::make_unique<QObject>();
    auto weak = base::make_weak(object.get());
    int calls = 0;
    auto callback = crl::guard(object.get(), [&] { ++calls; });
    callback();
    object.reset();
    callback();
    require(!weak && calls == 1, "real QObject guard did not follow destruction");
}
void queued_qobject_guard() {
    QEventLoop loop;
    auto deleted = std::make_unique<QObject>();
    QObject alive;
    int negative = 0, positive = 0;
    auto guarded = crl::guard(deleted.get(), [&] { ++negative; });
    auto control = crl::guard(&alive, [&] { ++positive; });
    QTimer::singleShot(0, [=] { guarded(); });
    QTimer::singleShot(0, [=] { control(); });
    QTimer::singleShot(20, &loop, &QEventLoop::quit);
    deleted.reset();
    loop.exec();
    require(positive == 1 && negative == 0, "queued Qt callbacks did not discriminate lifetimes");
}
void real_base_guard() {
    Window::SessionController controller;
    int calls = 0;
    auto callback = crl::guard(&controller, [&] { ++calls; });
    callback();
    invalidate_weak_ptrs(&controller);
    callback();
    require(calls == 1, "real base guard ignored explicit invalidation");
}
void information_deleted() {
    Fixture fixture;
    current = &fixture;
    Window::SessionController controller;
    auto box = std::make_unique<GenericBox>();
    auto callback = MakeInfoStart(&controller, box.get(), gift(true), 17);
    box.reset();
    callback();
    require(fixture.previews.empty() && !fixture.picker,
        "production info callback ran after actual QObject destruction");
}
void controller_deleted_before_selection() {
    Fixture fixture;
    current = &fixture;
    auto controller = std::make_unique<Window::SessionController>();
    auto box = new GenericBox();
    MakeInfoStart(controller.get(), box, gift(true), 18)();
    require(fixture.picker && !fixture.picker->allowResale, "owned-only picker was not requested");
    controller.reset();
    fixture.picker->chosen({gift(), 19});
    drainDeletes();
    require(fixture.previews.empty(), "selection ran after real controller weak invalidation");
}
void selection_dialog_deleted() {
    auto box = std::make_unique<GenericBox>();
    int calls = 0;
    auto callback = MakeSelection(box.get(), [&](GiftForCraft) { ++calls; }, true);
    box.reset();
    callback(gift());
    require(calls == 0, "production selection callback ignored QObject deletion");
}
void entry_after_deferred_delete() {
    Fixture fixture;
    current = &fixture;
    Window::SessionController controller;
    auto box = new GenericBox();
    QPointer<GenericBox> weak = box;
    auto callback = MakeInfoStart(&controller, box, gift(), 20);
    callback();
    drainDeletes();
    require(!weak, "Qt deferred deletion did not execute");
    callback();
    require(fixture.previews.size() == 1 && !fixture.previews[0].autoStart,
        "entry after actual deferred deletion reopened or auto-started");
}
void reply_after_controller_delete() {
    auto controller = std::make_unique<Window::SessionController>();
    auto session = controller->value;
    auto input = gift();
    auto secondary = gift(true);
    auto result = std::make_shared<Data::GiftUpgradeResult>();
    result->info.unique = input;
    int calls = 0;
    auto callback = MakeCraftResponse(session.get(), controller.get(), {{input, 21}, {secondary, 22}},
        [&](std::shared_ptr<Data::GiftUpgradeResult>) { ++calls; });
    controller.reset();
    callback(MTPUpdates{result});
    require(calls == 1 && session->api().applied == 1 && session->data().changes.size() == 2,
        "production reply did not reconcile after actual base controller destruction");
}
void real_qstring_validation() {
    auto show = std::make_shared<Show>();
    auto input = gift();
    require(!ShowCraftAddressError(show, input), "empty Qt address was rejected");
    input->giftAddress = u"fixture-address"_q;
    require(ShowCraftAddressError(show, input) && show->notices == 1,
        "Qt address validation did not report the primary restriction");
    input->canCraftAt = 1001;
    require(ShowCraftLaterError(show, input), "future cooldown was accepted");
    input->canCraftAt = 1000;
    require(!ShowCraftLaterError(show, input), "cooldown boundary was rejected");
}
int main(int argc, char **argv) {
    QApplication application(argc, argv);
    application.setQuitOnLastWindowClosed(false);
    std::cout << "Qt runtime: " << qVersion() << '\n';
    auto tests = std::vector<std::pair<const char *, Fn<void()>>>{
        {"real QObject and weak_qptr", real_qobject_guard},
        {"queued Qt callbacks with positive control", queued_qobject_guard},
        {"real base weak invalidation", real_base_guard},
        {"production info callback after QObject deletion", information_deleted},
        {"production picker after base controller deletion", controller_deleted_before_selection},
        {"production selection callback after QDialog deletion", selection_dialog_deleted},
        {"production entry after Qt deferred deletion", entry_after_deferred_delete},
        {"production reply after controller destruction", reply_after_controller_delete},
        {"production validation with real QString", real_qstring_validation},
    };
    if (argc == 2) {
        auto selected = decltype(tests)();
        for (const auto &test : tests) {
            if (std::string(argv[1]) == test.first) selected.push_back(test);
        }
        if (selected.empty()) {
            std::cerr << "Unknown component scenario\n";
            return 2;
        }
        tests = std::move(selected);
    } else if (argc != 1) {
        return 2;
    }
    int failed = 0;
    for (const auto &[name, test] : tests) {
        try {
            test();
            std::cout << "PASS: " << name << '\n';
        } catch (const std::exception &error) {
            ++failed;
            std::cout << "FAIL: " << name << ": " << error.what() << '\n';
        }
        drainDeletes();
    }
    std::cout << "SUMMARY: " << tests.size() - failed << '/' << tests.size()
              << " passed; real Qt/crl/base, test Session/data/UI adapters.\n";
    return failed ? 1 : 0;
}
