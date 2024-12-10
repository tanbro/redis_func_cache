local zset_key = KEYS[1]
local hmap_key = KEYS[2]

local maxsize = tonumber(ARGV[1])
local ttl = ARGV[2]
local hash = ARGV[3]
local retval = ARGV[4]

if maxsize > 0 then
    local n = redis.call('ZCARD', zset_key) - maxsize
    while n > 0 do
        local popped = redis.call('ZPOPMIN', zset_key, 1)
        n = n - 1
        redis.call('HDEL', hmap_key, popped[1])
    end
end

redis.call('ZADD', zset_key, 0, hash)
redis.call('HSET', hmap_key, hash, retval)

redis.call('EXPIRE', zset_key, ttl)
redis.call('EXPIRE', hmap_key, ttl)
