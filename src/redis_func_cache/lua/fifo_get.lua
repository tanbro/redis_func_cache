
--[[
  FIFO (First-In-First-Out) cache get operation using zset order.
  KEYS[1]: Redis sorted set key for cache hashes (score = order)
  KEYS[2]: Redis hash key for cache values
  ARGV[1]: TTL for both keys (number, seconds)
  ARGV[2]: hash key to retrieve
  Returns: value if found, otherwise nil. Cleans up stale entries.
]]
local zset_key = KEYS[1]
local hmap_key = KEYS[2]

local ttl = ARGV[1]
local hash = ARGV[2]

-- Set TTL if specified
if tonumber(ttl) > 0 then
    redis.call('EXPIRE', zset_key, ttl)
    redis.call('EXPIRE', hmap_key, ttl)
end

local rnk = redis.call('ZRANK', zset_key, hash)
local val = redis.call('HGET', hmap_key, hash)

-- If found, return value; else clean up stale entries
if rnk and val then
    return val
elseif rnk then
    redis.call('ZREM', zset_key, hash) -- remove stale zset member
elseif val then
    redis.call('HDEL', hmap_key, hash) -- remove stale hash value
end
