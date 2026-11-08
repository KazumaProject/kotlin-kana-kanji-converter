import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import dbpedia_sources as d


class DBpediaSourcesTest(unittest.TestCase):
    def test_person_pagination_counts_entities_before_optional_english_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rule=root/'policy.json'
            selector=dict(id='actors',topic='people.actors',kind='person',queryVersion=4,pageSize=1,
                occupationValues=['Actor','Actress'],**{'class':'Actor'})
            d.h.dump(rule,dict(schemaVersion=1,pageSize=5000,selectors=[selector]))
            calls=[]
            def reply(url,path):
                calls.append(url)
                rows=[]
                if len(calls)==1:
                    base=dict(item={'value':'http://dbpedia.org/resource/Fixture'},adult={'value':'0'},
                        company={'value':'0'},hasEnglishArticle={'value':'1'})
                    rows=[dict(base,label={'value':s,'xml:lang':'en'}) for s in ['Fixture','Fixture alias']]
                path.write_text(json.dumps(dict(results={'bindings':rows})));return {}
            with patch.object(d,'download',reply),patch.object(d.time,'sleep'):
                d.fetch(root/'source',rule)
            records,_,_=d.collect(root/'source',rule)
            self.assertEqual(2,len(calls));self.assertEqual({'Fixture','Fixture alias'},{r['surface'] for r in records})
            query=d.query(selector,0,1)
            inner=query[query.index('SELECT DISTINCT'):query.index('OPTIONAL')]
            self.assertNotIn('rdfs:label',inner)
            self.assertIn('"Actor"@en',inner)

    def test_http_200_partial_results_are_rejected(self):
        d.complete_headers({'Content-Type':'application/sparql-results+json'})
        for headers in [{'X-SPARQL-MaxRows':'10000'},{'X-SQL-State':'S1TAT'},{'X-SQL-Message':'Returning incomplete results'}]:
            with self.assertRaisesRegex(ValueError,'partial/capped'):d.complete_headers(headers)

    def test_sources_follow_keysets_and_keep_adult_records_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rule=root/'policy.json';d.h.dump(rule,dict(schemaVersion=1,pageSize=5000,
                selectors=[dict(id='actors',topic='people.actors',kind='person',**{'class':'Actor'})]))
            def reply(url,path):
                row=dict(item={'value':'http://dbpedia.org/resource/Fixture'},label={'value':'Fixture','xml:lang':'en'},
                         article={'value':'http://en.wikipedia.org/wiki/Fixture'},adult={'value':'1'},company={'value':'0'})
                path.write_text(json.dumps(dict(results={'bindings':[row]})));return {}
            with patch.object(d,'download',reply),patch.object(d.time,'sleep'):d.fetch(root/'source',rule)
            records,manifest,restricted=d.collect(root/'source',rule)
            self.assertEqual('Fixture',records[0]['surface']);self.assertEqual('adult-industry-person',restricted[0]['reason'])
            self.assertIn('Fixture',d.query(dict(id='actors',kind='person',**{'class':'Actor'}),0,5000,
                ['http://dbpedia.org/resource/Fixture','Fixture']))
            p=root/'source/dbpedia.json';v=d.h.replay.read_json(p);v['pages'][0]['headers']={'X-SQL-State':'S1TAT'};d.h.dump(p,v)
            with self.assertRaisesRegex(ValueError,'partial/capped'):d.verify(root/'source',rule)
