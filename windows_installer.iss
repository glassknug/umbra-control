#ifndef PackageDir
  #error PackageDir is required
#endif
[Setup]
AppId=glassknug.UmbraControl
AppName=Umbra Control
AppVersion=0.6.3
AppPublisher=glassknug
AppPublisherURL=https://github.com/glassknug/umbra-control
DefaultDirName={localappdata}\Programs\UmbraControl
DefaultGroupName=Umbra Control
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename=UmbraControl-Windows-0.6.3-Setup
OutputDir={#OutputDir}
SetupIconFile=umbra-icon.ico
UninstallDisplayIcon={app}\UmbraControl.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
LicenseFile=LICENSE
InfoAfterFile=WINDOWS_PACKAGE.txt
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked
[Files]
Source: "{#PackageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\Umbra Control"; Filename: "{app}\UmbraControl.exe"; WorkingDir: "{app}"; AppUserModelID: "glassknug.UmbraControl.WindowsPreview"
Name: "{autodesktop}\Umbra Control"; Filename: "{app}\UmbraControl.exe"; WorkingDir: "{app}"; Tasks: desktopicon
[Run]
Filename: "{app}\UmbraControl.exe"; Description: "Open Umbra Control"; Flags: nowait postinstall skipifsilent
