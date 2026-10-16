#!/usr/bin/env python3
"""File Finder and Cleanup — Python 3 / Tkinter, Linux and Windows.
Run: python3 file_finder_cleanup.py
No third-party packages required. Help is available inside the application.
"""
import csv
import fnmatch
import json
import os
from pathlib import Path
import queue
import shutil
import threading
import subprocess
import sys
from urllib.parse import urlsplit, unquote
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

CONFIG = Path.home() / '.file_finder_cleanup.json'


def network_path(raw):
    if not raw.lower().startswith('smb://'):
        return Path(raw).expanduser().resolve()
    url = urlsplit(raw)
    if url.username or url.password:
        raise ValueError('Do not put passwords in paths. Sign in using your file manager.')
    parts = [unquote(x) for x in url.path.split('/') if x]
    if not url.hostname or not parts:
        raise ValueError('Include a share name, for example smb://laptop.local/Movies')
    if os.name == 'nt':
        return Path('//' + url.hostname + '/' + '/'.join(parts)).resolve()
    base = Path('/run/user') / str(os.getuid()) / 'gvfs'
    if base.is_dir():
        for mount in base.iterdir():
            fields = dict(item.split('=', 1) for item in mount.name.split(',') if '=' in item)
            if (fields.get('server', '').casefold() == url.hostname.casefold()
                    and fields.get('share', '').casefold() == parts[0].casefold()):
                return mount.joinpath(*parts[1:]).resolve()
    raise ValueError('Share is not mounted. Click Open Samba, sign in in your file manager, then try again. You can also add its mounted folder path.')



def patterns(text):
    return [p.strip() for p in text.split(';') if p.strip()]


def matches(name, names, extensions, wildcard=True, case=False):
    n = name if case else name.casefold()
    def norm(s):
        return s if case else s.casefold()
    name_ok = not names or any(fnmatch.fnmatchcase(n, norm(p)) if wildcard
                              else norm(p) in n for p in names)
    ext_ok = not extensions or any(n.endswith('.' + norm(p).lstrip('*.'))
                                   for p in extensions)
    return name_ok and ext_ok


def signature(path):
    s = path.lstat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)


def transfer(source, destination, move=False):
    """Exclusive creation: never overwrite an existing destination."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with source.open('rb') as src, destination.open('xb') as dst:
            created = True
            shutil.copyfileobj(src, dst)
        shutil.copystat(source, destination)
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise
    if move:
        source.unlink()


HELP = '''FILE FINDER AND CLEANUP

1. Add one or more folders (or paste a folder path and press Add path).
2. Set filename patterns and/or extensions, then Search.
3. Review results. Ctrl-click or Shift-click to select; Select all selects all matches.
4. Choose an output folder for Copy or Move. Actions affect selected rows only.

FILTER EXAMPLES
Filename patterns: *.tmp;*.bak   (either pattern matches)
Filename patterns: *sample*     (sample anywhere in the filename)
Filename patterns: Thumbs.db;desktop.ini
Filename patterns: report?.txt  (? matches one character)
Extensions: tmp;bak;log         (dots are optional)
Both filters filled: a file must satisfy BOTH filters.
Blank filters: all files. Wildcards off: filename field uses literal contains matching.
Patterns are separated by semicolons. Matching ignores case unless checked.
Patterns match filenames, not folder names. Only files are listed or changed.

COPY / MOVE
Output structure: output/root-name/relative/subfolders/file.
If several roots have the same name, each receives its own numbered folder.
Existing destination files are skipped and reported; nothing is overwritten.
Move copies first, then removes the source after a successful copy.
Copy/Move rejects an output folder inside ANY search root (or equal to one).
Use a separate output folder, such as a quarantine folder, to review unwanted files.

DELETE
Delete permanently removes selected files, bypassing Trash/Recycle Bin.
A confirmation is required. Moving to a quarantine folder is reversible instead.
Files changed since the search are skipped. Search again to refresh them.
Symbolic links and linked directories are skipped. Hidden files ARE included.

NETWORK SHARES
Windows: use a mapped drive or a UNC path such as \\\\server\\share.
Linux: use a mounted share folder, including a GVfs path under /run/user/UID/gvfs.
For smb://server/share: enter it in the path field, click Open Samba, and sign in.
Then Add path and Search. Mounted shares lists GVfs Samba mounts on Linux.
The server name must match the name used to mount it. Manual CIFS mounts
work using their normal folder paths. Output can also be a mounted share.

Folders and filters are saved automatically. Export CSV saves the results list.
Stop cancels searching, or stops a file operation after the current file finishes.
Errors and completed actions appear in the log. No folder is deleted.
'''


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('File Finder and Cleanup')
        self.geometry('1100x760')
        self.minsize(850, 600)
        self.q = queue.Queue()
        self.stop = threading.Event()
        self.busy = False
        self.rows = {}
        self.path = tk.StringVar()
        self.names = tk.StringVar()
        self.ext = tk.StringVar()
        self.output = tk.StringVar()
        self.recursive = tk.BooleanVar(value=True)
        self.wildcard = tk.BooleanVar(value=True)
        self.case = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value='Add folders and choose filters, then Search.')
        self.buttons = []
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='File Finder and Cleanup', font=('', 18, 'bold')).pack(anchor='w')
        roots = ttk.LabelFrame(outer, text='Search folders', padding=6)
        roots.pack(fill='x', pady=6)
        self.roots = tk.Listbox(roots, height=4, selectmode='extended', exportselection=False)
        self.roots.pack(fill='x')
        bar = ttk.Frame(roots); bar.pack(fill='x', pady=4)
        ttk.Entry(bar, textvariable=self.path).pack(side='left', fill='x', expand=True)
        self.button(bar, 'Add path', lambda: self.add(self.path.get()))
        self.button(bar, 'Browse / Add', lambda: self.add(filedialog.askdirectory()))
        self.button(bar, 'Remove', self.remove_roots)
        self.button(bar, 'Open Samba', self.open_samba)
        self.button(bar, 'Mounted shares', self.mounted)
        filters = ttk.Frame(outer); filters.pack(fill='x')
        ttk.Label(filters, text='Filename patterns:').grid(row=0, column=0, sticky='w')
        ttk.Entry(filters, textvariable=self.names).grid(row=0, column=1, sticky='ew', padx=6)
        ttk.Label(filters, text='Extensions:').grid(row=0, column=2)
        ttk.Entry(filters, textvariable=self.ext, width=25).grid(row=0, column=3)
        filters.columnconfigure(1, weight=1)
        opts = ttk.Frame(outer); opts.pack(fill='x', pady=6)
        for label, var in [('Include subfolders', self.recursive), ('Wildcards', self.wildcard), ('Case sensitive', self.case)]:
            ttk.Checkbutton(opts, text=label, variable=var).pack(side='left', padx=4)
        self.button(opts, 'Search', self.search)
        ttk.Button(opts, text='Stop', command=self.stop.set).pack(side='left', padx=3)
        ttk.Button(opts, text='Help', command=self.help).pack(side='right')
        frame = ttk.Frame(outer); frame.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(frame, columns=('name','size','path'), show='headings', selectmode='extended')
        for col, label, width in [('name','Filename',220),('size','Bytes',100),('path','Full path',650)]:
            self.tree.heading(col, text=label); self.tree.column(col, width=width)
        scroll = ttk.Scrollbar(frame, orient='vertical', command=self.tree.yview)
        horizontal = ttk.Scrollbar(frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0,column=0,sticky='nsew'); scroll.grid(row=0,column=1,sticky='ns')
        horizontal.grid(row=1,column=0,sticky='ew'); frame.rowconfigure(0,weight=1); frame.columnconfigure(0,weight=1)
        bar = ttk.Frame(outer); bar.pack(fill='x', pady=5)
        self.button(bar, 'Select all', lambda: self.tree.selection_set(self.tree.get_children()))
        self.button(bar, 'Clear selection', lambda: self.tree.selection_remove(self.tree.selection()))
        self.button(bar, 'Export CSV', self.export)
        out = ttk.Frame(outer); out.pack(fill='x')
        ttk.Label(out,text='Output folder:').pack(side='left')
        ttk.Entry(out,textvariable=self.output).pack(side='left',fill='x',expand=True,padx=6)
        self.button(out,'Browse',lambda: self.output.set(filedialog.askdirectory() or self.output.get()))
        bar = ttk.Frame(outer); bar.pack(fill='x',pady=6)
        for action in ('Copy','Move','Delete permanently'):
            self.button(bar, action + ' selected', lambda a=action: self.act(a))
        ttk.Label(outer,textvariable=self.status).pack(anchor='w')
        self.log = tk.Text(outer,height=6,wrap='word',state='disabled')
        self.log.pack(fill='x',pady=5)
        self.load()
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.after(100,self.poll)

    def button(self, parent, text, command):
        b=ttk.Button(parent,text=text,command=command); b.pack(side='left',padx=3)
        self.buttons.append(b)

    def add(self, path):
        if path and path not in self.roots.get(0,'end'): self.roots.insert('end',path)

    def open_samba(self):
        raw=self.path.get().strip()
        if not raw.lower().startswith('smb://'):
            messagebox.showinfo('Samba', 'Enter smb://server/share in the path field, then click Open Samba.'); return
        try:
            url=urlsplit(raw)
            if not url.hostname or url.username or url.password:
                raise ValueError('Use smb://server/share without embedded credentials.')
            if os.name=='nt':
                os.startfile('\\\\'+url.hostname+unquote(url.path).replace('/','\\'))
            else:
                subprocess.Popen(['xdg-open',raw],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        except (OSError,ValueError) as e: messagebox.showerror('Samba',str(e))

    def mounted(self):
        if os.name=='nt':
            messagebox.showinfo('Shares','Use Browse / Add to select a mapped drive, or enter a UNC path.'); return
        base=Path('/run/user') / str(os.getuid()) / 'gvfs'
        try:
            shares=[p for p in base.iterdir() if p.is_dir() and p.name.startswith('smb-share:')]
        except OSError: shares=[]
        if not shares:
            messagebox.showinfo('Shares','No GVfs Samba shares found. Open Samba first, or use Browse / Add for a manually mounted share.'); return
        win=tk.Toplevel(self); win.title('Choose a mounted share')
        box=tk.Listbox(win,width=90,height=10); box.pack(fill='both',expand=True)
        for p in shares: box.insert('end',str(p))
        def choose():
            for i in box.curselection(): self.add(str(shares[i]))
            win.destroy()
        ttk.Button(win,text='Add selected share',command=choose).pack(pady=8)

    def remove_roots(self):
        for i in reversed(self.roots.curselection()): self.roots.delete(i)

    def load(self):
        try:
            data=json.loads(CONFIG.read_text())
            for p in data.get('roots',[]): self.add(p)
            for key in ('names','ext','output','recursive','wildcard','case'):
                if key in data: getattr(self,key).set(data[key])
        except (OSError, ValueError, TypeError): pass

    def save(self):
        try:
            data={k:getattr(self,k).get() for k in ('names','ext','output','recursive','wildcard','case')}
            data['roots']=list(self.roots.get(0,'end'))
            tmp=CONFIG.with_suffix('.tmp'); tmp.write_text(json.dumps(data,indent=2)); tmp.replace(CONFIG)
        except OSError as e: self.write('Settings could not be saved: '+str(e))

    def write(self,text):
        self.log.configure(state='normal'); self.log.insert('end',text+'\n'); self.log.see('end'); self.log.configure(state='disabled')

    def start(self,worker):
        self.busy=True; self.stop.clear(); self.save()
        for b in self.buttons: b.configure(state='disabled')
        threading.Thread(target=worker,daemon=True).start()

    def search(self):
        roots=[]
        try:
            for raw in self.roots.get(0,'end'):
                p=network_path(raw)
                if not p.is_dir(): raise ValueError('Folder not accessible: '+str(p))
                if p not in roots: roots.append(p)
            if not roots: raise ValueError('Add at least one search folder.')
        except (OSError,ValueError) as e: messagebox.showerror('Search',str(e)); return
        self.search_roots=roots
        self.tree.delete(*self.tree.get_children()); self.rows.clear()
        names,ext=patterns(self.names.get()),patterns(self.ext.get())
        wild,case,recurse=self.wildcard.get(),self.case.get(),self.recursive.get()
        def work():
            seen=set(); count=0
            try:
                for index,root in enumerate(roots):
                    for folder,dirs,files in os.walk(root,followlinks=False,onerror=lambda e:self.q.put(('log',str(e)))):
                        dirs[:]=[d for d in dirs if not Path(folder,d).is_symlink()]
                        if self.stop.is_set(): break
                        for name in files:
                            if self.stop.is_set(): break
                            p=Path(folder,name)
                            if p in seen or not matches(name,names,ext,wild,case): continue
                            try:
                                if p.is_symlink() or not p.is_file(): continue
                                sig=signature(p); seen.add(p)
                                self.q.put(('row',(p,root,index,sig))); count+=1
                            except OSError as e: self.q.put(('log',str(e)))
                        if not recurse: break
                    if self.stop.is_set(): break
            finally: self.q.put(('done',f'{count} matches. '+('Stopped.' if self.stop.is_set() else 'Search complete.')))
        self.status.set('Searching…'); self.start(work)

    def act(self,action):
        selected=[(i,self.rows[i]) for i in self.tree.selection()]
        if not selected: messagebox.showinfo('Select files','Select results first.'); return
        dest=None
        if action!='Delete permanently':
            try:
                if not self.output.get().strip(): raise ValueError('Choose an output folder.')
                dest=network_path(self.output.get())
                for root in self.search_roots:
                    if dest==root or root in dest.parents: raise ValueError('Output must be outside all search folders.')
                if dest.exists() and not dest.is_dir(): raise ValueError('Output is not a folder.')
            except (ValueError,OSError) as e: messagebox.showerror('Output folder',str(e)); return
        text=f'{action}: {len(selected)} selected files?'
        if dest: text+='\nOutput: '+str(dest)+'\nExisting destination files will be skipped.'
        else: text+='\nThis bypasses Trash / Recycle Bin and cannot be undone.'
        if not messagebox.askyesno('Confirm file operation',text,default='no'): return
        roots=self.search_roots[:]
        def work():
            ok=0; failed=0
            try:
                for iid,(p,root,index,sig) in selected:
                    if self.stop.is_set(): break
                    try:
                        if p.is_symlink() or signature(p)!=sig: raise ValueError('File changed since search')
                        if action=='Delete permanently': p.unlink()
                        else:
                            label=root.name or 'drive'
                            if sum((r.name or 'drive')==label for r in roots)>1: label+=f'_{index+1}'
                            target=dest/label/p.relative_to(root)
                            transfer(p,target,move=action=='Move')
                        ok+=1
                        self.q.put(('log',f'{action}: {p}'))
                        if action!='Copy': self.q.put(('remove',iid))
                    except Exception as e:
                        failed+=1; self.q.put(('log',f'SKIPPED / ERROR: {p}: {e}'))
            finally: self.q.put(('done',f'{action}: {ok} completed, {failed} skipped/errors. '+('Stopped.' if self.stop.is_set() else '')))
        self.status.set('Working…'); self.start(work)

    def poll(self):
        for _ in range(300):
            try: kind,data=self.q.get_nowait()
            except queue.Empty: break
            if kind=='row':
                p,root,index,sig=data
                iid=self.tree.insert('','end',values=(p.name,sig[2],str(p))); self.rows[iid]=data
                self.status.set(f'{len(self.rows)} matches found…')
            elif kind=='remove': self.tree.delete(data); self.rows.pop(data,None)
            elif kind=='log': self.write(data)
            elif kind=='done':
                self.busy=False; self.status.set(data); self.write(data)
                for b in self.buttons: b.configure(state='normal')
        self.after(100,self.poll)

    def export(self):
        path=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')])
        if not path:return
        try:
            with open(path,'w',newline='',encoding='utf-8-sig') as f:
                w=csv.writer(f); w.writerow(['Filename','Bytes','Full path'])
                for row in self.rows.values(): w.writerow([row[0].name,row[3][2],str(row[0])])
        except OSError as e: messagebox.showerror('Export',str(e))

    def help(self):
        win=tk.Toplevel(self); win.title('Help'); win.geometry('780x650')
        text=tk.Text(win,wrap='word',padx=15,pady=15); text.pack(fill='both',expand=True)
        text.insert('1.0',HELP); text.configure(state='disabled')

    def close(self):
        if self.busy:
            self.stop.set(); messagebox.showinfo('Stopping','Stopping after the current file. Close again when finished.'); return
        self.save(); self.destroy()


if __name__=='__main__':
    App().mainloop()
