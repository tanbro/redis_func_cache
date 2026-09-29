--[[
  GDSF (Greedy-Dual-Size) cache get operation.
  KEYS[1]: Redis sorted set key for cache hashes (score = freq * cost / size)
  KEYS[2]: Redis hash key for cache values; per-entry metadata field "<hash>:m" = "<freq> <cost>"
  ARGV[1]: update ttl flag (1 for update ttl, 0 for fixed ttl)
  ARGV[2]: TTL for both keys (number, seconds)
  ARGV[3]: hash key to retrieve
  Returns: value if found, otherwise nil. Re-scores the hit from its metadata
  (freq+1, size of the stored bytes), cleans up stale entries.
  The structure TTL is only refreshed on a hit; misses clean up stale entries.
]]
local zset_key = KEYS[1]
local hmap_key = KEYS[2]

local update_ttl_flag = ARGV[1]
local ttl = ARGV[2]
local hash = ARGV[3]

local rnk = redis.call('ZRANK', zset_key, hash)
local val = redis.call('HGET', hmap_key, hash)

if rnk and val then
    -- Refresh TTL on hit only (sliding expiration)
    if tonumber(ttl) > 0 and update_ttl_flag == "1" then
        redis.call('EXPIRE', zset_key, ttl)
        redis.call('EXPIRE', hmap_key, ttl)
    end

    -- Parse "<freq> <cost>"; missing or corrupt metadata restarts the entry
    local freq = 1
    local cost = 1
    local meta = redis.call('HGET', hmap_key, hash .. ':m')
    if meta then
        local sep = string.find(meta, ' ')
        if sep then
            freq = tonumber(string.sub(meta, 1, sep - 1)) or 1
            cost = tonumber(string.sub(meta, sep + 1)) or 1
        end
    end
    if cost <= 0 then
        cost = 1
    end

    freq = freq + 1
    local size = #val
    if size < 1 then
        size = 1
    end
    redis.call('ZADD', zset_key, freq * cost / size, hash)
    redis.call('HSET', hmap_key, hash .. ':m', freq .. ' ' .. cost)
    return val
elseif rnk then
    redis.call('ZREM', zset_key, hash) -- remove stale zset member
    redis.call('HDEL', hmap_key, hash .. ':m')
elseif val then
    redis.call('HDEL', hmap_key, hash, hash .. ':m') -- remove stale hash value
end

return nil
