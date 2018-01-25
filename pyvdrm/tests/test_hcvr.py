import os
import unittest

from pyparsing import ParseException

from pyvdrm.drm import MissingPositionError
from pyvdrm.hcvr import HCVR, AsiMutations, Score
from pyvdrm.vcf import Mutation, MutationSet, VariantCalls


# noinspection SqlNoDataSourceInspection,SqlDialectInspection
class TestRuleParser(unittest.TestCase):

    def test_stanford_ex1(self):
        HCVR("151M OR 69i")

    def test(self):
        rule = HCVR("SELECT ATLEAST 2 FROM (41L, 67N, 70R, 210W, 215F, 219Q)")
        self.assertTrue(rule(VariantCalls('41L 67N 70d 210d 215d 219d')))

    def test_atleast_false(self):
        rule = HCVR("SELECT ATLEAST 2 FROM (41L, 67N, 70R, 210W, 215F, 219Q)")
        self.assertFalse(rule(VariantCalls('41L 67d 70d 210d 215d 219d')))

    def test_atleast_missing(self):
        rule = HCVR("SELECT ATLEAST 2 FROM (41L, 67N, 70R, 210W, 215F, 219Q)")
        with self.assertRaisesRegex(MissingPositionError,
                                    r'Missing position 70.'):
            rule(VariantCalls('41L 67N'))

    def test_stanford_ex3(self):
        HCVR("SELECT ATLEAST 2 AND NOTMORETHAN 2 FROM (41L, 67N, 70R, 210W, 215FY, 219QE)")

    def test_stanford_ex4(self):
        HCVR("215FY AND 184!VI")

    def test_stanford_rest(self):
        examples = ["SCORE FROM (65R => 20, 74V => 20, 184VI => 20)",
                    "151M AND EXCLUDE 69i",
                    "215F OR 215Y",
                    "SCORE FROM (101P => 40, 101E => 30, 101HN => 15, 101Q => 5 )",
                    "SCORE FROM ( MAX  (101P => 40, 101E => 30, 101HN => 15, 101Q => 5 ))",
                    "(184V AND 115F) => 20"
                    "3N AND 9N",
                    "2N OR 9N AND 2N",
                    "3N AND (2N AND (4N OR 2N))"]

        for ex in examples:
            x = HCVR(ex)
            self.assertEqual(ex, x.rule)

    def test_asi2_compat(self):
        q = "SCORE FROM ( 98G => 10, 100I => 40,\
                          MAX (101P => 40, 101E => 30, 101HN => 15, 101Q => 5) )"
        HCVR(q)


# noinspection SqlNoDataSourceInspection,SqlDialectInspection
class TestRuleSemantics(unittest.TestCase):
    def test_score_from(self):
        rule = HCVR("SCORE FROM ( 100G => 5, 101DST => 20 )")
        self.assertEqual(rule(VariantCalls("100G 101G")), 5)
        self.assertEqual(rule(VariantCalls("100G 101d")), 5)
        self.assertEqual(rule(VariantCalls("100G 101D")), 25)
        self.assertEqual(rule(VariantCalls("100G 101DST")), 25)
        with self.assertRaisesRegex(MissingPositionError,
                                    r'Missing position 100.'):
            rule(VariantCalls("105G 106DST"))

    def test_score_negate(self):
        rule = HCVR("SCORE FROM ( 100!G => 10, 101!SD => 20 )")
        self.assertEqual(rule(VariantCalls("100G 101D")), 0)
        self.assertEqual(rule(VariantCalls("100S 101S")), 10)
        self.assertEqual(rule(VariantCalls("100S 101W")), 30)
        self.assertEqual(rule(VariantCalls("100G 101TW")), 20)

    def test_score_residues(self):
        rule = HCVR("SCORE FROM ( 100G => 10, 101D => 20 )")
        expected_residue = repr({Mutation('S100G')})

        result = rule.dtree(VariantCalls("S100G R101d"))

        self.assertEqual(expected_residue, repr(result.residues))

    def test_score_from_max(self):
        rule = HCVR("SCORE FROM (MAX (100G => 10, 101D => 20, 102D => 30))")
        self.assertEqual(rule(VariantCalls("100G 101D 102d")), 20)

    def test_score_from_max_neg(self):
        rule = HCVR("SCORE FROM (MAX (100G => -10, 101D => -20, 102D => 30))")
        self.assertEqual(-10, rule(VariantCalls("100G 101D 102d")))

    def test_bool_and(self):
        rule = HCVR("1G AND (2T AND 7Y)")
        self.assertEqual(rule(VariantCalls("2T 7Y 1G")), True)
        self.assertEqual(rule(VariantCalls("2T 7d 1G")), False)
        self.assertEqual(rule(VariantCalls("7Y 1G 2T")), True)
        with self.assertRaisesRegex(MissingPositionError,
                                    r"Missing position 1"):
            rule([])

    def test_bool_constants(self):
        rule = HCVR("TRUE OR 1G")
        self.assertEqual(rule(VariantCalls("1d")), True)
        rule = HCVR("FALSE AND 1G")
        self.assertEqual(rule(VariantCalls("1G")), False)
        rule = HCVR("TRUE OR (FALSE AND TRUE)")
        self.assertEqual(rule(VariantCalls("1G")), True)

    def test_bool_or(self):
        rule = HCVR("1G OR (2T OR 7Y)")
        self.assertTrue(rule(VariantCalls("1d 2T 7d")))
        self.assertFalse(rule(VariantCalls("1d 2d 7d")))
        self.assertTrue(rule(VariantCalls("1G 2d 7d")))
        with self.assertRaisesRegex(MissingPositionError,
                                    r"Missing position 1"):
            rule([])

    def test_select_from_atleast(self):
        rule = HCVR("SELECT ATLEAST 2 FROM (2T, 7Y, 3G)")
        self.assertTrue(rule(VariantCalls("2T 7Y 3d")))
        self.assertFalse(rule(VariantCalls("2T 7d 3d")))
        self.assertTrue(rule(VariantCalls("3G 7d 2T")))

    def test_score_from_exactly(self):
        rule = HCVR("SELECT EXACTLY 1 FROM (2T, 7Y)")
        score = rule(VariantCalls("2T 7Y 1G"))
        self.assertEqual(0, score)

    def test_score_comment(self):
        rule = HCVR('SCORE FROM (100G => 10, 200T => 3, 100S => "flag1 with_space")')
        self.assertEqual(rule(VariantCalls("100G 200d")), 10)
        result = rule.dtree(VariantCalls("100S 200T"))
        self.assertEqual(result.score, 3)
        self.assertIn("flag1 with_space", result.flags)

    def test_parse_exception(self):
        expected_error_message = (
            "Error in HCVR: SCORE FROM ( 10R => 2>!<;0 ) (at char 21), (line:1, col:22)")

        with self.assertRaises(ParseException) as context:
            HCVR("SCORE FROM ( 10R => 2;0 )")

        self.assertEqual(expected_error_message, str(context.exception))

    def test_parse_exception_multiline(self):
        rule = """\
SCORE FROM (
    10R => 2;0
)
"""
        expected_error_message = (
            "Error in HCVR: 10R => 2>!<;0 (at char 25), (line:2, col:13)")

        with self.assertRaises(ParseException) as context:
            HCVR(rule)

        self.assertEqual(expected_error_message, str(context.exception))


def add_mutations(text):
    """ Add a small set of mutations to an RT wild type. """

    # Start of RT reference.
    ref = ("PISPIETVPVKLKPGMDGPKVKQWPLTEEKIKALVEICTEMEKEGKISKIGPENPYNTPVFA"
           "IKKKDSTKWRKLVDFRELNKRTQDFWEVQLGIPHPAGLKKKKSVTVLDVGDAYFSVPLDEDF"
           "RKYTAFTIPSINNETPGIRYQYNVLPQGWKGSPAIFQSSMTKILEPFRKQNPDIVIYQYMDD"
           "LYVGSDLEIGQHRTKIEELRQHLLRWGLTTPDKKHQK")
    seq = list(ref)
    changes = VariantCalls(text)
    for mutation_set in changes:
        seq[mutation_set.pos - 1] = [m.variant for m in mutation_set]
    return VariantCalls(reference=ref, sample=seq)


class TestActualRules(unittest.TestCase):
    def test_hivdb_rules_parse(self):
        folder = os.path.dirname(__file__)
        rules_file = os.path.join(folder, 'HIVDB.rules')
        for line in open(rules_file):
            r = HCVR(line)
            self.assertEqual(line, r.rule)

    def test_chained_and(self):
        rule = HCVR("""
        SCORE FROM(41L => 5, 62V => 5, MAX ( 65E => 10, 65N =>
        30, 65R => 45 ), MAX ( 67E => 5, 67G => 5, 67H => 5, 67N => 5, 67S =>
        5, 67T => 5, 67d => 30 ), 68d => 15, MAX ( 69G => 10, 69i => 60, 69d =>
        15 ), MAX ( 70E => 15, 70G => 15, 70N => 15, 70Q => 15, 70R => 5, 70S
        => 15, 70T => 15, 70d => 15 ), MAX ( 74I => 30, 74V => 30 ), 75I => 5,
        77L => 5, 115F => 60, 116Y => 10, MAX ( 151L => 30, 151M => 60 ), MAX(
        184I => 15, 184V => 15 ), 210W => 5, MAX ( 215A => 5, 215C => 5, 215D
        => 5, 215E => 5, 215F => 10, 215I => 5, 215L => 5, 215N => 5, 215S =>
        5, 215V => 5, 215Y => 10 ), MAX ( 219E => 5, 219N => 5, 219Q => 5, 219R
        => 5 ), (40F AND 41L AND 210W AND 215FY) => 5, (41L AND 210W) => 10,
        (41L AND 210W AND 215FY) => 5, (41L AND 44AD AND 210W AND 215FY) => 5,
        (41L AND 67EGN AND 215FY) => 5, (67EGN AND 215FY AND 219ENQR) => 5,
        (67EGN AND 70R AND 184IV AND 219ENQR) => 20, (67EGN AND 70R AND
        219ENQR) => 10, (70R AND 215FY) => 5, (74IV AND 184IV) => 15, (77L AND
        116Y AND 151M) => 10, MAX ((210W AND 215ACDEILNSV) => 5, (210W AND
        215FY) => 10), MAX ((41L AND 215ACDEILNSV) => 5, (41L AND 215FY) =>
        15))
        """)
        self.assertEqual(rule(add_mutations("40F 41L 210W 215Y")), 65)
        self.assertEqual(rule(add_mutations("41L 210W 215F")), 60)
        self.assertEqual(rule(add_mutations("40F 210W 215Y")), 25)
        self.assertEqual(rule(add_mutations("40F 67G 215Y")), 15)


class TestAsiMutations(unittest.TestCase):
    def test_init_args(self):
        expected_mutation_set = MutationSet('Q80KR')
        m = AsiMutations(args='Q80KR')

        self.assertEqual(expected_mutation_set, m.mutations)
        self.assertEqual(expected_mutation_set.wildtype, m.mutations.wildtype)

    def test_repr(self):
        expected_repr = "AsiMutations(args='Q80KR')"
        m = AsiMutations(args='Q80KR')

        r = repr(m)

        self.assertEqual(expected_repr, r)


class TestScore(unittest.TestCase):
    def test_init(self):
        expected_value = 10
        expected_mutations = {Mutation('A23R')}

        score = Score(expected_value, expected_mutations)

        self.assertEqual(expected_value, score.score)
        self.assertEqual(expected_mutations, set(score.residues))

    def test_repr(self):
        expected_repr = "Score(10, {Mutation('A23R')})"
        score = Score(10, {Mutation('A23R')})

        r = repr(score)

        self.assertEqual(expected_repr, r)


class TestVariantPropagation(unittest.TestCase):
    def test_true_positive(self):
        m = VariantCalls('Q54H 444H')
        rule = HCVR("SCORE FROM ( 54H => 0, 444H => 8 )")
        dtree = rule.dtree(m)

        expected_repr = "[Mutation('Q54H'), Mutation('444H')]"
        self.assertEqual(expected_repr, repr(sorted(dtree.residues)))


if __name__ == '__main__':
    unittest.main()
