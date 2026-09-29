--[[
  Hyperbolic (LFU with aging) cache get operation.
  KEYS[1]: Redis sorted set key for cache hashes (score = hyperbolic priority)
  KEYS[2]: Redis hash key for cache values; each entry also has a companion
           metadata field '<hash>:m' storing "<freq> <insert_time_ms>"
  ARGV[1]: update ttl flag (1 for update ttl, 0 for fixed ttl)
  ARGV[2]: TTL for both keys (number, seconds)
  ARGV[3]: hash key to retrieve
  Returns: value if found, otherwise nil. Recomputes the hyperbolic priority
  score = log(freq + 1) / (age_seconds + 1) ^ 0.25 on every hit (server TIME is
  authoritative), and cleans up stale entries on a miss. The structure TTL is
  only refreshed on a hit.
]]
local zset_key = KEYS[1]
local hmap_key = KEYS[2]

local update_ttl_flag = ARGV[1]
local ttl = ARGV[2]
local hash = ARGV[3]

local rnk = redis.call('ZRANK', zset_key, hash)
local val = redis.call('HGET', hmap_key, hash)

-- If found, recompute the priority; else clean up stale entries
if rnk and val then
    -- Refresh TTL on hit only (sliding expiration)
    if tonumber(ttl) > 0 and update_ttl_flag == "1" then
        redis.call('EXPIRE', zset_key, ttl)
        redis.call('EXPIRE', hmap_key, ttl)
    end

    -- Parse "<freq> <insert_ms>"; missing or corrupt metadata restarts the entry
    local meta = redis.call('HGET', hmap_key, hash .. ':m')
    local freq = 1
    local insert_ms = 0
    if meta then
        local sep = string.find(meta, ' ')
        if sep then
            freq = tonumber(string.sub(meta, 1, sep - 1)) or 1
            insert_ms = tonumber(string.sub(meta, sep + 1)) or 0
        end
    end

    local time = redis.call('TIME')
    local now_ms = time[1] * 1000 + math.floor(time[2] / 1000)
    if insert_ms <= 0 then
        insert_ms = now_ms
    end

    -- Age floored at 0: a server clock reset must not produce a negative
    -- base for the fractional power (NaN scores would corrupt the index)
    local age = (now_ms - insert_ms) / 1000
    if age < 0 then
        age = 0
    end

    freq = freq + 1
    local score = math.log(freq + 1) / math.pow(age + 1, 0.25)
    redis.call('ZADD', zset_key, score, hash)
    redis.call('HSET', hmap_key, hash .. ':m', freq .. ' ' .. insert_ms)
    return val
elseif rnk then
    redis.call('ZREM', zset_key, hash) -- remove stale zset member
    redis.call('HDEL', hmap_key, hash .. ':m')
elseif val then
    redis.call('HDEL', hmap_key, hash) -- remove stale hash value
    redis.call('HDEL', hmap_key, hash .. ':m')
end

return nil
