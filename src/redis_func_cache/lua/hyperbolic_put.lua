--[[
  Hyperbolic (LFU with aging) cache put operation.
  KEYS[1]: Redis sorted set key for cache hashes (score = hyperbolic priority)
  KEYS[2]: Redis hash key for cache values; each entry also has a companion
           metadata field '<hash>:m' storing "<freq> <last_access_ms>"
  ARGV[1]: max cache size (number)
  ARGV[2]: update ttl flag (1 for update ttl, 0 for fixed ttl)
  ARGV[3]: TTL for both keys (number, seconds)
  ARGV[4]: hash key to store
  ARGV[5]: value to store
  ARGV[6]: field ttl (number, seconds)
  Returns: number of evicted items

  Score formula (Hyperbolic Caching, USENIX ATC 2020):
      priority = log(freq + 1) / (age_seconds + 1) ^ 0.25
  where age counts from the entry's LAST ACCESS (server TIME is
  authoritative): every access zeroes the age term, so a steadily hot entry's
  priority stays near log(freq + 1) while an untouched one decays. Between
  accesses a stored score can only over-estimate the true priority, so
  eviction must not trust the stored ordering: each eviction samples SAMPLE
  members, recomputes their true priorities from the metadata, and evicts the
  sampled minimum. Sampling is what lets stale hot entries age out — the LFU
  weakness this policy fixes.
]]
local zset_key = KEYS[1]
local hmap_key = KEYS[2]

local maxsize = tonumber(ARGV[1])
local update_ttl_flag = ARGV[2]
local ttl = ARGV[3]
local hash = ARGV[4]
local return_value = ARGV[5]
local field_ttl = ARGV[6]

local c = 0
-- Candidates inspected per eviction; each eviction event costs O(SAMPLE) hash lookups
local SAMPLE = 8
-- Sentinel for ghost members (value field missing): evict them before anything else
local GHOST = -1e308

local time = redis.call('TIME')
local now_ms = time[1] * 1000 + math.floor(time[2] / 1000)

-- Read the companion metadata field "<freq> <last_access_ms>"; missing or corrupt
-- metadata restarts the entry with the current clock as its last-access time
local function read_meta(field)
    local meta = redis.call('HGET', hmap_key, field)
    if meta then
        local sep = string.find(meta, ' ')
        if sep then
            local freq = tonumber(string.sub(meta, 1, sep - 1))
            local last_access_ms = tonumber(string.sub(meta, sep + 1))
            if freq and last_access_ms and last_access_ms > 0 then
                return freq, last_access_ms
            end
        end
    end
    return 1, now_ms
end

-- Hyperbolic priority; age floored at 0 so a server clock reset cannot
-- produce a negative base for the fractional power (NaN would corrupt the index)
local function priority(freq, last_access_ms)
    local age = (now_ms - last_access_ms) / 1000
    if age < 0 then
        age = 0
    end
    return math.log(freq + 1) / math.pow(age + 1, 0.25)
end

-- Check if zset and hash keys exist (multi-key EXISTS returns 0..2)
local both_exists = redis.call('EXISTS', zset_key, hmap_key)

-- If either zset or hash doesn't exist, clean up the other one (UNLINK is a no-op on missing keys)
if both_exists ~= 2 then
    redis.call('UNLINK', zset_key, hmap_key)
    both_exists = 0
end

-- If hash exists in zset, update the value and recompute the priority
if redis.call('ZRANK', zset_key, hash) then
    local freq = read_meta(hash .. ':m')
    freq = freq + 1
    -- Reset the clock: a put is an access (age counts from the last access)
    redis.call('ZADD', zset_key, priority(freq, now_ms), hash)
    redis.call('HSET', hmap_key, hash .. ':m', freq .. ' ' .. now_ms)
    redis.call('HSET', hmap_key, hash, return_value)

    -- Handle field TTL update (value and metadata fields age together)
    if tonumber(field_ttl) > 0 then
        redis.call('HEXPIRE', hmap_key, field_ttl, 'FIELDS', 2, hash, hash .. ':m')
    end

    -- Handle key TTL update (only update if update_ttl_flag is set)
    if tonumber(ttl) > 0 and update_ttl_flag == "1" then
        redis.call('EXPIRE', zset_key, ttl)
        redis.call('EXPIRE', hmap_key, ttl)
    end
else
    -- Hash does not exist in zset
    if maxsize > 0 then
        local n = redis.call('ZCARD', zset_key) - maxsize
        for _ = 0, n do
            -- Sample members, recompute their true priorities, evict the sampled minimum
            local victims = redis.call('ZRANDMEMBER', zset_key, SAMPLE)
            if #victims == 0 then
                break
            end
            local best = nil
            local best_p = math.huge
            for j = 1, #victims do
                local m = victims[j]
                local p
                if redis.call('HEXISTS', hmap_key, m) == 0 then
                    p = GHOST
                else
                    local freq, last_access_ms = read_meta(m .. ':m')
                    p = priority(freq, last_access_ms)
                end
                if p < best_p then
                    best_p = p
                    best = m
                end
            end
            if best then
                redis.call('ZREM', zset_key, best)
                c = c + redis.call('HDEL', hmap_key, best, best .. ':m')
            end
        end
    end
    redis.call('ZADD', zset_key, priority(1, now_ms), hash) -- initialize frequency to 1
    redis.call('HSET', hmap_key, hash, return_value)
    redis.call('HSET', hmap_key, hash .. ':m', '1 ' .. now_ms)

    -- Set Hash's Field TTL if specified (always set for new fields)
    if tonumber(field_ttl) > 0 then
        redis.call('HEXPIRE', hmap_key, field_ttl, 'FIELDS', 2, hash, hash .. ':m')
    end

    -- Set initial TTL for new keys (only when zset and hash keys are first created)
    if tonumber(ttl) > 0 and both_exists == 0 then
        redis.call('EXPIRE', zset_key, ttl)
        redis.call('EXPIRE', hmap_key, ttl)
    end
end

return c
