--[[
  Random Replacement (RR) cache get operation.
  KEYS[1]: Redis set key for cache hashes
  KEYS[2]: Redis hash key for cache values
  ARGV[1]: update ttl flag (1 for update ttl, 0 for fixed ttl)
  ARGV[2]: TTL for both keys (number, seconds)
  ARGV[3]: hash key to retrieve
  Returns: value if found, otherwise nil. Cleans up stale entries.
  The structure TTL is only refreshed on a hit; misses clean up stale entries instead.
]]
local set_key = KEYS[1]
local hmap_key = KEYS[2]

local update_ttl_flag = ARGV[1]
local ttl = ARGV[2]
local hash = ARGV[3]

local is_member = (redis.call('SISMEMBER', set_key, hash) ~= 0)
local val = redis.call('HGET', hmap_key, hash)

-- Return value if both exist, else clean up stale set/hash
if is_member and val then
    -- Refresh TTL on hit only (sliding expiration)
    if tonumber(ttl) > 0 and update_ttl_flag == "1" then
        redis.call('EXPIRE', set_key, ttl)
        redis.call('EXPIRE', hmap_key, ttl)
    end
    return val
elseif is_member then
    redis.call('SREM', set_key, hash) -- remove stale set member
elseif val then
    redis.call('HDEL', hmap_key, hash) -- remove stale hash value
end

return nil
