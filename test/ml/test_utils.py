from unittest import TestCase
from collections import defaultdict

from bavard_ml_common.ml.utils import make_stratified_folds


class TestUtils(TestCase):

    def test_make_stratified_folds(self) -> None:
        data = list(range(10))
        labels = [0, 1] * 5
        data_counts = defaultdict(int)
        for fold in make_stratified_folds(data, labels, 3):
            for item in fold:
                data_counts[item] += 1

        # Check each instance occurs once and only once in a fold.
        for item in data:
            self.assertEqual(data_counts[item], 1)