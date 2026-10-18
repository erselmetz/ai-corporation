!macro customUnInstall
  MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON1 "Keep local ERSELMETZ AI owner data, conversations, backups, and diagnostics?$\r$\n$\r$\nYes keeps this data for a later reinstall. No permanently removes the entire ERSELMETZ AI data folder under your Windows user profile. Choose No only if you intend to remove it." IDYES keepAppData
  RMDir /r "$LOCALAPPDATA\ERSELMETZ AI"
  Goto uninstallDataChoiceDone
  keepAppData:
  DetailPrint "Keeping local ERSELMETZ AI application data."
  uninstallDataChoiceDone:
!macroend