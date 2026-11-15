#ifndef ProductVersion
  #error ProductVersion must be supplied by the release build
#endif
[Setup]
AppId={{09C01260-7E81-4BC2-BB3C-F215D4405581}
AppName=Scrip Terminal
AppVersion={#ProductVersion}
AppPublisher=Anwar Dev
DefaultDirName={localappdata}\Programs\ScripTerminal
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist\installers
OutputBaseFilename=Scrip-Terminal-{#ProductVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
CloseApplications=yes
RestartApplications=no
ChangesEnvironment=yes
LicenseFile=..\..\LICENSE
MinVersion=10.0

[Files]
Source: "..\..\dist\ScripTerminal\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\LICENSE"; DestDir: "{app}"
Source: "..\..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"

[Tasks]
Name: terminalpath; Description: "Add Scrip to your user PATH for terminal commands"; Flags: checkedonce

[Code]
function SamePath(Left, Right: String): Boolean;
begin
  Result := CompareText(RemoveBackslashUnlessRoot(RemoveQuotes(Trim(Left))),
    RemoveBackslashUnlessRoot(RemoveQuotes(Trim(Right)))) = 0;
end;

function FilterPath(Value, Target: String; var Found: Boolean): String;
var
  Item: String;
  Separator: Integer;
begin
  Result := '';
  Found := False;
  while Value <> '' do begin
    Separator := Pos(';', Value);
    if Separator = 0 then begin
      Item := Value;
      Value := '';
    end else begin
      Item := Copy(Value, 1, Separator - 1);
      Delete(Value, 1, Separator);
    end;
    if SamePath(Item, Target) then Found := True
    else if Item <> '' then begin
      if Result <> '' then Result := Result + ';';
      Result := Result + Item;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Current, Filtered, AppPath: String;
  Found: Boolean;
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('terminalpath') then begin
    AppPath := ExpandConstant('{app}');
    RegQueryStringValue(HKCU, 'Environment', 'Path', Current);
    Filtered := FilterPath(Current, AppPath, Found);
    if not Found then begin
      if Current <> '' then Current := Current + ';';
      if not RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Current + AppPath) then
        RaiseException('Could not add Scrip to your user PATH.');
      RegWriteStringValue(HKCU, 'Software\Scrip\TerminalInstaller', 'AddedPath', AppPath);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Current, Filtered, AddedPath: String;
  Found: Boolean;
begin
  if CurUninstallStep = usUninstall then begin
    if RegQueryStringValue(HKCU, 'Software\Scrip\TerminalInstaller', 'AddedPath', AddedPath)
      and SamePath(AddedPath, ExpandConstant('{app}')) then begin
      if RegQueryStringValue(HKCU, 'Environment', 'Path', Current) then begin
        Filtered := FilterPath(Current, AddedPath, Found);
        if Found then RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Filtered);
      end;
      RegDeleteValue(HKCU, 'Software\Scrip\TerminalInstaller', 'AddedPath');
    end;
  end;
end;
