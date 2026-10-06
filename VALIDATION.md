# Blender export validation — 2026-10-05

Base commit: `katboi01/UmaViewer@07f82e9fa08f23c1cda3a9be3045a09372eae8bb`.

## Verified locally

- Disk capacity checked **before** creating the fork: C 21.03 GiB free, D 60.56 GiB free, E 2148.96 GiB free.
- GitHub fork parent verified as `katboi01/UmaViewer`, owner `Magiuswings`.
- Full source archive: all **2243 tracked files** checked by Git blob SHA against pinned HEAD. A Git partial clone was hydrated from this matching archive because ordinary clone downloads stalled.
- Both new runtime C# files compiled successfully against actual installed Unity managed reference assemblies using Mono C# compiler. The two existing integration types (`UmaContainerCharacter`, `UmaViewerBuilder`) were stubbed with their actual used members. This is an API/syntax check, not a complete Unity build.
- **Blender 4.2.23 LTS** and **Blender 5.2.1 LTS**: ran the real bundled conversion script on a synthetic mixed-renderer fixture and produced separate clothing/body `.blend` files.
- Reopened both files in fresh Blender processes on each tested version: verified compacted geometry, two UV sets, vertex colors, shape influence without double application, six bone influences, normalized weights, duplicate-name handling, bone hierarchy, packed textures, engine-specific material outputs, connected palette nodes and actual armature deformation.
- Each split synthetic file contains 4 vertices, 2 triangles, 6 bones, 1 material and 2 packed images; no unweighted vertices. These are test objects, not game models.
- Eight malformed snapshot cases rejected on both Blender versions: unsupported schema, cyclic hierarchy, duplicate IDs, invalid triangle, unsafe/missing texture, invalid weight, missing bone and invalid shape size.
- Blender 5.2.1: actually rendered the saved synthetic material with both EEVEE and Cycles, saved and inspected the two 128x128 images. This verifies renderable node graphs, not visual equivalence with a game character.

Machine-local reproducibility outputs are retained under ignored `Tests/Local/fixture/` and `Tests/Local/fixture42/`. They include `.blend` files, conversion reports and `verification.json`. Run commands are in `docs/BLENDER_EXPORT.md`; tests contain no game data.

## Implemented but not runtime-verified here

- Unity-readable and GPU-only asset extraction, full vertex streams, nonzero submesh `baseVertex`, source skin bindings, current-pose capture, shader parameter/texture capture and preservation of live model state.
- Runtime export panel, automatic Blender executable detection and asynchronous Blender process conversion inside the Unity player.
- An executable Unity smoke test is provided at `Assets/Editor/BlenderExportSmokeTest.cs` to cover these paths with a synthetic rig, without game data.

## Outstanding acceptance

No Unity Editor was found in checked standard installation locations; no Unity build Secrets were present in this new fork. No complete Unity project build or Windows player build has been performed. The Unity UI/player export path and visual comparison with actual gameplay remain unverified.

**Later headless validation on the same date:** the independent `Tools/HeadlessExporter` path has now actually exported the user-supplied `SpecialWeek1.zip`. It parsed 228 real UnityFS bundles, 10 main prefabs and 41 renderers, generated 66 Blender files and verified every file against decoded source geometry, weights, hierarchy, UV and packed textures. A real-character preview was rendered and inspected. This updates the real-data export evidence above; the Unity UI/player path and comparison with actual gameplay remain unverified. See `Tools/HeadlessExporter/README.md` for the exact boundaries, including heuristic body/clothing segmentation and missing shader dependencies.

The body-base workflow uses an existing swimsuit/tight costume as approved by the user. Missing body surfaces are not reconstructed. The editable EEVEE/Cycles materials retain source parameters and textures, but Unity shader fidelity, regional palette encodings, face lighting, eye atlases, outlines and physics remain outside the verified claims above.

## Broad apparel segmentation revision — 2026-10-05

The headless exporter now groups apparel into `clothing`, `headwear`, and combined `footwear` (shoes/socks and their attachments). It no longer exports skirt, jacket, cape, gloves or general accessories as separate garment categories. Existing face, eyes, eyebrows, hair, body skin and tail outputs remain. Empty apparel categories are recorded and do not produce placeholder meshes/files.

Real inputs: `1001_swim.zip` (245 UnityFS bundles, 11 prefab jobs, 91 referenced textures) and `1003_swim.zip` (470 bundles, 23 prefab jobs, 174 textures; both character 1001 and 1003 plus four generic bodies). Final outputs contain **57** and **116** Blender files respectively, including source references and complete body bases. Original inputs remain hash-identical. Generic 0002/0003/0004 textures are bound from supplied costume/bust filenames with explicit skin texture index 0, and full generic prefab filenames avoid collisions.

All final files are reopened in separate validation Blender processes, one file at a time, and compared with decoded source indices, coordinates, UV, normalized weights, parent hierarchy, packed textures and actual root-bone deformation. The category partition has exactly the source-reference triangle count. Checks also cover unique output names, absence of old fine categories and absence of outputs for empty groups. Both supplied 80 head variants have no headwear, and generic barefoot 0004 swimsuits have no footwear. Actual broad-group previews were rendered and inspected for the swimsuit and decorated costume samples.

The source parse and body classification ran on the actual ZIP files. Later head refinements reused those real snapshots; checks confirm all original geometry, bones and materials are unchanged and native-prefab coordinates produce the same final classifications as the aligned snapshots. Bone names alone cannot identify apparel: source 1003 variant 43 binds a fabric veil to Hair bones and its bun directly to Head. The final heuristic uses supplied base-hair geometry/colors and shared fabric bone chains to route those components, and keeps white flower ornaments separate from white hair. This improves the inspected examples; it does not certify semantic classification for every face or every other character. Original Unity shaders are absent (37/69 dependency warnings); all referenced 2D textures resolve with zero export errors. Per-prefab rigs and renderer objects remain separate inside each category file/collection.

Local delivery: `E:\UmaViewer-Exports\2026-10-05\1001_swim_delivery` and `1003_swim_delivery`, with `manifest.json`, `verification.json`, packed Blender files and inspection previews. These private game assets are excluded from Git; only program changes and documentation are committed.

## Blender 4.2 / PDX conversion — 2026-10-06

Both original swimsuit ZIPs were reparsed and regenerated using Blender **4.2.23**, producing **57 + 116** source/category/reference files. Every file was reopened against actual decoded source data; both verification reports passed. Their merge retains **24** unique jobs and removes **10** exact duplicate geometry/binding/material jobs, with character IDs 1001 and 1003 plus explicitly unowned shared bodies.

The new `Tools/PDXExporter` pipeline uses unmodified **IO PDX Mesh 0.91** and the provided original CK3 female body/head mesh references. It constructs full 134/61-bone contracts with original names, parents and orientations, direct semantic heads at the UMA source bind points and generated relative helper positions. Garment chains are mapped to matching reference chains. Unmatched source weights collapse along meaningful source ancestry; all weights are normalized with a maximum of four influences. Current real inputs required zero weight truncations. Source mesh coordinates, transforms, normals, UVs, Basis and connectivity are not aligned, scaled or warped during this stage. The independent final source-coordinate maximum error is **0**.

PDX shader mapping: body skin `portrait_skin`; face/effects `portrait_skin_face`; hair/brows/tail `portrait_hair`; eyes `portrait_eye`; clothing/headwear/footwear `portrait_attachment`. Original diffuse DDS maps and generated neutral PDX normal/properties maps are explicit. Nine quarter-width eye atlases are baked into separate texture pages without UV edits. Every binary texture reference has a real file adjacent to the `.mesh` and saved Blender images are packed. This does not claim Unity shader equivalence.

For the exact-topology generic swimsuit family, one skin/clothing boundary triangle is relabeled in an output snapshot copy using the base partition. The original inputs and classifications remain intact. Independent comparison of all 24 snapshots confirms all non-face mesh data and the complete directed triangle/material multiset remain exact. The single change is recorded in `partition-changes.json`. Original and normalized apparel indexes both retain all incompatible jobs and virtual skirt components; no skirt is physically separated from broad clothing.

Final output contains **96 component `.blend`/`.mesh` pairs**, **15 editable morph `.blend` files**, **15 morph base `.mesh` files** and **50 target `.mesh` files**. All 96 components were reopened in an independent process, checked against original vertex/UV indices and source weight accumulation, then actually reimported using the PDX plugin. Every morph was reopened and checked against target source vertices and base binary vertex order, all UV sets, directed triangles and complete skeleton attributes. The resulting `verification.json` has `passed=true`, 96 passed components, 96 passed plugin roundtrips and 15 passed morph groups.

The meaningful swimsuit example has **3510 Blender source vertices / 5472 triangles**, and UV/material splitting yields **3540 PDX vertices**. Its standalone clothing has **886 vertices / 1463 triangles**; standalone skin has **2654 vertices / 4009 triangles**. The maximum actual swimsuit target coordinate difference is approximately **0.00909794**. Both full body and standalone clothes/skin have verified morph outputs. Other groups preserve source variants; **11 of 50** targets exceed 1e-5 coordinate difference, while remaining variants have identical or almost identical geometry. Texture/material differences cannot be represented by geometry keys.

Independent review reproduced and verified fixes for a tail reference-roll precision error, a validation gap permitting a missing renderer, character-list merging and Blender 4.2 Key metadata/orphan-copy behavior. Review probes additionally saved/reopened a real clothing mesh with multiple keys after temporary morph export and checked actual whole-swimsuit, skin, clothing and mouth-line morph outputs. Heads for both characters and both generic swim morph endpoints were actually rendered and inspected. This does not establish CK3 game runtime, animation translation retargeting, physics or all-pose acceptance.

Neither the supplied character-specific broad clothes nor the virtual skirt candidates has a verified cross-character exact-topology correspondence. Their independent models and rejection reasons are retained; no non-existent character-specific skirt morph is reported as complete. Local final delivery is `E:\UmaViewer-Exports\2026-10-06-PDX\PDX-42-final`. Private models, textures and original references are excluded from the public repository.

## Bust-separated body bases — 2026-10-06

This revision supersedes the earlier cross-bust swimsuit reuse described above. Generic prefab fields are parsed as costume, subtype, body setting, height, shape and **bust**. Automatic full-body bases are selected per owner/bust, preserving separate shared bust 1 and 2 bases. Original character-specific bodies without that field remain unknown and independent. Both partition reuse and morph eligibility require the same complete generic body profile; even an explicit family override cannot bypass it. Old cached compatibility groups are rechecked against actual source filenames.

The real 485-bundle union of both supplied ZIPs was reparsed: 24 jobs, zero errors, four selected bases (shared bust 1, shared bust 2, and two independent character-specific bases). Meshes, bones and materials are exactly equal to the preceding decoded source. Two portable regression tests and an independent source audit verify forced-family rejection and stale-cache partition blocking. A real Blender probe rejects the old altered bust-2 skin/clothing files using the new source-category triangle assertion.

The complete PDX pipeline was rerun in Blender 4.2.23. All **96 components**, **96 actual PDX roundtrips**, **12 remaining morph groups** and **47 targets** passed. Bust 1 retains 4009 skin / 1463 garment triangles; bust 2 retains 4008 skin / 1464 garment triangles. Both complete bases preserve 3510 vertices and 5472 triangles. All 24 output source snapshots are exactly equal to original snapshots, including face categories; there are zero partition changes. The three earlier cross-bust whole-body/skin/clothing morph groups are removed. No mesh shifts, scaling, deletions or body reconstruction were introduced. Current delivery is `E:\UmaViewer-Exports\2026-10-06-PDX\PDX-bust-separated`; base paths and parameters are in `body-bases.json`.
