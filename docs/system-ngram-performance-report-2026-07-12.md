# Scoreless system n-gram implementation and performance report

Date: 2026-07-12

Post-measurement update: single-node `*` wildcard support was added. The current release asset contains 3 rules and is 3,252 bytes; the small-dictionary timing table below records the preceding 2-rule, 3,144-byte build.

## Implementation

- Editable source: `src/main/ngram/*.ngram`
- Runtime asset: `app/src/main/assets/ngram/system_ngram.dat`
- Runtime format: scoreless packed minimal acyclic automaton with terminal bits
- Storage used in this measurement: resident `ByteArray` (no mmap)
- Runtime storage policy: dictionaries up to 1 MiB use `ByteArray`; larger dictionaries are copied once to `noBackupFilesDir` and mapped read-only
- Ranking: a completed candidate path either matches or does not match; matching candidates are placed first and `Candidate.score` is not changed
- Rules in the measured dictionary:
  - `"服" + "を" + "着る"`
  - `"布" + "で" + pos("名詞") + "を" + "拭く"`

Binary build result:

| Rules | POS classes | Signatures | States | Edges | Bytes |
|---:|---:|---:|---:|---:|---:|
| 2 | 14 | 2 | 25 | 25 | 3,144 |

The current bytes-per-rule value is dominated by the fixed 2,672-byte context-ID-to-POS-class table, so it must not be extrapolated linearly from this two-rule dictionary.

## End-to-end conversion measurement

Environment:

- Pixel 7 Pro AVD, Android API 35, arm64
- `liteStandardDebug`
- Input: `ふくをきる`
- Requested candidates: 4
- Warm-up: 20 conversions per configuration
- Measurement: 50 conversions per configuration
- Full path: graph construction, path search, binary dictionary lookup, scoreless reranking, and final candidate construction

| System n-gram | Binary | Java heap delta | Native heap delta | PSS delta | Allocated / conversion | GC | p50 | p95 | p99 | First candidate | Original score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| Disabled | 0 B | 0 B | 992 B | -1,219,584 B* | 153,354 B | 0 | 2.350 ms | 4.968 ms | 6.490 ms | 服を切る | 10,440 |
| Enabled | 3,144 B | 4,096 B | 0 B | 4,096 B | 248,217 B | 0 | 2.295 ms | 4.324 ms | 5.537 ms | 服を着る | 10,691 |

`*` The disabled PSS delta is measurement noise caused by GC/page accounting between snapshots. PSS is reported at KiB granularity. The enabled run retained one additional 4 KiB page, consistent with the 3,144-byte binary.

Observed enabled-minus-disabled differences:

- p50: -0.055 ms; effectively unchanged at emulator measurement resolution
- p95: -0.645 ms; not interpreted as an optimization because the configurations were measured sequentially
- p99: -0.953 ms; likewise subject to emulator/JIT noise
- Java heap: +4,096 B
- PSS: approximately +4,096 B
- allocation per conversion: +94,863 B
- GC count: no increase

The allocation increase comes primarily from requesting a larger internal candidate pool for scoreless reranking. It did not increase GC in this 50-iteration run, but it is the main item to optimize before substantially increasing the pool or rule set.

## 100,002-rule large-dictionary measurement

To exercise the large-dictionary path, 100,000 deterministic nonmatching rules with randomized 16-character hexadecimal word components were temporarily added to the two real rules. The temporary rules were removed after measurement and are not present in the release asset.

Build result:

| Rules | States | Edges | Binary bytes | Bytes/rule |
|---:|---:|---:|---:|---:|
| 100,002 | 801,562 | 901,562 | 13,627,736 | 136.27 |

The first resident-`ByteArray` run retained approximately 13.63 MiB of Java heap/PSS. That failed the low-memory objective, although conversion latency and GC remained acceptable. Based on that result, the runtime loader was changed to use read-only mmap only for assets larger than 1 MiB.

After that change, the same 100,002-rule dictionary was measured for 30 conversions:

| System n-gram | Storage | Java heap delta | Native heap delta | PSS delta | Allocated / conversion | GC | p50 | p95 | p99 | First candidate |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Disabled | none | 0 B | 992 B | -145,408 B* | 154,009 B | 0 | 2.777 ms | 6.058 ms | 7.440 ms | 服を切る |
| Enabled | mmap, 13,627,736 B file | 0 B | 0 B | 65,536 B | 248,490 B | 0 | 2.552 ms | 4.688 ms | 6.502 ms | 服を着る |

`*` Negative PSS is snapshot noise. The relevant enabled measurement shows that only approximately 64 KiB of the 13.63 MiB mapped file was resident after the measured lookup workload.

This result is why mmap is conditional rather than mandatory: it provides no meaningful advantage for the 3,144-byte production dictionary, but removes approximately 13.63 MiB of Java-heap retention for the synthetic 100,002-rule dictionary.

## Functional result

- Without the system dictionary, the first candidate was `服を切る` with score 10,440.
- With the system dictionary, `服を着る` was detected as a matching path and moved to first place.
- Its existing conversion score remained 10,691. No score or adjustment is stored in the n-gram dictionary and no score was added to the candidate.

## Verification

- Converter unit tests: passed
- Deterministic binary and score-rejection tests: passed
- JapaneseKeyboard `liteStandardDebug` unit tests: passed
- Pixel 7 Pro AVD end-to-end instrumented test: passed
- Full dictionary asset generation and ZIP layout verification: passed
- Release ZIP contains `app/src/main/assets/ngram/system_ngram.dat`

The synthetic large test validates the data path and conditional mmap behavior at 100,002 rules. Its randomized long words are intentionally a low-compression stress case, not a model of expected Japanese corpus size. Final release thresholds should still be confirmed with representative rules on a fixed physical Android device.
