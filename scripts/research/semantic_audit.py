"""Read-only raw-XML semantic audit. Suggestions are source_review, never release decisions."""
import argparse,collections,gzip,hashlib,json,pathlib,re,xml.etree.ElementTree as ET
BIO_HEADS=r'(?:[a-z-]*(?:fish|bird|owl|eagle|crow|rat|mouse|deer|goat|sheep|horse|cow|ape|monkey|whale|dolphin|shark|ray|eel|carp|salmon|trout|clover|moss|fern|tree|pine|maple|oak|cedar|spruce|willow|poplar|alder|cypress|mushroom|fungus|lily|iris|orchid|rose|grass|bean|bamboo|spider|insect|moth|butterfly|beetle|bee|ant|snake|lizard|frog|toad|turtle|worm|snail|squid|octopus|jellyfish|anemone|crab|shrimp|lobster|butterwort|gentian|cress|palm|elm|hornbeam|birch|warbler|swan|grouse|cherry|gull|tern|oyster|duck|goose|tuna|pepper|zebra|bearberry|pea|azalea|hydrangea|magnolia|plum|wren|pigeon|sandpiper|hawk|heron|finch|viper|bat|weasel|squirrel|goby|cod|loach|cockle|clam|whelk|cockroach|aphid|fly|mosquito|cicada|cricket|mantis|locust|mite|tick|leech|slug|lichen|alga|bacterium|bacteria|yeast|plant|bug|skua|lamprey|rhubarb|ash|springtail|fescue|crake|marigold|python|axolotl|ragweed|apple|squash|creeper|admiral|starflower|wort|opah|wolf|dhole|camellia|wolverine|shoebill|louvar|pintail|starling|chosenia|squill|pear|petrel|cockatoo|stonechat|russula|amaranth|fleabane|flea|anise|thistle|bulbul|lespedeza|plover|lorikeet|medick|jelly|medusa|nightingale|prawn|barracuda|oxtongue|kestrel|coneflower|mussel|whitebeam|chestnut|cat|bush|chub|duckweed|bigeye|hypericum|merganser|madder|phalarope|wrasse|leopard|lapwing|bugbane|grunt|snipe|hazel|sunflower|bells|ptarmigan|drongo|alfonsino|tragopan|aspen|gurnard))(?:s|es)?'
BINOMIAL=r'\((?!(?:Boolean|Kofun|Edo|Muromachi|Japanese|Chinese|Korean|Dutch|Kyoto|French|English|Tang|Han|Meiji|Taisho|Showa|Heian|Kamakura|Sanskrit|Buddhist|Shinto|Christian)\b)[A-Z][a-z]+ [a-z]+(?: (?:var\.|subsp\.|f\.) [a-z]+)?\)'
HEADS={
 'astronomy':r'(?:galaxy|galaxies|nebula|nebulae|supernova|asteroid|planetoid|constellation|star cluster|solar eclipse|lunar eclipse|meteor shower|dwarf planet)',
 'facility':r'(?:temple|shrine|castle|palace|bridge|dam|airport|botanical garden|oil depot|fuel farm|storage facility)',
 'transport':r'(?:aircraft|airplane|aeroplane|motorcycle|bicycle|submarine|locomotive|freight train|passenger train|sailboat|ferry|warship|destroyer|steamship|helicopter|vehicle)',
 'technical':r'(?:carcinoma|sarcoma|leukemia|leukaemia|anaesthesia|anesthesia|antibiotic|vaccination|encephalitis|hepatitis|nephritis|dermatitis|arthritis|pneumonia|meningitis|diabetes|chromosome|enzyme|cancer|lymphoma|adenoma|hematoma|haematoma|glaucoma|cataract|epilepsy|dementia|sepsis|cirrhosis|cholera|tuberculosis|malaria|bronchitis|gastritis|osteoporosis|anaemia|anemia|neuropathy|scoliosis|endoscopy|biopsy|chemotherapy|radiotherapy|immunotherapy|dialysis|genome|genotype|phenotype|mutation|hormone|antibody|antigen|neuron|epithelium|ligament|tendon|cartilage|lymphocyte|monocyte|platelet|leukocyte|erythrocyte|capillary|nucleotide|amino acid|fatty acid|carboxylic acid|molecule|isotope|ion|cation|anion|electron|proton|neutron|boson|fermion|quark|meson|hadron|photon|theorem|equation|polynomial|algorithm|logarithm|integral|derivative|coefficient|integer|prime number|complex number|rational number|irrational number|eigenvalue|eigenvector|tensor|Boolean operator|logic gate|binary operator|programming language|operating system|database|compiler|interpreter|multiplexer|semiconductor|transistor|diode|thyristor|resistor|capacitor|inductor|oscillator|microprocessor)',
 'food':r'(?:bread|cake|cookie|biscuit|candy|confectionery|chocolate|sushi|soup|stew|sauce|cheese|yoghurt|yogurt|butter|noodles|pasta|dumplings|sandwich|salad|dessert|ice cream|pudding|sausage|ham|bacon|lunch|midday meal|breakfast|dinner|supper|snack|energy drink|soft drink|fruit juice|cooked rice|rice dish|Japanese dish|beverage|food ingredient)',
}
EVERYDAY=r'(?:laugh|cry|smile|eat|drink|sleep|walk|sit|stand|look|hear|tell|say|feel|wait|help|ask|want|love|hate|wash|buy|sell|pay|meet|leave|enter|arrive|bring|send|receive)'
PLACE_TYPES=r'(?:mountain|mountain range|river|lake|island|prefecture|province|municipality|district|county|village|waterfall|peninsula|bay)'
GENERAL_HEADS={
 'ordinary-mental-and-social-abstraction':r'(?:thought|feeling|emotion|desire|wish|hope|effort|decision|choice|intention|opinion|idea|memory|knowledge|habit|custom|attitude|behaviour|behavior|relationship|friendship|permission|promise|responsibility|duty|freedom|honesty|kindness|happiness|sadness|anger|fear|joy|love|hatred|confidence|courage|patience|uncertainty|possibility|necessity|truth|fact|reason|purpose|problem|situation|trouble|difficulty|mistake|failure|success|advantage|disadvantage|benefit|loss|luck|chance|opportunity|value|importance|experience|understanding|attention|interest|curiosity|concern|worry|anxiety|regret|surprise|excitement|pleasure|satisfaction|disappointment|embarrassment|pride|shame|trust|respect|gratitude|sympathy|envy|jealousy|determination|enthusiasm|despair|optimism|pessimism|insincerity|carelessness|diligence|laziness|greed|generosity|selfishness|modesty|humility|loyalty|disloyalty|obedience|disobedience|agreement|disagreement|argument|quarrel|conversation|discussion|communication|cooperation|competition|conflict|peace|violence|danger|safety|risk|threat|warning|complaint|criticism|praise|advice|suggestion|request|invitation|apology|excuse|greeting|farewell|message|news|rumour|rumor|joke|lie|secret|story|explanation|description|question|answer|reply)',
 'ordinary-household-object':r'(?:chair|table|spoon|bowl|fork|knife|bed|blanket|towel|shirt|dress|trousers|pants|skirt|socks|shoes|boots|hat|cap|coat|jacket|sweater|suit|umbrella|bag|box|basket|bucket|bottle|cup|plate|pot|pan|brush|comb|mirror|clock|watch|key|lock|door|window|wall|floor|roof|fence|gate|stairs|room|kitchen|bathroom|toilet|hall|curtain|lamp|candle|pillow|mattress|sheet|cushion|carpet|rug|shelf|drawer|cabinet|closet|wardrobe|desk|bench|stool|sofa|couch|furniture|clothing|clothes|linen|napkin|handkerchief|gloves|belt|tie|scarf|ribbon|button|zipper|needle|thread|rope|string|wire|chain|hook|hanger|peg|pin|nail|hammer|screwdriver|saw|scissors|spade|shovel|rake|broom|mop|cloth|rag|sponge|soap|detergent)',
 'ordinary-calendar-and-daily-life':r'(?:day|night|morning|afternoon|evening|noon|midnight|week|month|year|season|spring|summer|autumn|winter|birthday|holiday|anniversary|vacation|weekend|deadline|delay|time|moment|hour|minute|second|age|childhood|adulthood|youth|marriage|divorce|wedding|funeral|death|life|sleep|rest|leisure|recreation|work|employment|unemployment|salary|wage|income|expense|price|cost|payment|money|shopping|purchase|sale|gift|present|reward|punishment|journey|trip|travel|visit|arrival|departure|distance|direction|location|position|place|height|length|width|depth|size|shape|color|colour|brightness|darkness|beauty|ugliness|strength|weakness|speed|weight|quantity|amount|number|degree|quality|order|arrangement)',
}
SCOPED_TECHNICAL_HEADS={
 'math':r'(?:operator|ideal|kernel|space|function|set|group|vector|matrix|differential|tensor|distribution|variance|statistic|proof|form|algebra|geometry|calculus|topology|graph|edge|vertex|permutation|combination|homomorphism|morphism|dimension|limit|method|theorem|corollary|lemma|notation|axiom|conjecture|sequence|series|angle|polygon|triangle|circle|ellipse|parabola|hyperbola|polyhedron|sphere|intersection|union|quotient|remainder|divisor|multiple|factor|exponent|power|root|product|sum|difference|ratio|proportion|fraction|decimal|infinity|cardinality|bijection|surjection|injection)',
 'comp':r'(?:kernel|protocol|network|interface|port|socket|packet|address|buffer|register|cache|memory|stack|heap|thread|process|program|application|utility|file|directory|folder|path|link|pointer|reference|variable|constant|type|class|object|attribute|method|function|procedure|parameter|argument|statement|expression|instruction|code|bytecode|syntax|grammar|token|literal|keyword|identifier|module|package|library|framework|driver|handler|listener|event|callback|exception|interrupt|scheduler|parser|lexer|compiler|interpreter|assembler|debugger|disassembler|database|query|transaction|index|hash|checksum|encryption|decryption|authentication|authorization|certificate|signature|firewall|proxy|router|switch|server|client|host|terminal|console|shell|command|script|macro|spreadsheet|browser|cookie|session|database management system|character encoding|operating system|programming language)',
 'med':r'(?:syndrome|tumor|tumour|infection|inflammation|lesion|fracture|dislocation|hemorrhage|haemorrhage|edema|oedema|embolism|thrombosis|stenosis|occlusion|ischemia|ischaemia|necrosis|fibrosis|atrophy|hypertrophy|hyperplasia|metaplasia|dysplasia|malformation|anomaly|hypoplasia|agenesis|fistula|abscess|ulcer|cyst|polyp|calculi|calculus|contracture|adhesion|paralysis|palsy|paresis|spasm|convulsion|seizure|coma|syncope|vertigo|dizziness|nausea|vomiting|diarrhea|diarrhoea|constipation|dysphagia|dysarthria|aphasia|dyslexia|apraxia|agnosia|asthma|allergy|intolerance|addiction|dependence|poisoning|intoxication|shock|trauma|wound|burn|frostbite|surgery|operation|incision|excision|resection|amputation|transplantation|transfusion|infusion|injection|intubation|ventilation|resuscitation|rehabilitation|anaesthetic|anesthetic|analgesic|anticoagulant|antihypertensive|antidepressant|antipsychotic|sedative|hypnotic|stimulant|diuretic|laxative|antipyretic|antiemetic|antihistamine|antiseptic|disinfectant|vaccine)',
 'chem':r'(?:compound|element|atom|molecule|radical|bond|reaction|solution|solvent|solute|suspension|emulsion|colloid|precipitate|crystal|crystallization|distillation|sublimation|evaporation|condensation|polymer|monomer|oligomer|isomer|stereoisomer|enantiomer|tautomer|allotrope|catalyst|reagent|indicator|titration|oxidation|reduction|hydrolysis|electrolysis|fermentation|synthesis|decomposition|combustion|corrosion|adsorption|absorption|chelation|complex|ligand|orbital|valence|electronegativity|enthalpy|entropy|free energy|equilibrium|acid|base|salt|oxide|hydroxide|chloride|bromide|iodide|fluoride|sulfide|sulphide|sulfate|sulphate|sulfite|sulphite|nitrate|nitrite|carbonate|phosphate|silicate|borate|acetate|citrate|tartrate|oxalate)',
}
SCOPED_TECHNICAL_HEADS['anat']=r'(?:finger|toe|eye|ear|nose|mouth|tongue|lip|gum|tooth|teeth|palate|pharynx|larynx|throat|trachea|esophagus|oesophagus|stomach|intestine|bowel|colon|rectum|anus|liver|pancreas|gallbladder|kidney|bladder|ureter|urethra|prostate|ovary|uterus|womb|vagina|penis|testicle|scrotum|vulva|fallopian tube|breast|nipple|diaphragm|lung|heart|artery|vein|nerve|muscle|tendon|ligament|bone|cartilage|joint|vertebra|spine|skull|femur|tibia|fibula|humerus|radius|ulna|clavicle|scapula|sternum|rib|pelvis|coccyx|mandible|maxilla|sacrum|skin|tissue|follicle|gland|node|vessel|spleen|thymus|cerebrum|cortex|cerebellum|medulla|brainstem|spinal cord)'
SCOPED_TECHNICAL_HEADS['physics']=r'(?:energy|mass|acceleration|momentum|velocity|amplitude|frequency|wavelength|charge|potential|current|resistance|capacitance|inductance|impedance|admittance|conductance|conductivity|density|pressure|temperature|entropy|enthalpy|recoil|scattering|diffraction|interference|polarization|refraction|reflection|absorption|emission|fluorescence|phosphorescence|luminescence|resonance|oscillation|vibration|wave|particle|photon|electron|ion|atom|nucleon|hadron|boson|fermion|quark|neutrino|lepton|gluon|gravity|gravitation|force|magnetism|electricity|radiation|convection|conduction|conservation|viscosity|turbulence|hydrodynamics|aerodynamics|thermodynamics|electrodynamics|electrostatics|magnetostatics|relativity|mechanics|optics|acoustics|work)'
SCOPED_TECHNICAL_HEADS['eng']=r'(?:gear|bearing|shaft|piston|cylinder|valve|pump|turbine|compressor|boiler|engine|actuator|sensor|nozzle|rotor|stator|impeller|cam|sprocket|pulley|crankshaft|camshaft|flywheel|clutch|transmission|gearbox|brake|damper|spring|screw|bolt|nut|rivet|weld|gasket|seal|flange|coupling|joint|socket|plug|connector|terminal|electrode|insulator|conductor|relay|switch|breaker|fuse|motor|generator|transformer|rectifier|amplifier|oscillator|filter|inverter|converter|regulator|stabilizer|isolator|beam|column|truss|brace|bracket|frame|plate|rod|cable|hose|pipe|duct|tube|conduit|chamber|cavity|slot|groove|bore|port|aperture|orifice|outlet|inlet|vent|radiator|condenser|evaporator|heat exchanger|fan|blower|ventilator)'
SCOPED_TECHNICAL_HEADS['pharm']=r'(?:drug|medicine|tablet|capsule|pill|suppository|granule|solution|suspension|syrup|aerosol|inhaler|ointment|cream|gel|paste|plaster|patch|tincture|extract|infusion|decoction|lozenge|troche|drops|injection|ampoule|vial|preparation)'
SCOPED_TECHNICAL_HEADS['psy']=r'(?:autism|anorexia|bulimia|depression|anxiety|delusion|hallucination|neurosis|psychosis|mania|phobia|disorder|symptom|syndrome)'
SCOPED_TECHNICAL_HEADS['med']=SCOPED_TECHNICAL_HEADS['med'][:-1]+r'|disease|disorder|deficiency|dysfunction|defect|abnormality|symptom|therapy|treatment|diagnosis|prognosis|etiology|aetiology|pathogenesis|pathology|epidemiology|neurosis|psychosis|autism|aphasia|anorexia|bulimia|hypoxia|hypercapnia|hypocapnia|acidosis|alkalosis|hypoglycemia|hyperglycemia|hypotension|hypertension|tachycardia|bradycardia|arrhythmia|fibrillation|asystole|infarction|angina|aneurysm|hypothermia|hyperthermia|hypothyroidism|hyperthyroidism|neoplasm|malignancy)'
SCOPED_TECHNICAL_HEADS['biol']=r'(?:gene|genome|genotype|phenotype|allele|mutation|chromosome|chromatin|nucleus|nucleolus|ribosome|mitochondrion|mitochondria|chloroplast|vacuole|cytoplasm|cytosol|cytoskeleton|membrane|plasmid|transposon|intron|exon|codon|anticodon|nucleotide|nucleoside|protein|peptide|polypeptide|enzyme|coenzyme|substrate|metabolite|hormone|antigen|antibody|receptor|ligand|sperm|spermatozoa|ovum|ova|oocyte|embryo|fetus|foetus|blastocyst|zygote|mitosis|meiosis|metabolism|photosynthesis|respiration|digestion|circulation|excretion|secretion|fertilization|germination|pollination|grafting|taxonomy|phylogeny|ontogeny|homology|analogy|symbiosis|parasitism|commensalism|mutualism|amensalism|predation|competition|succession|adaptation|evolution|selection|speciation|extinction|biodiversity|ecosystem|biome|population|community|habitat|niche|trophic level|food chain|food web)'
SCOPED_TECHNICAL_HEADS['ling']=r'(?:phoneme|allophone|morpheme|allomorph|grapheme|syllable|phonology|phonetics|morphology|syntax|semantics|pragmatics|etymology|lexicology|lexicography|onomastics|sociolinguistics|psycholinguistics|neurolinguistics|typology|dialectology|prosody|intonation|accent|stress|pitch|tone|vowel|consonant|diphthong|triphthong|nasal|fricative|affricate|approximant|plosive|stop|tap|flap|trill|glide|bilabial|labiodental|dental|alveolar|postalveolar|retroflex|palatal|velar|uvular|pharyngeal|glottal|aspiration|palatalization|velarization|labialization|nasalization|devoicing|voicing|assimilation|dissimilation|elision|epenthesis|metathesis|syncope|apocope|aphaeresis|anaphora|cataphora|deixis|ellipsis|agreement|inflection|declension|conjugation|derivation|compounding|reduplication|clitic|affix|prefix|suffix|infix|circumfix)'
SCOPED_TECHNICAL_HEADS['gramm']=SCOPED_TECHNICAL_HEADS['ling'][:-1]+r'|noun|verb|adjective|adverb|pronoun|preposition|postposition|conjunction|interjection|determiner|article|quantifier|numeral|classifier|participle|gerund|infinitive|supine|subject|predicate|object|complement|modifier|clause|phrase|sentence|case|tense|aspect|mood|voice|person|number|gender|animacy|definiteness|transitivity|valency|nominative|accusative|genitive|dative|ablative|locative|instrumental|vocative|ergative|absolutive|active voice|passive voice|middle voice)'
FOOD_INGREDIENT_HEAD=r'(?:tea|coffee|sake|wine|beer|juice|milk|cream|flour|starch|rice|fish|meat|eggs|fruit|vegetables|beans|tofu|seaweed|konjac|natto|miso|dashi|wasabi|ramen|udon|soba|mochi|tempura|sukiyaki|yakitori|takoyaki|okonomiyaki|sashimi|amazake|umeshu|shochu|pork|beef|lamb|mutton|chicken|duck|turkey|ham|bacon|honey|sugar|salt|butter|margarine|mayonnaise|ketchup|mustard|vinegar|pepper|ginger|garlic|cinnamon|nutmeg|cloves|vanilla|cocoa|chocolate|custard|jam|jelly|marmalade|pickles|sauerkraut|kimchi|olives|caviar|roe|crabmeat|lobster|shrimp|prawns|clams|oysters|mussels|scallops|squid|octopus|tuna|salmon|sardines|anchovies|mackerel|herring|cod|trout|eel|sea bream|bonito|pollock|halibut|sole|flounder)'
GENERAL_HEADS['ordinary-human-role-or-description']=r'(?:person|people|man|woman|child|boy|girl|adult|infant|baby|teenager|elder|youngster|teacher|student|worker|farmer|merchant|buyer|seller|customer|neighbor|neighbour|friend|enemy|leader|follower|parent|mother|father|son|daughter|husband|wife|brother|sister|relative|ancestor|descendant|family member|acquaintance|stranger|visitor|guest|host|colleague|companion|partner|spectator|passenger|pedestrian|traveller|traveler|resident|inhabitant|citizen|volunteer|helper|supporter|opponent|competitor|participant|beginner|novice|expert|amateur|professional|outsider|insider|bystander|witness|victim|survivor|orphan|widow|widower|bachelor|bride|bridegroom)'
GENERAL_HEADS['ordinary-conduct-and-human-experience']=r'(?:abandonment|ability|action|activity|accomplishment|achievement|appearance|approach|artifice|attempt|betrayal|breakup|boredom|burden|character|characteristic|comfort|companionship|conduct|confusion|consent|consideration|convenience|courtesy|cruelty|deception|defiance|denial|devotion|discomfort|discretion|disgrace|disgust|dishonesty|dislike|disobedience|disrespect|distress|disturbance|earnestness|eloquence|endeavour|endeavor|enjoyment|exhaustion|expectation|expression|familiarity|favour|favor|frugality|generosity|gossip|grace|greed|grief|hardship|harmony|hesitation|humiliation|ignorance|imagination|impression|indifference|indiscretion|indolence|ingratitude|insight|insolence|interruption|judgement|judgment|laughter|loneliness|malice|manner|mercy|mood|nuisance|obstinacy|outlook|outward appearance|perseverance|personality|persistence|plan|politeness|predicament|preference|prejudice|preparation|prestige|procrastination|prudence|reassurance|reception|recognition|refusal|rejection|relief|reputation|resentment|retaliation|revenge|rivalry|rudeness|self-confidence|self-control|self-esteem|self-respect|sentiment|sincerity|skill|smugness|solitude|speech|suffering|tact|temper|temptation|tenderness|treachery|upbringing|virtue|weariness|welcome|wisdom|writing)'
GENERAL_HEADS['ordinary-body-and-grooming']=r'(?:head|face|hair|beard|moustache|mustache|eyebrow|eyelash|eye|ear|nose|mouth|tooth|teeth|tongue|lip|cheek|chin|neck|shoulder|arm|elbow|wrist|hand|palm|finger|fingernail|back|chest|waist|belly|stomach|hip|leg|knee|ankle|foot|feet|toe|toenail|skin|voice|breath|sweat|tear)'
GENERAL_HEADS['ordinary-weather-and-surroundings']=r'(?:weather|rain|snow|wind|sunshine|sunlight|shade|shadow|sky|water|air|ground|earth|soil|sand|mud|dust|stone|rock|wood|fire|smoke|ash|ice|frost|dew)'
COMMON_QUALITIES=r'(?:happy|sad|angry|afraid|fearful|joyful|sorrowful|cheerful|gloomy|anxious|worried|concerned|calm|peaceful|serene|relaxed|tense|nervous|excited|bored|interested|curious|eager|enthusiastic|confident|courageous|brave|timid|shy|bashful|proud|humble|modest|ashamed|embarrassed|regretful|remorseful|grateful|thankful|hopeful|optimistic|pessimistic|desperate|lonely|solitary|friendly|unfriendly|kind|unkind|gentle|harsh|cruel|generous|selfish|honest|dishonest|sincere|insincere|loyal|disloyal|faithful|unfaithful|patient|impatient|careful|careless|diligent|lazy|hardworking|energetic|tired|exhausted|sleepy|hungry|thirsty|satisfied|dissatisfied|content|discontented|pleased|displeased|delighted|disappointed|surprised|astonished|amazed|shocked|confused|puzzled|perplexed|bewildered|uncertain|unsure|certain|sure|small|large|big|little|tiny|huge|enormous|immense|great|long|short|tall|high|low|deep|shallow|wide|narrow|thick|thin|heavy|light|fast|slow|quick|swift|rapid|early|late|old|young|new|fresh|ancient|modern|recent|good|bad|excellent|poor|fine|wonderful|terrible|awful|beautiful|ugly|pretty|lovely|attractive|unattractive|handsome|plain|strong|weak|powerful|feeble|sturdy|fragile|delicate|soft|hard|rough|smooth|sharp|blunt|hot|cold|warm|cool|bright|dark|clear|cloudy|clean|dirty|neat|messy|tidy|untidy|wet|dry|full|empty|open|closed|loose|tight|free|busy|available|unavailable|ready|unready|simple|complex|complicated|easy|difficult|hard|possible|impossible|necessary|unnecessary|useful|useless|important|unimportant|valuable|worthless|cheap|expensive|safe|dangerous|secure|insecure|comfortable|uncomfortable|convenient|inconvenient|pleasant|unpleasant|enjoyable|unenjoyable|funny|amusing|interesting|boring|exciting|dull|strange|odd|unusual|ordinary|normal|common|rare|frequent|infrequent|regular|irregular|constant|variable|stable|unstable|steady|unsteady|reliable|unreliable|dependable|undependable|responsible|irresponsible|reasonable|unreasonable|sensible|foolish|wise|stupid|clever|smart|intelligent|unintelligent)'
SPECIALIST_WORDS=r'\b(?:quantum|nuclear|molecular|atomic|genetic|chromosomal|neuronal|clinical|diagnostic|pathological|physiological|anatomical|mathematical|statistical|geometric|algebraic|trigonometric|logarithmic|differential|integral|chemical|biochemical|electrical|electromagnetic|thermal|acoustic|optical|computer|computing|computational|digital|binary|software|programming|database|algorithm|algorithmic|operating system|financial|fiscal|monetary|bond|stock|insurance|contract|tax|legal|statutory|constitutional|judicial|parliamentary|legislative|military|imperial|dynasty|era|species|genus|cultivar|variety|cell|gene|chromosome|enzyme|protein|hormone|disease|syndrome|cancer)\b'


ORDINARY_MODIFIERS=set('a an the deep profound strong weak personal mutual close distant common everyday ordinary daily unexpected sudden pleasant unpleasant private public social emotional mental physical simple complex difficult easy great little small large big round square soft hard new old warm cold clean dirty white black red blue green winter summer spring autumn morning evening early late first last happy sad good bad long short empty full wooden cotton woolen paper metal glass plastic kitchen dining bath bed hand household'.split())
ORDINARY_MODIFIERS.update('main principal total final initial rare unlikely registered unregistered bicycle cycling walking straw mock ceremonial food low bottom-tier top-tier extra supplementary intense slight faint vague bitter friendly hostile honest dishonest regrettable regretted romantic unromantic'.split())
GENERAL_HEADS['ordinary-conduct-and-everyday-results']=r'(?:conduct|deed|act|action|doing|manner|mannerism|gesture|glance|behaviour|behavior|appearance|physique|expression|look|gaze|glare|wink|grin|laugh|smile|kiss|embrace|affection|intimacy|romance|flirtation|revenge|grudge|envy|resentment|relief|comfort|distress|hardship|adversity|misfortune|fortune|prosperity|opulence|poverty|wealth|result|outcome|output|matter|security|condolences|sympathy|greeting|congratulations|goodbye|effigy|doll|figure|sword|trip|tour|hike|outing|excursion|get-together|occurrence|routine|recollection|quarrel|squabble|rumour|rumor|hearsay|gossip|reputation|popularity|celebrity|fame|talent|genius|wisdom|virtue|knowledge|counsel|advice|warning|notice|ultimatum|criticism|condemnation|encouragement|determination|perseverance|patience|thoroughness|diligence|carelessness|negligence|obstinacy|insincerity|sincerity|enthusiasm|obsession|fixation|delight|pleasure|jubilation|exultation|sorrow|bitterness|vexation|chagrin|loathing|abhorrence|dislike|disgust)'
SCOPED_TECHNICAL_HEADS['biol']=SCOPED_TECHNICAL_HEADS['biol'][:-1]+r'|organelle|plasticity|adhesion|dyshesion)'
SCOPED_TECHNICAL_HEADS['physics']=SCOPED_TECHNICAL_HEADS['physics'][:-1]+r'|interaction|coupling|cross section)'
SCOPED_TECHNICAL_HEADS['math']=SCOPED_TECHNICAL_HEADS['math'][:-1]+r'|hypersurface|test|G-test)'
SCOPED_TECHNICAL_HEADS['comp']=SCOPED_TECHNICAL_HEADS['comp'][:-1]+r'|mouse|conversion|color system|colour system|typesetting system|document preparation system)'
SCOPED_TECHNICAL_HEADS['anat']=SCOPED_TECHNICAL_HEADS['anat'][:-1]+r'|ulna|urethral meatus|levator ani|levator anus muscles)'
for alias,scope in {'engr':'eng','civeng':'eng','electr':'eng','elec':'eng','geom':'math','stat':'math','logic':'math','surg':'med','dent':'med','pathol':'med','vet':'med','biochem':'biol','genet':'biol','physiol':'biol','ecol':'biol','psych':'psy','psyanal':'psy'}.items():
 SCOPED_TECHNICAL_HEADS[alias]=SCOPED_TECHNICAL_HEADS[scope]
CULINARY_PREPARATIONS=r'(?:cooked|boiled|steamed|fried|stir-fried|roasted|grilled|baked|braised|pickled|salted|smoked|blanched|seasoned|restructured|marinated)'
CULINARY_HEADS=r'(?:rice|meat|steak|fish|chicken|shellfish|vegetables|seaweed|nori|tofu|udon|mushi|meal|dish|custard|paste|roll|salt|tongue|mustard|pickles)'
STRUCTURAL_BRIDGE_TYPES=r'(?:girder|beam|truss|cantilever|arch|suspension|cable-stayed|bascule|lift|swing|floating|tied-arch) bridge'
FOOD_MODIFIERS=set('a an the Japanese Chinese Korean French Italian Indian Thai Vietnamese sweet sour spicy hot cold red white green black brown yellow blue dark light fresh dried cooked boiled steamed fried deep-fried stir-fried roasted grilled baked braised pickled salted smoked marinated seasoned powdered fermented raw minced ground chopped sliced shredded thick thin chicken beef pork lamb mutton duck turkey fish seafood noodle bean rice wheat barley rye wholemeal whole-wheat wholegrain soy soybean cream creamy tomato potato vegetable fruit egg cheese chocolate cocoa honey sugar sugar-free butter peanut coconut lemon orange vanilla cherry strawberry banana apple custard jelly jam sponge layer birthday pound poppy seed sesame curry miso clear instant traditional regional local homemade home-made home-cooked'.split())
GENERIC_HUMAN=r'(?:person|people|man|woman|child|boy|girl|someone|worker|friend|parent|mother|father|husband|wife)'
ORDINARY_HUMAN_PREDICATE=r'(?:is|are|was|were|has|have|had|does|do|takes|take|gets|get|gives|give|likes|like|wants|want|needs|need|lives|live|works|work|knows|know|feels|feel|thinks|think|sees|see|helps|help|can|cannot|always|never|frequently|often|usually|tends|tend)'
ROLE_SPECIALIST=r'\b(?:Buddhist|Buddhism|Shinto|Christian|Islamic|shaman|miko|priest|clergyman|monk|ordination|ritual|court|imperial|dynasty|Edo|Meiji|Heian|Tokugawa)\b'
ORDINARY_ACTIVITIES=r'(?:laughing|crying|smiling|eating|drinking|sleeping|walking|sitting|standing|looking|hearing|telling|saying|feeling|waiting|helping|asking|wanting|loving|hating|washing|buying|selling|paying|meeting|leaving|entering|arriving|bringing|sending|receiving|greeting|resting|reading|writing|carrying|wearing|holding|sharing|giving|taking|keeping|losing|forgetting|remembering|thinking|worrying|hoping|trying|refusing|avoiding|allowing|preparing|cooking|covering)'
FORMAL_SPECIALIST=r'\b(?:hypothesis|thermodynamics|enthalpy|taxon|logical|theorem|axiom|statistic|equation|calculus|algebra|geometry|quantum|neural|nuclear|cardinality|coefficient|derivative|integral|infinity|smegma|ovum|ovary|cerebral|artery|vein|serum|urethra|chromosome|cytoplasm|mitosis|meiosis|tectonic|voltage|capacitance|inductance|impedance|depreciation|receivable|dividend|securities|futures|accounting)\b'
RELIGIOUS_DOCTRINE=r'\b(?:rebirth|reincarnation|karma|enlightenment|salvation|nirvana|pilgrimage|ritual|precept|ordination|prayer|faith|immortality)\b'

def ordinary_modifier_prefix(prefix):
 return all(w.lower() in ORDINARY_MODIFIERS for w in prefix.strip().split())

def suggested_rules(glosses,fields=(),source='JMdict',pos=(),misc=()):
 """Bind rules to explicit sense definitions; POS/field labels alone never grant categories; paired concrete semantic heads are required."""
 found=[]
 for gloss in glosses:
  g=gloss.strip()
  if (source=='JMdict' and not fields and not re.search(SPECIALIST_WORDS+'|'+ROLE_SPECIALIST,g,re.I)
      and not re.search(r'\b[A-Z][a-z]+',g) and not re.search(BINOMIAL,g)
      and re.match(r'^(?:(?:a|an|the) )?'+GENERIC_HUMAN+r' who '+ORDINARY_HUMAN_PREDICATE+r'\b',g)):
   found.append(('general','explicit-generic-human-description-with-ordinary-predicate',g))
  if (re.match(r'^(?:'+CULINARY_PREPARATIONS+r'\b.*\b'+CULINARY_HEADS+r'\b|(?:fish|chicken|shellfish|vegetables|seaweed)\b.*\b'+CULINARY_PREPARATIONS+r'\b)',g,re.I)
      or ('food' in fields and re.search(r'\b'+CULINARY_HEADS+r'(?:s)?(?:$|\s+\()',g,re.I))
      or re.search(r'\b(?:edible seaweed|rice meal|rice-bran paste|custard dish|dish consisting of)\b',g,re.I)):
   found.append(('food','explicit-culinary-preparation-or-edible-definition',g))
  if re.fullmatch(r'evaporating dish',g,re.I):found.append(('technical','explicit-chemical-laboratory-equipment',g))
  if re.fullmatch(r'kanji ["“][^"”]+["”] radical(?: (?:at|on) (?:left|right|top|bottom|outside|inside))?',g,re.I):
   found.append(('technical','explicit-writing-system-radical-description',g))
  bio=re.search(r'\b'+BIO_HEADS+r'\s+'+BINOMIAL,g)
  explicit_taxon=re.search(r'\b(?:species|genus|subspecies|cultivar|variety) of\b',g)
  bio_subject=bio and not re.search(r'\b(?:at|in|of|from|by|under|near|for|with)\b',g[:bio.start()],re.I)
  if (explicit_taxon or bio_subject) and not re.search(r'\b(?:dried|cooked|salted|smoked|pickled|roasted|fried|powdered)\b',g) and not set(fields).intersection({'comp','physics','chem','math','ling','gramm'}):
   found.append(('organism','biological-type-or-binomial-and-biological-head',g))
  # Head is the defined object, not a mentioned context or a metaphor's object.
  for category,head in HEADS.items():
   primary=g.split('(')[0].strip()
   m=re.search(r'\b'+head+r'(?:s)?(?=$|\s+(?:whose|that)\b)',primary,re.I)
   if m and not re.match(r'(?:to|leaving|abandoning|boarding|entering|driving|riding|operating|repairing|building|maintaining|protecting|guarding|carrying|landing|selling|buying|eating|drinking|cooking|preparing|distributing)\b',g) and not (category=='transport' and re.search(r'\b(?:paper|toy|model|miniature)\b',primary,re.I)) and not re.search(r'\b(?:at|in|of|from|by|under|near|for|with|who|which|that)\b',g[:m.start()],re.I):
    found.append((category,'explicit-'+category+'-semantic-head',g))
   if category in ('technical','food') and re.search(r'\('+head+r'\)',g,re.I):found.append((category,'explicit-parenthetical-'+category+'-type',g))
   if category=='astronomy' and re.search(r'\((?:(?:no longer recognized|Chinese) )?'+head+r'\)',g,re.I):found.append((category,'parenthetical-astronomical-object-type',g))
  if source=='JMnedict' and re.search(r'\('+PLACE_TYPES+r'\)',g,re.I):found.append(('place','named-target-explicit-geographical-type',g))
  if re.search(r'\b(?:prayer|ritual|ceremony|precept|ordination|pilgrimage)\b',g,re.I) and re.search(r'\b(?:Buddhist|Shinto|Christian|religious)\b',g,re.I) and not re.search(r'\b(?:study|separation|center|centre|school|book|temple|shrine|sect)\b',g,re.I):found.append(('religion','explicit-religious-ritual-or-precept',g))
  if re.search(r'\((?:[^)]*\b)?(?:judo|sumo|soccer|baseball|tennis|karate|wrestling)\b[^)]*\)',g,re.I) and re.search(r'\b(?:throw|hold|kick|technique|pitch|foul|stance|serve|rank)\b',g,re.I) and not re.match(r'to\b',g):found.append(('sports','explicit-sport-and-technique-type',g))
  primary=g.split('(')[0].strip()
  for scope,head in SCOPED_TECHNICAL_HEADS.items():
   if scope in fields:
    m=re.search(r'\b'+head+r'(?:s)?$',primary,re.I)
    if m and not re.search(r'\b(?:of|from|by|at|in|for|with|who|which|that)\b',primary[:m.start()],re.I):found.append(('technical','closed-'+scope+'-semantic-head-with-source-sense-scope',g))
  if 'food' in fields:
   m=re.search(r'\b'+FOOD_INGREDIENT_HEAD+r'$',primary,re.I)
   if m and not re.search(r'\b(?:of|from|by|at|in|for|with|who|which|that)\b',primary[:m.start()],re.I) and not re.search(BINOMIAL,g):found.append(('food','explicit-edible-ingredient-head-with-food-sense-scope',g))
  if set(fields).intersection({'MA','sumo','sports','baseb'}) and re.fullmatch(r'(?:black|red|brown|white|yellow|green|blue) belt',primary,re.I):
   found.append(('sports','explicit-martial-arts-belt-rank',g))
  if re.fullmatch(STRUCTURAL_BRIDGE_TYPES,primary,re.I):
   found.append(('technical','explicit-structural-engineering-bridge-type',g))
   found=[v for v in found if not (v[0]=='facility' and v[2]==g)]
  if (not set(fields)-{'Buddh','Shinto','Christn','art','music','vidg','internet','food'}
      and not re.search(SPECIALIST_WORDS+'|'+FORMAL_SPECIALIST,g,re.I) and not re.search(BINOMIAL,g)
      and not (set(fields).intersection({'Buddh','Shinto','Christn'}) and re.search(RELIGIOUS_DOCTRINE,g,re.I))):
   if any(p.startswith('adj-') for p in pos) and re.fullmatch(r'(?:(?:very|extremely|quite|rather|somewhat|slightly|highly|deeply|completely|utterly|totally|absolutely|relatively|comparatively|fairly|moderately) )?'+COMMON_QUALITIES,g,re.I):found.append(('general','controlled-ordinary-quality-or-feeling',g))
   primary=g.split('(')[0].strip()
   for family,head in GENERAL_HEADS.items():
    if 'food' in fields:continue
    if family in ('ordinary-body-and-grooming','ordinary-weather-and-surroundings') and '(' in g:continue
    m=re.search(r'\b'+head+r'(?:s)?$',primary,re.I)
    if m and ordinary_modifier_prefix(primary[:m.start()]) and not re.search(r'\b[A-Z][a-z]+',primary):
     found.append(('general',family,g))
   if not re.search(r'\b[A-Z][a-z]+|'+ROLE_SPECIALIST,g):
    for family in ('ordinary-mental-and-social-abstraction','ordinary-conduct-and-human-experience'):
     if re.match(r'^(?:(?:a|an|the) )?'+GENERAL_HEADS[family]+r' (?:of|to|in|for|with|that|which|when|about)\b',g,re.I):
      found.append(('general','explicit-ordinary-experience-with-defined-complement',g))
    if re.match(r'^'+ORDINARY_ACTIVITIES+r' (?:a|an|the|one\x27s|someone|something|oneself|your|his|her|their|each|up|down|in|out|off|on|at|for|to|of|from|with|without|about|that|whether|how|when)\b',g,re.I):
     found.append(('general','explicit-everyday-activity-with-literal-object-or-complement',g))
  if not fields and re.fullmatch(r'to '+EVERYDAY+r'(?: (?:at|for|with|someone|something|angrily|happily|sadly|loudly|quietly|up|down|off|away|out))*',g):found.append(('general','controlled-everyday-action-definition',g))
 # A synonym naming food is insufficient when its grammar is an action,
 # an idiom, slang about the body, or the name of an organism.
 cleaned=[]
 for c,r,g in found:
  if c=='food':
   primary=g.split('(')[0].strip()
   if set(misc).intersection({'vulg','sl','proverb','id'}) or re.search(r'\b(?:species|genus|subspecies|cultivar) of\b',g):continue
   if re.match(r'^(?:to |\w+ing (?:in|on|with|of|for) )',primary,re.I):continue
   if r=='explicit-food-semantic-head':
    m=re.search(r'\b'+HEADS['food']+r'(?:s)?$',primary,re.I)
    if m and any(v.lower() not in FOOD_MODIFIERS for v in primary[:m.start()].split()):continue
  cleaned.append((c,r,g))
 found=[('product','explicit-named-computing-product-type',g) if c=='technical' and re.search(r'\((?:operating system|software|application|browser)\)',g,re.I) and ('tradem' in misc or re.match(r'[A-Z][\w+.-]*(?: [A-Z][\w+.-]*)? \(',g)) else (c,r,g) for c,r,g in cleaned]
 return sorted(set(found))

def surface(s):
 import unicodedata
 return unicodedata.normalize('NFKC',s)

def norm(s):
 import unicodedata
 s=unicodedata.normalize('NFKC',s)
 return ''.join(chr(ord(c)-96) if 'ァ'<=c<='ヶ' else c for c in s)
def inspect_rows(rows):
 docs={};rawentries={};entities={};valid=[];failures=[]
 for row in rows:
  p=row['path']
  if p not in docs:
   data=pathlib.Path(p).read_bytes();h=hashlib.sha256(data).hexdigest()
   if h!=row['sha256']:raise ValueError('Raw document hash mismatch: '+p)
   text=gzip.decompress(data).decode('utf-8')
   entities[p]=dict(re.findall(r'<!ENTITY\s+([\w-]+)\s+"([^"]*)"\s*>',text))
   ids={r['body']['entryId'] for r in rows if r['path']==p}
   rawentries[p]={m[1]:m[0] for m in re.finditer(r'<entry>\s*<ent_seq>(\d+)</ent_seq>.*?</entry>',text,re.S) if m[1] in ids};docs[p]=h
  raw=rawentries[p].get(row['body']['entryId'])
  if not raw:failures.append((row['id'],'raw-entry-absent'));continue
  e=ET.fromstring(re.sub(r'&([\w-]+);',lambda m:m[1] if m[1] in entities[p] else m[0],raw))
  written_kana=any(surface(r.findtext('reb',''))==row['surface'] for r in e.findall('r_ele'))
  declared_spelling=any(surface(v.text)==row['surface'] for v in e.findall('k_ele/keb'))
  if not (written_kana or declared_spelling):failures.append((row['id'],'surface-mismatch'));continue
  rs=[r for r in e.findall('r_ele') if norm(r.findtext('reb',''))==row['reading'] and
      (surface(r.findtext('reb',''))==row['surface'] or (declared_spelling and not r.findall('re_nokanji') and
       (not r.findall('re_restr') or row['surface'] in [surface(v.text) for v in r.findall('re_restr')])))]
  if not rs:failures.append((row['id'],'reading-or-restriction-mismatch'));continue
  source=row['body']['source'];unit=None;constraints={'re_restr':[[v.text for v in r.findall('re_restr')] for r in rs],'re_nokanji':[bool(r.findall('re_nokanji')) for r in rs],'publishedKanaLemma':written_kana};fields=[];pos=[];misc=[]
  if source=='JMdict':
   m=re.search(r'sense-(\d+)$',row['body'].get('evidence',''))
   if not m:failures.append((row['id'],'sense-index-absent'));continue
   n=int(m[1]);senses=e.findall('sense')
   if not 1<=n<=len(senses):failures.append((row['id'],'sense-index-invalid'));continue
   unit=senses[n-1];ks=[surface(v.text) for v in unit.findall('stagk')];rr=[norm(v.text) for v in unit.findall('stagr')]
   if ks and row['surface'] not in ks or rr and row['reading'] not in rr:failures.append((row['id'],'sense-restriction-mismatch'));continue
   glosses=[v.text for v in unit.findall('gloss')];fields=[v.text for v in unit.findall('field')];misc=[v.text for v in unit.findall('misc')]
   for prior in senses[:n]:
    if prior.findall('pos'):pos=[v.text for v in prior.findall('pos')]
   constraints['pos']=pos;constraints['misc']=misc;constraints.update(sense=n,stagk=ks,stagr=rr)
  else:
   n=int(row['target'].split(':')[-1]);trans=e.findall('trans')
   if not 0<=n<len(trans):failures.append((row['id'],'translation-index-invalid'));continue
   unit=trans[n];glosses=[v.text for v in unit.findall('trans_det')];constraints.update(translation=n,nameTypes=[v.text for v in unit.findall('name_type')])
  matches=suggested_rules(glosses,fields,source,pos,misc)
  valid.append(dict(candidateId=row['id'],reading=row['reading'],surface=row['surface'],evidenceId=row['evidenceId'],documentId=row['document_id'],sha256=row['sha256'],target=row['target'],source=source,quotation=raw,glosses=glosses,fields=fields,constraints=constraints,suggestions=[{'category':cat,'rule':rule,'matchedGloss':g,'method':'source_review'} for cat,rule,g in matches]))
 return valid,failures

def main():
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--recommendations');p.add_argument('--unresolved-batches');args=p.parse_args()
 rows=json.loads(pathlib.Path(args.input).read_text());valid,failures=inspect_rows(rows)
 counts=collections.Counter();unique=collections.defaultdict(set)
 for case in valid:
  for cat in {s['category'] for s in case['suggestions']}:counts[cat]+=1;unique[cat].add(case['candidateId'])
 chosen=[];seen=set()
 # Deterministic category-balanced inspection with explicit known false-positive regressions.
 negatives={'片歌','エクソア','鈴鏡','吊橋効果','神明造','こまいぬ','カミナリ族','巻き込み事故','自転車旅行','相撲に勝って勝負に負ける','宗学','祭政分離','関東十八檀林','非代替性トークン','テネシン','無記名債権','火口原','恒星年','貸付信託','不変量','親の心子知らず','Linux'}
 for c in valid:
  if c['surface'] in negatives and c['candidateId'] not in seen:chosen.append(c);seen.add(c['candidateId'])
 for category in ['organism','astronomy','facility','place','transport','religion','sports','technical','food','general']:
  n=0
  for c in valid:
   if c['candidateId'] not in seen and any(s['category']==category for s in c['suggestions']):chosen.append(c);seen.add(c['candidateId']);n+=1
   if n>=8:break
 for c in valid:
  if len(chosen)>=100:break
  if c['candidateId'] not in seen and c['suggestions']:chosen.append(c);seen.add(c['candidateId'])
 result={'schemaVersion':1,'purpose':'Read-only original XML semantic audit, not independent gold or production decisions','inputCandidates':len({r['id'] for r in rows}),'rawMeaningUnitsChecked':len(valid),'rawConstraintFailures':failures,'suggestedCandidateCounts':{k:len(v) for k,v in unique.items()},'totalSuggestedCandidates':len(set().union(*unique.values())),'route':'source_review; independent inference precision gate remains mandatory','rules':[{'category':k,'predicate':v,'negativeGuards':'Head must be defined subject; reject context prepositions and infinitive action metaphors'} for k,v in HEADS.items()]+[{'category':'organism','predicate':'Explicit species/genus/subspecies/cultivar/variety of, OR exact binomial with controlled biological semantic head','negativeGuards':'Boolean operator, Kofun period, Japanese poetry are not biological head types'},{'category':'place','predicate':'Named JMnedict translation unit explicitly gives geographical type in parentheses','negativeGuards':'Bare place tag and inferred kanji suffix are insufficient'},{'category':'religion','predicate':'Explicit religious tradition plus ritual/prayer/precept/ordination/pilgrimage; no study/separation/building/sect head'},{'category':'sports','predicate':'Explicit sport in parenthetical qualifier plus named technique, throw, hold, kick, pitch, stance, serve or rank; no infinitive metaphor'},{'category':'general','predicate':'Exact controlled everyday-action definition; fields may veto, never grant classification'}],'selectionSha256':hashlib.sha256(json.dumps([c['candidateId'] for c in chosen],separators=(',',':')).encode()).hexdigest(),'cases':chosen,'independentGoldCases':0}
 result['closedOrdinarySemanticFamilies']=GENERAL_HEADS
 result['scopedTechnicalSemanticHeads']=SCOPED_TECHNICAL_HEADS
 result['generalCoverageCeiling']={'rawVerifiedJMdictCandidates':len({c['candidateId'] for c in valid if c['source']=='JMdict'}),'atLeastOneFieldFreeSense':len({c['candidateId'] for c in valid if c['source']=='JMdict' and not c['fields']}),'fieldFreeExplicitNonSpecialistLowercaseGloss':len({c['candidateId'] for c in valid if c['source']=='JMdict' and not c['fields'] and any(g and not re.search(SPECIALIST_WORDS,g,re.I) and not re.search(BINOMIAL,g) and not re.search(r'\b[A-Z][a-z]+',g) for g in c['glosses'])}),'warning':'These are inspection candidate ceilings, not general category assignments.'}
 result['coreCoverageLimits']={'generalMinimum':10000,'technicalMinimum':1500,'foodMinimum':250,'note':'These thresholds remain unchanged; candidate suggestion counts do not prove publication eligibility.'}
 result['rawInputSha256']=hashlib.sha256(pathlib.Path(args.input).read_bytes()).hexdigest()
 if args.unresolved_batches:
  directory=pathlib.Path(args.unresolved_batches);directory.mkdir(parents=True,exist_ok=True)
  residual=[c for c in valid if c['source']=='JMdict' and not c['suggestions']]
  files=[]
  for start in range(0,len(residual),100):
   path=directory/('batch-%03d.json'%(start//100+1))
   path.write_text(json.dumps({'schemaVersion':1,'purpose':'Raw-source inspection queue, no inferred category assigned','cases':residual[start:start+100]},ensure_ascii=False,indent=2)+'\n')
   files.append({'file':path.name,'cases':len(residual[start:start+100]),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
  (directory/'manifest.json').write_text(json.dumps({'schemaVersion':1,'inputSha256':result['rawInputSha256'],'meaningUnits':len(residual),'files':files,'note':'Read only these current manifest files; older trailing batch files may belong to earlier audit runs.'},indent=2)+'\n')
 if args.recommendations:
  recommendations=[c for c in valid if c['suggestions']]
  pathlib.Path(args.recommendations).write_text(json.dumps({'schemaVersion':1,'route':'source_review','productionApplied':False,'independentGoldCases':0,'recommendations':recommendations},ensure_ascii=False,indent=2)+'\n')
 pathlib.Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('rawMeaningUnitsChecked','suggestedCandidateCounts','totalSuggestedCandidates')}));print('inspection cases',len(chosen))
if __name__=='__main__':main()
