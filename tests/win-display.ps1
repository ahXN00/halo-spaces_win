# Bildschirm der Windows-VM auf 1920 × 1080 stellen (ohne Fenster der VM wählt
# Parallels sonst 1024 × 768 – das 1500 × 900 große Testfenster passt dann nicht).
# Läuft vor jedem Testlauf in der VM (halo_test.py --vm, über prlctl exec
# --current-user); schreibt die Größe des Bildschirms nach <Ausgabe>.
param([string]$Ausgabe, [int]$Breite = 1920, [int]$Hoehe = 1080)
$code = @"
using System;
using System.Runtime.InteropServices;
public class HaloDisplay {
  [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
  public struct DEVMODE {
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string dmDeviceName;
    public short dmSpecVersion; public short dmDriverVersion; public short dmSize; public short dmDriverExtra; public int dmFields;
    public int dmPositionX; public int dmPositionY; public int dmDisplayOrientation; public int dmDisplayFixedOutput;
    public short dmColor; public short dmDuplex; public short dmYResolution; public short dmTTOption; public short dmCollate;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string dmFormName;
    public short dmLogPixels; public int dmBitsPerPel; public int dmPelsWidth; public int dmPelsHeight; public int dmDisplayFlags; public int dmDisplayFrequency;
    public int dmICMMethod; public int dmICMIntent; public int dmMediaType; public int dmDitherType; public int dmReserved1; public int dmReserved2; public int dmPanningWidth; public int dmPanningHeight;
  }
  [DllImport("user32.dll")] public static extern int EnumDisplaySettings(string dev, int mode, ref DEVMODE dm);
  [DllImport("user32.dll")] public static extern int ChangeDisplaySettings(ref DEVMODE dm, int flags);
  public static int Set(int w, int h) {
    DEVMODE dm = new DEVMODE(); dm.dmSize = (short)Marshal.SizeOf(typeof(DEVMODE));
    EnumDisplaySettings(null, -1, ref dm);
    if (dm.dmPelsWidth == w && dm.dmPelsHeight == h) return 0;
    dm.dmPelsWidth = w; dm.dmPelsHeight = h; dm.dmFields = 0x80000 | 0x100000;
    return ChangeDisplaySettings(ref dm, 0);
  }
}
"@
Add-Type -TypeDefinition $code
$r = [HaloDisplay]::Set($Breite, $Hoehe)
Add-Type -AssemblyName System.Windows.Forms
$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
"$r $($b.Width) $($b.Height)" | Out-File -Encoding ascii $Ausgabe
