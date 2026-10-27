// Fake reactive subscriptions and transport; production loading code is extracted.
namespace rpl {
class lifetime {
public:
    lifetime() = default;
    explicit lifetime(std::shared_ptr<bool> active) : _active(std::move(active)) {}
    lifetime(lifetime &&other) noexcept : _active(std::move(other._active)) {}
    lifetime &operator=(lifetime &&other) noexcept {
        destroy();
        _active = std::move(other._active);
        return *this;
    }
    ~lifetime() { destroy(); }
    void destroy() {
        if (_active) *_active = false;
        _active.reset();
    }

private:
    std::shared_ptr<bool> _active;

};
template <typename Callback> struct Listener { Callback callback; };
template <typename Callback> auto on_next(Callback callback) {
    return Listener<Callback>{std::move(callback)};
}
}
namespace Data {
struct CraftGiftsDescriptor { unsigned long long giftId = 0; };
struct ResaleGiftsDescriptor {
    unsigned long long giftId = 0;
    int count = 0;
};
}
struct PickerLoadFixture {
    int craftRequests = 0;
    int resaleRequests = 0;
    Session *session = nullptr;
    unsigned long long giftId = 0;
    Fn<void(Data::CraftGiftsDescriptor&&)> craft;
    Fn<void(Data::ResaleGiftsDescriptor&&)> resale;
};
PickerLoadFixture *loading = nullptr;
namespace Data {
struct CraftSource {};
struct ResaleSource {};
struct ResaleFilter { bool forCraft = false; };
CraftSource CraftGiftsSlice(Session *session, unsigned long long giftId) {
    ++loading->craftRequests;
    loading->session = session;
    loading->giftId = giftId;
    return {};
}
ResaleSource ResaleGiftsSlice(Session *, unsigned long long, ResaleFilter) {
    ++loading->resaleRequests;
    return {};
}
template <typename Callback>
rpl::lifetime operator|(CraftSource, rpl::Listener<Callback> listener) {
    auto active = std::make_shared<bool>(true);
    loading->craft = [weak = std::weak_ptr<bool>(active),
                      callback = std::move(listener.callback)](CraftGiftsDescriptor &&value) {
        const auto alive = weak.lock();
        if (alive && *alive) callback(std::move(value));
    };
    return rpl::lifetime(std::move(active));
}
template <typename Callback>
rpl::lifetime operator|(ResaleSource, rpl::Listener<Callback> listener) {
    auto active = std::make_shared<bool>(true);
    loading->resale = [weak = std::weak_ptr<bool>(active),
                       callback = std::move(listener.callback)](ResaleGiftsDescriptor &&value) {
        const auto alive = weak.lock();
        if (alive && *alive) callback(std::move(value));
    };
    return rpl::lifetime(std::move(active));
}
}
struct PickerLoadState {
    Data::CraftGiftsDescriptor craft;
    Data::ResaleGiftsDescriptor resale;
    rpl::lifetime craftLifetime;
    rpl::lifetime resaleLifetime;
};
Fn<void()> Box(Fn<void()> make) { return make; }
