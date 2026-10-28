# AI assistance and artifact provenance

AI assistance was used in project development, code, numerical audits,
supporting plots, and manuscript drafting and revision. The existing paper text
and code should therefore be described as AI assisted. They should not be
represented as independently authored without that assistance.

This release adds supporting audit software, technical documentation and plots.
It does not create a new scientific manuscript or change the provenance of
previously generated paper content. Human authors remain responsible for source
attribution, physical assumptions, numerical results, interpretation and any
text they submit.

The new physics audit independently implements the numerical reconstruction
without importing or running the original analysis scripts. Here,
"independently" refers to that separate implementation. It does not mean
independent authorship, an independent experimental dataset, or independent
physical validation of the truck model.

The ML audit checks stored predictions and records. The original Experiment A models were held in memory and were not serialized.
+The separate 28October reproduction now saves 72newly refitted estimators and
+verifies their predictions. Experiment B includes three older laboratory-model
+artifacts. These distinctions are recorded in each experiment folder; none
+establishes measured vehicle-temperature accuracy.

Source hashes, explicit input paths and machine-readable checks provide an
inspectable computational record. Passing those checks cannot validate the
assumed cell-to-pack transfer or establish battery safety. Physical limitations
are documented in [MODEL_AND_LIMITS.md](docs/MODEL_AND_LIMITS.md).

## Recorded tools and chronology

Codex generated substantial manuscript revisions and analysis/plotting support
code in the accompanying work. Athif also reports using Claude during earlier
development and revision; this package does not establish block-by-block Claude
attribution or the exact model versions. Assistance was not limited to grammar.

The five repository commits that preceded this release were dated16October2026
and did not contain Claude or ChatGPT co-author trailers. The new commit records
the present evidence upload. It does not backdate these files or prove when an
experiment was run, who independently authored it, or what a human reviewed.
