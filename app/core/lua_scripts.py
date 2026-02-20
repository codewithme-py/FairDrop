RATE_LIMIT_LUA_SCRIPT = """
local user_key = KEYS[1]
local item_key = KEYS[2]

local user_limit = tonumber(ARGV[1])
local item_limit = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])

local current_user_count = tonumber(redis.call('get', user_key) or '0')
local current_item_count = tonumber(redis.call('get', item_key) or '0')

if current_user_count >= user_limit then return 0 end
if current_item_count >= item_limit then return -1 end

redis.call('incr', user_key)
redis.call('incr', item_key)

if current_user_count == 0 then
    redis.call('expire', user_key, ttl)
end

if current_item_count == 0 then
    redis.call('expire', item_key, ttl)
end

return 1
"""
