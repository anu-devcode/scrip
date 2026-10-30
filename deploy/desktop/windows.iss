#ifndef ProductVersion
  #error ProductVersion must be supplied by the release build
#endif
[Setup]
AppId={{8F5BF94A-FC66-465E-BB94-77421F86651E}
AppName=Scrip
AppVersion={#ProductVersion}
AppPublisher=Anwar Dev
AppPublisherURL=https://scrip.anwardev.me
AppSupportURL=https://scrip.anwardev.me/quickstart.html
DefaultDirName={localappdata}\Programs\Scrip
DefaultGroupName=Scrip
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist\installers
OutputBaseFilename=Scrip-{#ProductVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableDirPage=yes
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\Scrip.exe
CloseApplications=yes
RestartApplications=no
SetupMutex=ScripInstaller
LicenseFile=..\..\LICENSE
SetupIconFile=..\..\build\native\scrip.ico
MinVersion=10.0

[Files]
Source: "..\..\dist\Scrip\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\LICENSE"; DestDir: "{app}"
Source: "..\..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"

[Icons]
Name: "{group}\Scrip"; Filename: "{app}\Scrip.exe"
Name: "{autodesktop}\Scrip"; Filename: "{app}\Scrip.exe"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\Scrip.exe"; Description: "Open Scrip"; Flags: nowait postinstall skipifsilent

; Private state and workspace hooks are deliberately preserved on uninstall.
; Use Connections > Disconnect before uninstalling to remove owned hooks.
