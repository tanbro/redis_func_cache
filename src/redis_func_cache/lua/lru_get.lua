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
    local highest_with_score = redis.call('ZRANGE', zset_key, '+inf', '-inf', 'BYSCORE', 'REV', 'LIMIT', 0, 1,
        'WITHSCORES')
    if not rawequal(next(highest_with_score), nil) then
        if hash ~= highest_with_score[1] then
            redis.call('ZADD', zset_key, 1 + highest_with_score[2], hash)
        end
    else
        redis.call('ZADD', zset_key, 1, hash)
    end
    return val
elseif rnk then
    redis.call('ZREM', zset_key, hash)
elseif val then
    redis.call('HDEL', hmap_key, hash)
end
