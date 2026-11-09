"""Live WASAPI loopback capture of system/game audio.

Uses PowerShell + inline C# (Add-Type) to drive Core Audio WASAPI loopback
(IAudioClient / IAudioCaptureClient COM interfaces). No external dependencies —
the C# interop definitions ship inside the script, mirroring the OCR approach.

The captured stream is downmixed to mono float32 (normalized -1.0..1.0),
written to a temp binary with a small header [sample_rate:i32, samples:i32],
then parsed by Python into :class:`AudioFrame` chunks that feed :class:`AudioMonitor`.

Note: endpoint selection uses ``EnumAudioEndpoints`` (first active render device)
rather than ``GetDefaultAudioEndpoint`` — more robust in headless/VM sessions
where no default endpoint is set.
"""

from __future__ import annotations

import contextlib
import struct
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from gfa.audio.capture import AudioFrame

_PS_SCRIPT = r'''
param([double]$Seconds = 0.25, [string]$OutPath = "")
$ErrorActionPreference = "Stop"

$csharp = @"
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;

namespace GFAAudio {
    // NOTE: vtable order (per mmdeviceapi.h): EnumAudioEndpoints, GetDefaultAudioEndpoint, GetDevice, ...
    [ComImport, Guid("a95664d2-9614-4f35-a746-de8db63617e6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IMMDeviceEnumerator {
        [PreserveSig] int EnumAudioEndpoints(int dataFlow, int stateMask, out IMMDeviceCollection collection);
        [PreserveSig] int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice device);
        [PreserveSig] int GetDevice([MarshalAs(UnmanagedType.LPWStr)] string id, out IMMDevice device);
    }

    [ComImport, Guid("0bd7a1be-7a1a-44db-8397-cc5392387b5e"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IMMDeviceCollection {
        [PreserveSig] int GetCount(out uint count);
        [PreserveSig] int Item(uint n, out IMMDevice device);
    }

    [ComImport, Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IMMDevice {
        [PreserveSig] int Activate([MarshalAs(UnmanagedType.LPStruct)] Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
    }

    [ComImport, Guid("1CB9AD4C-DBFA-4CDD-B8C7-07B19D3C88B5"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IAudioClient {
        [PreserveSig] int Initialize(int shareMode, int streamFlags, long bufferDuration, long periodicity, IntPtr format, Guid sessionId);
        [PreserveSig] int Reset();
        [PreserveSig] int StopClient();
        [PreserveSig] int StartClient();
        [PreserveSig] int GetService([MarshalAs(UnmanagedType.LPStruct)] Guid iid, int clsCtx, [MarshalAs(UnmanagedType.IUnknown)] out object ppv);
        [PreserveSig] int GetMixFormat(out IntPtr mixFormat);
    }

    [ComImport, Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IAudioCaptureClient {
        [PreserveSig] int GetBuffer(out IntPtr dataBuffer, out uint numFramesToRead, out int flags, out long devicePosition, out long qpcPosition);
        [PreserveSig] int ReleaseBuffer(uint numFramesRead);
        [PreserveSig] int GetNextPacketSize(out uint numFramesInNextPacket);
    }

    public static class Loopback {
        static readonly Guid IID_IAudioClient = new Guid("1CB9AD4C-DBFA-4CDD-B8C7-07B19D3C88B5");
        static readonly Guid IID_IAudioCaptureClient = new Guid("5CDF2C82-841E-4546-9722-0CF74078229A");
        const int CLSCTX_ALL = 23;
        const int AUDCLNT_STREAMFLAGS_LOOPBACK = 0x100;
        const int DEVICE_STATE_ACTIVE = 1;

        static IMMDevice PickRenderDevice() {
            var enumerator = (IMMDeviceEnumerator)Activator.CreateInstance(
                Type.GetTypeFromCLSID(new Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")));
            IMMDeviceCollection coll;
            int hr = enumerator.EnumAudioEndpoints(0, DEVICE_STATE_ACTIVE, out coll); // eRender, active only
            if (hr != 0) throw new COMException("EnumAudioEndpoints failed: 0x" + hr.ToString("X8"));
            uint count;
            hr = coll.GetCount(out count);
            if (hr != 0) throw new COMException("GetCount failed: 0x" + hr.ToString("X8"));
            if (count == 0) throw new COMException("No active render audio endpoints found");
            IMMDevice dev;
            hr = coll.Item(0, out dev);
            if (hr != 0) throw new COMException("GetItem failed: 0x" + hr.ToString("X8"));
            return dev;
        }

        public static void Capture(double seconds, string outPath) {
            var device = PickRenderDevice();

            object clientRaw;
            int hr = device.Activate(IID_IAudioClient, CLSCTX_ALL, IntPtr.Zero, out clientRaw);
            if (hr != 0) throw new COMException("Activate failed: 0x" + hr.ToString("X8"));
            var client = (IAudioClient)clientRaw;

            IntPtr fmtPtr;
            hr = client.GetMixFormat(out fmtPtr);
            if (hr != 0) throw new COMException("GetMixFormat failed: 0x" + hr.ToString("X8"));

            int formatTag = Marshal.ReadInt16(fmtPtr, 0) & 0xFFFF;
            if (formatTag == 0xFFFE) { // WAVE_FORMAT_EXTENSIBLE
                int subTag = Marshal.ReadInt32(fmtPtr, 24) & 0xFFFF;
                formatTag = subTag;
            }
            int channels = Math.Max(1, (int)Marshal.ReadInt16(fmtPtr, 2));
            int sampleRate = Marshal.ReadInt32(fmtPtr, 4);
            int bits = Marshal.ReadInt16(fmtPtr, 14);
            if (bits != 16 && bits != 32) throw new NotSupportedException("Only 16/32-bit formats supported, got " + bits);
            bool isFloat = (formatTag == 3);

            Guid empty = Guid.Empty;
            hr = client.Initialize(0, AUDCLNT_STREAMFLAGS_LOOPBACK, 500 * 10000, 0, fmtPtr, empty);
            if (hr != 0) throw new COMException("Initialize failed: 0x" + hr.ToString("X8"));
            Marshal.FreeCoTaskMem(fmtPtr);

            object captureRaw;
            hr = client.GetService(IID_IAudioCaptureClient, CLSCTX_ALL, out captureRaw);
            if (hr != 0) throw new COMException("GetService failed: 0x" + hr.ToString("X8"));
            var capture = (IAudioCaptureClient)captureRaw;

            var mono = new List<float>();

            hr = client.StartClient();
            if (hr != 0) throw new COMException("StartClient failed: 0x" + hr.ToString("X8"));

            long start = Environment.TickCount;
            long expectedMs = (long)(seconds * 1000.0);
            int bytesPerSample = bits / 8;

            while (Environment.TickCount - start < expectedMs) {
                Thread.Sleep(20);
                uint packet = 0;
                while (capture.GetNextPacketSize(out packet) == 0 && packet > 0) {
                    IntPtr data; uint frames; int flags; long pos, qpc;
                    hr = capture.GetBuffer(out data, out frames, out flags, out pos, out qpc);
                    if (hr != 0) throw new COMException("GetBuffer failed: 0x" + hr.ToString("X8"));
                    bool silent = (flags & 2) != 0; // AUDCLNT_BUFFERFLAGS_SILENT
                    long stride = (long)channels * bytesPerSample;
                    long totalBytes = (long)frames * stride;
                    byte[] raw = new byte[totalBytes];
                    Marshal.Copy(data, raw, 0, (int)totalBytes);
                    for (int f = 0; f < frames; f++) {
                        long frameOff = f * stride;
                        float v = 0f;
                        if (!silent) {
                            for (int c = 0; c < channels; c++) {
                                int off = (int)(frameOff + c * bytesPerSample);
                                if (isFloat) v += BitConverter.ToSingle(raw, off);
                                else v += BitConverter.ToInt16(raw, off) / 32768f;
                            }
                            v /= channels;
                        }
                        mono.Add(v);
                    }
                    capture.ReleaseBuffer(frames);
                }
            }

            client.StopClient();

            // If nothing was captured (e.g. no audio played), emit digital silence
            int expectedSamples = (int)(seconds * sampleRate);
            while (mono.Count < expectedSamples) mono.Add(0f);

            using (var fs = new FileStream(outPath, FileMode.Create, FileAccess.Write))
            using (var bw = new BinaryWriter(fs)) {
                bw.Write(sampleRate);
                bw.Write(mono.Count);
                byte[] buf = new byte[4];
                foreach (float s in mono) {
                    buf = BitConverter.GetBytes(s);
                    bw.Write(buf, 0, 4);
                }
            }
        }
    }
}
"@

$types = [PSCustomObject]@{
    ReferencedAssemblies = @("System.Runtime.InteropServices")
}
Add-Type -TypeDefinition $csharp -ReferencedAssemblies $types.ReferencedAssemblies

[GFAAudio.Loopback]::Capture([double]$Seconds, $OutPath)
"ok"
'''


class WasapiLoopbackSource:
    """Live system/game audio capture via WASAPI loopback.

    Implements :class:`gfa.audio.capture.AudioSource` — ``read()`` captures
    a short chunk (default 250ms) and returns it as ``AudioFrame`` mono samples.

    Capture failures (e.g. no audio device) raise ``RuntimeError``; agents
    using an ``AudioMonitor`` around this source should treat that as
    "audio unavailable" rather than a hard crash.
    """

    def __init__(self, seconds: float = 0.25, timeout_s: float = 30.0, sample_rate_expected: int = 44100):
        self.seconds = seconds
        self.timeout_s = timeout_s
        self.expected_rate = sample_rate_expected
        self._script_path: Path | None = None

    # ------------------------------------------------------------------
    @staticmethod
    def is_available() -> bool:
        """True if PowerShell runs (required for the C# interop script)."""
        try:
            r = subprocess.run(
                ["powershell", "-Command", "'ok'"],
                capture_output=True, text=True, timeout=10,
            )
            return r.returncode == 0 and "ok" in r.stdout
        except Exception:  # noqa: BLE001
            return False

    # ------------------------------------------------------------------
    def _write_script(self) -> Path:
        if self._script_path is None:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".ps1", delete=False, encoding="utf-8") as f:
                f.write(_PS_SCRIPT)
                self._script_path = Path(f.name)
        return self._script_path

    def capture(self, seconds: float | None = None) -> list[AudioFrame]:
        """Capture one chunk (default from constructor) of loopback audio."""
        dur = seconds if seconds is not None else self.seconds
        script = self._write_script()
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            out_path = Path(f.name)
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-File", str(script),
                 "-Seconds", str(dur), "-OutPath", str(out_path.resolve())],
                capture_output=True, text=True, timeout=self.timeout_s,
            )
            if result.returncode != 0 or not out_path.exists():
                raise RuntimeError(f"WASAPI capture failed: {result.stderr.strip()[:500]}")
            data = out_path.read_bytes()
            if len(data) < 8:
                raise RuntimeError(f"WASAPI capture returned truncated data ({len(data)} bytes)")
            sample_rate, count = struct.unpack_from("<ii", data, 0)
            samples_blob = data[8:]
            n = min(count, len(samples_blob) // 4)
            samples = list(struct.unpack_from(f"<{n}f", samples_blob, 0)) if n else []
            return [AudioFrame(samples=samples,
                               sample_rate=sample_rate if sample_rate > 0 else self.expected_rate,
                               source="loopback")]
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"WASAPI capture timed out after {self.timeout_s}s") from exc
        finally:
            out_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    def read(self) -> list[AudioFrame]:
        return self.capture(self.seconds)

    def close(self) -> None:
        if self._script_path is not None:
            with contextlib.suppress(Exception):  # noqa: BLE001
                self._script_path.unlink(missing_ok=True)
            self._script_path = None


def make_source(seconds: float = 0.25, timeout_s: float = 30.0,
                source_factory: Callable[[], WasapiLoopbackSource] | None = None) -> WasapiLoopbackSource | None:
    """Return a live WASAPI source if available, else None."""
    if source_factory is not None:
        return source_factory()
    if WasapiLoopbackSource.is_available():
        return WasapiLoopbackSource(seconds=seconds, timeout_s=timeout_s)
    return None
