local set_key = KEYS[1]
local hmap_key = KEYS[2]

local maxsize = tonumber(ARGV[1])
local ttl = ARGV[2]
local hash = ARGV[3]
local return_value = ARGV[4]

if tonumber(ttl) > 0 then
    redis.call('EXPIRE', set_key, ttl)
    redis.call('EXPIRE', hmap_key, ttl)
end

local is_member = (redis.call('SISMEMBER', set_key, hash) ~= 0)
local c = 0
if maxsize > 0 and not is_member then
    local n = redis.call('SCARD', set_key) - maxsize
    while n >= 0 do
        local popped = redis.call('SPOP', set_key)
        redis.call('HDEL', hmap_key, popped)
        n = n - 1
        c = c + 1
    end
end

redis.call('SADD', set_key, hash)
redis.call('HSET', hmap_key, hash, return_value)

return c
