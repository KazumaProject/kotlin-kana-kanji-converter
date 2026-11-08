import argparse
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import package_preview as p


class PackagePreviewTest(unittest.TestCase):
    def fixture(self, root):
        args = argparse.Namespace(base_archive=root/'base.zip', base_manifest=root/'manifest.json',
            base_licenses=root/'licenses.txt', runtime=root/'runtime', inventory=root/'inventory.jsonl',
            out=root/'out', revision='a'*40, base_release='v1.0.0')
        base = {'app/src/main/assets/system/token.dat.zip': b'original Japanese bytes'}
        manifest = p.encode(dict(files={n: p.sha(b) for n, b in base.items()}))
        args.base_manifest.write_bytes(manifest)
        args.base_archive.write_bytes(p.archive_bytes(base | {'dictionary-distribution-manifest.json': manifest}))
        args.base_archive_sha256 = p.sha(args.base_archive.read_bytes())
        args.base_licenses.write_text('Original license\n')
        files = {n: ('fixture '+n).encode() for n in p.CORE | p.OPTIONAL | {'source-evidence-manifest.json', 'supplement-manifest.json'}}
        files['grammar/notices/LICENSE.txt'] = b'English source license'
        files['grammar/bundle.properties'] = ('noticeCount=1\nnotice.LICENSE.txt.sha256=' +
            p.sha(files['grammar/notices/LICENSE.txt']) + '\ncategories.erol.sha256=' +
            p.sha(files['grammar/categories.erol']) + '\n').encode()
        for n, data in files.items():
            target=args.runtime/n;target.parent.mkdir(exist_ok=True, parents=True);target.write_bytes(data)
        args.inventory.write_text(json.dumps(dict(reading='name', surface='Name', cost=6000))+'\n')
        return args, base, files

    def test_split_archives_preserve_payloads_and_provenance_and_can_be_recombined(self):
        with tempfile.TemporaryDirectory() as t:
            args, base, runtime = self.fixture(Path(t))
            result=p.package(args)
            self.assertEqual((1,1,1),(result['spellings'],result['pairs'],result['japaneseFilesPreserved']))
            with zipfile.ZipFile(args.out/'japanese_keyboard_dictionary_assets.zip') as app, zipfile.ZipFile(args.out/p.SUPPORT) as support:
                for n,b in base.items():self.assertEqual(b,app.read(n))
                self.assertNotIn(p.PREFIX+'grammar/categories.erol',app.namelist())
                self.assertNotIn(p.PREFIX+'runtime-support/qwerty_glide_index.dat',app.namelist())
                combined={n:app.read(n) for n in app.namelist()}|{n:support.read(n) for n in support.namelist()}
                for n,b in runtime.items():
                    if n in {'reading.dat','token.dat'}:
                        with zipfile.ZipFile(io.BytesIO(combined[p.PREFIX+n+'.zip'])) as nested:self.assertEqual(b,nested.read(n))
                    else:self.assertEqual(b,combined[p.asset_path(n)])
                manifest=json.loads(app.read('dictionary-distribution-manifest.json'))
                self.assertEqual(p.sha((args.out/p.SUPPORT).read_bytes()),manifest['englishDictionary']['optionalSupport']['sha256'])
            self.assertIn('Original license',(args.out/'DICTIONARY-LICENSES.txt').read_text())
            self.assertIn('English source license',(args.out/'DICTIONARY-LICENSES.txt').read_text())
            for line in (args.out/'DICTIONARY-SHA256SUMS').read_text().splitlines():
                digest,name=line.split();self.assertEqual(digest,p.sha((args.out/name).read_bytes()))

    def test_rejects_bad_base_hash_and_extra_runtime_authoring_data(self):
        with tempfile.TemporaryDirectory() as t:
            args,_,_=self.fixture(Path(t));correct=args.base_archive_sha256;args.base_archive_sha256='0'*64
            with self.assertRaisesRegex(ValueError,'Base archive checksum'):p.package(args)
            args.base_archive_sha256=correct;(args.runtime/'entries.tsv').write_text('authoring only')
            with self.assertRaisesRegex(ValueError,'Unexpected runtime file'):p.package(args)
            self.assertFalse(args.out.exists())

    def test_rejects_unverified_notices(self):
        with tempfile.TemporaryDirectory() as t:
            args,_,_=self.fixture(Path(t));(args.runtime/'grammar/notices/LICENSE.txt').write_text('modified')
            with self.assertRaisesRegex(ValueError,'Notice checksum'):p.package(args)
