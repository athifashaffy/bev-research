# Data provenance and layout

workspace/ retains the legacy relative paths required by the verified input hashes. It contains nine archived native result databases, recorded settings, all-state energy and thermal tables, fixed reference-cell coefficients, original A123 source MAT files and saved forecast inputs/predictions.

The A123 source is Aloisio Kawakita de Souza (2021), DOI https://doi.org/10.17632/p8kf893yv3.1, CC BY 4.0. Its original values are copied unchanged. Published dataset data are separate from generated HAULSIM/thermal/ML outputs.

tum/ is a separate publicly documented LFP abuse-data collection, if present. It is not used to fit or score the current HAULSIM forecasting benchmark. Original clocks are not assumed synchronised and no independently verified onset labels are supplied.

SOURCE_MANIFEST.json lists the size and SHA-256 of every data file, using paths relative to data/. Verification checks identity, not field validity or authorship. No licence passwords, papers, professor correspondence or executable third-party libraries are included in this new folder.
