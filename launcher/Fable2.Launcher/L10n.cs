using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Documents;
using System.Text.RegularExpressions;

namespace Fable2Launcher;

/// <summary>Launcher UI language (EN source strings -> ES). The XAML keeps its
/// English source strings; L10n.Apply walks the tree and swaps them in place, and
/// dynamic status strings go through L10n.T so they are written already translated.
/// Switching back to English uses the reverse map, so round-trips stay exact.</summary>
public static class L10n
{
    public static string Current { get; private set; } = "en";

    private static readonly Dictionary<string, string> Es = new()
    {
        ["FABLE II  \u00b7  RECOMPILED FOR WINDOWS"] = "FABLE II  \u00b7  RECOMPILADO PARA WINDOWS",
        ["Every hero begins as a sparrow."] = "Todo h\u00e9roe empieza siendo un gorri\u00f3n.",
        ["Play"] = "Jugar",
        ["Ready to play"] = "Listo para jugar",
        ["Copy it anyway"] = "Copiar igualmente",
        ["Stop"] = "Detener",
        ["Play now, update later"] = "Jugar ahora, actualizar despu\u00e9s",
        ["EDITION"] = "EDICI\u00d3N",
        ["Enhanced"] = "Mejorado",
        ["Custom changes"] = "Cambios personalizados",
        ["Settings"] = "Ajustes",
        ["Controls"] = "Controles",
        ["Updates"] = "Actualizaciones",
        ["Help"] = "Ayuda",
        ["Close"] = "Cerrar",
        ["Minimise"] = "Minimizar",
        ["Maximise"] = "Maximizar",
        ["APPEARANCE"] = "APARIENCIA",
        ["Night"] = "Noche",
        ["Dusk"] = "Crep\u00fasculo",
        ["Day"] = "D\u00eda",
        ["Theme"] = "Tema",
        ["Night is darkest, Day is light."] = "Noche es el m\u00e1s oscuro, D\u00eda el m\u00e1s claro.",
        ["DISPLAY"] = "PANTALLA",
        ["Window"] = "Ventana",
        ["Window size"] = "Tama\u00f1o de ventana",
        ["Render scale"] = "Escala de renderizado",
        ["Draws the game sharper than the Xbox did"] = "Dibuja el juego con m\u00e1s nitidez que la Xbox",
        ["Texture filtering"] = "Filtrado de texturas",
        ["Game default"] = "Predeterminado del juego",
        ["Smoothing"] = "Suavizado",
        ["Off (game's own)"] = "Desactivado (el del juego)",
        ["Game frame rate"] = "Velocidad de fotogramas del juego",
        ["Above 60 can break timing in some scenes"] = "M\u00e1s de 60 puede romper la sincron\u00eda en algunas escenas",
        ["Display frame cap"] = "Tope de la pantalla",
        ["Ultra lighting"] = "Iluminaci\u00f3n ultra",
        ["Light shafts, sharper sun shadows, deeper contrast. About 6% slower; Modern graphics only"] = "Haces de luz, sombras solares m\u00e1s n\u00edtidas, m\u00e1s contraste. Un 6% m\u00e1s lento; solo con gr\u00e1ficos modernos",
        ["LANGUAGE"] = "IDIOMA",
        ["Game language"] = "Idioma del juego",
        ["Uses the language data included in your game copy"] = "Usa los datos de idioma incluidos en tu copia del juego",
        ["MODERN TEXTURES"] = "TEXTURAS MODERNAS",
        ["Download"] = "Descargar",
        ["Remove"] = "Quitar",
        ["Check now"] = "Buscar ahora",
        ["Check for updates"] = "Buscar actualizaciones",
        ["Build"] = "Construir",
        ["Restart to update"] = "Reiniciar para actualizar",
        ["DETAILED MODELS"] = "MODELOS DETALLADOS",
        ["Use detailed models"] = "Usar modelos detallados",
        ["Enhanced only. Takes effect the next time you play"] = "Solo Mejorado. Se aplica la pr\u00f3xima vez que juegues",
        ["GAME"] = "JUEGO",
        ["Skip intro videos"] = "Saltar v\u00eddeos de intro",
        ["Motion blur"] = "Desenfoque de movimiento",
        ["CPU yield batching"] = "Ceder CPU por lotes",
        ["Live skin changes"] = "Cambios de piel en vivo",
        ["Old skin fix"] = "Correcci\u00f3n de piel antigua",
        ["The earlier CPU fix for the hero and dog textures. Replaced by live skin changes"] = "Correcci\u00f3n por CPU de las texturas del h\u00e9roe y el perro. Sustituida por los cambios de piel en vivo",
        ["Draws the hero and dog skin changes on the GPU. Fixes a black hero or dog"] = "Dibuja los cambios de piel del h\u00e9roe y el perro en la GPU. Arregla un h\u00e9roe o perro en negro",
        ["Faster world tick"] = "Tick del mundo m\u00e1s r\u00e1pido",
        ["Runs the slow game tick at 30 Hz instead of 15. Unstable"] = "Ejecuta el tick lento del juego a 30 Hz en vez de 15. Inestable",
        ["Faster animation tick"] = "Tick de animaci\u00f3n m\u00e1s r\u00e1pido",
        ["Runs the fast tick at 60 Hz instead of 30. Needs the faster world tick. Unstable"] = "Ejecuta el tick r\u00e1pido a 60 Hz en vez de 30. Requiere el tick del mundo m\u00e1s r\u00e1pido. Inestable",
        ["Grants the old Fable II website rewards when a save loads"] = "Da las recompensas de la web antigua de Fable II al cargar una partida",
        ["Grants the Collector's Edition chest when a save loads"] = "Da el cofre de la Collector's Edition al cargar una partida",
        ["Website items"] = "Objetos de la web",
        ["Collector's Edition items"] = "Objetos de la Collector's Edition",
        ["KEYBOARD KEYS"] = "TECLAS DE TECLADO",
        ["Click a key box, then press the key or mouse button you want. Esc cancels."] = "Pulsa una caja de tecla y luego la tecla o bot\u00f3n de rat\u00f3n que quieras. Esc cancela.",
        ["Add a key"] = "A\u00f1adir tecla",
        ["MOUSE"] = "RAT\u00d3N",
        ["Mouse look"] = "C\u00e1mara con rat\u00f3n",
        ["Mouse speed"] = "Velocidad del rat\u00f3n",
        ["Direct camera"] = "C\u00e1mara directa",
        ["Turns the camera like a PC game instead of through the right stick. Experimental"] = "Mueve la c\u00e1mara como un juego de PC en vez de por el stick derecho. Experimental",
        ["Controllers work straight away. These settings are for playing on keyboard and mouse."] = "Los mandos funcionan directamente. Estos ajustes son para jugar con teclado y rat\u00f3n.",
        ["Windowed"] = "Ventana",
        ["Borderless fullscreen"] = "Pantalla completa sin bordes",
        ["Exclusive fullscreen"] = "Pantalla completa exclusiva",
        ["Stable"] = "Estable",
        ["Channel"] = "Canal",
        ["Newest fixes first, less tested. Back up your saves before switching back to Stable."] = "Lo \u00faltimo primero, menos probado. Haz copia de tus partidas antes de volver a Estable.",
        ["Tested releases. Updates download in the background; restart the launcher to install them."] = "Versiones probadas. Las actualizaciones se descargan en segundo plano; reinicia el launcher para instalarlas.",
        ["Automatic updates start once Project Sparrow is installed with its installer. "] = "Las actualizaciones autom\u00e1ticas empiezan cuando Project Sparrow est\u00e1 instalado con su instalador. ",
        ["This is a dev build."] = "Esta es una build de desarrollo.",
        ["You're running {0}."] = "Est\u00e1s usando la {0}.",
        ["Version {0} is ready. Restart to install it; your saves and settings stay as they are."] = "La versi\u00f3n {0} est\u00e1 lista. Reinicia para instalarla; tus partidas y ajustes se quedan igual.",
        ["Checking for updates\u2026"] = "Buscando actualizaciones\u2026",
        ["You're up to date ({0})."] = "Est\u00e1s al d\u00eda ({0}).",
        ["Report a problem"] = "Informar de un problema",
        ["Create report"] = "Crear informe",
        ["Bundle logs and settings, then open a GitHub issue"] = "Empaqueta logs y ajustes, y abre una incidencia en GitHub",
        ["This puts the following in one zip on your desktop. Nothing is uploaded; you attach it to the issue yourself."] = "Esto junta lo siguiente en un zip en tu escritorio. No se sube nada; t\u00fa adjuntas el zip a la incidencia.",
        ["Record performance logs"] = "Registrar logs de rendimiento",
        ["Records frame rate, stutters and slow shader builds while you play. The logs stay on your PC until you send them with Report a problem. If you turn this off, the issues you run into can't be seen or fixed"] = "Registra fotogramas, tirones y builds de shaders lentas mientras juegas. Los logs se quedan en tu PC hasta que los env\u00edes con Informar de un problema. Si lo desactivas, los problemas no se podr\u00e1n ver ni arreglar",
        ["Updates are signed by Project Sparrow and checked before they install. They never touch your saves, settings or game files."] = "Las actualizaciones las firma Project Sparrow y se comprueban antes de instalarse. Nunca tocan tus partidas, ajustes ni archivos del juego.",
        ["Choose disc image\u2026"] = "Elegir imagen de disco\u2026",
        ["Use game files from another folder\u2026"] = "Usar los archivos del juego de otra carpeta\u2026",
        ["Move to\u2026"] = "Mover a\u2026",
        ["Change data folder"] = "Cambiar carpeta de datos",
        ["Open save folder"] = "Abrir carpeta de partidas",
        ["Check game files"] = "Comprobar archivos del juego",
        ["Make sure every game file matches the original disc"] = "Comprueba que cada archivo del juego coincide con el disco original",
        ["Clear shader cache"] = "Vaciar cach\u00e9 de shaders",
        ["Reset to default"] = "Restaurar valores",
        ["Game program missing"] = "Falta el programa del juego",
        ["fable_2.exe isn't in the install folder. Reinstall Project Sparrow to fix this."] = "fable_2.exe no est\u00e1 en la carpeta de instalaci\u00f3n. Reinstala Project Sparrow para arreglarlo.",
        ["Choose your Fable II disc image"] = "Elige tu imagen de disco de Fable II",
        ["Pick the .iso you made from your own Fable II Game of the Year disc. It's checked, then about 7 GB is copied into your data folder. The disc image is never uploaded."] = "Elige la .iso que sacaste de tu propio disco de Fable II Game of the Year. Se comprueba y luego se copian unos 7 GB a tu carpeta de datos. La imagen del disco nunca se sube.",
        ["Update {0} is ready"] = "La versi\u00f3n {0} est\u00e1 lista",
        ["Restarting installs it and keeps your saves and settings. It takes a few seconds."] = "Reiniciar la instala y conserva tus partidas y ajustes. Tarda unos segundos.",
        ["This copy can't be played"] = "Esta copia no se puede jugar",
        ["Reading the disc image"] = "Leyendo la imagen de disco",
        ["Looking for the Xbox 360 file system\u2026"] = "Buscando el sistema de archivos de Xbox 360\u2026",
        ["Copying game files"] = "Copiando archivos del juego",
        ["This disc isn't a known Fable II GOTY copy"] = "Este disco no es una copia GOTY de Fable II conocida",
        ["Stopping\u2026"] = "Deteniendo\u2026",
        ["Checking game files\u2026"] = "Comprobando archivos del juego\u2026",
        ["Checking game files\u2026 {0}"] = "Comprobando archivos del juego\u2026 {0}",
        ["Your saves, settings and logs live in {0}. "] = "Tus partidas, ajustes y logs viven en {0}. ",
        ["The game files (about 7 GB) are in there too. "] = "Los archivos del juego (unos 7 GB) tambi\u00e9n est\u00e1n ah\u00ed. ",
        ["The game files are read from {0}. "] = "Los archivos del juego se leen de {0}. ",
        ["Updates never touch this folder."] = "Las actualizaciones nunca tocan esta carpeta.",
        ["Could not prepare the data folder: "] = "No se pudo preparar la carpeta de datos: ",
        ["Keyboard: WASD to move, E or Shift to interact, Esc to pause."] = "Teclado: WASD para moverte, E o Shift para interactuar, Esc para pausar.",
        ["Content missing"] = "Falta contenido",
        ["Mixed files detected"] = "Archivos mezclados detectados",
        ["Unknown XEX build"] = "Build de XEX desconocida",
        ["Version {0} installed. You're up to date."] = "Versi\u00f3n {0} instalada. Est\u00e1s al d\u00eda.",
        ["Shows when you play Enhanced with Use detailed models on."] = "Se ve al jugar en Mejorado con Usar modelos detallados activado.",
        ["Enhanced keeps the original models until the download finishes."] = "Mejorado usa los modelos originales hasta que termine la descarga.",
        ["Downloaded; the models still need to be built for your game files."] = "Descargado; falta construir los modelos para tus archivos del juego.",
        ["Takes a few minutes and about {0} of disk space. It also runs on its own when you play Enhanced."] = "Tarda unos minutos y unos {0} de disco. Tambi\u00e9n se ejecuta solo al jugar en Mejorado.",
        ["Version {0} installed."] = "Versi\u00f3n {0} instalada.",
        ["Version {0}: {1} to download."] = "Versi\u00f3n {0}: falta descargar {1}.",
        ["Not installed."] = "No instalado.",
        ["Looking for the newest model pack\u2026"] = "Buscando el pack de modelos m\u00e1s nuevo\u2026",
        ["Downloading version {0}\u2026"] = "Descargando la versi\u00f3n {0}\u2026",
        ["You can close the launcher in the meantime; the download resumes where it stopped."] = "Puedes cerrar el launcher mientras; la descarga contin\u00faa donde se qued\u00f3.",
        ["{0} of {1}"] = "{0} de {1}",
        ["This takes a few minutes. Your game folder isn't changed."] = "Tarda unos minutos. Tu carpeta del juego no se cambia.",
        ["Paused. The download resumes where it stopped."] = "En pausa. La descarga contin\u00faa donde se qued\u00f3.",
        ["Version {0} installed ({1}). You're up to date."] = "Versi\u00f3n {0} instalada ({1}). Est\u00e1s al d\u00eda.",
        ["Shows at a render scale of 2\u00d7 or more. F8 in game switches between Modern and Classic."] = "Se ve a escala de renderizado de 2\u00d7 o m\u00e1s. F8 en el juego alterna Moderno y Cl\u00e1sico.",
        ["Modern textures stay off until every part is in, so the game never shows a half pack."] = "Las texturas modernas se quedan apagadas hasta que est\u00e9n todas las partes, para que el juego nunca muestre un pack a medias.",
        ["Sharper, more detailed textures for the whole game, drawn with a key from your own game files. Shows at a render scale of 2\u00d7 or more; skip it on a weaker PC."] = "Texturas m\u00e1s n\u00edtidas y detalladas para todo el juego, generadas con una clave de tus propios archivos. Se ve a escala de renderizado de 2\u00d7 o m\u00e1s; s\u00e1ltatelo en un PC modesto.",
        ["Version {0}: {1} in {2} parts."] = "Versi\u00f3n {0}: {1} en {2} partes.",
        ["Looking for the newest texture pack\u2026"] = "Buscando el pack de texturas m\u00e1s nuevo\u2026",
        ["You can close the launcher or play in the meantime; the download resumes where it stopped."] = "Puedes cerrar el launcher o jugar mientras; la descarga contin\u00faa donde se qued\u00f3.",
        ["30 fps \u00b7 720p \u00b7 as on Xbox"] = "30 fps \u00b7 720p \u00b7 como en Xbox",
        ["60 fps \u00b7 1440p \u00b7 sharper textures, detailed models"] = "60 fps \u00b7 1440p \u00b7 texturas m\u00e1s n\u00edtidas, modelos detallados",
        ["30 FPS cap"] = "Tope 30 FPS",
        ["60 FPS cap"] = "Tope 60 FPS",
        ["120 FPS cap \u00b7 experimental"] = "Tope 120 FPS \u00b7 experimental",
        ["144 FPS cap \u00b7 experimental"] = "Tope 144 FPS \u00b7 experimental",
        ["165 FPS cap \u00b7 experimental"] = "Tope 165 FPS \u00b7 experimental",
        ["240 FPS cap \u00b7 experimental"] = "Tope 240 FPS \u00b7 experimental",
        ["Unlimited \u00b7 experimental"] = "Sin l\u00edmite \u00b7 experimental",
        ["Unlimited"] = "Sin l\u00edmite",
        ["Starting\u2026"] = "Empezando\u2026",
        ["Scanning disc for the GDFX header\u2026"] = "Escaneando el disco buscando la cabecera GDFX\u2026",
        ["Extracting data/audio"] = "Extrayendo data/audio",
        ["Extracting default.xex"] = "Extrayendo default.xex",
        ["Extracting default.xex ({0})\u2026"] = "Extrayendo default.xex ({0})\u2026",
        ["Extraction stopped."] = "Extracci\u00f3n detenida.",
        ["ISO not found."] = "ISO no encontrada.",
        ["No default.xex found at the root of this ISO."] = "No hay default.xex en la ra\u00edz de esta ISO.",
        ["{0} has no signature in its release, so it wasn't installed."] = "{0} no tiene firma en su release, as\u00ed que no se instal\u00f3.",
        ["{0} isn't signed by Project Sparrow, so it wasn't installed."] = "{0} no lo firma Project Sparrow, as\u00ed que no se instal\u00f3.",
        ["No release information for {0}."] = "No hay informaci\u00f3n de release para {0}.",
        ["Choose"] = "Elegir",
        ["COPYING"] = "COPIANDO",
        ["READING"] = "LEYENDO",
        ["DISC IMAGE"] = "IMAGEN DE DISCO",
        ["TO UPDATE"] = "PARA ACTUALIZAR",
        ["ANOTHER DISC"] = "OTRO DISCO",
        ["dev build"] = "build de desarrollo",
        ["\u2022 The last 3 game logs and the last 5 performance logs\n\u2022 Version, channel and edition\n\u2022 Your settings files (no saves)\n\u2022 Processor, memory, graphics card, driver and Windows version"] = "\u2022 Los \u00faltimos 3 logs del juego and los \u00faltimos 5 logs de rendimiento\n\u2022 Versi\u00f3n, canal y edici\u00f3n\n\u2022 Tus archivos de ajustes (sin partidas)\n\u2022 Procesador, memoria, tarjeta gr\u00e1fica, drivers y versi\u00f3n de Windows",
        ["\u2022 The last 3 game logs and the last 5 performance logs\n\u2022 Version, channel and edition\n\u2022 Your settings files (no saves)\n\u2022 Processor, memory, graphics card, driver and Windows version"] = "Los \u00faltimos 3 logs del juego y los \u00faltimos 5 logs de rendimiento\nVersi\u00f3n, canal y edici\u00f3n\nTus archivos de ajustes (sin partidas)\nProcesador, memoria, tarjeta gr\u00e1fica, drivers y versi\u00f3n de Windows",
        ["More detailed characters, creatures and objects for Enhanced, built from your own game files on this PC."] = "Personajes, criaturas y objetos m\u00e1s detallados para Mejorado, construidos con tus propios archivos del juego en este PC.",
        ["Using a local model pack (PROJECT_SPARROW_MODELS)."] = "Usando un pack de modelos local (PROJECT_SPARROW_MODELS).",
        ["The local model pack folder is empty."] = "La carpeta del pack de modelos local est\u00e1 vac\u00eda.",
        ["Version {0}: download stopped part-way."] = "Versi\u00f3n {0}: la descarga se qued\u00f3 a medias.",
        ["Version {0} is available."] = "La versi\u00f3n {0} est\u00e1 disponible.",
        ["Resume"] = "Continuar",
        ["Update"] = "Actualizar",
        ["No model pack has been published yet."] = "Todav\u00eda no hay pack de modelos publicado.",
        ["Detailed models installed ({0} models). They show when you play Enhanced."] = "Modelos detallados instalados ({0} modelos). Se ven al jugar en Mejorado.",
        ["Version {0} installed ({1}, {2} parts)."] = "Versi\u00f3n {0} instalada ({1}, {2} partes).",
        ["No texture pack has been published yet."] = "Todav\u00eda no hay pack de texturas publicado.",
        ["Sharper, more detailed textures for the whole game, drawn with a key from your own game files. Around 6 GB; downloads in parts and can be paused."] = "Texturas m\u00e1s n\u00edtidas y detalladas para todo el juego, generadas con una clave de tus propios archivos. Unos 6 GB; se descarga en partes y se puede pausar.",
        ["Version {0}: {1} of {2} parts still to download ({3})."] = "Versi\u00f3n {0}: faltan por descargar {1} de {2} partes ({3}).",
        ["Version {0} is available: {1} parts changed ({2})."] = "La versi\u00f3n {0} est\u00e1 disponible: {1} partes cambiadas ({2}).",
        ["Building the detailed models: "] = "Construyendo los modelos detallados: ",
        ["{0} \u00b7 {1} of {2}"] = "{0} \u00b7 {1} de {2}",
        ["{0} \u00b7 checking"] = "{0} \u00b7 comprobando",
        ["{0} \u00b7 unpacking"] = "{0} \u00b7 desempaquetando",
        ["{0} \u00b7 installed"] = "{0} \u00b7 instalada",
        ["{0} \u00b7 failed"] = "{0} \u00b7 fall\u00f3",
        ["{0} \u00b7 waiting"] = "{0} \u00b7 esperando",
        ["60 fps \u00b7 sharper textures, detailed models"] = "60 fps \u00b7 texturas m\u00e1s n\u00edtidas, modelos detallados",
        ["Original edition"] = "Edici\u00f3n Original",
        ["Enhanced edition"] = "Edici\u00f3n Mejorado",
        ["{0} selected."] = "Se seleccion\u00f3 {0}.",
        ["{0} selected. The detailed models aren't installed yet (Settings > Detailed models), so the original models show for now."] = "Se seleccion\u00f3 {0}. Los modelos detallados no est\u00e1n instalados todav\u00eda (Ajustes > Modelos detallados), as\u00ed que por ahora se ven los modelos originales.",
        ["Update {0} is ready."] = "La versi\u00f3n {0} est\u00e1 lista.",
        ["You're up to date."] = "Est\u00e1s al d\u00eda.",
        ["Couldn't check for updates."] = "No se pudo buscar actualizaciones.",
        ["Close Fable II first, then restart to update."] = "Cierra Fable II primero, y reinicia para actualizar.",
        ["Couldn't install the update: "] = "No se pudo instalar la actualizaci\u00f3n: ",
        ["Switched to Beta. Checking for beta updates\u2026"] = "Cambiado a Beta. Buscando actualizaciones beta\u2026",
        ["Switched to Stable."] = "Cambiado a Estable.",
        ["Stopped copying the disc."] = "Se detuvo la copia del disco.",
        ["Copied {0} files ({1}) from {2}. Modern textures can be downloaded from Settings."] = "Se copiaron {0} archivos ({1}) de {2}. Las texturas modernas se pueden descargar desde Ajustes.",
        ["Saved {0} to your desktop. Attach it to the GitHub issue that just opened."] = "Se guard\u00f3 {0} en tu escritorio. Adj\u00fantalo a la incidencia de GitHub que se abri\u00f3.",
        ["Moving your data. This can take a few minutes for the game files\u2026"] = "Moviendo tus datos. Puede tardar unos minutos por los archivos del juego\u2026",
        ["Moved. Your data now lives in {0}."] = "Listo. Tus datos viven ahora en {0}.",
        ["That folder doesn't have default.xex and a data folder."] = "Esa carpeta no tiene default.xex ni una carpeta de datos.",
        ["Using the game files in {0}."] = "Usando los archivos del juego de {0}.",
        ["Shader cache cleared. The first few minutes may stutter while it rebuilds."] = "Cach\u00e9 de shaders vaciada. Los primeros minutos pueden ir a tirones mientras se reconstruye.",
        ["Couldn't clear the cache. Close the game first, then try again."] = "No se pudo vaciar la cach\u00e9. Cierra el juego primero y prueba de nuevo.",
    };

    private static Dictionary<string, string>? _reverse;

    public static void Set(string language) => Current = language == "es" ? "es" : "en";

    private static Dictionary<string, string> Map =>
        Current == "es" ? Es : (_reverse ??= Es.GroupBy(p => p.Value).ToDictionary(g => g.Key, g => g.Last().Key));

    /// <summary>Translates a fixed source string (or an already-translated one) to
    /// the current language. {0} placeholders keep their argument order.</summary>
    public static string T(string s)
    {
        if (string.IsNullOrEmpty(s)) return s;
        return Map.TryGetValue(s, out string? translated) ? translated : s;
    }

    public static string T(string s, params object[] args) => string.Format(T(s), args);

    /// <summary>Runtime labels built from data ("GOTY Spain detected",
    /// "Incomplete GOTY files"). Translates the two recurring sentence shapes.
    /// </summary>
    public static string TLabel(string s)
    {
        var translated = T(s);
        if (!string.Equals(translated, s, StringComparison.Ordinal)) return translated;
        if (Current != "es") return s;
        if (s.EndsWith(" detected", StringComparison.Ordinal)) return s[..^" detected".Length] + " detectado";
        if (s.StartsWith("Incomplete ", StringComparison.Ordinal) && s.EndsWith(" files", StringComparison.Ordinal))
            return "Archivos " + s["Incomplete ".Length..^" files".Length] + " incompletos";
        return s;
    }

    /// <summary>Walks the whole tree of the window and swaps every static text.
    /// Safe to call repeatedly: unknown strings pass through unchanged.</summary>
    public static void Apply(Window window)
    {
        if (window.Content is DependencyObject root) Walk(root);
        Walk(window);
    }

    private static void Walk(DependencyObject node)
    {
        switch (node)
        {
            case TextBlock tb:
                tb.Text = T(tb.Text);
                if (tb.Inlines != null)
                    foreach (var inline in tb.Inlines) if (inline is Run run) run.Text = T(run.Text);
                break;
            case HeaderedContentControl hc:
                if (hc.Header is string h) hc.Header = T(h);
                break;
            case ContentControl cc:
                if (cc.Content is string s) cc.Content = T(s);
                if (cc.ToolTip is string tip) cc.ToolTip = T(tip);
                break;
        }
        foreach (var child in LogicalTreeHelper.GetChildren(node).OfType<DependencyObject>()) Walk(child);
        if (node is Visual || node is System.Windows.Media.Media3D.Visual3D)
        {
            int visual = VisualTreeHelper.GetChildrenCount(node);
            for (int i = 0; i < visual; i++) Walk(VisualTreeHelper.GetChild(node, i));
        }
    }
}
