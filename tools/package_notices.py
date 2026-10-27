"""Copy installed license material for Python modules actually frozen in the EXE."""
import ast,hashlib,json,re,shutil,sys
from importlib.metadata import distribution,packages_distributions
from pathlib import Path


def collect(root,work,artifact):
    toc_path=next((work/'analysis').rglob('PYZ-00.toc'))
    if toc_path.stat().st_size>10*1024*1024:raise ValueError('Unexpected frozen-module inventory size')
    toc=ast.literal_eval(toc_path.read_text(encoding='utf-8'))
    modules={row[0].split('.')[0] for row in toc[1]};mapping=packages_distributions()
    names={name for module in modules for name in mapping.get(module,[])}|{'pyinstaller'}
    destination=artifact/'LICENSES';destination.mkdir(exist_ok=True);inventory=[]
    for name in sorted(names):
        package=distribution(name);label=re.sub(r'[^a-zA-Z0-9_.-]','_',name+'-'+package.version)[:128];copied=[]
        for relative in package.files or []:
            parts=Path(str(relative)).parts;leaf=parts[-1].lower()
            if not ('.dist-info' in str(relative) and 'licenses' in parts or leaf.startswith(('license','copying','copyright','notice'))):continue
            source=Path(package.locate_file(relative))
            if not source.is_file() or source.stat().st_size>2*1024*1024:continue
            data=source.read_bytes()
            try:data.decode('utf-8')
            except UnicodeError:continue
            target=destination/label/(hashlib.sha256(str(relative).encode()).hexdigest()[:8]+'-'+source.name)
            target.parent.mkdir(exist_ok=True);target.write_bytes(data)
            copied.append({'installed_path':str(relative),'artifact_path':target.relative_to(artifact).as_posix(),'sha256':hashlib.sha256(data).hexdigest()})
        inventory.append({'distribution':name,'version':package.version,'license_files':copied})
    python_license=Path(sys.base_prefix)/'LICENSE.txt'
    if python_license.is_file():shutil.copy2(python_license,destination/'CPython-LICENSE.txt')
    shutil.copytree(root/'packaging'/'licenses',destination/'GNU')
    shutil.copy2(root/'packaging'/'third-party-sources.json',artifact/'third-party-sources.json')
    (artifact/'third-party-python-inventory.json').write_text(json.dumps(inventory,indent=2)+'\n',encoding='utf-8')
