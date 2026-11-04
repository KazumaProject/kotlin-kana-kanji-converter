import unittest
import yago_specific_types as y


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


if __name__=='__main__':unittest.main()
