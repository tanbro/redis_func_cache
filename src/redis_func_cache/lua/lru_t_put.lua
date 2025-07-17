
--[[
  LRU (Least Recently Used) cache put operation with timestamp.
  KEYS[1]: Redis sorted set key for cache hashes (score = timestamp)
  KEYS[2]: Redis hash key for cache values
  ARGV[1]: max cache size (number)
  ARGV[2]: TTL for both keys (number, seconds)
  ARGV[3]: hash key to store
  ARGV[4]: value to store
  ARGV[5]: (optional) 'mru' for MRU eviction
  Returns: number of evicted items
]]
local zset_key = KEYS[1]
local hmap_key = KEYS[2]

local maxsize = tonumber(ARGV[1])
local ttl = ARGV[2]
local hash = ARGV[3]
local return_value = ARGV[4]

-- Set TTL if specified
if tonumber(ttl) > 0 then
    redis.call('EXPIRE', zset_key, ttl)
    redis.call('EXPIRE', hmap_key, ttl)
end

local is_mru = false
if #ARGV > 4 then
    is_mru = (ARGV[5] == 'mru')
end

local c = 0
-- If hash not in zset, insert and evict if needed
if not redis.call('ZRANK', zset_key, hash) then
    if maxsize > 0 then
        local n = redis.call('ZCARD', zset_key) - maxsize
        while n >= 0 do
            local popped
            if is_mru then
                popped = redis.call('ZPOPMAX', zset_key) -- MRU eviction
            else
                popped = redis.call('ZPOPMIN', zset_key) -- LRU eviction
            end
            redis.call('HDEL', hmap_key, popped[1])
            n = n - 1
            c = c + 1
        end
    end

    local time = redis.call('TIME')
    redis.call('ZADD', zset_key, time[1] + time[2] * 1e-6, hash) -- use current time as score
    redis.call('HSET', hmap_key, hash, return_value)
end

return c
