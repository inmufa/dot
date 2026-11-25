# Speech gate (V0-speech)

Measurement only, CPU only. Stack: sherpa-onnx 2.0.3, Python 3.12, uv (`services/voice-worker`, scratch scripts in `services/voice-worker/scratch/`).
Machine: i7-12700K (20 threads), 14 GB RAM, all runs with `num_threads=4`, int8 STT models, no GPU.

## Decision

- STT: **Parakeet-TDT-0.6B-v2 int8**. Overall WER 5.85% vs 12.74% (Moonshine base) and 12.22% (whisper small.en). Fast enough (RTF 0.05).
- Moonshine base int8 is the fallback only if RAM gets tight: 2x faster, ~1/3 the RAM, but about 2x the WER.
- whisper small.en loses on every axis against Parakeet (5x slower, 2x WER). Drop it.
- TTS: **Kokoro fp32** (`kokoro-multi-lang-v1_0`), not int8. On this CPU the int8 build is 2.7x slower (RTF 0.57 vs 0.21) for 200 MB less RAM.
- Worst-case RAM with both loaded (Parakeet 60 s peak ~2.4 GB + Kokoro fp32 ~0.76 GB) is ~3.2 GB, inside the ~6 GB free budget. Not measured as one process.

## Models, licences, hashes

All SHA-256 checked against the Hugging Face LFS oids of the source repos (all matched). Files live in `models/voice/` (git-ignored).

| Model | Source repo | Licence | Check |
|---|---|---|---|
| Parakeet-TDT-0.6B-v2 int8 | csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8 | CC-BY-4.0 (attribution to NVIDIA required, add to THIRD_PARTY.md) | encoder 92a10bd9...a8b, decoder 4d097bae...f41, joiner 77a29f3e...428 |
| Kokoro v1.0 multi-lang fp32 | csukuangfj/kokoro-multi-lang-v1_0 (base hexgrad/Kokoro-82M) | Apache-2.0 (base card says apache-2.0; bundled LICENSE is Apache-2.0) | model.onnx b40f62b1...a11, voices.bin 1c5a5b98...c29 |
| Kokoro v1.0 multi-lang int8 | csukuangfj/kokoro-int8-multi-lang-v1_0 | Apache-2.0 | model.int8.onnx 75635ea3...95e, voices.bin same as fp32 |
| Moonshine base en int8 | csukuangfj/sherpa-onnx-moonshine-base-en-int8 | MIT (bundled LICENSE, upstream card mit) | 4 onnx files match |
| whisper small.en int8 | csukuangfj/sherpa-onnx-whisper-small.en | Apache-2.0 per HF card (upstream OpenAI repo is MIT) | enc/dec int8 match |

Kokoro "multi-lang v1.0" is the sherpa-onnx packaging of Kokoro v1.0 (82M params, English + Chinese voices). Voice used: sid 3.

## STT speed and RAM

Clips built by concatenating LibriSpeech test-clean audio and trimming to length (the 60 s clip ends mid-word, irrelevant for speed). Best of 3 after a warmup run. whisper is chunked at 28 s and moonshine at 30 s (model limits); Parakeet takes the whole clip.

| Model | Load | Idle RSS | 5 s | 15 s | 60 s | Peak RSS (60 s) |
|---|---|---|---|---|---|---|
| Parakeet int8 | 4.8 s | 1030 MB | 0.277 s, RTF 0.056 | 0.675 s, RTF 0.045 | 3.03 s, RTF 0.051 | 2417 MB |
| Moonshine base int8 | 2.8 s | 397 MB | 0.116 s, RTF 0.023 | 0.428 s, RTF 0.029 | 2.69 s, RTF 0.045 | 818 MB |
| whisper small.en int8 | 3.8 s | 507 MB | 0.83 s, RTF 0.166 | 4.15 s, RTF 0.276 | 15.3 s, RTF 0.256 | 1307 MB |

Parakeet RAM grows with clip length (encoder attention), so cap utterance chunks (e.g. 30 s) in the worker to keep peak near 1.4 GB (the WER run, max clip ~14 s, peaked at 1436 MB).
Thread-count scaling (1 vs 8 threads) was not measured: the scratch data was lost when the session was cut off.

## STT accuracy (WER)

26 clips, 224 s total, scratch dir only, nothing committed. Text normalised: uppercase, punctuation stripped, fillers (uh, um, hm) dropped. Numbers are not normalised (spoken-form refs vs digit hyps count as errors).

| Set | Clips | Source | Parakeet | Moonshine | whisper small.en |
|---|---|---|---|---|---|
| LibriSpeech test-clean | 12 | openslr/librispeech_asr (CC-BY-4.0) | 0.93 | 4.19 | 4.65 |
| LibriSpeech test-other | 5 | same, harder/accented | 3.09 | 7.22 | 11.34 |
| Noisy (synthetic) | 5 | test-clean + pink noise at 10 dB SNR | 1.03 | 7.22 | 6.19 |
| Accented conversational | 9 | edinburghcstr/edacc test, 9 different accents (Scottish, Indian, Nigerian, Lithuanian, Kenyan, Spanish, Jamaican, Vietnamese, Indonesian) | 16.28 | 29.65 | 25.58 |
| **All** | 26 | | **5.85** | 12.74 | 12.22 |

Caveats: small sample, so single clips move numbers by several points (EdAcc has 9 clips of casual speech). The planned VoxPopuli set failed to download (server 500), so "noisy" is synthetic, not recorded noise. Real-recording noise robustness is unmeasured.
Whole-run RTF over the 26 clips (includes 32 kHz resampling): Parakeet 0.045, Moonshine 0.025, whisper 0.245.

## TTS (Kokoro, 4 threads, voice sid 3, sentence-wise generation)

Time to first audio (TTFA) is the first callback from sherpa-onnx, i.e. after the first sentence is synthesised. Best of 3.

| Variant | Load | Idle RSS | Peak RSS | Text | Audio | TTFA | Total | RTF |
|---|---|---|---|---|---|---|---|---|
| fp32 | 4.7 s | 575 MB | 760 MB | 1 sentence | 2.18 s | 0.45 s | 0.45 s | 0.21 |
| fp32 | | | | 3 sentences | 8.34 s | 0.59 s | 2.02 s | 0.24 |
| fp32 | | | | 5 sentences | 18.7 s | 0.45 s | 3.98 s | 0.21 |
| int8 | 7.5 s | 379 MB | 590 MB | 1 sentence | 2.18 s | 1.25 s | 1.25 s | 0.57 |
| int8 | | | | 3 sentences | 8.32 s | 1.41 s | 4.69 s | 0.56 |
| int8 | | | | 5 sentences | 18.5 s | 1.22 s | 10.8 s | 0.59 |

fp32 streams faster than real time with ~0.5 s to first audio. int8 is slower here (this CPU has no benefit from the int8 TTS kernels), so it is not worth the RAM saving.

## Round trip (synth then transcribe)

6 sentences synthesised with Kokoro, transcribed back. Strict normalised WER:

| TTS variant | via Parakeet | via Moonshine |
|---|---|---|
| fp32 | 18.99% | 18.99% |
| int8 | 13.92% | 18.99% |

Most of that is normalisation, not errors: "eight thousand eighty" came back as "8080", "two gigabytes" as "2GB", "sea shells" as "seashells". The one real failure is the same in every combination: "Deployment to the staging server completed without any errors this morning" came back as "...server without any this morning", so Kokoro dropped or garbled "completed" and "errors" (both ASR models agree, so it is the TTS). Excluding the number and compound-word cases, real WER is about 4% (3 words of ~70). Check Kokoro's handling of that sentence before relying on it for status messages.

## Reproduce

```
cd services/voice-worker
uv sync
uv run python scratch/stt_bench.py parakeet 4 <data_dir> len|wer   # data_dir needs meta.json + wavs
uv run python scratch/tts_bench.py fp32 4
```
