--[[
  LRU (Least Recently Used) cache get operation with timestamp update.
  KEYS[1]: Redis sorted set key for cache hashes (score = timestamp)
  KEYS[2]: Redis hash key for cache values
  ARGV[1]: update ttl flag (1 for update ttl, 0 for fixed ttl)
  ARGV[2]: TTL for both keys (number, seconds)
  ARGV[3]: hash key to retrieve
  Returns: value if found, otherwise nil. Updates access time, cleans up stale entries.
]]
local zset_key = KEYS[1]
local hmap_key = KEYS[2]

local update_ttl_flag = ARGV[1]
local ttl = ARGV[2]
local hash = ARGV[3]

-- Set TTL if specified and update_ttl_flag is set
if tonumber(ttl) > 0 and update_ttl_flag == "1" then
    redis.call('EXPIRE', zset_key, ttl)
    redis.call('EXPIRE', hmap_key, ttl)
end

local rnk = redis.call('ZRANK', zset_key, hash)
local val = redis.call('HGET', hmap_key, hash)

-- If found, update timestamp; else clean up stale entries
if rnk and val then
    -- Only update timestamp if update_ttl_flag is set
    if update_ttl_flag == "1" then
        local time = redis.call('TIME')
        redis.call('ZADD', zset_key, time[1] + time[2] * 1e-6, hash)
    end
    return val
elseif rnk then
    redis.call('ZREM', zset_key, hash) -- remove stale zset member
elseif val then
    redis.call('HDEL', hmap_key, hash) -- remove stale hash value
end

return nil
