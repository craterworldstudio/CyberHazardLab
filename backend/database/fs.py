
import random
import json

FILE_CONTENTS = ""

class File:

    def __init__(self, name: str = "file", ext: str = ""):

        self.name = name
        self.ext = ext
        self.hidden = self.name.startswith(".")
        self.path = "/"

        self.owner = "root"
        self.group = "root"
        self.perms = "rw-rwxr--"

        self.contents = []

    def set_path(self, path):
        self.path = path

    def set_owner(self, name):
        self.owner = name

    def set_group(self, group):
        self.group = group

    def set_perms(self, perms):
        self.perms = perms

class Folder:

    def __init__(self, name: str = "folder", parent:Folder = None):

        self.name = name
        self.is_hidden = name.startswith(".")
        self.visible = set()
        self.hidden = set()
        self.path = "/"
        self.parent = parent

        self.owner = "root"
        self.group = "root"
        self.perms = "rw-rwxr--"

        self.all = set()

        curr = self
        self.add(self, h=True)

        if self.parent != None: self.add(self.parent, h=True)

        self._upd_content()

    def _upd_content(self):
        self.all.update(self.hidden)
        self.all.update(self.visible)

    def add(self, item, h=False):
        item_hidden = h or getattr(item, "is_hidden", False) or (isinstance(getattr(item, "hidden", False), bool) and item.hidden) or getattr(item, "name", "").startswith(".")
        if item_hidden:
            self.hidden.add(item)
        else:
            self.visible.add(item)

        self._upd_content()

    def get_item(self, name):
        for item in self.all:
            if isinstance(item, File):
                is_hid = getattr(item, "is_hidden", False) or (isinstance(getattr(item, "hidden", False), bool) and item.hidden)
                prefix = "." if is_hid and not item.name.startswith(".") else ""
                iname = prefix + item.name + (f".{item.ext}" if item.ext else "")
                if iname == name: return item
            elif getattr(item, "name", "") == name:
                return item
        return None

    def disp(self, h=False):
        if h:
            for item in self.all:
                ext = f'.{item.ext}' if (isinstance(item, File) and item.ext) else ""
                fol_slash = "/" if isinstance(item, Folder) else ""
                
                if item is self:
                    name_to_print = "."
                    hid = ""
                elif item is self.parent:
                    name_to_print = ".."
                    hid = ""
                else:
                    name_to_print = item.name
                    is_hid = getattr(item, "is_hidden", False) or (isinstance(getattr(item, "hidden", False), bool) and item.hidden)
                    hid = '.' if is_hid and not item.name.startswith(".") else ""
                    
                print(f"{item.perms}\t{item.owner}\t{item.group}\t {hid+name_to_print+ext+fol_slash}")
        else:
            for item in self.visible:
                ext = f'.{item.ext}' if (isinstance(item, File) and item.ext) else ""
                fol_slash = "/" if isinstance(item, Folder) else ""
                
                if item is self:
                    name_to_print = "."
                elif item is self.parent:
                    name_to_print = ".."
                else:
                    name_to_print = item.name
                    
                print(f"{item.perms}\t{item.owner}\t{item.group}\t {name_to_print+ext+fol_slash}")

    def set_owner(self, name):
        self.owner = name

    def set_group(self, group):
        self.group = group

    def set_perms(self, perms):
        self.perms = perms

    def remove(self, item):
        if item in self.visible:
            self.visible.remove(item)
        if item in self.hidden:
            self.hidden.remove(item)
        if item in self.all:
            self.all.remove(item)
        self._upd_content()

    def __repr__(self):
        lines = [f"{self.name}/"]
    
        def build_tree(folder, prefix=""):
            items = sorted(folder.all, key=lambda x: x.name)
    
            for i, item in enumerate(items):
                last = i == len(items) - 1
                branch = "└── " if last else "├── "

                if item.hidden: continue
                if isinstance(item, Folder):
                    lines.append(f"{prefix}{branch}{item.name}/")
                    build_tree(
                        item,
                        prefix + ("    " if last else "│   ")
                    )
                else:
                    lines.append(f"{prefix}{branch}{item.name}{f'.{item.ext}' if (isinstance(item, File) and item.ext) else ''}")
    
        build_tree(self)
    
        return "\n" + "\n".join(lines)


class Drive(Folder):
    def __init__(self, name: str = "C:", hidden: bool = False, owner: str = "root", group: str = "root", perms: str = "rwxr-xr-x"):
        super().__init__(name, parent=None)
        if name in ("C:", "C", "/"):
            self.path = "/"
        else:
            self.path = f"/mnt/{name}" if not name.startswith("/") else name
        self.is_drive = True
        self.is_hidden = hidden or name.startswith(".")
        self.owner = owner
        self.group = group
        self.perms = "rwx------" if self.is_hidden else perms



class FileSystem:

    def __init__(self, load_json="basefs.json"):
        import os
        self.tree = Drive("C:")
        self.curr_fol = self.tree
        self.ques_sets = []
        
        # We can dynamically generate a base FS if basefs.json is missing or path is passed
        try:
            # Check backend/database/basefs.json or basefs.json
            path = load_json if os.path.exists(load_json) else "backend/database/basefs.json"
            if not os.path.exists(path):
                # Fallback AST if no file exists
                self.fs_json = {
                    "root": {
                        "bin": {"ls": [], "cat": [], "mkdir": [], "touch": [], "rm": []},
                        "home": {"guest": {"Desktop": {}}},
                        "etc": {"config": {}}
                    }
                }
            else:
                with open(path, 'r') as f:
                    self.fs_json = json.load(f)
        except Exception:
            self.fs_json = {"root": {}}


    def generate_fs(self):

        def crawl(fol_obj, tree):
            for key, item in tree.items():
                #print(item)
                if ('.' in key and key[0] != '.'):
                    name, ext = key.rsplit('.', 1)

                    if isinstance(item, dict):
                        fol = Folder(key)
                        fol.parent = fol_obj
                        fol.path = fol_obj.path + key if fol_obj.path == "/" else fol_obj.path + "/" + key
                        fol_obj.add(fol)

                        self.curr_fol = fol
                        crawl(fol, item)

                    else:
                        f = File(name, ext)
                        f.set_path(fol_obj.path)
                        cont = FILE_CONTENTS.get(key, "")
                        #print(cont, key)
                        f.contents = cont[random.randrange(0, 3)]
                        fol_obj.add(f)
    
                elif ('.' in key and key[0] == '.'):
                    key_name = key[1:]
            
                    if ('.' in key_name):
                        name, ext = key_name.rsplit('.', 1)

                        if isinstance(item, dict):
                            fol = Folder(key)
                            fol.parent = fol_obj
                            fol.path = fol_obj.path + key if fol_obj.path == "/" else fol_obj.path + "/" + key
                            fol_obj.add(fol)

                            self.curr_fol = fol
                            self.crawl(fol, item)

                        else:
                            f = File(name, ext)
                            f.set_path(fol_obj.path)
                            f.contents = FILE_CONTENTS.get(key, "")[random.randrange(0,3)]
                            fol_obj.add(f, True)
                    else:
                        if isinstance(item, list):
                            f = File(key)
                            f.set_path(fol_obj.path)
                            f.contents = FILE_CONTENTS.get(key, "")[random.randrange(0,3)]
                            fol_obj.add(f, True)
                            return
                        
                        fol = Folder(key)
                        fol.parent = fol_obj
                        fol.path = fol_obj.path + key if fol_obj.path == "/" else fol_obj.path + "/" + key
                        fol_obj.add(fol, True)
                        #self.curr_path += f"/{key}"
                        

                        self.curr_fol = fol
                        #print(key, item)
                        crawl(fol, item)
    
                elif ('.' not in key):

                
                    if isinstance(item, list):
                        
                        f = File(name=key)
                        f.set_path(fol_obj.path)
                        cont = FILE_CONTENTS.get(key, "")
                        #print(cont, key)
                        f.contents = cont[random.randint(0,2)]
                        fol_obj.add(f, True)

                    else:
                        fol = Folder(key)
                        #self.curr_path += f"/{key}"
                        fol.path = fol_obj.path + key if fol_obj.path == "/" else fol_obj.path + "/" + key
                        fol.parent = fol_obj
                        fol_obj.add(fol)

                        self.curr_fol = fol
                        crawl(fol, item)

            
                


        root_part = self.fs_json["root"]
        crawl(self.tree, root_part)

        self.curr_fol = self.tree
                    
    def pwd(self):
        return self.curr_fol.path

    def get_item(self, name):

        for item in self.curr_fol.all:
            if isinstance(item, File):
                prefix = "." if item.hidden and not item.name.startswith(".") else ""
                iname = prefix + item.name + (f".{item.ext}" if item.ext else "")
                #print(name, iname, item.ext)
                if iname == name: return item
            else:
                if item.name == name:
                    return item

        return None

    def jmp_into(self, folder):
        if folder == "/" or folder == "~":
            self.curr_fol = self.tree
            return

        if folder.startswith("/"):
            fol = self.path_to_tree(folder)
        else:
            fol = self.get_item(folder)
            if fol is None and "/" in folder:
                cur = self.curr_fol
                for seg in folder.split("/"):
                    if not seg or seg == ".":
                        continue
                    elif seg == "..":
                        cur = cur.parent if cur.parent else cur
                    else:
                        sub = None
                        for itm in cur.all:
                            if itm.name == seg:
                                sub = itm
                                break
                        cur = sub
                        if cur is None:
                            break
                fol = cur

        if (fol is not None) and isinstance(fol, Folder):
            self.curr_fol = fol
        else:
            print(f"{folder} is a file or doesn't exist")

    def jmp_out(self):

        if self.curr_fol.parent:
            self.curr_fol = self.curr_fol.parent

    def path_to_tree(self, path):

        parts = [part for part in path.split("/") if part]
        current = self.tree

        for part in parts:
            found = None
            for item in current.all:

                if isinstance(item, File):
                    is_hid = getattr(item, "is_hidden", False) or (isinstance(getattr(item, "hidden", False), bool) and item.hidden)
                    prefix = "." if is_hid and not item.name.startswith(".") else ""
                    iname = prefix + item.name + (f".{item.ext}" if item.ext else "")

                    if iname == part:
                        found = item
                        break
                else:
                    if item.name == part:
                        found = item
                        break
            if found is None:
                return None
            if isinstance(found, File):
                # File is only valid if it is the final component
                if part != parts[-1]:
                    return None
                return found
            current = found
        return current

    def to_dict(self):
        return serialize_vfs(self)

    def from_dict(self, data):
        return deserialize_vfs(self, data)


def serialize_vfs(fs_or_tree):
    if hasattr(fs_or_tree, "tree"):
        root = fs_or_tree.tree
    else:
        root = fs_or_tree

    folders = []
    files = []

    def walk(folder):
        for item in sorted(folder.all, key=lambda x: getattr(x, "name", "")):
            if item is folder or item is folder.parent:
                continue
            if isinstance(item, Folder):
                folders.append({
                    "path": item.path,
                    "owner": getattr(item, "owner", "root"),
                    "group": getattr(item, "group", "root"),
                    "perms": getattr(item, "perms", "rwxr-xr-x")
                })
                walk(item)
            elif isinstance(item, File):
                is_hid = getattr(item, "is_hidden", False) or (isinstance(getattr(item, "hidden", False), bool) and item.hidden)
                prefix = "." if is_hid and not item.name.startswith(".") else ""
                ext = f".{item.ext}" if getattr(item, "ext", "") else ""
                fname = prefix + item.name + ext
                dir_path = folder.path.rstrip("/")
                fpath = f"{dir_path}/{fname}" if dir_path else f"/{fname}"

                content = item.contents
                if isinstance(content, (bytes, bytearray)):
                    import base64
                    try:
                        content = content.decode("utf-8")
                    except Exception:
                        content = f"base64:{base64.b64encode(content).decode('ascii')}"
                elif isinstance(content, list):
                    content = "\n".join(str(c) for c in content)
                elif content is None:
                    content = ""
                else:
                    content = str(content)

                files.append({
                    "path": fpath,
                    "owner": getattr(item, "owner", "root"),
                    "group": getattr(item, "group", "root"),
                    "perms": getattr(item, "perms", "rw-r--r--"),
                    "contents": content
                })

    walk(root)
    return {
        "folders": folders,
        "files": files
    }


def deserialize_vfs(fs_or_tree, data):
    if not data or not isinstance(data, dict):
        return
    if hasattr(fs_or_tree, "tree"):
        root = fs_or_tree.tree
    else:
        root = fs_or_tree

    def ensure_dir(path, owner="root", group="root", perms="rwxr-xr-x"):
        parts = [p for p in path.split("/") if p]
        curr = root
        built_path = ""
        for part in parts:
            built_path += f"/{part}"
            target = None
            for itm in curr.all:
                if isinstance(itm, Folder) and itm is not curr and itm is not curr.parent and itm.name == part:
                    target = itm
                    break
            if not target:
                target = Folder(part, parent=curr)
                target.path = built_path
                target.owner = owner
                target.group = group
                target.perms = perms
                curr.add(target, h=part.startswith("."))
            curr = target
        return curr

    for fld in data.get("folders", []):
        p = fld.get("path")
        if not p or p == "/":
            continue
        folder_obj = ensure_dir(p, fld.get("owner", "root"), fld.get("group", "root"), fld.get("perms", "rwxr-xr-x"))
        if "owner" in fld:
            folder_obj.owner = fld["owner"]
        if "group" in fld:
            folder_obj.group = fld["group"]
        if "perms" in fld:
            folder_obj.perms = fld["perms"]

    for finfo in data.get("files", []):
        fpath = finfo.get("path")
        if not fpath:
            continue
        parts = [p for p in fpath.split("/") if p]
        if not parts:
            continue
        fname = parts[-1]
        dir_parts = parts[:-1]
        dir_path = "/" + "/".join(dir_parts)
        folder_obj = ensure_dir(dir_path) if dir_parts else root

        existing = folder_obj.get_item(fname)
        contents = finfo.get("contents", "")
        if isinstance(contents, str) and contents.startswith("base64:"):
            import base64
            try:
                contents = base64.b64decode(contents[7:])
            except Exception:
                pass

        if existing and isinstance(existing, File):
            existing.contents = contents
            if "owner" in finfo:
                existing.owner = finfo["owner"]
            if "group" in finfo:
                existing.group = finfo["group"]
            if "perms" in finfo:
                existing.perms = finfo["perms"]
        else:
            f_obj = File(fname)
            f_obj.set_path(folder_obj.path)
            f_obj.contents = contents
            f_obj.owner = finfo.get("owner", "root")
            f_obj.group = finfo.get("group", "root")
            f_obj.perms = finfo.get("perms", "rw-r--r--")
            folder_obj.add(f_obj, h=fname.startswith("."))