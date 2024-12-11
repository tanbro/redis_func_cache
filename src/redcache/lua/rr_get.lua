local set_key = KEYS[1]
local hmap_key = KEYS[2]

local ttl = ARGV[1]
local hash = ARGV[2]

local is_member = redis.call('SISMEMBER', set_key, hash)
local retval = nil
if is_member then
    retval = redis.call('HGET', hmap_key, hash)
end

if tonumber(ttl) > 0 then
    redis.call('EXPIRE', set_key, ttl)
    redis.call('EXPIRE', hmap_key, ttl)
end

return retval
