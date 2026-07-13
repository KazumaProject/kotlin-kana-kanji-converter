# Scoreless system n-gram version 3 performance report

Date: 2026-07-12

## Result

The fixed-width state/edge format was replaced by version 3. Version 3 uses a
bucketed 64-bit hash index and front-coded canonical rule records. It does not
use mmap. JapaneseKeyboard retains exactly one dictionary `ByteArray` and uses
small thread-local query/record scratch buffers for lookup.

The rule language and result semantics did not change:

- exact words, coarse POS and one-node `*` wildcard are supported;
- the dictionary stores no score;
- a hash hit is always checked against the complete canonical rule, so a hash
  collision cannot produce a false match;
- matching only changes candidate ordering and never changes `Candidate.score`.

## Binary layout

The binary contains a header and CRC, context-ID-to-POS table, rule signatures,
a dynamically sized bucket directory, 10-byte hash entries (48 hash bits plus a
32-bit record ID), and complete canonical rules front-coded in blocks of 16.

Lookup performs:

1. allocation-free canonical query encoding;
2. bucket selection and binary search of the 48-bit hash suffix;
3. decoding of at most one 16-record block for each hash hit;
4. byte-for-byte comparison with the complete canonical rule.

The editable source remains `src/main/ngram/*.ngram`. GitHub Actions runs
`buildSystemNgramDictionary`, publishes its build report, and packages
`app/src/main/assets/ngram/system_ngram.dat` in the JapaneseKeyboard asset ZIP.

## 100,000-rule storage measurement

The stress dictionary contained the three release rules plus 99,997
deterministic exact three-gram rules with randomized hexadecimal word
components. The temporary rules were removed after measurement.

| Format | Rules | Binary bytes | MiB | Bytes/rule |
|---|---:|---:|---:|---:|
| Previous fixed-width format (reported baseline) | 100,000 | about 27,996,000 | about 26.7 | about 280.0 |
| Version 3 | 100,000 | 5,524,486 | 5.27 | 55.24 |

Version 3 is about 79.8% smaller than the 26.7 MiB baseline and remains below
the 8 MiB target without mmap. Its measured components were 1,262,148 bytes for
the hash index and 4,234,570 bytes for the exact compressed records.

The final three-rule release dictionary is 3,895 bytes. The relatively high
per-rule figure at this size is caused by fixed metadata, mainly the 2,672-entry
POS context table, and must not be extrapolated linearly.

## End-to-end Pixel 6 measurement

Environment and method:

- physical Pixel 6, Android 16;
- `liteStandardDebug`;
- input `ふくをきる`, requested candidates 4;
- full graph construction, path search, dictionary lookup, reranking and final
  candidate construction;
- both paths pre-warmed 30 times;
- 100 timed samples per path, with enabled/disabled calls interleaved to avoid
  sequential JIT/cache bias.

| System n-gram | Rules | Retained Java heap | PSS delta | Allocated/conversion | GC | p50 | p95 | p99 | First candidate | Score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| Disabled | 0 | 0 B | 17,408 B* | 153,026 B | 0 | 2.847 ms | 3.035 ms | 3.091 ms | 服を切る | 10,440 |
| Enabled | 100,000 | 5,525,504 B | 5,525,504 B | 153,026 B | 0 | 2.753 ms | 3.191 ms | 3.302 ms | 服を着る | 10,691 |

`*` PSS snapshots use page-level accounting and contain background noise. The
enabled retained-heap result is the relevant deterministic result: dictionary
retention is only 1,018 bytes above the 5,524,486-byte file.

Enabled-minus-disabled timing differences were -0.094 ms at p50, +0.156 ms at
p95, and +0.211 ms at p99. No GC was added.

An initial version 3 run always expanded the internal pool to 32 candidates. It
allocated about 248,053 bytes per conversion versus 153,354 bytes without the
dictionary. The search was changed to stop once the requested candidate count
has been reached and a system-rule match has already been found; it continues
up to the larger safety pool only when no match has yet been found. After this
change, measured allocation was identical for enabled and disabled conversion:
153,026 bytes per conversion.

## Functional verification

- Without the dictionary, the first candidate was `服を切る` (score 10,440).
- With the dictionary, `服を着る` matched and moved to first place.
- Its original score remained 10,691; no dictionary score exists.
- Exact-word, POS and wildcard reader tests passed.
- Converter format and deterministic-build tests passed.
- JapaneseKeyboard unit tests passed.
- The end-to-end Android instrumentation test passed with 100,000 rules.
- The final release asset was restored to the three editable rules after the
  stress measurement.
