#pragma once

#include <vector>
#include <string>
#include <mutex>
#include <shared_mutex>
#include <optional>
#include <functional>
#include <unordered_map>

// hash map split into N locked stripes instead of one global lock.
// keys hashing to different stripes don't block each other.
// STRIPE_PAD controls whether each stripe is padded to a cache line --
// toggle this and rerun benchmark.py to see the false sharing effect.

#define STRIPE_PAD

class StripedHashMap {
public:
    explicit StripedHashMap(size_t num_stripes = 64)
        : stripes_(num_stripes) {}

    void set(const std::string& key, const std::string& value) {
        Stripe& s = stripe_for(key);
        std::unique_lock lock(s.mutex);
        s.data[key] = value;
    }

    std::optional<std::string> get(const std::string& key) {
        Stripe& s = stripe_for(key);
        std::shared_lock lock(s.mutex);  // readers don't block readers
        auto it = s.data.find(key);
        if (it == s.data.end()) return std::nullopt;
        return it->second;
    }

    bool remove(const std::string& key) {
        Stripe& s = stripe_for(key);
        std::unique_lock lock(s.mutex);
        return s.data.erase(key) > 0;
    }

    size_t size() {
        size_t total = 0;
        for (auto& s : stripes_) {
            std::shared_lock lock(s.mutex);
            total += s.data.size();
        }
        return total;
    }

private:
#ifdef STRIPE_PAD
    // padded to 64 bytes so adjacent stripes don't share a cache line.
    // without this, locking stripe[3] can bounce stripe[4]'s cache line
    // even though nothing actually touched stripe[4] -- false sharing.
    struct alignas(64) Stripe {
        std::shared_mutex mutex;
        std::unordered_map<std::string, std::string> data;
    };
#else
    struct Stripe {
        std::shared_mutex mutex;
        std::unordered_map<std::string, std::string> data;
    };
#endif

    Stripe& stripe_for(const std::string& key) {
        size_t h = std::hash<std::string>{}(key);
        return stripes_[h % stripes_.size()];
    }

    std::vector<Stripe> stripes_;
};
