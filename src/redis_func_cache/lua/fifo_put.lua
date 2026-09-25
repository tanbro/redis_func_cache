--[[
  FIFO (First-In-First-Out) cache put operation using zset order.
  KEYS[1]: Redis sorted set key for cache hashes (score = order)
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
-- Max members per HDEL chunk: Lua unpack() overflows above ~8000 values
local UNPACK_CHUNK = 4000

-- Check if zset and hash keys exist (multi-key EXISTS returns 0..2)
local both_exists = redis.call('EXISTS', zset_key, hmap_key)

-- If either zset or hash doesn't exist, clean up the other one (UNLINK is a no-op on missing keys)
if both_exists ~= 2 then
    redis.call('UNLINK', zset_key, hmap_key)
    both_exists = 0
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
            local evicted_keys_data = redis.call('ZPOPMIN', zset_key, n + 1) -- evict oldest

            -- Extract keys from returned data (ZPOPMIN returns [key,score,key,score,...] format)
            if #evicted_keys_data > 0 then
                local keys_only = {}
                for i = 1, #evicted_keys_data, 2 do
                    keys_only[#keys_only + 1] = evicted_keys_data[i]
                end
                -- Chunked HDEL: unpack has a stack limit
                for i = 1, #keys_only, UNPACK_CHUNK do
                    c = c + redis.call('HDEL', hmap_key, unpack(keys_only, i, math.min(i + UNPACK_CHUNK - 1, #keys_only)))
                end
            end
        end
    end

    -- Find highest score and increment for new entry
    local highest_with_score = redis.call('ZRANGE', zset_key, -1, -1, 'WITHSCORES')
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

    -- Set initial TTL for new keys (only when zset and hash keys are first created)
    if tonumber(ttl) > 0 and both_exists == 0 then
        redis.call('EXPIRE', zset_key, ttl)
        redis.call('EXPIRE', hmap_key, ttl)
    end
end

return c
