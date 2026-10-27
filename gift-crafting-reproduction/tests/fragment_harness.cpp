#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <variant>
#include <vector>

// This harness substitutes UI, transport and framework lifetime primitives.
// It executes extracted production fragments, not the complete Qt application.
template <typename T> using not_null = T;
template <typename T> using Fn = std::function<T>;
struct QString : std::string {
    using std::string::string;
    QString() = default;
    QString(std::string value) : std::string(std::move(value)) {}
    bool startsWith(const QString &prefix) const { return starts_with(prefix); }
    QString mid(std::size_t offset) const { return substr(offset); }
    int toInt() const { return std::stoi(*this); }
};
QString operator""_q(const char16_t *text, std::size_t size) {
    QString result;
    for (std::size_t i = 0; i != size; ++i) result.push_back(char(text[i]));
    return result;
}
using PeerId = long long;
using TimeId = long long;
struct Address {
    bool present = false;
    bool isEmpty() const { return !present; }
};
namespace Data {
struct UniqueGift {
    Address giftAddress;
    unsigned long long initialGiftId = 42;
    TimeId canCraftAt = 0;
    int craftChancePermille = 100;
    PeerId ownerId = 1;
    QString slug;
};
struct CreditsHistoryEntry {
    std::shared_ptr<UniqueGift> uniqueGift;
    bool in = true;
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
QString lng_gift_craft_address_error(Marked) { return "address"; }
QString lng_gift_craft_unavailable() { return "unavailable"; }
}
namespace base::unixtime {
TimeId now() { return 1000; }
}
void ShowCraftLaterError(std::shared_ptr<Show> show, TimeId) {
    ++show->notices;
}
struct SessionData {
    struct Peer {
        PeerId id = 0;
        bool isSelf() const { return id == 1; }
    };
    std::map<PeerId, std::shared_ptr<Peer>> peers;
    int invalidations = 0;
    std::vector<Data::GiftUpdate> changes;
    void nextForUpgradeGiftInvalidate(int) { ++invalidations; }
    void notifyGiftUpdate(Data::GiftUpdate update) {
        changes.push_back(std::move(update));
    }
    const std::shared_ptr<Peer> &peer(PeerId id) {
        auto &value = peers[id];
        if (!value) value = std::make_shared<Peer>(Peer{id});
        return value;
    }
};
struct MTPUpdates { std::shared_ptr<Data::GiftUpgradeResult> gift; };
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
struct SessionController {
    int shownBoxes = 0;
    std::shared_ptr<bool> life = std::make_shared<bool>(true);
    std::shared_ptr<Session> value = std::make_shared<Session>();
    Session &session() {
        if (!*life) throw std::runtime_error("access to closed controller");
        return *value;
    }
    void close() { *life = false; }
    void show(Fn<void()> make) { ++shownBoxes; make(); }
};
}
struct GenericBox {
    std::shared_ptr<bool> life = std::make_shared<bool>(true);
    std::shared_ptr<Show> show = std::make_shared<Show>();
    std::shared_ptr<Show> uiShow() const { return show; }
    void closeBox() { *life = false; }
};
namespace crl {
template <typename Context, typename Callback>
auto guard(Context *context, Callback callback) {
    std::weak_ptr<bool> lifetime = context->life;
    return [lifetime, callback](auto... args) {
        const auto live = lifetime.lock();
        if (live && *live) callback(args...);
    };
}
}
struct Preview {
    std::vector<GiftForCraft> gifts;
    bool autoStart = false;
    Session *session = nullptr;
};
struct Picker {
    unsigned long long giftId = 0;
    Fn<void(GiftForCraft)> chosen;
    std::vector<GiftForCraft> selected;
    Fn<void()> closed;
    bool firstSlot = false;
    bool allowResale = true;
};
struct Fixture {
    std::vector<Preview> previews;
    std::optional<Picker> picker;
};
Fixture *current = nullptr;
void ShowGiftCraftBox(
        not_null<Window::SessionController*> controller,
        std::vector<GiftForCraft> gifts,
        bool autoStartCraft) {
    auto *session = &controller->session();
    current->previews.push_back({std::move(gifts), autoStartCraft, session});
}
void ShowSelectGiftBox(
        not_null<Window::SessionController*>,
        unsigned long long giftId,
        Fn<void(GiftForCraft)> chosen,
        std::vector<GiftForCraft> selected,
        Fn<void()> closed,
        bool firstSlot,
        bool allowResale = true) {
    current->picker = Picker{giftId, std::move(chosen), std::move(selected),
        std::move(closed), firstSlot, allowResale};
}
std::shared_ptr<Data::GiftUpgradeResult> FindUniqueGift(
        Session *, const MTPUpdates &updates) {
    return updates.gift;
}
namespace MTP {
struct Error {
    QString value;
    QString type() const { return value; }
};
}
struct CraftResultError { QString type; };
struct CraftResultWait { int seconds = 0; };
using CraftResult = std::variant<std::shared_ptr<Data::GiftUpgradeResult>,
    CraftResultError, CraftResultWait>;
struct StartState {
    bool crafting = false;
    struct Chosen {
        std::vector<GiftForCraft> list;
        const std::vector<GiftForCraft> &current() const { return list; }
    } chosen;
};

// @PICKER_LOADING_SUPPORT@
// @PRODUCTION_FRAGMENTS@

void require(bool value, const char *reason) {
    if (!value) throw std::runtime_error(reason);
}
std::shared_ptr<Data::UniqueGift> gift(const QString &slug, bool exported = false) {
    auto result = std::make_shared<Data::UniqueGift>();
    result->slug = slug;
    result->giftAddress.present = exported;
    return result;
}
void ordinary_preview() {
    Fixture fixture;
    current = &fixture;
    Window::SessionController controller;
    GenericBox info;
    const auto original = gift("ordinary");
    MakeInfoStart(&controller, &info, original, 77)();
    require(!fixture.picker, "ordinary gift must not open the extra picker");
    require(fixture.previews.size() == 1, "ordinary preview missing");
    const auto &preview = fixture.previews.front();
    require(preview.gifts.size() == 1 && preview.gifts[0].unique == original,
        "ordinary ingredient changed");
    require(preview.gifts[0].manageId == 77, "saved reference changed");
    require(!preview.autoStart, "crafting must not start automatically");
}
void exported_entry() {
    Fixture fixture;
    current = &fixture;
    Window::SessionController controller;
    GenericBox info;
    const auto original = gift("exported", true);
    MakeInfoStart(&controller, &info, original, 88)();
    require(fixture.picker.has_value(), "exported entry must ask for a primary");
    require(fixture.previews.empty(), "preview must wait for explicit selection");
    require(fixture.picker->giftId == original->initialGiftId, "wrong gift type");
    require(fixture.picker->firstSlot, "primary validation must be enabled");
    require(!fixture.picker->allowResale, "new entry must not offer purchases");
    require(fixture.picker->selected.size() == 1
        && fixture.picker->selected[0].unique == original,
        "original must be marked already selected");
    require(!*info.life, "information screen must close after dispatch");
}
void explicit_primary() {
    Fixture fixture;
    current = &fixture;
    Window::SessionController controller;
    GenericBox info;
    const auto original = gift("exported", true);
    const auto primary = gift("primary");
    MakeInfoStart(&controller, &info, original, 99)();
    require(fixture.picker.has_value(), "primary picker missing");
    GenericBox pickerBox;
    MakeSelection(&pickerBox, fixture.picker->chosen, fixture.picker->firstSlot)(primary);
    require(fixture.previews.size() == 1, "explicit selection must open preview");
    const auto &preview = fixture.previews.front();
    require(preview.gifts.size() == 2, "both ingredients must be retained");
    require(preview.gifts[0].unique == primary, "primary must be first");
    require(preview.gifts[1].unique == original && preview.gifts[1].manageId == 99,
        "original saved reference must be retained second");
    require(!preview.autoStart, "selection is not craft confirmation");
}
void cancelled_picker() {
    Fixture fixture;
    current = &fixture;
    Window::SessionController controller;
    GenericBox info;
    MakeInfoStart(&controller, &info, gift("exported", true), 11)();
    require(fixture.picker.has_value(), "primary picker missing");
    fixture.picker->closed();
    require(fixture.previews.empty(), "cancelling must not open a preview");
}
void closed_controller() {
    Fixture fixture;
    current = &fixture;
    Window::SessionController controller;
    GenericBox info;
    MakeInfoStart(&controller, &info, gift("exported", true), 11)();
    require(fixture.picker.has_value(), "primary picker missing");
    controller.close();
    fixture.picker->chosen(GiftForCraft{gift("primary"), 0});
    require(fixture.previews.empty(), "closed controller must suppress the transition");
}
void closed_information() {
    Fixture fixture;
    current = &fixture;
    Window::SessionController controller;
    GenericBox info;
    const auto delayed = MakeInfoStart(&controller, &info, gift("exported", true), 11);
    info.closeBox();
    delayed();
    require(!fixture.picker && fixture.previews.empty(),
        "closed information screen must suppress delayed work");
}
void cooldown_primary() {
    GenericBox picker;
    bool chosen = false;
    auto candidate = gift("cooldown");
    candidate->canCraftAt = 1001;
    MakeSelection(&picker, [&](GiftForCraft) { chosen = true; }, true)(candidate);
    require(!chosen && *picker.life && picker.show->notices == 1,
        "future cooldown must reject selection and keep picker open");
}
void cooldown_boundary() {
    GenericBox picker;
    bool chosen = false;
    auto candidate = gift("ready");
    candidate->canCraftAt = 1000;
    MakeSelection(&picker, [&](GiftForCraft) { chosen = true; }, true)(candidate);
    require(chosen && !*picker.life, "cooldown must expire exactly at its timestamp");
}
void blockchain_primary() {
    GenericBox picker;
    bool chosen = false;
    MakeSelection(&picker, [&](GiftForCraft) { chosen = true; }, true)(gift("NFT", true));
    require(!chosen && *picker.life && picker.show->notices == 1,
        "blockchain gift must remain invalid as primary under current API");
}
void closed_selection() {
    GenericBox picker;
    bool chosen = false;
    const auto delayed = MakeSelection(&picker, [&](GiftForCraft) { chosen = true; }, true);
    picker.closeBox();
    delayed(gift("ready"));
    require(!chosen, "closed selection screen must suppress selection callback");
}
void late_success() {
    Window::SessionController controller;
    auto *session = &controller.session();
    auto primary = gift("primary");
    auto original = gift("exported", true);
    std::vector<GiftForCraft> inputs{{primary, 7}, {original, 8}};
    bool delivered = false;
    auto result = std::make_shared<Data::GiftUpgradeResult>();
    result->info.unique = primary;
    auto response = MakeCraftResponse(session, &controller, inputs,
        [&](std::shared_ptr<Data::GiftUpgradeResult> got) {
            require(got == result, "wrong result delivered");
            delivered = true;
        });
    controller.close();
    response(MTPUpdates{result});
    require(delivered && session->api().applied == 1, "reply reconciliation missing");
    const auto &changes = session->data().changes;
    require(changes.size() == 2 && changes[0].id == 7 && changes[1].id == 8,
        "input references lost during late reply");
    require(changes[0].action == Data::GiftUpdate::Action::Upgraded
        && changes[1].action == Data::GiftUpdate::Action::Delete,
        "late reply must upgrade primary and remove consumed secondary");
}
void late_unsuccessful_craft() {
    Window::SessionController controller;
    auto *session = &controller.session();
    std::vector<GiftForCraft> inputs{{gift("primary"), 7}, {gift("secondary", true), 8}};
    bool delivered = false;
    auto response = MakeCraftResponse(session, &controller, inputs,
        [&](std::shared_ptr<Data::GiftUpgradeResult> got) {
            require(!got, "unsuccessful craft must not invent a result");
            delivered = true;
        });
    controller.close();
    response(MTPUpdates{});
    require(delivered && session->data().changes.size() == 2,
        "unsuccessful craft must reconcile all consumed inputs");
    for (const auto &change : session->data().changes) {
        require(change.action == Data::GiftUpdate::Action::Delete,
            "unsuccessful craft must not mark an input upgraded");
    }
}
void own_entry_allowed() {
    Session session;
    require(CanCraftGift(&session, {gift("mine"), true}), "owned eligible gift hidden");
}
void other_owner_rejected() {
    Session session;
    auto item = gift("other");
    item->ownerId = 2;
    require(!CanCraftGift(&session, {item, true}), "other owner's gift accepted");
}
void hosted_without_owner_rejected() {
    Session session;
    auto item = gift("hosted", true);
    item->ownerId = 0;
    require(!CanCraftGift(&session, {item, true}), "hosting mistaken for ownership");
}
void outgoing_entry_rejected() {
    Session session;
    require(!CanCraftGift(&session, {gift("sent"), false}), "outgoing entry accepted");
}
void missing_chance_rejected() {
    Session session;
    auto item = gift("disabled");
    item->craftChancePermille = 0;
    require(!CanCraftGift(&session, {item, true}), "missing server chance accepted");
}
void missing_unique_rejected() {
    Session session;
    require(!CanCraftGift(&session, {nullptr, true}), "missing unique gift accepted");
}
void double_entry() {
    Fixture fixture;
    current = &fixture;
    Window::SessionController controller;
    GenericBox info;
    const auto start = MakeInfoStart(&controller, &info, gift("ordinary"), 10);
    start();
    start();
    require(fixture.previews.size() == 1, "second entry invocation reopened a preview");
}
void double_selection() {
    GenericBox box;
    int callbacks = 0;
    auto selection = MakeSelection(&box, [&](GiftForCraft) { ++callbacks; }, true);
    auto primary = gift("primary");
    selection(primary);
    selection(primary);
    require(callbacks == 1, "selection callback invoked twice after closing picker");
}
void double_confirmation_gate() {
    GenericBox box;
    auto state = std::make_shared<StartState>();
    state->chosen.list = {{gift("primary"), 5}, {gift("secondary", true), 6}};
    int dispatches = 0;
    const auto start = MakeStartGate(state, &box, [&] { ++dispatches; });
    start();
    start();
    require(dispatches == 1 && state->crafting,
        "actual start gate did not suppress a duplicate invocation");
}
void account_routing() {
    Fixture fixture;
    current = &fixture;
    Window::SessionController originalAccount;
    Window::SessionController otherAccount;
    GenericBox info;
    auto *expected = &originalAccount.session();
    MakeInfoStart(&originalAccount, &info, gift("exported", true), 100)();
    require(fixture.picker.has_value(), "primary picker missing");
    otherAccount.session().apiValue.applied = 50;
    fixture.picker->chosen({gift("primary"), 0});
    require(fixture.previews.size() == 1 && fixture.previews[0].session == expected,
        "selection changed the originating account");
    require(otherAccount.session().apiValue.applied == 50,
        "unrelated account was modified");
}
void reply_account_routing() {
    Window::SessionController originalAccount;
    Window::SessionController otherAccount;
    auto *session = &originalAccount.session();
    std::vector<GiftForCraft> inputs{{gift("ingredient"), 45}};
    auto response = MakeCraftResponse(session, &originalAccount, inputs,
        [](std::shared_ptr<Data::GiftUpgradeResult>) {});
    response(MTPUpdates{});
    require(session->data().changes.size() == 1
        && otherAccount.session().data().changes.empty(),
        "late response touched an unrelated account");
}
void validation_errors_preserved() {
    for (const auto *type : {"STARGIFT_INVALID", "STARGIFT_NOT_OWNED",
                            "STARGIFT_ALREADY_USED", "STARGIFT_TYPE_INVALID"}) {
        int callbacks = 0;
        std::optional<CraftResult> result;
        MakeCraftError([&](CraftResult value) {
            ++callbacks;
            result = value;
        })(MTP::Error{type});
        require(callbacks == 1 && result && std::holds_alternative<CraftResultError>(*result),
            "RPC validation error confused with a completed probabilistic loss");
        require(std::get<CraftResultError>(*result).type == type,
            "server validation error was changed");
    }
}
void wait_error_preserved() {
    std::optional<CraftResult> result;
    MakeCraftError([&](CraftResult value) { result = value; })(
        MTP::Error{"STARGIFT_CRAFT_TOO_EARLY_3600"});
    require(result && std::holds_alternative<CraftResultWait>(*result)
        && std::get<CraftResultWait>(*result).seconds == 3600,
        "cooldown response was treated as a completed craft");
}
void uncertain_error_preserved() {
    int callbacks = 0;
    std::optional<CraftResult> result;
    MakeCraftError([&](CraftResult value) { ++callbacks; result = value; })(
        MTP::Error{"TIMEOUT"});
    require(callbacks == 1 && result && std::holds_alternative<CraftResultError>(*result)
        && std::get<CraftResultError>(*result).type == "TIMEOUT",
        "uncertain RPC error was not passed once as an unresolved error");
}
void three_and_four_ingredients() {
    for (const auto count : {3, 4}) {
        Window::SessionController controller;
        auto *session = &controller.session();
        std::vector<GiftForCraft> inputs;
        for (int i = 0; i != count; ++i) {
            inputs.push_back({gift("ingredient-" + std::to_string(i), i != 0), i + 1});
        }
        auto result = std::make_shared<Data::GiftUpgradeResult>();
        result->info.unique = inputs.front().unique;
        MakeCraftResponse(session, &controller, inputs,
            [](std::shared_ptr<Data::GiftUpgradeResult>) {})(MTPUpdates{result});
        require(int(session->data().changes.size()) == count,
            "result did not reconcile every selected ingredient");
        require(session->data().changes.front().action == Data::GiftUpdate::Action::Upgraded,
            "primary result was not retained");
        for (int i = 1; i != count; ++i) {
            require(session->data().changes[i].action == Data::GiftUpdate::Action::Delete,
                "consumed secondary ingredient was not removed");
        }
    }
}
void heap_lifetime_after_delete() {
    auto controller = std::make_unique<Window::SessionController>();
    const auto session = controller->value;
    const auto input = gift("primary");
    const auto result = std::make_shared<Data::GiftUpgradeResult>();
    result->info.unique = input;
    int callbacks = 0;
    const auto response = MakeCraftResponse(session.get(), controller.get(), {{input, 5}},
        [&](std::shared_ptr<Data::GiftUpgradeResult>) { ++callbacks; });
    controller.reset();
    response(MTPUpdates{result});
    require(callbacks == 1 && session->data().changes.size() == 1,
        "response could not complete after actual controller destruction");
}
void owned_picker_without_market() {
    PickerLoadFixture fixture;
    loading = &fixture;
    Window::SessionController controller;
    RunPickerLoad(&controller, false);
    require(fixture.craftRequests == 1 && fixture.resaleRequests == 0,
        "owned-only picker fetched marketplace candidates");
    require(fixture.session == &controller.session() && fixture.giftId == 42,
        "picker loaded another session or gift type");
    require(controller.shownBoxes == 0, "picker opened before owned response");
    fixture.craft({42});
    require(controller.shownBoxes == 1, "owned response did not open picker");
}
void owned_picker_empty() {
    PickerLoadFixture fixture;
    loading = &fixture;
    Window::SessionController controller;
    RunPickerLoad(&controller, false);
    fixture.craft({42});
    require(controller.shownBoxes == 1, "empty owned list did not open picker");
}
void owned_picker_no_reply() {
    PickerLoadFixture fixture;
    loading = &fixture;
    Window::SessionController controller;
    RunPickerLoad(&controller, false);
    require(controller.shownBoxes == 0, "missing reply opened picker");
}
void owned_picker_closed_controller() {
    PickerLoadFixture fixture;
    loading = &fixture;
    Window::SessionController controller;
    RunPickerLoad(&controller, false);
    controller.close();
    fixture.craft({42});
    require(controller.shownBoxes == 0, "late list reopened closed controller");
}
void owned_picker_duplicate_reply() {
    PickerLoadFixture fixture;
    loading = &fixture;
    Window::SessionController controller;
    RunPickerLoad(&controller, false);
    fixture.craft({42});
    fixture.craft({42});
    require(controller.shownBoxes == 1, "duplicate list reply reopened picker");
}
void resale_picker_craft_first() {
    PickerLoadFixture fixture;
    loading = &fixture;
    Window::SessionController controller;
    RunPickerLoad(&controller, true);
    require(fixture.craftRequests == 1 && fixture.resaleRequests == 1,
        "existing picker no longer fetches both lists");
    fixture.craft({42});
    require(controller.shownBoxes == 0, "existing picker ignored pending market");
    fixture.resale({42, 1});
    require(controller.shownBoxes == 1, "existing picker did not open after both lists");
}
void resale_picker_market_first() {
    PickerLoadFixture fixture;
    loading = &fixture;
    Window::SessionController controller;
    RunPickerLoad(&controller, true);
    fixture.resale({42, 1});
    require(controller.shownBoxes == 0, "existing picker ignored pending owned list");
    fixture.craft({42});
    require(controller.shownBoxes == 1, "reverse reply order did not open picker");
}
void resale_picker_empty_market() {
    PickerLoadFixture fixture;
    loading = &fixture;
    Window::SessionController controller;
    RunPickerLoad(&controller, true);
    fixture.resale({42, 0});
    fixture.craft({42});
    require(controller.shownBoxes == 1, "empty market kept existing picker blocked");
}
int main(int argc, char **argv) {
    auto tests = std::vector<std::pair<const char *, Fn<void()>>>{
        {"ordinary preview", ordinary_preview},
        {"exported entry: explicit owned-only primary", exported_entry},
        {"explicit primary preserves ingredients and saved reference", explicit_primary},
        {"cancelling the picker", cancelled_picker},
        {"controller closed before selection", closed_controller},
        {"information closed before delayed work", closed_information},
        {"primary cooldown rejected", cooldown_primary},
        {"primary cooldown boundary", cooldown_boundary},
        {"blockchain primary rejected", blockchain_primary},
        {"selection window closed", closed_selection},
        {"late successful reply after controller close", late_success},
        {"late unsuccessful craft after controller close", late_unsuccessful_craft},
        {"owned entry allowed", own_entry_allowed},
        {"other owner rejected", other_owner_rejected},
        {"host without owner rejected", hosted_without_owner_rejected},
        {"outgoing entry rejected", outgoing_entry_rejected},
        {"missing chance rejected", missing_chance_rejected},
        {"missing unique gift rejected", missing_unique_rejected},
        {"double entry", double_entry},
        {"double selection", double_selection},
        {"double confirmation gate", double_confirmation_gate},
        {"selection remains in originating account", account_routing},
        {"reply remains in originating account", reply_account_routing},
        {"validation errors preserve rejection", validation_errors_preserved},
        {"cooldown error preserves wait", wait_error_preserved},
        {"uncertain RPC error remains unresolved", uncertain_error_preserved},
        {"three and four ingredients reconciled", three_and_four_ingredients},
        {"owned picker does not request market", owned_picker_without_market},
        {"empty owned list opens picker", owned_picker_empty},
        {"missing owned reply opens nothing", owned_picker_no_reply},
        {"late owned list after controller closure", owned_picker_closed_controller},
        {"duplicate owned reply opens once", owned_picker_duplicate_reply},
        {"existing resale picker: craft first", resale_picker_craft_first},
        {"existing resale picker: market first", resale_picker_market_first},
        {"existing resale picker: empty market", resale_picker_empty_market},
    };
    if (argc == 2 && std::string(argv[1]) == "heap-lifetime-after-delete") {
        tests = {{"heap-lifetime-after-delete", heap_lifetime_after_delete}};
    } else if (argc == 2) {
        auto selected = decltype(tests)();
        for (const auto &test : tests) {
            if (std::string(argv[1]) == test.first) selected.push_back(test);
        }
        if (selected.empty()) {
            std::cerr << "Unknown scenario selector\n";
            return 2;
        }
        tests = std::move(selected);
    } else if (argc != 1) {
        std::cerr << "Unknown scenario selector\n";
        return 2;
    }
    auto failures = 0;
    for (const auto &[name, test] : tests) {
        try {
            test();
            std::cout << "PASS: " << name << '\n';
        } catch (const std::exception &error) {
            ++failures;
            std::cout << "FAIL: " << name << ": " << error.what() << '\n';
        }
    }
    std::cout << "SUMMARY: " << tests.size() - failures << '/' << tests.size()
        << " passed; UI, lifetime primitives and transport are test doubles.\n";
    return failures ? 1 : 0;
}
