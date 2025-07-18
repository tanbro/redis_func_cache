
--[[
  LFU (Least Frequently Used) cache put operation.
  KEYS[1]: Redis sorted set key for cache hashes (score = frequency)
  KEYS[2]: Redis hash key for cache values
  ARGV[1]: max cache size (number)
  ARGV[2]: TTL for both keys (number, seconds)
  ARGV[3]: hash key to store
  ARGV[4]: value to store
  Returns: number of evicted items
]]
local zset_key = KEYS[1]
local hmap_key = KEYS[2]

local maxsize = tonumber(ARGV[1])
local ttl = ARGV[2]
local hash = ARGV[3]
local return_value = ARGV[4]
local field_ttl = ARGV[5]

-- Set TTL if specified
if tonumber(ttl) > 0 then
    redis.call('EXPIRE', zset_key, ttl)
    redis.call('EXPIRE', hmap_key, ttl)
end

local c = 0
-- If hash not in zset, insert and evict if needed
if not redis.call('ZRANK', zset_key, hash) then
    if maxsize > 0 then
        local n = redis.call('ZCARD', zset_key) - maxsize
        while n >= 0 do
            local popped = redis.call('ZPOPMIN', zset_key) -- evict least frequently used
            redis.call('HDEL', hmap_key, popped[1])
            n = n - 1
            c = c + 1
        end
    end
    redis.call('ZINCRBY', zset_key, 1, hash) -- increment frequency
    redis.call('HSET', hmap_key, hash, return_value)
    -- Set Hash's Field TTL if specified
    if tonumber(field_ttl) > 0 then
        redis.call('HEXPIRE', hmap_key, ttl, FIELDS "1", hash)
    end
end

return c
