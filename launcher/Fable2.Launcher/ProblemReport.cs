using System.IO;
using System.IO.Compression;
using System.Runtime.InteropServices;
using Microsoft.Win32;
using System.Text;

namespace Fable2Launcher;

/// <summary>
/// Bundles what's needed to look into a player's problem into one zip:
/// recent logs, settings (never saves), version and PC details. Nothing is
/// sent anywhere; the player attaches the zip.
/// </summary>
public static class ProblemReport
{
    public const string IssuesUrl = "https://github.com/gitgudscrub/Fable-2-Recomp/issues/new";

    public static string Create(LauncherHome home, string version, string edition, string outputFolder)
    {
        Directory.CreateDirectory(outputFolder);
        string path = Path.Combine(outputFolder, $"ProjectSparrow-report-{DateTime.Now:yyyyMMdd-HHmmss}.zip");
        using ZipArchive zip = ZipFile.Open(path, ZipArchiveMode.Create);

        foreach (string log in Newest(home.LogsFolder, "fable_2*.log", 3))
            AddFile(zip, log, "logs/" + Path.GetFileName(log));
        // Performance logs (logs/perf_*.log, [perf] performance_log): small, so a few sessions.
        foreach (string log in Newest(home.LogsFolder, "perf_*.log", 5))
            AddFile(zip, log, "logs/" + Path.GetFileName(log));
        foreach (string config in new[] { home.GraphicsConfigPath, home.LauncherGraphicsPath, home.RecompConfigPath, home.SettingsPath })
            if (File.Exists(config)) AddFile(zip, config, "settings/" + Path.GetFileName(config));
        string build = Path.Combine(home.InstallFolder, "fable2_build.json");
        if (File.Exists(build)) AddFile(zip, build, "fable2_build.json");

        using (var writer = new StreamWriter(zip.CreateEntry("system.txt").Open(), Encoding.UTF8))
            writer.Write(SystemSummary(version, edition));
        return path;
    }

    public static string IssueUrl(string version, string edition)
    {
        string body = "**What happened?**\n\n\n**What were you doing just before?**\n\n\n" +
                      $"Version: {version}\nEdition: {edition}\nWindows: {Environment.OSVersion.VersionString}\n\n" +
                      "Please attach the ProjectSparrow-report zip from your desktop.";
        return IssuesUrl + "?title=" + Uri.EscapeDataString("Problem: ") + "&body=" + Uri.EscapeDataString(body);
    }

    private static string SystemSummary(string version, string edition)
    {
        var text = new StringBuilder();
        text.AppendLine($"Project Sparrow {version}");
        text.AppendLine($"Edition: {edition}");
        text.AppendLine($"Windows: {Environment.OSVersion.VersionString} ({(Environment.Is64BitOperatingSystem ? "64-bit" : "32-bit")})");
        text.AppendLine($"CPU: {ProcessorName()} ({Environment.ProcessorCount} threads)");
        text.AppendLine($"Memory: {MemoryGb()}");
        // Display adapters, from the registry (no WMI dependency).
        try
        {
            using RegistryKey? adapters = Registry.LocalMachine.OpenSubKey(
                @"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}");
            foreach (string name in adapters?.GetSubKeyNames() ?? [])
            {
                if (!int.TryParse(name, out _)) continue;
                using RegistryKey? adapter = adapters!.OpenSubKey(name);
                if (adapter?.GetValue("DriverDesc") is string description)
                    text.AppendLine($"GPU: {description} (driver {adapter.GetValue("DriverVersion")})");
            }
        }
        catch (Exception exception) when (exception is System.Security.SecurityException or UnauthorizedAccessException or IOException)
        {
            text.AppendLine("GPU: could not be read");
        }
        return text.ToString();
    }

    private static string ProcessorName()
    {
        try
        {
            using RegistryKey? cpu = Registry.LocalMachine.OpenSubKey(@"HARDWARE\DESCRIPTION\System\CentralProcessor\0");
            return (cpu?.GetValue("ProcessorNameString") as string)?.Trim() ?? "unknown";
        }
        catch (Exception exception) when (exception is System.Security.SecurityException or UnauthorizedAccessException or IOException)
        {
            return "unknown";
        }
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct MemoryStatus
    {
        public uint Length, MemoryLoad;
        public ulong TotalPhys, AvailPhys, TotalPageFile, AvailPageFile, TotalVirtual, AvailVirtual, AvailExtendedVirtual;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GlobalMemoryStatusEx(ref MemoryStatus status);

    private static string MemoryGb()
    {
        var status = new MemoryStatus { Length = (uint)Marshal.SizeOf<MemoryStatus>() };
        return GlobalMemoryStatusEx(ref status)
            ? $"{status.TotalPhys / (1024.0 * 1024 * 1024):F1} GB"
            : "unknown";
    }

    private static IEnumerable<string> Newest(string folder, string pattern, int count) =>
        Directory.Exists(folder)
            ? new DirectoryInfo(folder).EnumerateFiles(pattern).OrderByDescending(f => f.LastWriteTimeUtc)
                .Take(count).Select(f => f.FullName)
            : [];

    private static void AddFile(ZipArchive zip, string source, string name)
    {
        // Logs can still be open by a running game; share the read.
        using var input = new FileStream(source, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        using Stream output = zip.CreateEntry(name, CompressionLevel.Optimal).Open();
        input.CopyTo(output);
    }
}
