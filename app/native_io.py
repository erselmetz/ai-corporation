"""Bounded native tool IO primitives. Authorization/approval lives in the service.

No implicit file roots, proxies, redirects to private networks or code execution.
"""
from dataclasses import dataclass
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path,PureWindowsPath
from threading import RLock
from uuid import uuid4
import difflib
import http.client
from html.parser import HTMLParser
import ipaddress
import os
import re
import socket
import ssl
import stat
from urllib.parse import urlsplit,urlunsplit,urljoin,unquote,quote,urlencode

from app.knowledge.native_brain import secret_path,SKIP_DIRS


class NativeIOError(ValueError):pass


def write_clipboard(text,hwnd):
    """Set immediate Unicode data for this app's real native window; no clipboard read."""
    if os.name!='nt' or not hwnd:return False
    import ctypes
    from ctypes import wintypes
    user=ctypes.WinDLL('user32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    user.OpenClipboard.argtypes=[wintypes.HWND];user.OpenClipboard.restype=wintypes.BOOL
    user.EmptyClipboard.argtypes=[];user.EmptyClipboard.restype=wintypes.BOOL
    user.SetClipboardData.argtypes=[wintypes.UINT,wintypes.HANDLE];user.SetClipboardData.restype=wintypes.HANDLE
    user.CloseClipboard.argtypes=[];user.CloseClipboard.restype=wintypes.BOOL
    kernel.GlobalAlloc.argtypes=[wintypes.UINT,ctypes.c_size_t];kernel.GlobalAlloc.restype=wintypes.HGLOBAL
    kernel.GlobalLock.argtypes=[wintypes.HGLOBAL];kernel.GlobalLock.restype=wintypes.LPVOID
    kernel.GlobalUnlock.argtypes=[wintypes.HGLOBAL];kernel.GlobalFree.argtypes=[wintypes.HGLOBAL]
    data=text.encode('utf-16-le')+b'\0\0';memory=kernel.GlobalAlloc(2,len(data))
    if not memory:return False
    opened=False
    try:
        pointer=kernel.GlobalLock(memory)
        if not pointer:return False
        ctypes.memmove(pointer,data,len(data));kernel.GlobalUnlock(memory)
        opened=bool(user.OpenClipboard(hwnd))
        if not opened or not user.EmptyClipboard():return False
        if not user.SetClipboardData(13,memory):return False
        memory=None  # Windows owns the successfully transferred allocation.
        return True
    finally:
        if opened:user.CloseClipboard()
        if memory:kernel.GlobalFree(memory)


def http_url(value):
    if not isinstance(value,str) or not 1<=len(value.encode('utf-8'))<=2048 or '\\' in value:
        raise NativeIOError('Choose an http or https URL up to 2048 bytes.')
    if any(ord(c)<32 or ord(c)==127 for c in unquote(value)):raise NativeIOError('URL contains unsupported control characters.')
    try:
        parts=urlsplit(value)
        if parts.scheme.lower() not in {'http','https'} or not parts.hostname or parts.username is not None or parts.password is not None:
            raise ValueError()
        host=parts.hostname.rstrip('.').encode('idna').decode('ascii').lower()
        if not host or '%' in host or any(c.isspace() for c in host):raise ValueError()
        port=parts.port
        if port is not None and not 1<=port<=65535:raise ValueError()
        authority=('['+host+']' if ':' in host else host)+((':'+str(port)) if port is not None else '')
        return urlunsplit((parts.scheme.lower(),authority,quote(parts.path or '/',safe="/%:@-._~!$&'()*+,;="),
                           quote(parts.query,safe="%=&+/:?@-._~!$'()*;,"),quote(parts.fragment,safe='%/?:@-._~')))
    except (ValueError,UnicodeError):raise NativeIOError('URL destination is invalid. Credentials and non-web schemes are not allowed.') from None


def url_intent(text):
    if not isinstance(text,str):return None
    normalized=' '.join(text.strip().casefold().split()).rstrip('!.?')
    polite=r'(?:(?:can|could|would)\s+you\s+|please\s+|pwede\s+mo\s+bang\s+)?(?:please\s+)?'
    sites={
        'youtube':'https://www.youtube.com/','facebook':'https://www.facebook.com/',
        'tiktok':'https://www.tiktok.com/','instagram':'https://www.instagram.com/',
        'twitter':'https://x.com/','x':'https://x.com/','reddit':'https://www.reddit.com/',
        'github':'https://github.com/','gmail':'https://mail.google.com/','google':'https://www.google.com/',
        'linkedin':'https://www.linkedin.com/','messenger':'https://www.messenger.com/',
        'spotify':'https://open.spotify.com/','netflix':'https://www.netflix.com/',
        'amazon':'https://www.amazon.com/','shopee':'https://shopee.ph/','lazada':'https://www.lazada.com.ph/',
        'discord':'https://discord.com/app','twitch':'https://www.twitch.tv/',
    }
    site_pattern='|'.join(sorted((re.escape(site) for site in sites),key=len,reverse=True))
    known=re.fullmatch(
        polite+r'(?:open|launch|buksan(?:\s+ang)?)\s+'
        r'('+site_pattern+r')(?:\.com)?'
        r'(?:\s+(?:in|using|on)\s+(?:google\s+)?chrome)?',
        normalized,
    )
    if known:return sites[known.group(1)]
    fixed_sites={
        'open facebook':'https://www.facebook.com/', 'open facebook in chrome':'https://www.facebook.com/',
        'open facebook site':'https://www.facebook.com/', 'buksan ang facebook':'https://www.facebook.com/',
        'open tiktok':'https://www.tiktok.com/', 'open tiktok site':'https://www.tiktok.com/',
        'or tiktok site':'https://www.tiktok.com/', 'buksan ang tiktok':'https://www.tiktok.com/',
    }
    if normalized in fixed_sites:return fixed_sites[normalized]
    def media_search(platform,query):
        query=query.strip(' ,.-')
        if not 1<=len(query.encode('utf-8'))<=200:return None
        encoded=urlencode({'q':query})
        destinations={
            'youtube':'https://www.youtube.com/results?'+urlencode({'search_query':query}),
            'spotify':'https://open.spotify.com/search/'+quote(query,safe=''),
            'tiktok':'https://www.tiktok.com/search?'+encoded,
            'soundcloud':'https://soundcloud.com/search?'+encoded,
            'facebook':'https://www.facebook.com/search/top/?'+encoded,
            'instagram':'https://www.instagram.com/explore/search/keyword/?'+encoded,
            'twitter':'https://x.com/search?'+encoded,'x':'https://x.com/search?'+encoded,
            'reddit':'https://www.reddit.com/search/?'+encoded,
            'twitch':'https://www.twitch.tv/search?'+encoded,
        }
        return destinations.get(platform)
    media_platforms=r'youtube|spotify|tiktok|soundcloud|facebook|instagram|twitter|x|reddit|twitch'
    explicit_prefix=re.fullmatch(
        r'(?:i\s+mean\s+)?(?:in|on)\s+('+media_platforms+r')\s+(?:please\s+)?'
        r'(?:play|search(?:\s+for)?|hanapin|patugtog(?:in)?)\s+(.+)',normalized)
    if explicit_prefix:return media_search(explicit_prefix.group(1),explicit_prefix.group(2))
    explicit_suffix=re.fullmatch(
        r"(?:let'?s\s+|can\s+you\s+|please\s+)?(?:play|search(?:\s+for)?|hanapin|patugtog(?:in)?)\s+(.+?)"
        r'\s+(?:in|on)\s+('+media_platforms+r')',normalized)
    if explicit_suffix:return media_search(explicit_suffix.group(2),explicit_suffix.group(1))
    natural_music=re.fullmatch(
        r"(?:let'?s\s+|can\s+you\s+|please\s+)?(?:play|patugtog(?:in)?)\s+(?:some\s+)?"
        r'(.+\b(?:song|songs|music|playlist|mix|album|artist))',normalized)
    if natural_music:return media_search('youtube',natural_music.group(1))
    music=re.fullmatch(r'(?:play|search(?:\s+for)?)\s+(?:some\s+)?(.+?)\s+(?:music|songs?)',normalized)
    if music:
        query=(music.group(1)+' music').strip()
        if 1<=len(query.encode('utf-8'))<=200:return 'https://www.youtube.com/results?'+urlencode({'search_query':query})
    youtube=re.fullmatch(r'(?:open|buksan(?:\s+ang)?)\s+youtube\s+(?:and|at)\s+(?:play|search(?:\s+for)?|hanapin)\s+(.+)',normalized)
    if youtube:
        query=youtube.group(1).strip()
        if 1<=len(query.encode('utf-8'))<=200:
            return 'https://www.youtube.com/results?'+urlencode({'search_query':query})
    match=re.fullmatch(r'(?:open|buksan)\s+([a-z][a-z0-9+.-]*:\S+)',text.strip(),flags=re.IGNORECASE)
    if match:return http_url(match.group(1))
    domain=re.fullmatch(polite+r'(?:open|launch|buksan(?:\s+ang)?)\s+((?:[a-z0-9-]+\.)+[a-z]{2,}(?:/\S*)?)'
                        r'(?:\s+(?:in|using|on)\s+(?:google\s+)?chrome)?',normalized)
    return http_url('https://'+domain.group(1)) if domain else None


def folder_intent(text):
    """Return one explicitly requested Desktop folder name, never a pathname."""
    if not isinstance(text,str):return None
    value=' '.join(text.strip().split()).rstrip('!.?')
    patterns=(
        r'(?:create|make)\s+(?:a\s+)?folder(?:\s+(?:called|named)\s+(.+?))?\s+(?:in|on)\s+(?:the\s+)?de(?:s)?ktop',
        r'(?:create|make)\s+(?:a\s+)?folder\s+(?:in|on)\s+(?:the\s+)?de(?:s)?ktop\s+(?:called|named?|with\s+name)\s+(.+)',
        r'gumawa\s+(?:ng\s+)?folder(?:\s+(?:na\s+)?(?:pangalan(?:g)?|named)\s+(.+?))?\s+sa\s+de(?:s)?ktop',
    )
    for pattern in patterns:
        match=re.fullmatch(pattern,value,flags=re.IGNORECASE)
        if match:
            name=(match.group(1) or 'New folder').strip(' \"\'')
            return name if 1<=len(name.encode('utf-8'))<=160 else None
    return None


def desktop_directory():
    """Resolve the current Windows user's real Desktop known folder."""
    if os.name!='nt':raise NativeIOError('Desktop folder actions are available on Windows only.')
    import ctypes
    buffer=ctypes.create_unicode_buffer(32768)
    if ctypes.windll.shell32.SHGetFolderPathW(None,0x10,None,0,buffer)!=0:
        raise NativeIOError('The current Windows Desktop folder could not be resolved.')
    raw=buffer.value
    if not raw or raw.startswith(('\\\\','//')):raise NativeIOError('Only a local Windows Desktop folder is supported.')
    path=Path(raw).resolve(strict=True)
    if not path.is_dir() or linked(path):raise NativeIOError('The current Windows Desktop folder is unavailable or linked.')
    return path


def public_addresses(url,resolver=socket.getaddrinfo):
    parts=urlsplit(http_url(url));host=parts.hostname;port=parts.port or (443 if parts.scheme=='https' else 80)
    try:records=resolver(host,port,type=socket.SOCK_STREAM)
    except OSError:raise NativeIOError('The public site could not be resolved.') from None
    addresses=[]
    for record in records:
        try:address=ipaddress.ip_address(record[4][0])
        except ValueError:raise NativeIOError('The destination returned an invalid address.') from None
        mapped=getattr(address,'ipv4_mapped',None)
        if not address.is_global or (mapped is not None and not mapped.is_global):
            raise NativeIOError('Local, private and reserved network destinations cannot be retrieved.')
        if str(address) not in addresses:addresses.append(str(address))
    if not addresses or len(addresses)>32:raise NativeIOError('The destination has no bounded public address set.')
    return sorted(addresses,key=lambda address:ipaddress.ip_address(address).version)


class VisibleText(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.skip=0;self.parts=[];self.size=0
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style','noscript','svg','template'}:self.skip+=1
    def handle_endtag(self,tag):
        if tag in {'script','style','noscript','svg','template'}:self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip and self.size<12000:
            text=' '.join(data.split())[:12000-self.size]
            if text:self.parts.append(text);self.size+=len(text)


class PublicWebReader:
    MAX_BYTES=512*1024
    def __init__(self,*,resolver=socket.getaddrinfo,dial=socket.create_connection):self.resolve=resolver;self.dial=dial

    def read(self,url,*,stop=lambda:False):
        from app.resources.context import check_native_stop
        def check():
            check_native_stop()
            if stop():raise NativeIOError('Web retrieval was stopped.')
        current=http_url(url)
        for redirect in range(4):
            check();parts=urlsplit(current);addresses=public_addresses(current,self.resolve)
            port=parts.port or (443 if parts.scheme=='https' else 80)
            # Pin the validated address. HTTP(S)Connection never resolves the
            # hostname again; TLS still verifies the original hostname.
            connection=http.client.HTTPConnection(parts.hostname,port,timeout=10)
            try:
                raw=self.dial((addresses[0],port),timeout=10)
                connection.sock=raw
                if ipaddress.ip_address(raw.getpeername()[0])!=ipaddress.ip_address(addresses[0]):
                    raw.close();raise NativeIOError('The connection did not reach the approved public address.')
                connection.sock=(ssl.create_default_context().wrap_socket(raw,server_hostname=parts.hostname)
                                 if parts.scheme=='https' else raw)
                target=urlunsplit(('','',parts.path,parts.query,''))
                connection.request('GET',target,headers={'Host':parts.netloc,'Accept':'text/html,text/plain',
                    'Accept-Encoding':'identity','User-Agent':'ERSELMETZ-AI/1.0'})
                response=connection.getresponse();check()
                if 300<=response.status<400:
                    location=response.getheader('Location')
                    if not location or redirect==3:raise NativeIOError('Web redirect limit reached or destination missing.')
                    destination=http_url(urljoin(current,location));next_parts=urlsplit(destination)
                    if (next_parts.hostname!=parts.hostname or next_parts.port!=parts.port
                            or (parts.scheme=='https' and next_parts.scheme!='https')):
                        raise NativeIOError('Cross-site or downgraded redirects need a new exact destination approval.')
                    current=destination;continue
                if response.status!=200:raise NativeIOError('The site did not return a successful page.')
                if response.getheader('Content-Encoding','identity').lower() not in {'','identity'}:
                    raise NativeIOError('Compressed responses are outside the supported web size bound.')
                content_type=response.headers.get_content_type()
                if content_type not in {'text/html','text/plain'}:raise NativeIOError('Only public HTML and plain text can be retrieved.')
                declared=response.getheader('Content-Length')
                if declared and (not declared.isdecimal() or int(declared)>self.MAX_BYTES):raise NativeIOError('The page exceeds the 512 KB limit.')
                body=bytearray()
                while len(body)<=self.MAX_BYTES:
                    check();piece=response.read(min(8192,self.MAX_BYTES+1-len(body)))
                    if not piece:break
                    body.extend(piece)
                if len(body)>self.MAX_BYTES:raise NativeIOError('The page exceeds the 512 KB limit.')
                encoding=response.headers.get_content_charset() or 'utf-8'
                if encoding.lower() not in {'utf-8','utf8','ascii','iso-8859-1','windows-1252'}:raise NativeIOError('The page text encoding is unsupported.')
                text=body.decode(encoding,errors='strict')
                if content_type=='text/html':
                    parser=VisibleText();parser.feed(text);text='\n'.join(parser.parts)
                check();return {'source':current,'text':text[:4000],'untrusted':True,'bytes':len(body)}
            except (OSError,http.client.HTTPException,UnicodeError):raise NativeIOError('The public page could not be retrieved safely.') from None
            finally:connection.close()
        raise NativeIOError('Web redirect limit reached.')


def secret_file(path):
    return secret_path(path) or Path(path).name.casefold() in {'credentials','secrets','passwords'} or bool(re.search(r'(?i)(?:^|[_-])(?:api[_-]?keys?|secrets?|passwords?|credentials?)(?:[_.-]|$)',Path(path).name))


def linked(path):return any(p.is_symlink() or p.is_junction() for p in [path,*path.parents])


def final_handle_path(handle):
    """Inspect the opened Windows object, not a second pathname lookup."""
    if os.name!='nt':return None
    import ctypes
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    function=kernel.GetFinalPathNameByHandleW
    function.argtypes=[wintypes.HANDLE,wintypes.LPWSTR,wintypes.DWORD,wintypes.DWORD];function.restype=wintypes.DWORD
    buffer=ctypes.create_unicode_buffer(32768);length=function(handle,buffer,len(buffer),0)
    if not length or length>=len(buffer):raise NativeIOError('The opened file destination could not be verified.')
    value=buffer.value
    if value.startswith('\\\\?\\UNC\\'):raise NativeIOError('Network file destinations are blocked.')
    if value.startswith('\\\\?\\'):value=value[4:]
    return Path(value)


@contextmanager
def pin_directories(root,parent):
    """Prevent Windows directory rename/reparse changes during a file operation."""
    if os.name!='nt':
        yield;return
    import ctypes
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    create=kernel.CreateFileW;create.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE];create.restype=wintypes.HANDLE
    close=kernel.CloseHandle;close.argtypes=[wintypes.HANDLE];close.restype=wintypes.BOOL
    handles=[]
    try:
        folders=[];current=parent
        while True:
            folders.append(current)
            if current==root:break
            if not current.is_relative_to(root):raise NativeIOError('The file folder is outside its permission scope.')
            current=current.parent
        for folder in reversed(folders):
            # Allow ordinary child IO, but deny directory delete/rename handles.
            # Never follow a reparse point.
            handle=create(str(folder),0x80000000,3,None,3,0x02000000|0x00200000,None)
            if handle==wintypes.HANDLE(-1).value:raise NativeIOError('The folder is changing or busy; try again after it is stable.')
            handles.append(handle);actual=final_handle_path(handle)
            if actual!=folder or linked(folder):raise NativeIOError('The folder changed or became a link.')
        yield
    finally:
        for handle in reversed(handles):close(handle)


@dataclass(frozen=True)
class FileRoot:
    id:str
    owner:str
    window:str
    path:Path
    identity:tuple
    workspace_id:str=''


class NativeFiles:
    MAX_TEXT=8192
    def __init__(self):self.lock=RLock();self.roots={}

    def register(self,owner,window,path,*,consent,workspace_id=''):
        if consent is not True:raise NativeIOError('Explicit folder permission is required.')
        raw=str(path)
        if raw.startswith(('\\\\','//','\\??\\')):raise NativeIOError('Choose a local folder; network and device paths are not supported.')
        chosen=Path(path)
        if not chosen.is_absolute():raise NativeIOError('Choose an explicit absolute local folder.')
        if linked(chosen):raise NativeIOError('Links and junctions cannot be file-tool roots.')
        chosen=chosen.resolve(strict=True)
        if not chosen.is_dir():raise NativeIOError('Choose a local folder.')
        with self.lock:
            if len(self.roots)>=128 or sum(r.owner==owner and r.window==window for r in self.roots.values())>=8:
                raise NativeIOError('The folder permission limit has been reached.')
            stat=chosen.stat();root=FileRoot(uuid4().hex,owner,window,chosen,(stat.st_dev,stat.st_ino),workspace_id)
            self.roots[root.id]=root
        return {'id':root.id,'name':chosen.name or chosen.anchor,'path':str(chosen)}

    def revoke_window(self,owner,window):
        with self.lock:
            for key in [key for key,r in self.roots.items() if r.owner==owner and r.window==window]:self.roots.pop(key)

    def resolve(self,owner,window,identifier,relative,*,allow_root=False):
        with self.lock:root=self.roots.get(identifier)
        if root is None or (root.owner,root.window)!=(owner,window):raise NativeIOError('Choose a permitted folder for this window first.')
        if root.workspace_id:
            from app.application.services.chat_workspaces import current_workspace
            workspace=current_workspace.get()
            if workspace is None or (workspace.owner,workspace.id)!=(owner,root.workspace_id):
                raise NativeIOError('This folder permission belongs to another conversation workspace.')
        if not isinstance(relative,str) or len(relative)>512:raise NativeIOError('Use a bounded relative file path.')
        name=PureWindowsPath(relative)
        if (name.drive or name.is_absolute()
                or '\\' in relative or ':' in relative or any(p in {'..','.'} for p in relative.split('/'))):
            raise NativeIOError('Use a relative path inside the chosen folder.')
        if not relative and not allow_root:raise NativeIOError('Choose one file inside the permitted folder.')
        for part in name.parts:
            base=part.split('.')[0].casefold()
            if (part.endswith((' ','.')) or base in {'con','prn','aux','nul','clock$'} or re.fullmatch(r'(?:com|lpt)[0-9¹²³]+',base)
                    or part.casefold() in SKIP_DIRS or part.casefold() in {'.ssh','.aws','.azure'} or secret_file(part)):
                raise NativeIOError('Secret, reserved and junk paths are blocked.')
        target=root.path.joinpath(*name.parts)
        if linked(target):raise NativeIOError('Links and junctions are blocked.')
        actual=target.resolve(strict=False);identity=root.path.stat()
        if not actual.is_relative_to(root.path) or (identity.st_dev,identity.st_ino)!=root.identity:
            raise NativeIOError('The permitted folder changed; choose it again.')
        return actual

    def root_path(self,owner,window,root_id):
        with self.lock:root=self.roots.get(root_id)
        if root is None or (root.owner,root.window)!=(owner,window):raise NativeIOError('Folder permission is unavailable.')
        return root.path

    def read(self,owner,window,root_id,relative):
        path=self.resolve(owner,window,root_id,relative)
        from app.knowledge.intake import _TEXT_SUFFIXES
        if path.suffix.lower() not in _TEXT_SUFFIXES:raise NativeIOError('Choose a supported UTF-8 text file.')
        root=self.root_path(owner,window,root_id)
        with pin_directories(root,path.parent),path.open('rb') as handle:
            before=os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode):raise NativeIOError('Only regular text files can be read.')
            if os.name=='nt':
                import msvcrt
                opened=final_handle_path(msvcrt.get_osfhandle(handle.fileno()))
                if not opened.is_relative_to(root) or secret_file(opened):raise NativeIOError('The opened file is outside its permission scope.')
            self.resolve(owner,window,root_id,relative)
            data=handle.read(self.MAX_TEXT+1);after=os.fstat(handle.fileno())
        if len(data)>self.MAX_TEXT or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise NativeIOError('The text file exceeds 8 KB or changed while reading.')
        try:text=data.decode('utf-8-sig',errors='strict')
        except UnicodeError:raise NativeIOError('The file is not supported UTF-8 text.') from None
        if '\0' in text:raise NativeIOError('Binary data cannot be read as text.')
        return {'path':relative,'text':text,'digest':sha256(data).hexdigest(),'untrusted':True}

    def list_folder(self,owner,window,root_id,relative=''):
        path=self.resolve(owner,window,root_id,relative,allow_root=True)
        if not path.is_dir():raise NativeIOError('Choose a folder inside the permitted root.')
        items=[];truncated=False
        from app.resources.context import check_native_stop
        with pin_directories(self.root_path(owner,window,root_id),path),os.scandir(path) as entries:
            for visited,entry in enumerate(entries):
                check_native_stop()
                if visited>=5000 or len(items)>=200:truncated=True;break
                name=entry.name
                if name.casefold() in SKIP_DIRS or secret_file(name) or entry.is_symlink() or Path(entry.path).is_junction():continue
                directory=entry.is_dir(follow_symlinks=False)
                if not directory and not entry.is_file(follow_symlinks=False):continue
                items.append({'name':name,'kind':'folder' if directory else 'file','bytes':0 if directory else entry.stat(follow_symlinks=False).st_size})
        return {'items':sorted(items,key=lambda item:item['name'].casefold()),'truncated':truncated}

    def preview_write(self,owner,window,root_id,relative,content):
        if not isinstance(content,str) or len(content.encode('utf-8'))>self.MAX_TEXT or '\0' in content:
            raise NativeIOError('Writes are bounded to 8 KB of UTF-8 text.')
        path=self.resolve(owner,window,root_id,relative)
        if not path.parent.is_dir():raise NativeIOError('The destination folder must already exist.')
        existing=path.exists();old=self.read(owner,window,root_id,relative) if existing else {'text':'','digest':None}
        diff=''.join(difflib.unified_diff(old['text'].splitlines(keepends=True),content.splitlines(keepends=True),fromfile=relative+' (current)',tofile=relative+' (proposed)'))
        return {'path':relative,'exists':existing,'before_digest':old['digest'],'after_digest':sha256(content.encode()).hexdigest(),'diff':diff,'content':content}

    def preview_folder(self,owner,window,root_id,relative):
        path=self.resolve(owner,window,root_id,relative)
        if path.parent!=self.root_path(owner,window,root_id):raise NativeIOError('Create one folder directly inside the permitted folder.')
        if path.exists():raise NativeIOError('That folder already exists. Choose a different name.')
        if not path.parent.is_dir():raise NativeIOError('The destination folder is unavailable.')
        return {'path':relative,'exists':False}

    def create_folder(self,owner,window,root_id,preview):
        from app.resources.context import check_native_stop
        path=self.resolve(owner,window,root_id,preview['path']);root=self.root_path(owner,window,root_id)
        with self.lock,pin_directories(root,path.parent):
            check_native_stop();current=self.preview_folder(owner,window,root_id,preview['path'])
            if current!=preview:raise NativeIOError('The folder destination changed after approval; nothing was created.')
            path.mkdir(mode=0o700)
        return {'path':preview['path'],'created':True}

    def write(self,owner,window,root_id,preview):
        from app.resources.context import check_native_stop
        path=self.resolve(owner,window,root_id,preview['path']);root=self.root_path(owner,window,root_id)
        with self.lock,pin_directories(root,path.parent):
            check_native_stop();path=self.resolve(owner,window,root_id,preview['path'])
            current=self.preview_write(owner,window,root_id,preview['path'],preview['content'])
            if any(current[key]!=preview[key] for key in ['exists','before_digest','after_digest']):
                raise NativeIOError('The file changed after preview. Review a new diff; nothing was written.')
            temporary=path.parent/('.ersel-write-'+uuid4().hex+'.tmp')
            try:
                with temporary.open('xb') as handle:
                    handle.write(preview['content'].encode('utf-8'));handle.flush();os.fsync(handle.fileno())
                check_native_stop();self.resolve(owner,window,root_id,preview['path'])
                os.replace(temporary,path)
            finally:
                if temporary.exists():temporary.unlink()
            return {'path':preview['path'],'written':True,'digest':preview['after_digest']}
