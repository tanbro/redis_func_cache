local set_key = KEYS[1]
local hmap_key = KEYS[2]

local ttl = ARGV[1]
local hash = ARGV[2]

if tonumber(ttl) > 0 then
    redis.call('EXPIRE', set_key, ttl)
    redis.call('EXPIRE', hmap_key, ttl)
end

local is_member = redis.call('SISMEMBER', set_key, hash)
local val = redis.call('HGET', hmap_key, hash)

if is_member and val then
    return val
elseif is_member then
    redis.call('SREM', set_key, hash)
elseif val then
    redis.call('HDEL', hmap_key, hash)
end
