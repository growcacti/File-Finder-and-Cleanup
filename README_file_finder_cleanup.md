# File Finder and Cleanup

A Python desktop program for finding unwanted files mixed in with files you want to keep. Search by filename, extension, or wildcard patterns, review the matches, then copy, move, or permanently delete selected files.

Works with local folders, USB drives, and accessible Samba network shares on Linux and Windows.

## Features

- Search several folders or drives in one search.
- Include subfolders, or search only the top level.
- Match filenames using wildcards or literal text.
- Filter by one or more extensions.
- Display matching filenames, file sizes in bytes, and full paths.
- Copy or move selected files to an output folder while preserving their folder structure.
- Permanently delete selected files after confirmation.
- Skip existing destination files instead of overwriting them.
- Save search folders, filters, search options, and the output folder between sessions.
- Export the current results to CSV.
- Stop searches and file operations, and view errors in the log.
- Open Samba addresses through your system file manager and select mounted GVfs shares on Linux.

## Requirements and starting the program

You need Python 3 with Tkinter. No pip packages are required.

### MX Linux / Debian

If Python or Tkinter is missing, install the system packages:

```bash
sudo apt install python3 python3-tk
```

Open a terminal in the folder containing the program and run:

```bash
python3 file_finder_cleanup.py
```

If you use a separately installed Python, such as a version under `/usr/local`, it must have its own working Tkinter support. You can use the system Python explicitly:

```bash
/usr/bin/python3 file_finder_cleanup.py
```

### Windows

Install Python with Tcl/Tk support, then run from the program's folder:

```powershell
py file_finder_cleanup.py
```

## Quick start

1. Click **Browse / Add** to choose a search folder. Repeat to search several locations. Alternatively, paste a folder path and click **Add path**.
2. Enter filename patterns, extensions, or both.
3. Leave **Include subfolders** checked to search inside nested folders.
4. Click **Search** and review the results.
5. Use Ctrl-click or Shift-click to select files, or click **Select all**.
6. For copying or moving, choose an **Output folder** outside every search folder.
7. Click **Copy selected**, **Move selected**, or **Delete permanently selected**, then review the confirmation.

**Remove** removes a location from the search-folder list; it does not remove that folder from your disk.

## Filename and extension examples

Separate multiple patterns or extensions with semicolons. Do not put quotation marks around them.

| Goal | Filename patterns | Extensions |
| --- | --- | --- |
| Find temporary files | `*.tmp` | Leave blank |
| Find temporary and backup files | `*.tmp;*.bak` | Leave blank |
| Find filenames containing “sample” | `*sample*` | Leave blank |
| Find common thumbnail/settings files | `Thumbs.db;desktop.ini` | Leave blank |
| Find several extensions | Leave blank | `tmp;bak;log` |
| Find sample videos with either extension | `*sample*` | `mp4;avi` |
| Find report plus one character | `report?.txt` | Leave blank |
| Find one exact filename | `unwanted.txt` | Leave blank |

### How matching works

- With **Wildcards** checked, `*` matches any number of characters and `?` matches one character. Bracket patterns such as `[0-9]` are also supported.
- With **Wildcards** unchecked, the filename field searches for literal text anywhere in the filename. For example, `sample` finds `movie_sample.mp4`.
- Multiple filename patterns are alternatives: matching any one is enough.
- Multiple extensions are alternatives too. Leading dots are optional: `tmp` and `.tmp` both work. Use the filename field for wildcard extension expressions.
- If both fields are filled in, a file must match a filename pattern **and** an extension.
- With both fields blank, all regular files in the searched locations are eligible.
- Matching ignores letter case unless **Case sensitive** is checked.
- Matching uses the filename, including its extension, rather than the full folder path.
- Hidden files are included. Symbolic-link files and linked subdirectories encountered during traversal are skipped.

## Copy, move, and output folders

The program preserves each file's path beneath its search folder and adds the search folder's name under the output folder.

For example, searching `/media/Movies` and moving this file:

```text
/media/Movies/Film_A/extras/sample.mp4
```

into `/home/jh/Review` produces:

```text
/home/jh/Review/Movies/Film_A/extras/sample.mp4
```

Search roots with identical names receive numbered labels. If a destination file already exists, that file is skipped and the reason is logged. Nothing is automatically overwritten or renamed to resolve a file conflict.

The output must not equal, or be inside, any search root. For example, if you search `/media/Movies`, choose a separate folder such as `/media/Review`, rather than `/media/Movies/Review`.

**Copy** leaves the source in place. **Move** copies the file and its metadata first, then removes the source after that succeeds. There is no checksum verification or automatic undo. If removing the source fails after copying, both copies may remain; check the log before retrying.

Empty source folders are left in place. Folder copying, folder deletion, and renaming are not features of this program.

## Deleting files

**Delete permanently selected bypasses Trash and Recycle Bin.** The program asks for confirmation and operates only on selected result rows.

For files you are unsure about, use **Move selected** to place them in a separate review folder first. You can then check them before deciding whether to delete them.

Before an operation, the program checks the source file's identity, size, and modification time against the search result. If those checks differ, it skips the file. Search again to refresh the results. This is a change check, not a content comparison.

## Samba shared folders

### MX Linux / Xfce

1. Enter a share address in the path field, for example:

   ```text
   smb://laptop.local/Movies
   ```

2. Click **Open Samba**. The program asks your desktop to open the address in its file manager.
3. Sign in if prompted and open the share.
4. Return to the program and click **Add path**. Alternatively, click **Mounted shares**, select the mounted share, and add it.
5. Enter your filters and click **Search**.

Include a share name: `smb://laptop.local/` alone is not a searchable root in this program. Use the actual share name advertised by your server.

The `smb://` resolver on Linux looks for a GVfs mount under `/run/user/<your-user-id>/gvfs`. Use the same server name you used to open the share. A hostname, IP address, and alternate hostname are not automatically treated as equivalent.

If your file manager opens the share without creating a GVfs mount—for example, some KDE setups—use a normal CIFS-mounted folder path instead. **Mounted shares** only lists GVfs Samba mounts; manually mounted shares are added using **Browse / Add** or their folder paths.

The output folder can also be on a mounted share. The same rule applies: output must be outside all search roots.

Do not include usernames or passwords in Samba URLs. Authenticate through your system file manager. The program does not save Samba passwords or change server permissions.

### Windows

Use a mapped network drive or enter a UNC path:

```text
\\laptop.local\Movies
```

You can also add an `smb://server/share` address; the program converts it to a Windows network path. Authenticate to the share through Windows first if necessary.

### Permission errors

Being able to view or copy a file does not necessarily mean you can move or delete it. Copying needs source read access and destination write access. Moving also needs permission to remove the source file; deletion depends on permissions on its containing folder and the server's share rules.

If an operation reports **Permission denied**, inspect the log. Correct access on the Samba/OMV server or sign in with an account that has the required access. Running this program as administrator on your own computer does not grant additional rights on the server.

## Results, export, and stopping

- **Select all** selects every current result; **Clear selection** deselects the rows.
- **Export CSV** exports all current result rows, not just selected rows, with filename, size in bytes, and full path.
- Successful moves and deletions remove their rows from the results. Copies leave their rows listed.
- **Stop** requests cancellation. A file transfer already in progress finishes before the next file is considered. A blocked network operation can delay stopping.
- Stopping does not undo completed actions.
- If you close the window while work is running, the program requests a stop. Close it again after the operation finishes.
- The log displays completed actions, skipped files, and errors. It is not saved automatically.

## Saved settings

Settings are saved when a search or file operation begins and when the program closes normally. They include search folders, filename patterns, extensions, output folder, and search-option checkboxes.

This version does not retain a separate searchable history of previous searches or a permanent operation log. The **Help** button provides a shorter guide inside the application.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| No matching files | Check both filters; when both are filled, both must match. Check Case sensitive and Include subfolders. |
| A word finds no results with wildcards enabled | Use `*word*` to match a word anywhere in the filename. |
| Share is not mounted | Open it through Open Samba, sign in, then try Mounted shares or a manually mounted path. |
| Folder is not accessible | Check that the drive/share is connected and the path exists. |
| Existing destination file | Choose another output folder or review the existing file; the program will not overwrite it. |
| File changed since search | Run Search again before acting on that file. |
| Output must be outside all search folders | Choose a separate output folder, or narrow the search roots. |
| Permission denied | Check the containing folder and server permissions, especially for move/delete. |
| Missing tkinter module | Install Tkinter for the Python interpreter used to launch the program. |

## Scope and validation

The program is intended for Linux and Windows desktops with Tkinter. Filename matching, copying, moving, and destination collision protection were checked locally. Your particular Samba server, network reliability, desktop integration, and permissions were not tested remotely.
