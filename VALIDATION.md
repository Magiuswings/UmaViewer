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
