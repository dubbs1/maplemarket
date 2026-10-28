; MapleReader's Windows installer (Inno Setup 6). The automatic build makes it:
;   iscc /DAppVersion=2026-10-20g /DSrc=<folder with MapleReader.exe and _internal> /O<out> installer\MapleReader.iss
; It installs for the current user only (no admin rights needed) into %LOCALAPPDATA%\Programs\MapleReader.
; The run log, pictures and settings live next to the app and are kept on updates and on uninstall.
#ifndef AppVersion
  #define AppVersion "0-dev"
#endif
#ifndef Src
  #define Src "..\build_tmp\dist\MapleReader"
#endif

[Setup]
AppId={{6C1F0B6E-3D2A-4E5B-9A7C-4D8E2F1A0B93}
AppName=MapleReader
AppVersion={#AppVersion}
AppVerName=MapleReader {#AppVersion}
AppPublisher=Sapline (fan project, not affiliated with Nexon)
DefaultDirName={localappdata}\Programs\MapleReader
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=MapleReader-Setup-{#AppVersion}
SetupIconFile=..\shopreader\icon.ico
UninstallDisplayIcon={app}\MapleReader.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; updates start the setup only once the old copy has closed (see shopreader/update.py), so nothing to close here
CloseApplications=no

[Tasks]
Name: "desktopicon"; Description: "Put a MapleReader icon on the desktop"; Flags: checkedonce

[InstallDelete]
; the program's libraries are replaced as a whole on every update (the data and settings are not in here)
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#Src}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\GUIDE.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\MapleReader"; Filename: "{app}\MapleReader.exe"
Name: "{userdesktop}\MapleReader"; Filename: "{app}\MapleReader.exe"; Tasks: desktopicon

[Run]
; after a normal install: a "Start MapleReader" tick box; after a quiet update: starts it again by itself
Filename: "{app}\MapleReader.exe"; Description: "Start MapleReader"; Flags: nowait postinstall
