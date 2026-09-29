
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

class Folder:

    def __init__(self, name: str = "folder", parent:Folder = None):

        self.name = name
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
        if h:
            self.hidden.add(item)
        else:
            self.visible.add(item)

        self._upd_content()

    def get_item(self, name):
        for item in self.all:
            if isinstance(item, File):
                prefix = "." if getattr(item, "hidden", False) and not item.name.startswith(".") else ""
                iname = prefix + item.name + (f".{item.ext}" if item.ext else "")
                if iname == name: return item
            elif getattr(item, "name", "") == name:
                return item
        return None

    def disp(self, h=False):
        if h:
            for item in self.all:
                ext = f'.{item.ext}' if isinstance(item, File) else ""
                fol_slash = "/" if isinstance(item, Folder) else ""
                
                if item is self:
                    name_to_print = "."
                    hid = ""
                elif item is self.parent:
                    name_to_print = ".."
                    hid = ""
                else:
                    name_to_print = item.name
                    hid = '.' if item.hidden else ""
                    
                print(f"{item.perms}\t{item.owner}\t{item.group}\t {hid+name_to_print+ext+fol_slash}")
        else:
            for item in self.visible:
                ext = f'.{item.ext}' if isinstance(item, File) else ""
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
                    lines.append(f"{prefix}{branch}{item.name}{f'.{item.ext}' if isinstance(item, File) else ""}")
    
        build_tree(self)
    
        return "\n" + "\n".join(lines)


class Drive(Folder):
    def __init__(self, name: str = "C:"):
        super().__init__(name, parent=None)
        self.path = f"/{name}"
        self.is_drive = True



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

        fol = self.get_item(folder)
        #print(isinstance(fol, Folder), fol is not None)
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
                    prefix = "." if item.hidden and not item.name.startswith(".") else ""
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