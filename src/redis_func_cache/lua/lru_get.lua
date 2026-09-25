--[[
  LRU (Least Recently Used) cache get operation using zset order update.
  KEYS[1]: Redis sorted set key for cache hashes (score = order)
  KEYS[2]: Redis hash key for cache values
  ARGV[1]: update ttl flag (1 for update ttl, 0 for fixed ttl)
  ARGV[2]: TTL for both keys (number, seconds)
  ARGV[3]: hash key to retrieve
  Returns: value if found, otherwise nil. Updates order, cleans up stale entries.
  The structure TTL is only refreshed on a hit; misses clean up stale entries instead.
]]
local zset_key = KEYS[1]
local hmap_key = KEYS[2]

local update_ttl_flag = ARGV[1]
local ttl = ARGV[2]
local hash = ARGV[3]

local rnk = redis.call('ZRANK', zset_key, hash)
local val = redis.call('HGET', hmap_key, hash)

-- If found, update order; else clean up stale entries
if rnk and val then
    -- Refresh TTL on hit only (sliding expiration)
    if tonumber(ttl) > 0 and update_ttl_flag == "1" then
        redis.call('EXPIRE', zset_key, ttl)
        redis.call('EXPIRE', hmap_key, ttl)
    end

    -- Update LRU score (always update order regardless of update_ttl_flag)
    local highest_with_score = redis.call('ZRANGE', zset_key, -1, -1, 'WITHSCORES')
    if rawequal(next(highest_with_score), nil) then
        redis.call('ZADD', zset_key, 1, hash)
    else
        redis.call('ZADD', zset_key, 1 + highest_with_score[2], hash)
    end
    return val
elseif rnk then
    redis.call('ZREM', zset_key, hash) -- remove stale zset member
elseif val then
    redis.call('HDEL', hmap_key, hash) -- remove stale hash value
end

return nil
