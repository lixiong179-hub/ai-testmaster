import struct
import marshal
import types

PYC_FILE = 'app/api/v1/endpoints/__pycache__/test_case.cpython-311.pyc'

with open(PYC_FILE, 'rb') as f:
    magic = f.read(4)
    flags = struct.unpack('<I', f.read(4))[0]
    if flags & 0x1:
        source_hash = f.read(8)
    else:
        timestamp = struct.unpack('<I', f.read(4))[0]
        size = struct.unpack('<I', f.read(4))[0]
    code = marshal.load(f)

print(f"Code filename: {code.co_filename}")
print(f"First lineno: {code.co_firstlineno}")
print(f"Nlocals: {code.co_nlocals}")
print(f"Constants count: {len(code.co_consts)}")

all_names = set()
def traverse(c, depth=0):
    if depth > 50:
        return
    if hasattr(c, 'co_name'):
        all_names.add(c.co_name)
    if hasattr(c, 'co_consts'):
        for const in c.co_consts:
            if hasattr(const, 'co_code'):
                traverse(const, depth + 1)
    if hasattr(c, 'co_names'):
        for name in c.co_names:
            all_names.add(name)

traverse(code)

# Filter relevant names
interesting = [n for n in all_names if any(kw in n.lower() for kw in
    ['locator', 'coverage', 'view', 'export', 'statistics', 'config', 'step'])]
print("\nInteresting names related to missing endpoints:")
for n in sorted(interesting):
    print(f"  {n}")
