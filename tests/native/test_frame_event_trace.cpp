// Verifies the three runtime signals remain separately sequenced and labeled.
#include <rex/graphics/frame_event_trace.h>

#include <cstdint>
#include <cstring>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

#include <process.h>

int main() {
  using rex::graphics::FrameEventKind;
  using rex::graphics::FrameEventSequence;

  FrameEventSequence sequence;
  const auto swap1 = sequence.Record(FrameEventKind::kXeSwap, 100, 0);
  const auto output1 = sequence.Record(FrameEventKind::kGuestOutputProduced, 110, 0, 1, 0);
  const auto acquired1 = sequence.Record(FrameEventKind::kGuestOutputAcquired, 115, 0, 1, 0);
  const auto present1 = sequence.Record(FrameEventKind::kDxgiPresent, 120, -2005270523,
                                        1, 0, 9);
  const auto swap2 = sequence.Record(FrameEventKind::kXeSwap, 130, 0);

  if (swap1.sequence != 1 || swap2.sequence != 2 || output1.sequence != 1 ||
      acquired1.sequence != 1 || present1.sequence != 1) {
    std::cerr << "event sequences must be independent per event kind\n";
    return 1;
  }
  if (swap1.clock_ticks != 100 || output1.clock_ticks != 110 || present1.clock_ticks != 120 ||
      present1.result != -2005270523 || output1.guest_output_id != acquired1.guest_output_id ||
      acquired1.guest_output_id != present1.guest_output_id || output1.mailbox_index != 0 ||
      acquired1.mailbox_index != present1.mailbox_index ||
      present1.swapchain_present_count != 9) {
    std::cerr << "event records must preserve timestamp and present HRESULT\n";
    return 2;
  }
  rex::graphics::GuestOutputMailboxIds mailbox_ids;
  mailbox_ids.Set(output1.mailbox_index, output1.guest_output_id);
  mailbox_ids.Set(2, 22);
  if (mailbox_ids.Get(acquired1.mailbox_index) != present1.guest_output_id ||
      mailbox_ids.Get(2) != 22 || mailbox_ids.Get(3) != 0) {
    std::cerr << "mailbox slots must preserve the published guest-output ID\n";
    return 9;
  }
  if (std::strcmp(rex::graphics::FrameEventKindName(swap1.kind), "xe_swap") != 0 ||
      std::strcmp(rex::graphics::FrameEventKindName(output1.kind),
                  "guest_output_produced") != 0 ||
      std::strcmp(rex::graphics::FrameEventKindName(acquired1.kind),
                  "guest_output_acquired") != 0 ||
      std::strcmp(rex::graphics::FrameEventKindName(present1.kind),
                  "dxgi_present_attempt") != 0) {
    std::cerr << "event labels must describe their source without implying uniqueness/display\n";
    return 3;
  }

  // Trace setup must fail closed: it may create a new file but never truncate
  // an existing target, and it rejects relative paths.
  const auto test_dir = std::filesystem::temp_directory_path() /
                        ("fable-frame-trace-test-" + std::to_string(_getpid()));
  if (!std::filesystem::create_directory(test_dir)) {
    std::cerr << "test directory already exists; refusing to reuse it\n";
    return 4;
  }
  const auto existing_path = test_dir / "existing.csv";
  {
    std::ofstream existing(existing_path, std::ios::binary);
    existing << "do-not-truncate";
  }
  if (rex::graphics::OpenNewFrameEventTraceFile(existing_path) != nullptr) {
    std::cerr << "trace setup opened an existing file\n";
    return 5;
  }
  {
    std::ifstream existing(existing_path, std::ios::binary);
    const std::string contents((std::istreambuf_iterator<char>(existing)), {});
    if (contents != "do-not-truncate") {
      std::cerr << "existing trace target was modified\n";
      return 6;
    }
  }
  if (rex::graphics::OpenNewFrameEventTraceFile("relative.csv") != nullptr) {
    std::cerr << "trace setup accepted a relative path\n";
    return 7;
  }
  const auto new_path = test_dir / "new.csv";
  std::FILE* created = rex::graphics::OpenNewFrameEventTraceFile(new_path);
  if (!created) {
    std::cerr << "trace setup refused a new absolute file\n";
    return 8;
  }
  std::fputs("created", created);
  std::fclose(created);
  std::filesystem::remove(existing_path);
  std::filesystem::remove(new_path);
  std::filesystem::remove(test_dir);
  std::cout << "Distinct XE_SWAP, guest-output production, and DXGI-present signals verified.\n";
  return 0;
}
