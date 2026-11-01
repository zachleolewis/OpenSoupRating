# Changelog

## 2.1.0: OSR is Round Swing, with every round fully accounted for

OSR's job is to credit what each player did in the matches being rated: one
map, one series or a season. 2.0 instead blended Round Swing with kills,
deaths and damage, weighted to predict a player's results in *other* matches.
That traded accuracy about the match in front of you for long-run prediction,
which is the wrong trade for this rating. 2.1 removes the blend and fills the
gaps that kept Round Swing from adding up.

### What was wrong in 2.0

- **The headline rating described future matches, not this one.** Its weights
  favoured whatever repeats across matches (damage, deaths), so a decisive clutch
  counted for little in the rating of the map it decided.
- **Win probability that moved without a kill went to nobody.** Defenders
  holding as the round clock ran down, attackers sitting on a planted spike, and
  the final resolution of each round (a spike detonating, a failed retake, time
  running out) were unassigned. Mostly that short-changed players whose job is
  to hold and survive rather than take fights.
- **Plants and defuses were not zero-sum.** The planter gained, but nobody on
  the other side lost anything, so team totals didn't match results.
- **No series view, and season aggregates were shrunk by default.** That turned
  "what happened" into "what we'd expect" without being asked.

### What changed

- `rating` is now exactly the player's Round Swing per round: KillSwing +
  AssistSwing + DeathSwing + ObjectiveSwing + HoldSwing. There are no fitted
  weights and no centring.
- **New `HoldSwing` component.** Win probability that moves while no kill or
  objective happens is shared by each side's alive players.
- **Plants and defuses are now zero-sum.** The other side's alive players share
  the plant or defuse they conceded (in `ObjectiveSwing`).
- **Every round is fully accounted for.** Each team's credits sum exactly to
  its round result minus its round-start win probability, and the two teams sum
  to zero.
- **New `find_series()` and `aggregate_ratings(by='series')`, plus
  `osr calculate DIR --series`.** Series are detected from matching rosters
  (4 of 5 players per side) with maps starting within 3 hours of each other. On
  a month of pro matches, this matched an independent series table on all 393
  same-series map pairs.
- `aggregate_ratings()` is descriptive by default. It returns the
  rounds-weighted rating, `rounds_added`, and a luck band (`rating_low` /
  `rating_high`). `shrink=True` (`--shrink`) gives the player-level estimate
  instead. It also accepts any custom grouping: `by={match_id: group}`.
- Per-map results now include `rounds_added`, `plants`, `defuses`, `team`,
  `map_id` and `game_start`. The 2.0-only fields `round_swing` and
  `rating_breakdown` are removed: `rating` *is* Round Swing, and
  `swing_per_round` is its breakdown.

### Validation (2.1 vs 1.1.1)

| | 1.1.1 | 2.1 | (K−D)/round |
|---|---|---|---|
| Team average vs. that map's round differential (r) | 0.909 | **0.975** | 0.949 |
| Map winner has the higher team average | 92.8% | **98.6%** | — |
| Gap between best and worst role average (fraction of map SD) | 0.171 | **0.063** | 0.245 |
| Top 100 season ratings that are duelists (28% of players) | 50 | **40** | 64 |
| Split-half stability (1,597 players with 40+ maps) | **0.676** | 0.598 | 0.750 |
| Predicting held-out map winners (AUC) | 0.610 | 0.610 | 0.626 |

2.1 describes matches more accurately and treats roles more evenly than 1.1.1
or K−D. It is less stable from one set of maps to the next, because clutches
and late-round plays are worth more and don't repeat evenly. Use `shrink=True`
when you want a level estimate.

## 2.0.0 — Round Swing rewrite

OSR 2.0 replaces the 1.x formula. An audit of 1.1.1 against 25,086 professional
maps found bugs that silently corrupted most ratings, plus design problems that
made the number hard to trust or interpret. This release fixes all of them and
re-validates the rating against held-out matches.

**Ratings from 1.x are not comparable with 2.0.** The scale, the inputs and the
calibration data have all changed.

### What was wrong in 1.1.1

#### Bugs

1. **The spike always counted as planted.** Kill and death values checked
   `'plantRoundTime' in round_data`. Riot includes that key (set to `0`) in every
   round, so every kill was scored with post-plant win probabilities, even in
   rounds with no plant. The no-spike tables were never used.
2. **Attackers and defenders were often swapped.** Side detection assumed the
   planter's team defends in the second half, but whoever plants is always
   attacking. A misplaced `return` in the fallback path also took the side from
   the first player in the list. Measured on real matches, sides were backwards
   in **41% of rounds with a plant, 58% of rounds without one, and every
   overtime round**.
3. **Economy categories didn't match the data they looked up.** The code
   bucketed a *single player's* loadout with team-sized thresholds (≤1500,
   ≤4000, ≤7500 …), while `loadout_cost_analysis.json` defined per-player
   ranges (0–800, 801–1600, … 4501+). No player could ever reach "Full Buy": a
   Vandal with heavy shields counted as "Eco Round" and an Operator buy as
   "Force Buy". Every economic modifier looked up the wrong matchup.
4. **ADRa never matched an armor type.** Riot reports armor as an item UUID,
   not `"Light"`/`"Heavy"`, so expected damage per kill was always 100.
5. **pip installs could not find their data.** The calibration JSON lived in
   the repository's top-level `data/` folder, outside the package, and was never
   included in the wheel. An installed copy raised `FileNotFoundError` on the
   first rating.
6. Smaller issues:
   - The X-v-0 outcome adjustment read `roundEndReason`, which doesn't exist (Riot's field is `roundResultCode`), so it never ran.
   - KillContrib never copied `finishingDamage`, so spike deaths were never skipped.
   - Suicides and team kills didn't reduce the alive count.
   - Net impact was divided by the kill standard deviation instead of its own.
   - The README normalization numbers didn't match `normalization_params.json`.
   - A `DEBUG` line was printed for every player.

#### Design problems

- **Win probability ignored most of the round.** It used only alive counts and
  spike yes/no. A no-plant 2v1 with 5 seconds left was valued the same as one
  with 80 seconds left, and loadouts and maps were ignored.
- **The economy multiplier was bolted on.** `ΔWP × 2(1 − p)` turned a
  probability into an unexplained unit and partly double-counted what a better
  win-probability state should capture.
- **The killer got 100% of every kill.** Teammates' damage, flashes and traded
  deaths earned nothing in the impact part. APR and ADRa tried to add that back
  separately, which counted the same damage up to three times.
- **Units were mixed.** Kill/death impact was a per-match total, so long and
  overtime maps inflated it, while APR and ADRa were per round.
- **The weights had no stated target and no validation.**
- **No uncertainty.** A single map's rating is mostly noise, and averages over
  a few maps were treated as exact.
- **No role context.**

### What's new in 2.0

- **A fitted round win probability model** (`wp_model.json`): a logistic model
  over every alive-count × spike cell. Each cell has its own curve over time
  left (round timer before the plant, spike timer after), plus the loadout value
  still alive and the map. On the newest 20% of maps, held out from fitting,
  log loss is **0.452, against 0.491 for the 1.1.1 table as shipped**.
- **Round Swing**: every kill, death, plant and defuse is credited with the
  change in round win probability it caused. A kill's gain is split between the
  killer (50 + their damage), teammates who damaged the victim (their damage),
  utility-only assisters (30) and teammates the victim had just killed, i.e.
  traded deaths within 3 s (30). The victim is charged the full loss. Kills are
  zero-sum.
- **OSR** combines the four Round Swing components (kill, assist, death,
  objective) with kills, deaths and damage dealt/taken. Each input is weighted
  by how well it predicts the player's Round Swing in *other* matches. Both OSR
  and the raw Round Swing are reported in the same unit: percentage points of a
  round won per round, with 0 = average.
- **`aggregate_ratings()`** and `osr calculate DIR --aggregate`: per-player
  ratings across matches, shrunk toward average by rounds played, with a 90%
  interval. One map moves a player's estimate only a little; about 200 rounds
  count as much as the prior.
- **Role baselines** (`role_adjusted_rating`) from agent roles.
- **`tools/calibrate.py`** refits everything from any folder of Riot match
  JSON (`.json` or `.json.gz`). It supports a held-out score (`--holdout`) and
  date cut-offs for backtests (`--before`).
- Fixed ADRa armor handling. Data files now ship inside the package. Observers
  are excluded everywhere. The loader reads `.json.gz`.

### Validation

Everything was fitted on maps before 2026-04-06 and tested on the 5,018 maps
after it.

| | 1.1.1 | 2.0 OSR | 2.0 Round Swing | (K−D)/round |
|---|---|---|---|---|
| Split-half reliability (1,597 players with 40+ maps) | 0.676 | **0.733** | 0.593 | 0.750 |
| Predicting held-out map winners from earlier ratings (AUC) | 0.610 | **0.619** | 0.594 | 0.626 |
| Team average vs same-map round differential (r) | 0.909 | **0.940** | 0.922 | 0.949 |

95% bootstrap intervals for 2.0 OSR minus 1.1.1:
- Reliability: +0.057 [+0.037, +0.078]
- AUC: +0.009 [0.000, +0.018]

How to read this:
- OSR 2.0 beats 1.1.1 on every measure.
- Raw Round Swing is the most faithful record of what happened, but it is
  noisier. That is why OSR also weights the more stable inputs.
- Plain (K−D)/round is still slightly more stable and slightly more predictive
  than OSR (−0.018 reliability, −0.007 AUC; both intervals exclude zero). No
  per-match formula tried here beat it on prediction. The next lever is
  adjusting for opponent strength.

### Breaking changes

- Components `KillContrib` and `DeathContrib` are replaced by `KillSwing`,
  `AssistSwing`, `DeathSwing` and `ObjectiveSwing`. `APR` and `ADRa` are still
  reported but are not part of the rating.
- `weights` and `normalization_params` are ignored, with a `DeprecationWarning`.
  The CLI options `-w` and `-n` are removed.
- `data/weights.json`, `data/normalization_params.json`, `data/xvx_data.json`
  and `data/loadout_cost_analysis.json` are removed. Calibration now lives in
  `open_soup_rating/data/`.
- Default calibration is now 25,086 professional maps (VCT, Challengers, Game
  Changers; patches 8.00–13.08) instead of NA Premier. To rate a different
  population, run `tools/calibrate.py` on your own matches.
