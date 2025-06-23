local zset_key = KEYS[1]
local hmap_key = KEYS[2]

local ttl = ARGV[1]
local hash = ARGV[2]

if tonumber(ttl) > 0 then
    redis.call('EXPIRE', zset_key, ttl)
    redis.call('EXPIRE', hmap_key, ttl)
end

local rnk = redis.call('ZRANK', zset_key, hash)
local val = redis.call('HGET', hmap_key, hash)

if rnk and val then
    local time = redis.call('TIME')
    redis.call('ZADD', zset_key, time[1] + time[2] / 1e-6, hash)
    return val
elseif rnk then
    redis.call('ZREM', zset_key, hash)
elseif val then
    redis.call('HDEL', hmap_key, hash)
end
