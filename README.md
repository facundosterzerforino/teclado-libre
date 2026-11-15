# Teclado Libre (AOSP LatinIME 2.3.6 + Spanish)

Android keyboard for Android 2.3 (Gingerbread) phones, based on the unmodified
AOSP `LatinIME` at tag `android-2.3.6_r1` (commit `ec622ced`), with:

- **Spanish suggestions and auto-correction**: `java/res/raw-es/main.dict`, the
  60,000 most frequent words (664,513 bytes) of the AOSP Spanish word list
  (`dictionaries/es_wordlist.combined.gz` from AOSP LatinIME `main`, Apache 2.0,
  SHA-256 `889ad52bce2933e2a30a0560b8d5a76f5334500e776a7db7c7cb3e9e79fc2652`),
  converted to the header-less Gingerbread binary format by `tools/make_gb_dict.py`.
  AOSP 2.3 only shipped a 34-byte placeholder dictionary, and the newer AOSP
  dictionaries use a format the 2.3 native code cannot read.
- **Spanish layout with an `ñ` key** (`java/res/xml-es/`), used when the input
  language is Spanish. Accents are on long-press, and suggestions match
  unaccented typing (`cancion` -> `Canción`).
- **Lower memory**: the dictionary is stored uncompressed and memory-mapped
  from the APK (`BinaryDictionary.mapDictionary`) instead of copied into a
  private buffer; it falls back to the original copy if mapping fails.
- **Installs next to the system keyboard** as `org.libreteclado.latin`
  (renamed at packaging time; Java packages unchanged).
- **No microphone permission** (voice input needed Google services). No
  INTERNET permission. Kept: vibrate, user dictionary, contacts (local
  name suggestions).

The APK reuses the phone's `/system/lib/libjni_latinime.so`, which exposes
the same AOSP 2.3 JNI (`openNative`, `getSuggestionsNative`, ...), so no NDK
build is needed. This only works on Android 2.3 builds that include the
stock LatinIME native library.

## Measured on a Motorola XT550 (Android 2.3.6)

Keyboard process PSS with the keyboard shown in a new SMS (no typing), median of 3:

| Keyboard | Storage | RAM (PSS) | Suggestions |
|---|---|---|---|
| Swype 3.26 (stock) | 4.0 MB | 7.6 MB | yes (closed source) |
| Stock LatinIME 2.3.6 | 0.56 MB | 3.8 MB | none (placeholder dictionary) |
| Teclado Libre, dictionary copied | 1.4 MB | 6.6 MB | Spanish |
| **Teclado Libre, dictionary mapped** | **1.25 MB APK + 0.24 MB dex** | **5.35 MB** | **Spanish** |

After typing a word, Teclado Libre measured about 5.6-5.9 MB, because the
contacts and learned-word dictionaries are loaded on first use.

Small, device-specific measurements, not a general benchmark.

## Build (offline)

```
python build.py --jdk JDK_HOME --build-tools BUILD_TOOLS_30 \
  --android-jar android-10/android.jar \
  --keystore /outside/repo/key.jks --storepass-file /outside/repo/pass \
  [--wordlist es_wordlist.combined.gz --max-words 60000]
python -m unittest discover -s tests
```

`common-src/` holds the two Apache-2.0 classes from AOSP
`platform/frameworks/ex` (`android-2.3.6_r1`) that the build system normally
links as `android-common`.

## License

Apache License 2.0, like AOSP LatinIME (see `java/NOTICE`). Changes are
listed in the commit history of the `teclado-es` branch.
