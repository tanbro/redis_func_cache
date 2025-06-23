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

local is_mru = false
if #ARGV > 5 then
    is_mru = (ARGV[6] == 'mru')
end

local c = 0
local rnk = redis.call('ZRANK', zset_key, hash)
if maxsize > 0 and not rnk then
    local n = redis.call('ZCARD', zset_key) - maxsize
    while n >= 0 do
        local popped
        if is_mru then
            popped = redis.call('ZPOPMAX', zset_key)
        else
            popped = redis.call('ZPOPMIN', zset_key)
        end
        redis.call('HDEL', hmap_key, popped[1])
        n = n - 1
        c = c + 1
    end
end

local highest_with_score = redis.call('ZRANGE', zset_key, '+inf', '-inf', 'BYSCORE', 'REV', 'LIMIT', 0, 1, 'WITHSCORES')
if rawequal(next(highest_with_score), nil) then
    redis.call('ZADD', zset_key, 1, hash)
else
    if rnk then
        if hash ~= highest_with_score[1] then
            redis.call('ZADD', zset_key, 1 + highest_with_score[2], hash)
        end
    else
        redis.call('ZADD', zset_key, 1 + highest_with_score[2], hash)
    end
end

redis.call('HSET', hmap_key, hash, return_value)

return c
