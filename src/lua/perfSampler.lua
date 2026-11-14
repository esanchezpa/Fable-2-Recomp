-- Opt-in QA-only Lua sampler. It is inert unless explicitly started.
-- Sampling is deliberately limited to a bounded in-memory ring and a low
-- frame cadence. Do not add I/O, cprint, UI, or screenshot work to sample().

local MAX_CAPACITY = 4096
local DEFAULT_CAPACITY = 512
local SAMPLE_EVERY_FRAMES = 30
local DEFAULT_WINDOW_FRAMES = 10800 -- 180 seconds at 60 guest frames/second.
local MAX_WINDOW_FRAMES = 21600
local DEFAULT_ARM_DELAY_FRAMES = 300 -- allow console UI/output to settle before sampling.
local ring_methods = {}

local function new_ring(capacity)
  if type(capacity) ~= "number" or capacity < 1 or capacity > MAX_CAPACITY
      or capacity ~= math.floor(capacity) then
    return nil
  end
  return setmetatable({
    capacity = capacity, count_value = 0, next_index = 1, values = {},
    overwritten_value = 0,
  }, { __index = ring_methods })
end

local function push(ring, value)
  if ring.count_value == ring.capacity then
    ring.overwritten_value = ring.overwritten_value + 1
  end
  ring.values[ring.next_index] = value
  ring.next_index = ring.next_index % ring.capacity + 1
  if ring.count_value < ring.capacity then
    ring.count_value = ring.count_value + 1
  end
end

local function ordered(ring)
  local result = {}
  local first = ring.count_value == ring.capacity and ring.next_index or 1
  for i = 1, ring.count_value do
    local index = (first + i - 2) % ring.capacity + 1
    result[i] = ring.values[index]
  end
  return result
end

function ring_methods:push(value)
  push(self, value)
end

function ring_methods:count()
  return self.count_value
end

function ring_methods:overwritten()
  return self.overwritten_value
end

function ring_methods:ordered()
  return ordered(self)
end

local state = rawget(_G, "__f2_sampler")
if type(state) == "table" then
  -- Script-loader re-entry must not install a second per-frame update.
  return
end

state = {
  enabled = false,
  pending_frames = 0,
  frame = 0,
  window_frames = DEFAULT_WINDOW_FRAMES,
  dropped = 0,
  sampled = 0,
  ring = new_ring(DEFAULT_CAPACITY),
  sample_every = SAMPLE_EVERY_FRAMES,
  new_ring = new_ring,
}
rawset(_G, "__f2_sampler", state)

function state.configure(capacity)
  if state.enabled or state.pending_frames > 0 then return false end
  local ring = new_ring(capacity)
  if not ring then return false end
  state.ring = ring
  state.dropped = 0
  state.sampled = 0
  return true
end

function state.set_enabled(enabled)
  if type(enabled) ~= "boolean" then return false end
  if enabled then return state.start() end
  return state.stop()
end

function state.start(window_frames)
  if state.enabled then return false end
  if state.pending_frames > 0 then return false end
  if type(state.ring) ~= "table" then return false end
  if type(QuestManager) ~= "table" or type(QuestManager.HeroEntity) ~= "userdata" then
    return false
  end
  if window_frames == nil then window_frames = DEFAULT_WINDOW_FRAMES end
  if type(window_frames) ~= "number" or window_frames < 1
      or window_frames > MAX_WINDOW_FRAMES or window_frames ~= math.floor(window_frames) then
    return false
  end
  state.frame = 0
  state.window_frames = window_frames
  state.ring = new_ring(state.ring.capacity)
  state.dropped = 0
  state.sampled = 0
  state.enabled = true
  return true
end

-- Console commands write their acknowledgement to out.txt. Defer activation
-- so that command/output I/O happens before any timed position samples.
function state.request_start(window_frames, delay_frames)
  if state.enabled or state.pending_frames > 0 then return false end
  if window_frames == nil then window_frames = DEFAULT_WINDOW_FRAMES end
  if type(window_frames) ~= "number" or window_frames < 1
      or window_frames > MAX_WINDOW_FRAMES or window_frames ~= math.floor(window_frames) then
    return false
  end
  if delay_frames == nil then delay_frames = DEFAULT_ARM_DELAY_FRAMES end
  if type(delay_frames) ~= "number" or delay_frames < 1
      or delay_frames > MAX_WINDOW_FRAMES or delay_frames ~= math.floor(delay_frames) then
    return false
  end
  if type(state.ring) ~= "table" or type(QuestManager) ~= "table"
      or type(QuestManager.HeroEntity) ~= "userdata" then
    return false
  end
  state.window_frames = window_frames
  state.pending_frames = delay_frames
  return true
end

function state.tick_pending()
  if state.pending_frames <= 0 or state.enabled then return false end
  state.pending_frames = state.pending_frames - 1
  if state.pending_frames == 0 then return state.start(state.window_frames) end
  return false
end

function state.stop()
  if state.pending_frames > 0 then
    state.pending_frames = 0
    return true
  end
  if not state.enabled then return false end
  state.enabled = false
  return true
end

function state.dump()
  if state.enabled or state.pending_frames > 0 then return nil end
  return ordered(state.ring), state.dropped, state.ring:overwritten(), state.sampled
end

-- Called from the existing F5 per-frame coroutine. Do not register another
-- GeneralScriptManager script from a script selected by F5: that registration
-- occurs inside the manager's own update and can destabilize its script list.
function state.tick()
  if not state.enabled then return end
  state.frame = state.frame + 1
  if state.frame % state.sample_every == 0 then state.sample() end
  if state.frame >= state.window_frames then state.enabled = false end
end

state.sample = function()
  local hero = nil
  if type(QuestManager) == "table" then hero = QuestManager.HeroEntity end
  if type(hero) ~= "userdata" then
    state.dropped = state.dropped + 1
    return
  end
  -- A native null-entity fault is not catchable by Lua pcall. Caller must
  -- start and stop only in loaded mid-mission gameplay with a known live hero.
  local ok, pos = pcall(function() return hero:GetPosition() end)
  if not ok or type(pos) ~= "userdata" then
    state.dropped = state.dropped + 1
    return
  end
  local x, y, z = tostring(pos):match(
      "CVector3%((%-?%d+%.?%d*),%s*(%-?%d+%.?%d*),%s*(%-?%d+%.?%d*)")
  x, y, z = tonumber(x), tonumber(y), tonumber(z)
  if not x or not y or not z then
    state.dropped = state.dropped + 1
    return
  end
  push(state.ring, { frame = state.frame, x = x, y = y, z = z })
  state.sampled = state.sampled + 1
end
