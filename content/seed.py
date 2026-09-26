"""Content seed — the single source of truth for MaatraVani's bundled data.

Run scripts/emit_content.py to (re)generate the JSON files under content/
from these Python literals. Keeping the seed here means the data is diffable
in review and the JSON on disk is always exactly what the loader reads.

Contents:
  * FLN_OUTCOMES  - a representative subset of NIPUN Bharat foundational
                   literacy & numeracy outcomes, reworded for this PoC.
  * DEMO_SENTENCES - the fixed Hindi utterances used in the hackathon demo.
  * LEXICON       - the verified Hindi-Santali vocabulary. Entries are added
                    ONLY when verifiable against a public source; see the
                    'source' field on each entry and PROVENANCE.md.
"""

FLN_OUTCOMES = {
    "meta": {
        "name": "NIPUN Bharat FLN learning outcomes (representative subset)",
        "note": (
            "Reworded, grade-appropriate outcomes aligned to the NIPUN Bharat "
            "foundational literacy & numeracy framework for this proof of "
            "concept. A representative subset assembled for the demo, not an "
            "official copy of the Lakshya documents."
        ),
        "subjects": ["Foundational Literacy", "Foundational Numeracy"],
        "grades": ["1", "2", "3"],
        "topics": [
            "Animals", "Colours", "Numbers 1-10", "Family",
            "Fruits and Vegetables", "Body Parts", "Classroom Objects",
        ],
    },
    "outcomes": [
        {
            "id": "L1.1", "grade": "1", "subject": "Foundational Literacy",
            "text": "Student identifies and names common animals, objects and people in the surroundings.",
            "topics": ["Animals", "Family", "Classroom Objects"],
        },
        {
            "id": "L1.2", "grade": "1", "subject": "Foundational Literacy",
            "text": "Student recognizes letters and reads simple two-letter and three-letter words aloud.",
            "topics": ["Animals", "Colours"],
        },
        {
            "id": "L1.3", "grade": "1", "subject": "Foundational Literacy",
            "text": "Student listens to a short story and answers simple questions about it.",
            "topics": ["Animals", "Family"],
        },
        {
            "id": "N1.1", "grade": "1", "subject": "Foundational Numeracy",
            "text": "Student counts orally from 1 to 10 using concrete objects.",
            "topics": ["Numbers 1-10"],
        },
        {
            "id": "N1.2", "grade": "1", "subject": "Foundational Numeracy",
            "text": "Student compares groups of objects using more, less and equal.",
            "topics": ["Numbers 1-10", "Fruits and Vegetables"],
        },
        {
            "id": "L2.1", "grade": "2", "subject": "Foundational Literacy",
            "text": "Student reads short sentences aloud with understanding and matches them to pictures.",
            "topics": ["Animals", "Colours", "Body Parts"],
        },
        {
            "id": "L2.2", "grade": "2", "subject": "Foundational Literacy",
            "text": "Student identifies and names common animals and describes them in one line.",
            "topics": ["Animals"],
        },
        {
            "id": "L2.3", "grade": "2", "subject": "Foundational Literacy",
            "text": "Student writes two to three simple words from dictation.",
            "topics": ["Animals", "Fruits and Vegetables"],
        },
        {
            "id": "N2.1", "grade": "2", "subject": "Foundational Numeracy",
            "text": "Student reads and writes numbers up to 50.",
            "topics": ["Numbers 1-10"],
        },
        {
            "id": "N2.2", "grade": "2", "subject": "Foundational Numeracy",
            "text": "Student adds and subtracts single-digit numbers using objects.",
            "topics": ["Numbers 1-10"],
        },
        {
            "id": "L3.1", "grade": "3", "subject": "Foundational Literacy",
            "text": "Student reads a grade-level paragraph fluently and answers who/what/where questions.",
            "topics": ["Animals", "Family"],
        },
        {
            "id": "L3.2", "grade": "3", "subject": "Foundational Literacy",
            "text": "Student writes two to three connected sentences about a familiar topic.",
            "topics": ["Animals", "Fruits and Vegetables"],
        },
        {
            "id": "N3.1", "grade": "3", "subject": "Foundational Numeracy",
            "text": "Student solves simple daily-life word problems involving addition.",
            "topics": ["Numbers 1-10"],
        },
        {
            "id": "N3.2", "grade": "3", "subject": "Foundational Numeracy",
            "text": "Student identifies simple shapes in the surroundings and counts their sides.",
            "topics": ["Classroom Objects"],
        },
    ],
}

DEMO_SENTENCES = {
    "meta": {
        "name": "Demo utterances (Hindi)",
        "note": (
            "The fixed set of classroom utterances used across the demo, the "
            "tests and the latency measurements. Keep the wording stable - "
            "the measured numbers in DEMO.md refer to exactly these lines."
        ),
    },
    "sentences": [
        {
            "id": "greeting",
            "hi": "नमस्ते बच्चों।",
            "latin": "namaste bachchon.",
            "category": "greetings",
            "purpose": "opening a class",
        },
        {
            "id": "topic-intro",
            "hi": "आज हम जानवरों के नाम सीखेंगे।",
            "latin": "aaj ham jaanvaron ke naam seekhenge.",
            "category": "classroom",
            "purpose": "topic introduction - the flagship demo utterance",
        },
        {
            "id": "cow-milk",
            "hi": "गाय हमें दूध देती है।",
            "latin": "gaay hamein doodh deti hai.",
            "category": "animals",
            "purpose": "vocabulary sentence",
        },
        {
            "id": "dog-guard",
            "hi": "कुत्ता हमारी रखवाली करता है।",
            "latin": "kutta hamaari rakhwaali karta hai.",
            "category": "animals",
            "purpose": "vocabulary sentence",
        },
        {
            "id": "cat-milk",
            "hi": "बिल्ली दूध पीती है।",
            "latin": "billi doodh peeti hai.",
            "category": "animals",
            "purpose": "vocabulary sentence",
        },
        {
            "id": "call-and-repeat",
            "hi": "चलो, अब मिलकर जानवरों के नाम बोलते हैं।",
            "latin": "chalo, ab milkar jaanvaron ke naam bolte hain.",
            "category": "classroom",
            "purpose": "closing activity",
        },
        {
            "id": "mesh-homework",
            "hi": "कल गणित की कॉपी साथ लाईये।",
            "latin": "kal ganit ki kaupi saath laaiye.",
            "category": "mesh",
            "purpose": "the offline-mesh demo message (homework reminder)",
        },
    ],
}

LEXICON = {
    "meta": {
        "name": "MaatraVani verified classroom lexicon (Hindi - Santali)",
        "version": "0.2",
        "note": (
            "Entries are added only when a team member could verify the "
            "Santali word against a public source, and only when the Ol Chiki "
            "bytes we type here were checked against the machine-extracted "
            "evidence in content/vocabulary/evidence.json "
            "(scripts/collect_lexicon_evidence.py regenerates it from the "
            "live sources; tests/test_lexicon_evidence.py refuses to let an "
            "entry ship if its sat text is not found there - hand-retyping "
            "Ol Chiki is exactly how a neighbouring-script character sneaks "
            "into a project). Machine translations are NOT placed in this "
            "file - they come from the NLLB engine and always carry the "
            "review warning."
        ),
        "schema": {
            "id": "stable slug",
            "kind": "word | phrase",
            "category": "animals | numbers | colours | greetings | classroom | family | body | food",
            "hi": "Hindi text",
            "sat": "Santali text in Ol Chiki",
            "sat_latin": "optional romanization",
            "en": "optional English gloss",
            "icon": "optional emoji used on flashcards",
            "source": "where this was verified from",
            "needs_review": "false by default - only verified entries live here",
            "verified_against": (
                "evidence.json source keys whose extracted token sets must "
                "contain this entry's sat text; enforced by "
                "tests/test_lexicon_evidence.py"
            ),
        },
    },
    "entries": [
        # ---- numbers 1-10 ------------------------------------------------
        # Both number-list pages (Omniglot and countbylanguage) were fetched
        # raw and agree byte-for-byte, including the GAHARA sign in 'eight'
        # that some renderers munch into a dot. The digit articles on
        # sat.wikipedia use the same words in their titles.
        {"id": "num-1", "kind": "word", "category": "numbers",
         "hi": "एक", "sat": "ᱢᱤᱫ", "sat_latin": "mit'", "en": "one", "icon": "1",
         "source": "Omniglot 'Numbers in Santali' + countbylanguage Santali numbers, byte-identical; sat.wikipedia digit-article title agrees",
         "verified_against": ["omniglot_numbers", "countbylanguage", "satwiki_sitelinks"]},
        {"id": "num-2", "kind": "word", "category": "numbers",
         "hi": "दो", "sat": "ᱵᱟᱨ", "sat_latin": "bar", "en": "two", "icon": "2",
         "source": "Omniglot 'Numbers in Santali' + countbylanguage Santali numbers, byte-identical; sat.wikipedia digit-article title agrees",
         "verified_against": ["omniglot_numbers", "countbylanguage", "satwiki_sitelinks"]},
        {"id": "num-3", "kind": "word", "category": "numbers",
         "hi": "तीन", "sat": "ᱯᱮ", "sat_latin": "pe", "en": "three", "icon": "3",
         "source": "Omniglot 'Numbers in Santali' + countbylanguage Santali numbers, byte-identical",
         "verified_against": ["omniglot_numbers", "countbylanguage"]},
        {"id": "num-4", "kind": "word", "category": "numbers",
         "hi": "चार", "sat": "ᱯᱩᱱ", "sat_latin": "pun", "en": "four", "icon": "4",
         "source": "Omniglot 'Numbers in Santali' + countbylanguage Santali numbers, byte-identical",
         "verified_against": ["omniglot_numbers", "countbylanguage"]},
        {"id": "num-5", "kind": "word", "category": "numbers",
         "hi": "पाँच", "sat": "ᱢᱚᱬᱮ", "sat_latin": "môṇe", "en": "five", "icon": "5",
         "source": "Omniglot 'Numbers in Santali' + countbylanguage Santali numbers, byte-identical",
         "verified_against": ["omniglot_numbers", "countbylanguage"]},
        {"id": "num-6", "kind": "word", "category": "numbers",
         "hi": "छह", "sat": "ᱛᱩᱨᱩᱭ", "sat_latin": "turuy", "en": "six", "icon": "6",
         "source": "Omniglot + countbylanguage, byte-identical; sat.wiktionary entry agrees and glosses it in Hindi",
         "verified_against": ["omniglot_numbers", "countbylanguage", "satwiktionary"]},
        {"id": "num-7", "kind": "word", "category": "numbers",
         "hi": "सात", "sat": "ᱮᱭᱟᱭ", "sat_latin": "eyay", "en": "seven", "icon": "7",
         "source": "Omniglot 'Numbers in Santali' + countbylanguage Santali numbers, byte-identical",
         "verified_against": ["omniglot_numbers", "countbylanguage"]},
        {"id": "num-8", "kind": "word", "category": "numbers",
         "hi": "आठ", "sat": "ᱤᱨᱟᱹᱞ", "sat_latin": "irăl", "en": "eight", "icon": "8",
         "source": "Omniglot + countbylanguage, byte-identical, GAHARA sign verified as U+1C79 in the raw bytes of both",
         "verified_against": ["omniglot_numbers", "countbylanguage"]},
        {"id": "num-9", "kind": "word", "category": "numbers",
         "hi": "नौ", "sat": "ᱟᱨᱮ", "sat_latin": "are", "en": "nine", "icon": "9",
         "source": "Omniglot + countbylanguage, byte-identical; sat.wiktionary entry agrees",
         "verified_against": ["omniglot_numbers", "countbylanguage", "satwiktionary"]},
        {"id": "num-10", "kind": "word", "category": "numbers",
         "hi": "दस", "sat": "ᱜᱮᱞ", "sat_latin": "gel", "en": "ten", "icon": "10",
         "source": "Omniglot + countbylanguage, byte-identical; sat.wiktionary entry glosses it in Hindi",
         "verified_against": ["omniglot_numbers", "countbylanguage", "satwiktionary"]},

        # ---- animals -----------------------------------------------------
        # No 'deer' entry on purpose: Wikibooks lists the meat word under
        # deer, but the sat.wiktionary entry for that word glosses it as
        # meat in Hindi with meat examples - we take the Wiktionary side and
        # leave the conflict out of the classroom.
        {"id": "animal-cow", "kind": "word", "category": "animals",
         "hi": "गाय", "sat": "ᱜᱟᱹᱭ", "en": "cow", "icon": "🐄",
         "source": "sat.wikipedia cattle article title (Wikidata Q830 sitelink) + sat.wiktionary cow entry, both with the modern GAHARA spelling; Wikibooks lists the older period-orthography form",
         "verified_against": ["satwiki_sitelinks", "satwiktionary"]},
        {"id": "animal-dog", "kind": "word", "category": "animals",
         "hi": "कुत्ता", "sat": "ᱥᱮᱛᱟ", "en": "dog", "icon": "🐕",
         "source": "sat.wikipedia dog article title (Wikidata Q144 sitelink) + Wikibooks Santali/Animals, identical",
         "verified_against": ["satwiki_sitelinks", "wikibooks_animals"]},
        {"id": "animal-cat", "kind": "word", "category": "animals",
         "hi": "बिल्ली", "sat": "ᱯᱩᱥᱤ", "en": "cat", "icon": "🐈",
         "source": "sat.wikipedia cat article title (Wikidata Q146 sitelink) + Wikibooks Santali/Animals, identical",
         "verified_against": ["satwiki_sitelinks", "wikibooks_animals"]},
        {"id": "animal-goat", "kind": "word", "category": "animals",
         "hi": "बकरी", "sat": "ᱢᱮᱨᱚᱢ", "en": "goat", "icon": "🐐",
         "source": "sat.wikipedia goat article title (Wikidata Q2934 sitelink) + Wikibooks Santali/Animals, identical",
         "verified_against": ["satwiki_sitelinks", "wikibooks_animals"]},
        {"id": "animal-horse", "kind": "word", "category": "animals",
         "hi": "घोड़ा", "sat": "ᱥᱟᱫᱚᱢ", "en": "horse", "icon": "🐎",
         "source": "sat.wikipedia horse article title (Wikidata Q726 sitelink) + Wikibooks Santali/Animals, identical",
         "verified_against": ["satwiki_sitelinks", "wikibooks_animals"]},
        {"id": "animal-buffalo", "kind": "word", "category": "animals",
         "hi": "भैंस", "sat": "ᱠᱟᱲᱟ", "en": "buffalo", "icon": "🐃",
         "source": "Wikibooks Santali/Animals + sat.wiktionary buffalo entry (photo entry), identical",
         "verified_against": ["wikibooks_animals", "satwiktionary"]},
        {"id": "animal-bird", "kind": "word", "category": "animals",
         "hi": "पक्षी", "sat": "ᱪᱮᱬᱮ", "en": "bird", "icon": "🐦",
         "source": "sat.wikipedia bird article title (Wikidata Q5113 sitelink) + sat.wiktionary running text ('bird meat' in the meat entry), identical",
         "verified_against": ["satwiki_sitelinks", "satwiktionary"]},
        {"id": "animal-fox", "kind": "word", "category": "animals",
         "hi": "लोमड़ी", "sat": "ᱛᱩᱭᱩ", "en": "fox", "icon": "🦊",
         "source": "sat.wiktionary fox entry (Hindi gloss) + Wikibooks Santali/Animals, identical",
         "verified_against": ["satwiktionary", "wikibooks_animals"]},
        {"id": "animal-rabbit", "kind": "word", "category": "animals",
         "hi": "खरगोश", "sat": "ᱠᱩᱞᱟᱹᱭ", "en": "rabbit", "icon": "🐇",
         "source": "sat.wiktionary rabbit entry (Hindi gloss); the page title uses the older period orthography, the body uses the modern GAHARA form we ship",
         "verified_against": ["satwiktionary"]},
        {"id": "animal-donkey", "kind": "word", "category": "animals",
         "hi": "गधा", "sat": "ᱜᱟᱫᱷᱟ", "en": "donkey", "icon": "",
         "source": "Wikibooks Santali/Animals + sat.wiktionary donkey entry (donkey photo), identical",
         "verified_against": ["wikibooks_animals", "satwiktionary"]},

        # ---- food, body, classroom --------------------------------------
        {"id": "food-meat", "kind": "word", "category": "food",
         "hi": "मांस", "sat": "ᱡᱤᱞ", "en": "meat", "icon": "🍖",
         "source": "sat.wiktionary meat entry: Hindi gloss plus usage examples (bird meat, pork, goat meat)",
         "verified_against": ["satwiktionary"]},
        {"id": "food-water", "kind": "word", "category": "food",
         "hi": "पानी", "sat": "ᱫᱟᱜ", "en": "water", "icon": "💧",
         "source": "sat.wikipedia water article title (Wikidata Q283 sitelink); Wikibooks uses the same word inside its rhinoceros compound",
         "verified_against": ["satwiki_sitelinks", "wikibooks_animals"]},
        {"id": "food-food", "kind": "word", "category": "food",
         "hi": "भोजन", "sat": "ᱡᱚᱢᱟᱜ", "en": "food", "icon": "🍚",
         "source": "sat.wikipedia food article title (Wikidata Q2095 sitelink) + sat.wiktionary food entry (English gloss 'eatable; food')",
         "verified_against": ["satwiki_sitelinks", "satwiktionary"]},
        {"id": "body-hand", "kind": "word", "category": "body",
         "hi": "हाथ", "sat": "ᱛᱤ", "en": "hand", "icon": "✋",
         "source": "sat.wiktionary hand entry: Hindi gloss, right-hand/left-hand usage examples",
         "verified_against": ["satwiktionary"]},
        {"id": "classroom-school", "kind": "word", "category": "classroom",
         "hi": "विद्यालय", "sat": "ᱵᱤᱨᱫᱟᱹᱜᱟᱲ", "en": "school", "icon": "🏫",
         "source": "sat.wikipedia school article title (Wikidata Q3914 sitelink), modern GAHARA spelling",
         "verified_against": ["satwiki_sitelinks"]},
        # ---- classroom sentence words (added for the demo utterances) ----
        # These four are what the fixed demo sentences are built from; each
        # is byte-identical to a machine-extracted token in evidence.json.
        {"id": "classroom-child", "kind": "word", "category": "classroom",
         "hi": "बच्चे", "sat": "ᱜᱤᱫᱽᱨᱟ", "sat_latin": "gidra", "en": "child", "icon": "🧒",
         "source": "Wikibooks Santali/Animals word list, byte-identical",
         "verified_against": ["wikibooks_animals"]},
        {"id": "classroom-name", "kind": "word", "category": "classroom",
         "hi": "नाम", "sat": "ᱧᱩᱛᱩᱢ", "sat_latin": "nutum", "en": "name", "icon": "🏷️",
         "source": "sat.wiktionary name entry, byte-identical",
         "verified_against": ["satwiktionary"]},
        {"id": "classroom-animal", "kind": "word", "category": "classroom",
         "hi": "जानवर", "sat": "ᱡᱤᱵᱽ", "sat_latin": "jib'", "en": "animal", "icon": "🐾",
         "source": "sat.wiktionary animal entry, byte-identical",
         "verified_against": ["satwiktionary"]},
        {"id": "classroom-we", "kind": "word", "category": "classroom",
         "hi": "हम", "sat": "ᱟᱞᱮ", "sat_latin": "ale", "en": "we", "icon": "👥",
         "source": "sat.wiktionary we entry, byte-identical",
         "verified_against": ["satwiktionary"]},
    ],
}
