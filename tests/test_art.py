import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

spec=importlib.util.spec_from_file_location('gothic_art_test',Path(__file__).resolve().parents[1]/'scripts/gothic_art.py')
art=importlib.util.module_from_spec(spec);spec.loader.exec_module(art)


class GothicArtTests(unittest.TestCase):
    def test_canvas_dimensions_ascii_and_repeatability(self):
        for scene in ('facade','nave'):
            for width,height in ((81,41),(121,65),(240,120)):
                p=art.parameters(scene=scene,width=width,height=height)
                result=art.artwork(p)
                self.assertTrue(result.isascii())
                self.assertEqual(len(result.splitlines()),height)
                self.assertTrue(all(len(line)==width for line in result.splitlines()))
                self.assertEqual(result,art.artwork(p))
                self.assertGreater(result.count('@'),0,'Rose-window center missing')
                self.assertGreater(result.count('^'),0,'Pointed arch/spire missing')

    def test_seed_and_style_change_texture_without_code_input(self):
        first=art.artwork(art.parameters(seed=14))
        self.assertNotEqual(first,art.artwork(art.parameters(seed=15)))
        self.assertNotEqual(first,art.artwork(art.parameters(style='ruins')))

    def test_parameter_bounds_and_control_characters_are_rejected(self):
        for kwargs in ({'width':10000},{'height':1},{'seed':-1},{'width':True},{'title':'bad\ntext'},{'title':'non-ascii: \u2603'},{'scene':'shell-command'}):
            with self.assertRaises(ValueError):art.parameters(**kwargs)

    def test_monochrome_exports_windows_newlines_and_one_shot_preservation(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d);p=art.parameters(width=81,height=41,title='JUPI <&>')
            art.render(p,directory)
            text=(directory/'cathedral.txt').read_bytes();windows=(directory/'cathedral-windows.txt').read_bytes()
            self.assertEqual(windows,text.replace(b'\n',b'\r\n'))
            ET.parse(directory/'cathedral.svg')
            with Image.open(directory/'cathedral.png') as image:
                self.assertEqual(image.mode,'1')
                self.assertEqual({v for count,v in image.getcolors(3)},{0,255})
            before=(directory/'receipt.json').read_bytes()
            with self.assertRaises(FileExistsError):art.render(p,directory)
            self.assertEqual((directory/'receipt.json').read_bytes(),before)

    def test_queued_source_change_fails_before_writing(self):
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d)/'unwritten'
            with self.assertRaises(ValueError):art.render(art.parameters(),directory,expected_source='0'*64)
            self.assertFalse(directory.exists())


if __name__=='__main__':unittest.main()
