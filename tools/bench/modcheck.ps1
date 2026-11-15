# Hands-free look check: boots the game, loads the first save (as bench.ps1
# does), then for each chosen level calls Debug.LoadLevel, waits for it, and
# runs the lines of a command file through the console (console\in.txt),
# taking a window screenshot after each line. A line `F8` presses F8 in the
# game window instead. Lines matching FPSSTART<tag>/FPSEND<tag> mark the
# fps_meter.log position in fps_marks.txt.
#
# Shots land in %TEMP%\<OutName>\<level>-before.png and <level>-step<N>.png.
# Put `cvar frame_limit 60` first in the command file for repeatable framing.
#
# The saves folder is backed up first and put back when the run ends.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\bench\modcheck.ps1 `
#     -Only BWSMarket -CmdFile cmds.txt -OutName mycheck [-ExtraArgs "--resolution_scale=2"]
param(
  [string[]]$Only = @(),
  [int]$LoadTimeoutSec = 90,
  # Extra game arguments, e.g. '--resolution_scale=2'.
  [string]$ExtraArgs = '',
  [Parameter(Mandatory)][string]$CmdFile,
  [string]$OutName = 'fable2-modcheck',
  [string]$Root = 'E:\Fable 2\Fable-2-Recomp',
  [string]$Build = 'E:\Fable 2\Fable-2-Recomp\out\build\win-amd64-release'
)
$ErrorActionPreference = 'Stop'
$root = $Root

# Region path, start marker ('' = default), and whether it is outdoors.
$levels = @(
  @('BWSMarket', '', 1), @('BWSSlums', '', 1), @('BWSCemetary', 'PlayerStart', 1), @('BowerLake', '', 1),
  @('Brightwood', '', 1), @('Ravenscar', '', 1), @('DunecrestNew', 'PlayerStart', 1), @('Westcliff', '', 1),
  @('Wraithmarsh', '', 1), @('Bloodstone', '', 1), @('FairfaxCastleGardens', '', 1), @('TatteredSpire', '', 1),
  @('TempleOfEvil', '', 1), @('Crucible', '', 1), @('Dreamworld', '', 1), @('Reaver Beach (Bloodtsone)', '', 1),
  @('MysteryIsland', '', 1), @('WinterShrine', '', 1), @('SummerShrine', '', 1), @('ChamberOfSeasons', '', 1),
  @('DLC2\DLC2_Past', '', 1), @('DLC2\DLC2_Present', '', 1), @('DLC2\DLC2_Future', '', 1), @('DLC2\DLC2_Colosseum', '', 1),
  @('Tombs\Wraithmarsh\AutumnShrine', '', 0), @('Caves\Bloodstone\Bloodstone_Assault', '', 0),
  @('Tombs\FairfaxCastleGardens\FairfaxTomb', '', 0), @('Caves\Brightwood\BWFarmCellar', '', 0),
  @('Caves\GargoylesCave', '', 0), @('Caves\BWSCemetary\GravekeepersCave', '', 0),
  @('Caves\Westcliff\WestcliffExterior', '', 0), @('Caves\BowerLake\ThagsCave', '', 0),
  @('Tombs\BWSCemetery\HallOfTheDead', '', 0), @('Caves\Dunecrest\HobbeCave', '', 0),
  @('Caves\Ravenscar\HobbesCavern', '', 0), @('Caves\Dunecrest\InnCave', '', 0),
  @('Tombs\BWSCemetery\LadyGreysTomb', '', 0), @('Tombs\BWSMarket\Nightmare Hollow', '', 0),
  @('Caves\Westcliff\PalaceCave', '', 0), @('Tombs\BowerLake\RescueMyBabyTomb', '', 0),
  @('Caves\Ravenscar\RVSRitualCave', '', 0), @('Caves\Deepwood\RiverCave', '', 0),
  @('Tombs\Wraithmarsh\HOTCrypt', '', 0), @('Caves\Bloodstone\SinkHole', '', 0),
  @('Caves\Westcliff\SmugglersCave', '', 0), @('Caves\Bloodstone\TreasureIsland', '', 0),
  @('Tombs\Wraithmarsh\WraithmarshToBloodstoneTomb', '', 0), @('Caves\Dunecrest\WaterfallCave', '', 0),
  @('Caves\Brightwood\WellCave', '', 0), @('Caves\Wraithmarsh\WellCave', '', 0),
  @('DemonDoors\BloodstoneDD', '', 0), @('DemonDoors\BowerLakeDD', '', 0), @('DemonDoors\BrightwoodDD', '', 0),
  @('DemonDoors\RavenscarDD', '', 0), @('DemonDoors\MarcusMemorial', '', 0), @('DemonDoors\Homestead', '', 0),
  @('DemonDoors\DunecrestDD', '', 0), @('DemonDoors\WestcliffDD', '', 0), @('DemonDoors\DeepwoodDD', '', 0)
)
# (-File passes "a,b" as one string.)
$Only = @($Only | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
if ($Only.Count) { $levels = @($levels | Where-Object { $Only -contains $_[0] }) }

function Send-Console([string[]]$lines) {
  $in = Join-Path $root 'console\in.txt'
  $deadline = (Get-Date).AddSeconds(10)
  while ((Test-Path $in) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 100 }
  $tmp = Join-Path $root 'console\in.tmp'
  Set-Content -Path $tmp -Value ($lines -join "`n") -Encoding ascii
  Move-Item $tmp $in -Force
}
function Log-Lines { Get-Content $script:log.FullName }
function Wait-Log([string]$pattern, [int]$afterCount, [int]$timeoutSec) {
  $deadline = (Get-Date).AddSeconds($timeoutSec)
  while ((Get-Date) -lt $deadline) {
    if ((Select-String $script:log.FullName -Pattern $pattern | Measure-Object).Count -gt $afterCount) { return $true }
    if ($script:p.HasExited) { throw "game exited" }
    Start-Sleep -Milliseconds 250
  }
  return $false
}
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System; using System.Runtime.InteropServices;
public static class WB {
  [StructLayout(LayoutKind.Sequential)] public struct R { public int L,T,Rt,B; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
}
'@
[WB]::SetProcessDPIAware() | Out-Null
$shots = Join-Path $env:TEMP $OutName
New-Item -ItemType Directory -Force $shots | Out-Null
function Shot([string]$name) {
  $script:p.Refresh(); $h = $script:p.MainWindowHandle
  $r = New-Object WB+R; [WB]::GetWindowRect($h, [ref]$r) | Out-Null
  $bmp = New-Object System.Drawing.Bitmap ($r.Rt - $r.L), ($r.B - $r.T)
  $g = [System.Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc(); [WB]::PrintWindow($h, $dc, 2) | Out-Null; $g.ReleaseHdc($dc); $g.Dispose()
  $bmp.Save((Join-Path $shots "$name.png")); $bmp.Dispose()
}
function PressF8 {
  $script:p.Refresh(); (New-Object -ComObject WScript.Shell).AppActivate($script:p.Id) | Out-Null
  [WB]::SetForegroundWindow($script:p.MainWindowHandle) | Out-Null
  Start-Sleep -Milliseconds 300
  [WB]::keybd_event(0x77, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 150
  [WB]::keybd_event(0x77, 0, 2, [UIntPtr]::Zero); Start-Sleep 2
}
function Count-Log([string]$pattern) { (Select-String $script:log.FullName -Pattern $pattern | Measure-Object).Count }
# Walks the hero in a square so the following camera sweeps all around.
function Walk-Around {
  foreach ($stick in @('0 32767', '32767 0', '0 -32767', '-32767 0')) {
    Send-Console @("pad stick $stick 400")
    Start-Sleep 3
  }
  Send-Console @('pad off')
}

# Pipelines and shaders in the cache (read while the game is closed: the sizes
# of files the game holds open are stale on Windows).
$cacheDir = Join-Path $Build 'cache\shaders\shareable'
function Cache-Counts {
  $xpso = Join-Path $cacheDir '4D5307F1.rtv.d3d12.xpso'
  $xsh = Join-Path $cacheDir '4D5307F1.xsh'
  $n = if (Test-Path $xpso) { [int](((Get-Item $xpso).Length - 12) / 72) } else { 0 }
  $kb = if (Test-Path $xsh) { [int]((Get-Item $xsh).Length / 1024) } else { 0 }
  "$n pipelines, $kb KB of shaders"
}
$cacheBefore = Cache-Counts

# Back up the saves.
$saves = Join-Path $Build 'saves'
$backup = Join-Path $env:TEMP ("fable2-tour\saves-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force (Split-Path $backup) | Out-Null
Copy-Item $saves $backup -Recurse
"saves backed up to $backup"

New-Item -ItemType Directory -Force (Join-Path $root 'console') | Out-Null
Remove-Item (Join-Path $root 'console\in.txt') -ErrorAction SilentlyContinue
$before = Get-Date
# Uncapped: the menu presses below are timed in frames, as in bench.ps1.
$script:p = Start-Process (Join-Path $Build 'fable_2.exe') -ArgumentList ("--game_data_root=`"$root`" --vsync=false --d3d12_log_pipeline_timing=true " + $ExtraArgs) -WorkingDirectory $Build -PassThru
$results = @()
try {
  $script:log = $null
  for ($i = 0; $i -lt 60 -and -not $script:log; $i++) {
    Start-Sleep 1
    $script:log = Get-ChildItem (Join-Path $Build 'logs') -File | Where-Object { $_.LastWriteTime -ge $before } | Sort-Object LastWriteTime | Select-Object -Last 1
  }
  if (-not $script:log) { throw "no log" }
  if (-not (Wait-Log 'video ended' 1 120)) { throw "title not reached" }
  if (-not (Wait-Log 'fireEvent: END_LEGAL' 0 60)) { throw "legal text did not finish" }
  Start-Sleep 3
  $hud = Count-Log 'FinishedTransitioningToGame'
  Send-Console @('pad A 120', 'wait 5s', 'pad Down 60', 'wait 2s', 'pad A 60', 'wait 3s', 'pad A 60')
  if (-not (Wait-Log 'FinishedTransitioningToGame' $hud 120)) { throw "game not entered" }
  Start-Sleep 4
  Send-Console @('pad Start 60')
  Start-Sleep 15
  "in game; checking $($levels.Count) levels (log $($script:log.Name))"

  foreach ($lv in $levels) {
    $name, $marker, $outdoor = $lv
    $t0 = Get-Date
    $builds0 = Count-Log 'pipeline-timing\] create'
    $expect = '"albion", "' + [regex]::Escape($name.ToLower()) + '"'
    $seen = Count-Log $expect
    $luaName = $name.Replace('\', '\\')
    Send-Console @("lua Debug.LoadLevel(`"Albion`", `"$luaName`", `"$marker`")")
    $loaded = $false
    $deadline = (Get-Date).AddSeconds($LoadTimeoutSec)
    $resend = (Get-Date).AddSeconds(30)
    while (-not $loaded -and (Get-Date) -lt $deadline) {
      Start-Sleep 4
      if ($script:p.HasExited) { throw "game exited" }
      # The console file can drop a command sent while the game is busy, so send
      # the load again every 30 s until it lands (a load takes a few seconds).
      if ((Get-Date) -gt $resend) {
        Send-Console @("lua Debug.LoadLevel(`"Albion`", `"$luaName`", `"$marker`")")
        $resend = (Get-Date).AddSeconds(30)
      }
      Send-Console @('info')
      Start-Sleep 1
      $loaded = (Count-Log $expect) -gt $seen
    }
    if (-not $loaded) {
      $results += [pscustomobject]@{ Level = $name; Loaded = $false; NewBuilds = (Count-Log 'pipeline-timing\] create') - $builds0; Sec = [int]((Get-Date) - $t0).TotalSeconds }
      "{0,-48} did not load within {1} s" -f $name, $LoadTimeoutSec
      continue
    }
    Start-Sleep 6
    Send-Console @('godmode on')
    if ($outdoor) { Send-Console @('time 12') }
    Start-Sleep 12
    $tag = ($name -replace '[\\ ]', '_')
    Shot "$tag-before"
    $i = 0
    foreach ($line in @(Get-Content $CmdFile)) {
      $i++
      if ($line -eq 'F8') { PressF8 } else { Send-Console @($line) }
      if ($line -match 'FPS(START|END)([a-z]*)') {
        $fm = Join-Path $Build 'fps_meter.log'
        $cnt = if (Test-Path $fm) { (Get-Content $fm).Count } else { 0 }
        Add-Content (Join-Path $shots 'fps_marks.txt') "$($Matches[1])$($Matches[2]) $cnt"
      }
      Start-Sleep 6
      Shot "$tag-step$i"
    }
    $new = (Count-Log 'pipeline-timing\] create') - $builds0
    $results += [pscustomobject]@{ Level = $name; Loaded = $true; NewBuilds = $new; Sec = [int]((Get-Date) - $t0).TotalSeconds }
    "{0,-48} loaded, {1} blocking builds, {2} s" -f $name, $new, [int]((Get-Date) - $t0).TotalSeconds
  }
} finally {
  if ($script:p -and -not $script:p.HasExited) {
    $script:p.CloseMainWindow() | Out-Null
    if (-not $script:p.WaitForExit(20000)) { $script:p.Kill() }
  }
  Start-Sleep 2
  # Put the saves back exactly as they were.
  if (Test-Path $backup) {
    Remove-Item $saves -Recurse -Force -ErrorAction SilentlyContinue
    Copy-Item $backup $saves -Recurse
    "saves restored from $backup"
  }
}
$ok = @($results | Where-Object Loaded).Count
"done: $ok of $($results.Count) levels loaded"
"shader cache before: $cacheBefore"
"shader cache after:  $(Cache-Counts)"
