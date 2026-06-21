# TWD: Saints & Sinners — Native Quest Modder & Save Manager

An all-in-one standalone modding utility and save game manager for **The Walking Dead: Saints & Sinners** natively running on Meta Quest headsets. 

Designed to bypass Android 11+ Scoped Storage restrictions, this tool enables direct modification of in-game configuration files and binary GVAS save data without requiring an active PC connection during gameplay.

##  Key Features

* **Native Sinners Mode Toggle**: Instantly activate hidden developer cheats and accessibility options (`bSinner=True`) directly on the headset via a kinetic Material You toggle switch.
* **Full Configuration Editor**: Read, edit, and push all parameters within `GameUserSettings.ini` (handling Linux `LF` line endings automatically to prevent engine resets).
* **Advanced GVAS Save Manager**:
  * Automatically detects multi-profile save structures (`Profile0`, `Profile1`, etc.).
  * Inspects actual binary save files to display in-game days survived and exact playtime (hours/minutes).
  * Safely edits binary player attributes (Health, Stamina, Day count) without corrupting GVAS serialization headers.
  * Instant one-click save file backups and low-level renaming.
* **Automated Permission Injection**: Uses direct `AppOps` commands to grant the game persistent storage management rights, permanently unlocking save folder access.

##  How to Use

1. Connect your Meta Quest headset via USB with USB Debugging enabled.
2. Run `TWD_Modder.py`.
3. Go to **Quick Actions** and click **Grant Storage Permission** to initialize the open file structure.
4. Toggle **Sinners Mode** or switch to the **Saves** tab to edit your physical survival progress.
