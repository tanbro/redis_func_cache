local zset_key = KEYS[1]
local hmap_key = KEYS[2]

local maxsize = tonumber(ARGV[1])
local ttl = ARGV[2]
local hash = ARGV[3]
local return_value = ARGV[4]

if tonumber(ttl) > 0 then
    redis.call('EXPIRE', zset_key, ttl)
    redis.call('EXPIRE', hmap_key, ttl)
end

local c = 0
local rnk_with_score = redis.call('ZRANK', zset_key, hash, 'WITHSCORE')
if maxsize > 0 and not rnk_with_score then
    local n = redis.call('ZCARD', zset_key) - maxsize
    while n >= 0 do
        local popped = redis.call('ZPOPMIN', zset_key)
        redis.call('HDEL', hmap_key, popped[1])
        n = n - 1
        c = c + 1
    end
end

if not rnk_with_score then
    local time = redis.call('TIME')
    redis.call('ZADD', zset_key, time[1] + time[2] / 100000, hash)
    redis.call('HSET', hmap_key, hash, return_value)
end

return c
