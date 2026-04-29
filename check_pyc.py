import struct
import marshal

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

def extract_function_names(code_obj, depth=0):
    if depth > 30:
        return []
    names = []
    for const in code_obj.co_consts:
        if hasattr(const, 'co_name') and const.co_name.startswith('get_test_case_') or \
           (hasattr(const, 'co_name') and const.co_name.startswith('update_')) or \
           (hasattr(const, 'co_name') and const.co_name.startswith('batch_')) or \
           (hasattr(const, 'co_name') and const.co_name.startswith('ai_')) or \
           (hasattr(const, 'co_name') and const.co_name.startswith('restore_')) or \
           (hasattr(const, 'co_name') and const.co_name.startswith('submit_')) or \
           (hasattr(const, 'co_name') and const.co_name.startswith('start_')) or \
           (hasattr(const, 'co_name') and const.co_name.startswith('get_')) or \
           (hasattr(const, 'co_name') and const.co_name.startswith('parse_')):
            names.append(const.co_name)

        if hasattr(const, 'co_code'):
            names.extend(extract_function_names(const, depth + 1))
    return names

funcs = extract_function_names(code)
funcs = sorted(set(funcs))
print("Functions found in pyc:")
for f in funcs:
    print(f"  {f}")
