"""
Classes for dealing with amino acid mutation sets
"""
import re
from collections import namedtuple
from operator import attrgetter

AMINO_ALPHABET = 'ACDEFGHIKLMNPQRSTVWY'


class VariantCalls(namedtuple('VariantCalls', 'mutation_sets reference')):
    # TODO: remove all these __init__ methods once PyCharm bug is fixed.
    # https://youtrack.jetbrains.com/issue/PY-26834
    # noinspection PyUnusedLocal
    def __init__(self, text=None, reference=None, sample=None):
        """ Construct a set of Mutations given two aligned amino acid sequences

        :param str reference: the wild-type reference
        :param sample: amino acids present at each position, either a string or
        a list of strings
        """
        # noinspection PyArgumentList
        super().__init__()

    def __new__(cls, text=None, reference=None, sample=None):
        if text is not None:
            terms = text.split()
            mutation_sets = frozenset(
                MutationSet(term, reference=reference)
                for term in terms)
        else:
            if len(reference) != len(sample):
                raise ValueError(
                    'Reference length was {} and sample length was {}.'.format(
                        len(reference),
                        len(sample)))

            mutation_sets = {MutationSet(pos=i, variants=alt, wildtype=ref)
                             for i, (alt, ref) in enumerate(zip(sample,
                                                                reference),
                                                            1)
                             if alt}
        positions = set()
        for mutation_set in mutation_sets:
            if mutation_set.pos in positions:
                message = 'Multiple mutation sets at position {}.'.format(
                    mutation_set.pos)
                raise ValueError(message)
            positions.add(mutation_set.pos)
        # noinspection PyArgumentList
        return super().__new__(cls,
                               mutation_sets=mutation_sets,
                               reference=reference)

    def __str__(self):
        return ' '.join(map(str, sorted(self.mutation_sets,
                                        key=attrgetter('pos'))))

    def __repr__(self):
        text = str(self)
        return 'VariantCalls({!r})'.format(text)

    def __eq__(self, other):
        return self.mutation_sets == other.mutation_sets

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.mutation_sets)

    def __iter__(self):
        return iter(self.mutation_sets)

    def __len__(self):
        return len(self.mutation_sets)

    def __contains__(self, item):
        return item in self.mutation_sets


class Mutation(namedtuple('Mutation', 'pos variant wildtype')):
    """Mutation has optional wildtype, position, and call"""

    def __new__(cls, text=None, wildtype=None, pos=None, variant=None):
        if text is not None:
            match = re.match(r"([A-Z]?)(\d+)([idA-Z])", text)
            if match is None:
                raise ValueError('Mutation text expects wild type (optional), '
                                 'position, and one variant.')

            if match.group(0) != text:
                # user probably supplied ambiguous variant def
                raise ValueError('Mutation text only allows one variant.')

            wildtype, pos, variant = match.groups()
        # noinspection PyArgumentList
        return super().__new__(cls,
                               pos=int(pos),
                               variant=variant,
                               wildtype=wildtype or None)

    # noinspection PyUnusedLocal
    def __init__(self, text=None, wildtype=None, pos=None, variant=None):
        """ Initialize.

        :param str text: will be parsed for wildtype (optional), position,
            and variant
        :param str wildtype: amino acid abbreviation for wild type
        :param str|int pos: position
        :param str variant: single amino acid abbreviation, or 'i' for
            insertion, or 'd' for deletion
        """
        # noinspection PyArgumentList
        super().__init__()

    def __repr__(self):
        text = str(self)
        return "Mutation({!r})".format(text)

    def __str__(self):
        text = self.wildtype or ''
        text += '{}{}'.format(self.pos, self.variant)
        return text

    def __eq__(self, other):
        if self.pos != other.pos:
            return False

        if self.wildtype is not None and other.wildtype is not None:
            # if the wt is specified for wt and variant, they must match
            # otherwise the user is doing something weird
            if self.wildtype != other.wildtype:
                message = 'Wild type mismatch between {} and {}.'.format(self,
                                                                         other)
                raise ValueError(message)

        # now that we agree on the wt and position
        return (self.pos, self.variant) == (other.pos, other.variant)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.pos, self.variant))


class MutationSet(namedtuple('MutationSet', 'pos mutations wildtype')):
    """Handle sets of mutations at a position"""

    def __new__(cls,
                text=None,
                wildtype=None,
                pos=None,
                variants=None,
                mutations=None,
                reference=None):
        negative = None
        if text:
            match = re.match(r"([A-Z]?)(\d+)(!)?([idA-Z]+)$", text)
            if match is None:
                message = 'MutationSet text expects wild type (optional), ' \
                          'position, and one or more variants.'
                raise ValueError(message)

            wildtype, pos, negative, variants = match.groups()
            if reference:
                wildtype = reference[int(pos)-1]

        if variants:
            if negative:
                original_variants = variants
                variants = (c
                            for c in AMINO_ALPHABET
                            if c not in original_variants)
            mutations = frozenset(Mutation(wildtype=wildtype,
                                           pos=pos,
                                           variant=variant)
                                  for variant in variants)
        else:
            mutations = frozenset(mutations or tuple())
            positions = {mutation.pos for mutation in mutations}
            wildtypes = {mutation.wildtype for mutation in mutations}
            if pos is not None:
                positions.add(pos)
            wildtypes.add(wildtype)
            wildtypes.discard(None)
            if len(positions) > 1:
                message = 'Multiple positions found: {}.'.format(
                    ', '.join(map(str, sorted(positions))))
                raise ValueError(message)
            if not wildtypes and not mutations:
                raise ValueError('No wildtype and no variants.')
            if not positions:
                raise ValueError('No position and no variants.')
            if len(wildtypes) > 1:
                message = 'Multiple wildtypes found: {}.'.format(
                    ', '.join(sorted(wildtypes)))
                raise ValueError(message)
            pos = positions.pop()
            if wildtypes:
                wildtype = wildtypes.pop()
        # noinspection PyArgumentList
        return super().__new__(cls,
                               wildtype=wildtype or None,
                               pos=int(pos),
                               mutations=mutations)

    # noinspection PyUnusedLocal
    def __init__(self,
                 text=None,
                 wildtype=None,
                 pos=None,
                 variants=None,
                 mutations=None,
                 reference=None):
        """ Initialize

        :param str text: will be parsed for wildtype (optional), position,
            and variants
        :param str wildtype: amino acid abbreviation for wild type
        :param int|str pos: position
        :param str variants: zero or more amino acid abbreviations, or 'i' for
            insertion, or 'd' for deletion
        :param mutations: a sequence of Mutation objects, with matching
            positions and wild types
        :param str reference: alternative source for wildtype, based on
            pos - 1
        """
        # noinspection PyArgumentList
        super().__init__()

    def __len__(self):
        return len(self.mutations)

    def __contains__(self, call):
        return call in self.mutations

    def __eq__(self, other):
        if self.pos != other.pos:
            return False
        if self.wildtype is not None and other.wildtype is not None:
            # if the wt is specified for wt and variant, they must match
            # otherwise the user is doing something weird
            if self.wildtype != other.wildtype:
                message = 'Wild type mismatch between {} and {}.'.format(self,
                                                                         other)
                raise ValueError(message)
        return self.mutations == other.mutations

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.pos, self.mutations))

    def __iter__(self):
        return iter(self.mutations)

    def __str__(self):
        text = self.wildtype or ''
        text += str(self.pos)
        mutations = ''.join(sorted(mutation.variant
                                   for mutation in self.mutations))
        if len(mutations) > 10:
            text += '!'
            mutations = ''.join(c
                                for c in AMINO_ALPHABET
                                if c not in mutations)
        text += mutations
        return text

    def __repr__(self):
        text = str(self)
        return 'MutationSet({!r})'.format(text)
