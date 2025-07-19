
--[[
  Random Replacement (RR) cache put operation.
  KEYS[1]: Redis set key for cache hashes
  KEYS[2]: Redis hash key for cache values
  ARGV[1]: max cache size (number)
  ARGV[2]: TTL for both keys (number, seconds)
  ARGV[3]: hash key to store
  ARGV[4]: value to store
  Returns: number of evicted items
]]
local set_key = KEYS[1]
local hmap_key = KEYS[2]

local maxsize = tonumber(ARGV[1])
local ttl = ARGV[2]
local hash = ARGV[3]
local return_value = ARGV[4]
local field_ttl = ARGV[5]

-- Set TTL if specified
if tonumber(ttl) > 0 then
    redis.call('EXPIRE', set_key, ttl)
    redis.call('EXPIRE', hmap_key, ttl)
end

local c = 0
-- If hash not in set, insert and evict if needed
if redis.call('SISMEMBER', set_key, hash) == 0 then
    if maxsize > 0 then
        local n = redis.call('SCARD', set_key) - maxsize
        while n >= 0 do
            local popped = redis.call('SPOP', set_key) -- randomly evict one
            redis.call('HDEL', hmap_key, popped)
            n = n - 1
            c = c + 1
        end
    end
    redis.call('SADD', set_key, hash)
    redis.call('HSET', hmap_key, hash, return_value)
    -- Set Hash's Field TTL if specified
    if tonumber(field_ttl) > 0 then
        redis.call('HEXPIRE', hmap_key, field_ttl, 'FIELDS', 1, hash)
    end
end

return c
