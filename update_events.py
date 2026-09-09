import os
import re

directories = ["backend"]
replacements = 0

severity_rules = [
    (re.compile(r'(type="[^"]*DROP[^"]*"\s*,)'), r'\1\n                severity="HIGH",'),
    (re.compile(r'(type="[^"]*UNREACHABLE[^"]*"\s*,)'), r'\1\n                severity="HIGH",'),
    (re.compile(r'(type="[^"]*FAIL[^"]*"\s*,)'), r'\1\n                severity="HIGH",'),
    (re.compile(r'(type="[^"]*EXCEEDED[^"]*"\s*,)'), r'\1\n                severity="WARNING",'),
    (re.compile(r'(type="[^"]*ERROR[^"]*"\s*,)'), r'\1\n                severity="HIGH",'),
    (re.compile(r'(type="ARP_[^"]*"\s*,)'), r'\1\n                severity="INFO",'),
    (re.compile(r'(type="ICMP_[^"]*"\s*,)'), r'\1\n                severity="INFO",'), # Default ICMP info, Drops handled above
    (re.compile(r'(type="UDP_[^"]*"\s*,)'), r'\1\n                severity="INFO",'), 
    (re.compile(r'(type="TCP_[^"]*"\s*,)'), r'\1\n                severity="INFO",'),
    (re.compile(r'(type="FRAME_[^"]*"\s*,)'), r'\1\n                severity="INFO",'),
    (re.compile(r'(type="SERVICE_[^"]*"\s*,)'), r'\1\n                severity="INFO",'),
]

for root, _, files in os.walk(directories[0]):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r") as f:
                content = f.read()
                
            original = content
            
            # Find all Event( calls
            parts = content.split("Event(")
            if len(parts) > 1:
                new_content = parts[0]
                for i in range(1, len(parts)):
                    part = parts[i]
                    if 'severity=' not in part:
                        # Find the first type="..."
                        match = re.search(r'(type="([^"]+)"\s*,)', part)
                        if match:
                            event_type_line = match.group(1)
                            event_type_name = match.group(2)
                            
                            # Determine severity
                            added = False
                            for rule, repl in severity_rules:
                                if rule.search(part):
                                    part = rule.sub(repl, part, count=1)
                                    added = True
                                    replacements += 1
                                    break
                            
                            if not added:
                                # Default info
                                part = part.replace(event_type_line, event_type_line + '\n                severity="INFO",', 1)
                                replacements += 1
                                
                    new_content += "Event(" + part
                
                if new_content != original:
                    with open(path, "w") as f:
                        f.write(new_content)

print(f"Updated {replacements} events.")
