CineCode Setup for Windows

Extract the whole ZIP. Double-click INSTALL_CINECODE.cmd and wait for
“CineCode is ready.” Open the printed folder in Codex and type $cinecode.
Use a normal Windows account. If Windows requests administrator approval for
a required component, review the prompt before proceeding.

Setup uses installed components first and uses Microsoft WinGet for missing
ones. If Windows App Installer is missing, follow the official instructions at
https://learn.microsoft.com/windows/package-manager/winget/ and run setup again.

The launcher uses a PowerShell execution-policy override for its own process
so the extracted setup script can run. Windows security settings retain their
configured values. Review any Windows prompt using the normal system controls.

Run the same setup again to repair a same-version install. Film projects and
state are preserved. A different installed version requires a separate folder.
The setup window shows the path to its diagnostic log if a check fails.
