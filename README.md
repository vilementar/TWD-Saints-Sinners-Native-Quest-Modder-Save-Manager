# TWD: Saints & Sinners — Native Quest Modder & Save Manager

An all-in-one standalone modding utility and save game manager for **The Walking Dead: Saints & Sinners** natively running on Meta Quest headsets. 

**🎥 Full Step-by-Step Guide:** [Watch the video tutorial on YouTube](SOON)

---

## ⚠️ Crucial Requirement: The Modified APK

For this tool to work, **you must install the custom `.apk` attached in the Releases tab of this repository**. 

The vanilla retail version of the game locks its internal configuration and save files inside protected Android system folders. The provided custom `.apk` safely re-routes the game's working directory to `/sdcard/vlmn/TWD/`, allowing this script to freely inspect and modify your progress.

---

## 🌟 Key Features

* **Native Sinners Mode Toggle**: Instantly activate hidden developer cheats and accessibility options (`bSinner=True`) directly on the headset via a kinetic Material You toggle switch.
* **Full Configuration Editor**: Read, edit, and push all parameters within `GameUserSettings.ini` (handling Linux `LF` line endings automatically to prevent engine resets).
* **Advanced GVAS Save Manager**:
  * Automatically detects multi-profile save structures (`Profile0`, `Profile1`, etc.).
  * Inspects binary save files to display in-game days survived and exact playtime (hours/minutes).
  * Safely edits binary player attributes (Health, Stamina, Day count) without corrupting GVAS serialization headers.
  * Instant one-click save file backups and low-level file renaming directly on the headset.
* **Automated Permission Injection**: Uses direct `AppOps` commands to grant the game persistent storage management rights.

---

## 🚀 How to Use

1. Download and install the **modified `.apk`** (from this repository's Releases page) onto your Meta Quest.
2. **Launch the game once** to let the engine generate the base folder structure inside `/sdcard/vlmn/TWD/`, then close it.
3. Connect your Meta Quest headset to your PC via USB with **USB Debugging** enabled.
4. Run `TWD_Modder.py`.
5. Go to the **Quick Actions** tab and click **[ Grant Storage Permission ]** to authorize the new file paths.
6. Use the toggles to enable Sinners Mode, or switch to the **Saves** tab to edit your survival stats!
