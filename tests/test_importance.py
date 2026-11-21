"""Our own importance weighting for Mortal-S42's game rating: the situation buckets and the fit on top of them."""

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fit_importance as fit  # noqa: E402
import mine_importance as mine  # noqa: E402


def cell(turn=0, shanten=3, threat=0, kind=0, stage=0):
    return fit.CELL_INDEX[f"{turn}.{shanten}.{threat}.{kind}.{stage}"]


def synthetic(games=400, seed=0, players=None):
    """Seat-games whose place follows the player's mistakes at tenpai only; early mistakes are noise.

    Every seat has the same number of decisions in each situation, so the mix of situations says nothing.
    """
    rng = np.random.default_rng(seed)
    early, tenpai = cell(turn=0, shanten=3), cell(turn=6, shanten=0)
    n = np.zeros((games * 4, len(fit.CELLS)))
    loss = np.zeros_like(n)
    place, game, name = [], [], []
    for g in range(games):
        skill = rng.normal(size=4)
        late_loss = np.clip(2.0 - skill + rng.normal(0, 0.5, 4), 0, None)
        order = np.argsort(np.argsort(late_loss + rng.normal(0, 0.8, 4)))
        for seat in range(4):
            i = g * 4 + seat
            n[i, early], n[i, tenpai] = 40, 10
            loss[i, early] = rng.uniform(0, 30)
            loss[i, tenpai] = late_loss[seat]
            place.append(order[seat] + 1)
            game.append(f"g{g}")
            name.append(f"p{(g * 4 + seat) % players}" if players else None)
    data = {"n": n, "Q loss": loss, "ln p": loss.copy(), "miss": loss.copy(), "place": np.array(place, dtype=float),
            "game": np.array(game), "name": np.array(name, dtype=object), "seat": np.tile(np.arange(4), games)}
    return fit.add_adjusted(data)


class BucketTest(unittest.TestCase):
    def test_turns_come_in_pairs_and_shanten_is_capped(self):
        self.assertEqual(mine.bucket(1, 5, 0, 0, 0), "0.3.0.0.0")
        self.assertEqual(mine.bucket(2, 2, 0, 0, 0), "0.2.0.0.0")
        self.assertEqual(mine.bucket(3, 0, 2, 1, 2), "1.0.2.1.2")
        self.assertEqual(mine.bucket(40, -1, 1, 0, 1), "8.0.1.0.1")

    def test_stage(self):
        self.assertEqual(mine.stage_of({"bakaze": "E", "kyoku": 4}), 0)
        self.assertEqual(mine.stage_of({"bakaze": "S", "kyoku": 3}), 1)
        self.assertEqual(mine.stage_of({"bakaze": "S", "kyoku": 4}), 2)
        self.assertEqual(mine.stage_of({"bakaze": "W", "kyoku": 1}), 2)

    def test_every_bucket_the_miner_can_write_is_a_cell_of_the_fit(self):
        keys = {mine.bucket(t, s, th, k, st) for t in range(1, 30) for s in range(-1, 7) for th in range(3)
                for k in range(2) for st in range(3)}
        self.assertEqual(keys, set(fit.CELL_INDEX))
        self.assertEqual(len(fit.CELLS), 9 * 4 * 3 * 2 * 3)


class WeightingTest(unittest.TestCase):
    def test_wind_up_bird_formula_orders_situations_as_its_reviews_do(self):
        w = fit.weightings()["Wind-Up Bird, +threat"]
        self.assertGreater(w[cell(turn=6, shanten=0)], w[cell(turn=6, shanten=1)])
        self.assertGreater(w[cell(turn=6, shanten=1)], w[cell(turn=6, shanten=3)])
        self.assertGreater(w[cell(turn=8, shanten=2)], w[cell(turn=0, shanten=2)])
        self.assertGreater(w[cell(turn=4, shanten=2, threat=2)], w[cell(turn=4, shanten=2, threat=0)])
        # a tenpai hand late against a riichi weighs many times an opening discard, as on the site (55 against 2.4)
        self.assertGreater(w[cell(turn=6, shanten=0, threat=2)] / w[cell(turn=0, shanten=3)], 10)
        self.assertTrue(np.all(fit.weightings()["flat"] == 1))
        self.assertEqual(fit.weightings()["later turns"][cell(turn=4)], 9.5)

    def test_rating_is_minus_the_weighted_mean_loss(self):
        data = {"n": np.zeros((1, len(fit.CELLS))), "Q loss": np.zeros((1, len(fit.CELLS)))}
        a, b = cell(turn=0), cell(turn=8, shanten=0)
        data["n"][0, a], data["n"][0, b] = 30, 10
        data["Q loss"][0, a], data["Q loss"][0, b] = 6.0, 4.0
        flat = np.ones(len(fit.CELLS))
        self.assertAlmostEqual(fit.rating(data, "Q loss", flat)[0], -10 / 40)
        w = flat.copy()
        w[b] = 3.0
        self.assertAlmostEqual(fit.rating(data, "Q loss", w)[0], -(6 + 12) / (30 + 30))

    def test_raw_loss_is_the_usual_cost_plus_the_players_own_part(self):
        data = synthetic(games=30)
        np.testing.assert_allclose(data["Q loss usual"] + data["Q loss adj"], data["Q loss"])
        np.testing.assert_allclose(data["Q loss adj"].sum(axis=0), 0, atol=1e-8)  # nobody is better than usual on average

    def test_the_situation_mix_alone_can_track_the_place(self):
        # two kinds of seat: one was tenpai often and placed well; nobody ever makes a mistake that matters
        rng = np.random.default_rng(4)
        seats = 400
        n = np.zeros((seats, len(fit.CELLS)))
        loss = np.zeros_like(n)
        early, tenpai = cell(turn=0, shanten=3), cell(turn=6, shanten=0)
        lucky = rng.random(seats) < 0.5
        n[:, early] = 40
        n[:, tenpai] = np.where(lucky, 20, 2)
        loss[:, early] = n[:, early] * 0.4      # everyone gives up the usual amount
        loss[:, tenpai] = n[:, tenpai] * 0.1
        place = np.where(lucky, rng.integers(1, 3, seats), rng.integers(3, 5, seats)).astype(float)
        data = fit.add_adjusted({"n": n, "Q loss": loss, "ln p": loss.copy(), "miss": loss.copy(), "place": place,
                                 "game": np.array([f"g{i // 4}" for i in range(seats)]),
                                 "name": np.array([None] * seats, dtype=object), "seat": np.zeros(seats)})
        w = fit.weightings()["Wind-Up Bird, +threat"]
        self.assertLess(fit.spearman(fit.rating(data, "Q loss", w), place), -0.6)        # looks like a fine rating
        self.assertLess(fit.spearman(fit.rating(data, "Q loss usual", w), place), -0.6)  # but it is only the mix
        self.assertTrue(np.allclose(data["Q loss adj"], 0))                               # no decision differs


class FitTest(unittest.TestCase):
    def test_fit_finds_that_tenpai_mistakes_are_the_ones_that_count(self):
        data = synthetic()
        theta = dict(zip(fit.FEATURES, fit.fit_theta(data, "Q loss", np.arange(len(data["place"])))))
        self.assertGreater(theta["tenpai"], 1.0)
        flat = fit.spearman(fit.rating(data, "Q loss", np.ones(len(fit.CELLS))), data["place"])
        fitted = fit.spearman(fit.rating(data, "Q loss", np.exp(fit.Z @ fit.theta_of(theta))), data["place"])
        self.assertLess(fitted, flat - 0.2)

    def test_held_out_gain_is_real_and_its_interval_excludes_zero(self):
        out = fit.cross_validated(synthetic(), "Q loss")
        self.assertLess(out["diff"], -0.2)
        self.assertLess(out["hi"], 0)
        self.assertGreater(out["theta"]["tenpai"], 1.0)

    def test_no_gain_is_reported_when_every_situation_counts_the_same(self):
        rng = np.random.default_rng(2)
        data = synthetic(games=300, seed=5)
        data["place"] = rng.permutation(data["place"])  # the place no longer depends on anything
        out = fit.compare_to_flat(data, "Q loss", fit.weightings()["Wind-Up Bird, +threat"], boot=300)
        self.assertLess(out["lo"], 0)
        self.assertGreater(out["hi"], 0)

    def test_skill_across_games_prefers_the_weighting_that_holds_the_signal(self):
        data = synthetic(games=600, seed=8, players=60)
        # give each player a lasting skill: their tenpai loss and their places move together across games
        names, inv = np.unique(data["name"].astype(str), return_inverse=True)
        skill = np.random.default_rng(1).normal(size=len(names))[inv]
        tenpai = cell(turn=6, shanten=0)
        data["Q loss"][:, tenpai] = np.clip(2.0 - skill, 0, None)
        data["place"] = np.clip(np.round(2.5 - skill + np.random.default_rng(2).normal(0, 1.0, len(skill))), 1, 4)
        fit.add_adjusted(data)
        w = np.ones(len(fit.CELLS))
        w[tenpai] = 50.0
        out = fit.skill(data, "Q loss", w, min_games=20, splits=6, boot=120)
        self.assertEqual(out["players"], 60)
        self.assertLess(out["r"], out["flat"] - 0.1)
        self.assertLess(out["hi"], 0)
        self.assertLess(out["places_per_sd"], 0)
        few = fit.skill(data, "Q loss", w, min_games=10_000)
        self.assertIn("too few", few["note"])


if __name__ == "__main__":
    unittest.main()
