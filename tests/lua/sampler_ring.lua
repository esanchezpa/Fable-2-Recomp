-- In-game Lua 5.1 RED/GREEN test. Run only from F5 in loaded mid-mission QA
-- gameplay. RED is expected while perfSampler.lua is absent from the VFS.
local failures = {}
local function check(condition, message)
  if not condition then failures[#failures + 1] = message end
end

if type(rawget(_G, "__f2_sampler")) ~= "table" then
  local load_sampler = loadfile("scripts/recomp/perfSampler.lua")
  if type(load_sampler) == "function" then load_sampler() end
end

local sampler = rawget(_G, "__f2_sampler")
check(type(sampler) == "table", "sampler implementation is not loaded")
if type(sampler) == "table" then
  local original_state = {
    ring = sampler.ring,
    ring_count = sampler.ring:count(),
    enabled = sampler.enabled,
    pending_frames = sampler.pending_frames,
    frame = sampler.frame,
    window_frames = sampler.window_frames,
    dropped = sampler.dropped,
    sampled = sampler.sampled,
  }
  check(sampler.enabled == false, "sampler must default off")
  check(sampler.set_enabled(1) == false, "non-boolean enable state accepted")
  check(sampler.configure(0) == false, "invalid capacity accepted")
  check(sampler.configure(4097) == false, "capacity above bound accepted")
  check(sampler.configure(3) == true, "valid capacity rejected")
  -- GameFace exposes some engine globals through _G's __index, so assigning
  -- nil does not reliably shadow QuestManager for the sampler under test.
  local old_quest_manager = rawget(_G, "QuestManager")
  rawset(_G, "QuestManager", { HeroEntity = nil })
  check(sampler.start(60) == false, "sampler started without a live hero reference")
  rawset(_G, "QuestManager", old_quest_manager)
  check(sampler.start(0) == false, "zero-frame window accepted")
  check(sampler.start(21601) == false, "oversized frame window accepted")
  check(sampler.start(60) == true, "start failed")
  check(sampler.enabled == true, "start did not enable sampling")

  -- Tick with no live game entity must remain bounded and count missed samples.
  rawset(_G, "QuestManager", { HeroEntity = nil })
  for _ = 1, 60 do sampler.tick() end
  rawset(_G, "QuestManager", old_quest_manager)
  check(sampler.enabled == false, "sampler did not stop at its frame bound")
  check(sampler.frame == 60, "sampler frame count did not reach its bound")
  check(sampler.dropped == 2, "invalid hero samples were not counted")
  local rows, dropped, overwritten, sampled = sampler.dump()
  check(rows ~= nil, "stopped sampler dump failed")
  check(dropped == 2, "dump lost invalid-sample count")
  check(overwritten == 0, "fresh run unexpectedly overwrote samples")
  check(sampled == 0, "invalid hero samples counted as valid")

  local original_sample = sampler.sample
  local sample_calls = 0
  sampler.sample = function() sample_calls = sample_calls + 1 end
  check(sampler.start(29) == true, "29-frame window did not start")
  sampler.tick()
  check(sample_calls == 0, "sample ran before the 30-frame cadence")
  check(sampler.enabled == true, "29-frame window stopped before its bound")
  check(sampler.dump() == nil, "active sampler dump was allowed")
  for _ = 2, 29 do sampler.tick() end
  check(sampler.enabled == false, "29-frame window did not auto-stop")
  sampler.sample = original_sample

  check(sampler.start(60) == true, "manual-stop test did not start")
  sampler.tick()
  check(sampler.stop() == true, "manual stop failed")
  check(sampler.stop() == false, "stopping an idle sampler was not rejected")

  -- Exercise the ring without touching the game API or writing output.
  local ring = sampler.new_ring(3)
  check(ring ~= nil, "valid ring was not created")
  check(sampler.new_ring(0) == nil, "zero-capacity ring was created")
  check(sampler.new_ring(4097) == nil, "oversized ring was created")
  if ring then
    ring:push(11)
    ring:push(22)
    ring:push(33)
    ring:push(44)
    check(ring:count() == 3, "ring did not stay bounded at capacity")
    local values = ring:ordered()
    check(#values == 3, "ordered snapshot has wrong length")
    check(values[1] == 22 and values[2] == 33 and values[3] == 44,
        "overwrite/order mismatch")
    check(ring:overwritten() == 1, "ring overwrite was not counted")
  end
  check(sampler.enabled == false, "sampler unexpectedly enabled after ring test")
  check(sampler.start(1) == true, "restart failed")
  sampler.tick()
  check(sampler.enabled == false, "one-frame window did not auto-stop")
  check(sampler.stop() == false, "auto-stopped sampler reported running")
  check(sampler.request_start(60, 2) == true, "delayed start request failed")
  check(sampler.enabled == false, "delayed start sampled before its wait")
  check(sampler.dump() == nil, "pending sampler dump was allowed")
  sampler.tick_pending()
  check(sampler.enabled == false and sampler.pending_frames == 1,
      "delayed start ignored its first wait frame")
  check(sampler.stop() == true, "pending sampler could not be cancelled")
  check(sampler.pending_frames == 0, "cancel left sampler armed")
  check(sampler.request_start(60, 2) == true, "second delayed start request failed")
  sampler.tick_pending()
  check(sampler.enabled == false and sampler.pending_frames == 1,
      "second delayed start ignored its first wait frame")
  sampler.tick_pending()
  check(sampler.enabled == true and sampler.pending_frames == 0,
      "delayed start did not begin after its wait")
  check(sampler.stop() == true, "delayed-start run could not be stopped")

  -- Preserve the live QA sampler, including any buffered rows, rather than
  -- leaving the test's capacity-3 ring installed in the game session.
  sampler.ring = original_state.ring
  sampler.enabled = original_state.enabled
  sampler.pending_frames = original_state.pending_frames
  sampler.frame = original_state.frame
  sampler.window_frames = original_state.window_frames
  sampler.dropped = original_state.dropped
  sampler.sampled = original_state.sampled
  check(sampler.ring == original_state.ring
      and sampler.ring:count() == original_state.ring_count,
      "test failed to restore the original sampler ring")
end

local status = #failures == 0 and "GREEN" or "RED"
local message = "sampler_ring " .. status
for i = 1, #failures do message = message .. "\n- " .. failures[i] end
rawset(_G, "__f2_sampler_test_result", status)
pcall(GUI.DisplayMessageBox, message)
