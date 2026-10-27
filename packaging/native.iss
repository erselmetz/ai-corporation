; Per-user installation; application data is intentionally outside {app}.
; Uninstall removes installed binaries and shortcuts, and keeps owner data.
#ifndef PackageRoot
  #error PackageRoot must name a verified one-folder build
#endif
#ifndef InstallerOutput
  #error InstallerOutput is required
#endif
#ifndef AppVersion
  #error AppVersion is required
#endif
[Setup]
#ifdef ReviewBuild
AppId={{A08FF794-EB62-44CA-9DA7-83AEB9636607}
AppName=ERSELMETZ AI Review
DefaultDirName={localappdata}\Programs\ERSELMETZ AI Review
#else
AppId={{16D44A43-9566-4B57-AC45-274888F7B5BB}
AppName=ERSELMETZ AI
DefaultDirName={localappdata}\Programs\ERSELMETZ AI
#endif
AppVersion={#AppVersion}
AppPublisher=ERSELMETZ AI
DefaultGroupName=ERSELMETZ AI
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#InstallerOutput}
OutputBaseFilename=ERSELMETZ-AI-Setup-{#AppVersion}-win-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\ERSELMETZ-AI.exe
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Files]
Source: "{#PackageRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
#ifndef ReviewBuild
Name: "{userprograms}\ERSELMETZ AI"; Filename: "{app}\ERSELMETZ-AI.exe"; WorkingDir: "{app}"
#endif

; No UninstallDelete entry: never remove the separate per-user data folder.
; No network downloads, update checks, model installation or automatic launch.

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if FileExists(ExpandConstant('{app}\resources\app.asar')) or
     FileExists(ExpandConstant('{app}\chrome_100_percent.pak')) then
    Result := 'This folder contains the legacy application. Select a separate folder, or uninstall the legacy app while keeping your data, before installing this build.';
end;
