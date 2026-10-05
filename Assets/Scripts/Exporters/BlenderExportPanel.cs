using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using UnityEngine;

/// <summary>Runtime UI, available in existing scenes/builds without modifying scene YAML.</summary>
public sealed class BlenderExportPanel : MonoBehaviour
{
    Rect window = new Rect(20, 60, 760, 650);
    Vector2 scroll;
    bool visible;
    UmaContainerCharacter character;
    List<BlenderModelExporter.Selection> selections = new List<BlenderModelExporter.Selection>();
    string outputDirectory, blenderPath, status = "Load a character, then assign its material sections.";
    Task<string> conversion;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Install()
    {
        if (FindObjectOfType<BlenderExportPanel>()) return;
        var go = new GameObject("Blender Export Panel");
        DontDestroyOnLoad(go); go.AddComponent<BlenderExportPanel>();
    }

    void Awake()
    {
        outputDirectory = PlayerPrefs.GetString("BlenderExport.Directory", Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "UmaViewerExports"));
        blenderPath = PlayerPrefs.GetString("BlenderExport.Executable", "");
        if (string.IsNullOrEmpty(blenderPath))
        {
            string root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "Blender Foundation");
            if (Directory.Exists(root))
                blenderPath = Directory.GetDirectories(root).OrderByDescending(p => p).Select(p => Path.Combine(p, "blender.exe")).FirstOrDefault(File.Exists) ?? "";
        }
    }
    void Update()
    {
        if (Input.GetKeyDown(KeyCode.F8)) visible = !visible;
        if (conversion != null && conversion.IsCompleted)
        {
            status = conversion.IsFaulted ? "Blender failed: " + conversion.Exception.GetBaseException().Message : conversion.Result;
            conversion = null;
        }
    }
    void OnGUI()
    {
        if (GUI.Button(new Rect(Math.Max(0, Screen.width - 160), 8, 150, 28), "Blender Export [F8]")) visible = !visible;
        if (!visible) return;
        window.width = Math.Min(760, Screen.width);
        window.height = Math.Min(650, Screen.height - 40);
        window = GUILayout.Window(GetInstanceID(), window, DrawWindow, "Blender: separate clothing and body");
    }
    void Refresh()
    {
        character = UmaViewerBuilder.Instance ? UmaViewerBuilder.Instance.CurrentUMAContainer : null;
        selections = character ? BlenderModelExporter.GetSelections(character) : new List<BlenderModelExporter.Selection>();
    }
    void DrawWindow(int id)
    {
        var current = UmaViewerBuilder.Instance ? UmaViewerBuilder.Instance.CurrentUMAContainer : null;
        if (current != character) Refresh();
        GUILayout.Label(character ? character.name : "No character loaded");
        GUILayout.Label("For a body base, load a swimsuit/tight costume first. Assign each section; Exclude omits it from BOTH exports.");
        GUILayout.BeginHorizontal();
        if (GUILayout.Button("Refresh sections")) Refresh();
        if (GUILayout.Button("Swimsuit / tight outfit -> Body")) foreach (var s in selections) s.Part = BlenderModelExporter.Part.Body;
        if (GUILayout.Button("Exclude all")) foreach (var s in selections) s.Part = BlenderModelExporter.Part.Exclude;
        GUILayout.EndHorizontal();
        scroll = GUILayout.BeginScrollView(scroll, GUILayout.MinHeight(100), GUILayout.ExpandHeight(true));
        foreach (var s in selections)
        {
            GUILayout.BeginHorizontal();
            GUILayout.Label(s.Label, GUILayout.Width(Math.Max(150, window.width - 300)));
            s.Part = (BlenderModelExporter.Part)GUILayout.Toolbar((int)s.Part, new[] { "Exclude", "Clothing", "Body" });
            GUILayout.EndHorizontal();
        }
        GUILayout.EndScrollView();
        GUILayout.Label("Export folder:"); outputDirectory = GUILayout.TextField(outputDirectory);
        GUILayout.Label("Blender executable (optional for JSON package export):"); blenderPath = GUILayout.TextField(blenderPath);
        GUILayout.BeginHorizontal();
        GUI.enabled = character && conversion == null;
        if (GUILayout.Button("Export package")) Export(false);
        GUI.enabled = character && conversion == null && File.Exists(blenderPath);
        if (GUILayout.Button("Export clothing.blend + body.blend")) Export(true);
        GUI.enabled = true;
        if (GUILayout.Button("Close", GUILayout.Width(60))) visible = false;
        GUILayout.EndHorizontal();
        GUILayout.Label(status, GUILayout.Height(75));
        GUI.DragWindow(new Rect(0, 0, window.width, 24));
    }
    void Export(bool makeBlend)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(outputDirectory)) throw new ArgumentException("Choose an export folder.");
            PlayerPrefs.SetString("BlenderExport.Directory", outputDirectory);
            PlayerPrefs.SetString("BlenderExport.Executable", blenderPath);
            string directory = BlenderModelExporter.Export(character, selections, Path.GetFullPath(outputDirectory));
            status = "Package saved: " + directory;
            if (makeBlend)
            {
                string executable = blenderPath;
                status = "Blender is converting: " + directory;
                conversion = Task.Run(() => Convert(executable, directory));
            }
        }
        catch (Exception e) { status = "Export failed: " + e.Message; UnityEngine.Debug.LogException(e); }
    }
    static string Quote(string value)
    {
        if (value.Contains("\"") || value.Contains("\n") || value.Contains("\r")) throw new ArgumentException("Invalid path.");
        return "\"" + value + "\"";
    }
    static string Convert(string executable, string directory)
    {
        using (var process = new Process())
        {
            process.StartInfo = new ProcessStartInfo
            {
                FileName = executable,
                Arguments = "--background --factory-startup --python-exit-code 1 --python " + Quote(Path.Combine(directory, "uma_blender_import.py")) + " -- " + Quote(Path.Combine(directory, "model.uma.json")) + " --split",
                WorkingDirectory = directory, UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardOutput = true, RedirectStandardError = true
            };
            process.Start();
            var stdout = process.StandardOutput.ReadToEndAsync();
            var stderr = process.StandardError.ReadToEndAsync();
            if (!process.WaitForExit(600000))
            {
                process.Kill(); throw new TimeoutException("Blender exceeded 10 minutes; JSON package remains at " + directory);
            }
            Task.WaitAll(stdout, stderr);
            File.WriteAllText(Path.Combine(directory, "blender.log"), stdout.Result + "\n" + stderr.Result);
            if (process.ExitCode != 0) throw new InvalidOperationException("Exit " + process.ExitCode + ". See " + Path.Combine(directory, "blender.log"));
            var outputs = new[] { "clothing.blend", "body.blend" }.Where(p => File.Exists(Path.Combine(directory, p))).ToArray();
            if (outputs.Length == 0) throw new InvalidOperationException("No .blend was produced. See blender.log.");
            return "Saved " + string.Join(" + ", outputs) + " in " + directory;
        }
    }
}
