# Uma Viewer (2)

## Blender export fork

This fork adds **independent `clothing.blend` and `body.blend` exports**, with editable armatures, bone weights, material nodes, packed textures, UVs, vertex colors and existing mesh shape keys. Open **Blender Export [F8]** after loading a character and assign each renderer/material section to Clothing, Body or Exclude.

Body export can use a **swimsuit or tight outfit as the body base**: load that costume, then use **Swimsuit / tight outfit -> Body**. It keeps existing surfaces without reconstructing missing skin. Unity shaders are converted to an editable EEVEE toon approximation and a Cycles material, with the original shader parameters retained. See [the Blender export guide](docs/BLENDER_EXPORT.md) for usage, build requirements and validation limits.

The project currently pins **Unity 2022.3.62f3** in `ProjectSettings/ProjectVersion.txt`. Build this fork before using its new export panel; upstream release binaries do not contain this feature.

**Headless named-asset export:** [Tools/HeadlessExporter](Tools/HeadlessExporter/README.md) reads a `Loaded Assets -> Copy all` ZIP/directory directly with Python, then runs Blender in the background. It requires no Unity Editor or viewer UI. The complete path has been tested on a real SpecialWeek asset package, exporting independent parts and original-reference models with provenance filenames and packed textures. Body skin/garment segmentation is explicitly marked as heuristic.

⚠️ If you see **"Failed to load il2cpp"** or the app cannot start on Windows, it may be blocked by **Windows Smart App Control**.

 If it fails, turn off Smart App Control:

   `Windows Security → App & browser control → Smart App Control settings → Off`

This issue is caused by Windows blocking unsigned builds. The program should start normally after moving it to a local folder or disabling Smart App Control.

Unity application that makes it easy to view assets from Uma Musume: Pretty Derby.

| Version   | Supported |
|-----------|-----------|
| JP (DMM)  | ✅        |
| JP (Steam)| ✅        |
| KR        | ✅        |
| Global    | ✅        |

------------

## ⚠️ 🌍 EN/Global users ⚠️

In UmaViewer, set **WorkMode** to **Default** and **Region** to **Global** in the **'Other'** Settings tab.

Currently only the default work mode is supported - you need to download assets using the Download All button in the game's settings for the viewer to work.

------------

### Requirements/Installation
1. [Uma Musume: Pretty Derby](https://dmg.umamusume.jp/) with full data download is required to run the viewer.
2. Depending on your version and update status, the game stores its data in **different locations**
 - **DMM/Steam Older installations :** C:\Users\\*your_username*\AppData\LocalLow\Cygames\umamusume(?)\
 - **DMM/Steam Fresh installations :** ...\\*Umamusume installation directory*\Umamusume_Data\Persistent(?)\
 - In any case，confirm your file listing in target folder looks like this
   * Target Folder\
     * **meta**
     * master\
       * **master.mdb**
     * dat\
       - 2A\\...
       - 2B\\...
       - ...\\...
3. Download the most recent UmaViewer.zip file from [Releases](https://github.com/katboi01/UmaViewer/releases/) tab.
4. Extract the archive anywhere, can be extracted over previous version.
5. Run the UmaViewer.exe. 
6. UmaViewer will try to automatically detect the game data folder.  
   - If it fails or shows an error, go to **Settings → Other → Change DataPath** and manually select target folder.

------------

- For Developers/Contributors
1. [Unity Hub](https://unity3d.com/get-unity/download) with [Unity Engine Version 2022.3.62f1](https://unity.com/releases/editor/archive) is recommended. It should be possible to run it on newer 2022.3.X versions.
1. Clone or download and extract this repository.
1. Import and Open the project in Unity Hub, missing files should be automatically repaired.
1. Open the Assets/Scenes/Version2 scene.
   - note: If there are errors in the console, [JSON .NET For Unity](https://assetstore.unity.com/packages/tools/input-management/json-net-for-unity-11347) may be required

### Features

||||
| ------------ | ------------ | ------------ |
| ✓ - Working | / - Incomplete  | x - Unsupported  |

|||
| ------------ | ------------ |
| Viewing main character models/animations | ✓  |
| Swapping costumes/animations between characters | ✓  |
| Viewing chibi models/animations | ✓  |
| Viewing mob (NPC) models | ✓ |
| Playing facial animations, custom sliders | ✓  |
| Cloth/Hair physics | ✓  |
| Playing Live Audio with Lyrics | ✓  |
| Exporting animations to MMD | ✓  |
| Recording animations (.gif), screenshots | ✓  |
| Viewing Props, Scenery, Live scenes | /  |
| Exporting models | /  |


All characters and animations are supported

<img src="https://user-images.githubusercontent.com/59540382/222418271-a6e4ce82-b3a5-47ba-9fc9-4d85120218ec.png" height="350" />

Mobs / background characters as well

<img src="https://user-images.githubusercontent.com/32562737/219174232-7d0a0eec-8b1c-4571-9c08-8474e06dd3a8.png" height="350" />

Mixing outfits and animations

<img src="https://user-images.githubusercontent.com/59540382/222420757-609e1f77-d762-4b39-a7d0-d1fb2d3b79a3.png" height="350" />

Screenshot and .gif recording

<img src="https://user-images.githubusercontent.com/59540382/222421579-582be5db-5839-4f7c-bf1b-80efc812c4e0.gif" height="350" />

and more

<img src="https://user-images.githubusercontent.com/59540382/222422871-12e80e0b-778b-4f42-b581-5e4af5cd6df9.png" height="350" />

### Also check out:
[UmaChat by kagari](https://github.com/kagari-bi/UmaChat) - model viewer fork that lets you chat with Umas using AI + TTS

### Special Thank to:
MarshmallowAndroid: [UmaMusumeExplorer](https://github.com/MarshmallowAndroid/UmaMusumeExplorer) for acb/awb decoder.
