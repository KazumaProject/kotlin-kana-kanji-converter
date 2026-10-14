import unittest
import datetime
import supplement_gemini_readings as g


class GeminiReadingsTest(unittest.TestCase):
    def test_current_response_and_ids_preserve_mapping(self):
        response={'status':'completed','steps':[{'type':'model_output','content':[{'type':'text','text':'{"items":["9:い","2:あ"]}'}]}]}
        self.assertEqual(g.validate_items(g.parse_response(response),[(2,'甲'),(9,'乙')]),['あ','い'])
        for items in [['2:あ','2:い'],['2:あ'],['2:あ','10:い'],['あ','い']]:
            with self.assertRaises(ValueError):g.validate_items({'items':items},[(2,'甲'),(9,'乙')])
        with self.assertRaises(ValueError):g.parse_response({'status':'in_progress'})

    def test_reading_constraints_withhold_altered_kana_and_known_parts(self):
        known={'膵癌':{'すいがん'},'発赤':{'はっせき'}}
        hints=g.reading_hints('膵癌術後再発',known)
        self.assertEqual(hints,[{'surface':'膵癌','reading':'すいがん'}])
        self.assertTrue(g.consistent_reading('膵癌術後再発','すいがんじゅつごさいはつ',hints))
        self.assertFalse(g.consistent_reading('膵癌術後再発','すいこんじゅつごさいはつ',hints))
        self.assertFalse(g.consistent_reading('アレルギー歴','あれらぎーれき',[]))
        self.assertFalse(g.consistent_reading('不明','',[]))

    def test_paid_wrong_project_and_stale_proof_fail_closed(self):
        now=datetime.datetime(2026,10,14,tzinfo=datetime.timezone.utc)
        proof=dict(project_id=g.PROJECT,billing_enabled=False,api_project_verified=True,
                   api_quota_verified=True,model=g.MODEL,verified_at=now.isoformat())
        g.verify_free_project(proof,now)
        for change in [dict(billing_enabled=True),dict(project_id='another'),dict(model='another'),
                       dict(api_quota_verified=False),dict(verified_at=(now-datetime.timedelta(days=2)).isoformat())]:
            with self.assertRaises(ValueError):g.verify_free_project({**proof,**change},now)
