"""Recover a retired real document without changing its measured bytes."""
import hashlib,subprocess

COMMIT='f074a8aac9c23a24d04751b2d0c0d501414a3aad'


def document(root,item):
    path=root/item['path'];expected=item['sha256']
    if path.is_file():
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()==expected:return path,data
    data=subprocess.check_output(['git','show',COMMIT+':'+item['path'].replace('\\','/')],cwd=root)
    # The original measurements hashed the Windows checkout, not Git's LF blob.
    for candidate in [data,data.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')]:
        if hashlib.sha256(candidate).hexdigest()==expected:return path,candidate
    raise ValueError('Frozen real corpus hash mismatch: '+item['path'])
