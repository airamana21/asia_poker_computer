from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

# Suits and ranks
SUITS = ("S", "H", "D", "C")  # Spades, Hearts, Diamonds, Clubs
RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
JOKER = "XJ"  # Joker id

RANK_TO_VAL = {r: i + 2 for i, r in enumerate(RANKS)}  # 2..14 (A=14)
VAL_TO_RANK = {v: r for r, v in RANK_TO_VAL.items()}


@dataclass(frozen=True)
class Card:
    rank: str  # "2".."10","J","Q","K","A" or "XJ" for Joker
    suit: Optional[str]  # "S","H","D","C" or None for Joker

    def __post_init__(self):
        if self.rank == JOKER:
            object.__setattr__(self, "suit", None)
        else:
            assert self.rank in RANKS, f"Invalid rank: {self.rank}"
            assert self.suit in SUITS, f"Invalid suit: {self.suit}"

    def id(self) -> str:
        return self.rank if self.rank == JOKER else f"{self.rank}{self.suit}"

    def __str__(self) -> str:
        return self.id()

    def is_joker(self) -> bool:
        return self.rank == JOKER

    @property
    def val(self) -> int:
        if self.rank == JOKER:
            return RANK_TO_VAL["A"]  # treat as Ace value by default
        return RANK_TO_VAL[self.rank]


def parse(card_id: str) -> Card:
    """Parse an id like AS, TD, 9H, 2C, or XJ for the Joker."""
    s = card_id.strip().upper()
    if s == JOKER:
        return Card(JOKER, None)
    # 10 is two chars; others 1
    if s[:-1] == "10":
        rank = "10"
        suit = s[-1]
    else:
        rank, suit = s[:-1], s[-1]
    if rank not in RANKS:
        raise ValueError(f"Bad card rank: {rank}")
    if suit not in SUITS:
        raise ValueError(f"Bad suit: {suit}")
    return Card(rank, suit)


def full_deck(include_joker: bool = True) -> List[Card]:
    deck: List[Card] = [Card(r, s) for s in SUITS for r in RANKS]
    if include_joker:
        deck.append(Card(JOKER, None))
    return deck


def remaining_deck(exclude: Sequence[Card], include_joker: bool = True) -> List[Card]:
    excl = {c.id() for c in exclude}
    return [c for c in full_deck(include_joker) if c.id() not in excl]


def sort_desc(cards: Sequence[Card]) -> List[Card]:
    return sorted(cards, key=lambda c: (c.val, c.suit or "Z"), reverse=True)


# Pretty strings for UI
SUIT_SYMBOL = {"S": "♠", "H": "♥", "D": "♦", "C": "♣", None: ""}
RANK_LABEL = {**{r: r for r in RANKS}, JOKER: "Joker"}


def label(card: Card) -> str:
    if card.rank == JOKER:
        return "Joker"
    return f"{card.rank}{SUIT_SYMBOL[card.suit]}"


# Filename for PNG assets

def png_name(card: Card) -> str:
    return f"{card.id()}.png"
