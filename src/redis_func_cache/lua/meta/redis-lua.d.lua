---@meta _
-- Redis embedded Lua 5.1 sandbox API
-- Ref: https://redis.io/docs/latest/develop/programmability/lua-api/

---@class RedisSandbox
---@field call? fun(cmd: string, ...: any): any
---@field pcall? fun(cmd: string, ...: any): any
---@field error_reply? fun(msg: string): {["error"]: string}
---@field status_reply? fun(msg: string): {["ok"]: string}
---@field breakpoint? fun(): nil
---@field setresp? fun(enable: boolean): nil
---@field register_function? fun(def: RedisFuncDef): nil

---@class RedisFuncDef
---@field function_name string
---@field callback fun(keys: string[], argv: any[]): any

---@class CJson
---@field encode? fun(value: any): string
---@field decode? fun(str: string): any

---@class CMsgPack
---@field pack? fun(value: any): string
---@field unpack? fun(str: string): any

---@type RedisSandbox
redis = {}

---@type CJson
cjson = {}

---@type CMsgPack
cmsgpack = {}

---@type string
REDIS_VERSION = ""
---@type integer
REDIS_VERSION_NUM = 0

-- EVAL script global variables
-- Note: Redis Function callbacks DO NOT have KEYS / ARGV as global
---@type string[]
KEYS = {}
---@type any[]
ARGV = {}
