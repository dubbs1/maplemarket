; Sapline's Windows installer (Inno Setup 6). The automatic build makes it:
;   iscc /DAppVersion=2026-10-20g /DSrc=<folder with Sapline.exe and _internal> /O<out> installer\Sapline.iss
; It installs for the current user only (no admin rights needed) into %LOCALAPPDATA%\Programs\Sapline.
; The AppId never changes, so an update over an installed copy keeps its folder and data.
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
