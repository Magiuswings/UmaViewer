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

No Unity Editor was found in checked standard installation locations; no Unity build Secrets were present in this new fork. No complete Unity project build or Windows player build has been performed. No actual Uma Musume character/costume export, UI interaction or visual comparison with the game has been performed.

The body-base workflow uses an existing swimsuit/tight costume as approved by the user. Missing body surfaces are not reconstructed. The editable EEVEE/Cycles materials retain source parameters and textures, but Unity shader fidelity, regional palette encodings, face lighting, eye atlases, outlines and physics remain outside the verified claims above.
