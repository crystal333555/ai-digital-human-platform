import os
import re

musetalk_dir = r"C:\MuseTalk"
fixed_files = []

for root, dirs, files in os.walk(musetalk_dir):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        if f.endswith('.py'):
            filepath = os.path.join(root, f)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()
                if 'torch.load(' in content and 'weights_only' not in content:
                    new_content = re.sub(
                        r'torch\.load\(([^)]+)\)',
                        r'torch.load(\1, weights_only=False)',
                        content
                    )
                    if new_content != content:
                        with open(filepath, 'w', encoding='utf-8') as fh:
                            fh.write(new_content)
                        fixed_files.append(filepath)
                        print(f"Fixed: {filepath}")
            except Exception as e:
                print(f"Error: {filepath}: {e}")

print(f"\nTotal fixed: {len(fixed_files)} files")
