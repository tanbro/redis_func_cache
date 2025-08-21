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

-- Set TTL if specified
-- For new items, always set initial TTL; for existing items, only update if update_ttl_flag is set
if tonumber(ttl) > 0 then
    -- Check if this is a new item by checking if hash exists in set
    local is_member = redis.call('SISMEMBER', set_key, hash)
    if is_member == 0 then
        -- This is a new item, we'll set initial TTL after inserting the item
        -- (Handled later in the code after item insertion)
    elseif update_ttl_flag == "1" then
        -- This is an existing item and update_ttl_flag is set
        redis.call('EXPIRE', set_key, ttl)
        redis.call('EXPIRE', hmap_key, ttl)
    end
end

local c = 0

-- If hash not in set, insert and evict if needed
if redis.call('SISMEMBER', set_key, hash) == 0 then
    if maxsize > 0 then
        local n = redis.call('SCARD', set_key) - maxsize
        while n >= 0 do
            local popped = redis.call('SPOP', set_key) -- evict random member
            redis.call('HDEL', hmap_key, popped)
            n = n - 1
            c = c + 1
        end
    end
    redis.call('SADD', set_key, hash)
    redis.call('HSET', hmap_key, hash, return_value)
    -- Set Hash's Field TTL if specified (always set for new fields)
    if tonumber(field_ttl) > 0 then
        redis.call('HEXPIRE', hmap_key, field_ttl, 'FIELDS', 1, hash)
    end

    -- Set initial TTL for new items
    if tonumber(ttl) > 0 then
        redis.call('EXPIRE', set_key, ttl)
        redis.call('EXPIRE', hmap_key, ttl)
    end
else
    -- Hash exists, update the value
    redis.call('HSET', hmap_key, hash, return_value)

    -- Handle field TTL update based on update_ttl_flag
    if tonumber(field_ttl) > 0 and update_ttl_flag == "1" then
        redis.call('HEXPIRE', hmap_key, field_ttl, 'FIELDS', 1, hash)
    end
end

return c
