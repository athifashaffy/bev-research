# Underground BEV research

Private research transfer snapshot prepared on 16 October 2026 for Athif Shaffy.

## Start on the other laptop

1. Download **BEV_Research_Portable_2026-10-16.zip** from this repository. On its file page, use **Download raw file**. Extract the ZIP into a normal local folder. For numerical rechecking, also download **BEV_228Ah_Saved_Predictions_2026-10-16.zip** and extract it into the same parent folder so its `BEV_Research` folder merges with the first one.
2. Open **Underground_BEV_Research_and_HAULSIM_Step_by_Step_Guide.docx**. A separate copy is also at the repository root. The 15 page guide explains the research, actual HAULSIM screens, settings, running, results and remaining gaps.
3. In the extracted `BEV_Research` folder, open `Claude_Handoff_2026-10-16/02_VISUAL_OVERVIEW.html` in a browser. It works offline. Some older links contain the original laptop's absolute paths; find their files by the preserved folder names.
4. Open the extracted folder as a project in Codex. Give it `Claude_Handoff_2026-10-16/01_FULL_HANDOFF_FOR_CLAUDE.txt` and this README for context. That summary works with Codex despite its filename.
5. To use HAULSIM, install or use a compatible licensed version. Open a practice copy of a `.hsm` file with its matching `.hsmdb` beside it. The guide uses HAULSIM 3.8 build 585.

**This transfers files and a written handoff, not this live Codex chat. It is a dated snapshot, not automatic two way synchronization.** The full original workspace remains on the first laptop.

## What is in the main package

- The new follow along Word guide, its source and verification record.
- The generic four truck charging demonstration, screenshots, native database and exported results.
- The three completed New Afton informed rolling resistance scenarios, model pairs, native results and audits.
- The research plan, working paper draft, literature matrix, input register and incident evidence register.
- The external thermal coupling report and calculations.
- The 228 Ah laboratory thermal comparison: code, the seven aligned records, fitted coefficients, metrics, plots and verification records. Full saved predictions are in the separate predictions ZIP.
- The earlier temperature illustration and battery data search assessment.
- The full written handoff, interactive overview and selected evidence.
- Supporting native model builder and road experiment scripts.

`TRANSFER_MANIFEST.json` lists every included file and SHA-256 hash. Files are copied without rewriting the research evidence.

## Keep these studies separate

| Study | Configuration | What it supports |
|---|---|---|
| Generic demonstration | Four trucks; 42 t; assumed 400 kWh; 300 m lift; native charging enabled | Haulage, traffic and charging demonstration. Energy/SOC accounting remains unresolved. |
| New Afton road experiment | One truck; 45 t; 1500 m network and 135 m rise; 2/3/4% resistance; native battery energy disabled | Complete cycle and loaded travel sensitivity, not validated battery endurance. |
| External thermal coupling | Native road duty cycle plus assumed electrical conversion and laboratory cell response | Illustrative methodology, not Z50 pack temperature validation. |
| 228 Ah laboratory test | Six physical LFP cells; seven selected records; measured current and three temperature channels | Mixed exploratory evidence against simple baselines. |

The road cycles were 23.967, 24.308 and 24.631 minutes. Each short run delivered 180 t. The 228 Ah formula reduced pooled cross-cell RMSE from 0.274 to 0.187 degrees C, but worsened the later B1 test from 0.224 to 0.292 degrees C. Only 5 of 18 initial cell/channel comparisons improved. Do not present only the favourable pooled result.

No validated fire detector, early warning lead time, real New Afton pack temperature or fire probability has been established. The nine page paper draft predates the latest road and laboratory experiments; it still needs integration and supervisor approval. The accepted abstract's AI sensor fusion scope also needs deliberate alignment.

## Earlier presentation and video material

`BEV_Earlier_Presentation_and_Native_Video_2026-10-16.zip` contains earlier slides, briefing material and actual HAULSIM screen recordings. These are historical teaching and discussion assets; their results and claims must be checked against the newer reports before presentation.

`BEV_Truck_Illustration_Not_Native_HAULSIM.mp4` is a separate illustrative vehicle animation. It is not a native HAULSIM recording, not actual mine footage and not a verified Z50 digital twin.

## Reproduction and exclusions

The 1.27 GB full source dataset archive, downloaded third party publications, installed software/libraries, renderer caches, credentials, original chat databases and other large workspace assets are not included. No HAULSIM licence is included. This is not a complete backup of the original workspace.

The 228 Ah package contains the selected aligned input arrays and saved predictions, so the saved numerical checks can be repeated after setting up Python with NumPy and SciPy. The scripts also use Matplotlib, pandas/openpyxl, reportlab and python-docx for other steps. Existing script paths prefer task-local packages; install suitable packages on the other machine and review machine-specific paths before running. The original raw archive is required to repeat raw-to-aligned extraction; it is not required just to read results. A fresh machine installation has not been tested.

Preserve the reference results before rerunning. `code/verify_results.py` verifies saved predictions and splits; `code/run_comparison.py` refits and overwrites analysis outputs. Do not silently treat a new run as the archived reference.

## Dataset attribution

封, 居强 (2026). *Dataset of multi-dimensional electrical performance for large-capacity mining power lithium-ion batteries at early calendar aging under coupled temperature and soc conditions*. Mendeley Data, version 2. https://doi.org/10.17632/dhr726bk6z.2

Licence: [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/). Seven selected records were aligned and converted into compressed NumPy arrays for this analysis; model predictions and metrics are derived research outputs. Source members, exact alignment checks and hashes are recorded in `source_audit.json` and `aligned/*.json`. The original archive README retains a version 1 DOI in its text; the archive actually used here is version 2, as recorded in the download manifest. DataCite metadata was checked for author, year and licence on 16 October 2026.

Other references and their limitations are in the evidence matrix and data search register. Third party rights remain with their respective owners. Keeping this repository private does not grant permission to publish third party files or unpublished research.

## Work to resume

The next research decision is supervisor approval of paper scope and assumptions. Integrate the completed road and 228 Ah results with their limitations, seek proper vehicle pack and cooling data, and preserve core thesis contributions for the journal plan. Do not describe 36 proposed scenarios as executed.
