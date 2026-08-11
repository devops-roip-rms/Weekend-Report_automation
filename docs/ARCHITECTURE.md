# Architecture

The application is manual-run only. FastAPI creates run records after configuration preflight, a persistent worker atomically claims `CREATED` runs, collectors gather actual state/evidence, validators generate immutable automated findings, and reviewers use HTML pages to add module/result/Splunk notes.

Final confirmation freezes the run, results, evidence references, reviewer identity, decision, and every saved note into `runs/<RUN_ID>/final/review_snapshot.json`. One final PDF is then generated from that snapshot.

The default configuration intentionally contains placeholders and blocks real execution.
