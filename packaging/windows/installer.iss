; Installeur Windows (Inno Setup 6). Compilé par packaging\build.py :
;   iscc /DAppVersion=1.0.0 /DAppArch=x64 packaging\windows\installer.iss
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef AppArch
  #define AppArch "x64"
#endif

[Setup]
AppId={{6E0B8B9A-3F7C-4C57-9D2B-D15C3A7A1F42}
AppName=DiskMap
AppVersion={#AppVersion}
AppPublisher=DiskMap
DefaultDirName={autopf}\DiskMap
DefaultGroupName=DiskMap
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\DiskMap.exe
SetupIconFile=..\assets\icon.ico
OutputDir=..\..\dist
OutputBaseFilename=DiskMap-{#AppVersion}-setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
WizardStyle=modern
#if AppArch == "x64"
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
#endif

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\DiskMap\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\DiskMap"; Filename: "{app}\DiskMap.exe"
Name: "{autodesktop}\DiskMap"; Filename: "{app}\DiskMap.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\DiskMap.exe"; Description: "{cm:LaunchProgram,DiskMap}"; Flags: nowait postinstall skipifsilent
