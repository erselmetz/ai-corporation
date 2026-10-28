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
SetupLogging=no

[Files]
Source: "{#PackageRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
#ifdef ReviewBuild
Name: "{userprograms}\ERSELMETZ AI Review"; Filename: "{app}\ERSELMETZ-AI.exe"; Parameters: "--profile ""{localappdata}\ERSELMETZ AI Review"""; WorkingDir: "{app}"
#else
Name: "{userprograms}\ERSELMETZ AI"; Filename: "{app}\ERSELMETZ-AI.exe"; WorkingDir: "{app}"
#endif

; No UninstallDelete entry: never remove the separate per-user data folder.
; No network downloads, update checks, model installation or automatic launch.

[Code]
var RemoveOwnerData: Boolean;

function OwnerDataDirectory(): String;
begin
#ifdef ReviewBuild
  Result := ExpandConstant('{localappdata}\ERSELMETZ AI Review\ERSELMETZ AI');
#else
  Result := ExpandConstant('{localappdata}\ERSELMETZ AI');
#endif
end;

function SafeDataTree(const Folder: String; Depth: Integer): Boolean;
var Entry: TFindRec;
begin
  Result := False;
  if Depth > 64 then Exit;
  if not DirExists(Folder) then begin Result := True; Exit; end;
  { Never follow a junction/symlink out of the known per-user data tree. }
  if not FindFirst(Folder, Entry) then Exit;
  try
    if (Entry.Attributes and $400) <> 0 then Exit;
  finally FindClose(Entry); end;
  Result := True;
  if FindFirst(Folder + '\*', Entry) then begin
    try
      repeat
        if (Entry.Name <> '.') and (Entry.Name <> '..') then begin
          if (Entry.Attributes and $400) <> 0 then begin Result := False; Exit; end;
          if ((Entry.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0) and
             not SafeDataTree(Folder + '\' + Entry.Name, Depth + 1) then begin Result := False; Exit; end;
        end;
      until not FindNext(Entry);
    finally FindClose(Entry); end;
  end;
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
  RemoveOwnerData := False;
  { Silent uninstall always keeps data. Destruction requires an explicit interactive choice. }
  if not UninstallSilent then
    RemoveOwnerData := MsgBox('Also permanently remove your local chats, Brain, preferences and owner credentials? Choose No to keep them for reinstall. This cannot be undone.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var Folder: String;
begin
  if (CurUninstallStep = usPostUninstall) and RemoveOwnerData then begin
    Folder := OwnerDataDirectory();
    if SafeDataTree(Folder, 0) then begin
      if not DelTree(Folder, True, True, True) then
        MsgBox('Some owner data could not be removed. No alternate folder was touched.', mbError, MB_OK);
    end else
      MsgBox('Owner data contains a linked or unsupported folder and was kept. No linked target was touched.', mbError, MB_OK);
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if FileExists(ExpandConstant('{app}\resources\app.asar')) or
     FileExists(ExpandConstant('{app}\chrome_100_percent.pak')) then
    Result := 'This folder contains the legacy application. Select a separate folder, or uninstall the legacy app while keeping your data, before installing this build.';
end;
