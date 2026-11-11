; Compile only after the signed runtime and Adobe packages pass the release gate.
#ifndef ReleaseRoot
  #error Supply /DReleaseRoot with the verified release staging directory.
#endif
[Setup]
AppId={{8AF120B0-8187-4D39-B02B-144840F93125}
AppName=Storylens
AppVersion=0.4.0
DefaultDirName={localappdata}\Programs\Hinglish Editor
DefaultGroupName=Storylens
PrivilegesRequired=lowest
OutputBaseFilename=HinglishEditor-Setup-0.4.0
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\HinglishEditor.exe
[Types]
Name: "desktop"; Description: "Desktop edition"
Name: "plugins"; Description: "Editor Plugins edition"
[Components]
Name: "runtime"; Description: "Shared local editing engine"; Types: desktop plugins; Flags: fixed
Name: "plugins"; Description: "Editor integrations"; Types: plugins
[Files]
Source: "{#ReleaseRoot}\runtime\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: runtime
Source: "{#ReleaseRoot}\plugins\*"; DestDir: "{app}\plugins"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: plugins
Source: "{#ReleaseRoot}\Install-Resolve.ps1"; DestDir: "{app}"; Components: plugins
[Icons]
Name: "{group}\Storylens"; Filename: "{app}\HinglishEditor.exe"; Parameters: "--edition desktop"; Components: runtime
Name: "{group}\Activate Editor Plugins"; Filename: "{app}\HinglishEditor.exe"; Parameters: "--edition plugins"; Components: plugins
[Run]
Filename: "{app}\HinglishEditor.exe"; Parameters: "--edition desktop"; Description: "Open Storylens"; Flags: nowait postinstall skipifsilent; Check: not WizardIsComponentSelected('plugins')
Filename: "{app}\HinglishEditor.exe"; Parameters: "--edition plugins"; Description: "Activate your Plugin edition"; Flags: nowait postinstall skipifsilent; Check: WizardIsComponentSelected('plugins')
; Adobe panels are installed by the host's supported ZXP/CCX installer.
; Do not switch Adobe PlayerDebugMode on for customers.
