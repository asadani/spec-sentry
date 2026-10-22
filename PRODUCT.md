# Spec Sentry

Spec Sentry turns a narrow specification review into located findings and explicit reviewer decisions. It finds conflicting values for the same declared quantity, undefined explicitly marked terms, and open approval decisions.

The demo specification gives two different limits for preview size, uses an undefined `[[term:external collaborator]]`, and leaves a sharing-policy decision pending. The report cites both conflicting lines and the exact unresolved marker. A reviewer can accept, dismiss, or defer a finding with a note. If the relevant specification changes, prior review decisions are marked stale.

The first release uses a small documented Markdown annotation grammar. It does not pretend to discover every contradiction in arbitrary prose. Explicit annotations trade broad coverage for reproducible checks that a team can inspect.

Its artifact is a review report and a separate decision ledger. The checker never changes the specification or treats a dismissed finding as proof of correctness. Review history remains useful after a document revision because it retains the fingerprint that was actually reviewed.

Validate on specification reviews by measuring actionable findings, false positives, unresolved decisions brought to discussion, and annotation/triage effort. The tool earns its place only if that effort is smaller than the confusion it prevents.
