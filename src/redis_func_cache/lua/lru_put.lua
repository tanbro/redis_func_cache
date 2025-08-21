--[[
  LRU (Least Recently Used) cache put operation using zset order.
  KEYS[1]: Redis sorted set key for cache hashes (score = order)
  KEYS[2]: Redis hash key for cache values
  ARGV[1]: max cache size (number)
  ARGV[2]: update ttl flag (1 for update ttl, 0 for fixed ttl)
  ARGV[3]: TTL for both keys (number, seconds)
  ARGV[4]: hash key to store
  ARGV[5]: value to store
  ARGV[6]: field ttl (number, seconds)
  ARGV[7]: (optional) 'mru' for MRU eviction
  Returns: number of evicted items
]]
local zset_key = KEYS[1]
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
    -- Check if this is a new item by checking if hash exists in zset
    local zrank_result = redis.call('ZRANK', zset_key, hash)
    if not zrank_result then
        -- This is a new item, we'll set initial TTL after inserting the item
        -- (Handled later in the code after item insertion)
    elseif update_ttl_flag == "1" then
        -- This is an existing item and update_ttl_flag is set
        redis.call('EXPIRE', zset_key, ttl)
        redis.call('EXPIRE', hmap_key, ttl)
    end
end

local is_mru = false
if #ARGV >= 7 then
    is_mru = (ARGV[7] == 'mru')
end

local c = 0

-- If hash not in zset, insert and evict if needed
if not redis.call('ZRANK', zset_key, hash) then
    if maxsize > 0 then
        local n = redis.call('ZCARD', zset_key) - maxsize
        while n >= 0 do
            local popped
            if is_mru then
                popped = redis.call('ZPOPMAX', zset_key) -- MRU eviction
            else
                popped = redis.call('ZPOPMIN', zset_key) -- LRU eviction
            end
            redis.call('HDEL', hmap_key, popped[1])
            n = n - 1
            c = c + 1
        end
    end
    -- Find highest score and increment for new entry
    local highest_with_score = redis.call('ZRANGE', zset_key, '+inf', '-inf', 'BYSCORE', 'REV', 'LIMIT', 0, 1,
        'WITHSCORES')
    if rawequal(next(highest_with_score), nil) then
        redis.call('ZADD', zset_key, 1, hash)
    else
        redis.call('ZADD', zset_key, 1 + highest_with_score[2], hash)
    end
    redis.call('HSET', hmap_key, hash, return_value)
    -- Set Hash's Field TTL if specified (always set for new fields)
    if tonumber(field_ttl) > 0 then
        redis.call('HEXPIRE', hmap_key, field_ttl, 'FIELDS', 1, hash)
    end

    -- Set initial TTL for new items
    if tonumber(ttl) > 0 then
        redis.call('EXPIRE', zset_key, ttl)
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
