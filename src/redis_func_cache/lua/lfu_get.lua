--[[
  LFU (Least Frequently Used) cache get operation.
  KEYS[1]: Redis sorted set key for cache hashes (score = frequency)
  KEYS[2]: Redis hash key for cache values
  ARGV[1]: update ttl flag (1 for update ttl, 0 for fixed ttl)
  ARGV[2]: TTL for both keys (number, seconds)
  ARGV[3]: hash key to retrieve
  Returns: value if found, otherwise nil. Increments frequency, cleans up stale entries.
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

-- If found, increment frequency; else clean up stale entries
if rnk and val then
    -- Only increment frequency if update_ttl_flag is set
    if update_ttl_flag == "1" then
        redis.call('ZINCRBY', zset_key, 1, hash)
    end
    return val
elseif rnk then
    redis.call('ZREM', zset_key, hash) -- remove stale zset member
elseif val then
    redis.call('HDEL', hmap_key, hash) -- remove stale hash value
end

return nil
