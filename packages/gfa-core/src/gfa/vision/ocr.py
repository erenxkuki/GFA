"""OCR via Windows built-in Media.Ocr (WinRT) invoked through PowerShell."""

from __future__ import annotations

import base64
import subprocess
import tempfile
from pathlib import Path


class WindowsOCR:
    """Extract text from images using Windows 10+ built-in OCR.

    No external dependencies — uses PowerShell + WinRT Windows.Media.Ocr.
    """

    _PS_SCRIPT = r'''
param([string]$ImagePath, [string]$Language = "en-US")
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]

function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($engine -eq $null) {
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new($Language))
}
$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])

$text = $result.Text
$lines = @()
foreach ($line in $result.Lines) { $lines += $line.Text }
[PSCustomObject]@{ text = $text; lines = $lines; region_count = @($result.Lines).Count } | ConvertTo-Json -Compress
'''

    @staticmethod
    def is_available() -> bool:
        try:
            r = subprocess.run(
                ["powershell", "-Command", "Add-Type -AssemblyName System.Runtime.WindowsRuntime; 'ok'"],
                capture_output=True, text=True, timeout=10,
            )
            return r.returncode == 0
        except Exception:
            return False

    @staticmethod
    def extract_text(image_path: str | Path) -> dict:
        """Extract text from an image file. Returns {text, lines, region_count}."""
        path = Path(image_path)
        if not path.exists():
            return {"text": "", "lines": [], "region_count": 0, "error": "file not found"}
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".ps1", delete=False, encoding="utf-8") as f:
                f.write(WindowsOCR._PS_SCRIPT)
                script_path = f.name
            result = subprocess.run(
                ["powershell", "-NoProfile", "-File", script_path, "-ImagePath", str(path.resolve())],
                capture_output=True, text=True, timeout=30,
            )
            Path(script_path).unlink(missing_ok=True)
            if result.returncode != 0 or not result.stdout.strip():
                return {"text": "", "lines": [], "region_count": 0, "error": result.stderr.strip()[:500]}
            import json
            import re
            raw = result.stdout.strip()
            # Escape raw control characters that break JSON parsing
            clean = re.sub(r"[\x00-\x1f]", lambda m: "\\u%04x" % ord(m.group(0)), raw)
            return json.loads(clean)
        except subprocess.TimeoutExpired:
            return {"text": "", "lines": [], "region_count": 0, "error": "timeout"}
        except Exception as exc:  # noqa: BLE001
            return {"text": "", "lines": [], "region_count": 0, "error": str(exc)}

    @staticmethod
    def extract_from_frame(frame) -> dict:
        """Extract text from a CapturedFrame (saves to temp PNG first)."""
        from gfa.universal.capture import _encode_png_rgb
        # frame already has png_bytes
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(frame.png_bytes)
            tmp = f.name
        try:
            return WindowsOCR.extract_text(tmp)
        finally:
            Path(tmp).unlink(missing_ok=True)