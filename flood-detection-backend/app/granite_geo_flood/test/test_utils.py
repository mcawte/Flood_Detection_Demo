import pytest
import torch

from granite_geo_flood.utils.helper import calc_f1, calc_miou


@pytest.mark.parametrize(
    "truth,pred,expected",
    [
        (torch.tensor([0, 0, 1, 1]), torch.tensor([0, 0, 0, 0]), 0.25),
        (torch.tensor([-1, 1, 1, 1]), torch.tensor([-1, 0, 0, -1]), 0),
        (torch.tensor([[-1, 0], [1, -1]]), torch.tensor([[-1, 0], [1, -1]]), 1),
    ],
)
def test_calc_miou(truth, pred, expected):
    assert calc_miou(truth, pred) == expected


@pytest.mark.parametrize(
    "truth,pred,expected",
    [
        (torch.tensor([0, 0, 1, 1]), torch.tensor([0, 0, 0, 0]), 0.5),
        (torch.tensor([[-1, 0], [1, 0]]), torch.tensor([[-1, 0], [1, 0]]), 1),
        (torch.tensor([[-1, 0], [0, 0]]), torch.tensor([[-1, 0], [1, 1]]), 1 / 3),
    ],
)
def test_calc_f1(truth, pred, expected):
    assert calc_f1(truth, pred) == expected
