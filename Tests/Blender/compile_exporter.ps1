param(
    [Parameter(Mandatory=$true)][string]$UnityManagedDirectory,
    [Parameter(Mandatory=$true)][string]$MonoRoot
)
$ErrorActionPreference = 'Stop'
$repoPath = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$resultPath = Join-Path $repoPath 'Tests\Local'
New-Item -ItemType Directory -Force $resultPath | Out-Null
$stub = @'
using UnityEngine;
// Only the two existing integration types are stubbed. Actual Unity APIs are referenced.
public class UmaContainerCharacter : MonoBehaviour {}
public class UmaViewerBuilder : MonoBehaviour {
    public static UmaViewerBuilder Instance;
    public UmaContainerCharacter CurrentUMAContainer;
}
'@
[IO.File]::WriteAllText((Join-Path $resultPath 'IntegrationStubs.cs'), $stub)
$references = @('UnityEngine.CoreModule.dll','UnityEngine.AnimationModule.dll','UnityEngine.IMGUIModule.dll',
    'UnityEngine.InputLegacyModule.dll','UnityEngine.ImageConversionModule.dll','UnityEngine.JSONSerializeModule.dll','Unity.Collections.dll')
$compilerArgs = @('-nologo','-target:library',('-out:' + (Join-Path $resultPath 'BlenderExporter.CompileCheck.dll')),
    ('-r:' + (Join-Path $MonoRoot 'lib\mono\4.5\Facades\netstandard.dll')))
foreach ($reference in $references) { $compilerArgs += '-r:' + (Join-Path $UnityManagedDirectory $reference) }
$compilerArgs += Join-Path $resultPath 'IntegrationStubs.cs'
$compilerArgs += Join-Path $repoPath 'Assets\Scripts\Exporters\BlenderModelExporter.cs'
$compilerArgs += Join-Path $repoPath 'Assets\Scripts\Exporters\BlenderExportPanel.cs'
& (Join-Path $MonoRoot 'bin\mono.exe') (Join-Path $MonoRoot 'lib\mono\4.5\csc.exe') @compilerArgs
if ($LASTEXITCODE -ne 0) { throw 'Exporter compile check failed.' }
Write-Output 'UMA_EXPORTER_COMPILE_CHECK_OK (Unity reference APIs, integration stubs; not a full Unity build)'
