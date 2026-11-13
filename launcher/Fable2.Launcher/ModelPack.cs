using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using System.Text.Json;

namespace Fable2Launcher;

/// <summary>
/// The Sparrow Edition model pack: the game files the remade models change,
/// laid out like the game folder (data\streaming.bnk, data\levels.bnk, ...).
/// The game is given one folder, so Sparrow Edition plays from an overlay
/// folder of hard links: the pack's files where it has them, the player's own
/// game files everywhere else. Hard links cost no disk space, and the player's
/// game folder is never written to.
/// PROJECT_SPARROW_MODELS points at a local pack for testing.
/// </summary>
public sealed class ModelPack
{
    private const string StampName = "sparrow-overlay.json";

    public string PackFolder { get; }
    public string OverlayFolder { get; }

    public ModelPack(string dataFolder)
    {
        PackFolder = Environment.GetEnvironmentVariable("PROJECT_SPARROW_MODELS") is { Length: > 0 } custom
            ? Path.GetFullPath(custom)
            : Path.Combine(dataFolder, "sparrow-models");
        OverlayFolder = Path.Combine(dataFolder, "sparrow-game");
    }

    public bool Installed
    {
        get
        {
            string data = Path.Combine(PackFolder, "data");
            return Directory.Exists(data) && Directory.EnumerateFiles(data, "*", SearchOption.AllDirectories).Any();
        }
    }

    /// <summary>
    /// Returns the folder to pass as --game_data_root, rebuilding the overlay when
    /// the pack or the game files changed since it was last built.
    /// </summary>
    public string PrepareGameRoot(string gameFolder)
    {
        gameFolder = Path.GetFullPath(gameFolder);
        if (LauncherHome.IsInside(gameFolder, OverlayFolder) || LauncherHome.IsInside(OverlayFolder, gameFolder))
            throw new InvalidOperationException("The game folder and the Sparrow Edition folder overlap. Choose another game folder.");

        Dictionary<string, string> sources = new(StringComparer.OrdinalIgnoreCase);
        foreach (string file in Directory.EnumerateFiles(gameFolder, "*", SearchOption.AllDirectories))
            sources[Path.GetRelativePath(gameFolder, file)] = file;
        foreach (string file in Directory.EnumerateFiles(PackFolder, "*", SearchOption.AllDirectories))
        {
            string relative = Path.GetRelativePath(PackFolder, file);
            if (sources.ContainsKey(relative)) sources[relative] = file;   // the pack only replaces game files
        }

        string stamp = JsonSerializer.Serialize(sources.OrderBy(pair => pair.Key, StringComparer.OrdinalIgnoreCase)
            .Select(pair => new[] { pair.Key, pair.Value, Signature(pair.Value) }));
        string stampPath = Path.Combine(OverlayFolder, StampName);
        if (File.Exists(stampPath) && File.ReadAllText(stampPath) == stamp) return OverlayFolder;

        // Only hard links live here, so deleting the folder never touches the originals.
        if (Directory.Exists(OverlayFolder)) Directory.Delete(OverlayFolder, recursive: true);
        foreach ((string relative, string source) in sources)
        {
            string target = Path.Combine(OverlayFolder, relative);
            Directory.CreateDirectory(Path.GetDirectoryName(target)!);
            if (!CreateHardLink(target, source, IntPtr.Zero))
            {
                int error = Marshal.GetLastWin32Error();
                Directory.Delete(OverlayFolder, recursive: true);
                throw new InvalidOperationException(error == 17   // ERROR_NOT_SAME_DEVICE
                    ? "Sparrow Edition needs the game files, the model pack and the data folder on the same drive."
                    : $"Could not set up Sparrow Edition: {new Win32Exception(error).Message}");
            }
        }
        File.WriteAllText(stampPath, stamp);
        return OverlayFolder;
    }

    private static string Signature(string path)
    {
        var info = new FileInfo(path);
        return $"{info.Length}:{info.LastWriteTimeUtc.Ticks}";
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true, EntryPoint = "CreateHardLinkW")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CreateHardLink(string fileName, string existingFileName, IntPtr securityAttributes);
}
