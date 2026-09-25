--[[
  Vacuum: remove index members whose hash fields have expired ('ghost' entries).
  KEYS[1]: Redis sorted set key (zset policies) or set key (RR policy) for cache hashes
  KEYS[2]: Redis hash key for cache values
  ARGV[1]: cursor from the previous call ('0' to start a new scan)
  ARGV[2]: scan COUNT hint (max members probed per call)
  Returns: {next_cursor, number of ghost members removed}

  One call performs a single scan step (ZSCAN for zset, SSCAN for set), the HEXISTS
  probes and the removal atomically, so neither the scan nor the probe-then-remove
  pair can interleave with concurrent writes. Each call touches at most COUNT
  members and then yields, keeping the Redis server responsive.
]]
local index_key = KEYS[1]
local hmap_key = KEYS[2]

local cursor = ARGV[1]
local count = tonumber(ARGV[2])

local index_type = redis.call('TYPE', index_key)
-- Older Redis returns the type as a plain string, newer ones as a {ok=...} status table
if type(index_type) ~= 'string' then
    index_type = index_type.ok
end
if index_type == 'none' then
    return {cursor, 0}
end

local is_set = (index_type == 'set')

local scan
if is_set then
    scan = redis.call('SSCAN', index_key, cursor, 'COUNT', count)
else
    scan = redis.call('ZSCAN', index_key, cursor, 'COUNT', count)
end
cursor = scan[1]
local raw = scan[2]

-- ZSCAN yields member/score pairs (step 2); SSCAN yields a flat member list (step 1)
local step = is_set and 1 or 2
local ghosts = {}
for i = 1, #raw, step do
    if redis.call('HEXISTS', hmap_key, raw[i]) == 0 then
        ghosts[#ghosts + 1] = raw[i]
    end
end

local removed = 0
if #ghosts > 0 then
    -- Chunked unpack: it overflows above ~8000 values
    local UNPACK_CHUNK = 4000
    for i = 1, #ghosts, UNPACK_CHUNK do
        if is_set then
            removed = removed + redis.call('SREM', index_key, unpack(ghosts, i, math.min(i + UNPACK_CHUNK - 1, #ghosts)))
        else
            removed = removed + redis.call('ZREM', index_key, unpack(ghosts, i, math.min(i + UNPACK_CHUNK - 1, #ghosts)))
        end
    end
end

return {cursor, removed}
