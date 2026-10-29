; Sapline's Windows installer (Inno Setup 6). The automatic build makes it:
;   iscc /DAppVersion=2026-10-20g /DSrc=<folder with Sapline.exe and _internal> /O<out> installer\Sapline.iss
; It installs for the current user only (no admin rights needed) into %LOCALAPPDATA%\Programs\Sapline.
; The AppId never changes, so an update over an installed copy keeps its data. An installed copy that lives
; in another folder (an earlier name) is moved here: the data is copied over and the app removes the old folder.
; The run log, pictures and settings live next to the app and are kept on updates and on uninstall.
#ifndef AppVersion
  #define AppVersion "0-dev"
#endif
#ifndef Src
  #define Src "..\build_tmp\dist\Sapline"
#endif

[Setup]
AppId={{6C1F0B6E-3D2A-4E5B-9A7C-4D8E2F1A0B93}
AppName=Sapline
AppVersion={#AppVersion}
AppVerName=Sapline {#AppVersion}
AppPublisher=Sapline (fan project, not affiliated with Nexon)
DefaultDirName={localappdata}\Programs\Sapline
UsePreviousAppDir=no
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=Sapline-Setup-{#AppVersion}
SetupIconFile=..\sapline\icon.ico
UninstallDisplayIcon={app}\Sapline.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; updates start the setup only once the old copy has closed (see sapline/update.py), so nothing to close here
CloseApplications=no

[Tasks]
Name: "desktopicon"; Description: "Put a Sapline icon on the desktop"; Flags: checkedonce

[InstallDelete]
; the program's libraries are replaced as a whole on every update (the data and settings are not in here)
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#Src}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\GUIDE.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\Sapline"; Filename: "{app}\Sapline.exe"
Name: "{userdesktop}\Sapline"; Filename: "{app}\Sapline.exe"; Tasks: desktopicon

[Run]
; after a normal install: a "Start Sapline" tick box; after a quiet update: starts it again by itself
Filename: "{app}\Sapline.exe"; Description: "Start Sapline"; Flags: nowait postinstall

[Code]
// An installed copy in another folder (the registry remembers where): its data comes along to the new folder,
// and the app removes the old folder on its first start (moved_from.txt tells it which).
var
  OldDir: String;

function InitializeSetup(): Boolean;
begin
  if not RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6C1F0B6E-3D2A-4E5B-9A7C-4D8E2F1A0B93}_is1',
                             'Inno Setup: App Path', OldDir) then
    OldDir := '';
  Result := True;
end;

procedure CopyTree(const Src, Dst: String);
var
  R: TFindRec;
begin
  ForceDirectories(Dst);
  if FindFirst(Src + '\*', R) then
  begin
    try
      repeat
        if (R.Name <> '.') and (R.Name <> '..') then
        begin
          if (R.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
            CopyTree(Src + '\' + R.Name, Dst + '\' + R.Name)
          else if not FileExists(Dst + '\' + R.Name) then
            FileCopy(Src + '\' + R.Name, Dst + '\' + R.Name, False);
        end;
      until not FindNext(R);
    finally
      FindClose(R);
    end;
  end;
end;

procedure CopyOne(const Src, Dst: String);
begin
  if FileExists(Src) and not FileExists(Dst) then
  begin
    ForceDirectories(ExtractFileDir(Dst));
    FileCopy(Src, Dst, False);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  NewDir: String;
begin
  if CurStep <> ssPostInstall then
    exit;
  NewDir := RemoveBackslashUnlessRoot(ExpandConstant('{app}'));
  if (OldDir = '') or (CompareText(RemoveBackslashUnlessRoot(OldDir), NewDir) = 0) or not DirExists(OldDir) then
    exit;
  Log('The app lived in ' + OldDir + ': bringing its data to ' + NewDir);
  if DirExists(OldDir + '\scans') then
    CopyTree(OldDir + '\scans', NewDir + '\scans');
  CopyOne(OldDir + '\settings.json', NewDir + '\settings.json');
  CopyOne(OldDir + '\mobs.txt', NewDir + '\mobs.txt');
  CopyOne(OldDir + '\updates\pending.json', NewDir + '\updates\pending.json');
  SaveStringToFile(NewDir + '\moved_from.txt', OldDir, False);
end;
