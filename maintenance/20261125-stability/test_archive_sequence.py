from pathlib import Path
import stat
import sys
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import boot_archive as a
import audit_sequence as m


def archive(rows):
    out=b''
    for i,(name,body,mode) in enumerate(rows):
        out+=a.member(name,body,mode,i+1)
    return out+a.member('TRAILER!!!',b'',0,100)


def one(body=b'old'):
    return archive([('usbroot.sh',body,stat.S_IFREG|0o600)])


class SequenceTests(unittest.TestCase):
    def test_single(self):
        data=one();v,s=m.audit_archive_sequence(data)
        self.assertEqual(data[v['usbroot.sh']['body']:v['usbroot.sh']['body']+3],b'old')
        self.assertEqual(s['archives'],1)
    def test_later_selector_is_effective(self):
        data=one()+one(b'new');v,s=m.audit_archive_sequence(data);x=v['usbroot.sh']
        self.assertEqual(data[x['body']:x['body']+x['size']],b'new')
        self.assertEqual(x['archive_index'],1);self.assertEqual(s['overridden_paths'],['usbroot.sh'])
    def test_distinct_members_preserved(self):
        data=one()+archive([('other',b'x',stat.S_IFREG|0o600)])
        v,s=m.audit_archive_sequence(data);self.assertEqual(set(v),{'usbroot.sh','other'})
    def test_zero_padding(self):
        _,s=m.audit_archive_sequence(b'\0'*4+one()+b'\0'*512+one()+b'\0'*8)
        self.assertEqual(s['archives'],2)
    def test_empty(self):
        with self.assertRaises(ValueError):m.audit_archive_sequence(b'\0'*32)
    def test_junk_after_trailer(self):
        with self.assertRaises(ValueError):m.audit_archive_sequence(one()+b'junk')
    def test_truncated_next_header(self):
        with self.assertRaises(ValueError):m.audit_archive_sequence(one()+b'070701')
    def test_missing_trailer(self):
        with self.assertRaises(ValueError):m.audit_archive_sequence(a.member('x',b'1',stat.S_IFREG|0o600,1))
    def test_nonzero_trailer(self):
        with self.assertRaises(ValueError):m.audit_archive_sequence(a.member('TRAILER!!!',b'x',0,1))
    def test_path_traversal(self):
        with self.assertRaises(ValueError):m.audit_archive_sequence(archive([('../x',b'1',stat.S_IFREG|0o600)]))
    def test_duplicate_within_archive_remains_rejected(self):
        with self.assertRaises(ValueError):m.audit_archive_sequence(archive([('x',b'1',stat.S_IFREG|0o600),('x',b'2',stat.S_IFREG|0o600)]))
    def test_hardlinked_file_unqualified(self):
        data=bytearray(one());data[38:46]=b'00000002'
        with self.assertRaises(ValueError):m.audit_archive_sequence(bytes(data))
    def test_directory_nlink_two_supported(self):
        _,s=m.audit_archive_sequence(archive([('lib',b'',stat.S_IFDIR|0o755)]));self.assertEqual(s['archives'],1)
    def test_archive_count_bound(self):
        with self.assertRaises(ValueError):m.audit_archive_sequence(one()*17)
    def test_member_count_bound(self):
        data=archive([(str(i),b'',stat.S_IFREG|0o600) for i in range(4096)])
        with self.assertRaises(ValueError):m.audit_archive_sequence(data)
    def test_compressed_size_bound(self):
        with self.assertRaises(ValueError):m.audit_archive_sequence(b'\0'*(a.MAX_ARCHIVE+1))
    def test_single_archive_writer_stays_strict(self):
        with self.assertRaises(ValueError):list(a.entries(one()+one()))
    def test_private_supplement_contract_unchanged(self):
        # Synthetic bytes only; no real device key is accessed.
        import gzip
        result,receipt=a.supplement(gzip.compress(one(),mtime=0),b'T'*32)
        v=list(a.entries(a.unpack(result)))
        self.assertTrue(receipt['original_members_preserved']);self.assertIn(a.KEY_NAME,{x['name'] for x in v})


if __name__=='__main__':unittest.main(verbosity=2)
