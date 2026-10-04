import argparse,contextlib,gzip,hashlib,io,json,pathlib,sys,tempfile,unittest
from unittest import mock
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from semantic_audit import suggested_rules,inspect_rows
import ordinary_semantics as ordinary
import worker as w
import direct_review as d

class SemanticAuditTest(unittest.TestCase):
    @contextlib.contextmanager
    def literal_reading_repair_fixture(self):
        with tempfile.TemporaryDirectory() as root:
            base=pathlib.Path(root)/'ordinary';base.mkdir();(base/'inspection-records').mkdir()
            args=argparse.Namespace(ledger=str(pathlib.Path(root)/'ledger.sqlite'),documents=str(pathlib.Path(root)/'documents'),config=str(w.DEFAULT_CONFIG))
            with w.connect(args.ledger) as db:
                db.executescript(w.SCHEMA);w.pin_config(db,args);w.info(db,'goldFrozen',{'sha256':'a'*64,'cases':[]})
                cid=w.insert_candidate(db,'いす','椅子',1,1,10);e=w.Evidence(db,args)
                xml='<JMdict><entry><ent_seq>1</ent_seq><k_ele><keb>椅子</keb></k_ele><r_ele><reb>いす</reb></r_ele><sense><pos>n</pos><gloss>chair</gloss></sense></entry></JMdict>'
                did=e.save('https://www.edrdg.org/pub/Nihongo/JMdict_e.gz','v1',gzip.compress(xml.encode()),'EDRDG')
                fid=e.fact('いす','椅子','meaning',[],'JMdict:1:sense:1',did,{'source':'JMdict','entryId':'1','evidence':'entry-1-sense-1'})
                doc=d.verify_document(db,did)
                valid,failures=inspect_rows([dict(id=cid,reading='いす',surface='椅子',evidenceId=fid,document_id=did,target='JMdict:1:sense:1',body={'source':'JMdict','entryId':'1','evidence':'entry-1-sense-1'},path=doc['path'],sha256=doc['sha256'])])
                self.assertEqual([],failures);(base/'raw-verified.json').write_text(w.canonical(valid));(base/'groups.json').write_text('[]');db.commit()
            with mock.patch.object(ordinary,'BASE',base),mock.patch.object(w,'inference',side_effect=AssertionError('model called')):
                yield args,cid,xml

    def test_missing_reading_is_restored_only_from_verified_literal_xml(self):
        with self.literal_reading_repair_fixture() as (args,cid,xml),contextlib.redirect_stdout(io.StringIO()):
            ordinary.apply(args)
            with w.connect(args.ledger) as db:
                row=db.execute('SELECT state,decision FROM candidates WHERE id=?',(cid,)).fetchone()
                self.assertEqual('reviewed',row['state']);decision=json.loads(row['decision']);self.assertEqual(1,len(decision['readingEvidence']))
                body=json.loads(db.execute('SELECT body FROM facts WHERE id=?',(decision['readingEvidence'][0],)).fetchone()[0])
                self.assertEqual('いす',body['reading']);self.assertEqual('椅子',body['surface']);self.assertIn('<reb>いす</reb>',body['quotation'])

    def test_reading_repair_does_not_guess_from_semantic_category(self):
        with self.literal_reading_repair_fixture() as (args,cid,xml),contextlib.redirect_stdout(io.StringIO()):
            with w.connect(args.ledger) as db:db.execute('UPDATE candidates SET reading=? WHERE id=?',('ちぇあ',cid))
            with self.assertRaisesRegex(ValueError,'Literal source constraints changed'):ordinary.apply(args)
            with w.connect(args.ledger) as db:self.assertEqual(0,db.execute("SELECT COUNT(*) FROM facts WHERE kind='reading'").fetchone()[0])

    def test_unclassified_literal_sense_does_not_leave_reading_repair_queued(self):
        with self.literal_reading_repair_fixture() as (args,cid,xml),contextlib.redirect_stdout(io.StringIO()):
            with mock.patch('semantic_audit.suggested_rules',return_value=[]):ordinary.apply(args)
            with w.connect(args.ledger) as db:
                row=db.execute('SELECT state,decision FROM candidates WHERE id=?',(cid,)).fetchone()
                self.assertEqual('needs_review',row['state'])
                decision=json.loads(row['decision']);self.assertEqual([],decision['roles'])
                self.assertEqual(1,len(decision['readingEvidence']))

    def test_existing_repaired_reading_queue_is_rechecked_without_guessing_category(self):
        with self.literal_reading_repair_fixture() as (args,cid,xml),contextlib.redirect_stdout(io.StringIO()):
            ordinary.apply(args)
            with w.connect(args.ledger) as db:
                db.execute("UPDATE candidates SET state='queued',reason='evidence-changed',decision=NULL WHERE id=?",(cid,))
            with mock.patch('semantic_audit.suggested_rules',return_value=[]):ordinary.apply(args)
            with w.connect(args.ledger) as db:
                row=db.execute('SELECT state,decision FROM candidates WHERE id=?',(cid,)).fetchone()
                self.assertEqual('needs_review',row['state']);self.assertEqual([],json.loads(row['decision'])['roles'])

    def categories(self,gloss,fields=(),source='JMdict',pos=(),misc=()):
        return {c for c,r,g in suggested_rules([gloss],fields,source,pos,misc)}
    def test_explicit_biological_definition_and_scientific_name(self):
        self.assertEqual({'organism'},self.categories('Japanese parrotfish (Calotomus japonicus)'))
        self.assertEqual({'organism'},self.categories('grannyvine (species of morning glory, Ipomoea tricolor)'))
        self.assertEqual({'technical'},self.categories('XOR (Boolean operator)'))
        self.assertEqual(set(),self.categories('bronze mirror with bells (Kofun period)'))
        self.assertEqual(set(),self.categories('decisive character (Chinese poetry)'))
        self.assertEqual(set(),self.categories('salted cod (Gadus morhua)'))
    def test_object_head_is_distinct_from_mention_or_metaphor(self):
        for gloss in ('oil depot','Toyouke Shrine (the outer shrine of Ise Shrine)'):
            self.assertEqual({'facility'},self.categories(gloss))
        for gloss in ('suspension bridge effect','style of shrine architecture','guardian lion-dogs at a Shinto shrine','to cross a dangerous bridge'):
            self.assertNotIn('facility',self.categories(gloss))
        self.assertEqual({'transport'},self.categories('carrier-borne attack aircraft'))
        for gloss in ('vrooming motorcycle gangs','bicycle trip','vehicle accident involving a turn','dry weight (of a vehicle)','leaving a warship','vehicle accident involving a turn (when a car hits a bicycle that was going straight)','paper airplane'):
            self.assertNotIn('transport',self.categories(gloss))
    def test_geography_requires_explicit_named_target_type(self):
        self.assertEqual({'place'},self.categories('Tiree (island)',source='JMnedict'))
        self.assertEqual(set(),self.categories('Tiree',source='JMnedict'))
        self.assertEqual(set(),self.categories('mountain zebra (Equus zebra)')-{'organism'})
        self.assertNotIn('place',self.categories('guardian deity of rivers'))
    def test_new_categories_have_positive_semantics_and_negative_guards(self):
        self.assertEqual({'astronomy'},self.categories('active galaxy'))
        self.assertEqual({'astronomy'},self.categories('Ophiuchus (constellation)'))
        self.assertEqual({'sports'},self.categories('one-armed shoulder throw (judo or sumo)'))
        self.assertNotIn('sports',self.categories('to have the upper hand in sumo (technique) but lose the match'))
        self.assertEqual({'religion'},self.categories('ceremony to consecrate a newly made Buddhist statue'))
        self.assertNotIn('religion',self.categories('study of religious doctrine'))
        self.assertNotIn('religion',self.categories('separation of religious ritual and government administration'))
        self.assertEqual({'technical'},self.categories('epidural anaesthesia'))
        self.assertEqual({'technical'},self.categories('non-linear partial differential equation'))
        self.assertEqual({'technical'},self.categories('acute myeloid leukemia'))
        self.assertEqual({'technical'},self.categories('compiled programming language'))
        self.assertEqual({'food'},self.categories('midday meal'))
        self.assertEqual({'food'},self.categories('chicken noodle soup'))
        self.assertNotIn('food',self.categories('soup kitchen'))
        self.assertNotIn('food',self.categories('person who sells bread'))
    def test_ordinary_semantic_families_have_explicit_heads_and_exclusions(self):
        for gloss in ('deep regret','personal responsibility','mutual friendship','unexpected surprise','round table','soft pillow','winter vacation'):
            self.assertIn('general',self.categories(gloss))
        for gloss in ('quantum state','contract agreement','financial trouble','Japanese imperial era','algorithmic problem','molecular weight','person with a pillow'):
            self.assertNotIn('general',self.categories(gloss))
    def test_named_software_is_product(self):
        self.assertEqual({'product'},self.categories('Linux (operating system)'))
        self.assertEqual({'technical'},self.categories('operating system',fields=['comp']))
        self.assertEqual({'technical'},self.categories('XOR (Boolean operator)'))
    def test_raw_inspection_counterexamples(self):
        for gloss in ('crater floor','a sidereal year','loan trust','children do not know their parents'):
            self.assertNotIn('general',self.categories(gloss))
        self.assertNotIn('general',self.categories('constant'))
        self.assertIn('general',{c for c,r,g in suggested_rules(['happy'],pos=['adj-na'])})
    def test_scoped_technical_heads_need_both_type_and_scope(self):
        self.assertEqual({'technical'},self.categories('symmetric group',fields=['math']))
        self.assertEqual(set(),self.categories('symmetric group'))
        self.assertEqual({'technical'},self.categories('computer network',fields=['comp']))
        self.assertEqual({'technical'},self.categories('lymph node',fields=['anat']))
        self.assertEqual({'technical'},self.categories('kinetic energy',fields=['physics']))
        self.assertEqual({'food'},self.categories('green tea',fields=['food']))
        self.assertNotIn('food',self.categories('green tea (Camellia sinensis)',fields=['food']))
    def test_ordinary_definition_is_specific_and_fields_only_veto(self):
        self.assertEqual({'general'},self.categories('to laugh'))
        self.assertEqual(set(),self.categories('unregistered bond'))
        self.assertEqual(set(),self.categories('to screen for a disease'))
        self.assertEqual(set(),self.categories('unknown term',fields=['med']))
        self.assertEqual(set(),self.categories('to laugh',fields=['med']))

    def test_ordinary_complements_have_positive_semantics_and_domain_guards(self):
        for gloss in ('fear of being alone','refusal to listen','laughing at oneself','sharing a room','covering in salt'):
            self.assertIn('general',self.categories(gloss))
        self.assertIn('general',self.categories('covering in salt',fields=['food']))
        for gloss in ('rejection of the null hypothesis','preparation of molecular compounds','keeping the Buddhist precepts','laughing at oneself (clinical symptom)','moving average'):
            self.assertNotIn('general',self.categories(gloss))
        self.assertNotIn('general',self.categories('reincarnation',fields=['Buddh']))
        self.assertNotIn('general',self.categories('unknown definition',fields=[]))

    def test_domain_context_does_not_hide_an_explicit_ordinary_sense(self):
        self.assertEqual({'general'},self.categories('rare occurrence',fields=['Buddh']))
        self.assertNotIn('general',self.categories('Buddhist doctrine',fields=['Buddh']))
        self.assertEqual({'general'},self.categories('bicycle trip'))
        self.assertNotIn('transport',self.categories('bicycle trip'))

    def test_culinary_preparation_is_food_and_scientific_scope_is_explicit(self):
        self.assertEqual({'food'},self.categories('fish pickled in rice-bran paste'))
        self.assertEqual({'food'},self.categories('restructured meat'))
        self.assertNotIn('food',self.categories('to pickle fish'))

    def test_food_metaphors_and_actions_are_not_edible_targets(self):
        self.assertNotIn('food',self.categories('dick cheese',misc=['vulg','sl']))
        self.assertNotIn('food',self.categories('kail spares bread',misc=['proverb']))
        self.assertNotIn('food',self.categories('covering in salt',fields=['food']))
        self.assertEqual({'organism'},self.categories('Pyropia tenera (species of edible seaweed)'))

    def test_named_language_and_structural_types_keep_their_technical_meanings(self):
        self.assertEqual({'technical'},self.categories('Example (programming language)',fields=['comp']))
        self.assertEqual({'technical'},self.categories('girder bridge'))
        self.assertEqual({'technical'},self.categories('bascule bridge'))
        self.assertEqual({'sports'},self.categories('black belt',fields=['MA']))
        self.assertEqual({'technical'},self.categories('phenotypic plasticity',fields=['biol']))
        self.assertEqual(set(),self.categories('phenotypic plasticity'))
        self.assertEqual({'technical'},self.categories('ulna',fields=['anat']))
        self.assertEqual({'technical'},self.categories('serial mouse',fields=['comp']))
        self.assertEqual(set(),self.categories('serial mouse'))

    def test_kana_variant_cannot_borrow_another_lemma_reading(self):
        with tempfile.TemporaryDirectory() as root:
            p=pathlib.Path(root)/'source.gz'
            p.write_bytes(gzip.compress(b'<JMdict><entry><ent_seq>1</ent_seq><r_ele><reb>kana</reb></r_ele><r_ele><reb>kanna</reb></r_ele><sense><gloss>hello</gloss></sense></entry></JMdict>'))
            base={'id':'fixture','path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                  'surface':'kana','reading':'kanna','target':'JMdict:1:sense:1','evidenceId':'fact','document_id':'doc',
                  'body':{'source':'JMdict','entryId':'1','evidence':'entry-1-sense-1'}}
            valid,failures=inspect_rows([base]);self.assertEqual([],valid)
            self.assertEqual([('fixture','reading-or-restriction-mismatch')],failures)
            base['reading']='kana';valid,failures=inspect_rows([base]);self.assertEqual([],failures);self.assertEqual(1,len(valid))

if __name__=='__main__':unittest.main()
