#!/usr/bin/env python
"""Offline build of Teclado Libre (AOSP LatinIME 2.3.6 + Spanish) for Android 2.3.

Uses explicit local tools only: JDK, Android build-tools (aapt, zipalign, d8,
apksigner) and the API 10 android.jar. Signing key and password file must be
outside this repository. The dictionary engine (native/, AOSP 2.3.6 JNI) is built
with the NDK r10e by native/build_native.py and packed in the APK, so the
keyboard no longer needs the phone maker's /system/lib/libjni_latinime.so.
"""
import argparse, hashlib, os, pathlib, shutil, subprocess, sys, zipfile

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for a in ('--jdk', '--build-tools', '--android-jar', '--keystore', '--storepass-file', '--ndk'):
        p.add_argument(a, required=True)
    p.add_argument('--alias', default='music')
    p.add_argument('--wordlist', help='AOSP es_wordlist.combined.gz; regenerates raw-es/main.dict')
    p.add_argument('--max-words', type=int, default=60000)
    a = p.parse_args()
    root = pathlib.Path(__file__).resolve().parent
    for secret in (a.keystore, a.storepass_file):
        if pathlib.Path(secret).resolve().is_relative_to(root):
            raise SystemExit('Signing files must be outside the source tree')
    sfx = '.exe' if os.name == 'nt' else ''
    jdk, bt = pathlib.Path(a.jdk), pathlib.Path(a.build_tools)
    java, javac = jdk / 'bin' / ('java' + sfx), jdk / 'bin' / ('javac' + sfx)
    aapt, align = bt / ('aapt' + sfx), bt / ('zipalign' + sfx)
    d8, signer = bt / 'lib' / 'd8.jar', bt / 'lib' / 'apksigner.jar'
    out = root / 'build'
    if out.exists(): shutil.rmtree(out)
    for d in ('gen', 'classes', 'dex'): (out / d).mkdir(parents=True)
    run = lambda *c: subprocess.run([str(x) for x in c], cwd=root, check=True)
    dict_path = root / 'java/res/raw-es/main.dict'
    if a.wordlist:
        run('python', root / 'tools/make_gb_dict.py', a.wordlist, dict_path, '--max-words', a.max_words)
    # Source keeps the AOSP package (resource namespaces, JNI class names); only the installed package is renamed.
    common = ('-M', root / 'java/AndroidManifest.xml', '-S', root / 'java/res', '-I', a.android_jar,
              '--rename-manifest-package', 'org.libreteclado.latin')
    run(aapt, 'package', '-f', '-m', '-J', out / 'gen', *common)
    srcs = [*sorted((root / 'java/src').rglob('*.java')), *sorted((root / 'common-src').rglob('*.java')), *sorted((out / 'gen').rglob('*.java'))]
    run(javac, '-encoding', 'UTF-8', '-source', '7', '-target', '7', '-g:none', '-nowarn', '-Xlint:-options',
        '-bootclasspath', a.android_jar, '-d', out / 'classes', *srcs)
    run(java, '-cp', d8, 'com.android.tools.r8.D8', '--release', '--min-api', '9', '--lib', a.android_jar,
        '--output', out / 'dex', *sorted((out / 'classes').rglob('*.class')))
    unsigned, aligned, apk = out / 'unsigned.apk', out / 'aligned.apk', out / 'Teclado-Libre.apk'
    # Store the dictionary uncompressed (no inflate buffer at load) and keep only es/en and mdpi resources.
    run(aapt, 'package', '-f', '-0', 'dict', '-c', 'es,en,mdpi', *common, '-F', unsigned)
    sys.path.insert(0, str(root / 'native'))
    import build_native
    libdir = build_native.build(a.ndk, out / 'native')
    def add(z, path, name):  # fixed timestamp: the same sources give the same APK
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, path.read_bytes())
    with zipfile.ZipFile(unsigned, 'a', zipfile.ZIP_DEFLATED) as z:
        add(z, out / 'dex/classes.dex', 'classes.dex')
        for so in sorted(libdir.rglob('*.so')):
            add(z, so, so.relative_to(libdir.parent).as_posix())  # lib/armeabi-v7a/libjni_latinime.so
    run(align, '-f', '4', unsigned, aligned)
    run(java, '-jar', signer, 'sign', '--ks', a.keystore, '--ks-key-alias', a.alias, '--ks-pass', 'file:' + a.storepass_file,
        '--min-sdk-version', '9', '--v1-signing-enabled', 'true', '--v2-signing-enabled', 'false', '--v3-signing-enabled', 'false',
        '--out', apk, aligned)
    run(java, '-jar', signer, 'verify', '--min-sdk-version', '9', apk)
    print('APK:', apk, apk.stat().st_size, 'bytes, SHA256', hashlib.sha256(apk.read_bytes()).hexdigest())

if __name__ == '__main__':
    main()
