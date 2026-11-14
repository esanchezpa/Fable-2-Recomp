namespace Fable2Launcher;

/// <summary>
/// One edition: a named bundle of graphics settings (fable_2.toml), recomp
/// patches (fable2_config.toml) and which game data to load. Settings the
/// edition doesn't name are left as the player set them.
/// </summary>
/// <param name="ModernGraphics">[graphics] texture_pack: AI-upscaled textures, filtering and grade.</param>
/// <param name="Models">Load the Sparrow model pack (remade models) on top of the game files.</param>
/// <param name="Ultra">[graphics] ultra: light shafts, a sharper sun shadow map redrawn every frame, stronger AO.</param>
public sealed record Edition(
    string Id, string Name, string Summary,
    string Resolution, string RenderScale, string Anisotropic, string AntiAliasing, string FrameLimit,
    bool DisableMotionBlur, bool HighTickRate, bool HigherHfTickRate, bool ModernGraphics, bool Models,
    bool Ultra = false)
{
    public static readonly Edition Original = new("original", "Original", "30 fps · 720p · as on Xbox",
        "720p", "1", "-1", "none", "30",
        DisableMotionBlur: false, HighTickRate: false, HigherHfTickRate: false, ModernGraphics: false, Models: false);

    public static readonly Edition Enhanced = new("enhanced", "Enhanced", "60 fps · 1440p · AI textures",
        "1440p", "2", "5", "fxaa", "60",
        DisableMotionBlur: true, HighTickRate: false, HigherHfTickRate: false, ModernGraphics: true, Models: false);

    public static readonly Edition Sparrow = new("sparrow", "Sparrow Edition", "Remade models · Ultra lighting",
        "1440p", "2", "5", "fxaa", "60",
        DisableMotionBlur: true, HighTickRate: false, HigherHfTickRate: false, ModernGraphics: true, Models: true,
        Ultra: true);

    public static readonly Edition[] All = [Original, Enhanced, Sparrow];

    /// <summary>The saved edition. "experimental" (removed) becomes Enhanced; the player's own settings stay.</summary>
    public static Edition Find(string? id) =>
        id == "experimental" ? Enhanced : All.FirstOrDefault(edition => edition.Id == id) ?? Original;

    /// <summary>True when the current settings are exactly what this edition sets.</summary>
    public bool Matches(string resolution, string renderScale, string anisotropic, string antiAliasing,
        string frameLimit, Fable2ConfigValues recomp) =>
        resolution == Resolution && renderScale == RenderScale && anisotropic == Anisotropic &&
        antiAliasing == AntiAliasing && frameLimit == FrameLimit &&
        recomp.DisableMotionBlur == DisableMotionBlur && recomp.HighTickRate == HighTickRate &&
        recomp.HigherHfTickRate == HigherHfTickRate && recomp.TexturePack == ModernGraphics &&
        recomp.Ultra == Ultra;
}
