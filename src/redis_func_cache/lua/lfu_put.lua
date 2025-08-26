--[[
  LFU (Least Frequently Used) cache put operation.
  KEYS[1]: Redis sorted set key for cache hashes (score = frequency)
  KEYS[2]: Redis hash key for cache values
  ARGV[1]: max cache size (number)
  ARGV[2]: update ttl flag (1 for update ttl, 0 for fixed ttl)
  ARGV[3]: TTL for both keys (number, seconds)
  ARGV[4]: hash key to store
  ARGV[5]: value to store
  ARGV[6]: field ttl (number, seconds)
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

local c = 0

-- Check if zset and hash keys exist
local zset_exists = redis.call('EXISTS', zset_key)
local hmap_exists = redis.call('EXISTS', hmap_key)

-- If either zset or hash doesn't exist, clean up the other one
if zset_exists == 0 or hmap_exists == 0 then
    if zset_exists == 1 then
        redis.call('UNLINK', zset_key)
    end
    if hmap_exists == 1 then
        redis.call('UNLINK', hmap_key)
    end
    -- Reset existence flags since we just deleted them
    zset_exists = 0
    hmap_exists = 0
end

-- If hash exists in zset, update the value
if redis.call('ZRANK', zset_key, hash) then
    redis.call('HSET', hmap_key, hash, return_value)

    -- Handle field TTL update
    if tonumber(field_ttl) > 0 then
        redis.call('HEXPIRE', hmap_key, field_ttl, 'FIELDS', 1, hash)
    end

    -- Handle key TTL update (only update if update_ttl_flag is set)
    if tonumber(ttl) > 0 and update_ttl_flag == "1" then
        redis.call('EXPIRE', zset_key, ttl)
        redis.call('EXPIRE', hmap_key, ttl)
    end
else
    -- Hash does not exist in zset
    if maxsize > 0 then
        local n = redis.call('ZCARD', zset_key) - maxsize
        if n >= 0 then
            -- Use batch ZPOPMIN instead of looping calls
            local popped_keys_data = redis.call('ZPOPMIN', zset_key, n + 1) -- evict least frequently used

            -- Extract keys from returned data (ZPOPMIN returns [key,score,key,score,...] format)
            local popped_keys = {}
            for i = 1, #popped_keys_data, 2 do
                table.insert(popped_keys, popped_keys_data[i])
            end

            if #popped_keys > 0 then
                redis.call('HDEL', hmap_key, unpack(popped_keys))
                c = #popped_keys
            end
        end
    end
    redis.call('ZADD', zset_key, 1, hash) -- initialize frequency to 1
    redis.call('HSET', hmap_key, hash, return_value)

    -- Set Hash's Field TTL if specified (always set for new fields)
    if tonumber(field_ttl) > 0 then
        redis.call('HEXPIRE', hmap_key, field_ttl, 'FIELDS', 1, hash)
    end

    -- Set initial TTL for new keys (only when zset or hash keys are first created)
    if tonumber(ttl) > 0 and (zset_exists == 0 or hmap_exists == 0) then
        if zset_exists == 0 then
            redis.call('EXPIRE', zset_key, ttl)
        end
        if hmap_exists == 0 then
            redis.call('EXPIRE', hmap_key, ttl)
        end
    end
end

return c
