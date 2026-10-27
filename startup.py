"""Makes "Claude Usage.exe", a copy of pythonw.exe that names itself "Claude Usage" in Task Manager, and the Startup
shortcut that runs widget.py with it. Run it again after reinstalling or moving Python, or after moving this folder:
python startup.py
"""
import ctypes
import msvcrt
import shutil
import struct
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

NAME = "Claude Usage"
SHORTCUT = "Claude usage widget"
RT_VERSION, ENGLISH_US, UNICODE = 16, 0x0409, 1200

kernel32, version = ctypes.windll.kernel32, ctypes.windll.version
kernel32.BeginUpdateResourceW.restype = wintypes.HANDLE
kernel32.BeginUpdateResourceW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL]
kernel32.UpdateResourceW.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, wintypes.WORD,
                                     ctypes.c_void_p, wintypes.DWORD]
kernel32.EndUpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.BOOL]


def node(key, value=b"", text=False, children=()):
    """One block of a Windows version resource: header, key, value, then child blocks, each on a 4-byte boundary."""
    body = (key + "\0").encode("utf-16-le")
    body += b"\0" * (-(6 + len(body)) % 4) + value
    for child in children:
        body += b"\0" * (-(6 + len(body)) % 4) + child
    return struct.pack("<HHH", 6 + len(body), len(value) // 2 if text else len(value), int(text)) + body


def fixed_info(exe):
    """The binary file-version block of exe, kept as it is so the copy reports Python's own version."""
    size = version.GetFileVersionInfoSizeW(str(exe), None)
    data = ctypes.create_string_buffer(size)
    version.GetFileVersionInfoW(str(exe), 0, size, data)
    start = data.raw.find(struct.pack("<I", 0xFEEF04BD))
    return data.raw[start:start + 52]


def version_resource(exe, name):
    python = ".".join(map(str, sys.version_info[:3]))
    # Some readers (.NET's among them) show nothing unless FileVersion is there too.
    strings = [node(key, (value + "\0").encode("utf-16-le"), text=True) for key, value in (
        ("FileDescription", name), ("ProductName", name), ("InternalName", name),
        ("FileVersion", python), ("ProductVersion", python))]
    table = node(f"{ENGLISH_US:04x}{UNICODE:04x}", text=True, children=strings)
    translation = node("Translation", struct.pack("<HH", ENGLISH_US, UNICODE))
    return node("VS_VERSION_INFO", fixed_info(exe), children=[
        node("StringFileInfo", text=True, children=[table]),
        node("VarFileInfo", text=True, children=[translation])])


def make_exe():
    # The copy sits beside pythonw.exe because it needs that folder's Python DLL and standard library.
    source = Path(sys.base_prefix) / "pythonw.exe"
    target = source.with_name(NAME + ".exe")
    shutil.copyfile(source, target)
    # Python's signature wouldn't match the changed file, and a broken signature looks worse to Windows than none.
    with open(target, "r+b") as file:
        ctypes.windll.imagehlp.ImageRemoveCertificate(wintypes.HANDLE(msvcrt.get_osfhandle(file.fileno())), 0)
    data = version_resource(source, NAME)
    handle = kernel32.BeginUpdateResourceW(str(target), False)
    # Python files its block under US English too, so this replaces it rather than adding a second one.
    if not kernel32.UpdateResourceW(handle, RT_VERSION, 1, ENGLISH_US, data, len(data)) or \
            not kernel32.EndUpdateResourceW(handle, False):
        raise OSError(ctypes.WinError())
    return target


def make_shortcut(exe):
    here = Path(__file__).resolve().parent
    script = (f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut(\"$([Environment]::GetFolderPath('Startup'))"
              f"\\{SHORTCUT}.lnk\"); $s.TargetPath = '{exe}'; $s.Arguments = 'widget.py'; "
              f"$s.WorkingDirectory = '{here}'; $s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True)


if __name__ == "__main__":
    exe = make_exe()
    make_shortcut(exe)
    print(f"Made {exe} and the Startup shortcut \"{SHORTCUT}\".")
