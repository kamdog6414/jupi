import stat

import boot_archive


def audit_archive_sequence(data):
    """Inspect a bounded sequence of complete newc archives without extraction.

    Audit only: the private key-supplement writer retains its original strict
    single-archive parser. Last regular-file entries override earlier versions.
    Hard-linked files are deliberately unqualified because inode aliasing can
    change effective content without repeating a pathname.
    """
    if not isinstance(data, bytes) or len(data) > boot_archive.MAX_ARCHIVE:
        raise ValueError('Audit archive byte bound')
    offset = 0
    archives = 0
    count = 0
    effective = {}
    replaced = []
    while offset < len(data):
        while offset < len(data) and data[offset] == 0:
            offset += 1
        if offset == len(data):
            break
        if offset % 4 or archives >= 16:
            raise ValueError('Audit archive alignment/count bound')
        start = offset
        trailer = False
        # Stop at the validated trailer; the next archive is inspected by the
        # outer loop instead of relaxing entries()'s trailing-data rejection.
        for original in boot_archive.entries(data[start:]):
            item = dict(original)
            count += 1
            if count > 4096:
                raise ValueError('Audit member count bound')
            item['archive_index'] = archives
            for key in ('offset', 'body', 'end'):
                item[key] += start
            if item['name'] == 'TRAILER!!!':
                if item['size']:
                    raise ValueError('Nonempty audit archive trailer')
                offset = item['end']
                trailer = True
                break
            nlink = int(data[item['offset']+38:item['offset']+46], 16)
            item['nlink'] = nlink
            if not stat.S_ISDIR(item['mode']) and nlink != 1:
                raise ValueError('Hard-linked audit member unqualified')
            if item['name'] in effective:
                replaced.append(item['name'])
            effective[item['name']] = item
        if not trailer:
            raise ValueError('Missing audit archive trailer')
        archives += 1
    if not archives:
        raise ValueError('Empty audit archive sequence')
    return effective, {'archives': archives, 'members_with_trailers': count,
                       'overridden_paths': replaced,
                       'scope': 'Read-only complete newc sequence; no extraction, execution or key supplementation'}
