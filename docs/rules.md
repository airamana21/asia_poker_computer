# Asia Poker 4 2 1 rules and evaluator spec

Source backed summary of the common casino rules and the exact evaluator behavior this app will implement. Primary citations are listed in [docs/sources.md](docs/sources.md).

## Deck
- 53 cards: standard 52 card deck plus a single Joker.
- Joker behavior: may be used as an Ace, or to complete a straight, a flush, or a straight flush. Otherwise it plays as an Ace. This mirrors Pai Gow style Joker usage per casino rules.
- Suits have no rank.

## Hand structure
- A 7 card hand is arranged into three hands: 4 card high, 2 card medium, 1 card low.
- Strength order must be descending: 4 card ≥ 2 card ≥ 1 card. Any setting that violates this order is a foul and loses.
- Copy hands against the dealer push for that sub hand.

## 4 card hand rankings
High to low with tie breakers. Aces may be high or low for straights. Suits never break ties.
1. Straight flush: four consecutive ranks all same suit. Tie break by top card rank, then next highest if needed. A234 is the lowest straight.
2. Four of a kind: four cards of same rank. Tie break by rank of quads, then kicker rank if comparing mixed Joker cases that still yield a valid 4 of a kind.
3. Flush: four cards same suit. Tie break by highest rank, then next highest down to the 4th.
4. Straight: four consecutive ranks any suits. Tie break by top card rank, then next highest if needed. A234 is the lowest straight.
5. Three of a kind: three of same rank plus a kicker. Tie break by trip rank then kicker rank.
6. Two pair: tie break by higher pair rank, then lower pair rank, then kicker rank.
7. One pair: tie break by pair rank, then highest kicker, then next kicker.
8. High card: compare highest to lowest.

Joker handling in 4 card hands:
- First use the Joker to complete a straight flush, flush, or straight if possible.
- If none is possible, count the Joker as an Ace and evaluate normally. It cannot act as a fully wild card to make a four of a kind unless a straight or flush usage is also attainable by suit or sequence rules above.

## 2 card hand rankings
- Pair > High card.
- For pair vs pair, compare pair rank.
- For high card, compare highest then lowest.
- Joker in 2 card hands: counts as Ace only.

## 1 card hand rankings
- High card only, by rank. Joker counts as Ace.

## Ties and pushes
- If a player sub hand and the dealer corresponding sub hand are identical by rank and all tie breakers, that sub hand is a push.
- Overall result is win if at least two sub hands are wins, loss if at least two are losses, otherwise push.

## Dealer house way summary
Exact step by step house way varies by jurisdiction. We will encode a widely published casino House Way that follows these principles, aligning with Massachusetts Gaming Commission and common casino rack cards:
- Always set to avoid fouls 4 ≥ 2 ≥ 1.
- Use the Joker to complete a straight flush, flush, or straight in the high hand when it does not weaken the medium and low hands below the required order; otherwise treat as Ace.
- With strong made hands in the 4 card hand e.g., four of a kind, high straights flushes, split only when necessary to satisfy the order or to improve combined outcomes per published rules.
- When no pair or better is available, maximize the 4 card strength while keeping the 2 card and 1 card in descending order.

The specific, citation backed decision tree implemented for the dealer will be maintained in [docs/sources.md](docs/sources.md) and the code comments in [src/core/house_way.py](src/core/house_way.py).

## Evaluator objective
- The app searches across all 4 2 1 partitions of the player 7 cards and selects the partition that maximizes the probability of winning at least two of three sub hands versus a dealer who sets by the House Way.
- Probability is estimated by Monte Carlo sampling of the dealer 7 card hand from the remaining deck, with shared samples across all player partitions for performance.

## Implementation notes for engineers
- Ranking comparators and canonical score tuples will be implemented in [src/core/ranks.md](src/core/ranks.md) spec and the code at [src/core/ranks.py](src/core/ranks.py).
- A foul check helper compares 4 vs 2 vs 1 using the same total ordering as the comparators.
- Joker logic is centralized so all evaluators are consistent.
