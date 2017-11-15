import errno
import machine
import os

from noggin import Noggin, Response, HTTPError

# cribbed from
# https://github.com/micropython/micropython-lib/blob/master/stat/stat.py
S_IFDIR = 0o040000
S_IFMT = 0o170000

app = Noggin()

helptext = '''<html>

<h1>Simple file operations</h1>

<ul>
<li><a href="/disk"><code>GET /disk</code></a> to get filesystem
information</li>
<li><a href="/disk/free"><code>GET /disk/free</code></a> to get information
about available disk space</li>
<li><a href="/file"><code>GET /file</code></a> to list available files</li>
<li><code>GET /file/&lt;path&gt;</code> to get a file (for example,
<a href="/file/boot.py">boot.py</a>)</li>
<li><code>PUT /file/&lt;path&gt;</code> to write a file</li>
<li><code>POST /file/&lt;path&gt;</code> to rename a file (new name is
<code>POST</code> body)</li>
<li><code>DELETE /file/&lt;path&gt;</code> to delete a file</li>
</ul>
</html>'''


@app.route('/')
def index(req):
    return Response(content=helptext, mimetype='text/html')


def get_statvfs():
    statvfs_fields = [
        'bsize',
        'frsize',
        'blocks',
        'bfree',
        'bavail',
        'files',
        'ffree',
    ]
    return dict(zip(statvfs_fields, os.statvfs('/')))


@app.route('/disk')
def disk_stats(req):
    '''Return information about the filesystem.'''
    return get_statvfs()


@app.route('/disk/free')
def disk_free(req):
    '''Return available space'''
    s = get_statvfs()
    return {
        'blocks': s['bfree'],
        'bytes': (s['bsize'] * s['bfree'])
    }


def get_file_list(path):
    '''Recursively list files.

    Returns a list of (name, size, is_dir, children) tuples, where
    children is a similar list of is_dir is True or None of is_dir
    is False.
    '''

    files = []

    for f in os.listdir(path):
        fp = '/'.join([path, f])
        print('* checking', f)
        s = os.stat(fp)
        if s[0] & S_IFMT == S_IFDIR:
            files.append((f, s[6], True, get_file_list(fp)))
        else:
            files.append((f, s[6], False, None))

    return files


@app.route('/file')
def list_files(req):
    return get_file_list('/')


@app.route('/file/(.*)')
def get_file(req, path):
    print('* request to get {}'.format(path))
    buf = bytearray(256)
    try:
        with open(path) as fd:
            while True:
                nb = fd.readinto(buf)
                if not nb:
                    break
                yield buf[:nb]
    except OSError:
        raise HTTPError(404)


@app.route('/file/(.*)', methods=['DELETE'])
def del_file(req, path):
    print('* request to delete {}'.format(path))
    try:
        os.remove(path)
    except OSError as err:
        if err.args[0] == errno.ENOENT:
            raise HTTPError(404)
        else:
            raise HTTPError(500)


@app.route('/file/(.*)', methods=['POST'])
def rename_file(req, path):
    newpath = req.text
    print('* request to rename {} -> {}'.format(path, newpath))
    try:
        os.rename(path, newpath)
    except OSError as err:
        if err.args[0] == errno.ENOENT:
            raise HTTPError(404)
        else:
            raise HTTPError(500)


@app.route('/file/(.*)', methods=['PUT'])
def put_file(req, path):
    print('* request to put {}'.format(path))
    parts = path.split(b'/')

    for i in range(len(parts) - 1):
        partial = b'/'.join(parts[:i + 1])
        print('* create directory {}'.format(partial))
        try:
            os.mkdir(partial)
        except OSError:
            pass

    with open(path, 'w') as fd:
        for chunk in req.iter_content():
            fd.write(chunk)


@app.route('/reset')
def reset(req):
    req.close()
    machine.reset()
