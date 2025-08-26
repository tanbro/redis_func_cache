--[[
  Random Replacement (RR) cache put operation.
  KEYS[1]: Redis set key for cache hashes
  KEYS[2]: Redis hash key for cache values
  ARGV[1]: max cache size (number)
  ARGV[2]: update ttl flag (1 for update ttl, 0 for fixed ttl)
  ARGV[3]: TTL for both keys (number, seconds)
  ARGV[4]: hash key to store
  ARGV[5]: value to store
  ARGV[6]: field ttl (number, seconds)
  Returns: number of evicted items
]]
local set_key = KEYS[1]
local hmap_key = KEYS[2]

local maxsize = tonumber(ARGV[1])
local update_ttl_flag = ARGV[2]
local ttl = ARGV[3]
local hash = ARGV[4]
local return_value = ARGV[5]
local field_ttl = ARGV[6]

local c = 0

-- Check if set and hash keys exist
local set_exists = redis.call('EXISTS', set_key)
local hmap_exists = redis.call('EXISTS', hmap_key)

-- If either set or hash doesn't exist, clean up the other one
if set_exists == 0 or hmap_exists == 0 then
    if set_exists == 1 then
        redis.call('UNLINK', set_key)
    end
    if hmap_exists == 1 then
        redis.call('UNLINK', hmap_key)
    end
    -- Reset existence flags since we just deleted them
    set_exists = 0
    hmap_exists = 0
end

-- If hash exists in set, update the value
if redis.call('SISMEMBER', set_key, hash) == 1 then
    redis.call('HSET', hmap_key, hash, return_value)

    -- Handle field TTL update
    if tonumber(field_ttl) > 0 then
        redis.call('HEXPIRE', hmap_key, field_ttl, 'FIELDS', 1, hash)
    end

    -- Handle key TTL update (only update if update_ttl_flag is set)
    if tonumber(ttl) > 0 and update_ttl_flag == "1" then
        redis.call('EXPIRE', set_key, ttl)
        redis.call('EXPIRE', hmap_key, ttl)
    end
else
    -- Hash does not exist in set
    if maxsize > 0 then
        local n = redis.call('SCARD', set_key) - maxsize
        if n >= 0 then
            -- SPOP: Removes and returns one or more random members from the set value store at key
            local popped_keys = redis.call('SPOP', set_key, n + 1) -- evict random members

            if type(popped_keys) == "string" then
                -- What returned by SPOP is a string when only one element is popped
                redis.call('HDEL', hmap_key, popped_keys)
                c = 1
            elseif type(popped_keys) == "table" and #popped_keys > 0 then
                -- what returned by SPOP is a table when multiple elements are popped
                redis.call('HDEL', hmap_key, unpack(popped_keys))
                c = #popped_keys
            end
        end
    end
    redis.call('SADD', set_key, hash)
    redis.call('HSET', hmap_key, hash, return_value)

    -- Set Hash's Field TTL if specified (always set for new fields)
    if tonumber(field_ttl) > 0 then
        redis.call('HEXPIRE', hmap_key, field_ttl, 'FIELDS', 1, hash)
    end

    -- Set initial TTL for new keys (only when set or hash keys are first created)
    if tonumber(ttl) > 0 and (set_exists == 0 or hmap_exists == 0) then
        if set_exists == 0 then
            redis.call('EXPIRE', set_key, ttl)
        end
        if hmap_exists == 0 then
            redis.call('EXPIRE', hmap_key, ttl)
        end
    end
end

return c
