// perf_log.h - always-on performance log for playtesters ([perf] performance_log).
//
// Times every call of the game's main loop (MainRenderLoop_82B9CD68, one call
// per frame; called from the override in fps_meter.h) and writes a compact
// summary to <user root>/logs/perf_<date>-<time>.log:
//
//   every 10 s:  t=  130.0s fps=59.8 low1=52.3 worst=31.2ms over50ms=0
//   each stall:  hitch t=  134.2s 412.0ms
//
// fps is the average over the window, low1 the frame rate of its slowest 1%
// of frames, worst its longest frame, over50ms how many frames took 50 ms or
// more. A hitch is a single frame of 100 ms or more (loading screens show up
// as hitches too). About 25 KB per hour of play; the 20 newest logs are kept.
// The launcher's "Report a problem" zip includes the newest ones, and it turns
// on the SDK's [pipeline-timing] lines in the game log alongside this.
//
// Separate from fps_meter.log (FABLE2_FPS_METER=1), which the benchmark
// harness reads and which is unchanged.

#pragma once

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <string>
#include <system_error>
#include <vector>

#include "fable2_config.h"

namespace fable2::perflog {

namespace detail {

constexpr double kWindowSeconds = 10.0;
constexpr double kStutterMs = 50.0;
constexpr double kHitchMs = 100.0;
constexpr int kMaxHitchLines = 500;
constexpr size_t kKeepLogs = 20;

inline void PruneOldLogs(const std::filesystem::path& folder) {
  std::error_code ec;
  std::vector<std::filesystem::path> logs;
  for (const auto& entry : std::filesystem::directory_iterator(folder, ec)) {
    const std::string name = entry.path().filename().string();
    if (name.rfind("perf_", 0) == 0 && entry.path().extension() == ".log") logs.push_back(entry.path());
  }
  if (logs.size() <= kKeepLogs) return;
  // perf_YYYYMMDD-HHMMSS.log sorts by name in time order.
  std::sort(logs.begin(), logs.end());
  for (size_t i = 0; i + kKeepLogs < logs.size(); ++i) std::filesystem::remove(logs[i], ec);
}

inline std::ofstream* Open(const std::filesystem::path& user_root) {
  std::error_code ec;
  const std::filesystem::path folder = user_root / "logs";
  std::filesystem::create_directories(folder, ec);
  const std::time_t now = std::time(nullptr);
  std::tm local{};
  localtime_s(&local, &now);
  char stamp[32];
  std::strftime(stamp, sizeof(stamp), "%Y%m%d-%H%M%S", &local);
  static std::ofstream file(folder / (std::string("perf_") + stamp + ".log"));
  if (!file) return nullptr;
  char started[32];
  std::strftime(started, sizeof(started), "%Y-%m-%d %H:%M:%S", &local);
  file << "# Project Sparrow performance log, started " << started << "\n"
       << "# every 10 s: average fps, fps of the slowest 1% of frames, longest frame,\n"
       << "# frames of 50 ms or more. hitch = one frame of 100 ms or more.\n";
  file.flush();
  PruneOldLogs(folder);
  return &file;
}

}  // namespace detail

// Call once per frame from the main loop. user_root is fable2::UserRoot().
inline void OnFrame(const std::filesystem::path& user_root) {
  using clock = std::chrono::steady_clock;
  static const bool enabled = fable2::config::Get().performance_log;
  if (!enabled) return;

  static std::ofstream* out = nullptr;
  static bool opened = false;
  static clock::time_point session_start, window_start, last;
  static std::vector<float> frame_ms;
  static int hitch_lines = 0;

  const clock::time_point now = clock::now();
  if (!opened) {
    opened = true;
    out = detail::Open(user_root);
    session_start = window_start = last = now;
    frame_ms.reserve(2048);
    return;
  }
  if (!out) return;

  const double ms = std::chrono::duration<double, std::milli>(now - last).count();
  last = now;
  frame_ms.push_back(static_cast<float>(ms));
  const double t = std::chrono::duration<double>(now - session_start).count();
  char line[160];

  if (ms >= detail::kHitchMs && hitch_lines < detail::kMaxHitchLines) {
    ++hitch_lines;
    std::snprintf(line, sizeof(line), "hitch t=%9.1fs %.1fms\n", t, ms);
    *out << line;
  }

  const double window = std::chrono::duration<double>(now - window_start).count();
  if (window < detail::kWindowSeconds) return;

  const size_t frames = frame_ms.size();
  int over = 0;
  float worst = 0.0f;
  for (float f : frame_ms) {
    if (f >= detail::kStutterMs) ++over;
    worst = std::max(worst, f);
  }
  // The frame at the 99th percentile of frame time = the slowest 1%.
  const size_t k = std::min(frames - 1, static_cast<size_t>(frames * 0.99));
  std::nth_element(frame_ms.begin(), frame_ms.begin() + k, frame_ms.end());
  const double p99 = frame_ms[k];
  std::snprintf(line, sizeof(line), "t=%9.1fs fps=%.1f low1=%.1f worst=%.1fms over50ms=%d\n", t,
                frames / window, p99 > 0.0 ? 1000.0 / p99 : 0.0, worst, over);
  *out << line;
  out->flush();
  frame_ms.clear();
  window_start = now;
}

}  // namespace fable2::perflog
