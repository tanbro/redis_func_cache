local zset_key = KEYS[1]
local hmap_key = KEYS[2]

local ttl = ARGV[1]
local hash = ARGV[2]

local rnk = redis.call('ZRANK', zset_key, hash)
local retval = redis.call('HGET', hmap_key, hash)

if rnk and retval then
    local time = redis.call('TIME')
    redis.call('ZADD', zset_key, time[1] + time[2] / 100000, hash)
elseif rnk then
    redis.call('ZREM', zset_key, hash)
    retval = nil
elseif retval then
    redis.call('HDEL', hmap_key, hash)
    retval = nil
end

if tonumber(ttl) > 0 then
    redis.call('EXPIRE', zset_key, ttl)
    redis.call('EXPIRE', hmap_key, ttl)
end

return retval
