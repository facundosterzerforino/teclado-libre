#!/usr/bin/env python
"""Build native/libjni_latinime.so (the AOSP 2.3.6 dictionary engine) for
armeabi-v7a, Android 2.3, from the sources in this folder.

Before this, Teclado Libre used the copy that came in the phone's
/system/lib (built by the phone maker). Now the APK carries its own, built
here, and Android loads the one inside the app first.

Uses only the NDK r10e GCC 4.9 toolchain and the android-9 platform; no
ndk-build or make. Output: <out>/lib/armeabi-v7a/libjni_latinime.so
"""
import argparse, hashlib, os, pathlib, subprocess, sys

FLAGS = ['-march=armv7-a', '-mfloat-abi=softfp', '-mfpu=vfpv3-d16', '-mthumb',
         '-O2', '-fPIC', '-fno-exceptions', '-fno-rtti', '-fvisibility=hidden',
         '-ffunction-sections', '-fdata-sections', '-fno-strict-aliasing',
         '-Wall', '-Wno-unused-variable', '-Wno-unused-but-set-variable', '-DANDROID', '-DNDEBUG']


def build(ndk, out):
    ndk, out = pathlib.Path(ndk), pathlib.Path(out)
    native = pathlib.Path(__file__).resolve().parent
    if (ndk / 'RELEASE.TXT').read_text().split()[0] != 'r10e':
        raise SystemExit('NDK r10e required')
    host = 'windows-x86_64' if os.name == 'nt' else 'linux-x86_64'
    sfx = '.exe' if os.name == 'nt' else ''
    bindir = ndk / 'toolchains/arm-linux-androideabi-4.9/prebuilt' / host / 'bin'
    gxx, strip = bindir / ('arm-linux-androideabi-g++' + sfx), bindir / ('arm-linux-androideabi-strip' + sfx)
    sysroot = '--sysroot=' + str(ndk / 'platforms/android-9/arch-arm')
    objdir = out / 'obj'
    objdir.mkdir(parents=True, exist_ok=True)
    sources = [native / 'jni/com_android_inputmethod_latin_BinaryDictionary.cpp',
               native / 'src/dictionary.cpp', native / 'src/char_utils.cpp']
    objs = []
    for src in sources:
        obj = objdir / (src.stem + '.o')
        r = subprocess.run([str(gxx), sysroot, *FLAGS, '-I', str(native / 'src'), '-c', str(src), '-o', str(obj)],
                           capture_output=True, text=True)
        if r.stderr.strip():
            print('--', src.name, '\n' + r.stderr.strip(), file=sys.stderr)
        if r.returncode:
            raise SystemExit('native compile failed')
        objs.append(obj)
    lib = out / 'lib' / 'armeabi-v7a' / 'libjni_latinime.so'
    lib.parent.mkdir(parents=True, exist_ok=True)
    # Like the stock build: only bionic's tiny libstdc++.so (operator new/delete),
    # no exceptions, RTTI or STL (--no-undefined fails the link if that changes).
    subprocess.run([str(gxx), sysroot, '-shared', '-nodefaultlibs', '-Wl,-soname,libjni_latinime.so',
                    '-Wl,--gc-sections', '-Wl,--no-undefined', '-Wl,-z,noexecstack',
                    '-Wl,--build-id=none', '-march=armv7-a', '-Wl,--fix-cortex-a8',
                    '-o', str(lib), *[str(o) for o in objs], '-lc', '-lstdc++', '-lm', '-lgcc'], check=True)
    subprocess.run([str(strip), '--strip-unneeded', str(lib)], check=True)
    print('native:', lib, lib.stat().st_size, 'bytes, SHA256', hashlib.sha256(lib.read_bytes()).hexdigest())
    return out / 'lib'


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ndk', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    build(a.ndk, a.out)
