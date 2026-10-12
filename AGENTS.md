# Conversion and dictionary verification

- Before claiming JapaneseKeyboard compatibility, identify the actual consumer checkout, Git revision, runtime matching code, and dictionary asset hashes. Do not use a similarly named old copy as evidence for the active consumer.
- When a user identifies a release, test its shipped binary assets, not just locally generated files or text sources.
- Verify unigram scope in the consumer path search. Matching one node does not imply that the complete candidate or input is one node.
- Keep the verification CLI's unigram matching and de-duplication semantics aligned with the verified consumer. Do not add a stricter CLI-only guard that hides a production regression.
- Check standalone and compound inputs together: しろ, しろい, しろくろ, しろあり. Keep the しろ + 医 regression test.
- Separate verified observations from hypotheses. Do not claim full application parity, no side effects, or successful reproduction based only on this repository's simplified CLI.
- If a requested behavior cannot be encoded by the current asset format and consumer, state the limitation explicitly instead of claiming that a dictionary-only change enforces it.
