--[[
  Vacuum: remove ZSET members whose hash fields have expired ('ghost' entries).
  KEYS[1]: Redis sorted set key for cache hashes
  KEYS[2]: Redis hash key for cache values
  ARGV[1]: cursor from the previous call ('0' to start a new scan)
  ARGV[2]: scan COUNT hint (max members probed per call)
  Returns: {next_cursor, number of ghost members removed}

  One call performs a single ZSCAN step, the HEXISTS probes and the ZREM
  atomically, so neither the scan nor the probe-then-remove pair can interleave
  with concurrent writes. Each call touches at most COUNT members and then
  yields, keeping the Redis server responsive.
]]
local zset_key = KEYS[1]
local hmap_key = KEYS[2]

local cursor = ARGV[1]
local count = tonumber(ARGV[2])

local scan = redis.call('ZSCAN', zset_key, cursor, 'COUNT', count)
cursor = scan[1]
local members = scan[2]

local ghosts = {}
for i = 1, #members, 2 do
    if redis.call('HEXISTS', hmap_key, members[i]) == 0 then
        ghosts[#ghosts + 1] = members[i]
    end
end

local removed = 0
if #ghosts > 0 then
    removed = redis.call('ZREM', zset_key, unpack(ghosts))
end

return {cursor, removed}
