import unittest
import yago_specific_types as y
import yago_name_variants as variants


class SpecificTypeTests(unittest.TestCase):
    def test_type_mistakes_cannot_promote_protocol_partition_or_work_to_product(self):
        for root,text in [('yago:Electronic_Product','standard for the layout of a partition table'),('yago:Computing_platform','data query language developed by Facebook'),('yago:Service_On_Internet','analog horror YouTube web series'),('yago:Server_software','12-digit unique identity number for residents of India')]:
            self.assertFalse(y.supported(root,[{'label':text,'language':'en'}]))
        self.assertNotIn('schema:Product',y.ROOTS);self.assertNotIn('schema:CreativeWork',y.ROOTS)

    def test_specific_named_software_hardware_and_character_descriptions_support_types(self):
        for root,text in [('yago:Proprietary_software','desktop publishing application by Serif Europe'),('yago:Computing_platform','software framework created by Microsoft'),('yago:Electronic_Product','handheld GPS receiver'),('yago:Character_arts','fictional character from a television series')]:
            self.assertTrue(y.supported(root,[{'label':text,'language':'en'}]))
            self.assertFalse(y.supported(root,[{'label':text,'language':'fr'}]))
        self.assertFalse(y.supported('yago:Character_arts',[{'label':'Chinese deity associated with flood control','language':'en'}]))

    def test_additional_specific_types_need_their_own_explicit_description(self):
        examples=[('yago:Digital_audio_workstation','digital audio workstations for macOS, iOS, and iPadOS'),
            ('yago:Computer_Network_Protocol','computer network protocol'),
            ('yago:Python_Package','Python library'),('yago:Music_festival','annual American music festival'),
            ('yago:Convention_meeting','video game convention held by a company'),
            ('yago:Trade_show','trade fair for video games industry'),
            ('yago:Sports_league','ice hockey league in North America'),
            ('yago:Motorcycle_Racing_Series','Motorcycling World Championship class'),
            ('yago:Typeface_Family','sans-serif typeface family'),('yago:Film','1980 film directed by a filmmaker')]
        for root,text in examples:
            self.assertTrue(y.supported(root,[{'label':text,'language':'en'}]),root)
            self.assertFalse(y.supported(root,[{'label':'general abstract concept','language':'en'}]),root)
            self.assertFalse(y.supported(root,[{'label':text,'language':'fr'}]),root)
        self.assertFalse(y.supported('yago:Film',[{'label':'film production company','language':'en'}]))
        self.assertNotIn('name_product',y.ROOTS['yago:Computer_Network_Protocol'])

    def test_legacy_preparations_keep_their_original_root_matrix(self):
        self.assertTrue(y.LEGACY_ROOTS.keys() < y.ROOTS.keys())
        self.assertTrue(y.PREVIOUS_ROOTS.keys() < y.ROOTS.keys())
        self.assertNotIn('yago:Film',y.LEGACY_ROOTS)

    def test_genres_games_ships_and_services_require_specific_descriptions(self):
        examples=[('yago:Comedy_film','2001 American comedy film directed by a filmmaker'),
            ('yago:Film_Based_On_A_Novel','1992 film directed by a filmmaker'),
            ('yago:Tabletop_role-playing_game','tabletop fantasy role-playing game'),
            ('yago:Ship_of_the_line','74-gun ship of the line of the French Navy'),
            ('yago:News_Aggregation_Website','American online news aggregator and blog'),
            ('yago:Pokémon_Region','Pokémon region')]
        for root,text in examples:
            self.assertTrue(y.supported(root,[dict(label=text,language='en')]),root)
            self.assertFalse(y.supported(root,[dict(label=text,language='fr')]),root)
            self.assertFalse(y.supported(root,[dict(label='generic concept or unrelated entity',language='en')]),root)
        self.assertFalse(y.supported('yago:Comedy_film',[dict(label='film genre',language='en')]))

    def test_fictional_species_class_needs_both_specific_path_and_description(self):
        entity=dict(paths={},classPaths={'yago:Fictional_Bird':{'yago:Fictional_Bird':[]}},
            descriptions=[dict(label='fictional bird species',language='en')])
        self.assertEqual({'noun','noun_proper','name_fictional'},variants.categories(entity,y.ROOTS))
        entity['descriptions']=[dict(label='real bird species',language='en')]
        self.assertFalse(variants.categories(entity,y.ROOTS))
        entity['descriptions']=[dict(label='fictional bird species',language='en')]
        entity['classPaths']={'schema:Person':{'schema:Person':[]}}
        self.assertFalse(variants.categories(entity,y.ROOTS))
        entity['classPaths']={'yago:Fictional_Bird':{'yago:Fictional_Bird':[]}}
        entity['descriptions'][0]['language']='fr'
        self.assertFalse(variants.categories(entity,y.ROOTS))


if __name__=='__main__':unittest.main()
